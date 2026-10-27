import os
import hashlib
import pytest
from datetime import date
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from django.contrib.auth import get_user_model

from apps.institutions.models import Institution
from apps.instruments.models import Instrument, Document, InstrumentStatus, InstrumentType
from apps.users.models import UserRole
from apps.common.models import AuditLog

User = get_user_model()

@pytest.fixture
def phase2_setup(db):
    inst_a = Institution.objects.create(aicte_id="1-DEL-001", name="Delhi Engineering College", state="Delhi")
    inst_b = Institution.objects.create(aicte_id="1-MUM-002", name="Mumbai Tech Institute", state="Maharashtra")

    user_a = User.objects.create_user(
        username="user_delhi", password="Password@123", role=UserRole.INSTITUTION, institution=inst_a
    )
    user_b = User.objects.create_user(
        username="user_mumbai", password="Password@123", role=UserRole.INSTITUTION, institution=inst_b
    )
    officer = User.objects.create_user(
        username="officer_user", password="Password@123", role=UserRole.SCRUTINY_OFFICER
    )

    fdr_a = Instrument.objects.create(
        institution=inst_a,
        instrument_type=InstrumentType.FDR,
        reference_number="FDR-DEL-1001",
        issuing_bank="State Bank of India",
        issuing_branch="Main Branch",
        branch_ifsc="SBIN0000001",
        amount=1500000.00,
        issue_date=date(2024, 1, 1),
        maturity_date=date(2032, 1, 1),
        status=InstrumentStatus.SUBMITTED,
        created_by=user_a,
    )

    fdr_b = Instrument.objects.create(
        institution=inst_b,
        instrument_type=InstrumentType.FDR,
        reference_number="FDR-MUM-2002",
        issuing_bank="Bank of Baroda",
        issuing_branch="Nariman Point",
        branch_ifsc="BARB0000001",
        amount=1000000.00,
        issue_date=date(2023, 6, 1),
        maturity_date=date(2031, 6, 1),
        status=InstrumentStatus.SUBMITTED,
        created_by=user_b,
    )

    return {
        'inst_a': inst_a,
        'inst_b': inst_b,
        'user_a': user_a,
        'user_b': user_b,
        'officer': officer,
        'fdr_a': fdr_a,
        'fdr_b': fdr_b,
    }


# =============================================================================
# 1. DUPLICATE FDR NUMBER REJECTED
# =============================================================================

@pytest.mark.django_db
def test_duplicate_fdr_number_rejected(api_client, phase2_setup):
    """Submitting an FDR with a reference number that already exists must be rejected."""
    api_client.force_authenticate(user=phase2_setup['user_a'])
    url = reverse('instrument-list')
    payload = {
        'reference_number': 'FDR-DEL-1001',  # Already exists!
        'instrument_type': 'FDR',
        'issuing_bank': 'HDFC Bank',
        'issuing_branch': 'Sector 15',
        'branch_ifsc': 'HDFC0000002',
        'amount': '500000.00',
        'issue_date': '2024-01-01',
        'maturity_date': '2032-01-01',
    }
    res = api_client.post(url, payload, format='json')
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert 'reference_number' in str(res.data)


# =============================================================================
# 2. INVALID FILE TYPE REJECTED
# =============================================================================

@pytest.mark.django_db
def test_invalid_file_type_rejected(api_client, phase2_setup):
    """Uploading executable or text file must be rejected with 400 Bad Request."""
    api_client.force_authenticate(user=phase2_setup['user_a'])
    fdr_a = phase2_setup['fdr_a']
    url = reverse('instrument-documents', kwargs={'pk': fdr_a.id})

    # Upload disallowed .exe file
    bad_file = SimpleUploadedFile("malware.exe", b"MZ\x90\x00\x03fake-binary", content_type="application/octet-stream")
    res = api_client.post(url, {'file': bad_file, 'document_type': 'FDR_CERTIFICATE'}, format='multipart')
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert 'Invalid file type' in str(res.data)


# =============================================================================
# 3. FILE SIZE LIMIT REJECTED
# =============================================================================

@pytest.mark.django_db
def test_file_size_exceeding_limit_rejected(api_client, phase2_setup, settings):
    """Uploading file exceeding maximum allowed bytes is rejected."""
    settings.MAX_UPLOAD_SIZE_BYTES = 1000  # Set low limit for test
    api_client.force_authenticate(user=phase2_setup['user_a'])
    fdr_a = phase2_setup['fdr_a']
    url = reverse('instrument-documents', kwargs={'pk': fdr_a.id})

    oversized_content = b"%PDF-1.4" + (b"X" * 2000)
    oversized_file = SimpleUploadedFile("big_cert.pdf", oversized_content, content_type="application/pdf")
    res = api_client.post(url, {'file': oversized_file, 'document_type': 'FDR_CERTIFICATE'}, format='multipart')
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert 'exceeds' in str(res.data).lower()


# =============================================================================
# 4. HASH RECORDED & 5. ENCRYPTED FILE NOT READABLE RAW
# =============================================================================

@pytest.mark.django_db
def test_hash_recorded_and_file_encrypted_at_rest(api_client, phase2_setup):
    """
    Verifies that:
    1. The SHA-256 fingerprint matches the original plain bytes.
    2. The raw file stored on disk is encrypted ciphertext (starts with Fernet header and does NOT contain plain text).
    """
    api_client.force_authenticate(user=phase2_setup['user_a'])
    fdr_a = phase2_setup['fdr_a']
    url = reverse('instrument-documents', kwargs={'pk': fdr_a.id})

    plain_content = b"%PDF-1.4 AICTE Fixed Deposit Official Certificate Secret Data 12345"
    expected_hash = hashlib.sha256(plain_content).hexdigest()

    pdf_file = SimpleUploadedFile("deposit_receipt.pdf", plain_content, content_type="application/pdf")
    res = api_client.post(url, {'file': pdf_file, 'document_type': 'FDR_CERTIFICATE'}, format='multipart')
    assert res.status_code == status.HTTP_201_CREATED

    doc_id = res.data['id']
    doc = Document.objects.get(id=doc_id)

    # 1. SHA-256 Hash matches exactly
    assert doc.sha256_hash == expected_hash
    assert doc.is_encrypted is True
    assert doc.storage_path != ""
    assert os.path.exists(doc.storage_path)

    # 2. Raw content on disk is encrypted ciphertext
    with open(doc.storage_path, 'rb') as f:
        raw_disk_bytes = f.read()

    # Must NOT contain original secret text
    assert plain_content not in raw_disk_bytes
    # Must start with Fernet magic token header (Fernet ciphertext format starts with b'gAAAAA')
    assert raw_disk_bytes.startswith(b'gAAAAA')


# =============================================================================
# 6. UNAUTHORIZED DOWNLOAD BLOCKED & 7. AUTHORIZED DOWNLOAD SUCCEEDS
# =============================================================================

@pytest.mark.django_db
def test_unauthorized_download_blocked_and_authorized_succeeds(api_client, phase2_setup):
    """
    Verifies that:
    - Unauthenticated download returns 401.
    - Institution B user attempting to download Institution A's document returns 403 Forbidden.
    - Institution A user can download and receives exact decrypted bytes.
    - Scrutiny Officer can download and receives exact decrypted bytes.
    """
    # First, upload document as Institution A
    api_client.force_authenticate(user=phase2_setup['user_a'])
    fdr_a = phase2_setup['fdr_a']
    url_upload = reverse('instrument-documents', kwargs={'pk': fdr_a.id})

    plain_content = b"%PDF-1.4 Confirmed FDR Document Content for Delhi College"
    pdf_file = SimpleUploadedFile("fdr_cert.pdf", plain_content, content_type="application/pdf")
    upload_res = api_client.post(url_upload, {'file': pdf_file, 'document_type': 'FDR_CERTIFICATE'}, format='multipart')
    doc_id = upload_res.data['id']

    download_url = reverse('secure-document-download', kwargs={'pk': doc_id})

    # Case 1: Unauthenticated
    api_client.force_authenticate(user=None)
    res_unauth = api_client.get(download_url)
    assert res_unauth.status_code == status.HTTP_401_UNAUTHORIZED

    # Case 2: Institution B user (cross-institution download attempt)
    api_client.force_authenticate(user=phase2_setup['user_b'])
    res_cross = api_client.get(download_url)
    assert res_cross.status_code == status.HTTP_403_FORBIDDEN

    # Case 3: Institution A user (Owner)
    api_client.force_authenticate(user=phase2_setup['user_a'])
    res_owner = api_client.get(download_url)
    assert res_owner.status_code == status.HTTP_200_OK
    assert res_owner.content == plain_content
    assert res_owner['Content-Disposition'] == 'attachment; filename="fdr_cert.pdf"'
    assert res_owner['X-Content-Type-Options'] == 'nosniff'

    # Case 4: Scrutiny Officer
    api_client.force_authenticate(user=phase2_setup['officer'])
    res_officer = api_client.get(download_url)
    assert res_officer.status_code == status.HTTP_200_OK
    assert res_officer.content == plain_content

    # Verify audit log was recorded on download
    assert AuditLog.objects.filter(action='DOCUMENT_DOWNLOADED', entity_id=str(doc_id)).exists()


# =============================================================================
# 8. DETECT RE-UPLOAD OF IDENTICAL FILE HASH UNDER DIFFERENT INSTRUMENT
# =============================================================================

@pytest.mark.django_db
def test_detect_reupload_of_identical_file_hash_under_different_instrument(api_client, phase2_setup):
    """
    When an identical file (same SHA-256) is uploaded under a DIFFERENT instrument:
    - Flagged as duplicate.
    - Creates a DISCREPANCY_FLAG remark.
    - Transitions instrument status to Discrepancy.
    - Records DUPLICATE_DOCUMENT_HASH_DETECTED audit event.
    """
    plain_content = b"%PDF-1.4 Identical Certificate Being Reused Fraudulently Across Two Colleges"

    # Upload to Instrument A
    api_client.force_authenticate(user=phase2_setup['user_a'])
    fdr_a = phase2_setup['fdr_a']
    fdr_b = phase2_setup['fdr_b']

    file_a = SimpleUploadedFile("cert_a.pdf", plain_content, content_type="application/pdf")
    res_a = api_client.post(
        reverse('instrument-documents', kwargs={'pk': fdr_a.id}),
        {'file': file_a, 'document_type': 'FDR_CERTIFICATE'},
        format='multipart'
    )
    assert res_a.status_code == status.HTTP_201_CREATED
    assert res_a.data['is_duplicate_hash'] is False

    # Now upload the SAME file bytes to Instrument B (different institution/instrument)
    api_client.force_authenticate(user=phase2_setup['user_b'])
    file_b = SimpleUploadedFile("cert_b_identical.pdf", plain_content, content_type="application/pdf")
    res_b = api_client.post(
        reverse('instrument-documents', kwargs={'pk': fdr_b.id}),
        {'file': file_b, 'document_type': 'FDR_CERTIFICATE'},
        format='multipart'
    )
    assert res_b.status_code == status.HTTP_201_CREATED
    assert res_b.data['is_duplicate_hash'] is True
    assert res_b.data['duplicate_of'] == res_a.data['id']

    # Verify Instrument B is now flagged in Discrepancy
    fdr_b.refresh_from_db()
    assert fdr_b.status == InstrumentStatus.DISCREPANCY
    assert fdr_b.remarks.filter(remark_type='DISCREPANCY_FLAG').exists()
    assert AuditLog.objects.filter(action='DUPLICATE_DOCUMENT_HASH_DETECTED').exists()


# =============================================================================
# 9. DOCUMENT VERSIONING INSTEAD OF OVERWRITING
# =============================================================================

@pytest.mark.django_db
def test_document_versioning_instead_of_overwriting(api_client, phase2_setup):
    """
    Uploading a new file for the same document_type increments version (v1, v2)
    and preserves both documents on disk and in database without overwriting.
    """
    api_client.force_authenticate(user=phase2_setup['user_a'])
    fdr_a = phase2_setup['fdr_a']
    url = reverse('instrument-documents', kwargs={'pk': fdr_a.id})

    # Upload v1
    v1_content = b"%PDF-1.4 Initial Version 1 FDR Certificate"
    f1 = SimpleUploadedFile("cert_v1.pdf", v1_content, content_type="application/pdf")
    res_v1 = api_client.post(url, {'file': f1, 'document_type': 'FDR_CERTIFICATE'}, format='multipart')
    assert res_v1.status_code == status.HTTP_201_CREATED
    assert res_v1.data['version'] == 1
    assert res_v1.data['is_current_version'] is True

    # Upload v2 for same document_type
    v2_content = b"%PDF-1.4 Renewed Version 2 FDR Certificate with Bank Endorsement"
    f2 = SimpleUploadedFile("cert_v2.pdf", v2_content, content_type="application/pdf")
    res_v2 = api_client.post(url, {'file': f2, 'document_type': 'FDR_CERTIFICATE'}, format='multipart')
    assert res_v2.status_code == status.HTTP_201_CREATED
    assert res_v2.data['version'] == 2
    assert res_v2.data['is_current_version'] is True

    # Verify both records exist
    docs = Document.objects.filter(instrument=fdr_a, document_type='FDR_CERTIFICATE').order_by('version')
    assert docs.count() == 2
    doc_v1, doc_v2 = docs[0], docs[1]

    assert doc_v1.version == 1
    assert doc_v1.is_current_version is False  # Marked superseded
    assert doc_v2.version == 2
    assert doc_v2.is_current_version is True

    # Both files exist independently on disk
    assert doc_v1.storage_path != doc_v2.storage_path
    assert os.path.exists(doc_v1.storage_path)
    assert os.path.exists(doc_v2.storage_path)
