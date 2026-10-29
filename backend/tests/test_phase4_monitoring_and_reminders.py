import pytest
from datetime import date, timedelta
from decimal import Decimal
from django.utils import timezone
from django.core import mail
from rest_framework.test import APIClient
from rest_framework import status

from apps.institutions.models import Institution
from apps.instruments.models import (
    Instrument,
    InstrumentStatus,
    InstrumentType,
    Discrepancy,
    DiscrepancySeverity,
)
from apps.common.dates import (
    get_effective_date,
    set_simulated_date,
    is_simulation_allowed,
)
from apps.common.models import SystemSetting
from apps.notifications.models import (
    ReminderRule,
    EscalationRule,
    EscalationCondition,
    NotificationChannel,
    NotificationType,
    Notification,
    EscalationRecord,
)
from apps.notifications.services import run_monitoring_job, seed_default_rules
from apps.notifications.channels.sms import get_sms_adapter


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture(autouse=True)
def clean_simulation(db):
    """Ensure clean simulation state for every test."""
    SystemSetting.objects.filter(key='SIMULATED_SYSTEM_DATE').delete()
    yield
    SystemSetting.objects.filter(key='SIMULATED_SYSTEM_DATE').delete()


@pytest.fixture
def seed_test_data(db):
    seed_default_rules()
    
    # Institution 1
    inst1 = Institution.objects.create(
        name="Delhi Institute of Technology & Management",
        aicte_id="1-1000101",
        state="Delhi",
        district="Dwarka",
        address="Sector 12, Dwarka",
        institution_type="Engineering & Technology",
        contact_email="ditm@example.com",
        contact_phone="+91-9811122233"
    )

    # Users
    from apps.users.models import User
    inst_user = User.objects.create_user(
        username="user_ditm_p4",
        password="College@DITM2026",
        role="INSTITUTION",
        institution=inst1
    )
    officer_user = User.objects.create_user(
        username="officer_sharma_p4",
        password="Officer@AICTE2026",
        role="SCRUTINY_OFFICER"
    )
    admin_user = User.objects.create_user(
        username="aicte_admin_p4",
        password="Admin@AICTE2026",
        role="ADMIN",
        is_staff=True
    )

    return {
        'institution': inst1,
        'inst_user': inst_user,
        'officer_user': officer_user,
        'admin_user': admin_user,
    }


# =====================================================================
# 1. SIMULATED DATE TESTS
# =====================================================================

@pytest.mark.django_db
def test_simulated_date_admin_control(api_client, seed_test_data):
    admin = seed_test_data['admin_user']
    api_client.force_authenticate(user=admin)

    # Set simulated date to future date: 2028-06-15
    res = api_client.post('/api/admin/simulated-date/', {'simulated_date': '2028-06-15'}, format='json')
    assert res.status_code == status.HTTP_200_OK
    assert res.data['is_active'] is True
    assert res.data['effective_date'] == '2028-06-15'
    assert get_effective_date() == date(2028, 6, 15)

    # Clear simulated date
    res_clear = api_client.post('/api/admin/simulated-date/', {'simulated_date': None}, format='json')
    assert res_clear.status_code == status.HTTP_200_OK
    assert res_clear.data['is_active'] is False
    assert get_effective_date() == timezone.now().date()


@pytest.mark.django_db
def test_simulated_date_non_admin_blocked(api_client, seed_test_data):
    inst_user = seed_test_data['inst_user']
    api_client.force_authenticate(user=inst_user)

    res = api_client.post('/api/admin/simulated-date/', {'simulated_date': '2028-06-15'}, format='json')
    assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_simulated_date_production_guard(settings):
    # Guard 1: Environment is production
    settings.ENVIRONMENT = 'production'
    assert is_simulation_allowed() is False

    from rest_framework.exceptions import PermissionDenied
    with pytest.raises(PermissionDenied):
        set_simulated_date('2028-06-15')

    assert get_effective_date() == timezone.now().date()

    # Guard 2: ALLOW_SIMULATED_DATE flag disabled
    settings.ENVIRONMENT = 'development'
    settings.ALLOW_SIMULATED_DATE = False
    assert is_simulation_allowed() is False


# =====================================================================
# 2. STATUS RECOMPUTATION & TIME-TRAVEL TESTS
# =====================================================================

@pytest.mark.django_db
def test_derived_status_transitions_active_expiring_matured(seed_test_data):
    institution = seed_test_data['institution']

    # Create instrument with maturity on 2028-06-01
    fdr = Instrument.objects.create(
        institution=institution,
        instrument_type=InstrumentType.FDR,
        reference_number="FDR-TIME-TRAVEL-001",
        issuing_bank="State Bank of India",
        issuing_branch="Main Branch",
        branch_ifsc="SBIN0000001",
        amount=Decimal("5000000.00"),
        issue_date=date(2023, 6, 1),
        maturity_date=date(2028, 6, 1),
        lien_in_favour_of_aicte=True,
        status=InstrumentStatus.VERIFIED,
    )

    # Time-travel 1: 2027-01-01 (> 90 days before maturity)
    run_monitoring_job(effective_date=date(2027, 1, 1))
    fdr.refresh_from_db()
    assert fdr.status == InstrumentStatus.ACTIVE

    # Time-travel 2: 2028-04-01 (61 days before maturity <= 90 days)
    run_monitoring_job(effective_date=date(2028, 4, 1))
    fdr.refresh_from_db()
    assert fdr.status == InstrumentStatus.EXPIRING

    # Time-travel 3: 2028-06-01 (Maturity date)
    run_monitoring_job(effective_date=date(2028, 6, 1))
    fdr.refresh_from_db()
    assert fdr.status == InstrumentStatus.MATURED


# =====================================================================
# 3. CONFIGURABLE REMINDERS AT OFFSETS (90, 60, 30, 7 DAYS)
# =====================================================================

@pytest.mark.django_db
def test_reminders_trigger_at_correct_offsets_and_idempotency(seed_test_data):
    institution = seed_test_data['institution']

    fdr = Instrument.objects.create(
        institution=institution,
        instrument_type=InstrumentType.FDR,
        reference_number="FDR-REMINDER-101",
        issuing_bank="State Bank of India",
        issuing_branch="Delhi Branch",
        branch_ifsc="SBIN0001111",
        amount=Decimal("5000000.00"),
        issue_date=date(2023, 6, 1),
        maturity_date=date(2028, 6, 1),
        lien_in_favour_of_aicte=True,
        status=InstrumentStatus.ACTIVE,
    )

    # 1. Simulated date 2028-03-03 (90 days before 2028-06-01)
    res_90 = run_monitoring_job(effective_date=date(2028, 3, 3))
    assert res_90['reminders_dispatched'] > 0
    notifs_90 = Notification.objects.filter(instrument=fdr, offset_days=90)
    assert notifs_90.exists()

    # IDEMPOTENCY TEST: Running again on same day creates 0 duplicate notifications!
    count_before = Notification.objects.filter(instrument=fdr).count()
    res_90_repeat = run_monitoring_job(effective_date=date(2028, 3, 3))
    count_after = Notification.objects.filter(instrument=fdr).count()
    assert count_before == count_after
    assert res_90_repeat['reminders_dispatched'] == 0

    # 2. Simulated date 2028-04-02 (60 days before maturity)
    run_monitoring_job(effective_date=date(2028, 4, 2))
    assert Notification.objects.filter(instrument=fdr, offset_days=60).exists()

    # 3. Simulated date 2028-05-02 (30 days before maturity)
    run_monitoring_job(effective_date=date(2028, 5, 2))
    assert Notification.objects.filter(instrument=fdr, offset_days=30).exists()

    # 4. Simulated date 2028-05-25 (7 days before maturity)
    run_monitoring_job(effective_date=date(2028, 5, 25))
    assert Notification.objects.filter(instrument=fdr, offset_days=7).exists()


# =====================================================================
# 4. OVERDUE MATURED CASES & ESCALATION LADDER
# =====================================================================

@pytest.mark.django_db
def test_matured_fdr_overdue_and_multi_tier_escalation(seed_test_data):
    institution = seed_test_data['institution']

    fdr = Instrument.objects.create(
        institution=institution,
        instrument_type=InstrumentType.FDR,
        reference_number="FDR-OVERDUE-ESC",
        issuing_bank="Punjab National Bank",
        issuing_branch="CP Branch",
        branch_ifsc="PUNB0002222",
        amount=Decimal("3500000.00"),
        issue_date=date(2020, 1, 1),
        maturity_date=date(2028, 1, 1),
        status=InstrumentStatus.MATURED,
    )

    # 1. 5 days after maturity (less than 15-day wait period): No escalation yet
    res_5d = run_monitoring_job(effective_date=date(2028, 1, 6))
    assert res_5d['escalations_triggered'] == 0
    assert EscalationRecord.objects.filter(instrument=fdr).count() == 0

    # 2. 16 days after maturity (exceeds Tier 1 wait period of 15 days):
    # Should escalate from INSTITUTION to SCRUTINY_OFFICER
    res_16d = run_monitoring_job(effective_date=date(2028, 1, 17))
    assert res_16d['escalations_triggered'] == 1
    tier1 = EscalationRecord.objects.filter(instrument=fdr, to_level='SCRUTINY_OFFICER').first()
    assert tier1 is not None
    assert tier1.from_level == 'INSTITUTION'

    # Check escalation notification was dispatched
    assert Notification.objects.filter(
        instrument=fdr,
        notification_type=NotificationType.ESCALATION,
        escalation_level='SCRUTINY_OFFICER'
    ).exists()

    # 3. 32 days after maturity (exceeds Tier 2 wait period of 30 days):
    # Should escalate from SCRUTINY_OFFICER to DIRECTOR
    res_32d = run_monitoring_job(effective_date=date(2028, 2, 2))
    assert res_32d['escalations_triggered'] == 1
    tier2 = EscalationRecord.objects.filter(instrument=fdr, to_level='DIRECTOR').first()
    assert tier2 is not None
    assert tier2.from_level == 'SCRUTINY_OFFICER'


# =====================================================================
# 5. UNRESOLVED DISCREPANCY ESCALATION
# =====================================================================

@pytest.mark.django_db
def test_unresolved_discrepancy_escalation(seed_test_data):
    institution = seed_test_data['institution']

    fdr = Instrument.objects.create(
        institution=institution,
        instrument_type=InstrumentType.FDR,
        reference_number="FDR-DISC-ESC",
        issuing_bank="HDFC Bank",
        issuing_branch="Connaught Place",
        branch_ifsc="HDFC0000001",
        amount=Decimal("3500000.00"),
        issue_date=date(2024, 1, 1),
        maturity_date=date(2032, 1, 1),
        status=InstrumentStatus.DISCREPANCY,
    )

    # Add discrepancy created at 2028-01-01
    disc = Discrepancy.objects.create(
        instrument=fdr,
        rule_code="AMOUNT_MISMATCH_BANK",
        severity=DiscrepancySeverity.HIGH,
        title="Amount mismatch vs Bank",
        description="Declared amount is higher than bank record",
        is_resolved=False,
    )
    # Manually backdate created_at for time travel test
    Discrepancy.objects.filter(pk=disc.pk).update(created_at=timezone.make_aware(timezone.datetime(2028, 1, 1, 10, 0)))

    # At 2028-01-09 (8 days later, > 7 day SLA):
    # Escalates to SCRUTINY_OFFICER
    res = run_monitoring_job(effective_date=date(2028, 1, 9))
    assert res['escalations_triggered'] >= 1
    assert EscalationRecord.objects.filter(
        instrument=fdr,
        trigger_condition=EscalationCondition.UNRESOLVED_DISCREPANCY,
        to_level='SCRUTINY_OFFICER'
    ).exists()


# =====================================================================
# 6. COMMUNICATION CHANNELS: SMS & EMAIL DISPATCH TESTS
# =====================================================================

@pytest.mark.django_db
def test_sms_adapter_stub_and_email_delivery(seed_test_data):
    institution = seed_test_data['institution']
    fdr = Instrument.objects.create(
        institution=institution,
        instrument_type=InstrumentType.FDR,
        reference_number="FDR-SMS-EMAIL-001",
        issuing_bank="SBI",
        issuing_branch="Delhi",
        branch_ifsc="SBIN0000100",
        amount=Decimal("5000000.00"),
        issue_date=date(2023, 1, 1),
        maturity_date=date(2028, 1, 1),
        status=InstrumentStatus.ACTIVE,
    )

    mail.outbox = []

    # 7 days before maturity has channel=ALL (IN_APP, EMAIL, SMS)
    run_monitoring_job(effective_date=date(2027, 12, 25))

    # Verify Email was sent to outbox
    assert len(mail.outbox) > 0
    assert "FDR-SMS-EMAIL-001" in mail.outbox[0].subject or "FDR-SMS-EMAIL-001" in mail.outbox[0].body

    # Verify SMS notification was recorded
    sms_notif = Notification.objects.filter(
        instrument=fdr,
        channel=NotificationChannel.SMS
    ).first()
    assert sms_notif is not None


# =====================================================================
# 7. NOTIFICATION API: READ STATUS & ADMIN ON-DEMAND MONITORING JOB
# =====================================================================

@pytest.mark.django_db
def test_notification_mark_read_and_admin_job_endpoint(api_client, seed_test_data):
    admin = seed_test_data['admin_user']
    institution = seed_test_data['institution']
    api_client.force_authenticate(user=admin)

    # Create an instrument maturing on 2028-06-01
    Instrument.objects.create(
        institution=institution,
        instrument_type=InstrumentType.FDR,
        reference_number="FDR-ENDPOINT-TEST",
        issuing_bank="State Bank of India",
        issuing_branch="Dwarka Branch",
        branch_ifsc="SBIN0000001",
        amount=Decimal("5000000.00"),
        issue_date=date(2023, 6, 1),
        maturity_date=date(2028, 6, 1),
        status=InstrumentStatus.ACTIVE,
    )

    # 1. Admin triggers on-demand monitoring job with effective date
    res_job = api_client.post('/api/admin/run-monitoring-job/', {'effective_date': '2028-06-01'}, format='json')
    assert res_job.status_code == status.HTTP_200_OK
    assert res_job.data['status'] == 'SUCCESS'

    # 2. Check notifications API

    res_list = api_client.get('/api/notifications/')
    assert res_list.status_code == status.HTTP_200_OK
    items = res_list.data['results'] if isinstance(res_list.data, dict) and 'results' in res_list.data else res_list.data
    assert len(items) > 0

    first_notif_id = items[0]['id']


    # 3. Mark as read
    res_read = api_client.post(f'/api/notifications/{first_notif_id}/mark-read/')
    assert res_read.status_code == status.HTTP_200_OK
    assert res_read.data['is_read'] is True

    # 4. Check unread count
    res_count = api_client.get('/api/notifications/unread-count/')
    assert res_count.status_code == status.HTTP_200_OK
    assert 'unread_count' in res_count.data
