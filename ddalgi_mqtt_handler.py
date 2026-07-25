import paho.mqtt.client as mqtt
import json

# ⭐️ 쪼개놓은 개별 핸들러 함수들을 불러옵니다!
from mqtt_handlers.handlers import handle_crop_log, handle_env_log, handle_robot_status

'''
로봇/앱과의 MQTT 통신(수신 및 분류)을 전담
'''

# 전역 MQTT 클라이언트 객체 생성
mqtt_client = mqtt.Client()
flask_app = None
db_instance = None

def on_connect(client, userdata, flags, rc):
    print(f"✅ MQTT 브로커 연결 성공! (결과 코드: {rc})")
    # 서버가 실행될 때 기본적으로 구독(Sub)할 토픽들
    client.subscribe("ddalgi/sensor/env")
    client.subscribe("ddalgi/robot/crop")      # 누락되었던 구독 추가
    client.subscribe("ddalgi/robot/status/#")  # 하위 토픽까지 모두 구독하도록 # 추가

def on_message(client, userdata, msg):
    topic = msg.topic
    payload = msg.payload.decode('utf-8')
    print(f"📩 [메시지 수신] 토픽: {topic}")
    
    try:
        data = json.loads(payload)
        
        # 💡 각 담당자에게 데이터와 함께 flask_app, db_instance를 쥐어주고 일을 시킵니다!
        if topic == "ddalgi/robot/crop":
            handle_crop_log(data, flask_app, db_instance)
            
        elif topic == "ddalgi/sensor/env":
            handle_env_log(data, flask_app, db_instance)
            
        elif topic.startswith("ddalgi/robot/status/"):
            handle_robot_status(data, flask_app, db_instance)
            
        else:
            print(f"⚠️ [경고] 처리할 수 없는 토픽입니다: {topic}")

    except json.JSONDecodeError:
        print("❌ [에러] 수신된 메시지가 올바른 JSON 형식이 아닙니다.")
    except Exception as e:
        print(f"❌ [에러] 메시지 처리 중 문제 발생: {e}")

def init_mqtt(app, db):
    """
    플라스크(Flask) 서버가 켜질 때 같이 실행해줄 초기화 함수
    """
    global flask_app, db_instance
    flask_app = app
    db_instance = db
    
    broker = flask_app.config.get('MQTT_BROKER')
    port = flask_app.config.get('MQTT_PORT')
    
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    
    try:
        mqtt_client.connect(broker, port, 60)
        mqtt_client.loop_start() 
    except Exception as e:
        print(f"❌ MQTT 연결 실패: {e}")

def publish_message(topic, message_dict):
    """
    다른 파이썬 파일(app.py 등)에서 쉽게 데이터를 Pub 할 수 있도록 만든 도우미 함수
    """
    mqtt_client.publish(topic, json.dumps(message_dict))
    print(f"📤 [알람 발송] 토픽: {topic} 로 메시지를 보냈습니다.")