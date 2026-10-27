from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, Dict, Any, List

@dataclass
class FDRVerificationRequest:
    fdr_number: str
    bank_name: str
    branch_ifsc: str
    claimed_amount: float
    claimed_deposit_date: str
    claimed_maturity_date: str
    joint_holder_name: str
    institution_id: str
    extra_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FDRVerificationResponse:
    success: bool
    status_code: str  # e.g., 'CONFIRMED', 'DISCREPANCY_DETECTED', 'NOT_FOUND', 'SYSTEM_ERROR'
    bank_reference_id: str
    verified_at: str
    adapter_name: str
    is_mock: bool

    # Bank-confirmed fields (the truth as reported by the bank)
    confirmed_amount: Optional[float] = None
    confirmed_deposit_date: Optional[str] = None
    confirmed_maturity_date: Optional[str] = None
    confirmed_joint_holder: Optional[str] = None
    lien_marked: Optional[bool] = None
    lien_in_favor_of: Optional[str] = None

    # Discrepancies identified during bank reconciliation
    discrepancies: List[str] = field(default_factory=list)
    raw_payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LienStatusResponse:
    success: bool
    fdr_number: str
    lien_marked: bool
    lien_in_favor_of: Optional[str]
    encumbrance_status: str  # e.g. 'FREE', 'LIEN_MARKED_AICTE', 'THIRD_PARTY_ENCUMBRANCE'
    verified_at: str
    adapter_name: str
    is_mock: bool


class BankVerificationAdapter(ABC):
    """
    Pluggable abstract interface for Bank and SFMS/CBS verification.
    All bank verification must implement this contract.
    """
    adapter_name: str = "BaseBankVerificationAdapter"
    is_mock: bool = False

    @abstractmethod
    def verify_fdr(self, request: FDRVerificationRequest) -> FDRVerificationResponse:
        """
        Verify the FDR instrument with the issuing bank branch or CBS.
        Returns bank-confirmed details and any discrepancy flags.
        """
        pass

    @abstractmethod
    def check_lien_status(self, fdr_number: str, branch_ifsc: str) -> LienStatusResponse:
        """
        Query whether the FDR is encumbered or has a lien marked in favor of AICTE.
        """
        pass
