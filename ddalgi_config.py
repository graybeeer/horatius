# ddalgi_config.py
'''
DB 비밀번호, 주소 등 모든 환경 설정을 담당
핵심: 이 파일을 git에 올릴 때는 절대 비밀번호를 올리지 마세요
'''

class Config:
    # ---------------------------------------------------------
    # 1. 데이터베이스(MariaDB) 설정
    # ---------------------------------------------------------
    # 형식: mysql+pymysql://계정이름:비밀번호@호스트주소:포트/DB이름
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:8659@localhost:3306/ddalgi'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # ---------------------------------------------------------
    # 2. MQTT 브로커 설정
    # ---------------------------------------------------------
    MQTT_BROKER = 'localhost'  # AWS 사용 시 AWS IP로 변경
    MQTT_PORT = 1883