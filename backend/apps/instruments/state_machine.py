import logging
from typing import Dict, List, Optional, Any
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied

from apps.instruments.models import Instrument, InstrumentStatus, Remark
from apps.common.audit import record_audit_event

logger = logging.getLogger('aicte.state_machine')


class InstrumentStateMachine:
    """
    Explicit Finite State Machine governing the complete lifecycle of
    Technical Institution Security Deposit and FDR instruments.
    Strictly validates allowed status transitions and enforcing role permissions server-side.
    """

    ALLOWED_TRANSITIONS: Dict[str, List[str]] = {
        InstrumentStatus.SUBMITTED: [
            InstrumentStatus.UNDER_SCRUTINY,
            InstrumentStatus.VERIFIED,
            InstrumentStatus.DISCREPANCY,
            InstrumentStatus.RELEASE_REQUESTED,
            InstrumentStatus.REJECTED,
        ],
        InstrumentStatus.UNDER_SCRUTINY: [
            InstrumentStatus.VERIFIED,
            InstrumentStatus.DISCREPANCY,
            InstrumentStatus.REJECTED,
            InstrumentStatus.RELEASED,   # When release scrutiny is approved
        ],
        InstrumentStatus.DISCREPANCY: [
            InstrumentStatus.UNDER_SCRUTINY,
            InstrumentStatus.VERIFIED,
            InstrumentStatus.RELEASE_REQUESTED,
            InstrumentStatus.REJECTED,
        ],
        InstrumentStatus.VERIFIED: [
            InstrumentStatus.ACTIVE,
            InstrumentStatus.EXPIRING,
            InstrumentStatus.MATURED,
            InstrumentStatus.RELEASE_REQUESTED,
            InstrumentStatus.RENEWED,
            InstrumentStatus.REPLACED,
        ],
        InstrumentStatus.ACTIVE: [
            InstrumentStatus.EXPIRING,
            InstrumentStatus.MATURED,
            InstrumentStatus.RELEASE_REQUESTED,
            InstrumentStatus.RENEWED,
            InstrumentStatus.REPLACED,
        ],
        InstrumentStatus.EXPIRING: [
            InstrumentStatus.MATURED,
            InstrumentStatus.RELEASE_REQUESTED,
            InstrumentStatus.RENEWED,
            InstrumentStatus.REPLACED,
        ],
        InstrumentStatus.MATURED: [
            InstrumentStatus.RELEASE_REQUESTED,
            InstrumentStatus.RENEWED,
            InstrumentStatus.REPLACED,
        ],
        InstrumentStatus.RELEASE_REQUESTED: [
            InstrumentStatus.UNDER_SCRUTINY,
            InstrumentStatus.RELEASED,
            InstrumentStatus.REJECTED,
        ],
        # Terminal States: no further transitions permitted
        InstrumentStatus.RENEWED: [],
        InstrumentStatus.REPLACED: [],
        InstrumentStatus.RELEASED: [],
        InstrumentStatus.REJECTED: [],
    }

    @classmethod
    def validate_transition(
        cls,
        current_status: str,
        target_status: str,
        user=None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Validates whether current_status -> target_status is permitted by the state machine
        and whether user role has authority for this specific transition.
        """
        if current_status == target_status:
            return

        allowed = cls.ALLOWED_TRANSITIONS.get(current_status, [])
        if target_status not in allowed:
            raise ValidationError(
                f"Invalid state transition: Cannot transition instrument from '{current_status}' to '{target_status}'. "
                f"Allowed target states from '{current_status}': {allowed if allowed else 'None (Terminal State)'}."
            )

        if user is None:
            # System tasks (e.g. Celery lifecycle job) allowed valid transitions
            return

        role = getattr(user, 'role', '')
        is_admin = (role == 'ADMIN' or user.is_superuser)

        # Role Rules:
        # 1. Approving Authority (or Admin) ONLY can transition to RELEASED
        if target_status == InstrumentStatus.RELEASED:
            if role != 'APPROVING_AUTHORITY' and not is_admin:
                raise PermissionDenied(
                    "Forbidden: Only the Approving Authority or Regulation Bureau Administrator can approve release and mark an instrument as Released."
                )

        # 2. Only Institution (or Admin) can trigger RELEASE_REQUESTED
        elif target_status == InstrumentStatus.RELEASE_REQUESTED:
            if role != 'INSTITUTION' and not is_admin:
                raise PermissionDenied(
                    "Forbidden: Only the owning Technical Institution can initiate a release or refund request."
                )

        # 3. Only Scrutiny Officer or Admin can transition to UNDER_SCRUTINY, VERIFIED, or DISCREPANCY
        elif target_status in [InstrumentStatus.UNDER_SCRUTINY, InstrumentStatus.VERIFIED, InstrumentStatus.DISCREPANCY]:
            if role not in ['SCRUTINY_OFFICER', 'ADMIN'] and not user.is_superuser:
                raise PermissionDenied(
                    f"Forbidden: Role '{role}' lacks authority to transition instrument to '{target_status}'."
                )

        # 4. Only Approving Authority or Admin can REJECT release requests
        elif target_status == InstrumentStatus.REJECTED:
            if role not in ['APPROVING_AUTHORITY', 'ADMIN'] and not user.is_superuser:
                raise PermissionDenied(
                    "Forbidden: Only Approving Authority or Administrator can reject an instrument or release request."
                )

    @classmethod
    def apply_transition(
        cls,
        instrument: Instrument,
        target_status: str,
        user=None,
        reason: str = '',
        metadata: Optional[Dict[str, Any]] = None
    ) -> Instrument:
        """
        Executes a validated state transition:
        - Checks allowed transition and RBAC
        - Updates instrument status
        - Writes an AuditLog event
        - Creates a status change Remark
        - Handles replacement chaining side-effects (if new instrument verified, old becomes Replaced)
        """
        prev_status = instrument.status
        cls.validate_transition(prev_status, target_status, user=user)

        instrument.status = target_status
        instrument.save(update_fields=['status', 'updated_at'])

        actor_name = user.username if user else 'SYSTEM'
        actor_role = getattr(user, 'role', 'SYSTEM') if user else 'SYSTEM'

        # Record audit log
        record_audit_event(
            action=f"STATUS_TRANSITION_{target_status.upper().replace(' ', '_')}",
            entity_type='Instrument',
            entity_id=str(instrument.id),
            actor_username=actor_name,
            actor_role=actor_role,
            previous_state={'status': prev_status},
            new_state={'status': target_status, 'reason': reason, **(metadata or {})},
        )

        # Append remark
        Remark.objects.create(
            instrument=instrument,
            author=user if getattr(user, 'pk', None) else None,
            role=actor_role,
            remark_type='STATUS_CHANGE',
            text=f"Status transitioned from '{prev_status}' to '{target_status}'. {reason}".strip(),
            is_internal=False
        )

        # -------------------------------------------------------------
        # Phase 5: Automatic Replacement Chaining Trigger
        # When a replacement instrument becomes VERIFIED,
        # the predecessor instrument automatically becomes REPLACED!
        # -------------------------------------------------------------
        if target_status == InstrumentStatus.VERIFIED and instrument.replaces:
            old_inst = instrument.replaces
            if old_inst.status in [
                InstrumentStatus.VERIFIED,
                InstrumentStatus.ACTIVE,
                InstrumentStatus.EXPIRING,
                InstrumentStatus.MATURED,
                InstrumentStatus.SUBMITTED,
                InstrumentStatus.UNDER_SCRUTINY,
            ]:
                cls.apply_transition(
                    instrument=old_inst,
                    target_status=InstrumentStatus.REPLACED,
                    user=user,
                    reason=f"Automatically replaced by verified new instrument #{instrument.reference_number}.",
                    metadata={'replacing_instrument_id': instrument.id, 'replacing_reference': instrument.reference_number}
                )

        return instrument
