import bcrypt
from flask import current_app
from itsdangerous import URLSafeTimedSerializer
import os
from dotenv import load_dotenv
import secrets
from email_utils import send_email
from email_utils import send_email, styled_email_template

load_dotenv()

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT"))
EMAIL_USER = os.getenv("EMAIL_USER") 
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD") 

# ------------------ Password Utilities ------------------ #
def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt())

def check_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed)

# ------------------ Token Generators ------------------ #

def generate_verification_token(email):
    s = URLSafeTimedSerializer(current_app.config['JWT_SECRET_KEY'])
    return s.dumps(email)

def verify_token(token, max_age=300):
    s = URLSafeTimedSerializer(current_app.config['JWT_SECRET_KEY'])
    try:
        return s.loads(token, max_age=max_age)
    except Exception:
        return None

# ------------------ Email Sender ------------------ #
def send_verification_email(to_email: str, token: str) -> dict:
    link = f"http://localhost:5000/verify/{token}"
    subject = "Verify Your Email - JMeter Tool"

    message = f"""
    Thank you for signing up!<br><br>
    Please click the button below to verify your email address:
    <p style="text-align: center; margin: 30px 0;">
        <a href="{link}" target="_blank"
           style="background-color: #007bff; color: #fff; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold;">
            Verify Email
        </a>
    </p>
    This link is valid for 5 minutes for your security.<br><br>
    If you didn’t sign up for the JMeter Tool, you can ignore this email.
    """

    body = styled_email_template("Welcome to JMeter Tool", message)
    return send_email(to=to_email, subject=subject, body=body, is_html=True)



def generate_otp():
    return str(secrets.randbelow(900000) + 100000)

def send_otp_email(to_email: str, otp_code: str) -> dict:
    subject = "Your OTP for Password Reset - JMeter Tool"

    message = f"""
    We received a request to reset your password for the JMeter Tool account.<br><br>
    Your One-Time Password (OTP) is:
    <div style="text-align: center; margin: 30px 0;">
        <span style="display: inline-block; font-size: 28px; letter-spacing: 4px; background-color: #e9f2ff; padding: 12px 24px; border-radius: 5px; color: #007bff; font-weight: bold;">
            {otp_code}
        </span>
    </div>
    This code will expire in 5 minutes and can be used only once.<br><br>
    If you did not request a password reset, please ignore this email.
    """

    body = styled_email_template("Password Reset Request", message)
    return send_email(to=to_email, subject=subject, body=body, is_html=True)