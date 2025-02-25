from celery import Celery
from circ_toolbox.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND, CELERY_CONCURRENCY

def make_celery():
    celery = Celery("circ_toolbox", broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)
    celery.conf.update(
        worker_concurrency=CELERY_CONCURRENCY,
        task_acks_late=True,  # Ensure Celery waits until task is completed before acknowledging
        task_track_started=True  # Track task start time
    )
    return celery

celery_app = make_celery()
