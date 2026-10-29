from django.db import models
from django.conf import settings
from django.utils import timezone


class NotificationChannel(models.TextChoices):
    IN_APP = 'IN_APP', 'In-App Portal Notification'
    EMAIL = 'EMAIL', 'Email Alert'
    SMS = 'SMS', 'SMS Text'
    ALL = 'ALL', 'All Supported Channels'


class NotificationType(models.TextChoices):
    REMINDER = 'REMINDER', 'Maturity / Renewal Reminder'
    ESCALATION = 'ESCALATION', 'Administrative Escalation'
    STATUS_CHANGE = 'STATUS_CHANGE', 'Status Transition Notice'
    OVERDUE = 'OVERDUE', 'Overdue Compliance Alert'


class ReminderRule(models.Model):
    """
    Configurable reminder rule defining when reminders trigger
    (e.g., 90, 60, 30, 7 days before maturity).
    """
    name = models.CharField(max_length=150)
    offset_days = models.IntegerField(
        help_text="Number of days before FDR maturity date when reminder triggers"
    )
    channel = models.CharField(
        max_length=20,
        choices=NotificationChannel.choices,
        default=NotificationChannel.IN_APP
    )
    target_role = models.CharField(
        max_length=50,
        default='INSTITUTION',
        help_text="Target role receiving this reminder (e.g. INSTITUTION, SCRUTINY_OFFICER, ALL)"
    )
    template_subject = models.CharField(
        max_length=255,
        default="AICTE FDR Maturity Notice: {reference_number}"
    )
    template_body = models.TextField(
        default="Security deposit / FDR #{reference_number} for {institution_name} is maturing in {days_left} days on {maturity_date}. Please initiate renewal or submit release documentation."
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-offset_days']

    def __str__(self):
        return f"ReminderRule: {self.name} ({self.offset_days} days before maturity via {self.channel})"


class EscalationCondition(models.TextChoices):
    OVERDUE_MATURED = 'OVERDUE_MATURED', 'Matured FDR Unaddressed Beyond Grace Period'
    UNRESOLVED_DISCREPANCY = 'UNRESOLVED_DISCREPANCY', 'Discrepancy Unresolved Past SLA'
    EXPIRING_NO_ACTION = 'EXPIRING_NO_ACTION', 'Expiring FDR with No Renewal Action'


class EscalationRule(models.Model):
    """
    Configurable escalation chain escalating unresolved cases
    (e.g., Institution -> Scrutiny Officer -> Senior Officer / Approving Authority -> Director).
    """
    name = models.CharField(max_length=150)
    trigger_condition = models.CharField(
        max_length=50,
        choices=EscalationCondition.choices,
        default=EscalationCondition.OVERDUE_MATURED
    )
    wait_period_days = models.IntegerField(
        help_text="Wait period in days after the condition is met before escalating to this level"
    )
    from_level = models.CharField(
        max_length=50,
        default='INSTITUTION',
        help_text="Originating role / level (e.g. INSTITUTION, SCRUTINY_OFFICER)"
    )
    to_level = models.CharField(
        max_length=50,
        default='SCRUTINY_OFFICER',
        help_text="Escalation target role (e.g. SCRUTINY_OFFICER, APPROVING_AUTHORITY, DIRECTOR, ADMIN)"
    )
    channel = models.CharField(
        max_length=20,
        choices=NotificationChannel.choices,
        default=NotificationChannel.IN_APP
    )
    template_subject = models.CharField(
        max_length=255,
        default="ESCALATION LEVEL {to_level}: FDR #{reference_number} Compliance Overdue"
    )
    template_body = models.TextField(
        default="Case escalated to {to_level}: Instrument #{reference_number} ({institution_name}) has remained unresolved for {wait_days} days. Immediate regulatory intervention is required."
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['wait_period_days']

    def __str__(self):
        return f"EscalationRule: {self.name} ({self.from_level} -> {self.to_level} after {self.wait_period_days} days)"


class Notification(models.Model):
    """
    Multi-channel notification dispatched to users.
    Includes a dedup_key ensuring idempotent delivery and avoiding duplicate reminders.
    """
    instrument = models.ForeignKey(
        'instruments.Instrument',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications'
    )
    recipient_role = models.CharField(max_length=50, blank=True, db_index=True)
    recipient_email = models.CharField(max_length=255, blank=True)
    recipient_phone = models.CharField(max_length=30, blank=True)
    channel = models.CharField(max_length=20, choices=NotificationChannel.choices, default=NotificationChannel.IN_APP)
    notification_type = models.CharField(max_length=50, choices=NotificationType.choices, default=NotificationType.REMINDER)
    title = models.CharField(max_length=255)
    message = models.TextField()
    offset_days = models.IntegerField(null=True, blank=True)
    escalation_level = models.CharField(max_length=50, blank=True)
    
    # Idempotency deduplication key: e.g. "reminder:12:30:IN_APP" or "escalation:12:rule_1:DIRECTOR"
    dedup_key = models.CharField(max_length=255, unique=True, db_index=True)

    is_read = models.BooleanField(default=False, db_index=True)
    sent_at = models.DateTimeField(default=timezone.now, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['recipient_role', 'is_read']),
            models.Index(fields=['instrument', 'notification_type']),
        ]

    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])

    def __str__(self):
        return f"[{self.channel}] {self.notification_type}: {self.title} -> {self.recipient_role or self.recipient}"


class EscalationRecord(models.Model):
    """
    Formal regulatory escalation log tracking cases escalated up the chain.
    """
    instrument = models.ForeignKey(
        'instruments.Instrument',
        on_delete=models.CASCADE,
        related_name='escalations'
    )
    rule = models.ForeignKey(
        EscalationRule,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='records'
    )
    trigger_condition = models.CharField(max_length=50)
    from_level = models.CharField(max_length=50)
    to_level = models.CharField(max_length=50)
    reason = models.TextField()
    dedup_key = models.CharField(max_length=255, unique=True, db_index=True)
    triggered_at = models.DateTimeField(default=timezone.now, db_index=True)
    is_resolved = models.BooleanField(default=False, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_note = models.TextField(blank=True)

    class Meta:
        ordering = ['-triggered_at']

    def __str__(self):
        return f"Escalation on {self.instrument.reference_number}: {self.from_level} -> {self.to_level}"
