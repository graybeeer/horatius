from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

'''
DB 테이블 구조(명세서)를 전담
'''
# ---------------------------------------------------------
# 작물 사전 데이터
# ---------------------------------------------------------

class CropProfile(db.Model):
    __tablename__ = 'crop_profiles'
    crop_id = db.Column(db.String(50), primary_key=True) # 예: STRAWBERRY, TOMATO
    crop_name = db.Column(db.String(50))     # 예: 딸기
    opt_temp_min = db.Column(db.Float)       # 최저 10도
    opt_temp_max = db.Column(db.Float)       # 최고 25도
    harvest_days = db.Column(db.Integer)     # 파종 후 90일 뒤 수확
    # 앱 표시용
    image_url = db.Column(db.String(255), nullable=True) # 아이콘이나 사진 주소
    crop_description = db.Column(db.String(255), nullable=True) # 작물 설명
    
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
    #main_crop = db.Column(db.String(50))
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
    operating_status = db.Column(db.String(20), default='OFFLINE') #ACTIVE, IDLE, OFFLINE
    
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
    crop_id = db.Column(db.String(50))    # crop_profiles의 crop_id 참조
    status = db.Column(db.String(50))     # ripe, unripe, disease
    growth_status = db.Column(db.String(20), default='GROWING') 
    health_status = db.Column(db.String(20), default='NORMAL')  
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

# ---------------------------------------------------------
# 재배 테이블
# ---------------------------------------------------------
class ZoneBatch(db.Model):
    __tablename__ = 'zone_batches'
    batch_id = db.Column(db.String(50), primary_key=True) # 재배 번호 (예: 2026_A1_STRAWBERRY)
    zone_id = db.Column(db.String(50), nullable=False)    # 어디에 심었나? (A1 구역)
    crop_id = db.Column(db.String(50), nullable=False)    # 뭘 심었나? (설향딸기)
    
    planted_date = db.Column(db.DateTime, default=datetime.now) # 언제 심었나? (2026-07-23)
    
    # 예: SEEDLING(모종), GROWING(성장중), FLOWERING(개화기), HARVESTED(수확완료)
    growth_status = db.Column(db.String(20), default='GROWING') 
    
    # 예: NORMAL(정상), WARNING(주의), DISEASED(질병발생)
    health_status = db.Column(db.String(20), default='NORMAL')  
    
    # (선택) 질병에 걸렸다면 무슨 병인지 기록해두면 앱에 표시하기 좋습니다.
    last_disease_name = db.Column(db.String(50), nullable=True) # 예: '흰가루병' (정상일 땐 null)
    
# ---------------------------------------------------------
# 명령 이력 테이블 
# ---------------------------------------------------------
class CommandLog(db.Model):
    __tablename__ = 'command_logs'
    log_id = db.Column(db.Integer, primary_key=True, autoincrement=True) # 1, 2, 3... 자동 생성
    
    user_id = db.Column(db.String(50), nullable=False)   # 명령을 내린 사람
    robot_id = db.Column(db.String(50), nullable=False)  # 명령을 받은 로봇
    command = db.Column(db.String(50), nullable=False)   # 명령어 (예: STOP, MOVE)
    target_zone = db.Column(db.String(50), nullable=True) # 목적지 (없을 수도 있으니 True)
    
    # 서버가 명령을 전달한 정확한 시간 (기본값: 현재 시간)
    created_at = db.Column(db.DateTime, default=datetime.now)