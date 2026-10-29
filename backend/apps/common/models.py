from django.db import models
from django.utils import timezone

class DataProvenanceSource(models.TextChoices):
    """
    Core principle: Every data field records its source and the UI
    always distinguishes 'claimed' from 'bank-confirmed'.
    """
    INSTITUTION_SUBMITTED = 'INSTITUTION_SUBMITTED', 'Institution Submitted (Claimed)'
    OFFICER_ENTERED = 'OFFICER_ENTERED', 'Officer Entered'
    BANK_CONFIRMED = 'BANK_CONFIRMED', 'Bank Confirmed'


class AuditLog(models.Model):
    """
    Rule: Every state change writes an audit entry.
    Immutable log capturing actors, actions, previous and new states.
    """
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    actor_username = models.CharField(max_length=150, default='system', db_index=True)
    actor_role = models.CharField(max_length=50, blank=True, default='')
    action = models.CharField(max_length=100, db_index=True)
    entity_type = models.CharField(max_length=100, db_index=True)
    entity_id = models.CharField(max_length=100, db_index=True)
    previous_state = models.JSONField(default=dict, blank=True)
    new_state = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['entity_type', 'entity_id']),
            models.Index(fields=['actor_username', 'action']),
        ]

    def __str__(self):
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {self.actor_username} - {self.action} on {self.entity_type} #{self.entity_id}"


class SystemSetting(models.Model):
    """
    Global system settings, including demo-only simulated date.
    """
    key = models.CharField(max_length=100, unique=True, db_index=True)
    value = models.JSONField(default=dict)
    description = models.CharField(max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by_username = models.CharField(max_length=150, blank=True, default='system')

    class Meta:
        verbose_name = 'System Setting'
        verbose_name_plural = 'System Settings'

    def __str__(self):
        return f"{self.key} = {self.value}"

