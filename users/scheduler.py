import os
import time
from datetime import datetime
from dotenv import load_dotenv
from .models import users
from email_utils import send_email
from email_utils import styled_email_template

load_dotenv()
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")

def check_expiry(loop=False, interval_seconds=3600):
    """
    Check all users for trial or paid plan expiration and notify them and the admin.
    If `loop` is True, it runs every interval. If False, runs once (used by cron).
    """

    def run_once():
        now = datetime.utcnow()
        for user in users.find():
            email = user.get('email')
            updates = {}

            # Trial plan expiration
            trial_ends_at = user.get("trial_ends_at")
            if trial_ends_at and now > trial_ends_at:
                try:
                    send_email(
                        to=email,
                        subject="Your Trial Has Ended - JMeter Tool",
                        body=styled_email_template(
                            "Your Trial Has Ended",
                            "Your 7-day trial for the JMeter Tool has expired. Upgrade your plan to continue accessing performance testing features."
                        ),
                        is_html=True
                    )
                    send_email(
                        to=ADMIN_EMAIL,
                        subject="User Trial Ended",
                        body=f"User trial ended: {email}"
                    )
                    updates["trial_ends_at"] = None
                except Exception as e:
                    print(f"[Error] Trial expiry email failed for {email}: {e}")

            # Paid plan expiration
            paid_ends_at = user.get("paid_ends_at")
            if paid_ends_at and now > paid_ends_at:
                try:
                    send_email(
                        to=email,
                        subject="Your Paid Plan Has Expired - JMeter Tool",
                        body=styled_email_template(
                            "Your Paid Plan Has Expired",
                            "Your subscription to the JMeter Tool has ended. Renew now to regain access to all features and reports."
                        ),
                        is_html=True
                    )
                    send_email(
                        to=ADMIN_EMAIL,
                        subject="User Paid Plan Expired",
                        body=f"User paid plan expired: {email}"
                    )
                    updates["paid_ends_at"] = None
                except Exception as e:
                    print(f"[Error] Paid expiry email failed for {email}: {e}")

            if updates:
                users.update_one({"email": email}, {"$set": updates})

    if loop:
        while True:
            run_once()
            time.sleep(interval_seconds)
    else:
        run_once()