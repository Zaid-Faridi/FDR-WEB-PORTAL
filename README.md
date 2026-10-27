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
   The portal includes a clearly labelled sandbox mock: `apps.bank_adapters.mock_adapter.MockBankVerificationAdapter`.

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
