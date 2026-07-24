from flask import Flask
from ddalgi_models import db, CropProfile
from ddalgi_mqtt_handler import init_mqtt

# =========================================================
# 🧩 1. 분리해둔 블루프린트(API 조각) 모듈들 불러오기
# =========================================================
# (본인이 폴더를 구성한 위치에 맞게 import 경로를 살짝 맞춰주세요)
from routes.app_api.auth import auth_bp                   # 회원가입/로그인
from routes.app_api.command import command_bp     # 로봇 등록, 구역 설정, 로봇 명령
from routes.app_api.dashboard import dashboard_bp # 환경/작물 로그, 로봇 상태 조회
from routes.robot_api.vision import vision_bp     # 로봇의 사진 S3 업로드 및 알람

# =========================================================
# ⚙️ 2. Flask 메인 앱 생성 및 DB 설정
# =========================================================
app = Flask(__name__)
app.config.from_object('ddalgi_config.Config')

# DB 객체에 현재 플라스크 앱(app) 연동
db.init_app(app)

# =========================================================
# 🔗 3. 불러온 블루프린트를 메인 앱에 조립(등록)
# =========================================================
app.register_blueprint(auth_bp)
app.register_blueprint(command_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(vision_bp)

# =========================================================
# 🌱 4. 초기 작물 데이터 자동 등록 함수 (Seeding)
# =========================================================
def insert_default_crops():
    if CropProfile.query.count() == 0:
        print("[System] 작물 사전이 비어있습니다. 기본 데이터를 자동으로 생성합니다...")
        
        default_crops = [
            CropProfile(crop_id="strawberry", crop_name="딸기", opt_temp_min=5.0, opt_temp_max=25.0, harvest_days=90, crop_description="추위에 강해 겨울~봄 하우스 재배에 적합합니다."),
            CropProfile(crop_id="eggplant", crop_name="가지", opt_temp_min=15.0, opt_temp_max=30.0, harvest_days=70, crop_description="고온성 작물로 여름철 비닐하우스 재배에 적합합니다."),
            CropProfile(crop_id="grape", crop_name="포도", opt_temp_min=15.0, opt_temp_max=30.0, harvest_days=120, crop_description="햇빛을 많이 필요로 하며 배수가 잘 되는 환경이 중요합니다."),
            CropProfile(crop_id="oriental_melon", crop_name="참외", opt_temp_min=20.0, opt_temp_max=30.0, harvest_days=60, crop_description="고온 건조한 환경을 선호하는 여름철 대표 과채류입니다.")
        ]
        
        db.session.add_all(default_crops)
        db.session.commit()
        print("[System] 🌱 기본 작물(딸기, 가지, 포도, 참외) 사전 데이터 세팅 완료!")
    else:
        print("[System] 기존 작물 데이터가 존재하여 시딩을 건너뜁니다.")

# =========================================================
# 🚀 5. 메인 서버 실행 블록
# =========================================================
if __name__ == '__main__':
    # 1) MQTT 통신 시작
    init_mqtt(app, db)  
    
    # 2) 서버 실행 시 테이블이 없으면 자동 생성 및 시딩
    with app.app_context():
        db.create_all()
        insert_default_crops()
        
    # 3) Flask 서버 실행 (안드로이드 접속을 위한 0.0.0.0)
    # 🚨 MQTT 로그 중복(두 번씩 찍히는 현상) 방지를 위해 use_reloader=False
    app.run(host='0.0.0.0', port=12345, debug=True, use_reloader=False)