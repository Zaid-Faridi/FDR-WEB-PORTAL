"""
Analytics Service for Officer Dashboard and Institution Dashboard.
Provides:
- Officer metrics, status distributions, 30/60/90 expiry buckets, bank breakdown
- Monthly expiry timeline forecast
- Risk-ranked worklist
- Institution-specific summary and upcoming compliance deadlines
"""
from datetime import date, timedelta
from decimal import Decimal
from django.db.models import Sum, Count, Q
from apps.instruments.models import Instrument, InstrumentStatus
from .risk import get_risk_ranked_worklist


def get_officer_dashboard_metrics(effective_date: date) -> dict:
    """
    Computes comprehensive analytics and metrics for Scrutiny Officers and Bureau Admins.
    """
    total_qs = Instrument.objects.all()

    # Core Status Counts
    status_counts = dict(total_qs.values_list('status').annotate(c=Count('id')))

    active_count = status_counts.get(InstrumentStatus.ACTIVE, 0)
    matured_count = status_counts.get(InstrumentStatus.MATURED, 0)
    renewed_count = status_counts.get(InstrumentStatus.RENEWED, 0)
    released_count = status_counts.get(InstrumentStatus.RELEASED, 0)
    replaced_count = status_counts.get(InstrumentStatus.REPLACED, 0)
    discrepancy_status_count = status_counts.get(InstrumentStatus.DISCREPANCY, 0)
    submitted_count = status_counts.get(InstrumentStatus.SUBMITTED, 0)
    under_scrutiny_count = status_counts.get(InstrumentStatus.UNDER_SCRUTINY, 0)

    # Pending Verification: SUBMITTED or UNDER_SCRUTINY
    pending_verification_count = submitted_count + under_scrutiny_count

    # Total instruments with any open discrepancy
    open_discrepancies_count = total_qs.filter(discrepancies__is_resolved=False).distinct().count()

    # Expiring Buckets (from effective date):
    # 0 to 30 days
    date_30 = effective_date + timedelta(days=30)
    date_60 = effective_date + timedelta(days=60)
    date_90 = effective_date + timedelta(days=90)

    # Non-terminal statuses
    active_pool = total_qs.exclude(status__in=[
        InstrumentStatus.RELEASED,
        InstrumentStatus.REPLACED,
        InstrumentStatus.RENEWED,
    ])

    expiring_30 = active_pool.filter(
        maturity_date__gte=effective_date,
        maturity_date__lte=date_30
    ).count()

    expiring_60 = active_pool.filter(
        maturity_date__gt=date_30,
        maturity_date__lte=date_60
    ).count()

    expiring_90 = active_pool.filter(
        maturity_date__gt=date_60,
        maturity_date__lte=date_90
    ).count()

    expiring_total = expiring_30 + expiring_60 + expiring_90

    # Total Deposit Exposure in INR
    total_amount_val = total_qs.exclude(status__in=[
        InstrumentStatus.RELEASED,
        InstrumentStatus.REPLACED
    ]).aggregate(total=Sum('amount'))['total'] or Decimal('0')

    # Total active amount
    active_amount_val = total_qs.filter(status=InstrumentStatus.ACTIVE).aggregate(total=Sum('amount'))['total'] or Decimal('0')

    # Bank-wise distribution (Top 8 banks)
    bank_dist = list(
        total_qs.values('issuing_bank')
        .annotate(
            count=Count('id'),
            total_amount=Sum('amount')
        )
        .order_by('-total_amount')[:8]
    )

    # Expiry Timeline Chart: monthly distribution over the next 12 months
    expiry_timeline = []
    curr_month = effective_date.replace(day=1)

    for i in range(12):
        # Calculate month start and next month start
        if curr_month.month == 12:
            next_month = curr_month.replace(year=curr_month.year + 1, month=1)
        else:
            next_month = curr_month.replace(month=curr_month.month + 1)

        month_qs = active_pool.filter(
            maturity_date__gte=curr_month,
            maturity_date__lt=next_month
        )
        m_count = month_qs.count()
        m_amount = month_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0')

        expiry_timeline.append({
            'month_label': curr_month.strftime('%b %Y'),
            'month_key': curr_month.strftime('%Y-%m'),
            'count': m_count,
            'total_amount': float(m_amount),
        })
        curr_month = next_month

    # Risk-ranked worklist
    worklist = get_risk_ranked_worklist(active_pool, effective_date, limit=25)

    return {
        'effective_date': effective_date.isoformat(),
        'counts': {
            'total_instruments': total_qs.count(),
            'active': active_count,
            'expiring_30': expiring_30,
            'expiring_60': expiring_60,
            'expiring_90': expiring_90,
            'expiring_total': expiring_total,
            'matured': matured_count,
            'renewed': renewed_count,
            'released': released_count,
            'replaced': replaced_count,
            'pending_verification': pending_verification_count,
            'discrepancies': open_discrepancies_count,
            'total_amount': float(total_amount_val),
            'active_amount': float(active_amount_val),
        },
        'expiry_buckets': {
            '0_30_days': expiring_30,
            '31_60_days': expiring_60,
            '61_90_days': expiring_90,
            'total_expiring': expiring_total,
        },
        'status_distribution': [
            {'status': st, 'label': st, 'count': status_counts.get(st, 0)}
            for st in [
                InstrumentStatus.ACTIVE,
                InstrumentStatus.EXPIRING,
                InstrumentStatus.MATURED,
                InstrumentStatus.VERIFIED,
                InstrumentStatus.UNDER_SCRUTINY,
                InstrumentStatus.SUBMITTED,
                InstrumentStatus.DISCREPANCY,
                InstrumentStatus.RELEASE_REQUESTED,
                InstrumentStatus.RELEASED,
                InstrumentStatus.RENEWED,
                InstrumentStatus.REPLACED,
            ]
            if status_counts.get(st, 0) > 0
        ],
        'bank_distribution': [
            {
                'bank': b['issuing_bank'],
                'count': b['count'],
                'total_amount': float(b['total_amount'] or 0),
            }
            for b in bank_dist
        ],
        'expiry_timeline': expiry_timeline,
        'risk_worklist': worklist,
    }


def get_institution_dashboard_metrics(institution_id: int, effective_date: date) -> dict:
    """
    Computes strict institution-scoped summary and upcoming compliance deadlines.
    Ensures zero cross-institution data leakage.
    """
    inst_qs = Instrument.objects.filter(institution_id=institution_id)

    status_counts = dict(inst_qs.values_list('status').annotate(c=Count('id')))

    total_amount = inst_qs.exclude(status__in=[
        InstrumentStatus.RELEASED,
        InstrumentStatus.REPLACED
    ]).aggregate(total=Sum('amount'))['total'] or Decimal('0')

    # Upcoming Deadlines within 90 days or overdue
    deadline_pool = inst_qs.exclude(status__in=[
        InstrumentStatus.RELEASED,
        InstrumentStatus.REPLACED,
        InstrumentStatus.RENEWED,
    ]).filter(maturity_date__lte=effective_date + timedelta(days=90)).order_by('maturity_date')

    upcoming_deadlines = []
    for item in deadline_pool.prefetch_related('discrepancies'):
        days_left = (item.maturity_date - effective_date).days if item.maturity_date else 0
        has_disc = item.discrepancies.filter(is_resolved=False).exists()

        if days_left < 0:
            urgency = 'OVERDUE'
            action = 'Immediate action required: Submit replacement FDR or request Council release.'
        elif days_left <= 30:
            urgency = 'CRITICAL'
            action = 'Submit renewal FDR instrument and lien letter before scheduled maturity.'
        elif days_left <= 60:
            urgency = 'HIGH'
            action = 'Initiate bank renewal process with branch manager.'
        else:
            urgency = 'MEDIUM'
            action = 'Plan for maturity rollover or Council release application.'

        if has_disc:
            action += ' Also rectify pending discrepancy flags on record.'

        upcoming_deadlines.append({
            'id': item.id,
            'reference_number': item.reference_number,
            'issuing_bank': item.issuing_bank,
            'amount': str(item.amount),
            'status': item.status,
            'issue_date': item.issue_date.isoformat() if item.issue_date else None,
            'maturity_date': item.maturity_date.isoformat() if item.maturity_date else None,
            'days_left': days_left,
            'urgency': urgency,
            'action_required': action,
            'has_discrepancies': has_disc,
        })

    return {
        'effective_date': effective_date.isoformat(),
        'institution_id': institution_id,
        'summary': {
            'total_instruments': inst_qs.count(),
            'total_amount': float(total_amount),
            'active_count': status_counts.get(InstrumentStatus.ACTIVE, 0),
            'expiring_count': status_counts.get(InstrumentStatus.EXPIRING, 0),
            'matured_count': status_counts.get(InstrumentStatus.MATURED, 0),
            'under_scrutiny_count': status_counts.get(InstrumentStatus.UNDER_SCRUTINY, 0) + status_counts.get(InstrumentStatus.SUBMITTED, 0),
            'discrepancy_count': inst_qs.filter(discrepancies__is_resolved=False).distinct().count(),
            'released_count': status_counts.get(InstrumentStatus.RELEASED, 0),
            'replaced_count': status_counts.get(InstrumentStatus.REPLACED, 0),
        },
        'upcoming_deadlines': upcoming_deadlines,
    }
