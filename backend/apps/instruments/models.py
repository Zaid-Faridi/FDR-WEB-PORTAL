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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['institution', 'status']),
            models.Index(fields=['reference_number', 'issuing_bank']),
        ]

    def __str__(self):
        return f"{self.reference_number} ({self.issuing_bank}) - ₹{self.amount:,.2f} [{self.status}]"


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
