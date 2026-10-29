import logging
from typing import Any, Dict, Optional
from django.db import transaction
from .models import AuditLog

logger = logging.getLogger('aicte.audit')

def record_audit_event(
    *,
    action: str,
    entity_type: str,
    entity_id: str,
    actor_username: str = 'system',
    actor_role: str = '',
    previous_state: Optional[Dict[str, Any]] = None,
    new_state: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    """
    Standard function to record state transitions and audit-worthy actions.
    Ensures that every state change writes an audit entry.
    """
    log_entry = AuditLog.objects.create(
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        actor_username=actor_username,
        actor_role=actor_role,
        previous_state=previous_state or {},
        new_state=new_state or {},
        ip_address=ip_address,
        metadata=metadata or {},
    )
    logger.info(
        "AUDIT: %s by %s on %s:%s",
        action,
        actor_username,
        entity_type,
        entity_id
    )
    return log_entry
