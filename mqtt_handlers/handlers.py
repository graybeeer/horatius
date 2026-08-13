from datetime import datetime
import uuid

def handle_crop_log(data, flask_app, db_instance):
    """작물 촬영 로그 및 ZoneBatch 처리 담당"""
    with flask_app.app_context():
        from ddalgi_models import CropLog, ZoneBatch 
        
        try:
            # growth_status를 0~100 사이의 숫자(Float)로 안전하게 변환
            growth_status_val = data.get("growth_status", 0.0)
            try:
                growth_status_float = float(growth_status_val)
            except (ValueError, TypeError):
                growth_status_float = 0.0

            health_status_val = data.get("health_status")
            zone_id = data.get("zone_id")
            crop_id = data.get("crop_id")
            
            # 1. CropLog(로그)에 영구 기록 추가 (과거 이력은 무조건 Insert)
            new_crop_log = CropLog(
                user_id=data.get("user_id"),
                robot_id=data.get("robot_id"),
                crop_id=crop_id,
                growth_status=growth_status_float, # Float 변환 값 적용
                health_status=health_status_val,
                zone_id=zone_id,
                timestamp=data.get("timestamp", datetime.now()),
            )
            db_instance.session.add(new_crop_log)
            
            # 2. ⭐️ ZoneBatch(재배 데이터) Upsert 로직
            provided_batch_id = data.get("batch_id")

            if zone_id and crop_id:
                existing_batch = None
                final_batch_id = None
                
                # 로봇이 batch_id를 같이 보냈다면 DB에서 기존 데이터 검색
                if provided_batch_id:
                    existing_batch = ZoneBatch.query.filter_by(batch_id=provided_batch_id).first()
                    final_batch_id = provided_batch_id
                else:
                    # 안 보냈다면 고유한 batch_id 새로 생성
                    time_str = datetime.now().strftime("%Y%m%d%H%M%S")
                    final_batch_id = f"{zone_id}_{time_str}_{uuid.uuid4().hex[:4]}"
                
                # 질병 상태일 경우 메시지 자동 생성
                disease_name_val = "확인 필요(사진 참고)" if health_status_val and health_status_val.lower() == 'disease' else None
                
                if existing_batch:
                    # DB에 같은 batch_id가 있으면 최신 상태로 덮어쓰기 (Update)
                    existing_batch.crop_id = crop_id
                    existing_batch.growth_status = growth_status_float
                    existing_batch.health_status = health_status_val
                    existing_batch.disease_name = disease_name_val
                    print(f"🔄 [작물 담당] 기존 재배 데이터 갱신 완료 (ID: {final_batch_id})")
                else:
                    # 새로운 식물이면 새 줄 추가 (Insert)
                    new_batch = ZoneBatch(
                        batch_id=final_batch_id,
                        zone_id=zone_id,
                        crop_id=crop_id,
                        growth_status=growth_status_float,
                        health_status=health_status_val,
                        disease_name=disease_name_val
                    )
                    db_instance.session.add(new_batch)
                    print(f"🌱 [작물 담당] 새 재배 데이터 추가 완료 (ID: {final_batch_id})")

            # 3. DB에 두 테이블 변경사항 한 번에 반영
            db_instance.session.commit()
            
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

            # 구역(Zone) 변경 감지 로그
            new_current_zone = data.get("current_zone")
            if new_current_zone and robot.current_zone != new_current_zone:
                print(f"📍 [구역 이동] {robot_id} 로봇이 이동했습니다! (이전: {robot.current_zone} -> 현재: {new_current_zone})")

            # 마커(Marker) 변경 감지 로그
            new_marker = data.get("marker_id")
            if new_marker and robot.last_marker_id != new_marker:
                print(f"📍 [마커 이동] {robot_id} 로봇 마커 변경! (이전: {robot.last_marker_id} -> 현재: {new_marker})")
            
            # 모든 상태값 한 번에 업데이트 (구역, 마커 포함)
            robot.current_zone = data.get("current_zone", robot.current_zone)
            robot.last_marker_id = data.get("marker_id", robot.last_marker_id)
            robot.battery = data.get("battery", robot.battery)
            robot.operating_status = data.get("operating_status", robot.operating_status)
            robot.lat = data.get("lat", robot.lat)
            robot.lng = data.get("lng", robot.lng)
            robot.last_updated = datetime.now()
            
            db_instance.session.commit()
            print(f"[상태 담당] {robot_id} 로봇 상태 업데이트 완료 (배터리: {robot.battery}%)")
        except Exception as e:
            db_instance.session.rollback()
            print(f"❌ [상태 담당] DB 업데이트 에러: {e}")