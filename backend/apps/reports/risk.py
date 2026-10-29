"""
Risk Scoring Engine for AICTE FDR Monitoring.
Ranks worklist items based on:
1. Time to maturity (approaching maturity or overdue)
2. Discrepancy severity (CRITICAL, HIGH, etc.)
3. Unverified bank confirmation status
4. Deposit amount (financial exposure)
5. Institution's historical renewal delays
"""
from datetime import date
from decimal import Decimal
from apps.instruments.models import Instrument, InstrumentStatus, DiscrepancySeverity


def compute_institution_past_delays_map(effective_date: date) -> dict[int, int]:
    """
    Computes a map of {institution_id: past_delay_count}.
    A past delay is defined as an instrument belonging to the institution that reached
    maturity date past effective_date by >30 days without being timely renewed or replaced,
    or that has an overdue notification/history.
    """
    delay_map = {}
    matured_unrenewed = Instrument.objects.filter(
        maturity_date__lt=effective_date,
        status__in=[InstrumentStatus.MATURED, InstrumentStatus.DISCREPANCY, InstrumentStatus.UNDER_SCRUTINY]
    ).values('institution_id')

    for item in matured_unrenewed:
        inst_id = item['institution_id']
        delay_map[inst_id] = delay_map.get(inst_id, 0) + 1

    return delay_map


def compute_instrument_risk(
    instrument: Instrument,
    effective_date: date,
    past_delays_count: int = 0
) -> dict:
    """
    Calculates composite risk score (0-100), risk tier, and human-readable risk factors.
    """
    risk_score = 0
    risk_factors = []

    # 1. Time to Maturity (Max 35 points)
    days_to_maturity = None
    if instrument.maturity_date:
        days_to_maturity = (instrument.maturity_date - effective_date).days
        if days_to_maturity < 0 and instrument.status not in [InstrumentStatus.RELEASED, InstrumentStatus.REPLACED, InstrumentStatus.RENEWED]:
            risk_score += 35
            risk_factors.append(f"Overdue by {abs(days_to_maturity)} days without resolution (+35)")
        elif days_to_maturity <= 30:
            risk_score += 28
            risk_factors.append(f"Expiring imminently in {days_to_maturity} days (+28)")
        elif days_to_maturity <= 60:
            risk_score += 20
            risk_factors.append(f"Expiring in {days_to_maturity} days (+20)")
        elif days_to_maturity <= 90:
            risk_score += 12
            risk_factors.append(f"Expiring in {days_to_maturity} days (+12)")

    # 2. Discrepancy Severity (Max 30 points)
    open_discrepancies = list(instrument.discrepancies.filter(is_resolved=False))
    has_critical = any(d.severity == DiscrepancySeverity.CRITICAL for d in open_discrepancies)
    has_high = any(d.severity == DiscrepancySeverity.HIGH for d in open_discrepancies)
    has_medium = any(d.severity == DiscrepancySeverity.MEDIUM for d in open_discrepancies)
    has_low = any(d.severity == DiscrepancySeverity.LOW for d in open_discrepancies)

    if has_critical:
        risk_score += 30
        risk_factors.append("Critical unresolved discrepancy flag present (+30)")
    elif has_high:
        risk_score += 20
        risk_factors.append("High severity discrepancy flag present (+20)")
    elif has_medium:
        risk_score += 10
        risk_factors.append("Medium severity discrepancy flag present (+10)")
    elif has_low:
        risk_score += 5
        risk_factors.append("Low severity discrepancy flag present (+5)")

    # 3. Unverified Bank Status (Max 15 points)
    is_unverified = (
        instrument.status in [InstrumentStatus.SUBMITTED, InstrumentStatus.UNDER_SCRUTINY] or
        not instrument.field_sources.filter(value_source='BANK_CONFIRMED', is_confirmed=True).exists()
    )
    if is_unverified and instrument.status not in [InstrumentStatus.RELEASED, InstrumentStatus.REPLACED]:
        risk_score += 15
        risk_factors.append("Unverified by Core Banking System (+15)")

    # 4. Deposit Amount Exposure (Max 10 points)
    amt = instrument.amount or Decimal('0')
    if amt >= Decimal('5000000'):  # 50 Lakhs+
        risk_score += 10
        risk_factors.append(f"High financial exposure ₹{amt:,.0f} (+10)")
    elif amt >= Decimal('2500000'):  # 25 Lakhs+
        risk_score += 7
        risk_factors.append(f"Significant financial exposure ₹{amt:,.0f} (+7)")
    elif amt >= Decimal('1000000'):  # 10 Lakhs+
        risk_score += 4
        risk_factors.append(f"Moderate financial exposure ₹{amt:,.0f} (+4)")
    else:
        risk_score += 2

    # 5. Institution Historical Renewal Delays (Max 10 points)
    if past_delays_count >= 3:
        risk_score += 10
        risk_factors.append(f"Institution has {past_delays_count} past renewal delays (+10)")
    elif past_delays_count >= 1:
        risk_score += 6
        risk_factors.append(f"Institution has {past_delays_count} past renewal delay(s) (+6)")

    # Bound risk score between 0 and 100
    risk_score = min(100, max(0, risk_score))

    if risk_score >= 70:
        risk_tier = "CRITICAL"
    elif risk_score >= 50:
        risk_tier = "HIGH"
    elif risk_score >= 25:
        risk_tier = "MEDIUM"
    else:
        risk_tier = "LOW"

    return {
        'risk_score': risk_score,
        'risk_tier': risk_tier,
        'risk_factors': risk_factors,
        'days_to_maturity': days_to_maturity,
    }


def get_risk_ranked_worklist(queryset, effective_date: date, limit: int = 50) -> list[dict]:
    """
    Ranks instruments from queryset by descending risk score.
    """
    past_delays_map = compute_institution_past_delays_map(effective_date)
    ranked_items = []

    for inst in queryset.select_related('institution').prefetch_related('discrepancies', 'field_sources'):
        past_delays = past_delays_map.get(inst.institution_id, 0)
        risk_data = compute_instrument_risk(inst, effective_date, past_delays)

        ranked_items.append({
            'id': inst.id,
            'reference_number': inst.reference_number,
            'institution_id': inst.institution_id,
            'institution_name': inst.institution.name if inst.institution else 'N/A',
            'institution_aicte_id': inst.institution.aicte_id if inst.institution else 'N/A',
            'issuing_bank': inst.issuing_bank,
            'amount': str(inst.amount),
            'status': inst.status,
            'issue_date': inst.issue_date.isoformat() if inst.issue_date else None,
            'maturity_date': inst.maturity_date.isoformat() if inst.maturity_date else None,
            'days_to_maturity': risk_data['days_to_maturity'],
            'risk_score': risk_data['risk_score'],
            'risk_tier': risk_data['risk_tier'],
            'risk_factors': risk_data['risk_factors'],
            'open_discrepancies_count': inst.discrepancies.filter(is_resolved=False).count(),
            'compliance_hold': inst.compliance_hold,
        })

    # Sort descending by risk_score, then by days_to_maturity ascending
    ranked_items.sort(key=lambda x: (-x['risk_score'], x['days_to_maturity'] if x['days_to_maturity'] is not None else 9999))
    return ranked_items[:limit]
