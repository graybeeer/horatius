from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

'''
DB 테이블 구조(명세서)를 전담
'''

# ---------------------------------------------------------
# 1. 사용자 테이블 (회원가입 시 저장되는 정보)
# ---------------------------------------------------------
class User(db.Model):
    __tablename__ = 'users'
    user_id = db.Column(db.String(50), primary_key=True)
    password = db.Column(db.String(255), nullable=False) 
    name = db.Column(db.String(50), nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    country = db.Column(db.String(50))

# ---------------------------------------------------------
# 2. 구역 테이블
# ---------------------------------------------------------
class Zone(db.Model):
    __tablename__ = 'zones'
    zone_id = db.Column(db.String(50), primary_key=True)
    user_id = db.Column(db.String(50), nullable=False) # 주인이 누구인지 표시
    zone_name = db.Column(db.String(50))
    main_crop = db.Column(db.String(50))
    # 실내용 구역 판별 (예: "1,2,3,4,5")
    marker_list = db.Column(db.String(255), nullable=True) 
    
    # 실외용 구역 판별 (GPS 사각형 범위)
    min_lat = db.Column(db.Float, nullable=True)
    max_lat = db.Column(db.Float, nullable=True)
    min_lng = db.Column(db.Float, nullable=True)
    max_lng = db.Column(db.Float, nullable=True)
    

# ---------------------------------------------------------
# 3. 로봇 테이블
# ---------------------------------------------------------
class Robot(db.Model):
    __tablename__ = 'robots'
    robot_id = db.Column(db.String(50), primary_key=True)
    user_id = db.Column(db.String(50), nullable=False)
    current_zone = db.Column(db.String(50))
    battery = db.Column(db.Integer)
    last_updated = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 위치 데이터 1: 실내용 (마커)
    last_marker_id = db.Column(db.Integer, nullable=True)
    
    # 위치 데이터 2: 실외용 (GPS)
    lat = db.Column(db.Float, nullable=True) # 위도
    lng = db.Column(db.Float, nullable=True) # 경도

# ---------------------------------------------------------
# 4. 작물 촬영 로그 테이블 (로봇이 작물 사진을 찍었을 때 기록)
# ---------------------------------------------------------
class CropLog(db.Model):
    __tablename__ = 'crop_logs'
    log_id = db.Column(db.Integer, primary_key=True, autoincrement=True) # 자동 증가 고유값
    user_id = db.Column(db.String(50), nullable=False)
    robot_id = db.Column(db.String(50), nullable=False)
    crop_type = db.Column(db.String(50))  # 딸기, 가지, 참외 등
    status = db.Column(db.String(50))     # ripe, unripe, disease
    zone_id = db.Column(db.String(50))    # A1, C2 등
    image_url = db.Column(db.String(255)) # S3 이미지 주소 저장
    timestamp = db.Column(db.DateTime, default=datetime.now) # 기록 시각 자동 저장

# ---------------------------------------------------------
# 5. 환경 및 통계 기록 테이블 (일정 시간마다 기록)
# ---------------------------------------------------------
class EnvLog(db.Model):
    __tablename__ = 'env_logs'
    log_id = db.Column(db.Integer, primary_key=True, autoincrement=True) # 자동 증가 고유값
    user_id = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now) # 기록 시각 자동 저장
    temperature = db.Column(db.Float)
    humidity = db.Column(db.Float)
    ripe_count = db.Column(db.Integer)
    unripe_count = db.Column(db.Integer)
    disease_count = db.Column(db.Integer)