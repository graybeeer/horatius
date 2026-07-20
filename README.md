# 1조(딸기딸기) 농장 IoT 백엔드 서버

스마트 농장 관리를 위한 자율주행 로봇 제어 및 환경 모니터링 시스템의 백엔드(서버) 저장소입니다.

## 📌 주요 기능
- **회원 및 권한 관리**: 농장주(사용자) 계정 및 로봇 소유권 검증
- **MQTT 기반 실시간 통신**: 로봇과 서버 간의 실시간 명령 및 상태(배터리, 위치) 공유
- **작물 및 환경 모니터링**: 센서(온습도) 데이터 및 로봇이 촬영한 작물 상태(질병, 수확 가능 여부) DB 로깅
- **안드로이드 앱 API 제공**: 통계 데이터 조회 및 원격 로봇 제어(자동 순찰 등) API 지원

## 🛠️ 기술 스택 (Tech Stack)
- **Language**: Python 3.x
- **Framework**: Flask
- **Database**: MariaDB, SQLAlchemy (ORM)
- **Communication**: MQTT (Eclipse Mosquitto)
- **Cloud/Storage**: AWS S3 (이미지 저장 예정)

## 📁 프로젝트 구조
```text
ddalgi_project/
├── ddalgi_app.py         # 메인 서버 실행 및 REST API 라우터
├── ddalgi_models.py      # 데이터베이스 테이블(ORM) 모델 정의
├── ddalgi_mqtt_handler.py # MQTT 메시지 발행/구독 및 DB 저장 로직
├── ddalgi_config.py      # 환경 변수 및 DB/MQTT 접속 설정
└── requirements.txt      # 파이썬 라이브러리 설치 목록
```

## 로컬 실행 방법 (How to run)

1. **저장소 클론 및 폴더 이동**
   ```bash
   git clone [깃허브 저장소 주소]
   cd ddalgi_project
   ```

2. **가상환경 생성 및 라이브러리 설치**
   ```bash
   python -m venv myenv
   # 윈도우의 경우 가상환경 실행: myenv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **환경 설정 (Config)**
   - MariaDB를 설치하고 `ddalgi` 데이터베이스를 생성합니다.
   - `ddalgi_config.py` 파일에 DB 계정 정보와 MQTT 브로커 주소를 기입합니다.
   - 로컬에 Mosquitto MQTT 브로커를 실행합니다.

4. **서버 실행**
   ```bash
   python ddalgi_app.py
   ```