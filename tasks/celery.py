from celery import Celery
from celery.schedules import crontab
import os
from dotenv import load_dotenv


load_dotenv()

celery = Celery(
    "tasks",
    broker=os.getenv("REDIS_URL"),
    backend=os.getenv("REDIS_URL"),
    include=["tasks.tasks"]
)

celery.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='UTC',
    beat_schedule={
        'check-expired-users-every-hour': {
            'task': 'tasks.task.check_expiry_task',
            'schedule': crontab(minute=0, hour='*'),  # Every hour
        }
    }
)

shared_task = celery.task  # for compatibility

celery.conf.task_routes = {
    'tasks.tasks.run_jmeter_test_async': {'queue': 'jmeter'},
    'tasks.tasks.generate_gemini_analysis_async': {'queue': 'gemini'},
    'tasks.tasks.check_expiry_task': {'queue': 'scheduler'},
}


