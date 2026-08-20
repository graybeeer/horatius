from flask import Blueprint, request, jsonify
from datetime import datetime
from sqlalchemy import func, case

# 상위 폴더에 있는 모델 가져오기
from ddalgi_models import db, EnvLog, CropLog, Robot, Zone, ZoneBatch,CommandLog, CropProfile

# 'dashboard_bp' 블루프린트 생성
dashboard_bp = Blueprint('dashboard', __name__)

'''
앱의 메인 화면이나 통계 화면을 그릴 때 필요한 데이터(환경 로그, 작물 로그, 로봇 상태)를 반환하는 GET API
'''

# ---------------------------------------------------------
# API 엔드포인트: 주기적 환경 및 통계 데이터 조회
# ---------------------------------------------------------
@dashboard_bp.route('/api/logs/env', methods=['GET'])
def get_env_logs():
    user_id = request.args.get('user_id')
    
    # 앱에서 'limit' 값을 안 보내면 기본값 20, 문자를 섞어 보내면 무시하고 20으로 자동 변환(type=int)
    limit_count = request.args.get('limit', default=20, type=int)
    
    if not user_id:
        return jsonify({"status": "error", "message": "user_id 파라미터가 필요합니다."}), 400

    # 해당 사용자의 최신 로그 {limit_count}개를 시간 역순(최신순)으로 가져오기
    logs = EnvLog.query.filter_by(user_id=user_id).order_by(EnvLog.timestamp.desc()).limit(limit_count).all()
    
    result = [{
        "log_id": log.log_id,
        "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "temperature": log.temperature,
        "humidity": log.humidity
    } for log in logs]
        
    return jsonify({"status": "success", "data": result}), 200

# ---------------------------------------------------------
# API 엔드포인트: 작물 이상 상태 촬영 로그 조회
# ---------------------------------------------------------
@dashboard_bp.route('/api/logs/crop', methods=['GET'])
def get_crop_logs():
    user_id = request.args.get('user_id')

    # 앱에서 'limit' 값을 안 보내면 기본값 20, 문자를 섞어 보내면 무시하고 20으로 자동 변환(type=int)
    limit_count = request.args.get('limit', default=20, type=int)
    
    if not user_id:
        return jsonify({"status": "error", "message": "user_id 파라미터가 필요합니다."}), 400

    logs = CropLog.query.filter_by(user_id=user_id).order_by(CropLog.timestamp.desc()).limit(limit_count).all()
    
    result = [{
        "log_id": log.log_id,
        "robot_id": log.robot_id,
        "zone_id": log.zone_id,
        "crop_id": log.crop_id,
        "health_status": log.health_status,  # ✅ DB 모델 이름과 똑같이 맞춤!
        "growth_status": log.growth_status,  # (필요하다면 이것도 추가)
        "image_url": log.image_url,  # (필요하다면 이것도 추가)
        "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S")
    } for log in logs]
        
    return jsonify({"status": "success", "data": result}), 200
# ---------------------------------------------------------
# API 엔드포인트: 최근 로봇 제어 명령 로그 조회 (요청한 개수만큼)
# ---------------------------------------------------------
@dashboard_bp.route('/api/logs/command', methods=['GET'])
def get_command_logs():
    user_id = request.args.get('user_id')
    
    # 앱에서 'limit' 값을 안 보내면 기본값 20, 문자를 섞어 보내면 무시하고 20으로 자동 변환(type=int)
    limit_count = request.args.get('limit', default=20, type=int)
    
    if not user_id:
        return jsonify({"status": "error", "message": "user_id 파라미터가 필요합니다."}), 400

    try:
        # 1. limit_count 변수를 활용해 앱에서 원하는 개수만큼만 잘라서(limit) 가져옵니다.
        logs = CommandLog.query.filter_by(user_id=user_id)\
                               .order_by(CommandLog.timestamp.desc())\
                               .limit(limit_count).all()
        
        # 2. JSON 형태로 예쁘게 변환
        result = [{
            "log_id": log.log_id,
            "robot_id": log.robot_id,
            "command": log.command,
            "target_zone": log.target_zone,
            "target_marker": log.target_marker,
            "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S") if log.timestamp else None
        } for log in logs]
            
        return jsonify({
            "status": "success", 
            "message": f"최근 명령 로그 {len(result)}개 조회 완료",
            "data": result
        }), 200

    except Exception as e:
        print(f"명령 로그 조회 에러: {e}")
        return jsonify({"status": "error", "message": "서버 내부 오류가 발생했습니다."}), 500
# ---------------------------------------------------------
# API 엔드포인트: 특정 로봇의 현재 상태 조회 API
# ---------------------------------------------------------
@dashboard_bp.route('/api/robot/status/<robot_id>', methods=['GET'])
def get_robot_status(robot_id):
    request_user_id = request.args.get('user_id')
    
    if not request_user_id:
        return jsonify({"status": "error", "message": "요청자(user_id) 정보가 없습니다."}), 400

    robot = Robot.query.filter_by(robot_id=robot_id).first()
    
    if not robot:
        return jsonify({"status": "error", "message": "등록되지 않은 로봇입니다."}), 404

    if robot.user_id != request_user_id:
        return jsonify({"status": "error", "message": "이 로봇을 조회할 권한이 없습니다."}), 403

    current_time = datetime.now()
    final_status = robot.operating_status 
    
    if robot.last_updated:
        time_diff = (current_time - robot.last_updated).total_seconds()
        if time_diff > 30:
            final_status = 'OFFLINE'
    else:
        final_status = 'OFFLINE'

    return jsonify({
        "status": "success",
        "data": {
            "robot_id": robot.robot_id,
            "robot_type": robot.robot_type,
            "operating_status": final_status, 
            "battery": robot.battery,
            "current_zone": robot.current_zone,
            "last_marker_id": robot.last_marker_id,
            "lat": robot.lat,
            "lng": robot.lng,
            "last_updated": robot.last_updated.strftime('%Y-%m-%d %H:%M:%S') if robot.last_updated else None
        }
    }), 200
    
# ---------------------------------------------------------
# API 엔드포인트: 해당 유저의 전체 구역(Zone) 및 재배 현황(Batch) 조회
# ---------------------------------------------------------
@dashboard_bp.route('/api/user/zones', methods=['GET'])
def get_user_zones():
    user_id = request.args.get('user_id')
    
    if not user_id:
        return jsonify({"status": "error", "message": "user_id 파라미터가 필요합니다."}), 400

    # 1. 해당 유저가 소유한 모든 구역(Zone) 조회
    zones = Zone.query.filter_by(user_id=user_id).all()
    
    result = []
    for zone in zones:
        # 2. 해당 구역(zone_id)에 등록된 재배 이력(ZoneBatch)을 최신순으로 조회
        batches = ZoneBatch.query.filter_by(zone_id=zone.zone_id)\
                                 .order_by(ZoneBatch.planted_date.desc()).all()
        
        # 3. 재배 이력을 딕셔너리 리스트로 변환
        batch_list = []
        for batch in batches:
            batch_list.append({
                "batch_id": batch.batch_id,
                "crop_id": batch.crop_id,
                "planted_date": batch.planted_date.strftime("%Y-%m-%d %H:%M:%S") if batch.planted_date else None,
                "growth_status": batch.growth_status,
                "health_status": batch.health_status,
                "disease_name": batch.disease_name
            })
            
        # 4. 구역 정보 안에 재배 이력(batches)을 포함시켜 조립 (Nested JSON)
        result.append({
            "zone_id": zone.zone_id,
            "zone_name": zone.zone_name,
            "marker_list": zone.marker_list,
            "min_lat": zone.min_lat,
            "max_lat": zone.max_lat,
            "min_lng": zone.min_lng,
            "max_lng": zone.max_lng,
            "batches": batch_list  # 🍓 핵심! 구역 안에 작물 데이터가 쏙 들어갑니다.
        })
        
    return jsonify({
        "status": "success", 
        "data": result
    }), 200
# ---------------------------------------------------------
# API 엔드포인트: 작물(crop_id) 요약 통계 (Float 버전)
# ---------------------------------------------------------
@dashboard_bp.route('/api/user/crop/summary', methods=['GET'])
def get_single_crop_summary():
    user_id = request.args.get('user_id')
    crop_id = request.args.get('crop_id')

    if not user_id or not crop_id:
        return jsonify({"status": "error", "message": "user_id, crop_id가 필요합니다."}), 400

    try:
        # 1. 성장도(Float)를 구간별로 나누고 평균을 구하는 똑똑한 쿼리
        summary = db.session.query(
            func.count(ZoneBatch.batch_id).label('total_count'),
            func.avg(ZoneBatch.growth_status).label('avg_growth'), # 평균 성장률 계산
            
            # 0~30 미만: 모종 단계
            func.sum(case((ZoneBatch.growth_status < 30.0, 1), else_=0)).label('seedling_count'),
            # 30~80 미만: 성장 중
            func.sum(case((ZoneBatch.growth_status.between(30.0, 79.9), 1), else_=0)).label('growing_count'),
            # 80 이상: 수확 임박/완료
            func.sum(case((ZoneBatch.growth_status >= 80.0, 1), else_=0)).label('ripe_count')
        ).join(Zone, Zone.zone_id == ZoneBatch.zone_id)\
         .filter(Zone.user_id == user_id, ZoneBatch.crop_id == crop_id).first()

        # 건강 상태(health_status)는 기존처럼 글자이므로 Group By 유지
        health_counts = db.session.query(
            ZoneBatch.health_status, 
            func.count(ZoneBatch.batch_id)
        ).join(Zone, Zone.zone_id == ZoneBatch.zone_id)\
         .filter(Zone.user_id == user_id, ZoneBatch.crop_id == crop_id)\
         .group_by(ZoneBatch.health_status).all()

        health_summary = {status: count for status, count in health_counts if status}

        # 결과 반환 (None 방어 처리 포함)
        return jsonify({
            "status": "success",
            "message": f"[{crop_id}] 통계 조회 완료",
            "data": {
                "crop_id": crop_id,
                "total_count": int(summary.total_count or 0),
                "average_growth_percent": round(summary.avg_growth or 0.0, 1), # 예: 45.3%
                "growth_ranges": {
                    "0_to_30": int(summary.seedling_count or 0),
                    "30_to_80": int(summary.growing_count or 0),
                    "80_to_100": int(summary.ripe_count or 0)
                },
                "health_status_counts": health_summary
            }
        }), 200

    except Exception as e:
        print(f"작물 통계 에러: {e}")
        return jsonify({"status": "error", "message": "통계 에러"}), 500

# ---------------------------------------------------------
# API 엔드포인트: 작물 프로필 정보 조회 (전체 조회 & 단일 조회)
# ---------------------------------------------------------
@dashboard_bp.route('/api/crops/inform', methods=['GET'])
@dashboard_bp.route('/api/crops/inform/<string:crop_id>', methods=['GET'])
def get_crop_inform(crop_id=None):
    try:
        # 1. 특정 작물 ID가 입력된 경우 (단일 조회)
        if crop_id:
            crop = CropProfile.query.filter_by(crop_id=crop_id).first()
            
            # DB에 해당 작물이 없는 경우
            if not crop:
                return jsonify({
                    "status": "fail",
                    "message": f"'{crop_id}'에 해당하는 작물을 찾을 수 없습니다."
                }), 404
                
            crop_data = {
                "crop_id": crop.crop_id,
                "crop_name": crop.crop_name,
                "opt_temp_min": crop.opt_temp_min,
                "opt_temp_max": crop.opt_temp_max,
                "harvest_days": crop.harvest_days,
                "image_url": crop.image_url,
                "crop_description": crop.crop_description
            }
            
            return jsonify({
                "status": "success",
                "message": f"{crop.crop_name} 프로필을 불러왔습니다.",
                "data": crop_data
            }), 200

        # 2. 아무 ID도 입력되지 않은 경우 (전체 조회)
        else:
            crops = CropProfile.query.all()
            
            crop_list = []
            for crop in crops:
                crop_list.append({
                    "crop_id": crop.crop_id,
                    "crop_name": crop.crop_name,
                    "opt_temp_min": crop.opt_temp_min,
                    "opt_temp_max": crop.opt_temp_max,
                    "harvest_days": crop.harvest_days,
                    "image_url": crop.image_url,
                    "crop_description": crop.crop_description
                })
                
            return jsonify({
                "status": "success",
                "message": "전체 작물 프로필을 성공적으로 불러왔습니다.",
                "data": crop_list
            }), 200
            
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"서버 오류가 발생했습니다: {str(e)}"
        }), 500