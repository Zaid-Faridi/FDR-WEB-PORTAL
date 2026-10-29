import hmac
import hashlib
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from django.conf import settings
from apps.institutions.models import Institution, InstitutionStatus
from apps.common.audit import record_audit_event

logger = logging.getLogger('aicte.integrations')

AICTE_SYNC_SECRET = getattr(settings, 'AICTE_SYNC_WEBHOOK_SECRET', 'aicte-sync-secret-key-2026-secure')


class AICTEInstitutionSyncAdapter(ABC):
    """
    Abstract Integration Adapter Interface for syncing institutional master data
    from an existing AICTE System (e.g., Central Approval Process Bureau, e-Governance Portal).
    """

    @abstractmethod
    def fetch_institution(self, aicte_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single institution by AICTE Permanent ID."""
        pass

    @abstractmethod
    def fetch_all_institutions(self, state: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch batch institution records, optionally filtered by state."""
        pass

    @abstractmethod
    def verify_webhook_signature(self, payload_bytes: bytes, signature_header: str) -> bool:
        """Cryptographically verifies HMAC-SHA256 signature from the central AICTE webhook dispatcher."""
        pass


class MockAICTEApprovalSystemAdapter(AICTEInstitutionSyncAdapter):
    """
    High-fidelity Mock Adapter simulating the AICTE Central Approval Process System (e-Gov).
    Supplies accurate master records for technical institutions so institutions
    never have to enter duplicate organizational details into the FDR Portal.
    """

    MOCK_INSTITUTION_DIRECTORY: Dict[str, Dict[str, Any]] = {
        '1-100200300': {
            'aicte_id': '1-100200300',
            'name': 'Delhi Institute of Technology & Management',
            'institution_type': 'Engineering & Technology',
            'address': 'Sector 14, Dwarka',
            'state': 'Delhi',
            'district': 'South West Delhi',
            'pincode': '110078',
            'status': 'ACTIVE',
            'contact_email': 'registrar@ditm-delhi.edu.in',
            'contact_phone': '+91-11-28080001',
            'approval_year': 2004,
            'region': 'North',
        },
        '1-400500600': {
            'aicte_id': '1-400500600',
            'name': 'Mumbai College of Engineering & Research',
            'institution_type': 'Engineering & Technology',
            'address': 'Bandra Kurla Complex',
            'state': 'Maharashtra',
            'district': 'Mumbai Suburban',
            'pincode': '400051',
            'status': 'ACTIVE',
            'contact_email': 'principal@mumbai-engg.edu.in',
            'contact_phone': '+91-22-26590002',
            'approval_year': 2008,
            'region': 'West',
        },
        '1-700800900': {
            'aicte_id': '1-700800900',
            'name': 'Bangalore National Institute of Applied Sciences',
            'institution_type': 'Engineering & Technology',
            'address': 'Electronic City Phase 1',
            'state': 'Karnataka',
            'district': 'Bangalore Urban',
            'pincode': '560100',
            'status': 'ACTIVE',
            'contact_email': 'admin@bnias.ac.in',
            'contact_phone': '+91-80-28520003',
            'approval_year': 2011,
            'region': 'South-West',
        },
        '1-900100200': {
            'aicte_id': '1-900100200',
            'name': 'Chennai Institute of Engineering & Robotics',
            'institution_type': 'Engineering & Technology',
            'address': 'IT Highway, OMR, Sholinganallur',
            'state': 'Tamil Nadu',
            'district': 'Chennai',
            'pincode': '600119',
            'status': 'ACTIVE',
            'contact_email': 'dean@cier-chennai.edu.in',
            'contact_phone': '+91-44-24500004',
            'approval_year': 2013,
            'region': 'South',
        },
        '1-550660770': {
            'aicte_id': '1-550660770',
            'name': 'Pune College of Pharmaceutical Sciences',
            'institution_type': 'Pharmacy',
            'address': 'Erandwane, Karve Road',
            'state': 'Maharashtra',
            'district': 'Pune',
            'pincode': '411038',
            'status': 'ACTIVE',
            'contact_email': 'director@pcps-pune.edu.in',
            'contact_phone': '+91-20-25440005',
            'approval_year': 2009,
            'region': 'West',
        },
        '1-880990110': {
            'aicte_id': '1-880990110',
            'name': 'Hyderabad Global Institute of Management Studies',
            'institution_type': 'Management',
            'address': 'HITEC City, Madhapur',
            'state': 'Telangana',
            'district': 'Hyderabad',
            'pincode': '500081',
            'status': 'ACTIVE',
            'contact_email': 'admissions@hgims-hyd.ac.in',
            'contact_phone': '+91-40-23110006',
            'approval_year': 2015,
            'region': 'South-Central',
        },
    }

    def fetch_institution(self, aicte_id: str) -> Optional[Dict[str, Any]]:
        """Fetch institution by permanent ID from mock central AICTE directory."""
        if aicte_id in self.MOCK_INSTITUTION_DIRECTORY:
            return dict(self.MOCK_INSTITUTION_DIRECTORY[aicte_id])

        # If ID follows valid AICTE ID pattern (e.g. 1-XXXXXXXXX), generate dynamic deterministic record
        if aicte_id.startswith('1-') and len(aicte_id) >= 6:
            code = aicte_id.replace('-', '')
            return {
                'aicte_id': aicte_id,
                'name': f"National Technical Academy ({aicte_id})",
                'institution_type': 'Engineering & Technology',
                'address': f"AICTE Institutional Area, Sector {int(code[-2:]) % 30 + 1}",
                'state': 'Uttar Pradesh' if int(code[-1]) % 2 == 0 else 'Maharashtra',
                'district': 'Noida' if int(code[-1]) % 2 == 0 else 'Pune',
                'pincode': '201301' if int(code[-1]) % 2 == 0 else '411001',
                'status': 'ACTIVE',
                'contact_email': f"info@{code[-6:]}-tech.edu.in",
                'contact_phone': f"+91-120-25{code[-4:]}",
                'approval_year': 2016,
                'region': 'Northern',
            }
        return None

    def fetch_all_institutions(self, state: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch all institutions in mock directory, with optional state filter."""
        results = list(self.MOCK_INSTITUTION_DIRECTORY.values())
        if state:
            results = [r for r in results if r.get('state', '').lower() == state.lower()]
        return results

    def verify_webhook_signature(self, payload_bytes: bytes, signature_header: str) -> bool:
        """
        Verifies HMAC-SHA256 signature in X-AICTE-Signature header.
        Supports sha256=HEX_SIGNATURE or raw HEX_SIGNATURE format.
        """
        if not signature_header:
            return False

        expected_sig = signature_header.replace('sha256=', '').strip()
        computed_sig = hmac.new(
            AICTE_SYNC_SECRET.encode('utf-8'),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected_sig, computed_sig)


def sync_institution_record(
    data: Dict[str, Any],
    source: str = 'AICTE_REST_SYNC',
    actor_username: str = 'system'
) -> Institution:
    """
    Idempotent helper to upsert an Institution from an external AICTE system payload
    and record an append-only audit log entry.
    """
    aicte_id = data.get('aicte_id')
    if not aicte_id:
        raise ValueError("Missing mandatory 'aicte_id' field in institution sync payload.")

    status_str = data.get('status', 'ACTIVE').upper()
    valid_statuses = [c[0] for c in InstitutionStatus.choices]
    effective_status = status_str if status_str in valid_statuses else InstitutionStatus.ACTIVE

    institution, created = Institution.objects.update_or_create(
        aicte_id=aicte_id,
        defaults={
            'name': data.get('name', f"Institution {aicte_id}"),
            'institution_type': data.get('institution_type', 'Engineering & Technology'),
            'address': data.get('address', ''),
            'state': data.get('state', 'Unknown'),
            'district': data.get('district', ''),
            'pincode': data.get('pincode', ''),
            'status': effective_status,
            'contact_email': data.get('contact_email', ''),
            'contact_phone': data.get('contact_phone', ''),
        }
    )

    action = 'INSTITUTION_SYNC_CREATED' if created else 'INSTITUTION_SYNC_UPDATED'
    record_audit_event(
        action=action,
        entity_type='Institution',
        entity_id=str(institution.id),
        actor_username=actor_username,
        actor_role='SYSTEM_INTEGRATION',
        new_state={
            'aicte_id': institution.aicte_id,
            'name': institution.name,
            'state': institution.state,
            'sync_source': source,
        },
        metadata={'source': source, 'aicte_id': aicte_id}
    )

    logger.info("Successfully synced institution %s (%s) from %s", institution.aicte_id, institution.name, source)
    return institution


# Global default instance
default_sync_adapter = MockAICTEApprovalSystemAdapter()
