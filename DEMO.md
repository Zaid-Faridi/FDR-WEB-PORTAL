# AICTE Security Deposit / FDR Management Portal
## Comprehensive Scripted Demo Walkthrough (`DEMO.md`)

This guide provides a scripted, end-to-end demonstration walkthrough of the AICTE FDR / Security Deposit Management Portal. It follows the core problem statement scenarios and showcases all 10 portal capabilities across the 4 key user roles.

---

### Demo Environment Setup

Before starting the walkthrough, ensure Docker containers are running and the database is seeded:

```bash
# 1. Start all containers
docker compose up -d

# 2. Seed comprehensive demo dataset (25 Institutions, 63 Instruments across all 9 scenarios)
make seed

# 3. Access Portal
# Web UI:       http://localhost:3000
# Backend API:  http://localhost:8000/api/
# OpenAPI Docs: http://localhost:8000/api/docs/
```

---

### Demo Personas & Quick Role Switcher

The portal includes a **Quick Switcher** in the top navigation bar to instantaneously toggle between roles without manual re-login:

| Persona | Role | Username | Password | Key Responsibilities |
| :--- | :--- | :--- | :--- | :--- |
| **Dr. Rajesh Sharma** | Scrutiny Officer | `officer` | `officer123` | Document scrutiny, bank CBS verification, discrepancy flagging |
| **Prof. Sunita Rao** | Approving Authority | `approver` | `approver123` | Final sanction for deposit acceptance, renewal, and release orders |
| **System Administrator** | Bureau Admin | `admin` | `admin123` | Integrity hash checks, simulated date engine, master sync |
| **Registrar (DTU)** | Technical Institution | `inst_dtu` | `inst123` | New FDR submission, discrepancy rectification, renewal requests |

---

## Scripted Demo Scenarios

### Scenario 1: Initial Ingestion & Automated OCR Extraction (Institution Persona)
> **Goal**: Demonstrate how an institution submits a new deposit receipt and how the portal extracts structured data and validates file safety.

1. **Switch Role**: Select `Technical Institution (DTU)` from the Quick Switcher.
2. **Navigate**: Click **"Submit New FDR"** in the top navigation.
3. **Upload Certificate**:
   - Drag and drop any sample FDR PDF or image (e.g. `tests/fixtures/sample_fdr.pdf`).
   - Notice the **file safety scanner** validating magic bytes and MIME headers.
4. **Inspect OCR Extraction**:
   - The portal runs Tesseract OCR and parses the certificate.
   - Observe auto-populated fields: FDR Number, Bank Name, IFSC, Amount, and Maturity Date.
5. **Review Provenance Tag**:
   - Notice that newly submitted fields are tagged with the amber **`INSTITUTION_SUBMITTED`** badge.
6. **Submit**: Click **"Submit Deposit for Scrutiny"**.
   - The instrument enters status `SUBMITTED`.

---

### Scenario 2: Scrutiny Officer Review & Live CBS Bank Verification (Officer Persona)
> **Goal**: Demonstrate how Scrutiny Officers compare claimed data against live bank records and resolve discrepancies.

1. **Switch Role**: Select `Scrutiny Officer (Dr. Rajesh Sharma)`.
2. **Review Worklist**:
   - On the Officer Dashboard, observe the **Risk-Ranked Worklist** highlighting cases needing attention.
   - Click on an instrument with status `SUBMITTED` or `DISCREPANCY` (e.g. `FDR-SBI-2026-9011`).
3. **Inspect Provenance Reconciliation Panel**:
   - View the side-by-side reconciliation interface comparing:
     - Column 1: **Institution Claimed** (Amber)
     - Column 2: **CBS Bank Confirmed** (Emerald)
4. **Trigger Live Bank Verification**:
   - Click **"Query Core Banking System (CBS)"**.
   - The pluggable bank adapter queries the simulated CBS API.
   - Observe the **Trust Score** calculate dynamically (e.g., 98/100) based on field match consistency, lien marking, and joint holder title ("AICTE and Institution Name").
5. **Examine Automated Discrepancies**:
   - If an amount or maturity date differs, see the automated discrepancy card:
     - `Severity: CRITICAL`
     - Description: *"Claimed Amount ₹50,00,000 does not match CBS Ledger Amount ₹45,00,000."*
   - Click **"Issue Rectification Notice"** to notify the institution registrar automatically.

---

### Scenario 3: Automated Validity Tracking & Simulated Date Time-Travel (Admin Persona)
> **Goal**: Demonstrate how the portal tracks maturing instruments and executes automated 90/60/30/7-day reminders and multi-tier escalations.

1. **Switch Role**: Select `Bureau Admin (System Administrator)`.
2. **Access Date Simulator**:
   - In the top navigation, locate the **"🕒 Simulated Date Engine"** widget.
   - Check the current effective date (e.g., October 30, 2026).
3. **Time-Travel Forward**:
   - Set the simulated date forward by **60 days** (e.g., to December 30, 2026).
   - Click **"Apply Simulated Date & Run Daily Monitoring Job"**.
4. **Verify Automated Lifecycle Shifts**:
   - Instruments whose maturity now falls within the 60-day window automatically transition from `ACTIVE` to `EXPIRING`.
   - Instruments past maturity date transition to `MATURED`.
5. **Inspect Automated Reminders & Escalations**:
   - Navigate to the **Notifications Queue**.
   - Observe automated reminder notifications generated at configured offsets (90d, 60d, 30d, 7d).
   - For unresolved overdue cases, notice the **Escalation Ladder** firing:
     - Tier 1: Institution Registrar
     - Tier 2: Scrutiny Officer
     - Tier 3: Senior Bureau Officer
     - Tier 4: Regulation Bureau Advisor / Director

---

### Scenario 4: Linked Replacement / Renewal Chain & Historical Timeline (Institution & Officer)
> **Goal**: Demonstrate how maturing deposits are replaced by new FDRs while preserving full immutable historical lineage.

1. **Switch Role**: Select `Technical Institution (DTU)`.
2. **Initiate Replacement**:
   - Open an expiring deposit (e.g. `FDR-PNB-2026-8802`).
   - Click **"Submit Replacement FDR"**.
   - Enter the new FDR Number (`FDR-PNB-2026-RENEW-01`), new maturity date (5 years forward), and upload the renewed deposit certificate.
3. **Switch Role**: Select `Scrutiny Officer`.
4. **Verify Replacement**:
   - Open the renewal request.
   - Verify CBS credentials for the replacement instrument and click **"Approve Replacement"**.
5. **View Interactive Lineage Timeline**:
   - Notice the state transitions:
     - Predecessor FDR transitions to **`REPLACED`**.
     - Successor FDR transitions to **`ACTIVE`**.
   - Click **"View Lineage Timeline"** to view the interactive chain showing the ancestor FDR, date of rollover, scrutiny notes, and replacement link.

---

### Scenario 5: Strict 4-Stage Release / Refund Workflow (Approving Authority Persona)
> **Goal**: Demonstrate the multi-stakeholder release pipeline with automated statutory precondition checks.

1. **Switch Role**: Select `Technical Institution`.
2. **Request Release**:
   - For a matured 10-year deposit (e.g. `FDR-CAN-2026-RELEASE-REQ`), click **"Request Deposit Release & Refund"**.
   - Attach the institutional closure / compliance certificate.
3. **Switch Role**: Select `Scrutiny Officer`.
4. **Scrutiny Preconditions Check**:
   - Open the release dossier.
   - The portal evaluates automated statutory preconditions:
     - [x] Instrument CBS Bank-Verified
     - [x] Zero Open Discrepancies
     - [x] Mandatory Lock-in Tenure Completed (8-10 years)
     - [x] No Vigilance / Compliance Hold
   - Click **"Recommend for Final Release"**.
5. **Switch Role**: Select `Approving Authority (Prof. Sunita Rao)`.
6. **Approving Authority Sanction**:
   - Open the approval queue.
   - Review side-by-side evidence, scrutiny checklist, and audit history.
   - Enter AICTE Sanction Order Reference: `AICTE/REG/FDR-REL/2026/089`.
   - Click **"Grant Release Sanction & Issue Refund Order"**.
   - The instrument immutably transitions to **`RELEASED`**, and an automated sanction notification is dispatched to the institution registrar and bank branch manager.

---

### Scenario 6: Officer Dashboard, Risk-Ranked Worklist & Compliance Reports
> **Goal**: Demonstrate executive oversight, risk analytics, and exportable regulatory reporting.

1. **Switch Role**: Select `Scrutiny Officer`.
2. **View Officer Dashboard**:
   - Inspect summary counter cards: Total Value Locked (₹ Cr), Active, Expiring (30/60/90-day buckets), Matured, Discrepancies.
   - Inspect the **Bank Exposure Breakdown** chart showing deposit concentration across Public Sector and Private banks.
3. **Filter & Search**:
   - Filter instruments by State (`Maharashtra`), Bank (`State Bank of India`), and Status (`EXPIRING`).
   - Save filter preset as `"Maharashtra SBI Expiring"`.
4. **Export Standardized Compliance Reports**:
   - In the **Reports** menu, select one of the 6 standard compliance formats:
     - *Upcoming Maturities (Next 90 Days)*
     - *Pending CBS Verifications*
     - *Unresolved Discrepancies & Flagged Cases*
     - *Missing / Incomplete Documentation*
     - *Overdue Maturation & Escalation Register*
     - *State & Institution-wise Summary*
   - Click **"Download CSV"** or **"Generate Official PDF"** (formatted with AICTE headers, pagination, and official styling).
5. **Weekly Summary Email**:
   - Click **"Dispatch Weekly Summary Report"** to trigger the automated compliance digest email.

---

### Scenario 7: Immutable Audit Trail & Cryptographic Hash Chain Tamper Detection
> **Goal**: Demonstrate Merkle-style cryptographic chaining and prove non-repudiation and tamper resistance.

1. **Switch Role**: Select `Bureau Admin`.
2. **Inspect Audit Trail**:
   - Open **Audit & Security** in the navigation bar.
   - View chronological event entries: Actor, Role, IP Address, Timestamp, Action, Previous State, New State, and SHA-256 Hash.
   - Notice that each entry's hash incorporates the hash of the preceding record:
     $$\text{Hash}_n = \text{SHA256}(\text{Hash}_{n-1} + \text{Actor} + \text{Action} + \text{Timestamp} + \text{State})$$
3. **Run Cryptographic Integrity Check**:
   - Click **"Verify Hash Chain Integrity"**.
   - The backend validates all blocks sequentially.
   - Green badge displays: **"✓ Hash Chain Valid (60+ blocks verified, 0 broken links)"**.
4. **ORM / API Immutability**:
   - Note that `AuditEntry.save()` and `AuditEntry.delete()` are locked at both model and PostgreSQL database trigger levels. Any direct update attempt is blocked with a security exception.

---

### Scenario 8: Central AICTE System Integration & Webhook Sync
> **Goal**: Demonstrate zero-duplicate entry by synchronizing master technical institution records via REST and Webhook endpoints.

1. **REST Sync Demonstration**:
   - In terminal, invoke the master synchronization endpoint for a technical institution:
   ```bash
   curl -X POST http://localhost:8000/api/institutions/sync/ \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <OFFICER_TOKEN>" \
     -d '{"aicte_id": "1-100200300"}'
   ```
   - Response: `{"success": true, "synced_count": 1, "institutions": ["Delhi Institute of Technology & Management"]}`.
2. **Cryptographic Webhook Ingestion**:
   - Send an event-driven institutional update with HMAC-SHA256 signature (`X-AICTE-Signature`):
   ```bash
   # Generates HMAC signature using shared secret and submits payload
   python -c "
   import hmac, hashlib, json, requests
   payload = json.dumps({'event': 'institution.updated', 'institution': {'aicte_id': '1-400500600', 'name': 'Mumbai College of Engineering & Research', 'status': 'ACTIVE', 'state': 'Maharashtra'}}).encode('utf-8')
   sig = hmac.new(b'aicte-sync-secret-key-2026-secure', payload, hashlib.sha256).hexdigest()
   r = requests.post('http://localhost:8000/api/institutions/webhook/', data=payload, headers={'Content-Type': 'application/json', 'X-AICTE-Signature': f'sha256={sig}'})
   print('Status:', r.status_code, r.json())
   "
   ```
   - Response: `{"status": "SUCCESS", "event": "institution.updated"}`.

---

### Scenario 9: Impact Metrics & ROI Baseline Comparison
> **Goal**: Demonstrate measurable operational benefits compared to the legacy manual paper register baseline.

1. **Navigate**: In the top navigation, click **"📈 Impact & ROI Metrics"**.
2. **Inspect Empirical Key Performance Indicators (KPIs)**:
   - **Average Verification Turnaround**: **1.4 Days** (vs 21 business days manual — **93.3% reduction**).
   - **Manual Touchpoints Avoided**: **400+ operational touchpoints** saved via automated reminders, OCR extractions, and bank CBS reconciliations.
   - **Renewals Proactively Caught**: **98.5% compliance** (eliminating historical 38% unnoticed expiry lapses).
   - **Bank-Confirmed Record Accuracy**: **82.5% authenticated data** (vs 0% bank-confirmed under unverified paper claims).
3. **Review Seeded Baseline Comparison Table**:
   - Review the detailed comparison table contrasting legacy paper registers against the digital portal:
     - End-to-end turnaround
     - Manual touchpoints per case
     - Proactive expiry tracking
     - CBS bank confirmation share
     - Audit trail & tamper detection (Paper books vs SHA-256 Merkle chain)

---

## Scenario Summary Matrix

| Scenario | Primary User Persona | Core Problem Solved | Key Verification Signal |
| :--- | :--- | :--- | :--- |
| **1. Submission & OCR** | Technical Institution | Manual data entry errors, forged certificates | Amber `INSTITUTION_SUBMITTED` badge, magic byte check |
| **2. Scrutiny & CBS** | Scrutiny Officer | Unverified bank claims, fake FDR certificates | Emerald `BANK_CONFIRMED` badge, Trust Score (98/100) |
| **3. Validity & Time-Travel**| Bureau Admin | Lapsed FDRs, missed renewals, manual reminder burden | Simulated date advancement, 90/60/30/7d notifications |
| **4. Renewal Chain** | Institution / Officer | Lost paper lineage across multi-year rollovers | Interactive ancestor timeline, `REPLACED` $\to$ `ACTIVE` |
| **5. Release Workflow** | Approving Authority | Unauthorized refunds, missing statutory checks | 4-stage precondition checklist, sanction order ref |
| **6. Reports & Risk** | Scrutiny Officer | Lack of executive oversight, bank exposure risk | PDF/CSV compliance exports, risk worklist |
| **7. Tamper Detection** | Bureau Admin | Vigilance vulnerabilities, unauthorized edits | SHA-256 Merkle chain verification, DB trigger lock |
| **8. System Integration** | Integration Engineer | Duplicate institutional entry across AICTE portals | REST sync adapter, HMAC-SHA256 signed webhooks |
| **9. Impact & ROI** | Executive Leadership | Justification of digital transformation value | 93.3% turnaround reduction, 85.7% touchpoint saving |

---

*AICTE Regulation Bureau — Technical Documentation & Verification Portal (2026)*
