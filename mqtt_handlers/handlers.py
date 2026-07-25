from datetime import datetime

def handle_crop_log(data, flask_app, db_instance):
    """작물 촬영 로그 처리 담당"""
    with flask_app.app_context():
        from ddalgi_models import CropLog
        try:
            new_crop_log = CropLog(
                user_id=data.get("user_id"),
                robot_id=data.get("robot_id"),
                crop_id=data.get("crop_id"),
                growth_stage=data.get("growth_status"),
                health_status=data.get("health_status"),
                zone_id=data.get("zone_id"),
                timestamp=data.get("timestamp", datetime.now()),
            )
            db_instance.session.add(new_crop_log)
            db_instance.session.commit()
            print("💾 [작물 담당] 작물 촬영 로그 DB 저장 완료")
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
                temperature=data.get("temperature"),
                humidity=data.get("humidity"),
                ripe_count=data.get("ripe_count"),
                unripe_count=data.get("unripe_count"),
                disease_count=data.get("disease_count")
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