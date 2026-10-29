import logging
from datetime import timedelta, date
from typing import Dict, Any, Optional, List
from django.utils import timezone
from django.db import transaction

from apps.common.dates import get_effective_date
from apps.common.audit import record_audit_event
from apps.instruments.models import Instrument, InstrumentStatus, Remark, Discrepancy
from apps.notifications.models import (
    ReminderRule,
    EscalationRule,
    EscalationCondition,
    NotificationChannel,
    NotificationType,
    Notification,
    EscalationRecord,
)
from apps.notifications.sender import dispatch_notification

logger = logging.getLogger(__name__)


def seed_default_rules() -> None:
    """
    Seeds standard AICTE regulatory reminder offsets and escalation ladders
    if none currently exist in database.
    """
    if not ReminderRule.objects.exists():
        default_reminders = [
            ReminderRule(
                name="90-Day Early Renewal Notice",
                offset_days=90,
                channel=NotificationChannel.IN_APP,
                target_role='INSTITUTION',
                template_subject="AICTE 90-Day FDR Maturity Notice: {reference_number}",
                template_body="FDR #{reference_number} for {institution_name} will mature in {days_left} days on {maturity_date}. Please review required deposit thresholds and prepare renewal or release application."
            ),
            ReminderRule(
                name="60-Day Midterm Renewal Reminder",
                offset_days=60,
                channel=NotificationChannel.ALL,
                target_role='INSTITUTION',
                template_subject="URGENT: 60-Day Renewal Reminder for FDR #{reference_number}",
                template_body="Fixed Deposit Receipt #{reference_number} ({institution_name}) matures in {days_left} days. Action is required to avoid regulatory penalty or lien enforcement."
            ),
            ReminderRule(
                name="30-Day Critical Expiry Alert",
                offset_days=30,
                channel=NotificationChannel.ALL,
                target_role='INSTITUTION',
                template_subject="CRITICAL: 30-Day FDR Expiry Notice #{reference_number}",
                template_body="Final 30-day notice: Deposit #{reference_number} is scheduled to mature on {maturity_date}. Scrutiny Bureau has been notified."
            ),
            ReminderRule(
                name="7-Day Imminent Maturity Warning",
                offset_days=7,
                channel=NotificationChannel.ALL,
                target_role='INSTITUTION',
                template_subject="IMMINENT MATURITY: FDR #{reference_number} Matures in 7 Days",
                template_body="Security deposit #{reference_number} matures in {days_left} days. AICTE automated lien enforcement will initiate upon unaddressed maturity."
            ),
        ]
        ReminderRule.objects.bulk_create(default_reminders)
        logger.info("Seeded 4 standard ReminderRules.")

    if not EscalationRule.objects.exists():
        default_escalations = [
            EscalationRule(
                name="Unresolved Discrepancy SLA Tier 1 (7 Days)",
                trigger_condition=EscalationCondition.UNRESOLVED_DISCREPANCY,
                wait_period_days=7,
                from_level='INSTITUTION',
                to_level='SCRUTINY_OFFICER',
                channel=NotificationChannel.IN_APP,
                template_subject="Escalation: Unresolved Discrepancy on FDR #{reference_number} (7 Days)",
                template_body="Institution has not resolved flagged discrepancies within 7 days on instrument #{reference_number}. Case escalated to Scrutiny Officer."
            ),
            EscalationRule(
                name="Unresolved Discrepancy SLA Tier 2 (14 Days)",
                trigger_condition=EscalationCondition.UNRESOLVED_DISCREPANCY,
                wait_period_days=14,
                from_level='SCRUTINY_OFFICER',
                to_level='APPROVING_AUTHORITY',
                channel=NotificationChannel.ALL,
                template_subject="Senior Escalation: Discrepancy Stalled for 14 Days on FDR #{reference_number}",
                template_body="Discrepancy on FDR #{reference_number} ({institution_name}) remains unresolved for 14 days. Escalated to Approving Authority for enforcement review."
            ),
            EscalationRule(
                name="Matured FDR Overdue Tier 1 (15 Days)",
                trigger_condition=EscalationCondition.OVERDUE_MATURED,
                wait_period_days=15,
                from_level='INSTITUTION',
                to_level='SCRUTINY_OFFICER',
                channel=NotificationChannel.ALL,
                template_subject="OVERDUE ESCALATION: Matured FDR #{reference_number} Unaddressed (15 Days)",
                template_body="FDR #{reference_number} has passed maturity without renewal or release request for 15 days. Case escalated to Scrutiny Officer for show-cause notice."
            ),
            EscalationRule(
                name="Matured FDR Overdue Tier 2 (30 Days)",
                trigger_condition=EscalationCondition.OVERDUE_MATURED,
                wait_period_days=30,
                from_level='SCRUTINY_OFFICER',
                to_level='DIRECTOR',
                channel=NotificationChannel.ALL,
                template_subject="DIRECTOR ESCALATION: Serious Non-Compliance on FDR #{reference_number} (30 Days Overdue)",
                template_body="FDR #{reference_number} for {institution_name} is 30 days overdue past maturity. Escalated to Regulation Bureau Director for statutory encashment."
            ),
        ]
        EscalationRule.objects.bulk_create(default_escalations)
        logger.info("Seeded 4 standard EscalationRules.")


def run_monitoring_job(effective_date: Optional[date] = None, triggered_by: str = 'celery_beat') -> Dict[str, Any]:
    """
    Daily monitoring and lifecycle execution job.
    1. Recomputes derived statuses (Active, Expiring, Matured, Overdue).
    2. Dispatches reminders at configured offsets (90, 60, 30, 7 days) with strict deduplication.
    3. Escalates unresolved cases up the regulatory chain after wait periods.
    """
    if effective_date is None:
        effective_date = get_effective_date()

    seed_default_rules()

    transitions_active = 0
    transitions_expiring = 0
    transitions_matured = 0
    reminders_dispatched = 0
    escalations_triggered = 0
    overdue_flagged = 0

    instruments = Instrument.objects.select_related('institution').all()

    for inst in instruments:
        prev_status = inst.status

        # -------------------------------------------------------------
        # 1. Derived Status Transitions
        # -------------------------------------------------------------
        if inst.status in [InstrumentStatus.VERIFIED, InstrumentStatus.ACTIVE, InstrumentStatus.EXPIRING]:
            # Matured condition
            if effective_date >= inst.maturity_date:
                inst.status = InstrumentStatus.MATURED
                inst.save(update_fields=['status', 'updated_at'])
                transitions_matured += 1

                Remark.objects.create(
                    instrument=inst,
                    author=None,
                    role='SYSTEM',
                    remark_type='STATUS_CHANGE',
                    text=f"System Lifecycle Engine: FDR matured on {inst.maturity_date} (Effective Date: {effective_date}).",
                    is_internal=False
                )
                record_audit_event(
                    action='STATUS_CHANGED_MATURED',
                    entity_type='Instrument',
                    entity_id=str(inst.id),
                    actor_username=triggered_by,
                    actor_role='SYSTEM',
                    previous_state={'status': prev_status},
                    new_state={'status': inst.status, 'effective_date': effective_date.isoformat()},
                )
                dispatch_notification(
                    title=f"FDR Matured: {inst.reference_number}",
                    message=f"Instrument #{inst.reference_number} has reached maturity on {inst.maturity_date}. Please initiate replacement/renewal or refund request immediately.",
                    channel=NotificationChannel.IN_APP,
                    notification_type=NotificationType.STATUS_CHANGE,
                    instrument=inst,
                    recipient_role='INSTITUTION',
                    dedup_key=f"status_matured:{inst.id}:{effective_date.isoformat()}"
                )

            # Expiring condition (within 90 days before maturity)
            elif (inst.maturity_date - effective_date) <= timedelta(days=90):
                if inst.status != InstrumentStatus.EXPIRING:
                    inst.status = InstrumentStatus.EXPIRING
                    inst.save(update_fields=['status', 'updated_at'])
                    transitions_expiring += 1

                    Remark.objects.create(
                        instrument=inst,
                        author=None,
                        role='SYSTEM',
                        remark_type='STATUS_CHANGE',
                        text=f"System Lifecycle Engine: Status transitioned to Expiring (Maturity: {inst.maturity_date}).",
                        is_internal=False
                    )
                    record_audit_event(
                        action='STATUS_CHANGED_EXPIRING',
                        entity_type='Instrument',
                        entity_id=str(inst.id),
                        actor_username=triggered_by,
                        actor_role='SYSTEM',
                        previous_state={'status': prev_status},
                        new_state={'status': inst.status, 'effective_date': effective_date.isoformat()},
                    )

            # Active condition (Verified and > 90 days from maturity)
            elif inst.status == InstrumentStatus.VERIFIED:
                inst.status = InstrumentStatus.ACTIVE
                inst.save(update_fields=['status', 'updated_at'])
                transitions_active += 1

                record_audit_event(
                    action='STATUS_CHANGED_ACTIVE',
                    entity_type='Instrument',
                    entity_id=str(inst.id),
                    actor_username=triggered_by,
                    actor_role='SYSTEM',
                    previous_state={'status': prev_status},
                    new_state={'status': inst.status, 'effective_date': effective_date.isoformat()},
                )

        # -------------------------------------------------------------
        # 2. Configurable Reminder Rules Execution (Avoids duplicates)
        # -------------------------------------------------------------
        if inst.status in [InstrumentStatus.ACTIVE, InstrumentStatus.EXPIRING]:
            days_left = (inst.maturity_date - effective_date).days
            if days_left >= 0:
                active_rules = ReminderRule.objects.filter(is_active=True)
                for rule in active_rules:
                    if days_left <= rule.offset_days:
                        dedup_key = f"reminder:{inst.id}:offset_{rule.offset_days}"
                        
                        # Format templates
                        subject = rule.template_subject.format(
                            reference_number=inst.reference_number,
                            institution_name=inst.institution.name if inst.institution else '',
                            days_left=days_left,
                            maturity_date=inst.maturity_date.isoformat(),
                        )
                        body = rule.template_body.format(
                            reference_number=inst.reference_number,
                            institution_name=inst.institution.name if inst.institution else '',
                            days_left=days_left,
                            maturity_date=inst.maturity_date.isoformat(),
                        )

                        notifs = dispatch_notification(
                            title=subject,
                            message=body,
                            channel=rule.channel,
                            notification_type=NotificationType.REMINDER,
                            instrument=inst,
                            recipient_role=rule.target_role,
                            offset_days=rule.offset_days,
                            dedup_key=dedup_key,
                        )
                        if notifs:
                            reminders_dispatched += len(notifs)

        # -------------------------------------------------------------
        # 3. Overdue Detection for Matured FDRs
        # -------------------------------------------------------------
        if inst.status == InstrumentStatus.MATURED:
            days_past = (effective_date - inst.maturity_date).days
            if days_past > 0:
                overdue_flagged += 1
                dedup_key = f"overdue:{inst.id}:initial_alert"
                notifs = dispatch_notification(
                    title=f"OVERDUE NOTICE: FDR #{inst.reference_number} Expired {days_past} Days Ago",
                    message=f"Deposit #{inst.reference_number} ({inst.institution.name}) expired on {inst.maturity_date} and remains unaddressed. Please renew or release immediately.",
                    channel=NotificationChannel.ALL,
                    notification_type=NotificationType.OVERDUE,
                    instrument=inst,
                    recipient_role='INSTITUTION',
                    dedup_key=dedup_key,
                )
                if notifs:
                    reminders_dispatched += len(notifs)

        # -------------------------------------------------------------
        # 4. Configurable Escalation Engine
        # -------------------------------------------------------------
        escalation_rules = EscalationRule.objects.filter(is_active=True)
        for esc_rule in escalation_rules:
            should_escalate = False
            reason_text = ""

            if esc_rule.trigger_condition == EscalationCondition.OVERDUE_MATURED:
                if inst.status == InstrumentStatus.MATURED:
                    days_overdue = (effective_date - inst.maturity_date).days
                    if days_overdue >= esc_rule.wait_period_days:
                        should_escalate = True
                        reason_text = f"FDR #{inst.reference_number} is {days_overdue} days past maturity without renewal/release action (Threshold: {esc_rule.wait_period_days} days)."

            elif esc_rule.trigger_condition == EscalationCondition.UNRESOLVED_DISCREPANCY:
                unresolved_discs = inst.discrepancies.filter(is_resolved=False)
                for disc in unresolved_discs:
                    disc_age = (effective_date - disc.created_at.date()).days
                    if disc_age >= esc_rule.wait_period_days:
                        should_escalate = True
                        reason_text = f"Discrepancy [{disc.rule_code}] on #{inst.reference_number} has remained unresolved for {disc_age} days (Threshold: {esc_rule.wait_period_days} days)."
                        break

            if should_escalate:
                esc_dedup_key = f"escalation:{inst.id}:{esc_rule.id}:{esc_rule.to_level}"
                if not EscalationRecord.objects.filter(dedup_key=esc_dedup_key).exists():
                    with transaction.atomic():
                        record = EscalationRecord.objects.create(
                            instrument=inst,
                            rule=esc_rule,
                            trigger_condition=esc_rule.trigger_condition,
                            from_level=esc_rule.from_level,
                            to_level=esc_rule.to_level,
                            reason=reason_text,
                            dedup_key=esc_dedup_key,
                            triggered_at=timezone.now(),
                        )
                        escalations_triggered += 1

                        # Render and dispatch escalation notifications
                        esc_title = esc_rule.template_subject.format(
                            reference_number=inst.reference_number,
                            institution_name=inst.institution.name if inst.institution else '',
                            to_level=esc_rule.to_level,
                            from_level=esc_rule.from_level,
                        )
                        esc_msg = esc_rule.template_body.format(
                            reference_number=inst.reference_number,
                            institution_name=inst.institution.name if inst.institution else '',
                            to_level=esc_rule.to_level,
                            from_level=esc_rule.from_level,
                            wait_days=esc_rule.wait_period_days,
                        )

                        dispatch_notification(
                            title=esc_title,
                            message=f"{esc_msg}\nFinding: {reason_text}",
                            channel=esc_rule.channel,
                            notification_type=NotificationType.ESCALATION,
                            instrument=inst,
                            recipient_role=esc_rule.to_level,
                            escalation_level=esc_rule.to_level,
                            dedup_key=f"notif:{esc_dedup_key}",
                        )

                        Remark.objects.create(
                            instrument=inst,
                            author=None,
                            role='SYSTEM',
                            remark_type='DISCREPANCY_FLAG',
                            text=f"Regulatory Escalation Triggered [{esc_rule.from_level} -> {esc_rule.to_level}]: {reason_text}",
                            is_internal=False
                        )

                        record_audit_event(
                            action='ESCALATION_TRIGGERED',
                            entity_type='Instrument',
                            entity_id=str(inst.id),
                            actor_username=triggered_by,
                            actor_role='SYSTEM',
                            previous_state={},
                            new_state={
                                'rule_id': esc_rule.id,
                                'from_level': esc_rule.from_level,
                                'to_level': esc_rule.to_level,
                                'reason': reason_text,
                            },
                        )

    return {
        "status": "SUCCESS",
        "effective_date": effective_date.isoformat(),
        "instruments_evaluated": instruments.count(),
        "status_transitions": {
            "to_active": transitions_active,
            "to_expiring": transitions_expiring,
            "to_matured": transitions_matured,
        },
        "reminders_dispatched": reminders_dispatched,
        "escalations_triggered": escalations_triggered,
        "overdue_flagged": overdue_flagged,
    }
