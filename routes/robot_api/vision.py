from flask import Blueprint, request, jsonify, current_app
import boto3
from werkzeug.utils import secure_filename
import uuid

# 상위 폴더(ddalgi_backend)의 모듈 가져오기
from ddalgi_models import db, CropLog
from ddalgi_mqtt_handler import publish_message

# 'vision_bp' 블루프린트 생성
vision_bp = Blueprint('vision', __name__)

# ---------------------------------------------------------
# API 엔드포인트: 로봇 작물 이미지 S3 업로드 및 DB 로깅
# ---------------------------------------------------------
@vision_bp.route('/api/upload_crop', methods=['POST'])
def upload_crop_image():
    # 1. 파일이 요청에 포함되어 있는지 확인
    if 'image' not in request.files:
        return jsonify({"status": "error", "message": "이미지 파일이 없습니다."}), 400
        
    file = request.files['image']
    if file.filename == '':
        return jsonify({"status": "error", "message": "선택된 파일이 없습니다."}), 400

    # 2. 로봇이 폼 데이터(multipart/form-data)로 같이 보낸 텍스트들
    user_id = request.form.get('user_id')
    robot_id = request.form.get('robot_id')
    crop_id = request.form.get('crop_id')
    status = request.form.get('status')
    zone_id = request.form.get('zone_id')

    if not user_id or not robot_id:
        return jsonify({"status": "error", "message": "필수 파라미터 누락"}), 400

    try:
        # 3. AWS S3 클라이언트 셋팅 (⭐️ current_app.config 사용!)
        s3 = boto3.client(
            's3',
            aws_access_key_id=current_app.config['AWS_ACCESS_KEY_ID'],
            aws_secret_access_key=current_app.config['AWS_SECRET_ACCESS_KEY'],
            region_name=current_app.config['AWS_REGION']
        )
        
        # 4. 파일 이름 겹침 방지를 위해 고유한 이름 생성
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        
        # 5. S3에 파일 업로드
        s3.upload_fileobj(
            file,
            current_app.config['S3_BUCKET_NAME'],
            unique_filename,
            ExtraArgs={'ContentType': file.content_type}
        )
        
        # 6. S3 이미지 URL 주소 생성
        image_url = f"https://{current_app.config['S3_BUCKET_NAME']}.s3.{current_app.config['AWS_REGION']}.amazonaws.com/{unique_filename}"
        
        # 7. DB(CropLog)에 저장
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
        
        # 8. 만약 상태가 'disease'라면 즉시 앱으로 알람(사진 포함) 발송!
        if status == 'disease':
            alert_data = {
                'log_id': new_log.log_id,
                'user_id': user_id,
                'robot_id': robot_id,
                'zone': zone_id,
                'crop': crop_id,
                'status': status,
                'message': f"{zone_id} 구역에서 문제가 발견되었습니다!",
                'image_url': image_url  
            }
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
# 테스트용 API (AI 감지 가상 테스트)
# ---------------------------------------------------------
@vision_bp.route('/test_alert', methods=['GET'])
def test_alert():
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
    
    publish_message("ddalgi/alert/disease/test_user", alert_data)
    
    return jsonify({"status": "success", "message": "앱으로 알람 발송을 지시했습니다."})