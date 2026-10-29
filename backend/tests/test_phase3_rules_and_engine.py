import pytest
from datetime import date, timedelta
from decimal import Decimal
from django.urls import reverse
from rest_framework import status

from apps.users.models import User, UserRole
from apps.institutions.models import Institution
from apps.instruments.models import (
    Instrument,
    InstrumentType,
    InstrumentStatus,
    Document,
    FieldSource,
    Discrepancy,
    DiscrepancySeverity,
)
from apps.common.models import DataProvenanceSource
from apps.bank_adapters.factory import get_bank_adapter
from apps.bank_adapters.mock_adapter import MockBankAdapter
from apps.instruments.engine import (
    DiscrepancyEngine,
    calculate_trust_score,
    run_discrepancy_check,
    get_required_deposit_for_institution,
)
from apps.instruments.ocr import (
    extract_fdr_fields_from_text,
    compare_ocr_vs_typed,
    normalize_date_string,
    normalize_amount_string,
)


@pytest.fixture
def phase3_setup(db):
    inst_eng = Institution.objects.create(
        aicte_id="1-ENG-001",
        name="Global College of Engineering & Technology",
        institution_type="Engineering & Technology",
        state="Delhi"
    )
    inst_poly = Institution.objects.create(
        aicte_id="1-POLY-002",
        name="Apex Polytechnic Institute",
        institution_type="Polytechnic",
        state="Haryana"
    )
    inst_tech_campus = Institution.objects.create(
        aicte_id="1-CAMPUS-003",
        name="Integrated Technical Campus",
        institution_type="Technical Campus",
        state="Karnataka"
    )

    officer = User.objects.create_user(
        username="officer_p3",
        password="Password@123",
        role=UserRole.SCRUTINY_OFFICER
    )
    inst_user = User.objects.create_user(
        username="inst_user_p3",
        password="Password@123",
        role=UserRole.INSTITUTION,
        institution=inst_eng
    )

    # Standard clean FDR matching required deposit for Engineering (₹50,00,000)
    instrument_clean = Instrument.objects.create(
        institution=inst_eng,
        instrument_type=InstrumentType.FDR,
        reference_number="FDR-CLEAN-2026-001",
        issuing_bank="State Bank of India",
        issuing_branch="Connaught Place, New Delhi",
        branch_ifsc="SBIN0000001",
        amount=Decimal("5000000.00"),
        issue_date=date(2024, 1, 15),
        maturity_date=date(2034, 1, 15),
        lien_in_favour_of_aicte=True,
        joint_holder_name="Global College and Member Secretary AICTE",
        status=InstrumentStatus.SUBMITTED,
        created_by=inst_user
    )

    # Attach required documents to instrument_clean
    doc_fdr = Document.objects.create(
        instrument=instrument_clean,
        document_type='FDR_CERTIFICATE',
        file_name='fdr_scan.pdf',
        sha256_hash='a' * 64,
        is_current_version=True,
        storage_path='/app/secure_vault/test_fdr.enc'
    )
    doc_lien = Document.objects.create(
        instrument=instrument_clean,
        document_type='BANK_CONFIRMATION',
        file_name='bank_confirmation.pdf',
        sha256_hash='b' * 64,
        is_current_version=True,
        storage_path='/app/secure_vault/test_lien.enc'
    )

    return {
        'inst_eng': inst_eng,
        'inst_poly': inst_poly,
        'inst_tech_campus': inst_tech_campus,
        'officer': officer,
        'inst_user': inst_user,
        'clean_instrument': instrument_clean,
        'doc_fdr': doc_fdr,
        'doc_lien': doc_lien,
    }


# =============================================================================
# 1. Bank Verification Adapter & Mock Edge Cases Tests
# =============================================================================

def test_mock_bank_adapter_seeded_registry_and_edge_cases():
    adapter = get_bank_adapter()
    assert isinstance(adapter, MockBankAdapter)
    assert adapter.is_mock is True
    assert "MOCK" in adapter.adapter_name

    # Edge Case 1: Match
    res_match = adapter.verify("FDR-SBI-2026-001", "State Bank of India")
    assert res_match["status"] == "CONFIRMED"
    assert res_match["is_mock"] is True
    assert "MOCK" in res_match["adapter_name"]
    assert res_match["confirmed_amount"] == 10000000.00
    assert res_match["lien_marked"] is True
    assert len(res_match["discrepancies"]) == 0

    # Edge Case 2: Amount Mismatch
    res_amt = adapter.verify("FDR-PNB-MISMATCH-AMT", "Punjab National Bank")
    assert res_amt["status"] == "DISCREPANCY_DETECTED"
    assert res_amt["confirmed_amount"] == 2500000.00
    assert any("Amount mismatch" in d for d in res_amt["discrepancies"])

    # Edge Case 3: Date Mismatch
    res_date = adapter.verify("FDR-HDFC-MISMATCH-DATE", "HDFC Bank")
    assert res_date["status"] == "DISCREPANCY_DETECTED"
    assert res_date["confirmed_maturity_date"] == "2028-01-01"
    assert any("Maturity date mismatch" in d for d in res_date["discrepancies"])

    # Edge Case 4: Not Found
    res_404 = adapter.verify("FDR-UNKNOWN-404", "Bank of Baroda")
    assert res_404["status"] == "NOT_FOUND"
    assert res_404["confirmed_amount"] is None
    assert any("not found" in d.lower() for d in res_404["discrepancies"])


# =============================================================================
# 2. OCR Text Extraction and Mismatch Detection Tests
# =============================================================================

def test_ocr_field_extraction_from_text():
    sample_text = """
    STATE BANK OF INDIA
    FIXED DEPOSIT RECEIPT
    Receipt No: FDR-SBI-2026-999
    Issue Date: 15/01/2024
    Maturity Date: 15/01/2034
    Amount: ₹ 50,00,000.00
    Lien marked in favor of Member Secretary AICTE New Delhi
    """
    extracted = extract_fdr_fields_from_text(sample_text)
    assert extracted["bank_name"] == "State Bank of India"
    assert extracted["reference_number"] == "FDR-SBI-2026-999"
    assert extracted["amount"] == 5000000.00
    assert extracted["issue_date"] == "2024-01-15"
    assert extracted["maturity_date"] == "2034-01-15"
    assert "AICTE" in extracted["joint_holder"]


def test_ocr_date_and_amount_normalization():
    assert normalize_date_string("15/01/2024") == "2024-01-15"
    assert normalize_date_string("15-01-2024") == "2024-01-15"
    assert normalize_date_string("2024-01-15") == "2024-01-15"
    assert normalize_amount_string("₹ 1,00,00,000.00") == 10000000.0
    assert normalize_amount_string("Rs. 5000000") == 5000000.0


def test_ocr_vs_typed_mismatch_detection():
    ocr_data = {
        "success": True,
        "reference_number": "FDR-1111",
        "bank_name": "State Bank of India",
        "amount": 5000000.0,
        "issue_date": "2024-01-15",
        "maturity_date": "2034-01-15",
    }
    typed_matching = {
        "reference_number": "FDR-1111",
        "issuing_bank": "State Bank of India",
        "amount": 5000000.0,
        "issue_date": "2024-01-15",
        "maturity_date": "2034-01-15",
    }
    # No mismatch
    assert len(compare_ocr_vs_typed(ocr_data, typed_matching)) == 0

    # Amount & Date mismatch
    typed_diff = {
        "reference_number": "FDR-1111",
        "issuing_bank": "State Bank of India",
        "amount": 3500000.0,  # typed 35L vs OCR 50L
        "issue_date": "2024-01-15",
        "maturity_date": "2030-01-15",  # typed 2030 vs OCR 2034
    }
    diffs = compare_ocr_vs_typed(ocr_data, typed_diff)
    diff_fields = [d["field"] for d in diffs]
    assert "amount" in diff_fields
    assert "maturity_date" in diff_fields


# =============================================================================
# 3. Discrepancy Engine Rules Unit Tests
# =============================================================================

@pytest.mark.django_db
def test_rule_duplicate_fdr_number(phase3_setup):
    """Rule 1: Duplicate FDR Number (CRITICAL)"""
    inst = phase3_setup['clean_instrument']
    # An incoming/unpersisted instrument with the same reference number as an existing instrument
    dup_inst = Instrument(
        institution=phase3_setup['inst_poly'],
        instrument_type=InstrumentType.FDR,
        reference_number=inst.reference_number,  # duplicate
        issuing_bank="Punjab National Bank",
        issuing_branch="Camp Branch",
        branch_ifsc="PUNB0000001",
        amount=Decimal("5000000.00"),
        issue_date=date(2024, 1, 1),
        maturity_date=date(2034, 1, 1),
    )
    discrepancies = DiscrepancyEngine.evaluate(dup_inst)
    codes = [d["rule_code"] for d in discrepancies]
    assert "DUPLICATE_FDR_NUMBER" in codes
    dup_flag = next(d for d in discrepancies if d["rule_code"] == "DUPLICATE_FDR_NUMBER")
    assert dup_flag["severity"] == DiscrepancySeverity.CRITICAL


@pytest.mark.django_db
def test_rule_duplicate_document_hash(phase3_setup):
    """Rule 2: Duplicate Document Hash (CRITICAL)"""
    inst = phase3_setup['clean_instrument']
    doc = inst.documents.first()
    doc.is_duplicate_hash = True
    doc.save()

    discrepancies = DiscrepancyEngine.evaluate(inst)
    codes = [d["rule_code"] for d in discrepancies]
    assert "DUPLICATE_DOCUMENT_HASH" in codes
    dup_flag = next(d for d in discrepancies if d["rule_code"] == "DUPLICATE_DOCUMENT_HASH")
    assert dup_flag["severity"] == DiscrepancySeverity.CRITICAL


@pytest.mark.django_db
def test_rule_maturity_before_issue(phase3_setup):
    """Rule 3: Maturity Date on or before Issue Date (CRITICAL)"""
    inst = phase3_setup['clean_instrument']
    inst.maturity_date = inst.issue_date - timedelta(days=10)
    inst.save()

    discrepancies = DiscrepancyEngine.evaluate(inst)
    codes = [d["rule_code"] for d in discrepancies]
    assert "MATURITY_BEFORE_ISSUE" in codes
    flag = next(d for d in discrepancies if d["rule_code"] == "MATURITY_BEFORE_ISSUE")
    assert flag["severity"] == DiscrepancySeverity.CRITICAL


@pytest.mark.django_db
def test_rule_amount_mismatch_vs_bank(phase3_setup):
    """Rule 4: Amount Mismatch with Bank Records (HIGH)"""
    inst = phase3_setup['clean_instrument']
    bank_resp = {
        "status": "CONFIRMED",
        "confirmed_amount": 4000000.00,  # 40L vs claimed 50L
        "confirmed_maturity_date": str(inst.maturity_date),
        "lien_marked": True,
    }
    discrepancies = DiscrepancyEngine.evaluate(inst, bank_response=bank_resp)
    codes = [d["rule_code"] for d in discrepancies]
    assert "AMOUNT_MISMATCH_BANK" in codes
    flag = next(d for d in discrepancies if d["rule_code"] == "AMOUNT_MISMATCH_BANK")
    assert flag["severity"] == DiscrepancySeverity.HIGH
    assert flag["details"]["claimed_amount"] == 5000000.0
    assert flag["details"]["bank_confirmed_amount"] == 4000000.0


@pytest.mark.django_db
def test_rule_amount_below_institution_category_minimum(phase3_setup):
    """Rule 5: Amount below configured required deposit for the institution category (HIGH)"""
    # Technical Campus norm is ₹1.00 Crore (100 Lakhs)
    campus_inst = Instrument.objects.create(
        institution=phase3_setup['inst_tech_campus'],
        instrument_type=InstrumentType.FDR,
        reference_number="FDR-CAMPUS-LOW",
        issuing_bank="State Bank of India",
        issuing_branch="Main Branch",
        branch_ifsc="SBIN0000001",
        amount=Decimal("6000000.00"),  # 60 Lakhs, shortfall of 40 Lakhs
        issue_date=date(2024, 1, 1),
        maturity_date=date(2034, 1, 1),
        lien_in_favour_of_aicte=True,
    )
    # Norm check function
    norm = get_required_deposit_for_institution(phase3_setup['inst_tech_campus'])
    assert norm == Decimal("10000000.00")

    discrepancies = DiscrepancyEngine.evaluate(campus_inst)
    codes = [d["rule_code"] for d in discrepancies]
    assert "AMOUNT_BELOW_MINIMUM" in codes
    flag = next(d for d in discrepancies if d["rule_code"] == "AMOUNT_BELOW_MINIMUM")
    assert flag["severity"] == DiscrepancySeverity.HIGH
    assert flag["details"]["shortfall"] == 4000000.0


@pytest.mark.django_db
def test_rule_missing_lien_letter(phase3_setup):
    """Rule 6: Missing Lien Letter / AICTE Lien Not Marked (HIGH)"""
    inst = phase3_setup['clean_instrument']
    inst.lien_in_favour_of_aicte = False
    inst.save()

    discrepancies = DiscrepancyEngine.evaluate(inst)
    codes = [d["rule_code"] for d in discrepancies]
    assert "MISSING_LIEN" in codes
    flag = next(d for d in discrepancies if d["rule_code"] == "MISSING_LIEN")
    assert flag["severity"] == DiscrepancySeverity.HIGH


@pytest.mark.django_db
def test_rule_missing_mandatory_documents(phase3_setup):
    """Rule 7: Missing Mandatory Documents (HIGH)"""
    inst = phase3_setup['clean_instrument']
    # Delete FDR certificate scan
    inst.documents.filter(document_type='FDR_CERTIFICATE').delete()

    discrepancies = DiscrepancyEngine.evaluate(inst)
    codes = [d["rule_code"] for d in discrepancies]
    assert "MISSING_MANDATORY_DOCS" in codes
    flag = next(d for d in discrepancies if d["rule_code"] == "MISSING_MANDATORY_DOCS")
    assert flag["severity"] == DiscrepancySeverity.HIGH


@pytest.mark.django_db
def test_rule_unreadable_or_invalid_dates(phase3_setup):
    """Rule 8: Unreadable or Invalid Dates (MEDIUM)"""
    inst = phase3_setup['clean_instrument']
    # Issue date in the future
    inst.issue_date = date.today() + timedelta(days=30)
    inst.save()

    discrepancies = DiscrepancyEngine.evaluate(inst)
    codes = [d["rule_code"] for d in discrepancies]
    assert "INVALID_DATES" in codes
    flag = next(d for d in discrepancies if d["rule_code"] == "INVALID_DATES")
    assert flag["severity"] == DiscrepancySeverity.MEDIUM


@pytest.mark.django_db
def test_rule_date_mismatch_vs_bank(phase3_setup):
    """Rule 9: Date mismatch vs bank (HIGH)"""
    inst = phase3_setup['clean_instrument']
    bank_resp = {
        "status": "CONFIRMED",
        "confirmed_amount": float(inst.amount),
        "confirmed_maturity_date": "2029-01-15",  # 5 years earlier than claimed 2034
        "lien_marked": True,
    }
    discrepancies = DiscrepancyEngine.evaluate(inst, bank_response=bank_resp)
    codes = [d["rule_code"] for d in discrepancies]
    assert "DATE_MISMATCH_BANK" in codes
    flag = next(d for d in discrepancies if d["rule_code"] == "DATE_MISMATCH_BANK")
    assert flag["severity"] == DiscrepancySeverity.HIGH


@pytest.mark.django_db
def test_rule_bank_not_found(phase3_setup):
    """Rule 10: Bank record not found (CRITICAL)"""
    inst = phase3_setup['clean_instrument']
    bank_resp = {
        "status": "NOT_FOUND",
        "discrepancies": ["FDR number not found in issuing bank CBS."],
    }
    discrepancies = DiscrepancyEngine.evaluate(inst, bank_response=bank_resp)
    codes = [d["rule_code"] for d in discrepancies]
    assert "BANK_NOT_FOUND" in codes
    flag = next(d for d in discrepancies if d["rule_code"] == "BANK_NOT_FOUND")
    assert flag["severity"] == DiscrepancySeverity.CRITICAL


@pytest.mark.django_db
def test_rule_ocr_vs_typed_mismatch(phase3_setup):
    """Rule 11: OCR vs Typed Mismatch (MEDIUM)"""
    inst = phase3_setup['clean_instrument']
    ocr_mismatched = {
        "success": True,
        "reference_number": "FDR-DIFFERENT-999",
        "bank_name": "State Bank of India",
        "amount": 2500000.0,
        "issue_date": str(inst.issue_date),
        "maturity_date": str(inst.maturity_date),
    }
    discrepancies = DiscrepancyEngine.evaluate(inst, ocr_data=ocr_mismatched)
    codes = [d["rule_code"] for d in discrepancies]
    assert "OCR_TYPED_MISMATCH" in codes
    flag = next(d for d in discrepancies if d["rule_code"] == "OCR_TYPED_MISMATCH")
    assert flag["severity"] == DiscrepancySeverity.MEDIUM


# =============================================================================
# 4. Trust Score Calculation Tests
# =============================================================================

@pytest.mark.django_db
def test_trust_score_calculation_clean_instrument(phase3_setup):
    inst = phase3_setup['clean_instrument']
    # Fully clean instrument with bank confirmation and docs
    FieldSource.objects.create(
        instrument=inst, field_name='amount', field_value=str(inst.amount),
        value_source=DataProvenanceSource.BANK_CONFIRMED, is_confirmed=True
    )
    FieldSource.objects.create(
        instrument=inst, field_name='maturity_date', field_value=str(inst.maturity_date),
        value_source=DataProvenanceSource.BANK_CONFIRMED, is_confirmed=True
    )
    FieldSource.objects.create(
        instrument=inst, field_name='lien_in_favour_of_aicte', field_value='True',
        value_source=DataProvenanceSource.BANK_CONFIRMED, is_confirmed=True
    )

    score = calculate_trust_score(inst, unresolved_discrepancies=[], bank_confirmed=True)
    assert score >= 90  # 40 (bank) + 40 (discrepancy clean) + 20 (docs) = 100


@pytest.mark.django_db
def test_trust_score_penalizes_unresolved_discrepancies(phase3_setup):
    inst = phase3_setup['clean_instrument']
    crit_disc = Discrepancy(severity=DiscrepancySeverity.CRITICAL)
    high_disc = Discrepancy(severity=DiscrepancySeverity.HIGH)

    score_penalized = calculate_trust_score(
        inst,
        unresolved_discrepancies=[crit_disc, high_disc],
        bank_confirmed=False
    )
    # 10 baseline bank - 20 (crit) - 10 (high) + 20 (docs) = 30
    assert score_penalized <= 40


# =============================================================================
# 5. Officer Scrutiny Workflow & Discrepancy Resolution API Tests
# =============================================================================

@pytest.mark.django_db
def test_officer_can_resolve_discrepancy(client, phase3_setup):
    from rest_framework.test import APIClient
    api = APIClient()
    api.force_authenticate(user=phase3_setup['officer'])

    inst = phase3_setup['clean_instrument']
    disc = Discrepancy.objects.create(
        instrument=inst,
        rule_code="AMOUNT_BELOW_MINIMUM",
        severity=DiscrepancySeverity.HIGH,
        title="Deposit Shortfall",
        description="Amount is below regulatory category norm.",
        is_resolved=False
    )
    inst.status = InstrumentStatus.DISCREPANCY
    inst.save()

    resolve_url = reverse('instrument-resolve-discrepancy', kwargs={'pk': inst.pk})
    res = api.post(resolve_url, {
        'discrepancy_id': disc.id,
        'resolution_note': 'Exemption granted under AICTE special regional concession order #2026/09.'
    })
    assert res.status_code == status.HTTP_200_OK
    assert res.data['status'] == InstrumentStatus.UNDER_SCRUTINY

    disc.refresh_from_db()
    assert disc.is_resolved is True
    assert disc.resolved_by == phase3_setup['officer']
    assert "Exemption granted" in disc.resolution_note


@pytest.mark.django_db
def test_officer_mark_verified_blocked_by_critical_discrepancy(client, phase3_setup):
    from rest_framework.test import APIClient
    api = APIClient()
    api.force_authenticate(user=phase3_setup['officer'])

    inst = phase3_setup['clean_instrument']
    Discrepancy.objects.create(
        instrument=inst,
        rule_code="DUPLICATE_FDR_NUMBER",
        severity=DiscrepancySeverity.CRITICAL,
        title="Duplicate FDR Number",
        description="FDR registered to another college.",
        is_resolved=False
    )

    verify_url = reverse('instrument-mark-verified', kwargs={'pk': inst.pk})
    res = api.post(verify_url, {'notes': 'Attempting verification'})
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "CRITICAL" in str(res.data)
