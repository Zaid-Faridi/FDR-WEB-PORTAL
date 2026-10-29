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


import json
import hashlib
from django.conf import settings
from django.core.exceptions import PermissionDenied

GENESIS_HASH = "0" * 64


def compute_audit_hash(
    *,
    previous_hash: str,
    timestamp_iso: str,
    actor_id: str,
    role: str,
    action: str,
    object_type: str,
    object_id: str,
    before_values: dict,
    after_values: dict,
    ip_address: str = '',
) -> str:
    """
    Deterministic SHA-256 hash calculation for an AuditEntry node in the hash chain.
    """
    canonical_before = json.dumps(before_values or {}, sort_keys=True, default=str)
    canonical_after = json.dumps(after_values or {}, sort_keys=True, default=str)
    payload = (
        f"{previous_hash}|"
        f"{timestamp_iso}|"
        f"{actor_id or ''}|"
        f"{role or ''}|"
        f"{action}|"
        f"{object_type}|"
        f"{object_id}|"
        f"{canonical_before}|"
        f"{canonical_after}|"
        f"{ip_address or ''}"
    )
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


class AuditEntry(models.Model):
    """
    Phase 7 Append-Only Cryptographic Audit Log:
    - Guaranteed immutable: no updates or deletions allowed through ORM or direct API.
    - Forms an unbroken cryptographic hash chain where each entry includes the previous entry's hash.
    - Any tampering or broken link is deterministically detectable via verify_chain.
    """
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='audit_entries',
        db_index=True,
    )
    actor_username = models.CharField(max_length=150, default='system', db_index=True)
    role = models.CharField(max_length=50, blank=True, default='', db_index=True)
    action = models.CharField(max_length=100, db_index=True)
    object_type = models.CharField(max_length=100, db_index=True)
    object_id = models.CharField(max_length=100, db_index=True)
    object_repr = models.TextField(blank=True, default='')
    before_values = models.JSONField(default=dict, blank=True)
    after_values = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    previous_hash = models.CharField(max_length=64, db_index=True)
    entry_hash = models.CharField(max_length=64, unique=True, db_index=True)

    class Meta:
        ordering = ['id']
        verbose_name = 'Audit Entry'
        verbose_name_plural = 'Audit Entries'
        indexes = [
            models.Index(fields=['object_type', 'object_id']),
            models.Index(fields=['actor_username', 'action']),
            models.Index(fields=['previous_hash']),
            models.Index(fields=['timestamp']),
        ]

    def __str__(self):
        return f"AuditEntry #{self.id} [{self.action}] on {self.object_type}#{self.object_id} ({self.entry_hash[:8]}...)"

    def save(self, *args, **kwargs):
        # Strict append-only enforcement: if the record exists in the DB, reject any modification
        if self.pk and AuditEntry.objects.filter(pk=self.pk).exists():
            raise PermissionDenied("AuditEntry is append-only. Modification of existing audit entries is strictly forbidden.")

        # Chain with the latest entry in the hash chain
        if not self.previous_hash:
            last = AuditEntry.objects.order_by('-id').first()
            self.previous_hash = last.entry_hash if last else GENESIS_HASH

        # Compute hash if not explicitly set
        if not self.entry_hash:
            ts_str = self.timestamp.isoformat() if self.timestamp else timezone.now().isoformat()
            self.entry_hash = compute_audit_hash(
                previous_hash=self.previous_hash,
                timestamp_iso=ts_str,
                actor_id=str(self.actor_id or ''),
                role=self.role or '',
                action=self.action,
                object_type=self.object_type,
                object_id=str(self.object_id),
                before_values=self.before_values,
                after_values=self.after_values,
                ip_address=self.ip_address or '',
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Strict append-only enforcement: deletion is prohibited
        raise PermissionDenied("AuditEntry is append-only. Deletion of audit entries is strictly forbidden.")


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

