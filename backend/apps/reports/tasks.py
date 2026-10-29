"""
Celery tasks for scheduled reporting.
"""
from celery import shared_task
import logging
from .services import dispatch_weekly_summary_email

logger = logging.getLogger(__name__)


@shared_task(name="weekly_officer_summary_email_job")
def weekly_officer_summary_email_job():
    """
    Periodic job triggered by Celery Beat to deliver weekly compliance email summary.
    """
    logger.info("Executing scheduled weekly officer compliance summary email job...")
    result = dispatch_weekly_summary_email()
    logger.info(f"Weekly officer summary email dispatched to {len(result['recipients'])} recipients.")
    return result
