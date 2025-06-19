from flask import Blueprint, request, jsonify, redirect
from datetime import datetime, timedelta
from .models import create_user, find_user, mark_user_verified, update_user, save_otp, get_latest_otp, mark_otp_used
from .utils import (
    hash_password, check_password,
    generate_verification_token,
    verify_token, send_verification_email, generate_otp, send_otp_email
)
from flask_jwt_extended import (
    create_access_token, create_refresh_token, jwt_required,
    get_jwt_identity, set_refresh_cookies, unset_jwt_cookies
)
from users import limiter
import os 
from dotenv import load_dotenv
from .licence_utils import get_license_info

load_dotenv() 

FRONTEND_ORIGIN = os.getenv("CORS_ORIGIN")


auth_bp = Blueprint('auth', __name__)

# -------------------- SIGNUP --------------------
@auth_bp.route('/signup', methods=['POST'])
@limiter.limit("5 per minute")
def signup():
    data = request.json

    # Extract fields
    email = data.get("email")
    password = data.get("password")
    full_name = data.get("fullName")
    phone = data.get("phone")
    organization_name = data.get("organizationName")
    organization_type = data.get("organizationType")
    country = data.get("country")

    # Check for missing fields
    required_fields = {
        "email": email,
        "password": password,
        "fullName": full_name,
        "phone": phone,
        "organizationName": organization_name,
        "country": country
    }

    missing_fields = [key for key, value in required_fields.items() if not value]
    if missing_fields:
        return jsonify({"error": f"Missing fields: {', '.join(missing_fields)}"}), 400

    existing_user = find_user(email)
    if existing_user:
        if existing_user.get("is_verified"):
            return jsonify({"error": "User already exists."}), 400
        else:
            token = generate_verification_token(email)
            send_verification_email(email, token)
            return jsonify({"message": "User already exists but not verified. Verification email re-sent."}), 200

    hashed_pw = hash_password(password)
    create_user(email, hashed_pw, full_name, phone, organization_name, organization_type, country)

    token = generate_verification_token(email)
    send_verification_email(email, token)

    return jsonify({"message": "User created. Please verify your email."}), 201


# -------------------- VERIFY EMAIL --------------------
@auth_bp.route('/verify/<token>', methods=['GET'])
def verify_email(token):
    email = verify_token(token)
    if not email:
        return redirect(f"{FRONTEND_ORIGIN}/verified-popup?status=error")

    user = find_user(email)
    if not user:
        return redirect(f"{FRONTEND_ORIGIN}/verified-popup?status=not_found")

    if user.get("is_verified"):
        return redirect(f"{FRONTEND_ORIGIN}/verified-popup?status=already_verified")

    mark_user_verified(email)
    return redirect(f"{FRONTEND_ORIGIN}/verified-popup?status=success")

# -------------------- RESEND VERIFICATION --------------------
@auth_bp.route('/resend-verification', methods=['POST'])
def resend_verification():
    data = request.json
    email = data.get("email")
    user = find_user(email)
    if not user:
        return jsonify({"error": "User not found."}), 404
    if user.get("is_verified"):
        return jsonify({"message": "User already verified."}), 200

    token = generate_verification_token(email)
    send_verification_email(email, token)
    return jsonify({"message": "Verification email sent."}), 200

# -------------------- LOGIN --------------------
@auth_bp.route('/login', methods=['POST'])
@limiter.limit("10 per minute")
def login():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    user = find_user(email)
    if not user or not check_password(password, user.get("password", "")):
        return jsonify({"error": "Invalid credentials."}), 401

    if not user.get("is_verified"):
        return jsonify({"error": "Email not verified."}), 403

    license_info = get_license_info(user)

    access_token = create_access_token(identity=email)
    refresh_token = create_refresh_token(identity=email)

    user_info = {
        "email": user.get("email", ""),
        "name": user.get("name", user.get("fullName", "")),
        "mobile": user.get("mobile", user.get("phone", "")),
        "organization": user.get("organizationName", user.get("organization", "")),
        "country": user.get("country", ""),
        "is_verified": user.get("is_verified", False),
        **license_info
    }

    response = jsonify({
        "access_token": access_token,
        "user": user_info
    })
    set_refresh_cookies(response, refresh_token)
    return response, 200




@auth_bp.route('/refresh', methods=['POST', 'OPTIONS'])
@jwt_required(refresh=True)
def refresh_token():
    identity = get_jwt_identity()
    new_token = create_access_token(identity=identity)

    user = find_user(identity)
    if not user:
        return jsonify({"error": "User not found."}), 404

    license_type, trial_ends_at, paid_ends_at = get_license_info(user)

    user_info = {
        "email": user.get("email", ""),
        "name": user.get("name", user.get("fullName", "")),
        "mobile": user.get("mobile", user.get("phone", "")),
        "organization": user.get("organizationName", user.get("organization", "")),
        "country": user.get("country", ""),
        "license": license_type,
        "trial_ends_at": trial_ends_at.isoformat() if trial_ends_at else None,
        "paid_ends_at": paid_ends_at.isoformat() if paid_ends_at else None,
        "is_verified": user.get("is_verified", False)
    }

    return jsonify({
        "access_token": new_token,
        "user": user_info
    }), 200


# -------------------- LOGOUT --------------------
@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    response = jsonify({"message": "Logout successful."})
    unset_jwt_cookies(response)
    return response, 200



# -------------------- RESET PASSWORD --------------------

@auth_bp.route("/request-reset", methods=["POST"])
@limiter.limit("3 per minute")
def request_reset():
    data = request.json
    email = data.get("email")

    user = find_user(email)
    if not user:
        return jsonify({"error": "User not found."}), 404

    otp_code = generate_otp()
    hashed_otp = hash_password(otp_code)

    save_otp(email, hashed_otp)
    send_otp_email(email, otp_code)

    return jsonify({"message": "OTP sent to your email."}), 200

@auth_bp.route("/reset-password-with-otp", methods=["POST"])
def reset_with_otp():
    data = request.json
    email = data.get("email")
    otp_input = data.get("otp")
    new_password = data.get("password")

    if not all([email, otp_input, new_password]):
        return jsonify({"error": "Email, OTP, and password required."}), 400

    otp_record = get_latest_otp(email)
    if not otp_record:
        return jsonify({"error": "Invalid or expired OTP."}), 400

    if not check_password(otp_input, otp_record["otp"]):
        return jsonify({"error": "Incorrect OTP."}), 400

    # Mark OTP as used
    mark_otp_used(email)

    update_user(email, {
        "password": hash_password(new_password)
    })

    return jsonify({"message": "Password reset successful."}), 200

@auth_bp.route("/verify-otp", methods=["POST"])
@limiter.limit("5 per minute")
def verify_otp():
    data = request.json
    email = data.get("email")
    otp_input = data.get("otp")

    if not all([email, otp_input]):
        return jsonify({"error": "Email and OTP required."}), 400

    otp_record = get_latest_otp(email)
    if not otp_record:
        return jsonify({"error": "Invalid or expired OTP."}), 400

    if not check_password(otp_input, otp_record["otp"]):
        return jsonify({"error": "Incorrect OTP."}), 400

    return jsonify({"message": "OTP verified successfully."}), 200

