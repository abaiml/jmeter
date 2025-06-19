import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import os
from typing import Union, List, Optional
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

# Load SMTP config from .env
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))

if not all([SENDER_EMAIL, SENDER_PASSWORD, SMTP_SERVER, SMTP_PORT]):
    logger.warning("⚠️ Missing email configuration in environment variables.")

def styled_email_template(title, message):
    return f"""
    <html>
      <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f6f8fa; padding: 20px; color: #333;">
        <table style="max-width: 600px; margin: auto; background-color: #ffffff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.05);">
          <tr>
            <td>
              <h2 style="color: #007bff;">{title}</h2>
              <p>{message}</p>
              <p style="margin-top: 40px;">Thanks,<br>The JMeter Tool Team</p>
            </td>
          </tr>
        </table>
      </body>
    </html>
    """


def _send_email_internal(to, subject, body, attachments=None, is_html=False) -> dict:
    """This does the actual sending logic, used both directly and by Celery."""
    try:
        recipients = [to] if isinstance(to, str) else to
        if not recipients or not all(isinstance(r, str) for r in recipients):
            raise ValueError("Recipient(s) must be a string or list of strings.")

        msg = MIMEMultipart()
        msg["From"] = SENDER_EMAIL
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject

        mime_subtype = "html" if is_html else "plain"
        msg.attach(MIMEText(body, mime_subtype, "utf-8"))

        if attachments:
            for file_path in attachments:
                if not os.path.isfile(file_path):
                    logger.warning(f"📎 Attachment not found: {file_path}")
                    continue
                with open(file_path, "rb") as f:
                    part = MIMEApplication(f.read(), Name=os.path.basename(file_path))
                    part["Content-Disposition"] = f'attachment; filename="{os.path.basename(file_path)}"'
                    msg.attach(part)

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, recipients, msg.as_string())

        logger.info(f"✅ Email sent to {', '.join(recipients)}")
        return {"success": f"Email sent to {len(recipients)} recipient(s)."}

    except Exception as e:
        logger.error(f"❌ Failed to send email: {e}")
        return {"error": f"Failed to send email: {str(e)}"}

# Public function: tries to use Celery if available
try:
    from tasks.tasks import send_email_async
except ImportError:
    send_email_async = None

def send_email(to, subject, body, attachments=None, is_html=False):
    if send_email_async:
        send_email_async.delay(to, subject, body, attachments, is_html)
        return {"message": "📨 Email task queued in background."}
    else:
        return _send_email_internal(to, subject, body, attachments, is_html)
