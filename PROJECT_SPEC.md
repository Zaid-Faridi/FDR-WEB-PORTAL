# AICTE Security Deposit / FDR Management Portal
## Technical & Functional Specification Document

### 1. Purpose & Objectives
The **AICTE Security Deposit / FDR Management Portal** is a secure, centralized web portal designed for the **AICTE Regulation Bureau** to manage the complete lifecycle of technical institution security deposits and Fixed Deposit Receipts (FDRs). 

It replaces disparate manual and semi-digital records with a unified, tamper-evident digital workflow covering:
1. **Submission**: Initial deposit and FDR certificate submission by technical institutions.
2. **Verification & Discrepancy Detection**: Multi-tier scrutiny, automated cross-checks, and bank confirmation workflows.
3. **Validity & Maturity Tracking**: Proactive tracking of FDR tenures, maturity dates, and encumbrance/lien status.
4. **Renewal & Replacement Monitoring**: Managed workflows for maturing or invalid deposits requiring roll-overs or replacement instruments.
5. **Release & Refund**: Multi-stakeholder approval pipeline for the lawful release, refund, or forfeiture of deposits upon fulfillment of statutory requirements.
6. **Audit & Compliance**: Complete chronological event logging for regulatory inspections, vigilance audits, and legal compliance.

---

### 2. User Roles & Access Control
Access to the portal is governed by Role-Based Access Control (RBAC) across four distinct roles:

1. **Institution (Applicant / Representative)**:
   - Registers and manages institutional profile (AICTE Permanent Institute ID, approval status, category).
   - Submits FDR and security deposit details along with digital copies of deposit receipts and joint FDR agreements.
   - Responds to discrepancy notices or requests for clarification issued during scrutiny.
   - Tracks deposit status, validity, renewal demands, and initiates release/refund requests.

2. **Scrutiny Officer (Regulation Bureau Officer)**:
   - Verifies submitted deposit certificates against bank branch details and AICTE approval stipulations.
   - Triggers bank verification requests and evaluates responses received from financial institutions.
   - Flags discrepancies (amount mismatch, tenure shortfall, invalid joint-account naming, encumbrance issues).
   - Prepares verification reports and makes recommendations for approval, renewal, or rejection.

3. **Approving Authority (Bureau Head / Advisor / Member Secretary)**:
   - Reviews scrutiny recommendations with side-by-side verification evidence.
   - Grants final approval for FDR acceptance, renewal sanction, or release/refund orders.
   - Authorizes escalation procedures, penalties, or forfeiture proceedings for non-compliant institutions.

4. **Admin (System & Security Administrator)**:
   - Manages user accounts, institutional directory, role provisioning, and system configurations.
   - Oversees audit logs, API integration health, alert queues, and system backups.
   - Configures bank verification adapters, policy thresholds (alert lead times, SLA escalation windows), and master data.

---

### 3. The 10 Core Capabilities

1. **Centralized Repository**:
   - Single source of truth for all security deposits, FDRs, bank guarantees, and joint-lien agreements across all AICTE-approved institutions nationwide.
   - Comprehensive searchable index by Institution ID, FDR Number, Bank Branch, State, Program, and Status.

2. **Digital Document Management**:
   - Secure digital storage and indexing of scanned FDR certificates, bank confirmation letters, joint pledge deeds, and encashment mandates.
   - SHA-256 document fingerprinting to guarantee document integrity and prevent tampering.

3. **Verification and Discrepancy Detection**:
   - Comparison engine that automatically checks claimed institution inputs against bank-confirmed records and AICTE norms (required deposit amount based on programs/intake, correct joint holder naming format e.g. "Institution Name and AICTE", minimum tenure).
   - Real-time discrepancy flagging highlighting field-level differences.

4. **Automated Validity and Maturity Tracking**:
   - Continuous monitoring of deposit start dates, terms, and scheduled maturity dates.
   - Status transitions (e.g. `Active`, `Expiring Soon`, `Matured`, `Overdue Renewal`, `Lien Enforced`, `Released`).

5. **Renewal/Replacement Monitoring**:
   - Standardized tracking for renewals, auto-rollovers, and replacement instruments.
   - Traceability linking renewed FDRs to their ancestor FDR records to preserve historical lineage.

6. **Release/Refund Workflow**:
   - Strict state-machine driven workflow for the lawful release or refund of FDRs after the mandatory lock-in period (e.g., 8–10 years for new colleges or program closure).
   - Requires no-objection certificates (NOC), Scrutiny recommendation, Approving Authority digital sign-off, and bank lien-revocation letters.

7. **Automated Alerts and Escalation**:
   - Scheduled automated notifications (email, dashboard notifications, SMS alerts) triggered at configured intervals (e.g. 90, 60, 30, and 15 days prior to maturity).
   - Automated SLA-driven escalation to senior bureau officers if critical renewal or discrepancy resolution deadlines elapse.

8. **Dashboard and Reports**:
   - Executive dashboard presenting Bureau-level analytics: total locked deposit value, expiring FDRs distribution, bank-wise deposit exposure, state/regional breakdown, and pending scrutiny queue.
   - Standardized exportable compliance reports (PDF, CSV, Excel) for executive and vigilance reviews.

9. **Audit Trail and Access Control**:
   - Immutable audit logging of every creation, view of sensitive details, modification, status transition, document download, and approval decision.
   - Captures Actor, IP Address, Timestamp, Action Type, Previous State, New State, and Context Metadata.

10. **Integration Readiness and Data Security**:
    - Pluggable external interfaces for Core Banking Systems (CBS) / Public Financial Management System (PFMS) / SFMS (Structured Financial Messaging System) / AICTE Approval Portal.
    - End-to-end data security: encryption at rest, TLS 1.3 in transit, strict RBAC, no plaintext storage of credentials, and security headers.

---

### 4. Key Data Source Provenance Principle
Every data attribute regarding a deposit instrument (FDR Number, Bank Name, Branch IFSC, Principal Amount, Interest Rate, Deposit Date, Maturity Date, Lien Marking Status, Joint Beneficiary Title) explicitly stores its provenance:
- **`INSTITUTION_SUBMITTED`** (Claimed values entered/uploaded by the institution)
- **`OFFICER_ENTERED`** (Adjusted or verified by AICTE Scrutiny Officers during manual inspection)
- **`BANK_CONFIRMED`** (Directly verified and confirmed via Bank Verification Adapters / APIs)

**UI Rule**: The web interface must **always visually distinguish** between claimed data and bank-confirmed data (e.g., distinct badges, color-coded validation tags, side-by-side reconciliation panels).

---

### 5. Pluggable Bank Verification Architecture
To ensure compatibility across banks with differing technological readiness, all bank verification calls pass through an abstracted adapter interface:
```python
class BankVerificationAdapter(ABC):
    @abstractmethod
    def verify_fdr(self, fdr_details: FDRVerificationRequest) -> FDRVerificationResponse:
        pass

    @abstractmethod
    def check_lien_status(self, fdr_details: FDRVerificationRequest) -> LienStatusResponse:
        pass
```
- **Pluggable Architecture**: Implementations can be swapped via configuration (`BANK_ADAPTER_CLASS`).
- **Clearly Labelled MOCK Implementation**: Includes a comprehensive `MockBankVerificationAdapter` simulating realistic bank responses, simulated network latency, edge-case discrepancies (lien missing, amount variance, wrong account name), and bank confirmation status without requiring live banking credentials.

---

### 6. Architectural Stack
- **Backend**: Python 3.12, Django 5.x, Django REST Framework (DRF), Celery 5.x, Redis 7.x
- **Database**: PostgreSQL 16
- **Frontend**: React 18 / 19, TypeScript, Vite, Modern Vanilla CSS / Design System
- **Testing**: `pytest` & `pytest-django` for backend, modern test suite
- **DevOps & Containerization**: Docker, Docker Compose, automated healthchecks
- **Configuration**: Strictly environment-variable driven (12-Factor App) with `.env.example` templates; zero hardcoded secrets.
