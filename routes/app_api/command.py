from flask import Blueprint, request, jsonify
from datetime import datetime

from ddalgi_models import db, Robot, CommandLog, Zone, ZoneBatch, Marker
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
# API 엔드포인트: 구역(Zone) 등록 및 수정 API 
# ---------------------------------------------------------
@command_bp.route('/api/zone/setup', methods=['POST'])
def setup_zone():
    data = request.get_json()
    
    if not data or 'zone_id' not in data or 'user_id' not in data or 'zone_name' not in data:
        return jsonify({"status": "error", "message": "zone_id, user_id, zone_name은 필수 항목입니다."}), 400

    zone_id = data['zone_id']                                                                                                                                                                             
    user_id = data['user_id']
    
    try:
        # DB에 이미 만들어진 구역인지 확인 (Upsert 로직)
        zone = Zone.query.filter_by(zone_id=zone_id, user_id=user_id).first()
        
        if not zone:
            zone = Zone(zone_id=zone_id, user_id=user_id)
            db.session.add(zone)
            action_msg = "등록"
        else:
            action_msg = "수정"

        # 구역 정보 업데이트 (새로 추가된 zone_description 포함!)
        zone.zone_name = data.get('zone_name', zone.zone_name)
        zone.zone_description = data.get('zone_description', zone.zone_description) # ✅ 추가된 부분
        
        # 실외용 구역 판별 (GPS 사각형 범위)
        zone.min_lat = data.get('min_lat', zone.min_lat)
        zone.max_lat = data.get('max_lat', zone.max_lat)
        zone.min_lng = data.get('min_lng', zone.min_lng)
        zone.max_lng = data.get('max_lng', zone.max_lng)
        
        db.session.commit()
        
        return jsonify({
            "status": "success", 
            "message": f"'{zone.zone_name}' 구역이 성공적으로 {action_msg}되었습니다."
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": f"구역 설정 실패: {str(e)}"}), 500

# ---------------------------------------------------------
# API 엔드포인트: 구역(Zone) 삭제 API (해당 구역의 마커도 자동 삭제)
# ---------------------------------------------------------
@command_bp.route('/api/zone/delete', methods=['POST'])
def delete_zone():
    data = request.get_json()
    
    user_id = data.get('user_id')
    zone_id = data.get('zone_id')
    
    if not user_id or not zone_id:
        return jsonify({"status": "error", "message": "user_id, zone_id가 필요합니다."}), 400

    try:
        zone = Zone.query.filter_by(zone_id=zone_id, user_id=user_id).first()
        
        if not zone:
            return jsonify({"status": "error", "message": "해당 구역을 찾을 수 없거나 권한이 없습니다."}), 404
            
        # 1. 이 구역에 속한 마커(Marker)들 일괄 삭제
        Marker.query.filter_by(zone_id=zone_id).delete(synchronize_session=False)
        
        # 2. 구역(Zone) 자체 삭제
        db.session.delete(zone)
        db.session.commit()
        
        return jsonify({
            "status": "success", 
            "message": f"'{zone.zone_name}' 구역과 연관된 모든 마커가 삭제되었습니다."
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": f"구역 삭제 실패: {str(e)}"}), 500

# ---------------------------------------------------------
# API 엔드포인트: 마커(Marker) 등록 및 수정 API
# ---------------------------------------------------------
@command_bp.route('/api/marker/setup', methods=['POST'])
def setup_marker():
    data = request.get_json()
    
    # 1. 필수값 체크
    marker_id = data.get('marker_id')
    zone_id = data.get('zone_id')
    
    if not marker_id or not zone_id:
        return jsonify({"status": "error", "message": "marker_id, zone_id는 필수 항목입니다."}), 400

    try:
        # 먼저 해당 zone이 실제로 존재하는지 확인하는 것도 좋은 방어 로직입니다.
        zone = Zone.query.filter_by(zone_id=zone_id).first()
        if not zone:
            return jsonify({"status": "error", "message": "존재하지 않는 구역(Zone)입니다. 먼저 구역을 생성하세요."}), 404

        # 2. 마커 존재 여부 확인 (Upsert 로직)
        marker = Marker.query.filter_by(marker_id=marker_id).first()
        
        if not marker:
            marker = Marker(marker_id=marker_id, zone_id=zone_id)
            db.session.add(marker)
            action_msg = "등록"
        else:
            action_msg = "수정"
            # 구역을 다른 곳으로 옮길 수도 있으므로 업데이트 처리
            marker.zone_id = zone_id 

        # 3. GPS 정보가 같이 들어왔다면 업데이트 (실내용이라 안 쓸 수도 있지만 확장성을 위해 남겨둠)
        marker.lat = data.get('lat', marker.lat)
        marker.lng = data.get('lng', marker.lng)
        
        db.session.commit()
        
        return jsonify({
            "status": "success", 
            "message": f"마커({marker_id})가 성공적으로 {action_msg}되었습니다."
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": f"마커 설정 실패: {str(e)}"}), 500

# ---------------------------------------------------------
# API 엔드포인트: 특정 마커(Marker) 1개 삭제 API
# ---------------------------------------------------------
@command_bp.route('/api/marker/delete', methods=['POST'])
def delete_marker():
    data = request.get_json()
    marker_id = data.get('marker_id')
    
    if not marker_id:
        return jsonify({"status": "error", "message": "삭제할 marker_id가 필요합니다."}), 400

    try:
        marker = Marker.query.filter_by(marker_id=marker_id).first()
        
        if not marker:
            return jsonify({"status": "error", "message": "해당 마커를 찾을 수 없습니다."}), 404
            
        db.session.delete(marker)
        db.session.commit()
        
        return jsonify({
            "status": "success", 
            "message": f"마커({marker_id})가 삭제되었습니다."
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": f"마커 삭제 실패: {str(e)}"}), 500
    
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
    target_marker = data.get('marker_id')  
    
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
            target_zone=target_zone,
            target_marker=target_marker  
        )
        db.session.add(new_log)
        db.session.commit()
        
        # 4. 로봇에게 보낼 MQTT 메시지(명령어) 구성
        mqtt_message = {
            "command": command,
            "target_zone": target_zone,
            "target_marker": target_marker,  # ⭐️ 추가됨: 로봇에게 마커 ID도 전달
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