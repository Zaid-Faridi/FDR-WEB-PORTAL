import logging
from celery import shared_task
from apps.notifications.services import run_monitoring_job

logger = logging.getLogger(__name__)


@shared_task(name="daily_fdr_lifecycle_and_reminders_job")
def daily_fdr_lifecycle_and_reminders_job():
    """
    Celery beat periodic task:
    Runs daily to evaluate instrument maturity dates, recompute statuses,
    fire reminders, and escalate overdue compliance items.
    """
    logger.info("Starting scheduled daily FDR lifecycle and reminders task...")
    result = run_monitoring_job(triggered_by='celery_beat')
    logger.info(f"Daily FDR lifecycle task completed: {result}")
    return result
