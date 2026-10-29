"""
AICTE FDR Management Portal - Rule-Based Discrepancy & Trust Score Engine
Evaluates compliance against regulatory norms, banking CBS responses, and document scans.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Dict, Any, List, Optional
import logging

from apps.instruments.models import (
    Instrument,
    InstrumentStatus,
    Document,
    FieldSource,
    Discrepancy,
    DiscrepancySeverity,
)
from apps.common.models import DataProvenanceSource
from apps.common.audit import record_audit_event

logger = logging.getLogger('aicte.engine')

# Mandatory deposit minimums by institution category under AICTE Approval Process Handbook (APH)
INSTITUTION_CATEGORY_DEPOSIT_NORMS: Dict[str, Decimal] = {
    "Technical Campus": Decimal("10000000.00"),          # ₹1.00 Crore
    "Multi-Disciplinary": Decimal("10000000.00"),        # ₹1.00 Crore
    "Engineering & Technology": Decimal("5000000.00"),   # ₹50 Lakhs
    "Engineering College": Decimal("5000000.00"),        # ₹50 Lakhs
    "Management": Decimal("3500000.00"),                 # ₹35 Lakhs
    "MBA": Decimal("3500000.00"),                        # ₹35 Lakhs
    "Pharmacy": Decimal("3500000.00"),                   # ₹35 Lakhs
    "Architecture": Decimal("3500000.00"),               # ₹35 Lakhs
    "Polytechnic": Decimal("2500000.00"),                # ₹25 Lakhs
    "Diploma": Decimal("2500000.00"),                    # ₹25 Lakhs
    "Default": Decimal("3500000.00"),                    # ₹35 Lakhs
}


def get_required_deposit_for_institution(institution) -> Decimal:
    """
    Looks up the required minimum deposit amount for an institution's category.
    """
    if not institution:
        return INSTITUTION_CATEGORY_DEPOSIT_NORMS["Default"]
    itype = getattr(institution, 'institution_type', '')
    for cat, norm in INSTITUTION_CATEGORY_DEPOSIT_NORMS.items():
        if cat.lower() in itype.lower():
            return norm
    return INSTITUTION_CATEGORY_DEPOSIT_NORMS["Default"]


class DiscrepancyEngine:
    """
    Evaluates regulatory compliance rules for an Instrument.
    Produces structured flags with severity ratings:
    CRITICAL, HIGH, MEDIUM, LOW.
    """

    @classmethod
    def evaluate(
        cls,
        instrument: Instrument,
        bank_response: Optional[Dict[str, Any]] = None,
        ocr_data: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Runs all compliance rules against the instrument.
        Returns a list of structured discrepancy dictionaries.
        """
        discrepancies: List[Dict[str, Any]] = []

        # -------------------------------------------------------------
        # Rule 1: Duplicate FDR Number (CRITICAL)
        # -------------------------------------------------------------
        dup_qs = Instrument.objects.filter(
            reference_number__iexact=instrument.reference_number
        ).exclude(pk=instrument.pk)
        if dup_qs.exists():
            conflicting = list(dup_qs.values_list('reference_number', 'institution__name'))
            discrepancies.append({
                "rule_code": "DUPLICATE_FDR_NUMBER",
                "severity": DiscrepancySeverity.CRITICAL,
                "title": "Duplicate FDR Reference Number Detected",
                "description": f"FDR number '{instrument.reference_number}' is already registered in the portal under another record.",
                "details": {"conflicts": conflicting},
            })

        # -------------------------------------------------------------
        # Rule 2: Duplicate Document Hash (CRITICAL)
        # -------------------------------------------------------------
        if instrument.pk:
            has_duplicate_hash = instrument.documents.filter(is_duplicate_hash=True).exists()
            if has_duplicate_hash:
                dup_docs = list(instrument.documents.filter(is_duplicate_hash=True).values('id', 'file_name', 'sha256_hash'))
                discrepancies.append({
                    "rule_code": "DUPLICATE_DOCUMENT_HASH",
                    "severity": DiscrepancySeverity.CRITICAL,
                    "title": "Duplicate Document Hash (Cross-Instrument Re-upload)",
                    "description": "One or more documents uploaded for this instrument have identical cryptographic SHA-256 fingerprints to documents from another instrument.",
                    "details": {"duplicate_documents": dup_docs},
                })

        # -------------------------------------------------------------
        # Rule 3: Maturity Before Issue (CRITICAL)
        # -------------------------------------------------------------
        if instrument.issue_date and instrument.maturity_date:
            if instrument.maturity_date <= instrument.issue_date:
                discrepancies.append({
                    "rule_code": "MATURITY_BEFORE_ISSUE",
                    "severity": DiscrepancySeverity.CRITICAL,
                    "title": "Invalid Term: Maturity Date is on or before Issue Date",
                    "description": f"Claimed maturity date ({instrument.maturity_date}) cannot be on or prior to the issue date ({instrument.issue_date}).",
                    "details": {
                        "issue_date": str(instrument.issue_date),
                        "maturity_date": str(instrument.maturity_date),
                    },
                })

        # -------------------------------------------------------------
        # Rule 4: Bank Record Not Found (CRITICAL)
        # -------------------------------------------------------------
        if bank_response:
            b_status = bank_response.get("status")
            if b_status == "NOT_FOUND":
                discrepancies.append({
                    "rule_code": "BANK_NOT_FOUND",
                    "severity": DiscrepancySeverity.CRITICAL,
                    "title": "FDR Not Found in Bank CBS Records",
                    "description": f"Issuing bank '{instrument.issuing_bank}' reported no record for reference '{instrument.reference_number}'.",
                    "details": bank_response,
                })

        # -------------------------------------------------------------
        # Rule 5: Amount Mismatch vs Bank (HIGH)
        # -------------------------------------------------------------
        if bank_response and bank_response.get("confirmed_amount") is not None:
            bank_amt = Decimal(str(bank_response["confirmed_amount"]))
            inst_amt = Decimal(str(instrument.amount))
            if abs(bank_amt - inst_amt) > Decimal("0.01"):
                discrepancies.append({
                    "rule_code": "AMOUNT_MISMATCH_BANK",
                    "severity": DiscrepancySeverity.HIGH,
                    "title": "Amount Mismatch with Bank Records",
                    "description": f"Institution claimed deposit of ₹{inst_amt:,.2f}, but issuing bank confirmed ₹{bank_amt:,.2f}.",
                    "details": {
                        "claimed_amount": float(inst_amt),
                        "bank_confirmed_amount": float(bank_amt),
                        "variance": float(bank_amt - inst_amt),
                    },
                })

        # -------------------------------------------------------------
        # Rule 6: Amount Below Category Minimum Norm (HIGH)
        # -------------------------------------------------------------
        inst_obj = getattr(instrument, 'institution', None)
        required_norm = get_required_deposit_for_institution(inst_obj)
        if Decimal(str(instrument.amount)) < required_norm:
            shortfall = required_norm - Decimal(str(instrument.amount))
            cat_name = getattr(inst_obj, 'institution_type', 'General')
            discrepancies.append({
                "rule_code": "AMOUNT_BELOW_MINIMUM",
                "severity": DiscrepancySeverity.HIGH,
                "title": "Deposit Below AICTE Regulatory Minimum",
                "description": f"Deposit amount of ₹{instrument.amount:,.2f} is below the mandatory minimum of ₹{required_norm:,.2f} required for '{cat_name}'. Shortfall: ₹{shortfall:,.2f}.",
                "details": {
                    "claimed_amount": float(instrument.amount),
                    "required_minimum": float(required_norm),
                    "shortfall": float(shortfall),
                    "institution_category": cat_name,
                },
            })

        # -------------------------------------------------------------
        # Rule 7: Missing Lien Letter / AICTE Lien Not Marked (HIGH)
        # -------------------------------------------------------------
        lien_flag_missing = not instrument.lien_in_favour_of_aicte
        bank_lien_missing = (bank_response and bank_response.get("lien_marked") is False)
        docs = list(instrument.documents.all()) if instrument.pk else []
        has_lien_doc = any(d.document_type in ['BANK_CONFIRMATION', 'JOINT_PLEDGE_DEED'] for d in docs)

        if lien_flag_missing or bank_lien_missing or not has_lien_doc:
            reasons = []
            if lien_flag_missing:
                reasons.append("Lien flag is not set in favour of AICTE")
            if bank_lien_missing:
                reasons.append("Bank CBS confirms no lien is registered in favor of AICTE")
            if not has_lien_doc:
                reasons.append("Missing Bank Confirmation Letter or Joint Pledge Deed")

            discrepancies.append({
                "rule_code": "MISSING_LIEN",
                "severity": DiscrepancySeverity.HIGH,
                "title": "AICTE Lien Incomplete or Missing",
                "description": "; ".join(reasons) + ".",
                "details": {
                    "lien_in_favour_of_aicte": instrument.lien_in_favour_of_aicte,
                    "bank_lien_marked": bank_response.get("lien_marked") if bank_response else None,
                    "has_lien_document": has_lien_doc,
                },
            })

        # -------------------------------------------------------------
        # Rule 8: Missing Mandatory Documents (HIGH)
        # -------------------------------------------------------------
        has_fdr_scan = any(d.document_type == 'FDR_CERTIFICATE' for d in docs)
        if not docs or not has_fdr_scan:
            discrepancies.append({
                "rule_code": "MISSING_MANDATORY_DOCS",
                "severity": DiscrepancySeverity.HIGH,
                "title": "Mandatory Document Missing",
                "description": "FDR Certificate scan has not been uploaded for this instrument.",
                "details": {"total_documents": len(docs), "has_fdr_scan": has_fdr_scan},
            })

        # -------------------------------------------------------------
        # Rule 9: Date Mismatch vs Bank (HIGH)
        # -------------------------------------------------------------
        if bank_response and bank_response.get("confirmed_maturity_date"):
            bank_mat = str(bank_response["confirmed_maturity_date"])
            inst_mat = str(instrument.maturity_date)
            if bank_mat != inst_mat:
                discrepancies.append({
                    "rule_code": "DATE_MISMATCH_BANK",
                    "severity": DiscrepancySeverity.HIGH,
                    "title": "Maturity Date Mismatch with Bank Records",
                    "description": f"Institution claimed maturity date {inst_mat}, but issuing bank records confirm maturity date {bank_mat}.",
                    "details": {
                        "claimed_maturity_date": inst_mat,
                        "bank_confirmed_maturity_date": bank_mat,
                    },
                })

        # -------------------------------------------------------------
        # Rule 10: Unreadable or Invalid Dates (MEDIUM)
        # -------------------------------------------------------------
        today = date.today()
        if instrument.issue_date:
            if instrument.issue_date > today:
                discrepancies.append({
                    "rule_code": "INVALID_DATES",
                    "severity": DiscrepancySeverity.MEDIUM,
                    "title": "Issue Date is in the Future",
                    "description": f"Issue date ({instrument.issue_date}) cannot be in the future.",
                    "details": {"issue_date": str(instrument.issue_date), "today": str(today)},
                })
        if instrument.issue_date and instrument.maturity_date:
            days = (instrument.maturity_date - instrument.issue_date).days
            if days < 365:
                discrepancies.append({
                    "rule_code": "INVALID_DATES",
                    "severity": DiscrepancySeverity.MEDIUM,
                    "title": "FDR Tenure Below Minimum (1 Year)",
                    "description": f"Tenure is only {days} days. AICTE security deposits mandate multi-year fixed deposits (minimum 1 year, typically 5-10 years).",
                    "details": {"tenure_days": days, "minimum_days": 365},
                })

        # -------------------------------------------------------------
        # Rule 11: OCR vs Typed Mismatches (MEDIUM)
        # -------------------------------------------------------------
        active_ocr = ocr_data or getattr(instrument, 'ocr_extracted_data', None)
        if active_ocr and active_ocr.get("success"):
            from apps.instruments.ocr import compare_ocr_vs_typed
            typed_dict = {
                "reference_number": instrument.reference_number,
                "issuing_bank": instrument.issuing_bank,
                "amount": float(instrument.amount),
                "issue_date": str(instrument.issue_date),
                "maturity_date": str(instrument.maturity_date),
            }
            mismatches = compare_ocr_vs_typed(active_ocr, typed_dict)
            if mismatches:
                summary = "; ".join(m["message"] for m in mismatches)
                discrepancies.append({
                    "rule_code": "OCR_TYPED_MISMATCH",
                    "severity": DiscrepancySeverity.MEDIUM,
                    "title": "OCR Scan vs Typed Value Mismatch",
                    "description": f"Scanned certificate OCR extracted values differ from entered values: {summary}",
                    "details": {"mismatches": mismatches},
                })

        return discrepancies


def calculate_trust_score(
    instrument: Instrument,
    unresolved_discrepancies: List[Any],
    bank_confirmed: bool = False
) -> int:
    """
    Computes an automated Trust Score (0 - 100) based on:
    - Bank Confirmation (40% weight)
    - Discrepancy Cleanliness (40% weight)
    - Document Completeness (20% weight)
    """
    score = 0

    # 1. Bank Confirmation Component (Max 40 pts)
    # Check if bank has confirmed fields
    has_bank_field_sources = instrument.field_sources.filter(
        value_source=DataProvenanceSource.BANK_CONFIRMED,
        is_confirmed=True
    ).exists()

    if bank_confirmed or has_bank_field_sources:
        # Check if amount and maturity were confirmed
        amount_confirmed = instrument.field_sources.filter(
            field_name='amount',
            value_source=DataProvenanceSource.BANK_CONFIRMED,
            is_confirmed=True
        ).exists()
        mat_confirmed = instrument.field_sources.filter(
            field_name='maturity_date',
            value_source=DataProvenanceSource.BANK_CONFIRMED,
            is_confirmed=True
        ).exists()
        lien_confirmed = instrument.field_sources.filter(
            field_name='lien_in_favour_of_aicte',
            value_source=DataProvenanceSource.BANK_CONFIRMED,
            is_confirmed=True
        ).exists()

        confirmed_count = sum([amount_confirmed, mat_confirmed, lien_confirmed, True])
        score += int((confirmed_count / 4.0) * 40)
    else:
        # Baseline before bank verification
        score += 10

    # 2. Discrepancy Cleanliness Component (Max 40 pts)
    clean_score = 40
    for d in unresolved_discrepancies:
        if isinstance(d, dict):
            sev = d.get('severity')
        else:
            sev = getattr(d, 'severity', None)

        if sev == DiscrepancySeverity.CRITICAL or sev == 'CRITICAL':
            clean_score -= 20
        elif sev == DiscrepancySeverity.HIGH or sev == 'HIGH':
            clean_score -= 10
        elif sev == DiscrepancySeverity.MEDIUM or sev == 'MEDIUM':
            clean_score -= 5
        elif sev == DiscrepancySeverity.LOW or sev == 'LOW':
            clean_score -= 2
    score += max(0, clean_score)

    # 3. Document Completeness Component (Max 20 pts)
    docs = instrument.documents.all()
    has_dup_hash = docs.filter(is_duplicate_hash=True).exists()
    if not has_dup_hash:
        has_fdr_cert = docs.filter(document_type='FDR_CERTIFICATE').exists()
        has_lien_or_other = docs.filter(document_type__in=['BANK_CONFIRMATION', 'JOINT_PLEDGE_DEED', 'OTHER']).exists()
        if has_fdr_cert:
            score += 10
        if has_lien_or_other:
            score += 10

    return max(0, min(100, score))


def run_discrepancy_check(
    instrument: Instrument,
    save: bool = True,
    bank_response: Optional[Dict[str, Any]] = None,
    ocr_data: Optional[Dict[str, Any]] = None,
    user: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Executes the DiscrepancyEngine, synchronizes Discrepancy records,
    recalculates trust score, updates instrument status if necessary, and records audit trail.
    """
    evaluated = DiscrepancyEngine.evaluate(
        instrument=instrument,
        bank_response=bank_response,
        ocr_data=ocr_data
    )

    created_discrepancies = []
    if save:
        # Update existing or create new discrepancy records
        for item in evaluated:
            obj, created = Discrepancy.objects.get_or_create(
                instrument=instrument,
                rule_code=item["rule_code"],
                defaults={
                    "severity": item["severity"],
                    "title": item["title"],
                    "description": item["description"],
                    "details": item.get("details", {}),
                    "is_resolved": False,
                }
            )
            if not created and not obj.is_resolved:
                # Update details and severity
                obj.severity = item["severity"]
                obj.title = item["title"]
                obj.description = item["description"]
                obj.details = item.get("details", {})
                obj.save()
            created_discrepancies.append(obj)

        # Get all currently unresolved discrepancies
        unresolved = list(instrument.discrepancies.filter(is_resolved=False))

        # Recalculate trust score
        is_bank_confirmed = bool(bank_response and bank_response.get("status") == "CONFIRMED")
        new_trust_score = calculate_trust_score(
            instrument=instrument,
            unresolved_discrepancies=unresolved,
            bank_confirmed=is_bank_confirmed
        )
        instrument.trust_score = new_trust_score

        # Auto-transition status to Discrepancy if critical/high unresolved discrepancies exist
        # and current status is not already Rejected or Released
        has_critical_or_high = any(
            d.severity in [DiscrepancySeverity.CRITICAL, DiscrepancySeverity.HIGH]
            for d in unresolved
        )
        if has_critical_or_high and instrument.status not in [
            InstrumentStatus.REJECTED,
            InstrumentStatus.RELEASED,
            InstrumentStatus.VERIFIED,
        ]:
            instrument.status = InstrumentStatus.DISCREPANCY

        instrument.save(update_fields=['trust_score', 'status', 'updated_at'])

        if user:
            record_audit_event(
                action="DISCREPANCY_CHECK_EXECUTED",
                entity_type="Instrument",
                entity_id=str(instrument.pk),
                actor_username=getattr(user, 'username', 'system'),
                actor_role=getattr(user, 'role', ''),
                metadata={
                    "discrepancies_count": len(unresolved),
                    "trust_score": new_trust_score,
                    "status": instrument.status,
                    "description": f"Rule discrepancy check executed on {instrument.reference_number}. Flags found: {len(unresolved)}, Trust Score: {new_trust_score}/100.",
                }
            )

    return {
        "discrepancies": evaluated,
        "trust_score": instrument.trust_score,
        "status": instrument.status,
    }
