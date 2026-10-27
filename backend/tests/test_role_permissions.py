import pytest
from datetime import date
from django.urls import reverse
from rest_framework import status
from django.contrib.auth import get_user_model

from apps.institutions.models import Institution
from apps.instruments.models import Instrument, InstrumentStatus, InstrumentType
from apps.users.models import UserRole
from apps.common.models import DataProvenanceSource, AuditLog

User = get_user_model()

@pytest.fixture
def rbac_fixture(db):
    # Two distinct institutions
    inst_a = Institution.objects.create(aicte_id="1-AAA", name="Alpha Institute", state="Delhi")
    inst_b = Institution.objects.create(aicte_id="1-BBB", name="Beta Polytechnic", state="Maharashtra")

    # Users
    user_inst_a = User.objects.create_user(
        username="user_a", password="Password@123", role=UserRole.INSTITUTION, institution=inst_a
    )
    user_inst_b = User.objects.create_user(
        username="user_b", password="Password@123", role=UserRole.INSTITUTION, institution=inst_b
    )
    user_officer = User.objects.create_user(
        username="officer", password="Password@123", role=UserRole.SCRUTINY_OFFICER
    )
    user_approver = User.objects.create_user(
        username="approver", password="Password@123", role=UserRole.APPROVING_AUTHORITY
    )
    user_admin = User.objects.create_user(
        username="admin_user", password="Password@123", role=UserRole.ADMIN, is_staff=True
    )

    # Instruments
    fdr_a = Instrument.objects.create(
        institution=inst_a,
        instrument_type=InstrumentType.FDR,
        reference_number="FDR-A-001",
        issuing_bank="State Bank of India",
        issuing_branch="Main Branch",
        branch_ifsc="SBIN0000001",
        amount=1000000.00,
        issue_date=date(2024, 1, 1),
        maturity_date=date(2032, 1, 1),
        status=InstrumentStatus.SUBMITTED,
        created_by=user_inst_a
    )
    fdr_b = Instrument.objects.create(
        institution=inst_b,
        instrument_type=InstrumentType.FDR,
        reference_number="FDR-B-002",
        issuing_bank="Punjab National Bank",
        issuing_branch="Camp Branch",
        branch_ifsc="PUNB0000002",
        amount=500000.00,
        issue_date=date(2023, 5, 1),
        maturity_date=date(2031, 5, 1),
        status=InstrumentStatus.SUBMITTED,
        created_by=user_inst_b
    )

    return {
        'inst_a': inst_a,
        'inst_b': inst_b,
        'user_inst_a': user_inst_a,
        'user_inst_b': user_inst_b,
        'user_officer': user_officer,
        'user_approver': user_approver,
        'user_admin': user_admin,
        'fdr_a': fdr_a,
        'fdr_b': fdr_b,
    }


def authenticate_user(api_client, user):
    api_client.force_authenticate(user=user)


# =============================================================================
# 1. INSTITUTION ROLE PERMISSIONS & CROSS-INSTITUTION RESTRICTIONS
# =============================================================================

@pytest.mark.django_db
def test_institution_user_sees_only_own_records(api_client, rbac_fixture):
    authenticate_user(api_client, rbac_fixture['user_inst_a'])
    url = reverse('instrument-list')
    res = api_client.get(url)
    assert res.status_code == status.HTTP_200_OK

    ref_numbers = [item['reference_number'] for item in res.data['results'] if 'results' in res.data] if isinstance(res.data, dict) and 'results' in res.data else [item['reference_number'] for item in res.data]
    assert "FDR-A-001" in ref_numbers
    assert "FDR-B-002" not in ref_numbers  # Beta Polytechnic record hidden


@pytest.mark.django_db
def test_cross_institution_access_strictly_denied(api_client, rbac_fixture):
    """Institution A user attempts to directly access Institution B instrument"""
    authenticate_user(api_client, rbac_fixture['user_inst_a'])
    url = reverse('instrument-detail', kwargs={'pk': rbac_fixture['fdr_b'].id})
    res = api_client.get(url)
    assert res.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN]


@pytest.mark.django_db
def test_cross_institution_modification_denied(api_client, rbac_fixture):
    """Institution A user attempts to PATCH/modify Institution B instrument"""
    authenticate_user(api_client, rbac_fixture['user_inst_a'])
    url = reverse('instrument-detail', kwargs={'pk': rbac_fixture['fdr_b'].id})
    res = api_client.patch(url, {'amount': 999999.00}, format='json')
    assert res.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN]


@pytest.mark.django_db
def test_institution_user_cannot_verify_instrument(api_client, rbac_fixture):
    """Institution user cannot trigger bank verification"""
    authenticate_user(api_client, rbac_fixture['user_inst_a'])
    url = reverse('instrument-verify', kwargs={'pk': rbac_fixture['fdr_a'].id})
    res = api_client.post(url, {})
    assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_institution_user_cannot_flag_discrepancy(api_client, rbac_fixture):
    """Institution user cannot flag discrepancies"""
    authenticate_user(api_client, rbac_fixture['user_inst_a'])
    url = reverse('instrument-flag-discrepancy', kwargs={'pk': rbac_fixture['fdr_a'].id})
    res = api_client.post(url, {'reason': 'Invalid test'})
    assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_institution_user_cannot_approve_or_reject_release(api_client, rbac_fixture):
    """Institution user cannot approve or reject release"""
    authenticate_user(api_client, rbac_fixture['user_inst_a'])
    approve_url = reverse('instrument-approve-release', kwargs={'pk': rbac_fixture['fdr_a'].id})
    res = api_client.post(approve_url, {})
    assert res.status_code == status.HTTP_403_FORBIDDEN

    reject_url = reverse('instrument-reject-release', kwargs={'pk': rbac_fixture['fdr_a'].id})
    res2 = api_client.post(reject_url, {})
    assert res2.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_institution_user_can_create_own_instrument_and_request_release(api_client, rbac_fixture):
    """Institution user can submit instrument for their own college and request release"""
    authenticate_user(api_client, rbac_fixture['user_inst_a'])
    create_url = reverse('instrument-list')
    payload = {
        'instrument_type': 'FDR',
        'reference_number': 'FDR-A-NEW-999',
        'issuing_bank': 'HDFC Bank',
        'issuing_branch': 'Connaught Place',
        'branch_ifsc': 'HDFC0000001',
        'amount': '750000.00',
        'issue_date': '2024-03-01',
        'maturity_date': '2032-03-01',
        'lien_in_favour_of_aicte': True,
        'joint_holder_name': 'Alpha Institute and AICTE',
    }
    res = api_client.post(create_url, payload, format='json')
    assert res.status_code == status.HTTP_201_CREATED
    inst_id = res.data['id']

    # Now request release
    req_url = reverse('instrument-request-release', kwargs={'pk': inst_id})
    req_res = api_client.post(req_url, {'notes': 'Completed 8 years'})
    assert req_res.status_code == status.HTTP_200_OK
    assert req_res.data['status'] == InstrumentStatus.RELEASE_REQUESTED


# =============================================================================
# 2. SCRUTINY OFFICER ROLE PERMISSIONS
# =============================================================================

@pytest.mark.django_db
def test_scrutiny_officer_sees_all_institutions(api_client, rbac_fixture):
    authenticate_user(api_client, rbac_fixture['user_officer'])
    url = reverse('instrument-list')
    res = api_client.get(url)
    assert res.status_code == status.HTTP_200_OK
    data = res.data['results'] if 'results' in res.data else res.data
    ref_numbers = [item['reference_number'] for item in data]
    assert "FDR-A-001" in ref_numbers
    assert "FDR-B-002" in ref_numbers  # Scrutiny officer sees both Alpha and Beta


@pytest.mark.django_db
def test_scrutiny_officer_can_verify_and_detect_confirmation(api_client, rbac_fixture):
    authenticate_user(api_client, rbac_fixture['user_officer'])
    fdr_a = rbac_fixture['fdr_a']
    url = reverse('instrument-verify', kwargs={'pk': fdr_a.id})
    res = api_client.post(url, {'notes': 'Verified against SBI CBS portal'})
    assert res.status_code == status.HTTP_200_OK
    assert res.data['status'] == InstrumentStatus.VERIFIED
    assert res.data['bank_verification']['status_code'] == 'CONFIRMED'

    # Check FieldSource created with BANK_CONFIRMED
    fdr_a.refresh_from_db()
    sources = fdr_a.field_sources.filter(value_source=DataProvenanceSource.BANK_CONFIRMED)
    assert sources.exists()


@pytest.mark.django_db
def test_scrutiny_officer_can_flag_discrepancy(api_client, rbac_fixture):
    authenticate_user(api_client, rbac_fixture['user_officer'])
    fdr_a = rbac_fixture['fdr_a']
    url = reverse('instrument-flag-discrepancy', kwargs={'pk': fdr_a.id})
    res = api_client.post(url, {'reason': 'Branch stamp missing on page 2', 'field_name': 'document'})
    assert res.status_code == status.HTTP_200_OK
    assert res.data['status'] == InstrumentStatus.DISCREPANCY

    fdr_a.refresh_from_db()
    assert fdr_a.status == InstrumentStatus.DISCREPANCY
    assert fdr_a.remarks.filter(remark_type='DISCREPANCY_FLAG').exists()


@pytest.mark.django_db
def test_scrutiny_officer_cannot_approve_or_reject_release(api_client, rbac_fixture):
    authenticate_user(api_client, rbac_fixture['user_officer'])
    fdr_a = rbac_fixture['fdr_a']
    fdr_a.status = InstrumentStatus.RELEASE_REQUESTED
    fdr_a.save()

    approve_url = reverse('instrument-approve-release', kwargs={'pk': fdr_a.id})
    res = api_client.post(approve_url, {'decision_notes': 'Officer trying to approve'})
    assert res.status_code == status.HTTP_403_FORBIDDEN

    reject_url = reverse('instrument-reject-release', kwargs={'pk': fdr_a.id})
    res2 = api_client.post(reject_url, {'decision_notes': 'Officer trying to reject'})
    assert res2.status_code == status.HTTP_403_FORBIDDEN


# =============================================================================
# 3. APPROVING AUTHORITY ROLE PERMISSIONS
# =============================================================================

@pytest.mark.django_db
def test_approving_authority_can_approve_release_request(api_client, rbac_fixture):
    authenticate_user(api_client, rbac_fixture['user_approver'])
    fdr_a = rbac_fixture['fdr_a']
    fdr_a.status = InstrumentStatus.RELEASE_REQUESTED
    fdr_a.save()

    approve_url = reverse('instrument-approve-release', kwargs={'pk': fdr_a.id})
    res = api_client.post(approve_url, {'decision_notes': 'Approved release as lock-in completed', 'noc_reference': 'NOC-2026-DEL-101'})
    assert res.status_code == status.HTTP_200_OK
    assert res.data['status'] == InstrumentStatus.RELEASED

    fdr_a.refresh_from_db()
    assert fdr_a.status == InstrumentStatus.RELEASED

    # Verify audit entry recorded
    audit = AuditLog.objects.filter(action='RELEASE_APPROVED', entity_id=str(fdr_a.id)).first()
    assert audit is not None
    assert audit.actor_username == 'approver'


@pytest.mark.django_db
def test_approving_authority_can_reject_release_request(api_client, rbac_fixture):
    authenticate_user(api_client, rbac_fixture['user_approver'])
    fdr_a = rbac_fixture['fdr_a']
    fdr_a.status = InstrumentStatus.RELEASE_REQUESTED
    fdr_a.save()

    reject_url = reverse('instrument-reject-release', kwargs={'pk': fdr_a.id})
    res = api_client.post(reject_url, {'decision_notes': 'Pending vigilance inquiry'})
    assert res.status_code == status.HTTP_200_OK
    assert res.data['status'] == InstrumentStatus.REJECTED

    fdr_a.refresh_from_db()
    assert fdr_a.status == InstrumentStatus.REJECTED


@pytest.mark.django_db
def test_approving_authority_cannot_verify_or_flag_discrepancy(api_client, rbac_fixture):
    authenticate_user(api_client, rbac_fixture['user_approver'])
    fdr_a = rbac_fixture['fdr_a']

    verify_url = reverse('instrument-verify', kwargs={'pk': fdr_a.id})
    res = api_client.post(verify_url, {})
    assert res.status_code == status.HTTP_403_FORBIDDEN

    flag_url = reverse('instrument-flag-discrepancy', kwargs={'pk': fdr_a.id})
    res2 = api_client.post(flag_url, {'reason': 'Approver trying to flag'})
    assert res2.status_code == status.HTTP_403_FORBIDDEN


# =============================================================================
# 4. ADMIN ROLE PERMISSIONS
# =============================================================================

@pytest.mark.django_db
def test_admin_can_manage_users(api_client, rbac_fixture):
    authenticate_user(api_client, rbac_fixture['user_admin'])
    users_url = reverse('user-list')
    res = api_client.get(users_url)
    assert res.status_code == status.HTTP_200_OK

    # Create new user
    create_res = api_client.post(users_url, {
        'username': 'new_officer_2',
        'email': 'officer2@aicte.org',
        'password': 'OfficerPassword2026',
        'role': UserRole.SCRUTINY_OFFICER,
    }, format='json')
    assert create_res.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
def test_non_admin_cannot_access_user_management(api_client, rbac_fixture):
    for non_admin in [rbac_fixture['user_inst_a'], rbac_fixture['user_officer'], rbac_fixture['user_approver']]:
        authenticate_user(api_client, non_admin)
        users_url = reverse('user-list')
        res = api_client.get(users_url)
        assert res.status_code == status.HTTP_403_FORBIDDEN
