"""
Celery application factory.

Beat schedule:
  - check_low_stock: every 6 hours — query inventory and emit LowStockEvents
  - escalate_overdue_approvals: every hour — check approval timeouts
  - cleanup_expired_tokens: daily — purge expired Redis blacklist keys
"""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "epims",
    broker=settings.celery_broker,
    backend=settings.celery_backend,
    include=[
        "app.tasks.email_tasks",
        "app.tasks.report_tasks",
        "app.tasks.inventory_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=86400,  # 24 hours
)

# ── Beat schedule ─────────────────────────────────────────────────────────────

celery_app.conf.beat_schedule = {
    "check-low-stock": {
        "task": "app.tasks.inventory_tasks.check_low_stock",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    "escalate-overdue-approvals": {
        "task": "app.tasks.email_tasks.escalate_overdue_approvals",
        "schedule": crontab(minute=0),  # every hour
    },
    "cleanup-expired-tokens": {
        "task": "app.tasks.email_tasks.cleanup_expired_tokens",
        "schedule": crontab(minute=0, hour=2),  # 2 AM daily
    },
}
