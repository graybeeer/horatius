from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

from ddalgi_models import db, User, EnvLog, CropLog, Robot, Zone
from ddalgi_mqtt_handler import init_mqtt, publish_message
from datetime import datetime
import boto3
from werkzeug.utils import secure_filename
import uuid

'''
서버 실행 및 안드로이드 앱 통신용 API(로그인, 명령, 조회)를 전담
'''
app = Flask(__name__)

# DB 설정
app.config.from_object('ddalgi_config.Config')

# 불러온 db 객체에 현재 플라스크 앱(app)을 연동시킵니다.
db.init_app(app)

# 서버 실행 시 테이블이 없으면 자동 생성
with app.app_context():
    db.create_all()


# ---------------------------------------------------------
# API 엔드포인트: 회원가입 (/signup)
# ---------------------------------------------------------
@app.route('/signup', methods=['POST'])
def signup():
    # 안드로이드 앱에서 보낸 JSON 데이터 받기
    data = request.get_json()
    
    user_id = data.get('user_id')
    password = data.get('password')
    name = data.get('name')
    phone_number = data.get('phone_number')
    country = data.get('country')
    email = data.get('email')

    # 필수 값이 빠져있는지 확인
    if not user_id or not password or not name or not phone_number or not email:
        return jsonify({"status": "error", "message": "필수 정보를 모두 입력해주세요."}), 400

    # 이미 존재하는 아이디인지 확인
    existing_user = User.query.filter_by(user_id=user_id).first()
    if existing_user:
        return jsonify({"status": "error", "message": "이미 존재하는 아이디입니다."}), 409

    # 비밀번호 암호화 (보안 처리)
    hashed_password = generate_password_hash(password)

    # 새 사용자 객체 생성 및 DB에 저장
    new_user = User(
        user_id=user_id, 
        password=hashed_password, 
        name=name, 
        phone_number=phone_number, 
        country=country,
        email=email 
    )
    
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"status": "success", "message": "회원가입이 완료되었습니다."}), 201

# ---------------------------------------------------------
# API 엔드포인트: 로그인 (/login)
# ---------------------------------------------------------
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    
    user_id = data.get('user_id')
    password = data.get('password')

    if not user_id or not password:
        return jsonify({"status": "error", "message": "아이디와 비밀번호를 입력해주세요."}), 400

    # DB에서 사용자 검색
    user = User.query.filter_by(user_id=user_id).first()

    # 사용자가 존재하고, 비밀번호가 일치하는지 확인 (해시 비교)
    if user and check_password_hash(user.password, password):
        return jsonify({
            "status": "success", 
            "message": f"{user.name}님 환영합니다!",
            "data": {
                "user_id": user.user_id,
                "name": user.name
            }
        }), 200
    else:
        return jsonify({"status": "error", "message": "아이디 또는 비밀번호가 잘못되었습니다."}), 401
# ---------------------------------------------------------
# API 엔드포인트: 신규 로봇 등록 API
# ---------------------------------------------------------
@app.route('/api/robot/register', methods=['POST'])
def register_robot():
    # 1. 앱에서 보낸 JSON 데이터 받기
    data = request.get_json()
    
    # 2. 필수 데이터 누락 검사
    if not data or 'robot_id' not in data or 'user_id' not in data:
        return jsonify({
            "status": "error", 
            "message": "robot_id와 user_id는 필수 항목입니다."
        }), 400

    robot_id = data['robot_id']
    user_id = data['user_id']
    
    # 3. 중복 검사: 이미 DB에 있는 로봇인지 확인
    existing_robot = Robot.query.filter_by(robot_id=robot_id).first()
    
    if existing_robot:
        # HTTP 409(Conflict)는 데이터 충돌(중복)이 발생했을 때 쓰는 표준 코드입니다.
        return jsonify({
            "status": "error", 
            "message": "이미 등록된 로봇 기기입니다."
        }), 409

    try:
        # 4. 새로운 로봇 생성 및 초기값 세팅
        new_robot = Robot(
            robot_id=robot_id,
            user_id=user_id,
            operating_status='OFFLINE',  # 처음 등록하면 꺼져있는 상태로 시작
            battery=100                  # (선택) 초기 배터리를 100으로 세팅
        )
        
        # 5. DB에 저장
        db.session.add(new_robot)
        db.session.commit()
        
        return jsonify({
            "status": "success", 
            "message": f"로봇({robot_id})이 성공적으로 등록되었습니다."
        }), 201  # HTTP 201(Created)은 데이터가 새로 생성되었을 때 쓰는 성공 코드입니다.
        
    except Exception as e:
        db.session.rollback()  # 에러가 나면 하던 작업을 취소(롤백)해서 DB 고장을 막습니다.
        return jsonify({
            "status": "error", 
            "message": f"서버 오류로 로봇 등록에 실패했습니다: {str(e)}"
        }), 500
# ---------------------------------------------------------
# API 엔드포인트: 주기적 환경 및 통계 데이터 조회 (/api/env_logs)
# ---------------------------------------------------------
@app.route('/api/env_logs', methods=['GET'])
def get_env_logs():
    # URL 쿼리 파라미터에서 user_id 가져오기 (예: ?user_id=U001)
    user_id = request.args.get('user_id')
    
    if not user_id:
        return jsonify({"status": "error", "message": "user_id 파라미터가 필요합니다."}), 400

    # 해당 사용자의 최신 로그 10개를 시간 역순(최신순)으로 가져오기
    logs = EnvLog.query.filter_by(user_id=user_id).order_by(EnvLog.timestamp.desc()).limit(10).all()
    
    result = []
    for log in logs:
        result.append({
            "log_id": log.log_id,
            "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S"), # 시간 포맷팅
            "temperature": log.temperature,
            "humidity": log.humidity,
            "ripe_count": log.ripe_count,
            "unripe_count": log.unripe_count,
            "disease_count": log.disease_count
        })
        
    return jsonify({
        "status": "success", 
        "data": result
    }), 200

# ---------------------------------------------------------
# API 엔드포인트: 작물 이상 상태 촬영 로그 조회 (/api/crop_logs)
# ---------------------------------------------------------
@app.route('/api/crop_logs', methods=['GET'])
def get_crop_logs():
    user_id = request.args.get('user_id')
    
    if not user_id:
        return jsonify({"status": "error", "message": "user_id 파라미터가 필요합니다."}), 400

    # 해당 사용자의 최신 작물 촬영 로그 10개 조회
    logs = CropLog.query.filter_by(user_id=user_id).order_by(CropLog.timestamp.desc()).limit(10).all()
    
    result = []
    for log in logs:
        result.append({
            "log_id": log.log_id,
            "robot_id": log.robot_id,
            "zone_id": log.zone_id,
            "crop_id": log.crop_id,
            "status": log.status,
            "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        })
        
    return jsonify({
        "status": "success", 
        "data": result
    }), 200
# ---------------------------------------------------------
# API 엔드포인트: 특정 로봇의 현재 상태 조회 API (보안 적용)
# ---------------------------------------------------------
@app.route('/api/robot/status/<robot_id>', methods=['GET'])
def get_robot_status(robot_id):
    # 1. 앱에서 보낸 유저 ID 꺼내기 (예: ?user_id=U001)
    request_user_id = request.args.get('user_id')
    
    if not request_user_id:
        return jsonify({"status": "error", "message": "요청자(user_id) 정보가 없습니다."}), 400

    # 2. DB에서 로봇 정보 조회
    robot = Robot.query.filter_by(robot_id=robot_id).first()
    
    if not robot:
        return jsonify({"status": "error", "message": "등록되지 않은 로봇입니다."}), 404

    # 3. 권한 체크 
    # DB에 적힌 로봇의 진짜 주인(robot.user_id)과 지금 요청한 사람(request_user_id)이 다르면 차단
    if robot.user_id != request_user_id:
        # HTTP 403 상태 코드는 'Forbidden(접근 금지)'을 의미하는 국제 표준입니다.
        return jsonify({"status": "error", "message": "이 로봇을 조회할 권한이 없습니다."}), 403

    # 4. 통신 끊김(OFFLINE) 자동 판별 로직 (이전과 동일)
    current_time = datetime.now()
    final_status = robot.operating_status 
    
    if robot.last_updated:
        time_diff = (current_time - robot.last_updated).total_seconds()
        if time_diff > 30:
            final_status = 'OFFLINE'
    else:
        final_status = 'OFFLINE'

    # 5. 앱으로 전달할 데이터 포장
    return jsonify({
        "status": "success",
        "data": {
            "robot_id": robot.robot_id,
            "operating_status": final_status, 
            "battery": robot.battery,
            "last_marker_id": robot.last_marker_id,
            "lat": robot.lat,
            "lng": robot.lng,
            "last_updated": robot.last_updated.strftime('%Y-%m-%d %H:%M:%S') if robot.last_updated else None
        }
    }), 200
# ---------------------------------------------------------
# API 엔드포인트: 로봇 제어 명령 (앱 -> 서버 -> 로봇)
# ---------------------------------------------------------
@app.route('/api/robot_command', methods=['POST'])
def robot_command():
    data = request.get_json()
    
    # 앱에서 보낸 데이터 추출
    user_id = data.get('user_id')
    robot_id = data.get('robot_id')
    command = data.get('command')      # 예: "start_patrol", "stop", "return_home"
    target_zone = data.get('zone_id')  # 예: "A1" (어디로 순찰 갈지 - 옵션)
    
    # 1. 필수 데이터 누락 확인
    if not user_id or not robot_id or not command:
        return jsonify({"status": "error", "message": "필수 파라미터가 누락되었습니다."}), 400
        
    # 2. (보안 검증) DB에서 이 로봇이 해당 사용자의 소유가 맞는지 확인
    robot = Robot.query.filter_by(robot_id=robot_id, user_id=user_id).first()
    if not robot:
        return jsonify({"status": "error", "message": "권한이 없거나 존재하지 않는 로봇입니다."}), 403
        
    # 3. 로봇에게 보낼 MQTT 메시지(명령어) 구성
    mqtt_message = {
        "command": command,
        "target_zone": target_zone,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # 4. 지정된 로봇 전용 토픽으로 메시지 발행 (Pub)
    # 전체 로봇이 아닌 '특정 로봇'만 명령을 받도록 토픽에 로봇 ID를 넣는 것이 좋습니다.
    topic = f"ddalgi/robot/{robot_id}/command"
    publish_message(topic, mqtt_message)
    
    # 5. 앱에게 정상 처리되었음을 응답
    return jsonify({
        "status": "success", 
        "message": f"{robot_id} 로봇에 '{command}' 명령을 안전하게 전송했습니다."
    }), 200
# ---------------------------------------------------------
# API 엔드포인트: 구역(Zone) 등록 및 수정 API
# ---------------------------------------------------------
@app.route('/api/zone/setup', methods=['POST'])
def setup_zone():
    # 1. 앱에서 보낸 구역 데이터(JSON) 받기
    data = request.get_json()
    
    # 2. 필수 데이터 누락 검사
    if not data or 'zone_id' not in data or 'user_id' not in data or 'zone_name' not in data:
        return jsonify({
            "status": "error", 
            "message": "zone_id, user_id, zone_name은 필수 항목입니다."
        }), 400

    zone_id = data['zone_id']
    user_id = data['user_id']
    
    try:
        # 3. DB에 이미 만들어진 구역인지 확인
        # (남의 구역을 덮어쓰면 안 되므로 user_id도 함께 조건으로 줍니다)
        zone = Zone.query.filter_by(zone_id=zone_id, user_id=user_id).first()
        
        # 만약 DB에 없다면 새 구역 객체 생성!
        if not zone:
            zone = Zone(zone_id=zone_id, user_id=user_id)
            db.session.add(zone)
            action_msg = "등록"
        else:
            action_msg = "수정"

        # 4. 하이브리드 구역 정보 업데이트 (있는 데이터만 덮어쓰기)
        zone.zone_name = data.get('zone_name', zone.zone_name)
        #zone.main_crop = data.get('main_crop', zone.main_crop)
        
        # 실내용: 마커 번호 리스트 (예: "1,2,3,4,5")
        zone.marker_list = data.get('marker_list', zone.marker_list)
        
        # 실외용: GPS 사각형 범위
        zone.min_lat = data.get('min_lat', zone.min_lat)
        zone.max_lat = data.get('max_lat', zone.max_lat)
        zone.min_lng = data.get('min_lng', zone.min_lng)
        zone.max_lng = data.get('max_lng', zone.max_lng)
        
        # 5. DB에 최종 저장
        db.session.commit()
        
        return jsonify({
            "status": "success", 
            "message": f"'{zone.zone_name}' 구역이 성공적으로 {action_msg}되었습니다."
        }), 200
        
    except Exception as e:
        db.session.rollback() # 에러 발생 시 DB 원상복구
        return jsonify({
            "status": "error", 
            "message": f"서버 오류로 구역 설정에 실패했습니다: {str(e)}"
        }), 500
# ---------------------------------------------------------
# API 엔드포인트: 로봇 작물 이미지 S3 업로드 및 DB 로깅 (/api/upload_crop)
# ---------------------------------------------------------
@app.route('/api/upload_crop', methods=['POST'])
def upload_crop_image():
    # 1. 파일이 요청에 포함되어 있는지 확인
    if 'image' not in request.files:
        return jsonify({"status": "error", "message": "이미지 파일이 없습니다."}), 400
        
    file = request.files['image']
    if file.filename == '':
        return jsonify({"status": "error", "message": "선택된 파일이 없습니다."}), 400

    # 2. 로봇이 함께 보낸 텍스트 데이터들 (multipart/form-data 형식)
    user_id = request.form.get('user_id')
    robot_id = request.form.get('robot_id')
    crop_id = request.form.get('crop_id')
    status = request.form.get('status')
    zone_id = request.form.get('zone_id')

    if not user_id or not robot_id:
        return jsonify({"status": "error", "message": "필수 파라미터 누락"}), 400

    try:
        # 3. AWS S3 클라이언트 셋팅
        s3 = boto3.client(
            's3',
            aws_access_key_id=app.config['AWS_ACCESS_KEY_ID'],
            aws_secret_access_key=app.config['AWS_SECRET_ACCESS_KEY'],
            region_name=app.config['AWS_REGION']
        )
        
        # 4. 파일 이름 겹침 방지를 위해 고유한 이름 생성 (안전한 파일명 + 난수)
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        
        # 5. S3에 파일 업로드
        s3.upload_fileobj(
            file,
            app.config['S3_BUCKET_NAME'],
            unique_filename,
            ExtraArgs={'ContentType': file.content_type} # 웹에서 바로 보이도록 타입 지정
        )
        
        # 6. 업로드된 파일의 접속 주소(URL) 생성
        image_url = f"https://{app.config['S3_BUCKET_NAME']}.s3.{app.config['AWS_REGION']}.amazonaws.com/{unique_filename}"
        
        # 7. DB(CropLog)에 데이터와 이미지 주소 함께 저장
        new_log = CropLog(
            user_id=user_id,
            robot_id=robot_id,
            crop_id=crop_id,  
            status=status,
            zone_id=zone_id,
            image_url=image_url
        )
        db.session.add(new_log)
        db.session.commit()
        
        # 만약 상태가 'disease'라면 즉시 앱으로 알람(사진 포함) 발송!
        if status == 'disease':
            alert_data = {
                'log_id': new_log.log_id, # 방금 저장된 실제 DB 로그 번호
                'user_id': user_id,
                'robot_id': robot_id,
                'zone': zone_id,
                'crop': crop_id,
                'status': status,
                'message': f"{zone_id} 구역에서 문제가 발견되었습니다!",
                'image_url': image_url  # S3에 올라간 사진 주소!
            }
            # MQTT로 앱에 알람 쏘기 (ddalgi_mqtt_handler.py에 있는 함수 사용)
            target_topic = f"ddalgi/alert/disease/{user_id}"
            publish_message(target_topic, alert_data)
        
        return jsonify({
            "status": "success", 
            "message": "이미지 업로드 및 로깅 완료",
            "image_url": image_url
        }), 200
        
    except Exception as e:
        return jsonify({"status": "error", "message": f"업로드 실패: {str(e)}"}), 500
# ---------------------------------------------------------
# 테스트용 API: AI가 병충해를 감지했다고 가정하고 앱으로 알람 보내기
# ---------------------------------------------------------
@app.route('/test_alert', methods=['GET'])
def test_alert():
    # 보낼 데이터 세팅
    alert_data = {
        'log_id': 'log_001',
        'user_id': 'test_user',
        'robot_id': 'robot_001',
        'timestamp': '2024-06-01T12:00:00Z',
        "zone": "A1",
        "crop": "딸기",
        "status": "disease",
        "message": "병충해가 발견되었습니다!",
        "image_url": "https://본인의_버킷_이름.s3.ap-northeast-2.amazonaws.com/sample_image.jpg"
    }
    
    # 2. 분리해둔 함수를 이용해 MQTT 메시지 발행(Pub)
    publish_message("ddalgi/alert/disease", alert_data)
    
    return jsonify({"status": "success", "message": "앱으로 알람 발송을 지시했습니다."})
if __name__ == '__main__':
    init_mqtt(app, db)  
    # 안드로이드 등 외부 기기에서 접속할 수 있도록 host='0.0.0.0' 설정
    app.run(host='0.0.0.0', port=12345,debug=True)