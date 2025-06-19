from tasks.celery import celery, shared_task
from email_utils import _send_email_internal
from run_test import _run_jmeter_internal
from users.scheduler import check_expiry
from gemini import generate_with_gemini


@celery.task
def send_email_async(to, subject, body, attachments=None, is_html=False):
    return _send_email_internal(to, subject, body, attachments, is_html)

@celery.task
def run_jmeter_test_async(file_path, result_file_path):
    _run_jmeter_internal(file_path, result_file_path)

@celery.task
def check_expiry_task():
    check_expiry(loop=False) 

@shared_task
def generate_gemini_analysis_async(prompt):
    return generate_with_gemini(prompt)