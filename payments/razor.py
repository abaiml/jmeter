import razorpay
import os
import hmac
import hashlib

RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

def create_order(amount, receipt_id, currency="INR"):
    try:
        client = razorpay.Client(
            auth=(os.getenv("RAZORPAY_KEY_ID"), RAZORPAY_KEY_SECRET)
        )
        return client.order.create({
            "amount": amount,
            "currency": currency,
            "receipt": receipt_id,
            "payment_capture": 1
        })
    except Exception as e:
        return {"error": str(e)}

def verify_signature(order_id, payment_id, signature):
    generated_signature = hmac.new(
        RAZORPAY_KEY_SECRET.encode(),
        f"{order_id}|{payment_id}".encode(),
        hashlib.sha256
    ).hexdigest()
    return generated_signature == signature
