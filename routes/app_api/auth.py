# routes/auth.py
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from ddalgi_models import db, User

# 'auth_bp'라는 이름의 블루프린트(설계도 조각)를 만듭니다.
auth_bp = Blueprint('auth', __name__)
# 회원가입, 로그인
# ---------------------------------------------------------
# API 엔드포인트: 회원가입 (/signup)
# ---------------------------------------------------------
@auth_bp.route('/signup', methods=['POST'])
def signup():
    # 안드로이드 앱에서 보낸 JSON 데이터 받기
    data = request.get_json()
    
    user_id = data.get('user_id')
    password = data.get('password')
    name = data.get('name')
    phone_number = data.get('phone_number')
    country = data.get('country')
    email = data.get('email')

    # 필수 값이 빠져있는지 확인
    if not user_id or not password or not name or not phone_number or not email:
        return jsonify({"status": "error", "message": "필수 정보를 모두 입력해주세요."}), 400

    # 이미 존재하는 아이디인지 확인
    existing_user = User.query.filter_by(user_id=user_id).first()
    if existing_user:
        return jsonify({"status": "error", "message": "이미 존재하는 아이디입니다."}), 409

    # 비밀번호 암호화 (보안 처리)
    hashed_password = generate_password_hash(password)

    # 새 사용자 객체 생성 및 DB에 저장
    new_user = User(
        user_id=user_id, 
        password=hashed_password, 
        name=name, 
        phone_number=phone_number, 
        country=country,
        email=email 
    )
    
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"status": "success", "message": "회원가입이 완료되었습니다."}), 201


# ---------------------------------------------------------
# API 엔드포인트: 로그인 (/login)
# ---------------------------------------------------------
@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    
    user_id = data.get('user_id')
    password = data.get('password')

    if not user_id or not password:
        return jsonify({"status": "error", "message": "아이디와 비밀번호를 입력해주세요."}), 400

    # DB에서 사용자 검색
    user = User.query.filter_by(user_id=user_id).first()

    # 사용자가 존재하고, 비밀번호가 일치하는지 확인 (해시 비교)
    if user and check_password_hash(user.password, password):
        return jsonify({
            "status": "success", 
            "message": f"{user.name}님 환영합니다!",
            "data": {
                "user_id": user.user_id,
                "name": user.name
            }
        }), 200
    else:
        return jsonify({"status": "error", "message": "아이디 또는 비밀번호가 잘못되었습니다."}), 401