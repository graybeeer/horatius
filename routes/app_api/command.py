from flask import Blueprint, request, jsonify
from datetime import datetime

from ddalgi_models import db, Robot, CommandLog, Zone
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
# API 엔드포인트: 로봇 제어 명령 (/api/robot_command)
# ---------------------------------------------------------
# start_patrol: 순찰 시작, 
# stop: 순찰 중지
# return_home: 귀환
@command_bp.route('/api/robot_command', methods=['POST'])
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