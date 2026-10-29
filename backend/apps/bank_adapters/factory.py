import importlib
import logging
from django.conf import settings
from .base import BankVerificationAdapter

logger = logging.getLogger('aicte.bank_adapters')

def get_bank_adapter() -> BankVerificationAdapter:
    """
    Factory loader to retrieve the configured BankVerificationAdapter.
    Loads class dynamically specified by settings.BANK_ADAPTER_CLASS.
    """
    adapter_path = getattr(
        settings,
        'BANK_ADAPTER_CLASS',
        'apps.bank_adapters.mock_adapter.MockBankVerificationAdapter'
    )
    try:
        module_path, class_name = adapter_path.rsplit('.', 1)
        module = importlib.import_module(module_path)
        adapter_class = getattr(module, class_name)
        adapter_instance = adapter_class()
        logger.info("Loaded Bank Verification Adapter: %s (is_mock=%s)", adapter_instance.adapter_name, adapter_instance.is_mock)
        return adapter_instance
    except Exception as exc:
        logger.error("Failed to load adapter %s: %s. Falling back to MockBankVerificationAdapter.", adapter_path, exc)
        from .mock_adapter import MockBankVerificationAdapter
        return MockBankVerificationAdapter()
