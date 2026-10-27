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

class MockBankVerificationAdapter(BankVerificationAdapter):
    """
    [MOCK] Bank Verification Adapter
    Simulates Core Banking System (CBS) and SFMS verification responses.
    """
    adapter_name = "MOCK_BANK_VERIFICATION_ADAPTER (Sandbox Simulator)"
    is_mock = True

    def verify_fdr(self, request: FDRVerificationRequest) -> FDRVerificationResponse:
        """
        Simulates bank verification logic.
        Certain test FDR numbers trigger predictable mock behavior:
        - Numbers containing 'DISCREPANT': returns amount or holder mismatch
        - Numbers containing 'NOLIEN': returns lien missing
        - Numbers containing 'NOTFOUND': simulates receipt not found in bank CBS
        - Default: returns fully confirmed valid FDR
        """
        fdr_num = request.fdr_number.upper()
        now_str = datetime.now().isoformat()
        ref_id = f"MOCK-CBS-{uuid.uuid4().hex[:10].upper()}"

        # Case 1: FDR does not exist in bank records
        if "NOTFOUND" in fdr_num:
            return FDRVerificationResponse(
                success=False,
                status_code="NOT_FOUND",
                bank_reference_id=ref_id,
                verified_at=now_str,
                adapter_name=self.adapter_name,
                is_mock=True,
                discrepancies=["FDR receipt number not found in issuing bank CBS records."],
                raw_payload={"mock_case": "not_found", "queried_fdr": fdr_num},
            )

        # Case 2: FDR found but with discrepancies (e.g. amount variance or name mismatch)
        if "DISCREPANT" in fdr_num:
            confirmed_amount = float(request.claimed_amount) - 50000.0  # 50k less than claimed
            return FDRVerificationResponse(
                success=True,
                status_code="DISCREPANCY_DETECTED",
                bank_reference_id=ref_id,
                verified_at=now_str,
                adapter_name=self.adapter_name,
                is_mock=True,
                confirmed_amount=confirmed_amount,
                confirmed_deposit_date=request.claimed_deposit_date,
                confirmed_maturity_date=request.claimed_maturity_date,
                confirmed_joint_holder=f"{request.joint_holder_name} (Single Owner, No AICTE Lien)",
                lien_marked=False,
                lien_in_favor_of=None,
                discrepancies=[
                    f"Amount mismatch: Claimed ₹{request.claimed_amount:,.2f} vs Bank-Confirmed ₹{confirmed_amount:,.2f}",
                    "Lien not marked in favor of AICTE",
                ],
                raw_payload={
                    "mock_case": "discrepant",
                    "bank_branch": request.branch_ifsc,
                    "claimed_amount": request.claimed_amount,
                    "confirmed_amount": confirmed_amount,
                },
            )

        # Case 3: FDR found but Lien is missing
        if "NOLIEN" in fdr_num:
            return FDRVerificationResponse(
                success=True,
                status_code="DISCREPANCY_DETECTED",
                bank_reference_id=ref_id,
                verified_at=now_str,
                adapter_name=self.adapter_name,
                is_mock=True,
                confirmed_amount=float(request.claimed_amount),
                confirmed_deposit_date=request.claimed_deposit_date,
                confirmed_maturity_date=request.claimed_maturity_date,
                confirmed_joint_holder=request.joint_holder_name,
                lien_marked=False,
                lien_in_favor_of=None,
                discrepancies=["Lien has not been marked in favor of AICTE by issuing branch."],
                raw_payload={"mock_case": "missing_lien"},
            )

        # Default Happy Path: Fully confirmed bank record
        return FDRVerificationResponse(
            success=True,
            status_code="CONFIRMED",
            bank_reference_id=ref_id,
            verified_at=now_str,
            adapter_name=self.adapter_name,
            is_mock=True,
            confirmed_amount=float(request.claimed_amount),
            confirmed_deposit_date=request.claimed_deposit_date,
            confirmed_maturity_date=request.claimed_maturity_date,
            confirmed_joint_holder=f"{request.joint_holder_name} and Member Secretary AICTE",
            lien_marked=True,
            lien_in_favor_of="Member Secretary, AICTE New Delhi",
            discrepancies=[],
            raw_payload={
                "mock_case": "confirmed_standard",
                "bank_name": request.bank_name,
                "branch_ifsc": request.branch_ifsc,
                "verified_by": "MOCK_CBS_GATEWAY_V1",
            },
        )

    def check_lien_status(self, fdr_number: str, branch_ifsc: str) -> LienStatusResponse:
        """
        Simulates lien status query against bank branch ledger.
        """
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
