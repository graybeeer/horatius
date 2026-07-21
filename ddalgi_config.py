# ddalgi_config.py
'''
DB 비밀번호, 주소 등 모든 환경 설정을 담당
핵심: 이 파일을 git에 올릴 때는 절대 비밀번호를 올리지 마세요
'''

import os
from dotenv import load_dotenv

# .env 파일에 적힌 값들을 파이썬으로 불러옵니다.
load_dotenv()

class Config:
    # 1. os.getenv()를 이용해 .env의 값을 꺼내옵니다.
    db_user = os.getenv('DB_USER', 'root')
    db_password = os.getenv('DB_PASSWORD', '') # 비밀번호가 없으면 빈 칸 처리
    db_name = os.getenv('DB_NAME', 'ddalgi')
    
    # 2. 꺼내온 값들을 퍼즐처럼 조립해서 DB 주소를 만듭니다.
    SQLALCHEMY_DATABASE_URI = f'mysql+pymysql://{db_user}:{db_password}@localhost:3306/{db_name}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 3. MQTT 설정도 동일하게 적용합니다.
    MQTT_BROKER = os.getenv('MQTT_BROKER', 'localhost')
    MQTT_PORT = 1883