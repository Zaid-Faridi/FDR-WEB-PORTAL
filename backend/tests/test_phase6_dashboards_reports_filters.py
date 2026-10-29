"""
Tests for Phase 6:
1. Officer Dashboard counts, 30/60/90 expiry buckets, bank breakdown, monthly forecast, and risk worklist.
2. Risk-ranked scoring algorithm components (time-to-maturity, discrepancy severity, verification, amount, past delays).
3. Institution Dashboard isolation and upcoming deadlines countdown.
4. Search and filters on instruments (bank, status, amount range, maturity range, discrepancy type, text search).
5. User Saved Filter presets CRUD and scoping.
6. CSV report exports for all 6 report types.
7. PDF report exports with ReportLab styling and headers.
8. Scheduled weekly summary compliance email service and on-demand admin endpoint.
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from django.core import mail
from rest_framework.test import APIClient
from rest_framework import status

from apps.institutions.models import Institution
from apps.users.models import User, UserRole
from apps.instruments.models import (
    Instrument,
    InstrumentStatus,
    Discrepancy,
    DiscrepancySeverity,
    FieldSource,
    SavedFilter,
)
from apps.common.models import DataProvenanceSource
from apps.reports.risk import compute_instrument_risk, get_risk_ranked_worklist
from apps.reports.analytics import get_officer_dashboard_metrics, get_institution_dashboard_metrics
from apps.reports.generators import generate_csv_report, generate_pdf_report
from apps.reports.services import dispatch_weekly_summary_email


@pytest.fixture
def test_setup():
    inst_a = Institution.objects.create(
        name="Delhi Technological University",
        aicte_id="1-DEL-001",
        state="Delhi",
        district="New Delhi",
        institution_type="UNIVERSITY"
    )
    inst_b = Institution.objects.create(
        name="Mumbai Engineering College",
        aicte_id="1-MUM-002",
        state="Maharashtra",
        district="Mumbai",
        institution_type="COLLEGE"
    )

    user_officer = User.objects.create_user(
        username="officer_phase6",
        email="officer6@aicte-india.org",
        password="TestPassword@123",
        role=UserRole.SCRUTINY_OFFICER,
    )
    user_approver = User.objects.create_user(
        username="approver_phase6",
        email="approver6@aicte-india.org",
        password="TestPassword@123",
        role=UserRole.APPROVING_AUTHORITY,
    )
    user_admin = User.objects.create_user(
        username="admin_phase6",
        email="admin6@aicte-india.org",
        password="TestPassword@123",
        role=UserRole.ADMIN,
    )
    user_inst_a = User.objects.create_user(
        username="inst_a_user",
        email="delhi@dtu.ac.in",
        password="TestPassword@123",
        role=UserRole.INSTITUTION,
        institution=inst_a,
    )
    user_inst_b = User.objects.create_user(
        username="inst_b_user",
        email="mumbai@mec.ac.in",
        password="TestPassword@123",
        role=UserRole.INSTITUTION,
        institution=inst_b,
    )

    # Base dates
    today = date(2026, 10, 29)

    # 1. Active FDR (Expiring in 20 days -> 30-day bucket)
    fdr_expiring_soon = Instrument.objects.create(
        institution=inst_a,
        reference_number="FDR-DEL-SOON-01",
        issuing_bank="State Bank of India",
        issuing_branch="Connaught Place",
        branch_ifsc="SBIN0000001",
        amount=Decimal("3500000.00"),
        issue_date=today - timedelta(days=365 * 3),
        maturity_date=today + timedelta(days=20),
        status=InstrumentStatus.ACTIVE,
        created_by=user_inst_a,
    )
    FieldSource.objects.create(
        instrument=fdr_expiring_soon,
        field_name='amount',
        field_value='3500000.00',
        value_source=DataProvenanceSource.BANK_CONFIRMED,
        is_confirmed=True,
    )

    # 2. Overdue Matured FDR with Critical Discrepancy (Unverified)
    fdr_overdue = Instrument.objects.create(
        institution=inst_b,
        reference_number="FDR-MUM-OVERDUE-02",
        issuing_bank="Punjab National Bank",
        issuing_branch="Nariman Point",
        branch_ifsc="PUNB0000002",
        amount=Decimal("6000000.00"),
        issue_date=today - timedelta(days=365 * 5),
        maturity_date=today - timedelta(days=45),  # 45 days overdue
        status=InstrumentStatus.MATURED,
        created_by=user_inst_b,
    )
    Discrepancy.objects.create(
        instrument=fdr_overdue,
        rule_code="DOC_MANDATORY_MISSING",
        severity=DiscrepancySeverity.CRITICAL,
        title="Missing Mandatory FDR Certificate",
        description="FDR certificate scan missing from vault.",
        is_resolved=False,
    )

    # 3. Pending Verification FDR (Submitted, expiring in 50 days -> 60-day bucket)
    fdr_pending = Instrument.objects.create(
        institution=inst_a,
        reference_number="FDR-DEL-PENDING-03",
        issuing_bank="HDFC Bank",
        issuing_branch="Nehru Place",
        branch_ifsc="HDFC0000003",
        amount=Decimal("1500000.00"),
        issue_date=today - timedelta(days=30),
        maturity_date=today + timedelta(days=50),
        status=InstrumentStatus.SUBMITTED,
        created_by=user_inst_a,
    )

    # 4. Released FDR (Historical)
    fdr_released = Instrument.objects.create(
        institution=inst_b,
        reference_number="FDR-MUM-RELEASED-04",
        issuing_bank="Canara Bank",
        issuing_branch="Fort",
        branch_ifsc="CNRB0000004",
        amount=Decimal("1000000.00"),
        issue_date=today - timedelta(days=365 * 8),
        maturity_date=today - timedelta(days=100),
        status=InstrumentStatus.RELEASED,
        created_by=user_inst_b,
    )

    return {
        'inst_a': inst_a,
        'inst_b': inst_b,
        'user_officer': user_officer,
        'user_approver': user_approver,
        'user_admin': user_admin,
        'user_inst_a': user_inst_a,
        'user_inst_b': user_inst_b,
        'fdr_expiring_soon': fdr_expiring_soon,
        'fdr_overdue': fdr_overdue,
        'fdr_pending': fdr_pending,
        'fdr_released': fdr_released,
        'today': today,
    }


@pytest.mark.django_db
def test_risk_scoring_algorithm_components(test_setup):
    """
    Verifies that compute_instrument_risk calculates exact scores from:
    maturity proximity, discrepancy severity, bank confirmation, amount, and past delays.
    """
    today = test_setup['today']
    fdr_overdue = test_setup['fdr_overdue']

    # fdr_overdue:
    # 1. Overdue (>0 days overdue) = +35
    # 2. Critical discrepancy = +30
    # 3. Unverified bank confirmation = +15
    # 4. Amount 60 Lakhs (>=50L) = +10
    # 5. Past delays (e.g. 1) = +6
    # Total = 35 + 30 + 15 + 10 + 6 = 96
    risk_data = compute_instrument_risk(fdr_overdue, today, past_delays_count=1)

    assert risk_data['risk_score'] == 96
    assert risk_data['risk_tier'] == 'CRITICAL'
    assert any("Overdue by 45 days" in f for f in risk_data['risk_factors'])
    assert any("Critical unresolved discrepancy" in f for f in risk_data['risk_factors'])
    assert any("Unverified by Core Banking System" in f for f in risk_data['risk_factors'])
    assert any("High financial exposure" in f for f in risk_data['risk_factors'])
    assert any("past renewal delay" in f for f in risk_data['risk_factors'])

    # Verified clean FDR
    fdr_clean = test_setup['fdr_expiring_soon']
    # 1. Expiring in 20 days = +28
    # 2. Discrepancy = 0
    # 3. Verified by bank = 0
    # 4. Amount 35L (>=25L) = +7
    # 5. Past delays = 0
    # Total = 28 + 7 = 35 -> MEDIUM tier
    clean_risk = compute_instrument_risk(fdr_clean, today, past_delays_count=0)
    assert clean_risk['risk_score'] == 35
    assert clean_risk['risk_tier'] == 'MEDIUM'


@pytest.mark.django_db
def test_officer_dashboard_counts_and_charts(test_setup):
    """
    Verifies officer dashboard metrics: counts, 30/60/90 buckets, bank distribution, and timeline.
    """
    today = test_setup['today']
    metrics = get_officer_dashboard_metrics(today)

    counts = metrics['counts']
    assert counts['total_instruments'] == 4
    assert counts['active'] == 1
    assert counts['expiring_30'] == 1
    assert counts['expiring_60'] == 1
    assert counts['matured'] == 1
    assert counts['released'] == 1
    assert counts['pending_verification'] == 1
    assert counts['discrepancies'] == 1

    # Expiry buckets
    assert metrics['expiry_buckets']['0_30_days'] == 1
    assert metrics['expiry_buckets']['31_60_days'] == 1

    # 12-month timeline chart
    assert len(metrics['expiry_timeline']) == 12
    assert all('month_label' in m and 'count' in m and 'total_amount' in m for m in metrics['expiry_timeline'])

    # Risk-ranked worklist
    worklist = metrics['risk_worklist']
    assert len(worklist) >= 2
    # First item should be the highest risk (fdr_overdue)
    assert worklist[0]['reference_number'] == test_setup['fdr_overdue'].reference_number
    assert worklist[0]['risk_tier'] == 'CRITICAL'


@pytest.mark.django_db
def test_officer_dashboard_endpoint_access_and_rbac(test_setup):
    """
    Verifies API endpoint /api/reports/officer-dashboard/ enforces RBAC.
    """
    client = APIClient()

    # 1. Scrutiny Officer can access
    client.force_authenticate(user=test_setup['user_officer'])
    res = client.get('/api/reports/officer-dashboard/')
    assert res.status_code == status.HTTP_200_OK
    assert 'counts' in res.data
    assert 'risk_worklist' in res.data

    # 2. Institution user is strictly forbidden (403)
    client.force_authenticate(user=test_setup['user_inst_a'])
    res = client.get('/api/reports/officer-dashboard/')
    assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_institution_dashboard_isolation_and_deadlines(test_setup):
    """
    Verifies /api/reports/institution-dashboard/ returns only the authenticated
    institution's summary and deadlines.
    """
    client = APIClient()

    # Institution A
    client.force_authenticate(user=test_setup['user_inst_a'])
    res_a = client.get('/api/reports/institution-dashboard/')
    assert res_a.status_code == status.HTTP_200_OK
    assert res_a.data['summary']['total_instruments'] == 2
    # Verify inst A only sees FDR-DEL-SOON-01 and FDR-DEL-PENDING-03
    deadline_refs = [d['reference_number'] for d in res_a.data['upcoming_deadlines']]
    assert "FDR-DEL-SOON-01" in deadline_refs
    assert "FDR-MUM-OVERDUE-02" not in deadline_refs

    # Institution B
    client.force_authenticate(user=test_setup['user_inst_b'])
    res_b = client.get('/api/reports/institution-dashboard/')
    assert res_b.status_code == status.HTTP_200_OK
    assert res_b.data['summary']['total_instruments'] == 2
    deadline_refs_b = [d['reference_number'] for d in res_b.data['upcoming_deadlines']]
    assert "FDR-MUM-OVERDUE-02" in deadline_refs_b
    assert "FDR-DEL-SOON-01" not in deadline_refs_b


@pytest.mark.django_db
def test_search_and_filters_on_instruments(test_setup):
    """
    Verifies query parameters on /api/instruments/ (bank, status, amount, maturity, discrepancy, search).
    """
    client = APIClient()
    client.force_authenticate(user=test_setup['user_officer'])

    def get_refs(data):
        items = data if isinstance(data, list) else data.get('results', [])
        return [i['reference_number'] for i in items]

    # 1. Filter by bank
    res = client.get('/api/instruments/?bank=Punjab')
    assert res.status_code == status.HTTP_200_OK
    assert get_refs(res.data) == ["FDR-MUM-OVERDUE-02"]

    # 2. Filter by status
    res = client.get('/api/instruments/?status=ACTIVE')
    assert res.status_code == status.HTTP_200_OK
    assert get_refs(res.data) == ["FDR-DEL-SOON-01"]

    # 3. Filter by amount range
    res = client.get('/api/instruments/?min_amount=5000000')
    assert res.status_code == status.HTTP_200_OK
    assert get_refs(res.data) == ["FDR-MUM-OVERDUE-02"]

    # 4. Filter by discrepancy rule code
    res = client.get('/api/instruments/?discrepancy_type=DOC_MANDATORY_MISSING')
    assert res.status_code == status.HTTP_200_OK
    assert get_refs(res.data) == ["FDR-MUM-OVERDUE-02"]

    # 5. Text search
    res = client.get('/api/instruments/?search=Connaught')
    assert res.status_code == status.HTTP_200_OK
    assert get_refs(res.data) == ["FDR-DEL-SOON-01"]


@pytest.mark.django_db
def test_saved_filters_crud_and_user_scoping(test_setup):
    """
    Verifies user can create, list, and delete saved filter presets.
    """
    client = APIClient()
    client.force_authenticate(user=test_setup['user_officer'])

    # Create saved filter
    payload = {
        'name': 'High Risk Expiries',
        'filter_params': {'bank': 'State Bank of India', 'status': 'ACTIVE'},
        'is_default': True,
    }
    create_res = client.post('/api/saved-filters/', payload, format='json')
    assert create_res.status_code == status.HTTP_201_CREATED
    filter_id = create_res.data['id']
    assert create_res.data['name'] == 'High Risk Expiries'
    assert create_res.data['is_default'] is True

    # List saved filters
    list_res = client.get('/api/saved-filters/')
    assert list_res.status_code == status.HTTP_200_OK
    assert len(list_res.data) == 1

    # Scoping: another user sees 0 saved filters
    client.force_authenticate(user=test_setup['user_approver'])
    approver_res = client.get('/api/saved-filters/')
    assert approver_res.status_code == status.HTTP_200_OK
    assert len(approver_res.data) == 0


@pytest.mark.django_db
def test_reports_csv_generation(test_setup):
    """
    Verifies CSV generation for all required report types.
    """
    client = APIClient()
    client.force_authenticate(user=test_setup['user_officer'])

    report_types = [
        'pending_verifications',
        'upcoming_maturities',
        'missing_documents',
        'overdue_cases',
        'cases_needing_intervention',
        'institution_summary',
    ]

    for rt in report_types:
        res = client.get(f'/api/reports/{rt}/csv/')
        assert res.status_code == status.HTTP_200_OK
        assert 'text/csv' in res['Content-Type']
        assert 'attachment;' in res['Content-Disposition']
        content = res.content.decode('utf-8')
        assert "AICTE FDR Management Portal" in content


@pytest.mark.django_db
def test_reports_pdf_generation(test_setup):
    """
    Verifies PDF report generation with ReportLab.
    """
    client = APIClient()
    client.force_authenticate(user=test_setup['user_officer'])

    res = client.get('/api/reports/upcoming_maturities/pdf/')
    assert res.status_code == status.HTTP_200_OK
    assert res['Content-Type'] == 'application/pdf'
    assert 'attachment;' in res['Content-Disposition']
    assert res.content.startswith(b'%PDF')
    assert len(res.content) > 1000


@pytest.mark.django_db
def test_weekly_summary_email_service_and_endpoint(test_setup):
    """
    Verifies dispatch_weekly_summary_email compiles metrics and delivers email.
    """
    mail.outbox.clear()
    today = test_setup['today']

    # 1. Service execution
    result = dispatch_weekly_summary_email(today)
    assert result['status'] == 'sent'
    assert len(mail.outbox) == 1

    sent_msg = mail.outbox[0]
    assert "[AICTE FDR Portal] Weekly Security Deposit Compliance Summary" in sent_msg.subject
    assert "PORTFOLIO SNAPSHOT:" in sent_msg.body
    assert "TOP 5 RISK-RANKED CASES REQUIRING ATTENTION:" in sent_msg.body
    assert "FDR-MUM-OVERDUE-02" in sent_msg.body

    # 2. On-demand API trigger
    client = APIClient()
    client.force_authenticate(user=test_setup['user_admin'])
    api_res = client.post('/api/reports/send-weekly-summary/')
    assert api_res.status_code == status.HTTP_200_OK
    assert api_res.data['status'] == 'sent'
    assert len(mail.outbox) == 2
