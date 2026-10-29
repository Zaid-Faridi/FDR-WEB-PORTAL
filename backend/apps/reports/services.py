"""
Weekly Compliance Summary Email Service.
Collects executive portfolio metrics, formats an official summary digest,
and delivers emails to Scrutiny Officers, Approving Authority, and Bureau Admins.
"""
from datetime import date
from django.core.mail import send_mail
from django.conf import settings
from apps.users.models import User, UserRole
from apps.common.dates import get_effective_date
from apps.common.audit import record_audit_event
from .analytics import get_officer_dashboard_metrics


def dispatch_weekly_summary_email(effective_date: date = None) -> dict:
    """
    Constructs and dispatches the weekly security deposit compliance email summary.
    """
    if effective_date is None:
        effective_date = get_effective_date()

    data = get_officer_dashboard_metrics(effective_date)
    counts = data['counts']
    top_risks = data['risk_worklist'][:5]

    # Find recipient emails (Officers, Approving Authority, Admin)
    recipients = list(
        User.objects.filter(
            role__in=[UserRole.SCRUTINY_OFFICER, UserRole.APPROVING_AUTHORITY, UserRole.ADMIN],
            is_active=True
        ).exclude(email='').values_list('email', flat=True)
    )

    if not recipients:
        # Fallback to default admin email
        recipients = ['officers@aicte-india.org', 'regulation@aicte-india.org']

    subject = f"[AICTE FDR Portal] Weekly Security Deposit Compliance Summary — {effective_date.strftime('%d %b %Y')}"

    # Construct clean email body
    lines = [
        "ALL INDIA COUNCIL FOR TECHNICAL EDUCATION",
        "Bureau of Approval & Regulation",
        "=" * 60,
        f"WEEKLY SECURITY DEPOSIT COMPLIANCE REPORT — {effective_date.strftime('%d %B %Y')}",
        "=" * 60,
        "",
        "PORTFOLIO SNAPSHOT:",
        f"• Total Active Instruments:        {counts['active']} (₹{counts['active_amount']:,.2f})",
        f"• Total Maturing in 30 Days:       {counts['expiring_30']} instruments",
        f"• Total Maturing in 60 Days:       {counts['expiring_60']} instruments",
        f"• Total Maturing in 90 Days:       {counts['expiring_90']} instruments",
        f"• Total Matured / Overdue:         {counts['matured']} instruments",
        f"• Pending Officer Verification:    {counts['pending_verification']} instruments",
        f"• Open Discrepancy Flags:          {counts['discrepancies']} instruments",
        "",
        "=" * 60,
        "TOP 5 RISK-RANKED CASES REQUIRING ATTENTION:",
        "=" * 60,
    ]

    if top_risks:
        for idx, item in enumerate(top_risks, 1):
            reasons = "; ".join(item['risk_factors'][:2]) or 'High priority'
            lines.append(
                f"{idx}. [{item['risk_tier']}] {item['reference_number']} — {item['institution_name']}"
            )
            lines.append(f"   Bank: {item['issuing_bank']} | Amount: ₹{float(item['amount']):,.2f} | Maturity: {item['maturity_date']}")
            lines.append(f"   Risk Factors: {reasons}")
            lines.append("")
    else:
        lines.append("No critical risk cases currently outstanding.")
        lines.append("")

    lines.extend([
        "=" * 60,
        "PORTAL ACCESS:",
        "Log in to the AICTE Security Deposit Portal to review the full risk-ranked worklist",
        "and download CSV/PDF audit reports: https://fdr.aicte-india.org",
        "",
        "Confidential — Automated report dispatched by AICTE FDR Core.",
    ])

    body_text = "\n".join(lines)

    sent_count = send_mail(
        subject=subject,
        message=body_text,
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'alerts@aicte-india.org'),
        recipient_list=recipients,
        fail_silently=False,
    )

    # Log audit event
    record_audit_event(
        action='WEEKLY_SUMMARY_EMAIL_DISPATCHED',
        entity_type='Report',
        entity_id='weekly_summary',
        actor_username='system_celery',
        actor_role='SYSTEM',
        previous_state={},
        new_state={
            'recipient_count': len(recipients),
            'effective_date': effective_date.isoformat(),
            'counts': counts,
        }
    )

    return {
        'status': 'sent',
        'recipients': recipients,
        'emails_sent': sent_count,
        'effective_date': effective_date.isoformat(),
        'counts': counts,
    }
