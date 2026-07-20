import paho.mqtt.client as mqtt
import json
from datetime import datetime

'''
로봇/앱과의 MQTT 통신(수신 및 DB 저장)을 전담
'''

# 전역 MQTT 클라이언트 객체 생성
mqtt_client = mqtt.Client()
flask_app = None
db_instance = None

def on_connect(client, userdata, flags, rc):
    print(f"✅ MQTT 브로커 연결 성공! (결과 코드: {rc})")
    # 서버가 실행될 때 기본적으로 구독(Sub)할 토픽들
    client.subscribe("ddalgi/sensor/env")
    client.subscribe("ddalgi/robot/status")

def on_message(client, userdata, msg):
    topic = msg.topic
    payload = msg.payload.decode('utf-8')
    print(f"📩 [메시지 수신] 토픽: {topic}\n내용: {payload}")
    
    try:
        data = json.loads(payload)
        
        with flask_app.app_context():
            from ddalgi_models import CropLog, EnvLog

            if topic == "ddalgi/robot/crop":
                new_crop_log = CropLog(
                    user_id=data.get("user_id"),
                    robot_id=data.get("robot_id"),
                    crop_type=data.get("crop_type"),
                    status=data.get("status"),
                    zone_id=data.get("zone_id")
                )
                db_instance.session.add(new_crop_log)
                db_instance.session.commit()
                print("💾 [DB 저장 완료] 작물 촬영 로그 기록됨")

            elif topic == "ddalgi/sensor/env":
                new_env_log = EnvLog(
                    user_id=data.get("user_id"),
                    temperature=data.get("temperature"),
                    humidity=data.get("humidity"),
                    ripe_count=data.get("ripe_count"),
                    unripe_count=data.get("unripe_count"),
                    disease_count=data.get("disease_count")
                )
                db_instance.session.add(new_env_log)
                db_instance.session.commit()
                print("💾 [DB 저장 완료] 환경 및 통계 로그 기록됨")

    except Exception as e:
        print(f"❌ [DB 저장 에러] {e}")

def init_mqtt(app, db):
    """
    플라스크(Flask) 서버가 켜질 때 같이 실행해줄 초기화 함수
    """
    global flask_app, db_instance
    flask_app = app
    db_instance = db
    
    # app.config에서 MQTT 설정값을 꺼내옵니다.
    broker = flask_app.config.get('MQTT_BROKER')
    port = flask_app.config.get('MQTT_PORT')
    
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    
    try:
        # 꺼내온 변수(broker, port)로 접속하도록 변경합니다.
        mqtt_client.connect(broker, port, 60)
        mqtt_client.loop_start() 
    except Exception as e:
        print(f"❌ MQTT 연결 실패: {e}")

def publish_message(topic, message_dict):
    """
    다른 파이썬 파일(app.py 등)에서 쉽게 데이터를 Pub 할 수 있도록 만든 도우미 함수
    """
    # 딕셔너리(JSON) 형태의 데이터를 문자열로 변환하여 전송
    mqtt_client.publish(topic, json.dumps(message_dict))
    print(f"📤 [알람 발송] 토픽: {topic} 로 메시지를 보냈습니다.")