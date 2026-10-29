"""
Tests for Phase 8:
1. Integration Readiness: REST and Webhook endpoints for syncing institutional data
   from an existing AICTE system (Mock Adapter) with cryptographic HMAC-SHA256 signatures.
2. Impact Metrics & ROI Analytics: Verification turnaround, manual steps avoided,
   renewals caught before expiry, pending-case queues, and record accuracy.
3. Baseline Comparison: Seeded legacy manual process vs digital portal metrics.
"""
import hmac
import hashlib
import json
import pytest
from decimal import Decimal
from datetime import date, timedelta
from rest_framework.test import APIClient
from rest_framework import status
from django.conf import settings

from apps.users.models import User, UserRole
from apps.institutions.models import Institution, InstitutionStatus
from apps.instruments.models import (
    Instrument,
    InstrumentStatus,
    Discrepancy,
    DiscrepancySeverity,
    FieldSource,
)
from apps.common.models import DataProvenanceSource, AuditEntry
from apps.notifications.models import Notification
from apps.institutions.sync_adapter import (
    default_sync_adapter,
    AICTE_SYNC_SECRET,
    sync_institution_record,
)
from apps.reports.impact_metrics import calculate_impact_metrics


@pytest.fixture
def phase8_setup():
    inst1 = Institution.objects.create(
        name="Indian Institute of Engineering & Technology",
        aicte_id="1-IIET-001",
        state="Maharashtra",
        district="Pune",
        institution_type="Engineering & Technology",
        status=InstitutionStatus.ACTIVE,
    )
    inst2 = Institution.objects.create(
        name="Global College of Pharmacy",
        aicte_id="1-GCP-002",
        state="Delhi",
        district="New Delhi",
        institution_type="Pharmacy",
        status=InstitutionStatus.ACTIVE,
    )

    officer = User.objects.create_user(
        username="officer_phase8",
        email="officer8@aicte-india.org",
        password="TestPassword@123",
        role=UserRole.SCRUTINY_OFFICER,
    )
    approver = User.objects.create_user(
        username="approver_phase8",
        email="approver8@aicte-india.org",
        password="TestPassword@123",
        role=UserRole.APPROVING_AUTHORITY,
    )
    inst_user = User.objects.create_user(
        username="inst_phase8",
        email="inst8@iiet.ac.in",
        password="TestPassword@123",
        role=UserRole.INSTITUTION,
        institution=inst1,
    )

    # Create a set of instruments covering different states using the correct model field names
    ins_active = Instrument.objects.create(
        institution=inst1,
        reference_number="FDR-P8-ACTIVE",
        issuing_bank="State Bank of India",
        issuing_branch="Pune Main",
        branch_ifsc="SBIN0001234",
        amount=Decimal("1500000.00"),
        issue_date=date(2023, 1, 1),
        maturity_date=date(2028, 1, 1),
        status=InstrumentStatus.ACTIVE,
        trust_score=98,
    )
    FieldSource.objects.create(
        instrument=ins_active,
        field_name="amount",
        value_source=DataProvenanceSource.BANK_CONFIRMED,
        is_confirmed=True,
    )

    ins_expiring = Instrument.objects.create(
        institution=inst1,
        reference_number="FDR-P8-EXPIRING",
        issuing_bank="Punjab National Bank",
        issuing_branch="Connaught Place",
        branch_ifsc="PUNB0005678",
        amount=Decimal("2000000.00"),
        issue_date=date(2021, 6, 1),
        maturity_date=date(2026, 11, 15),
        status=InstrumentStatus.EXPIRING,
        trust_score=85,
    )

    ins_replaced = Instrument.objects.create(
        institution=inst2,
        reference_number="FDR-P8-REPLACED",
        issuing_bank="Canara Bank",
        issuing_branch="Delhi South",
        branch_ifsc="CNRB0009999",
        amount=Decimal("1000000.00"),
        issue_date=date(2020, 1, 1),
        maturity_date=date(2025, 1, 1),
        status=InstrumentStatus.REPLACED,
    )

    ins_discrepancy = Instrument.objects.create(
        institution=inst2,
        reference_number="FDR-P8-DISC",
        issuing_bank="Bank of Baroda",
        issuing_branch="Janpath",
        branch_ifsc="BARB0001111",
        amount=Decimal("3500000.00"),
        issue_date=date(2023, 4, 1),
        maturity_date=date(2028, 4, 1),
        status=InstrumentStatus.DISCREPANCY,
    )
    Discrepancy.objects.create(
        instrument=ins_discrepancy,
        rule_code="AMOUNT_MISMATCH_BANK",
        severity=DiscrepancySeverity.CRITICAL,
        title="Amount mismatch against CBS ledger",
        description="Amount mismatch of Rs. 500,000",
        details={"portal_value": "3500000.00", "bank_value": "3000000.00"},
        is_resolved=False,
    )

    Notification.objects.create(
        recipient=inst_user,
        message="Deposit FDR-P8-EXPIRING approaching maturity in 16 days.",
        channel="EMAIL",
    )

    return {
        "inst1": inst1,
        "inst2": inst2,
        "officer": officer,
        "approver": approver,
        "inst_user": inst_user,
        "ins_active": ins_active,
        "ins_expiring": ins_expiring,
        "ins_replaced": ins_replaced,
        "ins_discrepancy": ins_discrepancy,
    }


@pytest.mark.django_db
class TestAICTEInstitutionSync:
    """Tests for Phase 8 Institution Sync Adapter and REST/Webhook endpoints."""

    def test_mock_adapter_fetch_institution(self):
        """Verifies the mock adapter correctly resolves registered and deterministic IDs."""
        known = default_sync_adapter.fetch_institution("1-100200300")
        assert known is not None
        assert known["aicte_id"] == "1-100200300"
        assert "Delhi Institute of Technology" in known["name"]

        dynamic = default_sync_adapter.fetch_institution("1-998877665")
        assert dynamic is not None
        assert dynamic["aicte_id"] == "1-998877665"

        invalid = default_sync_adapter.fetch_institution("INVALID_ID")
        assert invalid is None

    def test_sync_institution_record_idempotence(self):
        """Verifies idempotent record synchronization and audit trail logging."""
        payload = {
            "aicte_id": "1-SYNC-TEST-01",
            "name": "Sync Test Institute of Technology",
            "institution_type": "Engineering & Technology",
            "state": "Karnataka",
            "district": "Bangalore",
            "pincode": "560001",
            "status": "ACTIVE",
            "contact_email": "registrar@synctest.ac.in",
        }
        inst1 = sync_institution_record(payload, source="UNIT_TEST", actor_username="test_runner")
        assert inst1.aicte_id == "1-SYNC-TEST-01"
        assert inst1.name == "Sync Test Institute of Technology"

        # Update same record
        payload["name"] = "Sync Test Institute of Technology (Updated)"
        inst2 = sync_institution_record(payload, source="UNIT_TEST", actor_username="test_runner")
        assert inst2.id == inst1.id
        assert inst2.name == "Sync Test Institute of Technology (Updated)"

        # Check audit entry using object_id
        audit_entry = AuditEntry.objects.filter(object_id=str(inst1.id)).last()
        assert audit_entry is not None
        assert audit_entry.action == "INSTITUTION_SYNC_UPDATED"

    def test_rest_sync_endpoint_single_institution(self, phase8_setup):
        """Officer can sync a single institution via REST endpoint."""
        client = APIClient()
        client.force_authenticate(user=phase8_setup["officer"])

        response = client.post("/api/institutions/sync/", {"aicte_id": "1-100200300"}, format="json")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["synced_count"] == 1
        assert Institution.objects.filter(aicte_id="1-100200300").exists()

    def test_rest_sync_endpoint_batch_state(self, phase8_setup):
        """Officer can sync institutions batch by state."""
        client = APIClient()
        client.force_authenticate(user=phase8_setup["officer"])

        response = client.post("/api/institutions/sync/", {"state": "Maharashtra"}, format="json")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["synced_count"] >= 1

    def test_rest_sync_forbidden_for_institution_user(self, phase8_setup):
        """Institution users are not allowed to invoke master sync."""
        client = APIClient()
        client.force_authenticate(user=phase8_setup["inst_user"])

        response = client.post("/api/institutions/sync/", {"aicte_id": "1-100200300"}, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_webhook_endpoint_with_valid_hmac_signature(self):
        """Webhook verifies HMAC-SHA256 signature and applies institutional payload."""
        client = APIClient()
        payload = {
            "event": "institution.updated",
            "institution": {
                "aicte_id": "1-WH-SYNC-01",
                "name": "Webhook Verified Polytechnic",
                "institution_type": "Polytechnic",
                "state": "Gujarat",
                "district": "Ahmedabad",
                "status": "ACTIVE",
                "contact_email": "polytechnic@gujarat.edu.in",
            }
        }
        body_bytes = json.dumps(payload).encode("utf-8")
        raw_signature = hmac.new(
            AICTE_SYNC_SECRET.encode("utf-8"),
            body_bytes,
            hashlib.sha256
        ).hexdigest()

        response = client.post(
            "/api/institutions/webhook/",
            data=body_bytes,
            content_type="application/json",
            HTTP_X_AICTE_SIGNATURE=f"sha256={raw_signature}",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["success"] is True
        assert response.json()["status"] == "ACTIVE"
        assert Institution.objects.filter(aicte_id="1-WH-SYNC-01").exists()

    def test_webhook_endpoint_rejects_invalid_signature(self):
        """Webhook rejects requests with tampered or incorrect HMAC signatures."""
        client = APIClient()
        payload = {"event": "institution.updated", "institution": {"aicte_id": "1-FAKE-01"}}
        body_bytes = json.dumps(payload).encode("utf-8")

        response = client.post(
            "/api/institutions/webhook/",
            data=body_bytes,
            content_type="application/json",
            HTTP_X_AICTE_SIGNATURE="sha256=invalidhexsignature0000000000",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid or missing" in response.json()["error"]


@pytest.mark.django_db
class TestImpactMetricsAndBaseline:
    """Tests for Phase 8 Impact Metrics & Legacy Manual Baseline Comparison."""

    def test_impact_metrics_calculation_logic(self, phase8_setup):
        """Impact metrics calculation computes turnaround, avoided steps, and baseline rows."""
        metrics = calculate_impact_metrics()

        assert "summary" in metrics
        assert "breakdown" in metrics
        assert "pending_cases" in metrics
        assert "baseline_comparison" in metrics

        summary = metrics["summary"]
        assert summary["total_instruments_managed"] >= 4
        assert summary["avg_verification_turnaround_days"] > 0
        assert summary["manual_steps_avoided"] > 0
        assert summary["renewals_caught_before_expiry"] >= 2  # 1 replaced + 1 expiring
        assert summary["record_accuracy_pct"] >= 0

        pending = metrics["pending_cases"]
        assert pending["open_discrepancies"] >= 1

        baseline = metrics["baseline_comparison"]
        assert "metrics" in baseline
        metric_keys = [m["key"] for m in baseline["metrics"]]
        assert "turnaround_time" in metric_keys
        assert "manual_steps" in metric_keys
        assert "renewal_tracking" in metric_keys
        assert "record_accuracy" in metric_keys
        assert "audit_immutability" in metric_keys

    def test_impact_metrics_rest_api_access(self, phase8_setup):
        """Officer and Approver can access the Impact Metrics endpoint."""
        client = APIClient()
        client.force_authenticate(user=phase8_setup["officer"])

        response = client.get("/api/reports/impact-metrics/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "summary" in data
        assert "baseline_comparison" in data
        assert len(data["baseline_comparison"]["metrics"]) >= 5

    def test_impact_metrics_forbidden_for_institution(self, phase8_setup):
        """Institution users cannot access bureau-wide impact metrics."""
        client = APIClient()
        client.force_authenticate(user=phase8_setup["inst_user"])

        response = client.get("/api/reports/impact-metrics/")
        assert response.status_code == status.HTTP_403_FORBIDDEN
