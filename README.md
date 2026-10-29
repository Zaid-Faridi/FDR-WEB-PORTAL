# AICTE Security Deposit & FDR Management Portal

Production-minded monorepo prototype for the **AICTE Regulation Bureau**, managing the end-to-end lifecycle of technical institution security deposits and Fixed Deposit Receipts (FDRs).

---

## Architecture & Technology Stack

| Layer | Technology | Details |
| :--- | :--- | :--- |
| **Backend** | Python 3.12, Django 5.x, DRF | REST API, state machines, audit log subsystem |
| **Database** | PostgreSQL 16 | Relational storage with strict schema integrity |
| **Worker & Cache**| Celery 5.x, Redis 7.x | Asynchronous jobs, reminders, escalation scheduling |
| **Frontend** | React 18, TypeScript, Vite | Modern UI, strict separation of claimed vs confirmed |
| **Bank Interface**| Pluggable Adapter Pattern | Swappable CBS/SFMS interface with a clearly labelled `MockBankVerificationAdapter` |
| **Testing** | `pytest`, `pytest-django` | Unit and integration test coverage |
| **Orchestration**| Docker & Docker Compose | Single-command local dev and CI execution |

---

## Core Principles & Design Rules

1. **Data Provenance Source Tracking**:
   Every data field records whether it was:
   - `INSTITUTION_SUBMITTED` (Claimed by the institution)
   - `OFFICER_ENTERED` (Recorded by Regulation Bureau Scrutiny Officers)
   - `BANK_CONFIRMED` (Verified directly by bank APIs / CBS)
   *Rule: The UI always clearly visually distinguishes "claimed" from "bank-confirmed".*

2. **Pluggable Bank Verification**:
   All bank inquiries operate through the `BankVerificationAdapter` interface (`apps.bank_adapters.base.BankVerificationAdapter`).
   The portal includes a clearly labelled sandbox mock: `apps.bank_adapters.mock_adapter.MockBankAdapter` (`MockBankVerificationAdapter`).

### How a Real Bank API Plugs In
To integrate a real Core Banking System (CBS), SFMS, or open banking gateway (e.g. SBI e-Treasury, PNB Open Banking, or ICICI Corporate API):

1. **Subclass `BankVerificationAdapter`**:
   Create a module under `backend/apps/bank_adapters/` (e.g., `sbi_adapter.py`):
   ```python
   import requests
   from apps.bank_adapters.base import BankVerificationAdapter, FDRVerificationRequest, FDRVerificationResponse

   class SBICoreBankingAdapter(BankVerificationAdapter):
       adapter_name = "State Bank of India CBS API Gateway"
       is_mock = False

       def __init__(self):
           self.api_url = settings.SBI_API_ENDPOINT
           self.client_id = settings.SBI_CLIENT_ID
           self.cert_path = settings.SBI_CLIENT_CERT_PATH

       def verify(self, fdr_number: str, bank: str) -> dict:
           # Call bank REST / mTLS API
           payload = {"fdr_reference": fdr_number, "bank_identifier": bank}
           response = requests.post(f"{self.api_url}/v1/fdr/verify", json=payload, cert=self.cert_path, timeout=10)
           data = response.json()
           return {
               "status": "CONFIRMED" if data.get("is_valid") else "NOT_FOUND",
               "fdr_number": fdr_number,
               "bank": bank,
               "confirmed_amount": data.get("deposit_amount"),
               "confirmed_issue_date": data.get("issue_date"),
               "confirmed_maturity_date": data.get("maturity_date"),
               "lien_marked": data.get("lien_registered_aicte", False),
               "lien_in_favor_of": data.get("lien_holder"),
               "bank_reference_id": data.get("cbs_txn_ref"),
               "verified_at": datetime.now().isoformat(),
               "adapter_name": self.adapter_name,
               "is_mock": False,
               "discrepancies": data.get("reconciliation_errors", []),
               "raw_payload": data,
           }

       def verify_fdr(self, request: FDRVerificationRequest) -> FDRVerificationResponse:
           # Optional detailed wrapper for full request objects
           ...

       def check_lien_status(self, fdr_number: str, branch_ifsc: str):
           # Specialized lien inquiry
           ...
   ```

2. **Configure Environment Variable**:
   In `.env` or production deployment configuration:
   ```bash
   BANK_ADAPTER_CLASS=apps.bank_adapters.sbi_adapter.SBICoreBankingAdapter
   ```
   The `get_bank_adapter()` factory in `apps/bank_adapters/factory.py` dynamically imports and instantiates the configured adapter.

---

### Rule-Based Discrepancy & Trust Score Engine
Phase 3 introduces an automated regulatory discrepancy engine with severity ratings (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`):
- **Duplicate Checks**: Duplicate FDR certificate reference number across institutions; duplicate SHA-256 document fingerprints.
- **Tenure & Date Logic**: Maturity date on or prior to issue date; issue date in future; tenure < 1 year.
- **Regulatory Norms**: Deposit amount below mandatory AICTE category minimums (e.g., ₹1 Crore for Technical Campus, ₹50 Lakhs for Engineering, ₹35 Lakhs for Management/Pharmacy, ₹25 Lakhs for Polytechnic).
- **Lien & Document Integrity**: Unmarked AICTE lien; missing bank confirmation letter or joint pledge deed; missing FDR scan.
- **Bank Reconciliation**: Discrepancies between claimed vs bank-confirmed amount, dates, or missing bank records.
- **Automated Trust Score**: A composite score (0-100) reflecting bank confirmation share (40%), discrepancy-free cleanliness (40%), and document completeness (20%).
- **Optical Character Recognition (OCR)**: `pytesseract`-powered scan text extraction to pre-fill submission forms and identify OCR vs typed mismatches.

---

3. **Audit Trail**:
   Every state change writes an immutable audit record (`AuditLog`) capturing actor, role, action, previous state, new state, IP address, and timestamp.

4. **Zero Hardcoded Secrets**:
   All secrets, URLs, and configurations are loaded via environment variables (`.env`).

---

## Monorepo Layout

```
.
├── PROJECT_SPEC.md              # Complete technical & functional specifications
├── docker-compose.yml           # Multi-container orchestration (db, redis, backend, celery, frontend)
├── Makefile                     # CLI shortcuts (make up, make test, make seed)
├── .env.example                 # Environment variables template
├── .env                         # Local runtime environment file
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── manage.py
│   ├── pytest.ini
│   ├── entrypoint.sh
│   ├── aicte_fdr_core/          # Django core project configuration & Celery app
│   ├── apps/
│   │   ├── common/              # Data provenance enums, base models, AuditLog subsystem
│   │   ├── bank_adapters/       # Pluggable adapter interface & MockBankVerificationAdapter
│   │   └── core/                # Health check API, seed commands
│   └── tests/                   # Pytest test suite (health, adapters, audit)
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── vite.config.ts
    ├── index.html
    └── src/
        ├── App.tsx              # Portal dashboard shell with live health check
        ├── index.css            # Modern AICTE theme
        └── types/provenance.ts  # Provenance & role typing
```

---

## Quickstart Instructions

### 1. Prerequisites
- Docker Engine & Docker Compose
- `make` (optional, can run `docker compose` directly)

### 2. Launch All Services
```bash
make up
# Or: docker compose up -d
```

Check logs:
```bash
make logs
# Or: docker compose logs -f
```

### 3. Run Backend Test Suite
```bash
make test
# Or: docker compose run --rm backend pytest
```

### 4. Seed Foundational Accounts & Audit Records
```bash
make seed
# Or: docker compose run --rm backend python manage.py seed_data
```

### 5. Access the Applications
- **Frontend Portal**: [http://localhost:5173](http://localhost:5173)
- **Backend API Health Check**: [http://localhost:8000/api/health/](http://localhost:8000/api/health/)
- **Django Admin Portal**: [http://localhost:8000/admin/](http://localhost:8000/admin/)
  - *Default Seed Credentials*: `aicte_admin` / `Admin@AICTE2026`

---

## Stopping the Services
```bash
make down
# Or: docker compose down
```
