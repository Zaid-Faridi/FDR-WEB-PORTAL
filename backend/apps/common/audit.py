import logging
from typing import Any, Dict, Optional
from django.db import transaction
from django.contrib.auth import get_user_model
from .models import AuditLog, AuditEntry, GENESIS_HASH, compute_audit_hash

logger = logging.getLogger('aicte.audit')


def record_audit_event(
    *,
    action: str,
    entity_type: str = 'System',
    entity_id: str = '0',
    actor_username: str = 'system',
    actor_role: str = '',
    actor=None,
    previous_state: Optional[Dict[str, Any]] = None,
    new_state: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    object_repr: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    """
    Standard function to record state transitions and audit-worthy actions.
    Writes both the legacy AuditLog and the cryptographic, append-only AuditEntry hash chain.
    """
    User = get_user_model()
    actor_user = actor
    if not actor_user and actor_username and actor_username != 'system':
        actor_user = User.objects.filter(username=actor_username).first()

    effective_role = actor_role
    if not effective_role and actor_user and hasattr(actor_user, 'role'):
        effective_role = actor_user.role

    # 1. Legacy AuditLog
    log_entry = AuditLog.objects.create(
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        actor_username=actor_username or 'system',
        actor_role=effective_role,
        previous_state=previous_state or {},
        new_state=new_state or {},
        ip_address=ip_address,
        metadata=metadata or {},
    )

    # 2. Phase 7 Cryptographic Append-Only AuditEntry
    audit_entry = None
    try:
        audit_entry = AuditEntry.objects.create(
            actor=actor_user,
            actor_username=actor_username or (actor_user.username if actor_user else 'system'),
            role=effective_role,
            action=action,
            object_type=entity_type,
            object_id=str(entity_id),
            object_repr=object_repr or f"{entity_type} #{entity_id}",
            before_values=previous_state or {},
            after_values=new_state or {},
            ip_address=ip_address,
            user_agent=user_agent or '',
        )
        log_entry.audit_entry = audit_entry
        log_entry.entry_hash = audit_entry.entry_hash
        log_entry.previous_hash = audit_entry.previous_hash
    except Exception as exc:
        logger.error("Failed to append to cryptographic AuditEntry chain: %s", exc, exc_info=True)

    logger.info(
        "AUDIT: %s by %s on %s:%s",
        action,
        actor_username,
        entity_type,
        entity_id,
    )
    return log_entry


def verify_audit_hash_chain() -> Dict[str, Any]:
    """
    Cryptographically verifies the entire AuditEntry hash chain sequentially.
    Reports the first broken entry, or confirms complete chain integrity.
    """
    entries = AuditEntry.objects.order_by('id')
    total = entries.count()
    if total == 0:
        return {
            "valid": True,
            "total_verified": 0,
            "latest_hash": GENESIS_HASH,
            "first_broken_id": None,
            "message": "Audit chain is empty. Genesis state intact."
        }

    expected_previous = GENESIS_HASH
    for idx, entry in enumerate(entries, start=1):
        # 1. Verify previous_hash linkage
        if entry.previous_hash != expected_previous:
            return {
                "valid": False,
                "total_verified": idx - 1,
                "first_broken_id": entry.id,
                "reason": f"Linkage broken at entry #{entry.id}: previous_hash '{entry.previous_hash}' does not match expected '{expected_previous}'."
            }

        # 2. Recompute entry_hash over all fields
        ts_str = entry.timestamp.isoformat()
        computed = compute_audit_hash(
            previous_hash=entry.previous_hash,
            timestamp_iso=ts_str,
            actor_id=str(entry.actor_id or ''),
            role=entry.role or '',
            action=entry.action,
            object_type=entry.object_type,
            object_id=str(entry.object_id),
            before_values=entry.before_values,
            after_values=entry.after_values,
            ip_address=entry.ip_address or '',
        )
        if entry.entry_hash != computed:
            return {
                "valid": False,
                "total_verified": idx - 1,
                "first_broken_id": entry.id,
                "reason": f"Tampering detected at entry #{entry.id}: stored hash '{entry.entry_hash}' != recomputed hash '{computed}'."
            }

        expected_previous = entry.entry_hash

    return {
        "valid": True,
        "total_verified": total,
        "latest_hash": expected_previous,
        "first_broken_id": None,
        "message": f"Audit hash chain is cryptographically intact across all {total} entries."
    }

