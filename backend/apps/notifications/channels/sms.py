import logging
import uuid
from abc import ABC, abstractmethod
from typing import Dict, Any

logger = logging.getLogger(__name__)


class SmsAdapter(ABC):
    """
    Abstract adapter interface for telecom SMS gateways (e.g. CDAC / NIC / Twilio / Karix).
    """
    @abstractmethod
    def send_sms(self, to_phone: str, message: str) -> Dict[str, Any]:
        """
        Sends an SMS message to a mobile number.
        Returns dictionary with status and message identifier.
        """
        pass


class MockSmsAdapter(SmsAdapter):
    """
    Mock SMS gateway adapter for local development and hackathon demos.
    Logs SMS payloads clearly to stdout/logger without incurring carrier costs.
    """
    def __init__(self, sender_id: str = "AICTE-REG"):
        self.sender_id = sender_id

    def send_sms(self, to_phone: str, message: str) -> Dict[str, Any]:
        msg_id = f"SMS-MOCK-{uuid.uuid4().hex[:12].upper()}"
        clean_phone = to_phone.strip() if to_phone else "+91-9876543210"
        
        logger.info(
            f"[MOCK SMS GATEWAY] To: {clean_phone} | Sender: {self.sender_id} | MsgID: {msg_id}\n"
            f"Content: {message}"
        )
        print(
            f"\n--- [MOCK SMS DISPATCH] ---\n"
            f"Recipient: {clean_phone}\n"
            f"Sender: {self.sender_id}\n"
            f"Message ID: {msg_id}\n"
            f"Text: {message}\n"
            f"---------------------------\n"
        )

        return {
            "success": True,
            "status": "DELIVERED",
            "message_id": msg_id,
            "to_phone": clean_phone,
            "sender_id": self.sender_id,
            "is_mock": True,
        }


# Global default instance
default_sms_adapter = MockSmsAdapter()


def get_sms_adapter() -> SmsAdapter:
    """Returns configured SMS adapter."""
    return default_sms_adapter
