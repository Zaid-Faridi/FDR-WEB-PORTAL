import hashlib
from django.db import models
from django.conf import settings
from apps.common.models import DataProvenanceSource

class InstrumentStatus(models.TextChoices):
    SUBMITTED = 'Submitted', 'Submitted'
    UNDER_SCRUTINY = 'Under Scrutiny', 'Under Scrutiny'
    VERIFIED = 'Verified', 'Verified'
    ACTIVE = 'Active', 'Active'
    EXPIRING = 'Expiring', 'Expiring'
    MATURED = 'Matured', 'Matured'
    RENEWED = 'Renewed', 'Renewed'
    REPLACED = 'Replaced', 'Replaced'
    RELEASE_REQUESTED = 'Release Requested', 'Release Requested'
    RELEASED = 'Released', 'Released'
    DISCREPANCY = 'Discrepancy', 'Discrepancy'
    REJECTED = 'Rejected', 'Rejected'


class InstrumentType(models.TextChoices):
    FDR = 'FDR', 'Fixed Deposit Receipt'
    SECURITY_DEPOSIT = 'SECURITY_DEPOSIT', 'Security Deposit'
    BANK_GUARANTEE = 'BANK_GUARANTEE', 'Bank Guarantee'


class Instrument(models.Model):
    """
    Security Deposit / FDR instrument submitted by a technical institution.
    """
    institution = models.ForeignKey(
        'institutions.Institution',
        on_delete=models.CASCADE,
        related_name='instruments',
        help_text="Owning technical institution"
    )
    instrument_type = models.CharField(
        max_length=50,
        choices=InstrumentType.choices,
        default=InstrumentType.FDR
    )
    reference_number = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="FDR Certificate Number or Bank Deposit Reference"
    )
    issuing_bank = models.CharField(max_length=200, db_index=True)
    issuing_branch = models.CharField(max_length=200)
    branch_ifsc = models.CharField(max_length=20, db_index=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    issue_date = models.DateField()
    maturity_date = models.DateField(db_index=True)
    lien_in_favour_of_aicte = models.BooleanField(
        default=False,
        help_text="Flag indicating whether lien is officially marked in favor of AICTE"
    )
    joint_holder_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="E.g., Institution Name and Member Secretary AICTE"
    )
    status = models.CharField(
        max_length=30,
        choices=InstrumentStatus.choices,
        default=InstrumentStatus.SUBMITTED,
        db_index=True
    )
    trust_score = models.IntegerField(
        default=0,
        help_text="Automated Trust Score (0-100) based on bank confirmation, discrepancy clean state, and documents"
    )
    ocr_extracted_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Data extracted via pytesseract OCR from uploaded FDR certificate scan"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='created_instruments'
    )

    # Phase 5: Renewal / Replacement Lineage Tracking
    replaces = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='replacement_instruments',
        help_text="Ancestor instrument being replaced or renewed"
    )
    renewal_type = models.CharField(
        max_length=50,
        blank=True,
        choices=[('RENEWAL', 'Tenure Renewal'), ('REPLACEMENT', 'Replacement Instrument')],
        default='REPLACEMENT'
    )

    # Phase 5: Release / Refund Workflow Tracking
    release_requested_at = models.DateTimeField(null=True, blank=True)
    release_justification = models.TextField(blank=True)
    scrutiny_recommended_at = models.DateTimeField(null=True, blank=True)
    scrutiny_recommendation = models.CharField(
        max_length=50,
        blank=True,
        choices=[('RECOMMEND_APPROVAL', 'Recommend Approval'), ('RECOMMEND_REJECTION', 'Recommend Rejection')]
    )
    scrutiny_notes = models.TextField(blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='approved_releases'
    )
    release_order_reference = models.CharField(max_length=100, blank=True)
    rejection_reason = models.TextField(blank=True)
    compliance_hold = models.BooleanField(
        default=False,
        help_text="Statutory or vigilance compliance hold blocking release"
    )
    compliance_hold_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['institution', 'status']),
            models.Index(fields=['reference_number', 'issuing_bank']),
            models.Index(fields=['replaces', 'status']),
        ]

    def __str__(self):
        return f"{self.reference_number} ({self.issuing_bank}) - ₹{self.amount:,.2f} [{self.status}]"

    def get_replacement_chain(self):
        """
        Traverses ancestors and descendants to construct the full
        chronological replacement and renewal timeline.
        """
        # Find root ancestor
        curr = self
        visited = set()
        while curr.replaces and curr.replaces.pk not in visited:
            visited.add(curr.pk)
            curr = curr.replaces

        # Now traverse downwards from root
        chain = []
        queue = [curr]
        seen_pks = set()

        while queue:
            node = queue.pop(0)
            if node.pk in seen_pks:
                continue
            seen_pks.add(node.pk)

            chain.append({
                'id': node.id,
                'reference_number': node.reference_number,
                'issuing_bank': node.issuing_bank,
                'amount': str(node.amount),
                'status': node.status,
                'issue_date': node.issue_date.isoformat() if node.issue_date else None,
                'maturity_date': node.maturity_date.isoformat() if node.maturity_date else None,
                'is_current': (node.id == self.id),
                'replaces_id': node.replaces_id,
                'renewal_type': node.renewal_type,
                'created_at': node.created_at.isoformat() if node.created_at else None,
            })

            # Queue descendants
            for child in node.replacement_instruments.all().order_by('created_at'):
                if child.pk not in seen_pks:
                    queue.append(child)

        return sorted(chain, key=lambda x: (x['created_at'] or ''))

    def evaluate_release_checklist(self, noc_reference: str = ''):
        """
        Evaluates regulatory release preconditions:
        1. Bank-confirmed deposit.
        2. Zero open discrepancies.
        3. Prescribed conditions satisfied (lock-in period, maturity, or NOC document/reference).
        4. No pending statutory compliance hold.
        5. Mandatory FDR certificate document present (or official NOC reference on file).
        """
        from apps.common.dates import get_effective_date
        effective_date = get_effective_date()

        # 1. Bank verification check
        has_bank_confirmed_source = self.field_sources.filter(
            value_source=DataProvenanceSource.BANK_CONFIRMED,
            is_confirmed=True
        ).exists()
        is_bank_confirmed = has_bank_confirmed_source or self.status in [
            InstrumentStatus.VERIFIED,
            InstrumentStatus.ACTIVE,
            InstrumentStatus.MATURED,
            InstrumentStatus.RELEASE_REQUESTED,
        ]

        # 2. Open discrepancies check
        open_discrepancies_count = self.discrepancies.filter(is_resolved=False).count()
        no_open_discrepancies = (open_discrepancies_count == 0)

        # 3. Prescribed conditions (Lock-in tenure of 8-10 yrs, maturity reached, or NOC on file)
        has_noc_document = self.documents.filter(document_type='NOC_DOCUMENT').exists() or bool(noc_reference)
        is_matured = bool(self.maturity_date and effective_date >= self.maturity_date)
        tenure_years = (effective_date.year - self.issue_date.year) if self.issue_date else 0
        lock_in_satisfied = is_matured or (tenure_years >= 8) or has_noc_document

        # 4. Compliance hold check
        no_compliance_hold = not self.compliance_hold

        # 5. Mandatory certificate scan present
        has_certificate_doc = self.documents.filter(
            document_type__in=['FDR_CERTIFICATE', 'BANK_CONFIRMATION']
        ).exists() or bool(noc_reference)

        blocking_reasons = []
        if not is_bank_confirmed:
            blocking_reasons.append("Deposit values have not been verified via Bank Core Banking System.")
        if not no_open_discrepancies:
            blocking_reasons.append(f"Instrument has {open_discrepancies_count} unresolved discrepancy flag(s).")
        if not lock_in_satisfied:
            blocking_reasons.append("Statutory lock-in period (8 years or scheduled maturity) has not elapsed and no AICTE Bureau NOC is attached.")
        if not no_compliance_hold:
            blocking_reasons.append(f"Statutory compliance hold active: {self.compliance_hold_reason or 'Under investigation'}.")
        if not has_certificate_doc:
            blocking_reasons.append("Mandatory FDR certificate scan or bank confirmation document missing from vault.")

        can_approve = (len(blocking_reasons) == 0)

        return {
            'is_bank_confirmed': is_bank_confirmed,
            'no_open_discrepancies': no_open_discrepancies,
            'open_discrepancies_count': open_discrepancies_count,
            'lock_in_satisfied': lock_in_satisfied,
            'has_noc_document': has_noc_document,
            'is_matured': is_matured,
            'no_compliance_hold': no_compliance_hold,
            'compliance_hold_reason': self.compliance_hold_reason,
            'mandatory_documents_present': has_certificate_doc,
            'has_required_documents': has_certificate_doc,
            'can_approve': can_approve,
            'all_conditions_met': can_approve,
            'blocking_reasons': blocking_reasons,
        }



class Document(models.Model):
    """
    Digital document associated with an Instrument,
    stored with encryption at rest outside web root and SHA-256 fingerprinting.
    Includes automated versioning and duplicate fingerprint detection.
    """
    DOCUMENT_TYPES = [
        ('FDR_CERTIFICATE', 'FDR Certificate Scan'),
        ('BANK_CONFIRMATION', 'Bank Branch Confirmation Letter'),
        ('JOINT_PLEDGE_DEED', 'Joint Pledge Agreement / Deed'),
        ('NOC_DOCUMENT', 'No Objection Certificate (NOC)'),
        ('OTHER', 'Other Supporting Document'),
    ]

    instrument = models.ForeignKey(
        Instrument,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPES, default='FDR_CERTIFICATE')
    file = models.FileField(upload_to='documents/%Y/%m/', null=True, blank=True)
    file_name = models.CharField(max_length=255, blank=True)
    mime_type = models.CharField(max_length=100, blank=True)
    sha256_hash = models.CharField(max_length=64, blank=True, db_index=True)
    file_size_bytes = models.BigIntegerField(default=0)
    version = models.PositiveIntegerField(default=1, db_index=True)
    is_current_version = models.BooleanField(default=True, db_index=True)
    storage_path = models.CharField(max_length=500, blank=True, help_text="Path in secure encrypted storage vault outside web root")
    is_encrypted = models.BooleanField(default=True)
    is_duplicate_hash = models.BooleanField(default=False, db_index=True)
    duplicate_of = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='duplicate_instances'
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='uploaded_documents'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['document_type', '-version', '-uploaded_at']
        indexes = [
            models.Index(fields=['instrument', 'document_type', 'version']),
            models.Index(fields=['sha256_hash', 'is_duplicate_hash']),
        ]

    def save(self, *args, **kwargs):
        if self.file and not self.file_name:
            self.file_name = getattr(self.file, 'name', '')
        if self.file and not self.sha256_hash:
            import hashlib
            hasher = hashlib.sha256()
            try:
                self.file.open('rb')
                for chunk in self.file.chunks(4096):
                    hasher.update(chunk)
                self.file.seek(0)
                self.sha256_hash = hasher.hexdigest()
            except Exception:
                pass
        if self.file and self.file_size_bytes == 0:
            try:
                self.file_size_bytes = self.file.size
            except Exception:
                pass
        super().save(*args, **kwargs)

    def __str__(self):
        v = f"v{self.version}"
        dup = " [DUPLICATE DETECTED]" if self.is_duplicate_hash else ""
        return f"{self.document_type} ({v}) for {self.instrument.reference_number}{dup}"


class FieldSource(models.Model):
    """
    Key principle: Every data field records its source
    (institution-submitted, officer-entered, bank-confirmed) and verified_at timestamp.
    """
    instrument = models.ForeignKey(
        Instrument,
        on_delete=models.CASCADE,
        related_name='field_sources'
    )
    field_name = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Instrument field being tracked (e.g. amount, maturity_date, lien_in_favour_of_aicte)"
    )
    field_value = models.TextField(help_text="Serialized representation of the value")
    value_source = models.CharField(
        max_length=50,
        choices=DataProvenanceSource.choices,
        default=DataProvenanceSource.INSTITUTION_SUBMITTED,
        db_index=True
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='verified_field_sources'
    )
    source_reference = models.CharField(
        max_length=255,
        blank=True,
        help_text="Bank reference ID, officer note, or receipt batch reference"
    )
    is_confirmed = models.BooleanField(
        default=False,
        help_text="True if confirmed by bank CBS or authorized scrutiny officer"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['field_name', '-created_at']
        indexes = [
            models.Index(fields=['instrument', 'field_name']),
            models.Index(fields=['value_source', 'is_confirmed']),
        ]

    def __str__(self):
        status_tag = "CONFIRMED" if self.is_confirmed else "CLAIMED"
        return f"{self.instrument.reference_number}.{self.field_name} = {self.field_value} [{self.value_source} / {status_tag}]"


class Remark(models.Model):
    """
    Notes, discrepancy observations, scrutiny findings, and recommendations.
    """
    REMARK_TYPES = [
        ('GENERAL', 'General Note'),
        ('SCRUTINY_NOTE', 'Scrutiny Officer Observation'),
        ('DISCREPANCY_FLAG', 'Discrepancy Flag'),
        ('APPROVAL_NOTE', 'Approving Authority Note'),
        ('REJECTION_REASON', 'Rejection Reason'),
        ('INSTITUTION_RESPONSE', 'Institution Clarification'),
    ]

    instrument = models.ForeignKey(
        Instrument,
        on_delete=models.CASCADE,
        related_name='remarks'
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='remarks'
    )
    role = models.CharField(max_length=50, blank=True)
    remark_type = models.CharField(max_length=50, choices=REMARK_TYPES, default='GENERAL')
    text = models.TextField()
    is_internal = models.BooleanField(
        default=False,
        help_text="Internal note visible only to Officers, Approving Authority, and Admin."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if getattr(self, 'author_id', None) and not self.role:
            try:
                self.role = getattr(self.author, 'role', '')
            except Exception:
                pass
        super().save(*args, **kwargs)

    def __str__(self):
        author_name = self.author.username if self.author else 'System'
        return f"Remark by {author_name} ({self.role}) on {self.instrument.reference_number}"



class DiscrepancySeverity(models.TextChoices):
    CRITICAL = 'CRITICAL', 'Critical'
    HIGH = 'HIGH', 'High'
    MEDIUM = 'MEDIUM', 'Medium'
    LOW = 'LOW', 'Low'


class Discrepancy(models.Model):
    """
    Structured discrepancy flag detected by rule engine or raised by scrutiny officer.
    """
    instrument = models.ForeignKey(
        Instrument,
        on_delete=models.CASCADE,
        related_name='discrepancies'
    )
    rule_code = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Machine rule code e.g. DUPLICATE_FDR_NUMBER, AMOUNT_MISMATCH_BANK, etc."
    )
    severity = models.CharField(
        max_length=20,
        choices=DiscrepancySeverity.choices,
        default=DiscrepancySeverity.HIGH,
        db_index=True
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    details = models.JSONField(default=dict, blank=True)
    is_resolved = models.BooleanField(default=False, db_index=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='resolved_discrepancies'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['instrument', 'is_resolved']),
            models.Index(fields=['severity', 'is_resolved']),
        ]

    def __str__(self):
        status = "RESOLVED" if self.is_resolved else "UNRESOLVED"
        return f"[{self.severity}] {self.title} ({self.instrument.reference_number}) - {status}"


class SavedFilter(models.Model):
    """
    User-specific saved filter presets for FDR search and worklist filtering.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_filters'
    )
    name = models.CharField(max_length=150)
    filter_params = models.JSONField(
        default=dict,
        help_text="Key-value mapping of search parameters (e.g. status, bank, amount range, etc.)"
    )
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = [('user', 'name')]

    def __str__(self):
        return f"{self.user.username} - {self.name}"

