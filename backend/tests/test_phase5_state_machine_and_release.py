import pytest
from datetime import date, timedelta
from django.urls import reverse
from rest_framework import status
from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError, PermissionDenied

from apps.institutions.models import Institution
from apps.instruments.models import (
    Instrument,
    InstrumentStatus,
    InstrumentType,
    Document,
    FieldSource,
    Discrepancy,
    DiscrepancySeverity,
)
from apps.instruments.state_machine import InstrumentStateMachine
from apps.users.models import UserRole
from apps.common.models import DataProvenanceSource, AuditLog
from apps.notifications.models import Notification

User = get_user_model()


@pytest.fixture
def p5_fixture(db):
    inst = Institution.objects.create(
        aicte_id="1-P5-TEST",
        name="National Institute of Technology Delhi",
        state="Delhi",
        district="New Delhi",
        institution_type="Engineering & Technology",
        contact_email="director@nitdelhi.ac.in"
    )

    user_inst = User.objects.create_user(
        username="p5_inst_user",
        password="Password@123",
        role=UserRole.INSTITUTION,
        institution=inst
    )
    user_officer = User.objects.create_user(
        username="p5_officer",
        password="Password@123",
        role=UserRole.SCRUTINY_OFFICER
    )
    user_approver = User.objects.create_user(
        username="p5_approver",
        password="Password@123",
        role=UserRole.APPROVING_AUTHORITY
    )
    user_admin = User.objects.create_user(
        username="p5_admin",
        password="Password@123",
        role=UserRole.ADMIN,
        is_staff=True
    )

    base_fdr = Instrument.objects.create(
        institution=inst,
        instrument_type=InstrumentType.FDR,
        reference_number="P5-FDR-001",
        issuing_bank="State Bank of India",
        issuing_branch="Parliament Street",
        branch_ifsc="SBIN0000691",
        amount=1500000.00,
        issue_date=date(2016, 5, 1),
        maturity_date=date(2024, 5, 1),
        status=InstrumentStatus.ACTIVE,
        created_by=user_inst
    )

    return {
        'inst': inst,
        'user_inst': user_inst,
        'user_officer': user_officer,
        'user_approver': user_approver,
        'user_admin': user_admin,
        'base_fdr': base_fdr,
    }


def auth(client, user):
    client.force_authenticate(user=user)


# =============================================================================
# 1. STATE MACHINE SERVER-SIDE TESTS: ALLOWED & FORBIDDEN TRANSITIONS
# =============================================================================

@pytest.mark.django_db
def test_state_machine_allowed_transitions(p5_fixture):
    """Verifies all valid state machine transitions transition cleanly."""
    fdr = p5_fixture['base_fdr']
    officer = p5_fixture['user_officer']
    approver = p5_fixture['user_approver']
    admin = p5_fixture['user_admin']

    # 1. ACTIVE -> MATURED (lifecycle/officer/admin)
    InstrumentStateMachine.apply_transition(fdr, InstrumentStatus.MATURED, user=admin)
    assert fdr.status == InstrumentStatus.MATURED

    # 2. MATURED -> RELEASE_REQUESTED (inst user)
    InstrumentStateMachine.apply_transition(fdr, InstrumentStatus.RELEASE_REQUESTED, user=p5_fixture['user_inst'])
    assert fdr.status == InstrumentStatus.RELEASE_REQUESTED

    # 3. RELEASE_REQUESTED -> UNDER_SCRUTINY (officer)
    InstrumentStateMachine.apply_transition(fdr, InstrumentStatus.UNDER_SCRUTINY, user=officer)
    assert fdr.status == InstrumentStatus.UNDER_SCRUTINY

    # 4. UNDER_SCRUTINY -> RELEASED (approver)
    InstrumentStateMachine.apply_transition(fdr, InstrumentStatus.RELEASED, user=approver)
    assert fdr.status == InstrumentStatus.RELEASED


@pytest.mark.django_db
def test_state_machine_forbidden_transitions_raise_validation_error(p5_fixture):
    """Verifies that invalid state transitions raise ValidationError."""
    fdr = p5_fixture['base_fdr']

    # Current status: ACTIVE. Cannot jump to SUBMITTED or UNDER_SCRUTINY
    with pytest.raises(ValidationError):
        InstrumentStateMachine.validate_transition(fdr.status, InstrumentStatus.SUBMITTED)

    with pytest.raises(ValidationError):
        InstrumentStateMachine.validate_transition(fdr.status, InstrumentStatus.UNDER_SCRUTINY)

    # Terminal states: RELEASED, REPLACED, RENEWED, REJECTED cannot transition anywhere
    fdr.status = InstrumentStatus.RELEASED
    fdr.save()
    with pytest.raises(ValidationError):
        InstrumentStateMachine.validate_transition(fdr.status, InstrumentStatus.ACTIVE)

    fdr.status = InstrumentStatus.REPLACED
    fdr.save()
    with pytest.raises(ValidationError):
        InstrumentStateMachine.validate_transition(fdr.status, InstrumentStatus.VERIFIED)

    fdr.status = InstrumentStatus.REJECTED
    fdr.save()
    with pytest.raises(ValidationError):
        InstrumentStateMachine.validate_transition(fdr.status, InstrumentStatus.UNDER_SCRUTINY)


@pytest.mark.django_db
def test_state_machine_role_enforcement(p5_fixture):
    """Verifies that unauthorized roles are forbidden from executing restricted transitions."""
    fdr = p5_fixture['base_fdr']
    inst_user = p5_fixture['user_inst']
    officer = p5_fixture['user_officer']
    approver = p5_fixture['user_approver']

    # 1. Institution user cannot verify
    fdr.status = InstrumentStatus.SUBMITTED
    with pytest.raises(PermissionDenied):
        InstrumentStateMachine.validate_transition(
            current_status=fdr.status,
            target_status=InstrumentStatus.VERIFIED,
            user=inst_user
        )

    # 2. Scrutiny Officer cannot approve release
    fdr.status = InstrumentStatus.UNDER_SCRUTINY
    with pytest.raises(PermissionDenied):
        InstrumentStateMachine.validate_transition(
            current_status=fdr.status,
            target_status=InstrumentStatus.RELEASED,
            user=officer
        )

    # 3. Scrutiny Officer cannot reject release
    with pytest.raises(PermissionDenied):
        InstrumentStateMachine.validate_transition(
            current_status=fdr.status,
            target_status=InstrumentStatus.REJECTED,
            user=officer
        )

    # 4. Approving Authority cannot mark verified
    fdr.status = InstrumentStatus.SUBMITTED
    with pytest.raises(PermissionDenied):
        InstrumentStateMachine.validate_transition(
            current_status=fdr.status,
            target_status=InstrumentStatus.VERIFIED,
            user=approver
        )


# =============================================================================
# 2. RENEWAL / REPLACEMENT LINKED CHAIN & TIMELINE TESTS
# =============================================================================

@pytest.mark.django_db
def test_replacement_submission_and_auto_replacement_on_verification(api_client, p5_fixture):
    """
    Institution submits a replacement FDR linked to the original.
    When the replacement FDR is verified, the original automatically becomes Replaced.
    """
    inst_user = p5_fixture['user_inst']
    officer = p5_fixture['user_officer']
    old_fdr = p5_fixture['base_fdr']
    assert old_fdr.status == InstrumentStatus.ACTIVE

    auth(api_client, inst_user)

    # Submit replacement FDR linked to old_fdr
    create_url = reverse('instrument-list')
    replacement_payload = {
        'instrument_type': 'FDR',
        'reference_number': 'P5-REPLACE-002',
        'issuing_bank': 'State Bank of India',
        'issuing_branch': 'Parliament Street',
        'branch_ifsc': 'SBIN0000691',
        'amount': '1500000.00',
        'issue_date': '2024-05-01',
        'maturity_date': '2032-05-01',
        'lien_in_favour_of_aicte': True,
        'joint_holder_name': 'NIT Delhi and Member Secretary AICTE',
        'replaces': old_fdr.id,
        'renewal_type': 'REPLACEMENT'
    }
    res = api_client.post(create_url, replacement_payload, format='json')
    assert res.status_code == status.HTTP_201_CREATED
    new_fdr_id = res.data['id']

    new_fdr = Instrument.objects.get(pk=new_fdr_id)
    assert new_fdr.replaces_id == old_fdr.id

    # Attach FDR certificate document to replacement instrument and clear flags
    Document.objects.create(
        instrument=new_fdr,
        document_type='FDR_CERTIFICATE',
        file_name='fdr_replacement.pdf',
        mime_type='application/pdf',
        sha256_hash='b' * 64,
        file_size_bytes=2048,
        storage_path='/secure_vault/replace.enc',
        is_encrypted=True
    )
    new_fdr.discrepancies.all().delete()
    new_fdr.status = InstrumentStatus.SUBMITTED
    new_fdr.save()
    assert new_fdr.status == InstrumentStatus.SUBMITTED

    # Old FDR remains ACTIVE while replacement is under scrutiny/submitted
    old_fdr.refresh_from_db()
    assert old_fdr.status == InstrumentStatus.ACTIVE

    # Scrutiny Officer verifies the replacement FDR
    auth(api_client, officer)
    verify_url = reverse('instrument-mark-verified', kwargs={'pk': new_fdr_id})
    v_res = api_client.post(verify_url, {'notes': 'Replacement FDR verified with CBS confirmation.'})
    assert v_res.status_code == status.HTTP_200_OK
    assert v_res.data['status'] == InstrumentStatus.VERIFIED

    # Check side effect: Old FDR MUST automatically transition to REPLACED
    old_fdr.refresh_from_db()
    assert old_fdr.status == InstrumentStatus.REPLACED
    assert old_fdr.remarks.filter(remark_type='STATUS_CHANGE', text__contains='Automatically replaced by verified new instrument').exists()

    # Verify audit log recorded for auto-replacement
    audit = AuditLog.objects.filter(
        action='STATUS_TRANSITION_REPLACED',
        entity_id=str(old_fdr.id)
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_replacement_timeline_lineage(api_client, p5_fixture):
    """
    Tests get_replacement_chain() and /api/instruments/<id>/lineage/
    across a 3-generation replacement chain (Gen 1 -> Gen 2 -> Gen 3).
    """
    inst = p5_fixture['inst']
    user_inst = p5_fixture['user_inst']
    fdr_gen1 = p5_fixture['base_fdr']  # 2016-2024

    fdr_gen2 = Instrument.objects.create(
        institution=inst,
        instrument_type=InstrumentType.FDR,
        reference_number="P5-FDR-GEN2",
        issuing_bank="State Bank of India",
        issuing_branch="Main",
        branch_ifsc="SBIN0000691",
        amount=1500000.00,
        issue_date=date(2024, 5, 1),
        maturity_date=date(2028, 5, 1),
        status=InstrumentStatus.REPLACED,
        replaces=fdr_gen1,
        created_by=user_inst
    )

    fdr_gen3 = Instrument.objects.create(
        institution=inst,
        instrument_type=InstrumentType.FDR,
        reference_number="P5-FDR-GEN3",
        issuing_bank="State Bank of India",
        issuing_branch="Main",
        branch_ifsc="SBIN0000691",
        amount=1500000.00,
        issue_date=date(2028, 5, 1),
        maturity_date=date(2036, 5, 1),
        status=InstrumentStatus.ACTIVE,
        replaces=fdr_gen2,
        created_by=user_inst
    )

    auth(api_client, user_inst)

    # Calling lineage from Gen 2 should return all 3 generations
    lineage_url = reverse('instrument-lineage', kwargs={'pk': fdr_gen2.id})
    res = api_client.get(lineage_url)
    assert res.status_code == status.HTTP_200_OK

    timeline = res.data['timeline']
    assert len(timeline) == 3
    refs = [item['reference_number'] for item in timeline]
    assert refs == ['P5-FDR-001', 'P5-FDR-GEN2', 'P5-FDR-GEN3']

    # Gen 2 should be flagged as is_current: True when querying from Gen 2
    gen2_entry = next(item for item in timeline if item['reference_number'] == 'P5-FDR-GEN2')
    assert gen2_entry['is_current'] is True


# =============================================================================
# 3. RELEASE / REFUND WORKFLOW TESTS (REQUEST -> SCRUTINY -> APPROVAL -> RELEASE)
# =============================================================================

@pytest.mark.django_db
def test_full_release_workflow_happy_path(api_client, p5_fixture):
    """
    Tests complete lifecycle:
    1. Institution requests release
    2. Officer scrutinizes and recommends approval
    3. Precondition checklist passes (bank verified, no discrepancies, matured, no hold)
    4. Approving Authority approves release with order reference
    5. Notifications received by institution at each step
    """
    fdr = p5_fixture['base_fdr']
    inst_user = p5_fixture['user_inst']
    officer = p5_fixture['user_officer']
    approver = p5_fixture['user_approver']

    # Attach bank confirmed provenance so precondition passes
    FieldSource.objects.create(
        instrument=fdr,
        field_name='amount',
        field_value=str(fdr.amount),
        value_source=DataProvenanceSource.BANK_CONFIRMED,
        is_confirmed=True
    )
    # Attach mandatory certificate document
    Document.objects.create(
        instrument=fdr,
        document_type='FDR_CERTIFICATE',
        file_name='fdr_scan.pdf',
        mime_type='application/pdf',
        sha256_hash='a' * 64,
        file_size_bytes=1024,
        storage_path='/secure_vault/test.enc',
        is_encrypted=True
    )

    # Step 1: Institution requests release
    auth(api_client, inst_user)
    req_url = reverse('instrument-request-release', kwargs={'pk': fdr.id})
    res1 = api_client.post(req_url, {'justification': 'Completed 8-year statutory lock-in period successfully.'})
    assert res1.status_code == status.HTTP_200_OK
    assert res1.data['status'] == InstrumentStatus.RELEASE_REQUESTED

    fdr.refresh_from_db()
    assert fdr.status == InstrumentStatus.RELEASE_REQUESTED
    assert fdr.release_requested_at is not None

    # Step 2: Officer scrutinizes release
    auth(api_client, officer)
    scrutiny_url = reverse('instrument-scrutinize-release', kwargs={'pk': fdr.id})
    res2 = api_client.post(scrutiny_url, {
        'recommendation': 'RECOMMEND_APPROVAL',
        'notes': 'All bank certificates verified. Zero compliance flags.'
    })
    assert res2.status_code == status.HTTP_200_OK
    assert res2.data['status'] == InstrumentStatus.UNDER_SCRUTINY

    fdr.refresh_from_db()
    assert fdr.status == InstrumentStatus.UNDER_SCRUTINY
    assert fdr.scrutiny_recommendation == 'RECOMMEND_APPROVAL'

    # Step 3: Check automated preconditions
    chk_url = reverse('instrument-release-checklist', kwargs={'pk': fdr.id})
    chk_res = api_client.get(chk_url)
    assert chk_res.status_code == status.HTTP_200_OK
    assert chk_res.data['can_approve'] is True
    assert chk_res.data['is_bank_confirmed'] is True
    assert chk_res.data['no_open_discrepancies'] is True
    assert chk_res.data['no_compliance_hold'] is True

    # Step 4: Approving Authority approves release
    auth(api_client, approver)
    approve_url = reverse('instrument-approve-release', kwargs={'pk': fdr.id})
    res3 = api_client.post(approve_url, {
        'release_order_reference': 'AICTE-HQ-REL-2026-9901',
        'decision_notes': 'Formal refund and release sanctioned by Competent Authority.'
    })
    assert res3.status_code == status.HTTP_200_OK
    assert res3.data['status'] == InstrumentStatus.RELEASED

    fdr.refresh_from_db()
    assert fdr.status == InstrumentStatus.RELEASED
    assert fdr.released_by == approver
    assert fdr.release_order_reference == 'AICTE-HQ-REL-2026-9901'

    # Step 5: Notifications verified at each milestone
    notifs = Notification.objects.filter(instrument=fdr)
    assert notifs.filter(title__contains='Release Request Submitted').exists()
    assert notifs.filter(title__contains='Release Request Under Scrutiny').exists()
    assert notifs.filter(title__contains='RELEASE APPROVED').exists()


@pytest.mark.django_db
def test_release_blocked_when_preconditions_fail(api_client, p5_fixture):
    """
    Tests that Approving Authority release approval is STRICTLY blocked server-side when:
    - Open discrepancies exist
    - Compliance hold is active
    """
    fdr = p5_fixture['base_fdr']
    approver = p5_fixture['user_approver']
    fdr.status = InstrumentStatus.UNDER_SCRUTINY
    fdr.save()

    # Precondition Failure 1: Unresolved discrepancy
    Discrepancy.objects.create(
        instrument=fdr,
        rule_code='DISC_AMOUNT_MISMATCH',
        severity=DiscrepancySeverity.CRITICAL,
        title='Amount discrepancy',
        description='Bank reported lower amount',
        is_resolved=False
    )

    auth(api_client, approver)
    approve_url = reverse('instrument-approve-release', kwargs={'pk': fdr.id})
    res = api_client.post(approve_url, {
        'release_order_reference': 'REL-FAIL-001',
        'decision_notes': 'Attempting approval'
    })
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert 'preconditions' in res.data
    assert any('unresolved discrepancy' in msg for msg in res.data['preconditions'])

    # Resolve discrepancy, but activate Compliance Hold
    fdr.discrepancies.all().update(is_resolved=True)
    fdr.compliance_hold = True
    fdr.compliance_hold_reason = "Vigilance inquiry pending regarding land title"
    fdr.save()

    res2 = api_client.post(approve_url, {
        'release_order_reference': 'REL-FAIL-002',
        'decision_notes': 'Attempting approval with hold'
    })
    assert res2.status_code == status.HTTP_400_BAD_REQUEST
    assert any('compliance hold' in msg.lower() for msg in res2.data['preconditions'])


@pytest.mark.django_db
def test_release_rejection_with_mandatory_reason(api_client, p5_fixture):
    """
    Tests that Approving Authority can reject release request,
    recording the rejection reason, updating status to REJECTED, and notifying the institution.
    """
    fdr = p5_fixture['base_fdr']
    approver = p5_fixture['user_approver']
    fdr.status = InstrumentStatus.UNDER_SCRUTINY
    fdr.save()

    auth(api_client, approver)
    reject_url = reverse('instrument-reject-release', kwargs={'pk': fdr.id})
    res = api_client.post(reject_url, {
        'rejection_reason': 'Institution has unresolved deficiencies noted in latest inspection report.'
    })
    assert res.status_code == status.HTTP_200_OK
    assert res.data['status'] == InstrumentStatus.REJECTED

    fdr.refresh_from_db()
    assert fdr.status == InstrumentStatus.REJECTED
    assert fdr.rejection_reason == 'Institution has unresolved deficiencies noted in latest inspection report.'

    # Check notification dispatched to institution
    notif = Notification.objects.filter(
        instrument=fdr,
        title__contains='REJECTED'
    ).first()
    assert notif is not None
    assert 'unresolved deficiencies' in notif.message


@pytest.mark.django_db
def test_compliance_hold_action_set_and_clear(api_client, p5_fixture):
    """
    Tests officer placing and clearing statutory compliance hold.
    """
    fdr = p5_fixture['base_fdr']
    officer = p5_fixture['user_officer']
    auth(api_client, officer)

    hold_url = reverse('instrument-compliance-hold', kwargs={'pk': fdr.id})

    # 1. Place hold
    res1 = api_client.post(hold_url, {
        'compliance_hold': True,
        'reason': 'Pending audit query by CAG'
    })
    assert res1.status_code == status.HTTP_200_OK
    assert res1.data['compliance_hold'] is True
    assert res1.data['compliance_hold_reason'] == 'Pending audit query by CAG'

    fdr.refresh_from_db()
    assert fdr.compliance_hold is True

    # 2. Clear hold
    res2 = api_client.post(hold_url, {
        'compliance_hold': False,
        'reason': 'CAG audit query settled satisfactorily'
    })
    assert res2.status_code == status.HTTP_200_OK
    assert res2.data['compliance_hold'] is False

    fdr.refresh_from_db()
    assert fdr.compliance_hold is False
