from flask import Blueprint, request, jsonify, current_app
import boto3
from werkzeug.utils import secure_filename
import uuid
from datetime import datetime

# 상위 폴더(ddalgi_backend)의 모듈 가져오기
from ddalgi_models import db, CropLog, ZoneBatch
from ddalgi_mqtt_handler import publish_message

# 'vision_bp' 블루프린트 생성
vision_bp = Blueprint('vision', __name__)
# ---------------------------------------------------------
# 작물 사진(선택) S3 업로드, 생육 데이터 DB 저장(Upsert) 및 질병 감지 시 실시간 앱 알림을 처리하는 API
# ---------------------------------------------------------
@vision_bp.route('/api/upload/crop', methods=['POST'])
def upload_crop_image():
    # 1. 파일이 있는지 부드럽게 확인 (없어도 에러를 내지 않고 None으로 받음)
    file = request.files.get('image')
    has_image = file and file.filename != ''

    # 2. 로봇이 폼 데이터(multipart/form-data)로 같이 보낸 텍스트들
    user_id = request.form.get('user_id')
    robot_id = request.form.get('robot_id')
    crop_id = request.form.get('crop_id')
    health_status = request.form.get('health_status')
    zone_id = request.form.get('zone_id')
    
    provided_batch_id = request.form.get('batch_id')
    growth_status_str = request.form.get('growth_status', '0.0')
    try:
        growth_status = float(growth_status_str)
    except ValueError:
        growth_status = 0.0

    if not user_id or not robot_id:
        return jsonify({"status": "error", "message": "필수 파라미터 누락"}), 400

    try:
        image_url = None # 이미지가 없을 경우를 대비해 기본값을 None으로 설정

        # 3. 이미지가 실제로 전송되었을 때만 AWS S3 업로드 로직 실행
        if has_image:
            s3 = boto3.client(
                's3',
                aws_access_key_id=current_app.config['AWS_ACCESS_KEY_ID'],
                aws_secret_access_key=current_app.config['AWS_SECRET_ACCESS_KEY'],
                region_name=current_app.config['AWS_REGION']
            )
            
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4().hex}_{filename}"
            
            s3.upload_fileobj(
                file,
                current_app.config['S3_BUCKET_NAME'],
                unique_filename,
                ExtraArgs={'ContentType': file.content_type}
            )
            
            image_url = f"https://{current_app.config['S3_BUCKET_NAME']}.s3-{current_app.config['AWS_REGION']}.amazonaws.com/{unique_filename}"
        
        # 4. DB(CropLog)에 저장 (이미지가 없으면 image_url에 None이 들어감)
        new_log = CropLog(
            user_id=user_id,
            robot_id=robot_id,
            crop_id=crop_id,  
            growth_status=growth_status, 
            health_status=health_status,
            zone_id=zone_id,
            image_url=image_url 
        )
        db.session.add(new_log)

        # 5. ZoneBatch에 데이터 갱신 (Upsert 로직)
        if zone_id and crop_id:
            existing_batch = None
            final_batch_id = None
            
            if provided_batch_id:
                existing_batch = ZoneBatch.query.filter_by(batch_id=provided_batch_id).first()
                final_batch_id = provided_batch_id
            else:
                time_str = datetime.now().strftime("%Y%m%d%H%M%S")
                final_batch_id = f"{zone_id}_{time_str}_{uuid.uuid4().hex[:4]}"
            
            disease_name_val = "확인 필요(사진 참고)" if health_status and health_status.lower() == 'disease' else None

            if existing_batch:
                existing_batch.crop_id = crop_id
                existing_batch.growth_status = growth_status
                existing_batch.health_status = health_status
                existing_batch.disease_name = disease_name_val
                print(f"🔄 [작물 담당] 기존 재배 데이터 갱신 완료 (ID: {final_batch_id})")
            else:
                new_batch = ZoneBatch(
                    batch_id=final_batch_id,
                    zone_id=zone_id,
                    crop_id=crop_id,
                    growth_status=growth_status,
                    health_status=health_status,
                    disease_name=disease_name_val
                )
                db.session.add(new_batch)
                print(f"🌱 [작물 담당] 새 재배 데이터 추가 완료 (ID: {final_batch_id})")

        db.session.commit()
        
        # 6. 만약 상태가 'disease'라면 즉시 앱으로 알람 발송
        if health_status == 'disease':
            alert_data = {
                'log_id': new_log.log_id,
                'user_id': user_id,
                'robot_id': robot_id,
                'zone': zone_id,
                'crop': crop_id,
                'growth_status': growth_status,
                'health_status': health_status,
                'message': f"{zone_id} 구역에서 문제가 발견되었습니다!",
                'image_url': image_url  # 이미지가 없으면 null로 전송됨
            }
            target_topic = f"ddalgi/alert/disease/{user_id}"
            publish_message(target_topic, alert_data)
        
        # 응답 메시지도 이미지가 있었는지 없었는지에 따라 다르게 반환
        return jsonify({
            "status": "success", 
            "message": "데이터 로깅 완료 (이미지 포함)" if has_image else "데이터 로깅 완료 (이미지 없음)",
            "image_url": image_url
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": f"서버 처리 실패: {str(e)}"}), 500