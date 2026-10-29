import os
import uuid
import mimetypes
from pathlib import Path
from datetime import datetime
from typing import Tuple, Optional

from django.conf import settings
from rest_framework.exceptions import ValidationError
from django.db import transaction
from cryptography.fernet import Fernet

from .models import Document, Instrument, Remark, InstrumentStatus
from apps.common.audit import record_audit_event


def get_fernet() -> Fernet:
    """Returns the configured Fernet cipher engine."""
    key = getattr(settings, 'SECURE_STORAGE_ENCRYPTION_KEY', None)
    if not key:
        key = Fernet.generate_key().decode()
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


def validate_file_spec(file_obj):
    """
    Validates file type (PDF, JPG, PNG) and size constraints.
    Raises ValidationError on violations.
    """
    name = file_obj.name.lower()
    ext = os.path.splitext(name)[1]

    if ext not in settings.ALLOWED_DOCUMENT_EXTENSIONS:
        raise ValidationError(
            f"Invalid file type '{ext}'. Allowed file types are: {', '.join(settings.ALLOWED_DOCUMENT_EXTENSIONS)}."
        )

    # Check size
    size = getattr(file_obj, 'size', 0)
    if size > settings.MAX_UPLOAD_SIZE_BYTES:
        max_mb = settings.MAX_UPLOAD_SIZE_BYTES / (1024 * 1024)
        raise ValidationError(f"File size ({size / (1024 * 1024):.2f} MB) exceeds maximum limit of {max_mb:.0f} MB.")

    return True


def compute_sha256(raw_bytes: bytes) -> str:
    """Computes SHA-256 hexadecimal hash from raw byte buffer."""
    import hashlib
    return hashlib.sha256(raw_bytes).hexdigest()


def encrypt_content(raw_bytes: bytes) -> bytes:
    """Encrypts byte buffer using Fernet."""
    fernet = get_fernet()
    return fernet.encrypt(raw_bytes)


def decrypt_content(encrypted_bytes: bytes) -> bytes:
    """Decrypts ciphertext using Fernet."""
    fernet = get_fernet()
    return fernet.decrypt(encrypted_bytes)


def decrypt_document_bytes(storage_path: str) -> bytes:
    """Reads ciphertext from disk and returns decrypted plaintext bytes."""
    with open(storage_path, 'rb') as f:
        encrypted = f.read()
    return decrypt_content(encrypted)


def process_and_save_document(
    *,
    uploaded_file,
    instrument: Instrument,
    document_type: str = 'FDR_CERTIFICATE',
    uploaded_by=None
) -> Document:
    """
    Core Phase 2 document pipeline:
    1. Validates file type and size.
    2. Reads plaintext bytes and computes SHA-256 fingerprint.
    3. Detects duplicate fingerprint uploaded under any different instrument.
    4. Applies automated versioning (increments version if document_type exists for instrument).
    5. Encrypts payload at rest using Fernet and saves outside web root.
    6. Creates Document model and logs audit trail.
    """
    # 1. Validation
    validate_file_spec(uploaded_file)

    # Read plaintext bytes
    uploaded_file.seek(0)
    plain_bytes = uploaded_file.read()
    file_size = len(plain_bytes)

    # 2. SHA-256 fingerprint
    sha256_hash = compute_sha256(plain_bytes)

    # Guess MIME type
    guessed_type, _ = mimetypes.guess_type(uploaded_file.name)
    mime_type = guessed_type or getattr(uploaded_file, 'content_type', 'application/octet-stream')

    with transaction.atomic():
        # 3. Detect duplicate document hash under a different instrument
        existing_other = Document.objects.filter(sha256_hash=sha256_hash).exclude(instrument=instrument).first()
        is_duplicate = False
        duplicate_ref = None

        if existing_other:
            is_duplicate = True
            duplicate_ref = existing_other

            # Flag discrepancy on current instrument
            other_inst_name = getattr(existing_other.instrument.institution, 'name', 'Another Institution')
            other_ref = existing_other.instrument.reference_number
            alert_text = (
                f"SECURITY ALERT: Identical document fingerprint detected! SHA-256 hash ({sha256_hash}) "
                f"was previously uploaded under instrument '{other_ref}' ({other_inst_name})."
            )

            Remark.objects.create(
                instrument=instrument,
                author=uploaded_by if uploaded_by and uploaded_by.is_authenticated else instrument.created_by,
                role=getattr(uploaded_by, 'role', 'SYSTEM'),
                remark_type='DISCREPANCY_FLAG',
                text=alert_text,
                is_internal=False
            )

            instrument.status = InstrumentStatus.DISCREPANCY
            instrument.save()

            record_audit_event(
                action='DUPLICATE_DOCUMENT_HASH_DETECTED',
                entity_type='Instrument',
                entity_id=str(instrument.id),
                actor_username=getattr(uploaded_by, 'username', 'system'),
                actor_role=getattr(uploaded_by, 'role', ''),
                previous_state={},
                new_state={
                    'sha256_hash': sha256_hash,
                    'matched_instrument_ref': other_ref,
                    'matched_document_id': existing_other.id,
                }
            )

        # 4. Versioning: increment version if document_type exists for this instrument
        previous_docs = Document.objects.filter(
            instrument=instrument,
            document_type=document_type
        ).order_by('-version')

        if previous_docs.exists():
            new_version = previous_docs.first().version + 1
            previous_docs.update(is_current_version=False)
        else:
            new_version = 1

        # 5. Encryption at rest outside web root
        ciphertext = encrypt_content(plain_bytes)

        now = datetime.now()
        rel_dir = f"{now.year}/{now.month:02d}"
        target_dir = Path(settings.SECURE_STORAGE_ROOT) / rel_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        file_uuid = uuid.uuid4().hex[:12]
        safe_filename = f"{instrument.id}_{document_type}_v{new_version}_{file_uuid}_{uploaded_file.name}.enc"
        full_path = target_dir / safe_filename

        with open(full_path, 'wb') as f:
            f.write(ciphertext)

        # 6. Create Document record
        doc = Document.objects.create(
            instrument=instrument,
            document_type=document_type,
            file_name=uploaded_file.name,
            mime_type=mime_type,
            sha256_hash=sha256_hash,
            file_size_bytes=file_size,
            version=new_version,
            is_current_version=True,
            storage_path=str(full_path),
            is_encrypted=True,
            is_duplicate_hash=is_duplicate,
            duplicate_of=duplicate_ref,
            uploaded_by=uploaded_by if uploaded_by and uploaded_by.is_authenticated else None,
        )

        record_audit_event(
            action='DOCUMENT_UPLOADED',
            entity_type='Document',
            entity_id=str(doc.id),
            actor_username=getattr(uploaded_by, 'username', 'system'),
            actor_role=getattr(uploaded_by, 'role', ''),
            previous_state={},
            new_state={
                'instrument_id': instrument.id,
                'document_type': doc.document_type,
                'version': doc.version,
                'sha256_hash': doc.sha256_hash,
                'file_name': doc.file_name,
                'is_encrypted': True,
                'is_duplicate_hash': is_duplicate,
            }
        )

    return doc


def get_decrypted_document_bytes(document: Document) -> Tuple[bytes, str, str]:
    """
    Reads the encrypted file from secure storage, decrypts it,
    and returns (plaintext_bytes, file_name, mime_type).
    """
    if not document.storage_path or not os.path.exists(document.storage_path):
        raise FileNotFoundError("Encrypted document file not found in secure storage vault.")

    with open(document.storage_path, 'rb') as f:
        ciphertext = f.read()

    plain_bytes = decrypt_content(ciphertext)
    return plain_bytes, document.file_name or "document", document.mime_type or "application/octet-stream"
