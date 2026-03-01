from celery import Celery

from server.core.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "nexus_leads",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    timezone="UTC",
    enable_utc=True,
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=True,
)

celery_app.autodiscover_tasks(["server.workers"])
