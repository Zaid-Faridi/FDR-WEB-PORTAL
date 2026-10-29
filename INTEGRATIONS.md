# AICTE FDR Portal: System Integrations Guide (Phase 8)

This guide documents the integration readiness, adapter interfaces, REST synchronization endpoints, inbound webhook receivers, and Core Banking System (CBS) connectivity for the AICTE Security Deposit & Fixed Deposit Receipt Management Portal.

---

## 1. Integration Architecture Overview

The FDR Portal eliminates duplicate data entry for technical institutions by interfacing directly with existing AICTE Enterprise systems (such as the Central Approval Bureau MIS and e-Governance Portals) as well as Scheduled Commercial Banks.

```
 +-------------------------------------+
 |   Existing AICTE Approval MIS /     |
 |   e-Governance Central Database     |
 +------------------+------------------+
                    |
          +---------+---------+
          |                   |
 [Inbound Webhooks]     [On-Demand Sync]
   (X-AICTE-Signature)    (REST Pull)
          |                   |
          v                   v
 +-------------------------------------+
 |  AICTE FDR Management Portal Engine |
 |  - sync_adapter.py (Pluggable)      |
 |  - Append-Only Audit Logging        |
 |  - Field Provenance Tracker         |
 +------------------+------------------+
                    |
           [CBS Mock / Live Adapter]
          (ISO 8583 / REST CBS / SFMS)
                    |
                    v
 +-------------------------------------+
 |   Scheduled Commercial Banks (CBS)  |
 |   (SBI, PNB, Canara, BoB, HDFC)     |
 +-------------------------------------+
```

---

## 2. Institution Master Data Synchronization

### 2.1 On-Demand Pull Synchronization (`POST /api/institutions/sync/`)
Allows administrators or automated background jobs to pull the latest institutional records directly from the AICTE Central Approval Directory.

#### Headers
```http
Authorization: Bearer <JWT_ACCESS_TOKEN>
Content-Type: application/json
```

#### Request Payload: Single Institution
```json
{
  "aicte_id": "1-100200300"
}
```

#### Request Payload: Batch Sync by State or Global
```json
{
  "state": "Maharashtra"
}
```
*Or:*
```json
{
  "sync_all": true
}
```

#### Success Response (`200 OK`)
```json
{
  "success": true,
  "message": "Institution 'Delhi Institute of Technology & Management' successfully synced from central AICTE directory.",
  "institution": {
    "id": 1,
    "aicte_id": "1-100200300",
    "name": "Delhi Institute of Technology & Management",
    "institution_type": "Engineering & Technology",
    "address": "Sector 14, Dwarka",
    "state": "Delhi",
    "district": "South West Delhi",
    "pincode": "110078",
    "status": "ACTIVE",
    "contact_email": "registrar@ditm-delhi.edu.in",
    "contact_phone": "+91-11-28080001",
    "created_at": "2026-10-27T02:00:00Z",
    "updated_at": "2026-10-30T00:50:00Z"
  }
}
```

#### cURL Example
```bash
curl -X POST "http://localhost:8000/api/institutions/sync/" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"aicte_id": "1-100200300"}'
```

---

### 2.2 Event-Driven Inbound Webhook (`POST /api/institutions/webhook/`)
External AICTE portals dispatch real-time events whenever an institution profile changes, is approved, or undergoes regulatory status updates.

#### Headers
```http
Content-Type: application/json
X-AICTE-Signature: sha256=<HMAC_SHA256_HEX_DIGEST>
```

#### HMAC Signature Generation
The signature is computed over the raw request payload bytes using the shared secret (`AICTE_SYNC_WEBHOOK_SECRET`):
```python
import hmac, hashlib
signature = hmac.new(secret.encode('utf-8'), payload_bytes, hashlib.sha256).hexdigest()
# Header: X-AICTE-Signature: sha256={signature}
```

#### Inbound Webhook Payload
```json
{
  "event": "institution.updated",
  "timestamp": "2026-10-30T00:45:00Z",
  "data": {
    "aicte_id": "1-550660770",
    "name": "Pune College of Pharmaceutical Sciences",
    "institution_type": "Pharmacy",
    "address": "Erandwane, Karve Road",
    "state": "Maharashtra",
    "district": "Pune",
    "pincode": "411038",
    "status": "ACTIVE",
    "contact_email": "director@pcps-pune.edu.in",
    "contact_phone": "+91-20-25440005"
  }
}
```

#### Acknowledgement Response (`200 OK`)
```json
{
  "success": true,
  "event": "institution.updated",
  "aicte_id": "1-550660770",
  "status": "ACTIVE",
  "message": "Webhook processed: Institution 1-550660770 successfully updated."
}
```

---

## 3. Pluggable Adapter Interfaces (`sync_adapter.py`)

All integration points adhere to strict abstract base classes to allow effortless transition between the demo mock implementations and production enterprise ESBs.

```python
class AICTEInstitutionSyncAdapter(ABC):
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
        """Verifies HMAC-SHA256 signature from the central AICTE webhook dispatcher."""
        pass
```

---

## 4. Core Banking System (CBS) Adapter Integration

The portal integrates with Core Banking Systems via `apps/bank_adapters/base.py`:
- **Interface**: `BankVerificationAdapter`
- **Primary Method**: `verify_instrument(instrument: Instrument) -> BankVerificationResult`
- **Returned Provenance Fields**:
  - `account_active`: boolean confirmation from branch records.
  - `lien_confirmed`: lien explicitly marked in favor of Member Secretary AICTE.
  - `balance_matches`: deposit amount matches CBS general ledger.
  - `maturity_date`: contractual maturity recorded in CBS.
  - `joint_holder`: joint names recorded in bank database.
- **Mock CBS Engine**: Simulates SBI, PNB, Canara, and BoB verification latency, trust score computation, and automatic discrepancy detection.
