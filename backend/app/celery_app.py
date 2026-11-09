"""The Celery application. Feature packages register tasks by importing ``celery`` from here.

Every task module must be listed in ``include`` or the worker raises "unregistered task" even though
API-side tests (which never start a worker) pass.
"""
from celery import Celery

from app.config import settings

TASK_MODULES = [
    "app.tasks",
    "app.diagnosis.tasks",
    "app.quality.tasks",
    "app.assistant.tasks",
    "app.incidents.tasks",
    "app.assessments.tasks",
]

celery = Celery("leetbug", broker=settings.redis_url, backend=settings.redis_url, include=TASK_MODULES)
celery.conf.update(
    task_serializer="json", result_serializer="json", accept_content=["json"],
    task_ignore_result=True, task_acks_late=True, task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1, task_soft_time_limit=170, task_time_limit=180,
    broker_connection_retry_on_startup=True, broker_transport_options={"visibility_timeout": 240},
    # Problem-quality jobs (validation and mutation execution) run on a separate low-concurrency
    # worker so they never compete with user submissions for the default queue.
    task_routes={"app.quality.*": {"queue": "quality"}},
    beat_schedule={
        "clean-expired-jobs": {"task": "app.tasks.cleanup", "schedule": 60.0},
        "expire-assessment-sessions": {"task": "app.assessments.expire_sessions", "schedule": 30.0},
        "recover-quality-jobs": {"task": "app.quality.recover", "schedule": 120.0},
    },
)
