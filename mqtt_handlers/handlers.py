from datetime import datetime
import uuid

def handle_crop_log(data, flask_app, db_instance):
    """작물 촬영 로그 및 ZoneBatch 처리 담당"""
    with flask_app.app_context():
        # 💡 ZoneBatch 모델도 함께 불러옵니다.
        from ddalgi_models import CropLog, ZoneBatch 
        
        try:
            # 1. CropLog(로그)에 영구 기록 추가
            new_crop_log = CropLog(
                user_id=data.get("user_id"),
                robot_id=data.get("robot_id"),
                crop_id=data.get("crop_id"),
                growth_status=data.get("growth_status"), # 테이블 명세에 맞게 growth_status로 수정
                health_status=data.get("health_status"),
                zone_id=data.get("zone_id"),
                timestamp=data.get("timestamp", datetime.now()),
            )
            db_instance.session.add(new_crop_log)
            
            # 2. ⭐️ ZoneBatch(재배 데이터)에도 무조건 새 줄(Insert)로 쌓기
            zone_id = data.get("zone_id")
            crop_id = data.get("crop_id")
            
            if zone_id and crop_id:
                # 고유한 batch_id 생성 (예: zone01_202608041530_a1b2)
                time_str = datetime.now().strftime("%Y%m%d%H%M%S")
                unique_batch_id = f"{zone_id}_{time_str}_{uuid.uuid4().hex[:4]}"
                
                health_status = data.get("health_status")
                disease_name = "확인 필요(사진 참고)" if health_status and health_status.lower() == 'disease' else None
                
                new_batch = ZoneBatch(
                    batch_id=unique_batch_id,
                    zone_id=zone_id,
                    crop_id=crop_id,
                    growth_status=data.get("growth_status"),
                    health_status=health_status,
                    disease_name=disease_name
                )
                db_instance.session.add(new_batch)

            # 3. DB에 두 테이블 변경사항 한 번에 반영
            db_instance.session.commit()
            print("💾 [작물 담당] 작물 촬영 로그 및 ZoneBatch 저장 완료")
            
        except Exception as e:
            db_instance.session.rollback()
            print(f"❌ [작물 담당] DB 저장 에러: {e}")

def handle_env_log(data, flask_app, db_instance):
    """환경 및 통계 로그 처리 담당"""
    with flask_app.app_context():
        from ddalgi_models import EnvLog
        try:
            new_env_log = EnvLog(
                user_id=data.get("user_id"),
                robot_id=data.get("robot_id"),
                timestamp=data.get("timestamp", datetime.now()),
                temperature=data.get("temperature"),
                humidity=data.get("humidity")
            )
            db_instance.session.add(new_env_log)
            db_instance.session.commit()
            print("💾 [환경 담당] 환경 및 통계 로그 DB 저장 완료")
        except Exception as e:
            db_instance.session.rollback()
            print(f"❌ [환경 담당] DB 저장 에러: {e}")
            

def handle_robot_status(data, flask_app, db_instance):
    """로봇 상태 업데이트 처리 담당"""
    robot_id = data.get("robot_id")
    if not robot_id:
        return
        
    with flask_app.app_context():
        from ddalgi_models import Robot
        try:
            robot = Robot.query.filter_by(robot_id=robot_id).first()
            
            if not robot:
                print(f"[상태 담당] 로봇 ID {robot_id}를 DB에서 찾을 수 없습니다.")
                return

            # 구역(Zone) 변경 감지 및 업데이트
            new_current_zone = data.get("current_zone")
            if new_current_zone and robot.current_zone != new_current_zone:
                print(f"📍 [구역 이동] {robot_id} 로봇이 이동했습니다! (이전: {robot.current_zone} -> 현재: {new_current_zone})")
                # ⭐️ [수정됨] 새 구역으로 DB 값 변경 (이 코드가 없으면 로그가 무한 반복됩니다!)
                robot.current_zone = new_current_zone 

            # 마커(Marker) 변경 감지 및 업데이트
            new_marker = data.get("marker_id")
            if new_marker and robot.last_marker_id != new_marker:
                print(f"📍 [마커 이동] {robot_id} 로봇 마커 변경! (이전: {robot.last_marker_id} -> 현재: {new_marker})")
                # 마커 업데이트는 기존에 잘 작성하셨던 아래쪽 코드에서 처리됩니다.
            
            # 나머지 상태값 업데이트
            robot.battery = data.get("battery", robot.battery)
            robot.last_marker_id = data.get("marker_id", robot.last_marker_id)
            robot.operating_status = data.get("operating_status", robot.operating_status)
            robot.lat = data.get("lat", robot.lat)
            robot.lng = data.get("lng", robot.lng)
            robot.last_updated = datetime.now()
            
            db_instance.session.commit()
            print(f"[상태 담당] {robot_id} 로봇 상태 업데이트 완료 (배터리: {robot.battery}%)")
        except Exception as e:
            db_instance.session.rollback()
            print(f"❌ [상태 담당] DB 업데이트 에러: {e}")