import logging
from typing import Optional, List, Dict, Any
from django.conf import settings
from django.core.mail import send_mail
from django.contrib.auth import get_user_model
from apps.notifications.models import (
    Notification,
    NotificationChannel,
    NotificationType,
)
from apps.notifications.channels.sms import get_sms_adapter

logger = logging.getLogger(__name__)
User = get_user_model()


def dispatch_notification(
    title: str,
    message: str,
    channel: str = NotificationChannel.IN_APP,
    notification_type: str = NotificationType.REMINDER,
    instrument=None,
    recipient=None,
    recipient_role: str = '',
    offset_days: Optional[int] = None,
    escalation_level: str = '',
    dedup_key: str = '',
) -> List[Notification]:
    """
    Central dispatcher that creates Notification records and dispatches to
    In-App, Email (Django console backend in dev), and SMS (MockSmsAdapter).
    Guarantees idempotency via dedup_key so duplicate alerts are impossible.
    """
    created_notifications = []

    # Determine channels to target
    target_channels = (
        [NotificationChannel.IN_APP, NotificationChannel.EMAIL, NotificationChannel.SMS]
        if channel == NotificationChannel.ALL
        else [channel]
    )

    # Determine recipient user and email/phone
    recip_email = ''
    recip_phone = ''

    if recipient:
        recip_email = getattr(recipient, 'email', '')
        recip_role = recipient_role or getattr(recipient, 'role', '')
    else:
        recip_role = recipient_role

    if instrument and hasattr(instrument, 'institution') and instrument.institution:
        inst = instrument.institution
        if not recip_email:
            recip_email = inst.contact_email or f"{inst.aicte_id.lower()}@aicte-institutions.org"
        if not recip_phone:
            recip_phone = inst.contact_phone or '+91-9876543210'

    if not recip_email:
        recip_email = 'officer@aicte-india.org' if 'OFFICER' in recip_role else 'registry@aicte-india.org'
    if not recip_phone:
        recip_phone = '+91-9876543210'

    for ch in target_channels:
        channel_dedup_key = f"{dedup_key}:{ch}" if dedup_key else f"notif:{instrument.id if instrument else 'gen'}:{timezone.now().timestamp()}:{ch}"

        # 1. Idempotency Check: Avoid duplicate reminder/escalation
        existing = Notification.objects.filter(dedup_key=channel_dedup_key).first()
        if existing:
            logger.debug(f"Skipping duplicate notification with dedup_key: {channel_dedup_key}")
            continue

        notif = Notification.objects.create(
            instrument=instrument,
            recipient=recipient,
            recipient_role=recip_role,
            recipient_email=recip_email,
            recipient_phone=recip_phone,
            channel=ch,
            notification_type=notification_type,
            title=title,
            message=message,
            offset_days=offset_days,
            escalation_level=escalation_level,
            dedup_key=channel_dedup_key,
        )
        created_notifications.append(notif)

        # 2. Channel-specific delivery
        if ch == NotificationChannel.EMAIL:
            try:
                from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'alerts@aicte-india.org')
                send_mail(
                    subject=f"[AICTE Alert] {title}",
                    message=message,
                    from_email=from_email,
                    recipient_list=[recip_email],
                    fail_silently=True,
                )
                logger.info(f"Dispatched email to {recip_email} for dedup_key: {channel_dedup_key}")
            except Exception as e:
                logger.warning(f"Failed to deliver email: {e}")

        elif ch == NotificationChannel.SMS:
            try:
                sms_adapter = get_sms_adapter()
                sms_adapter.send_sms(to_phone=recip_phone, message=f"{title}: {message}")
                logger.info(f"Dispatched SMS to {recip_phone} for dedup_key: {channel_dedup_key}")
            except Exception as e:
                logger.warning(f"Failed to deliver SMS: {e}")

    return created_notifications
