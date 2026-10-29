import pytest
import hashlib
from datetime import date
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model

from apps.institutions.models import Institution
from apps.instruments.models import (
    Instrument,
    Document,
    FieldSource,
    Remark,
    InstrumentStatus,
    InstrumentType,
)
from apps.common.models import DataProvenanceSource
from apps.users.models import UserRole

User = get_user_model()

@pytest.fixture
def model_fixture(db):
    inst = Institution.objects.create(aicte_id="1-MOD-001", name="Model Test Institute", state="Karnataka")
    user = User.objects.create_user(username="mod_user", password="Password@123", role=UserRole.INSTITUTION, institution=inst)
    instrument = Instrument.objects.create(
        institution=inst,
        instrument_type=InstrumentType.FDR,
        reference_number="FDR-MODEL-001",
        issuing_bank="Canara Bank",
        issuing_branch="Bangalore Main",
        branch_ifsc="CNRB0000001",
        amount=2000000.00,
        issue_date=date(2024, 1, 1),
        maturity_date=date(2032, 1, 1),
        status=InstrumentStatus.SUBMITTED,
        created_by=user,
    )
    return inst, user, instrument


@pytest.mark.django_db
def test_document_sha256_hash_auto_generation(model_fixture):
    _, user, instrument = model_fixture
    content = b"AICTE FDR Joint Fixed Deposit Agreement Certificate Content"
    expected_hash = hashlib.sha256(content).hexdigest()

    file_upload = SimpleUploadedFile("fdr_certificate.pdf", content, content_type="application/pdf")
    doc = Document.objects.create(
        instrument=instrument,
        document_type="FDR_CERTIFICATE",
        file=file_upload,
        uploaded_by=user,
    )

    assert doc.sha256_hash == expected_hash
    assert len(doc.sha256_hash) == 64
    assert doc.file_name == "fdr_certificate.pdf"


@pytest.mark.django_db
def test_field_source_provenance_tracking(model_fixture):
    _, user, instrument = model_fixture

    # Claimed institution source
    fs_claimed = FieldSource.objects.create(
        instrument=instrument,
        field_name='amount',
        field_value='2000000.00',
        value_source=DataProvenanceSource.INSTITUTION_SUBMITTED,
        is_confirmed=False
    )
    assert fs_claimed.value_source == DataProvenanceSource.INSTITUTION_SUBMITTED
    assert fs_claimed.is_confirmed is False

    # Bank-confirmed source
    fs_confirmed = FieldSource.objects.create(
        instrument=instrument,
        field_name='amount',
        field_value='2000000.00',
        value_source=DataProvenanceSource.BANK_CONFIRMED,
        source_reference='CBS-REF-9988',
        is_confirmed=True
    )
    assert fs_confirmed.value_source == DataProvenanceSource.BANK_CONFIRMED
    assert fs_confirmed.is_confirmed is True

    # Officer-entered adjustment
    fs_officer = FieldSource.objects.create(
        instrument=instrument,
        field_name='joint_holder_name',
        field_value='Model Test Institute and AICTE',
        value_source=DataProvenanceSource.OFFICER_ENTERED,
        is_confirmed=True
    )
    assert fs_officer.value_source == DataProvenanceSource.OFFICER_ENTERED


@pytest.mark.django_db
def test_all_instrument_statuses_valid(model_fixture):
    _, _, instrument = model_fixture
    expected_statuses = [
        'Submitted',
        'Under Scrutiny',
        'Verified',
        'Active',
        'Expiring',
        'Matured',
        'Renewed',
        'Replaced',
        'Release Requested',
        'Released',
        'Discrepancy',
        'Rejected',
    ]
    for st in expected_statuses:
        instrument.status = st
        instrument.save()
        instrument.refresh_from_db()
        assert instrument.status == st


@pytest.mark.django_db
def test_remark_internal_vs_external(model_fixture):
    _, user, instrument = model_fixture
    rem_ext = Remark.objects.create(
        instrument=instrument,
        author=user,
        remark_type='INSTITUTION_RESPONSE',
        text='Submitted renewed lien document',
        is_internal=False
    )
    rem_int = Remark.objects.create(
        instrument=instrument,
        author=user,
        remark_type='SCRUTINY_NOTE',
        text='Vigilance clearance flag checked internally',
        is_internal=True
    )
    assert rem_ext.is_internal is False
    assert rem_int.is_internal is True
