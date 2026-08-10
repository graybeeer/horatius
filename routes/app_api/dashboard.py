from flask import Blueprint, request, jsonify
from datetime import datetime
from sqlalchemy import func, case

# 상위 폴더에 있는 모델 가져오기
from ddalgi_models import db, EnvLog, CropLog, Robot, Zone, ZoneBatch,CommandLog

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
        "status": log.status,
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
# API 엔드포인트: 특정 작물(crop_id)의 모든 상태별 개수 자동 집계
# ---------------------------------------------------------
@dashboard_bp.route('/api/user/crop/summary', methods=['GET'])
def get_single_crop_summary():
    user_id = request.args.get('user_id')
    crop_id = request.args.get('crop_id')

    if not user_id or not crop_id:
        return jsonify({"status": "error", "message": "user_id와 crop_id 파라미터가 모두 필요합니다."}), 400

    try:
        # 1. 자란 상태(growth_status)별 개수 집계 쿼리
        growth_counts = db.session.query(
            ZoneBatch.growth_status, 
            func.count(ZoneBatch.batch_id)
        ).join(Zone, Zone.zone_id == ZoneBatch.zone_id)\
         .filter(Zone.user_id == user_id, ZoneBatch.crop_id == crop_id)\
         .group_by(ZoneBatch.growth_status).all()

        # 2. 건강 상태(health_status)별 개수 집계 쿼리
        health_counts = db.session.query(
            ZoneBatch.health_status, 
            func.count(ZoneBatch.batch_id)
        ).join(Zone, Zone.zone_id == ZoneBatch.zone_id)\
         .filter(Zone.user_id == user_id, ZoneBatch.crop_id == crop_id)\
         .group_by(ZoneBatch.health_status).all()

        # 3. 조회된 데이터를 딕셔너리(JSON Object) 형태로 예쁘게 변환
        # 예: {'GROWING': 15, 'FLOWERING': 5}
        growth_summary = {status: count for status, count in growth_counts if status}
        health_summary = {status: count for status, count in health_counts if status}

        # 총 작물 개수는 growth_summary의 모든 value(개수)를 더하면 됩니다.
        total_count = sum(growth_summary.values())

        # 4. 결과 반환
        return jsonify({
            "status": "success",
            "message": f"[{crop_id}] 작물 전체 상태 요약 조회 완료",
            "data": {
                "crop_id": crop_id,
                "total_count": total_count,
                "growth_status_counts": growth_summary, # 모든 자란 상태별 숫자
                "health_status_counts": health_summary  # 모든 건강 상태별 숫자
            }
        }), 200

    except Exception as e:
        print(f"작물 통계 에러: {e}")
        return jsonify({"status": "error", "message": "통계 데이터 조회 중 오류가 발생했습니다."}), 500