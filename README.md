# 1조(딸기딸기) 농장 IoT 백엔드 서버

스마트 농장 관리를 위한 자율주행 로봇 제어 및 환경 모니터링 시스템의 백엔드(서버) 저장소입니다.

## 📌 주요 기능
- **회원 및 권한 관리**: 농장주(사용자) 계정 및 로봇 소유권 검증
- **MQTT 기반 실시간 통신**: 로봇과 서버 간의 실시간 명령 및 상태(배터리, 위치) 공유
- **작물 및 환경 모니터링**: 센서(온습도) 데이터 및 로봇이 촬영한 작물 상태(질병, 수확 가능 여부) DB 로깅
- **안드로이드 앱 API 제공**: 통계 데이터 조회, 작물 프로필 관리, 원격 로봇 제어(자동 순찰 등) API 지원
- **실시간 비전(Vision) 알림**: 작물 질병 감지 시 AWS S3에 이미지를 업로드하고 앱으로 즉각적인 MQTT 알람 발송

## 🛠️ 기술 스택 (Tech Stack)
- **Language**: Python 3.x
- **Framework**: Flask
- **Database**: MariaDB, SQLAlchemy (ORM)
- **Communication**: MQTT (Eclipse Mosquitto)
- **Infrastructure**: AWS EC2 (Ubuntu 24.04)
- **Cloud/Storage**: AWS S3 (이미지 스토리지)

## 📁 프로젝트 구조 (Project Structure)
기능 확장에 대비하여 Flask Blueprint와 MQTT Handler 모듈화를 적용한 실무형 아키텍처입니다.

```
ddalgi_backend/
├── ddalgi_app.py             # 메인 서버 실행 및 블루프린트/MQTT 초기 설정
├── ddalgi_models.py          # 데이터베이스 테이블(ORM) 모델 설계도
├── ddalgi_config.py          # DB, AWS S3, MQTT 등 환경 변수 설정
├── ddalgi_mqtt_handler.py    # MQTT 통신 메인 라우터 (토픽별 수신 및 분류)
│
├── routes/                   # [HTTP] REST API 라우터 (목적별 블루프린트 분리)
│   ├── auth.py               # 계정 관리 (회원가입, 로그인)
│   ├── app_api/              # 📱 안드로이드 앱 통신 전용 API
│   │   ├── command.py        # 기기/구역 등록 및 로봇 제어 명령 하달
│   │   └── dashboard.py      # 환경/작물 로그, 기기 상태 조회 (대시보드용)
│   └── robot_api/            # 🤖 하드웨어(로봇) 통신 전용 API
│       └── vision.py         # 작물 사진 AWS S3 업로드 및 질병 감지 알람
│
├── mqtt_handlers/            # [MQTT] 토픽별 DB 저장 및 비즈니스 로직 처리
├── requirements.txt          # 파이썬 라이브러리 설치 의존성 목록
└── restart.sh                # (AWS EC2 전용) 서버 자동 재시작 및 무중단 실행 쉘 스크립트
```

## 로컬 실행 방법 (How to run)

1. **저장소 클론**
   ```bash
   git clone https://github.com/graybeeer/horatius
   ```

2. **가상환경 생성 및 라이브러리 설치**
   ```bash
   python -m venv myenv
   source venv/bin/activate  # Mac/Linux
   # venv\Scripts\activate   # Windows
   pip install -r requirements.txt
   ```

3. **환경 설정 (Config)**
   - MariaDB를 설치하고 `ddalgi` 데이터베이스를 생성합니다.
   - 프로젝트 폴더에 있는 .env.template 파일을 복사한 후 .template를 지워 .env 파일을 생성합니다.
   - 생성된 .env 파일을 열고 데이터베이스 비밀번호, MQTT 주소, AWS 인증 키 등을 본인의 환경에 맞게 입력합니다.
   - 로컬에 Mosquitto MQTT 브로커를 실행합니다.

4. **서버 실행**
   ```bash
   python ddalgi_app.py
   ```