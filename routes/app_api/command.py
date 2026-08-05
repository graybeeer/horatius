from flask import Blueprint, request, jsonify
from datetime import datetime

from ddalgi_models import db, Robot, CommandLog, Zone, ZoneBatch
from ddalgi_mqtt_handler import publish_message

# 'command_bp' 블루프린트 생성
command_bp = Blueprint('command', __name__)

'''
액션(Action) 및 설정(Setup)
앱에서 로봇에게 명령을 내리거나 구역을 설정할 때 필요한 POST API를 제공
'''

# ---------------------------------------------------------
# API 엔드포인트: 신규 로봇 등록 (/api/robot/register)
# ---------------------------------------------------------
@command_bp.route('/api/robot/register', methods=['POST'])
def register_robot():
    data = request.get_json()
    
    # 1. 필수 데이터 누락 검사
    if not data or 'robot_id' not in data or 'user_id' not in data:
        return jsonify({
            "status": "error", 
            "message": "robot_id와 user_id는 필수 항목입니다."
        }), 400

    robot_id = data['robot_id']
    user_id = data['user_id']
    
    # 2. 중복 검사: 이미 DB에 있는 로봇인지 확인
    existing_robot = Robot.query.filter_by(robot_id=robot_id).first()
    
    if existing_robot:
        return jsonify({
            "status": "error", 
            "message": "이미 등록된 로봇 기기입니다."
        }), 409

    try:
        # 3. 새로운 로봇 생성 및 DB 저장
        new_robot = Robot(
            robot_id=robot_id,
            user_id=user_id,
            operating_status='OFFLINE',
            battery=100
        )
        db.session.add(new_robot)
        db.session.commit()
        
        return jsonify({
            "status": "success", 
            "message": f"로봇({robot_id})이 성공적으로 등록되었습니다."
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error", 
            "message": f"서버 오류로 로봇 등록에 실패했습니다: {str(e)}"
        }), 500

# ---------------------------------------------------------
# API 엔드포인트: 구역(Zone) 등록 및 수정 API (/api/zone/setup)
# ---------------------------------------------------------
@command_bp.route('/api/zone/setup', methods=['POST'])
def setup_zone():
    data = request.get_json()
    
    # 1. 필수 데이터 누락 검사
    if not data or 'zone_id' not in data or 'user_id' not in data or 'zone_name' not in data:
        return jsonify({
            "status": "error", 
            "message": "zone_id, user_id, zone_name은 필수 항목입니다."
        }), 400

    zone_id = data['zone_id']
    user_id = data['user_id']
    
    try:
        # 2. DB에 이미 만들어진 구역인지 확인 (Upsert 로직)
        zone = Zone.query.filter_by(zone_id=zone_id, user_id=user_id).first()
        
        if not zone:
            zone = Zone(zone_id=zone_id, user_id=user_id)
            db.session.add(zone)
            action_msg = "등록"
        else:
            action_msg = "수정"

        # 3. 하이브리드 구역 정보 업데이트
        zone.zone_name = data.get('zone_name', zone.zone_name)
        zone.marker_list = data.get('marker_list', zone.marker_list)
        zone.min_lat = data.get('min_lat', zone.min_lat)
        zone.max_lat = data.get('max_lat', zone.max_lat)
        zone.min_lng = data.get('min_lng', zone.min_lng)
        zone.max_lng = data.get('max_lng', zone.max_lng)
        
        # 4. DB에 최종 저장
        db.session.commit()
        
        return jsonify({
            "status": "success", 
            "message": f"'{zone.zone_name}' 구역이 성공적으로 {action_msg}되었습니다."
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error", 
            "message": f"서버 오류로 구역 설정에 실패했습니다: {str(e)}"
        }), 500
# ---------------------------------------------------------
# API 엔드포인트: 특정 구역(또는 전체)의 재배 데이터를 DB에서 완전 삭제(초기화)하는 API
# ---------------------------------------------------------
@command_bp.route('/api/zones/batch/manage', methods=['POST'])
def manage_zone_batches():
    data = request.get_json()
    
    user_id = data.get('user_id')
    zone_id = data.get('zone_id') # 특정 구역 ID 또는 'ALL'

    # 1. 필수값 체크 (이제 action 파라미터는 필요 없습니다)
    if not user_id or not zone_id:
        return jsonify({"status": "error", "message": "user_id, zone_id 값이 모두 필요합니다."}), 400

    try:
        # 2. 작업할 타겟 구역(Zone) ID 리스트 구하기
        if zone_id.upper() != 'ALL':
            # [특정 구역]
            target_zone = Zone.query.filter_by(user_id=user_id, zone_id=zone_id).first()
            if not target_zone:
                return jsonify({"status": "error", "message": "해당 구역을 찾을 수 없거나 권한이 없습니다."}), 404
            target_zone_ids = [target_zone.zone_id]
        else:
            # [전체 구역]
            user_zones = Zone.query.filter_by(user_id=user_id).all()
            if not user_zones:
                return jsonify({"status": "error", "message": "사용자에게 등록된 구역이 없습니다."}), 404
            target_zone_ids = [zone.zone_id for zone in user_zones]

        # 3. 요청받은 구역들의 ZoneBatch 데이터 완전 삭제
        batch_query = ZoneBatch.query.filter(ZoneBatch.zone_id.in_(target_zone_ids))
        affected_rows = batch_query.delete(synchronize_session=False)
        
        # 4. DB 반영
        db.session.commit()

        # 5. 결과 반환
        return jsonify({
            "status": "success",
            "message": f"총 {len(target_zone_ids)}개 구역에서 {affected_rows}건의 재배 데이터가 완전 삭제되었습니다.",
            "data": {
                "cleared_zones": target_zone_ids,
                "affected_count": affected_rows
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"재배 데이터 삭제 에러: {e}")
        return jsonify({"status": "error", "message": "서버 내부 오류가 발생했습니다."}), 500
# ---------------------------------------------------------
# API 엔드포인트: 로봇 제어 명령 (/api/robot/command)
# ---------------------------------------------------------
# start_patrol: 순찰 시작, 
# stop: 순찰 중지
# return_home: 귀환
@command_bp.route('/api/robot/command', methods=['POST'])
def robot_command():
    data = request.get_json()
    
    user_id = data.get('user_id')
    robot_id = data.get('robot_id')
    command = data.get('command')
    target_zone = data.get('zone_id')
    
    # 1. 필수 데이터 누락 확인
    if not user_id or not robot_id or not command:
        return jsonify({"status": "error", "message": "필수 파라미터가 누락되었습니다."}), 400
        
    # 2. (보안 검증) DB에서 이 로봇이 해당 사용자의 소유가 맞는지 확인
    robot = Robot.query.filter_by(robot_id=robot_id, user_id=user_id).first()
    if not robot:
        return jsonify({"status": "error", "message": "권한이 없거나 존재하지 않는 로봇입니다."}), 403
        
    try:
        # 3. DB에 명령 이력(Log) 저장하기
        new_log = CommandLog(
            user_id=user_id,
            robot_id=robot_id,
            command=command,
            target_zone=target_zone
        )
        db.session.add(new_log)
        db.session.commit()
        
        # 4. 로봇에게 보낼 MQTT 메시지(명령어) 구성
        mqtt_message = {
            "command": command,
            "target_zone": target_zone,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # 5. 지정된 로봇 전용 토픽으로 메시지 발행 (Pub)
        topic = f"ddalgi/robot/command/{robot_id}"
        publish_message(topic, mqtt_message)
        
        return jsonify({
            "status": "success", 
            "message": f"{robot_id} 로봇에 '{command}' 명령을 안전하게 전송했습니다."
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error", 
            "message": f"명령 처리 중 서버 오류가 발생했습니다: {str(e)}"
        }), 500