import pytest
from apps.common.models import AuditLog, DataProvenanceSource
from apps.common.audit import record_audit_event

@pytest.mark.django_db
def test_record_audit_event():
    initial_count = AuditLog.objects.count()
    log = record_audit_event(
        action="FDR_STATUS_UPDATED",
        entity_type="FDRDeposit",
        entity_id="101",
        actor_username="officer_verma",
        actor_role="Scrutiny Officer",
        previous_state={"status": "SUBMITTED"},
        new_state={"status": "SCRUTINY_IN_PROGRESS"},
        ip_address="192.168.1.10",
        metadata={"notes": "Initiated verification against SBI branch"}
    )
    assert AuditLog.objects.count() == initial_count + 1
    assert log.action == "FDR_STATUS_UPDATED"
    assert log.actor_username == "officer_verma"
    assert log.previous_state["status"] == "SUBMITTED"
    assert log.new_state["status"] == "SCRUTINY_IN_PROGRESS"

def test_provenance_choices_defined():
    sources = [choice[0] for choice in DataProvenanceSource.choices]
    assert 'INSTITUTION_SUBMITTED' in sources
    assert 'OFFICER_ENTERED' in sources
    assert 'BANK_CONFIRMED' in sources
