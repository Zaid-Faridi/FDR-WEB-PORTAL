import pytest
import io
import pyotp
from datetime import date, timedelta
from django.db import connection
from django.core.exceptions import PermissionDenied, ValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError
from django.utils import timezone
from apps.users.models import User, UserRole
from apps.institutions.models import Institution
from apps.instruments.models import Instrument, InstrumentStatus, InstrumentType
from apps.common.models import AuditEntry, GENESIS_HASH
from apps.common.audit import record_audit_event, verify_audit_hash_chain
from apps.common.validators import ComplexityPasswordValidator
from apps.instruments.storage import scan_uploaded_file

@pytest.fixture
def users_db(db):
    inst = Institution.objects.create(aicte_id="1-TEST-PH7", name="Phase 7 Test Institute", state="Delhi")
    admin = User.objects.create_superuser(
        username="admin_sec",
        email="admin_sec@aicte-india.org",
        password="AdminSecurePassword123!",
        role=UserRole.ADMIN
    )
    officer = User.objects.create_user(
        username="officer_sec",
        email="officer_sec@aicte-india.org",
        password="OfficerPassword123!",
        role=UserRole.SCRUTINY_OFFICER
    )
    approver = User.objects.create_user(
        username="approver_sec",
        email="approver_sec@aicte-india.org",
        password="ApproverPassword123!",
        role=UserRole.APPROVING_AUTHORITY
    )
    institution_user = User.objects.create_user(
        username="inst_sec",
        email="inst_sec@college.edu",
        password="InstPassword123!",
        role=UserRole.INSTITUTION,
        institution=inst
    )
    return {
        "admin": admin,
        "officer": officer,
        "approver": approver,
        "institution": institution_user,
        "inst": inst,
    }

# -------------------------------------------------------------
# 1. APPEND-ONLY & HASH CHAIN AUDIT TESTS
# -------------------------------------------------------------

@pytest.mark.django_db
def test_audit_entry_append_only_orm_prevent_update_and_delete(users_db):
    """Verify ORM blocks updates and deletes on AuditEntry."""
    entry = AuditEntry.objects.create(
        action="TEST_ACTION",
        object_type="Instrument",
        object_id="999",
        actor_username="admin_sec",
        role=UserRole.ADMIN,
        ip_address="127.0.0.1",
    )
    assert entry.id is not None
    assert entry.entry_hash is not None

    # Attempting to update via ORM save() MUST raise PermissionDenied
    entry.action = "TAMPERED_ACTION"
    with pytest.raises(PermissionDenied, match="append-only"):
        entry.save()

    # Attempting to delete via ORM MUST raise PermissionDenied
    with pytest.raises(PermissionDenied, match="append-only"):
        entry.delete()

@pytest.mark.django_db
def test_audit_hash_chain_integrity(users_db):
    """Verify hash chain continuity and verify_audit_hash_chain returns valid."""
    e1 = AuditEntry.objects.create(
        action="FDR_CREATED",
        object_type="Instrument",
        object_id="1",
        actor_username="inst_sec",
        role=UserRole.INSTITUTION,
    )
    e2 = AuditEntry.objects.create(
        action="FDR_STATUS_UPDATED",
        object_type="Instrument",
        object_id="1",
        actor_username="officer_sec",
        role=UserRole.SCRUTINY_OFFICER,
        before_values={"status": "SUBMITTED"},
        after_values={"status": "UNDER_SCRUTINY"},
    )
    e3 = AuditEntry.objects.create(
        action="LOGIN_SUCCESS",
        object_type="User",
        object_id="2",
        actor_username="admin_sec",
        role=UserRole.ADMIN,
    )

    # e2 must point to e1's hash, e3 must point to e2's hash
    assert e2.previous_hash == e1.entry_hash
    assert e3.previous_hash == e2.entry_hash

    # Verification should succeed
    result = verify_audit_hash_chain()
    assert result["valid"] is True
    assert result["total_verified"] >= 3
    assert result["first_broken_id"] is None

@pytest.mark.django_db
def test_audit_hash_chain_tamper_detection(users_db):
    """
    Simulate a malicious database tampering bypass (direct SQL) and verify that
    the hash chain verifier detects the exact broken entry ID.
    """
    e1 = AuditEntry.objects.create(action="EVENT_1", object_type="Instrument", object_id="1", actor_username="inst_sec", role=UserRole.INSTITUTION)
    e2 = AuditEntry.objects.create(action="EVENT_2", object_type="Instrument", object_id="2", actor_username="officer_sec", role=UserRole.SCRUTINY_OFFICER)
    e3 = AuditEntry.objects.create(action="EVENT_3", object_type="Instrument", object_id="3", actor_username="approver_sec", role=UserRole.APPROVING_AUTHORITY)

    # Raw database bypass: drop trigger temporarily to simulate malicious direct database edit
    with connection.cursor() as cursor:
        if connection.vendor == 'postgresql':
            cursor.execute("DROP TRIGGER IF EXISTS trg_auditentry_prevent_tamper ON common_auditentry;")
            cursor.execute("UPDATE common_auditentry SET action = 'TAMPERED_MALICIOUS_EVENT' WHERE id = %s;", [e2.id])
            cursor.execute("""
                CREATE TRIGGER trg_auditentry_prevent_tamper
                BEFORE UPDATE OR DELETE ON common_auditentry
                FOR EACH ROW EXECUTE FUNCTION prevent_audit_tampering();
            """)
        elif connection.vendor == 'sqlite':
            cursor.execute("DROP TRIGGER IF EXISTS trg_auditentry_no_update;")
            cursor.execute("UPDATE common_auditentry SET action = 'TAMPERED_MALICIOUS_EVENT' WHERE id = %s;", [e2.id])

    # Now verify the chain - e2 should be identified as the broken entry
    result = verify_audit_hash_chain()
    assert result["valid"] is False
    assert result["first_broken_id"] == e2.id
    assert "Tampering detected" in result["reason"] or "mismatch" in result["reason"]

@pytest.mark.django_db
def test_verify_chain_admin_endpoint(api_client, users_db):
    """Verify /api/audit/verify-chain/ is restricted to admins and returns chain report."""
    # Institution user forbidden
    api_client.force_authenticate(user=users_db["institution"])
    res = api_client.get("/api/audit/verify-chain/")
    assert res.status_code == 403

    # Officer user forbidden
    api_client.force_authenticate(user=users_db["officer"])
    res = api_client.get("/api/audit/verify-chain/")
    assert res.status_code == 403

    # Admin user allowed
    api_client.force_authenticate(user=users_db["admin"])
    res = api_client.get("/api/audit/verify-chain/")
    assert res.status_code == 200
    data = res.json()
    assert "valid" in data
    assert "total_verified" in data

# -------------------------------------------------------------
# 2. SECURITY: ACCOUNT LOCKOUT & FAILED LOGINS
# -------------------------------------------------------------

@pytest.mark.django_db
def test_account_lockout_after_5_failed_logins(api_client, users_db):
    """Account must lock out after 5 consecutive bad login attempts."""
    user = users_db["officer"]
    assert user.failed_login_attempts == 0
    assert not user.is_locked_out()

    login_url = "/api/auth/token/"

    # 4 failed attempts
    for i in range(4):
        res = api_client.post(login_url, {"username": user.username, "password": "WrongPassword!"})
        assert res.status_code == 401

    user.refresh_from_db()
    assert user.failed_login_attempts == 4
    assert not user.is_locked_out()

    # 5th failed attempt -> locks account
    res = api_client.post(login_url, {"username": user.username, "password": "WrongPassword!"})
    assert res.status_code == 401
    assert "locked" in res.json().get("detail", "").lower()

    user.refresh_from_db()
    assert user.failed_login_attempts == 5
    assert user.is_locked_out()

    # 6th attempt with CORRECT password must still be rejected while locked out
    res = api_client.post(login_url, {"username": user.username, "password": "OfficerPassword123!"})
    assert res.status_code == 401
    assert "locked" in res.json().get("detail", "").lower()

# -------------------------------------------------------------
# 3. SECURITY: TOTP 2FA WORKFLOW
# -------------------------------------------------------------

@pytest.mark.django_db
def test_totp_2fa_setup_and_login_flow(api_client, users_db):
    """Officers/Approvers can enroll TOTP 2FA and login requires TOTP challenge code."""
    officer = users_db["officer"]
    api_client.force_authenticate(user=officer)

    # 1. Setup 2FA endpoint
    setup_res = api_client.get("/api/auth/2fa/setup/")
    assert setup_res.status_code == 200
    secret = setup_res.json()["secret"]
    assert len(secret) > 0

    # 2. Enable with invalid code -> should fail
    bad_enable = api_client.post("/api/auth/2fa/enable/", {"code": "000000"})
    assert bad_enable.status_code == 400

    # 3. Enable with valid TOTP code
    totp = pyotp.TOTP(secret)
    valid_code = totp.now()
    good_enable = api_client.post("/api/auth/2fa/enable/", {"code": valid_code})
    assert good_enable.status_code == 200
    assert good_enable.json()["totp_enabled"] is True

    officer.refresh_from_db()
    assert officer.totp_enabled is True

    # 4. Now attempt login without 2FA code
    api_client.logout()
    login_url = "/api/auth/token/"
    res_no_code = api_client.post(login_url, {
        "username": officer.username,
        "password": "OfficerPassword123!"
    })
    assert res_no_code.status_code == 200
    assert res_no_code.json().get("requires_2fa") is True

    # 5. Login with invalid 2FA code -> 401
    res_bad_code = api_client.post(login_url, {
        "username": officer.username,
        "password": "OfficerPassword123!",
        "totp_code": "999999"
    })
    assert res_bad_code.status_code == 401

    # 6. Login with valid 2FA code -> 200 + tokens
    res_good_code = api_client.post(login_url, {
        "username": officer.username,
        "password": "OfficerPassword123!",
        "totp_code": totp.now()
    })
    assert res_good_code.status_code == 200
    assert "access" in res_good_code.json()
    assert "refresh" in res_good_code.json()

# -------------------------------------------------------------
# 4. SECURITY: FILE SCANNING HOOK
# -------------------------------------------------------------

def test_file_scanning_hook_detects_malicious_and_invalid_files():
    """File scanning hook detects magic byte mismatches and malicious executable headers."""
    # Valid PDF magic bytes (%PDF)
    valid_pdf = io.BytesIO(b"%PDF-1.4 sample safe pdf content")
    scan_uploaded_file(valid_pdf, "document.pdf")

    # Valid JPEG magic bytes (\xFF\xD8\xFF)
    valid_jpeg = io.BytesIO(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00")
    scan_uploaded_file(valid_jpeg, "photo.jpg")

    # Mismatched file: claimed PDF but has ASCII/plain text
    fake_pdf = io.BytesIO(b"Hello world, I am actually a text file")
    with pytest.raises((ValidationError, DRFValidationError), match="does not match its contents|File signature mismatch"):
        scan_uploaded_file(fake_pdf, "invoice.pdf")

    # Executable binary header (Windows MZ header)
    malicious_exe = io.BytesIO(b"MZ\x90\x00\x03\x00\x00\x00")
    with pytest.raises((ValidationError, DRFValidationError), match="Executable binary or script headers"):
        scan_uploaded_file(malicious_exe, "virus.exe")

    # Executable ELF header
    malicious_elf = io.BytesIO(b"\x7fELF\x02\x01\x01\x00")
    with pytest.raises((ValidationError, DRFValidationError), match="Executable binary or script headers"):
        scan_uploaded_file(malicious_elf, "malware.bin")

    # Script header (PHP / bash)
    malicious_php = io.BytesIO(b"<?php system($_GET['cmd']); ?>")
    with pytest.raises((ValidationError, DRFValidationError), match="Malicious embedded script"):
        scan_uploaded_file(malicious_php, "webshell.php")

# -------------------------------------------------------------
# 5. SECURITY: FIELD-LEVEL BANK DETAILS MASKING
# -------------------------------------------------------------

@pytest.mark.django_db
def test_field_level_bank_masking(api_client, users_db):
    """
    IFSC details masked when mask=true or for restricted contexts.
    Institutions viewing with ?mask=true view masked IFSC (e.g. SBIN***).
    """
    inst = users_db["inst"]
    instrument = Instrument.objects.create(
        institution=inst,
        instrument_type=InstrumentType.FDR,
        reference_number="FDR-PH7-MASK",
        issuing_bank="State Bank of India",
        issuing_branch="Connaught Place",
        branch_ifsc="SBIN0000691",
        amount=1500000.00,
        issue_date=date(2024, 1, 1),
        maturity_date=date(2032, 1, 1),
        status=InstrumentStatus.ACTIVE,
        created_by=users_db["institution"]
    )

    # When accessed with mask=true
    api_client.force_authenticate(user=users_db["institution"])
    res = api_client.get(f"/api/instruments/{instrument.id}/?mask=true")
    assert res.status_code == 200
    data = res.json()
    assert data["branch_ifsc"] == "SBIN*******"
    assert data["is_bank_details_masked"] is True

    # When accessed by Officer / Approver / Admin without mask query, IFSC is preserved
    api_client.force_authenticate(user=users_db["officer"])
    res_officer = api_client.get(f"/api/instruments/{instrument.id}/")
    assert res_officer.status_code == 200
    assert res_officer.json()["branch_ifsc"] == "SBIN0000691"

# -------------------------------------------------------------
# 6. SECURITY: PASSWORD POLICY COMPLEXITY
# -------------------------------------------------------------

def test_password_complexity_validator():
    """Password complexity requires min 10 chars, upper, lower, digit, and special char."""
    validator = ComplexityPasswordValidator()

    # Too short (< 10)
    with pytest.raises(ValidationError, match="at least 10 characters"):
        validator.validate("Short1!")

    # Missing uppercase
    with pytest.raises(ValidationError, match="uppercase"):
        validator.validate("lowercase123!@#")

    # Missing lowercase
    with pytest.raises(ValidationError, match="lowercase"):
        validator.validate("UPPERCASE123!@#")

    # Missing digit
    with pytest.raises(ValidationError, match="digit"):
        validator.validate("NoDigitsHere!@#")

    # Missing special char
    with pytest.raises(ValidationError, match="special character"):
        validator.validate("NoSpecialChar12345")

    # Valid password passes without raising
    validator.validate("StrongP@ssw0rd2026!")

# -------------------------------------------------------------
# 7. SECURITY: HEADERS AND CSP
# -------------------------------------------------------------

@pytest.mark.django_db
def test_security_headers_and_csp(api_client):
    """Verify responses include standard security headers and Content-Security-Policy."""
    res = api_client.get("/api/health/")
    assert res.status_code == 200
    headers = res.headers

    assert "Content-Security-Policy" in headers
    assert "default-src 'self'" in headers["Content-Security-Policy"]
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert "camera=()" in headers.get("Permissions-Policy", "")

# -------------------------------------------------------------
# 8. ACCESS-CONTROL BYPASS ATTEMPTS & PERMISSION DENIAL AUDIT
# -------------------------------------------------------------

@pytest.mark.django_db
def test_access_control_bypass_logged_in_audit(api_client, users_db):
    """
    Unauthorized action by an unprivileged role is denied (403) AND
    logged as PERMISSION_DENIED in AuditEntry.
    """
    initial_denial_count = AuditEntry.objects.filter(action="PERMISSION_DENIED").count()

    # Institution user attempts to call admin verify-chain endpoint
    api_client.force_authenticate(user=users_db["institution"])
    res = api_client.get("/api/audit/verify-chain/")
    assert res.status_code == 403

    # Check that a PERMISSION_DENIED audit entry was logged
    denials = AuditEntry.objects.filter(action="PERMISSION_DENIED")
    assert denials.count() == initial_denial_count + 1
    latest_denial = denials.order_by("-id").first()
    assert latest_denial.actor_username == "inst_sec"
    assert latest_denial.role == UserRole.INSTITUTION
