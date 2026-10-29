"""
=============================================================================
CLEARLY LABELLED MOCK IMPLEMENTATION: MockBankVerificationAdapter
=============================================================================
This module is a simulated Bank Verification Adapter designed for hackathon
evaluation, automated CI tests, and local sandboxing without live banking APIs.

It adheres strictly to the BankVerificationAdapter interface.
In production, this is swapped via the BANK_ADAPTER_CLASS environment variable.
=============================================================================
"""

import uuid
from datetime import datetime
from typing import Dict, Any, List

from .base import (
    BankVerificationAdapter,
    FDRVerificationRequest,
    FDRVerificationResponse,
    LienStatusResponse,
)

class MockBankAdapter(BankVerificationAdapter):
    """
    [MOCK] Bank Verification Adapter (Sandbox Simulator)
    Simulates Core Banking System (CBS) and SFMS verification responses.
    Clearly labelled MOCK in all code, API responses, and logs.
    """
    adapter_name = "MOCK_BANK_VERIFICATION_ADAPTER (Sandbox Simulator)"
    is_mock = True

    # Seeded registry with deliberate edge cases
    SEEDED_REGISTRY: Dict[str, Dict[str, Any]] = {
        # Edge Case 1: Match
        "FDR-SBI-2026-001": {
            "status": "CONFIRMED",
            "bank": "State Bank of India",
            "branch": "New Delhi Main Branch (SBIN0000691)",
            "amount": 10000000.00,
            "issue_date": "2024-01-15",
            "maturity_date": "2034-01-15",
            "lien_marked": True,
            "lien_in_favor_of": "Member Secretary, AICTE New Delhi",
            "joint_holder": "Delhi Institute of Technology & Management and AICTE",
            "discrepancies": [],
        },
        "FDR-MATCH-SBI-101": {
            "status": "CONFIRMED",
            "bank": "State Bank of India",
            "branch": "Connaught Place, New Delhi",
            "amount": 5000000.00,
            "issue_date": "2023-08-01",
            "maturity_date": "2033-08-01",
            "lien_marked": True,
            "lien_in_favor_of": "Member Secretary, AICTE New Delhi",
            "joint_holder": "Mumbai Engineering College and AICTE",
            "discrepancies": [],
        },
        # Edge Case 2: Amount Mismatch (Claimed ₹35,00,000 vs Bank ₹25,00,000)
        "FDR-PNB-MISMATCH-AMT": {
            "status": "DISCREPANCY_DETECTED",
            "bank": "Punjab National Bank",
            "branch": "Nehru Place, New Delhi (PUNB0123456)",
            "amount": 2500000.00,  # Deliberately 10L less than claimed 35L
            "issue_date": "2023-05-10",
            "maturity_date": "2031-05-10",
            "lien_marked": True,
            "lien_in_favor_of": "Member Secretary, AICTE New Delhi",
            "joint_holder": "Technical Institute and AICTE",
            "discrepancies": [
                "Amount mismatch: Bank confirmed deposit is ₹25,00,000.00 (less than claimed deposit)."
            ],
        },
        # Edge Case 3: Date Mismatch (Bank maturity is 2028-01-01 instead of claimed 2033-01-01)
        "FDR-HDFC-MISMATCH-DATE": {
            "status": "DISCREPANCY_DETECTED",
            "bank": "HDFC Bank",
            "branch": "Kasturba Gandhi Marg, New Delhi (HDFC0000123)",
            "amount": 5000000.00,
            "issue_date": "2023-01-01",
            "maturity_date": "2028-01-01",  # 5-year tenure instead of 10-year
            "lien_marked": True,
            "lien_in_favor_of": "Member Secretary, AICTE New Delhi",
            "joint_holder": "Technical Institute and AICTE",
            "discrepancies": [
                "Maturity date mismatch: Bank CBS records maturity as 2028-01-01 (claimed 2033-01-01)."
            ],
        },
        # Edge Case 4: Not Found
        "FDR-UNKNOWN-404": {
            "status": "NOT_FOUND",
            "bank": "Bank of Baroda",
            "branch": "Unknown Branch",
            "amount": None,
            "issue_date": None,
            "maturity_date": None,
            "lien_marked": False,
            "lien_in_favor_of": None,
            "joint_holder": None,
            "discrepancies": ["FDR instrument not found in issuing bank CBS records."],
        },
    }

    def verify(self, fdr_number: str, bank: str) -> Dict[str, Any]:
        """
        Verify the FDR instrument with the issuing bank branch or CBS.
        Labels the result explicitly as [MOCK].
        """
        key = fdr_number.strip().upper()
        now_str = datetime.now().isoformat()
        ref_id = f"MOCK-CBS-{uuid.uuid4().hex[:10].upper()}"

        # 1. Check exact seeded registry
        for seeded_key, data in self.SEEDED_REGISTRY.items():
            if seeded_key.upper() == key:
                return {
                    "status": data["status"],
                    "fdr_number": fdr_number,
                    "bank": data.get("bank", bank),
                    "branch": data.get("branch", "CBS Automated Gateway"),
                    "confirmed_amount": data.get("amount"),
                    "confirmed_issue_date": data.get("issue_date"),
                    "confirmed_maturity_date": data.get("maturity_date"),
                    "lien_marked": data.get("lien_marked", False),
                    "lien_in_favor_of": data.get("lien_in_favor_of"),
                    "joint_holder": data.get("joint_holder"),
                    "bank_reference_id": ref_id,
                    "verified_at": now_str,
                    "adapter_name": self.adapter_name,
                    "is_mock": True,
                    "discrepancies": list(data.get("discrepancies", [])),
                    "raw_payload": {
                        "mock_mode": "seeded_registry",
                        "matched_key": seeded_key,
                        "queried_bank": bank,
                    },
                }

        # 2. Dynamic pattern matching for test fixtures
        if "NOTFOUND" in key or "404" in key:
            return {
                "status": "NOT_FOUND",
                "fdr_number": fdr_number,
                "bank": bank,
                "branch": None,
                "confirmed_amount": None,
                "confirmed_issue_date": None,
                "confirmed_maturity_date": None,
                "lien_marked": False,
                "lien_in_favor_of": None,
                "joint_holder": None,
                "bank_reference_id": ref_id,
                "verified_at": now_str,
                "adapter_name": self.adapter_name,
                "is_mock": True,
                "discrepancies": ["FDR receipt number not found in issuing bank CBS records."],
                "raw_payload": {"mock_case": "not_found", "queried_fdr": fdr_number},
            }

        if "DISCREPANT" in key:
            return {
                "status": "DISCREPANCY_DETECTED",
                "fdr_number": fdr_number,
                "bank": bank,
                "branch": "Mock Urban Branch",
                "confirmed_amount": 450000.00,  # 50k less than typical 500k in test
                "confirmed_issue_date": "2023-05-10",
                "confirmed_maturity_date": "2031-05-10",
                "lien_marked": False,
                "lien_in_favor_of": None,
                "joint_holder": "Technical Institute (Single Owner, No AICTE Lien)",
                "bank_reference_id": ref_id,
                "verified_at": now_str,
                "adapter_name": self.adapter_name,
                "is_mock": True,
                "discrepancies": [
                    "Amount mismatch: Confirmed amount is less than claimed deposit",
                    "Lien not marked in favor of AICTE",
                ],
                "raw_payload": {"mock_case": "discrepant"},
            }

        if "MISMATCH-AMT" in key or "AMT_MISMATCH" in key:
            return {
                "status": "DISCREPANCY_DETECTED",
                "fdr_number": fdr_number,
                "bank": bank,
                "branch": "Mock Urban Branch",
                "confirmed_amount": 2500000.00,  # 25 Lakhs
                "confirmed_issue_date": "2023-05-10",
                "confirmed_maturity_date": "2031-05-10",
                "lien_marked": True,
                "lien_in_favor_of": "Member Secretary, AICTE New Delhi",
                "joint_holder": "Technical Institute and AICTE",
                "bank_reference_id": ref_id,
                "verified_at": now_str,
                "adapter_name": self.adapter_name,
                "is_mock": True,
                "discrepancies": ["Amount mismatch: Bank confirmed deposit is ₹25,00,000.00."],
                "raw_payload": {"mock_case": "amount_mismatch"},
            }

        if "MISMATCH-DATE" in key or "DATE_MISMATCH" in key:
            return {
                "status": "DISCREPANCY_DETECTED",
                "fdr_number": fdr_number,
                "bank": bank,
                "branch": "Mock Metro Branch",
                "confirmed_amount": 5000000.00,
                "confirmed_issue_date": "2023-01-01",
                "confirmed_maturity_date": "2028-01-01",  # 5-year tenure
                "lien_marked": True,
                "lien_in_favor_of": "Member Secretary, AICTE New Delhi",
                "joint_holder": "Technical Institute and AICTE",
                "bank_reference_id": ref_id,
                "verified_at": now_str,
                "adapter_name": self.adapter_name,
                "is_mock": True,
                "discrepancies": ["Maturity date mismatch: Bank CBS records maturity date as 2028-01-01."],
                "raw_payload": {"mock_case": "date_mismatch"},
            }

        if "NOLIEN" in key:
            return {
                "status": "DISCREPANCY_DETECTED",
                "fdr_number": fdr_number,
                "bank": bank,
                "branch": "Mock City Branch",
                "confirmed_amount": 5000000.00,
                "confirmed_issue_date": "2024-01-01",
                "confirmed_maturity_date": "2034-01-01",
                "lien_marked": False,
                "lien_in_favor_of": None,
                "joint_holder": "Technical Institute Only",
                "bank_reference_id": ref_id,
                "verified_at": now_str,
                "adapter_name": self.adapter_name,
                "is_mock": True,
                "discrepancies": ["Lien has not been marked in favor of AICTE by issuing branch."],
                "raw_payload": {"mock_case": "missing_lien"},
            }

        # Default: Confirmed Match
        return {
            "status": "CONFIRMED",
            "fdr_number": fdr_number,
            "bank": bank,
            "branch": "AICTE Specialized Branch",
            "confirmed_amount": None,  # Dynamically resolved to claimed amount in verify_fdr or 5,000,000 if standalone
            "confirmed_issue_date": "2024-01-15",
            "confirmed_maturity_date": "2034-01-15",
            "lien_marked": True,
            "lien_in_favor_of": "Member Secretary, AICTE New Delhi",
            "joint_holder": "Institution and Member Secretary AICTE",
            "bank_reference_id": ref_id,
            "verified_at": now_str,
            "adapter_name": self.adapter_name,
            "is_mock": True,
            "discrepancies": [],
            "raw_payload": {"mock_case": "confirmed_standard", "bank": bank},
        }

    def verify_fdr(self, request: FDRVerificationRequest) -> FDRVerificationResponse:
        """
        Backwards-compatible wrapper calling verify().
        """
        raw = self.verify(request.fdr_number, request.bank_name)
        status = raw["status"]
        success = (status != "NOT_FOUND" and status != "SYSTEM_ERROR")

        confirmed_amount = raw.get("confirmed_amount")
        if confirmed_amount is None and success:
            confirmed_amount = float(request.claimed_amount)
        elif "DISCREPANT" in request.fdr_number.upper():
            confirmed_amount = float(request.claimed_amount) - 50000.0

        # Detect discrepancy against request claimed fields if confirmed
        discrepancies = list(raw.get("discrepancies", []))
        if confirmed_amount is not None and abs(confirmed_amount - float(request.claimed_amount)) > 0.01:
            if not any("Amount mismatch" in d for d in discrepancies):
                discrepancies.append(
                    f"Amount mismatch: Claimed ₹{request.claimed_amount:,.2f} vs Bank-Confirmed ₹{confirmed_amount:,.2f}"
                )

        confirmed_dep_date = raw.get("confirmed_issue_date")
        confirmed_mat_date = raw.get("confirmed_maturity_date")
        if raw.get("raw_payload", {}).get("mock_case") == "confirmed_standard":
            confirmed_dep_date = request.claimed_deposit_date
            confirmed_mat_date = request.claimed_maturity_date

        return FDRVerificationResponse(
            success=success,
            status_code=status,
            bank_reference_id=raw["bank_reference_id"],
            verified_at=raw["verified_at"],
            adapter_name=self.adapter_name,
            is_mock=True,
            confirmed_amount=confirmed_amount,
            confirmed_deposit_date=confirmed_dep_date or request.claimed_deposit_date,
            confirmed_maturity_date=confirmed_mat_date or request.claimed_maturity_date,
            confirmed_joint_holder=raw.get("joint_holder") or f"{request.joint_holder_name} and Member Secretary AICTE",
            lien_marked=raw.get("lien_marked", False),
            lien_in_favor_of=raw.get("lien_in_favor_of"),
            discrepancies=discrepancies,
            raw_payload=raw.get("raw_payload", {}),
        )

    def check_lien_status(self, fdr_number: str, branch_ifsc: str) -> LienStatusResponse:
        fdr_num = fdr_number.upper()
        now_str = datetime.now().isoformat()

        if "NOLIEN" in fdr_num or "DISCREPANT" in fdr_num:
            return LienStatusResponse(
                success=True,
                fdr_number=fdr_number,
                lien_marked=False,
                lien_in_favor_of=None,
                encumbrance_status="FREE",
                verified_at=now_str,
                adapter_name=self.adapter_name,
                is_mock=True,
            )

        return LienStatusResponse(
            success=True,
            fdr_number=fdr_number,
            lien_marked=True,
            lien_in_favor_of="Member Secretary, AICTE New Delhi",
            encumbrance_status="LIEN_MARKED_AICTE",
            verified_at=now_str,
            adapter_name=self.adapter_name,
            is_mock=True,
        )


# Backward compatibility alias
MockBankVerificationAdapter = MockBankAdapter
