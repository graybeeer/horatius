from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

from ddalgi_models import db, User, EnvLog, CropLog, Robot
from ddalgi_mqtt_handler import init_mqtt, publish_message
from datetime import datetime

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
            "crop_type": log.crop_type,
            "status": log.status,
            "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        })
        
    return jsonify({
        "status": "success", 
        "data": result
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
    # Robot 테이블이 쿼리되려면 맨 위 import 영역에 Robot 모델도 추가해야 합니다.
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
    # 💡 팁: 전체 로봇이 아닌 '특정 로봇'만 명령을 받도록 토픽에 로봇 ID를 넣는 것이 좋습니다.
    topic = f"ddalgi/robot/{robot_id}/command"
    publish_message(topic, mqtt_message)
    
    # 5. 앱에게 정상 처리되었음을 응답
    return jsonify({
        "status": "success", 
        "message": f"{robot_id} 로봇에 '{command}' 명령을 안전하게 전송했습니다."
    }), 200
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
        "message": "병충해가 발견되었습니다!"
    }
    
    # 🚀 2. 분리해둔 도우미 함수를 이용해 아주 간단하게 MQTT 메시지 발행(Pub)
    publish_message("ddalgi/alert/disease", alert_data)
    
    return jsonify({"status": "success", "message": "앱으로 알람 발송을 지시했습니다."})
if __name__ == '__main__':
    init_mqtt(app, db)  
    # 안드로이드 등 외부 기기에서 접속할 수 있도록 host='0.0.0.0' 설정
    app.run(host='0.0.0.0', port=12345,debug=True)