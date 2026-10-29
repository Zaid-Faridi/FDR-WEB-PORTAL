import pytest
from apps.bank_adapters.factory import get_bank_adapter
from apps.bank_adapters.base import FDRVerificationRequest
from apps.bank_adapters.mock_adapter import MockBankVerificationAdapter

def test_bank_adapter_factory_loads_mock():
    adapter = get_bank_adapter()
    assert isinstance(adapter, MockBankVerificationAdapter)
    assert adapter.is_mock is True
    assert "MOCK" in adapter.adapter_name

def test_mock_adapter_confirmed_path():
    adapter = get_bank_adapter()
    req = FDRVerificationRequest(
        fdr_number="FDR-CONF-1001",
        bank_name="State Bank of India",
        branch_ifsc="SBIN0000001",
        claimed_amount=1000000.0,
        claimed_deposit_date="2024-01-01",
        claimed_maturity_date="2032-01-01",
        joint_holder_name="XYZ Engineering College",
        institution_id="INST-001"
    )
    res = adapter.verify_fdr(req)
    assert res.success is True
    assert res.status_code == "CONFIRMED"
    assert res.is_mock is True
    assert res.lien_marked is True
    assert len(res.discrepancies) == 0
    assert res.confirmed_amount == 1000000.0

def test_mock_adapter_discrepancy_detection():
    adapter = get_bank_adapter()
    req = FDRVerificationRequest(
        fdr_number="FDR-DISCREPANT-8899",
        bank_name="Punjab National Bank",
        branch_ifsc="PUNB0000002",
        claimed_amount=500000.0,
        claimed_deposit_date="2023-05-10",
        claimed_maturity_date="2031-05-10",
        joint_holder_name="ABC Polytechnic Institute",
        institution_id="INST-002"
    )
    res = adapter.verify_fdr(req)
    assert res.success is True
    assert res.status_code == "DISCREPANCY_DETECTED"
    assert len(res.discrepancies) > 0
    assert res.lien_marked is False
    assert res.confirmed_amount < req.claimed_amount

def test_mock_adapter_not_found():
    adapter = get_bank_adapter()
    req = FDRVerificationRequest(
        fdr_number="FDR-NOTFOUND-9999",
        bank_name="Bank of Baroda",
        branch_ifsc="BARB0000003",
        claimed_amount=250000.0,
        claimed_deposit_date="2022-01-01",
        claimed_maturity_date="2030-01-01",
        joint_holder_name="Test College",
        institution_id="INST-003"
    )
    res = adapter.verify_fdr(req)
    assert res.success is False
    assert res.status_code == "NOT_FOUND"
    assert "not found" in res.discrepancies[0].lower()
