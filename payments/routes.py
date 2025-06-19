from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from .razor import create_order, verify_signature
from users.models import update_user, find_user
from email_utils import send_email, styled_email_template
from datetime import datetime, timedelta
import uuid
import os

payments_bp = Blueprint("payments", __name__)
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
BASE_PRICE_INR = 20000

EXCHANGE_RATES = {
    "INR": 1,
    "USD": 0.0116,
    "EUR": 0.0101,
    "GBP": 0.0086,
    "AUD": 0.0179,
    "CAD": 0.0158,
    "SGD": 0.0149,
    "CHF": 0.0094,
    "JPY": 1.6789,
    "CNY": 0.0833,
    "SAR": 0.0435,
    "AED": 0.0426,
    "HKD": 0.0911,
    "MYR": 0.0493,
    "QAR": 0.0422,
    "THB": 0.3763,
    "ZAR": 0.2085,
    "BHD": 0.0093,
    "KRW": 13.45,
    "SEK": 0.112,
    "DKK": 0.0758,
    "NOK": 0.107,
    "RUB": 1.12,
    "MXN": 0.198,
    "BRL": 0.058,
    "PHP": 0.65,
    "IDR": 178.45,
    "TRY": 0.35,
    "PLN": 0.045,
    "VND": 275.0
}


@payments_bp.route("/create-order", methods=["POST"])
@jwt_required()
def create_payment_order():
    identity = get_jwt_identity()
    user = find_user(identity)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json()
    months = int(data.get("months", 1))
    currency = data.get("currency", "INR").upper()

    if months < 1 or currency not in EXCHANGE_RATES:
        return jsonify({"error": "Invalid input"}), 400

    exchange_rate = EXCHANGE_RATES[currency]
    base_amount = BASE_PRICE_INR * months
    if months >= 12:
        base_amount *= 0.95

    amount_in_currency = round(base_amount * exchange_rate * 100)
    receipt_id = str(uuid.uuid4())

    order = create_order(amount_in_currency, receipt_id, currency=currency)
    if "error" in order:
        return jsonify(order), 500

    return jsonify(order)


@payments_bp.route("/verify-payment", methods=["POST"])
@jwt_required()
def verify_payment():
    data = request.get_json()
    identity = get_jwt_identity()

    razorpay_order_id = data.get("razorpay_order_id")
    razorpay_payment_id = data.get("razorpay_payment_id")
    razorpay_signature = data.get("razorpay_signature")
    months = int(data.get("months", 1))
    currency = data.get("currency", "INR").upper()

    if not (razorpay_order_id and razorpay_payment_id and razorpay_signature):
        return jsonify({"error": "Missing payment verification data"}), 400

    # Verify signature
    if not verify_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
        return jsonify({"error": "Invalid payment signature"}), 400

    # Extend user's subscription
    new_paid_end = datetime.utcnow() + timedelta(days=30 * months)
    update_user(identity, {
        "paid_ends_at": new_paid_end,
        "trial_ends_at": None
    })

    # Email notifications
    send_email(
        to=ADMIN_EMAIL,
        subject="New Payment Verified - JMeter Tool",
        body=styled_email_template(
            "Payment Verified",
            f"User <strong>{identity}</strong> has paid successfully for a <strong>{months}-month</strong> plan using <strong>{currency}</strong>."
        ),
        is_html=True
    )

    send_email(
        to=identity,
        subject="Payment Successful - JMeter Tool",
        body=styled_email_template(
            "Your Payment was Successful",
            f"Your <strong>{months}-month</strong> subscription is now active. You paid in <strong>{currency}</strong>. Enjoy full access!"
        ),
        is_html=True
    )

    return jsonify({"message": "Payment verified successfully"}), 200
