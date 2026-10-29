from datetime import datetime
from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from django.db import transaction

from .models import (
    Instrument,
    Document,
    FieldSource,
    Remark,
    InstrumentStatus,
    Discrepancy,
    DiscrepancySeverity,
)
from .serializers import (
    InstrumentSerializer,
    InstrumentCreateSerializer,
    DocumentSerializer,
    FieldSourceSerializer,
    RemarkSerializer,
    DiscrepancySerializer,
    VerifyActionSerializer,
    DiscrepancyActionSerializer,
    ResolveDiscrepancySerializer,
    OCRScanRequestSerializer,
    ReleaseDecisionSerializer,
)
from .engine import run_discrepancy_check, calculate_trust_score
from .ocr import extract_fdr_fields_from_file
from apps.common.models import DataProvenanceSource
from apps.common.audit import record_audit_event
from apps.common.permissions import InstrumentAccessPermission
from apps.bank_adapters.factory import get_bank_adapter
from apps.bank_adapters.base import FDRVerificationRequest

class InstrumentViewSet(viewsets.ModelViewSet):
    """
    Core Instrument Management API.
    Enforces strict Role-Based Access Control and data provenance tracking.
    """
    permission_classes = [InstrumentAccessPermission]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference_number', 'issuing_bank', 'branch_ifsc', 'institution__name', 'institution__aicte_id']
    ordering_fields = ['created_at', 'amount', 'maturity_date', 'status']

    def get_serializer_class(self):
        if self.action == 'create':
            return InstrumentCreateSerializer
        return InstrumentSerializer

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return Instrument.objects.none()

        qs = Instrument.objects.all().select_related('institution', 'created_by').prefetch_related(
            'field_sources', 'documents', 'remarks'
        )

        # Institution users see ONLY their own institution's instruments
        if getattr(user, 'role', None) == 'INSTITUTION':
            if not user.institution_id:
                return Instrument.objects.none()
            return qs.filter(institution_id=user.institution_id)

        # Scrutiny Officers, Approving Authority, and Admin see all instruments nationwide
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        from .storage import validate_file_spec, process_and_save_document

        # Pre-validate any uploaded files before saving instrument
        uploaded_files = []
        for key in ['file', 'document_file', 'fdr_certificate']:
            if key in self.request.FILES:
                f = self.request.FILES[key]
                validate_file_spec(f)
                uploaded_files.append((f, 'FDR_CERTIFICATE'))

        # Also support arbitrary uploaded documents in request.FILES
        for key, f in self.request.FILES.items():
            if key not in ['file', 'document_file', 'fdr_certificate']:
                validate_file_spec(f)
                doc_type = self.request.data.get(f'{key}_type', 'OTHER')
                uploaded_files.append((f, doc_type))

        if getattr(user, 'role', None) == 'INSTITUTION':
            if not user.institution_id:
                raise PermissionDenied("User does not belong to any approved institution.")
            instrument = serializer.save(institution=user.institution, created_by=user, status=InstrumentStatus.SUBMITTED)
        else:
            instrument = serializer.save(created_by=user, status=InstrumentStatus.SUBMITTED)

        # Automatically record initial claimed provenance fields
        with transaction.atomic():
            claimed_fields = {
                'amount': str(instrument.amount),
                'maturity_date': str(instrument.maturity_date),
                'issue_date': str(instrument.issue_date),
                'lien_in_favour_of_aicte': str(instrument.lien_in_favour_of_aicte),
                'joint_holder_name': instrument.joint_holder_name,
                'issuing_bank': instrument.issuing_bank,
                'branch_ifsc': instrument.branch_ifsc,
                'reference_number': instrument.reference_number,
            }
            for field_name, val in claimed_fields.items():
                FieldSource.objects.create(
                    instrument=instrument,
                    field_name=field_name,
                    field_value=val,
                    value_source=DataProvenanceSource.INSTITUTION_SUBMITTED,
                    is_confirmed=False,
                )

            # Process and encrypt all uploaded documents
            for f, d_type in uploaded_files:
                process_and_save_document(
                    uploaded_file=f,
                    instrument=instrument,
                    document_type=d_type,
                    uploaded_by=user
                )

            # Try OCR extraction on FDR certificate scan if provided
            fdr_doc = instrument.documents.filter(document_type='FDR_CERTIFICATE', is_current_version=True).first()
            if fdr_doc and fdr_doc.storage_path:
                try:
                    from .storage import decrypt_document_bytes
                    decrypted = decrypt_document_bytes(fdr_doc.storage_path)
                    import io
                    ocr_res = extract_fdr_fields_from_file(io.BytesIO(decrypted), fdr_doc.file_name)
                    if ocr_res.get('success'):
                        instrument.ocr_extracted_data = ocr_res
                        instrument.save(update_fields=['ocr_extracted_data'])
                except Exception:
                    pass

            # Initial rule discrepancy check and trust score computation
            run_discrepancy_check(instrument, save=True, user=user)

            # Record audit event
            record_audit_event(
                action='INSTRUMENT_SUBMITTED',
                entity_type='Instrument',
                entity_id=str(instrument.id),
                actor_username=user.username,
                actor_role=getattr(user, 'role', ''),
                previous_state={},
                new_state={
                    'reference_number': instrument.reference_number,
                    'status': instrument.status,
                    'trust_score': instrument.trust_score,
                    'amount': str(instrument.amount),
                    'institution_id': instrument.institution_id,
                    'documents_count': len(uploaded_files),
                },
                ip_address=self.request.META.get('REMOTE_ADDR')
            )

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """
        Scrutiny Officer verification action.
        Queries BankVerificationAdapter (or MockBankAdapter),
        stores Bank-Confirmed FieldSource provenance, runs DiscrepancyEngine,
        recalculates Trust Score, and returns comprehensive verification status.
        """
        user = request.user
        if getattr(user, 'role', None) not in ['SCRUTINY_OFFICER', 'ADMIN'] and not user.is_superuser:
            raise PermissionDenied("Only Scrutiny Officers or Administrators can trigger bank verification.")

        instrument = self.get_object()
        serializer = VerifyActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        notes = serializer.validated_data.get('notes', '')

        adapter = get_bank_adapter()
        bank_raw = adapter.verify(instrument.reference_number, instrument.issuing_bank)
        prev_status = instrument.status
        now = timezone.now()

        with transaction.atomic():
            # Update or create BANK_CONFIRMED field sources
            if bank_raw.get("confirmed_amount") is not None:
                FieldSource.objects.create(
                    instrument=instrument,
                    field_name='amount',
                    field_value=str(bank_raw["confirmed_amount"]),
                    value_source=DataProvenanceSource.BANK_CONFIRMED,
                    verified_at=now,
                    verified_by=user,
                    source_reference=bank_raw["bank_reference_id"],
                    is_confirmed=(bank_raw["status"] == 'CONFIRMED'),
                )
            if bank_raw.get("confirmed_issue_date"):
                FieldSource.objects.create(
                    instrument=instrument,
                    field_name='issue_date',
                    field_value=str(bank_raw["confirmed_issue_date"]),
                    value_source=DataProvenanceSource.BANK_CONFIRMED,
                    verified_at=now,
                    verified_by=user,
                    source_reference=bank_raw["bank_reference_id"],
                    is_confirmed=(bank_raw["status"] == 'CONFIRMED'),
                )
            if bank_raw.get("confirmed_maturity_date"):
                FieldSource.objects.create(
                    instrument=instrument,
                    field_name='maturity_date',
                    field_value=str(bank_raw["confirmed_maturity_date"]),
                    value_source=DataProvenanceSource.BANK_CONFIRMED,
                    verified_at=now,
                    verified_by=user,
                    source_reference=bank_raw["bank_reference_id"],
                    is_confirmed=(bank_raw["status"] == 'CONFIRMED'),
                )
            if bank_raw.get("lien_marked") is not None:
                FieldSource.objects.create(
                    instrument=instrument,
                    field_name='lien_in_favour_of_aicte',
                    field_value=str(bank_raw["lien_marked"]),
                    value_source=DataProvenanceSource.BANK_CONFIRMED,
                    verified_at=now,
                    verified_by=user,
                    source_reference=bank_raw["bank_reference_id"],
                    is_confirmed=bool(bank_raw["lien_marked"]),
                )
            if bank_raw.get("joint_holder"):
                FieldSource.objects.create(
                    instrument=instrument,
                    field_name='joint_holder_name',
                    field_value=bank_raw["joint_holder"],
                    value_source=DataProvenanceSource.BANK_CONFIRMED,
                    verified_at=now,
                    verified_by=user,
                    source_reference=bank_raw["bank_reference_id"],
                    is_confirmed=True,
                )

            # Run discrepancy engine with bank verification result
            run_discrepancy_check(
                instrument=instrument,
                save=True,
                bank_response=bank_raw,
                user=user
            )

            # Determine status: if bank confirmed and no bank-side discrepancies, mark verified
            bank_discrepancies = bank_raw.get("discrepancies", [])
            if bank_raw["status"] == 'CONFIRMED' and not bank_discrepancies:
                instrument.status = InstrumentStatus.VERIFIED
                if bank_raw.get("lien_marked") is not None:
                    instrument.lien_in_favour_of_aicte = bool(bank_raw["lien_marked"])
                instrument.save()

                Remark.objects.create(
                    instrument=instrument,
                    author=user,
                    role=getattr(user, 'role', ''),
                    remark_type='SCRUTINY_NOTE',
                    text=f"Bank verification confirmed via {adapter.adapter_name}. Ref: {bank_raw['bank_reference_id']}. {notes}".strip(),
                    is_internal=False
                )
            else:
                instrument.status = InstrumentStatus.DISCREPANCY
                instrument.save()

                discrepancy_msg = "; ".join(bank_raw.get("discrepancies", [])) or "Discrepancy detected during bank reconciliation."
                Remark.objects.create(
                    instrument=instrument,
                    author=user,
                    role=getattr(user, 'role', ''),
                    remark_type='DISCREPANCY_FLAG',
                    text=f"Verification flagged discrepancies: {discrepancy_msg}. {notes}".strip(),
                    is_internal=False
                )

            record_audit_event(
                action='INSTRUMENT_VERIFIED' if instrument.status == InstrumentStatus.VERIFIED else 'DISCREPANCY_DETECTED',
                entity_type='Instrument',
                entity_id=str(instrument.id),
                actor_username=user.username,
                actor_role=getattr(user, 'role', ''),
                previous_state={'status': prev_status},
                new_state={
                    'status': instrument.status,
                    'trust_score': instrument.trust_score,
                    'bank_reference_id': bank_raw["bank_reference_id"],
                    'adapter': adapter.adapter_name,
                    'discrepancies': bank_raw.get("discrepancies", []),
                },
                ip_address=request.META.get('REMOTE_ADDR')
            )

        return Response({
            'status': instrument.status,
            'trust_score': instrument.trust_score,
            'bank_verification': {
                'success': (bank_raw["status"] != 'NOT_FOUND' and bank_raw["status"] != 'SYSTEM_ERROR'),
                'status_code': bank_raw["status"],
                'bank_reference_id': bank_raw["bank_reference_id"],
                'verified_at': bank_raw["verified_at"],
                'adapter_name': bank_raw["adapter_name"],
                'is_mock': True,
                'confirmed_amount': bank_raw.get("confirmed_amount"),
                'confirmed_issue_date': bank_raw.get("confirmed_issue_date"),
                'confirmed_maturity_date': bank_raw.get("confirmed_maturity_date"),
                'lien_marked': bank_raw.get("lien_marked"),
                'lien_in_favor_of': bank_raw.get("lien_in_favor_of"),
                'discrepancies': bank_raw.get("discrepancies", []),
                'raw_payload': bank_raw.get("raw_payload", {}),
            },
            'instrument': InstrumentSerializer(instrument, context={'request': request}).data
        })

    @action(detail=True, methods=['post'])
    def flag_discrepancy(self, request, pk=None):
        """
        Scrutiny Officer action to manually flag discrepancies.
        """
        user = request.user
        if getattr(user, 'role', None) not in ['SCRUTINY_OFFICER', 'ADMIN'] and not user.is_superuser:
            raise PermissionDenied("Only Scrutiny Officers or Administrators can flag discrepancies.")

        instrument = self.get_object()
        serializer = DiscrepancyActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data['reason']
        field_name = serializer.validated_data.get('field_name', '')
        severity = serializer.validated_data.get('severity', DiscrepancySeverity.HIGH)

        prev_status = instrument.status
        instrument.status = InstrumentStatus.DISCREPANCY

        # Create structured Discrepancy record
        Discrepancy.objects.create(
            instrument=instrument,
            rule_code='MANUAL_OFFICER_FLAG',
            severity=severity,
            title='Officer Raised Discrepancy',
            description=reason + (f" (Field: {field_name})" if field_name else ""),
            details={'flagged_by': user.username, 'field_name': field_name},
            is_resolved=False,
        )

        unresolved = list(instrument.discrepancies.filter(is_resolved=False))
        instrument.trust_score = calculate_trust_score(instrument, unresolved)
        instrument.save(update_fields=['status', 'trust_score', 'updated_at'])

        Remark.objects.create(
            instrument=instrument,
            author=user,
            role=getattr(user, 'role', ''),
            remark_type='DISCREPANCY_FLAG',
            text=f"Discrepancy flagged [{severity}]: {reason}" + (f" (Field: {field_name})" if field_name else ""),
            is_internal=False
        )

        record_audit_event(
            action='DISCREPANCY_FLAGGED',
            entity_type='Instrument',
            entity_id=str(instrument.id),
            actor_username=user.username,
            actor_role=getattr(user, 'role', ''),
            previous_state={'status': prev_status},
            new_state={
                'status': instrument.status,
                'trust_score': instrument.trust_score,
                'reason': reason,
                'field_name': field_name,
                'severity': severity
            },
            ip_address=request.META.get('REMOTE_ADDR')
        )

        return Response({
            'status': instrument.status,
            'trust_score': instrument.trust_score,
            'message': 'Discrepancy flagged successfully.',
            'instrument': InstrumentSerializer(instrument, context={'request': request}).data
        })

    @action(detail=True, methods=['post'], url_path='resolve-discrepancy')
    def resolve_discrepancy(self, request, pk=None):
        """
        Scrutiny Officer action to mark a discrepancy as resolved with resolution notes.
        """
        user = request.user
        if getattr(user, 'role', None) not in ['SCRUTINY_OFFICER', 'ADMIN'] and not user.is_superuser:
            raise PermissionDenied("Only Scrutiny Officers or Administrators can resolve discrepancies.")

        instrument = self.get_object()
        serializer = ResolveDiscrepancySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        note = serializer.validated_data['resolution_note']
        discrepancy_id = request.data.get('discrepancy_id')

        if not discrepancy_id:
            raise ValidationError({"discrepancy_id": "discrepancy_id is required."})

        try:
            discrepancy = instrument.discrepancies.get(pk=discrepancy_id)
        except Discrepancy.DoesNotExist:
            raise ValidationError({"discrepancy_id": f"Discrepancy #{discrepancy_id} not found on this instrument."})

        discrepancy.is_resolved = True
        discrepancy.resolved_by = user
        discrepancy.resolved_at = timezone.now()
        discrepancy.resolution_note = note
        discrepancy.save()

        # Recalculate trust score
        unresolved = list(instrument.discrepancies.filter(is_resolved=False))
        instrument.trust_score = calculate_trust_score(instrument, unresolved)

        # If no more critical or high discrepancies, return status to Under Scrutiny
        has_critical_high = any(d.severity in [DiscrepancySeverity.CRITICAL, DiscrepancySeverity.HIGH] for d in unresolved)
        if not has_critical_high and instrument.status == InstrumentStatus.DISCREPANCY:
            instrument.status = InstrumentStatus.UNDER_SCRUTINY
        instrument.save(update_fields=['trust_score', 'status', 'updated_at'])

        Remark.objects.create(
            instrument=instrument,
            author=user,
            role=getattr(user, 'role', ''),
            remark_type='SCRUTINY_NOTE',
            text=f"Resolved discrepancy [{discrepancy.rule_code}]: {note}",
            is_internal=False
        )

        record_audit_event(
            action='DISCREPANCY_RESOLVED',
            entity_type='Instrument',
            entity_id=str(instrument.id),
            actor_username=user.username,
            actor_role=getattr(user, 'role', ''),
            previous_state={},
            new_state={
                'discrepancy_id': discrepancy.id,
                'rule_code': discrepancy.rule_code,
                'resolution_note': note,
                'trust_score': instrument.trust_score,
            },
            ip_address=request.META.get('REMOTE_ADDR')
        )

        return Response({
            'status': instrument.status,
            'trust_score': instrument.trust_score,
            'message': 'Discrepancy marked as resolved.',
            'instrument': InstrumentSerializer(instrument, context={'request': request}).data
        })

    @action(detail=True, methods=['post'], url_path='mark-verified')
    def mark_verified(self, request, pk=None):
        """
        Officer marks an instrument as Verified after satisfying all scrutiny checks.
        Blocked if unresolved CRITICAL discrepancies exist.
        """
        user = request.user
        if getattr(user, 'role', None) not in ['SCRUTINY_OFFICER', 'ADMIN'] and not user.is_superuser:
            raise PermissionDenied("Only Scrutiny Officers or Administrators can mark an instrument as verified.")

        instrument = self.get_object()
        notes = request.data.get('notes', 'Officer marked instrument verified.')

        unresolved_critical = instrument.discrepancies.filter(
            is_resolved=False,
            severity=DiscrepancySeverity.CRITICAL
        ).exists()
        if unresolved_critical:
            raise ValidationError("Cannot verify instrument with unresolved CRITICAL discrepancies. Resolve them first.")

        prev_status = instrument.status
        instrument.status = InstrumentStatus.VERIFIED
        instrument.trust_score = calculate_trust_score(
            instrument,
            list(instrument.discrepancies.filter(is_resolved=False)),
            bank_confirmed=True
        )
        instrument.save(update_fields=['status', 'trust_score', 'updated_at'])

        Remark.objects.create(
            instrument=instrument,
            author=user,
            role=getattr(user, 'role', ''),
            remark_type='SCRUTINY_NOTE',
            text=notes,
            is_internal=False
        )

        record_audit_event(
            action='INSTRUMENT_VERIFIED',
            entity_type='Instrument',
            entity_id=str(instrument.id),
            actor_username=user.username,
            actor_role=getattr(user, 'role', ''),
            previous_state={'status': prev_status},
            new_state={'status': instrument.status, 'trust_score': instrument.trust_score, 'notes': notes},
            ip_address=request.META.get('REMOTE_ADDR')
        )

        return Response({
            'status': instrument.status,
            'trust_score': instrument.trust_score,
            'message': 'Instrument marked as Verified.',
            'instrument': InstrumentSerializer(instrument, context={'request': request}).data
        })

    @action(detail=False, methods=['post'], url_path='extract-ocr')
    def extract_ocr(self, request):
        """
        Optional OCR endpoint: accepts an uploaded FDR scan,
        runs pytesseract / regex entity extraction, and returns pre-filled values for the form.
        """
        from .storage import validate_file_spec
        file_obj = request.FILES.get('file')
        if not file_obj:
            raise ValidationError({"file": "No document file uploaded."})

        validate_file_spec(file_obj)
        ocr_result = extract_fdr_fields_from_file(file_obj, file_obj.name)

        return Response({
            'success': ocr_result.get('success', False),
            'extracted_fields': {
                'reference_number': ocr_result.get('reference_number'),
                'bank_name': ocr_result.get('bank_name'),
                'amount': ocr_result.get('amount'),
                'issue_date': ocr_result.get('issue_date'),
                'maturity_date': ocr_result.get('maturity_date'),
                'joint_holder': ocr_result.get('joint_holder'),
            },
            'ocr_engine': ocr_result.get('ocr_engine'),
            'raw_text_preview': (ocr_result.get('raw_text') or '')[:300],
        })

    @action(detail=True, methods=['post'])
    def request_release(self, request, pk=None):
        """
        Initiates a formal release/refund request for the instrument.
        """
        instrument = self.get_object()
        user = request.user
        prev_status = instrument.status

        instrument.status = InstrumentStatus.RELEASE_REQUESTED
        instrument.save()

        notes = request.data.get('notes', 'Institution requested deposit release/refund.')
        Remark.objects.create(
            instrument=instrument,
            author=user,
            role=getattr(user, 'role', ''),
            remark_type='APPROVAL_NOTE',
            text=notes,
            is_internal=False
        )

        record_audit_event(
            action='RELEASE_REQUESTED',
            entity_type='Instrument',
            entity_id=str(instrument.id),
            actor_username=user.username,
            actor_role=getattr(user, 'role', ''),
            previous_state={'status': prev_status},
            new_state={'status': instrument.status, 'notes': notes},
            ip_address=request.META.get('REMOTE_ADDR')
        )

        return Response({
            'status': instrument.status,
            'message': 'Release request registered.',
            'instrument': InstrumentSerializer(instrument, context={'request': request}).data
        })

    @action(detail=True, methods=['post'])
    def approve_release(self, request, pk=None):
        """
        Approving Authority action to approve a release/refund request.
        Only Approving Authority or Admin can call this.
        """
        user = request.user
        if getattr(user, 'role', None) not in ['APPROVING_AUTHORITY', 'ADMIN'] and not user.is_superuser:
            raise PermissionDenied("Only Approving Authorities or Administrators can approve deposit release.")

        instrument = self.get_object()
        serializer = ReleaseDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        decision_notes = serializer.validated_data.get('decision_notes', 'Release approved by Approving Authority.')
        noc_ref = serializer.validated_data.get('noc_reference', '')

        prev_status = instrument.status
        instrument.status = InstrumentStatus.RELEASED
        instrument.save()

        Remark.objects.create(
            instrument=instrument,
            author=user,
            role=getattr(user, 'role', ''),
            remark_type='APPROVAL_NOTE',
            text=f"RELEASE APPROVED: {decision_notes}" + (f" (NOC Ref: {noc_ref})" if noc_ref else ""),
            is_internal=False
        )

        record_audit_event(
            action='RELEASE_APPROVED',
            entity_type='Instrument',
            entity_id=str(instrument.id),
            actor_username=user.username,
            actor_role=getattr(user, 'role', ''),
            previous_state={'status': prev_status},
            new_state={'status': instrument.status, 'notes': decision_notes, 'noc_ref': noc_ref},
            ip_address=request.META.get('REMOTE_ADDR')
        )

        return Response({
            'status': instrument.status,
            'message': 'Release approved successfully.',
            'instrument': InstrumentSerializer(instrument, context={'request': request}).data
        })

    @action(detail=True, methods=['post'])
    def reject_release(self, request, pk=None):
        """
        Approving Authority action to reject a release/refund request.
        Only Approving Authority or Admin can call this.
        """
        user = request.user
        if getattr(user, 'role', None) not in ['APPROVING_AUTHORITY', 'ADMIN'] and not user.is_superuser:
            raise PermissionDenied("Only Approving Authorities or Administrators can reject deposit release.")

        instrument = self.get_object()
        serializer = ReleaseDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        decision_notes = serializer.validated_data.get('decision_notes', 'Release rejected by Approving Authority.')

        prev_status = instrument.status
        instrument.status = InstrumentStatus.REJECTED
        instrument.save()

        Remark.objects.create(
            instrument=instrument,
            author=user,
            role=getattr(user, 'role', ''),
            remark_type='REJECTION_REASON',
            text=f"RELEASE REJECTED: {decision_notes}",
            is_internal=False
        )

        record_audit_event(
            action='RELEASE_REJECTED',
            entity_type='Instrument',
            entity_id=str(instrument.id),
            actor_username=user.username,
            actor_role=getattr(user, 'role', ''),
            previous_state={'status': prev_status},
            new_state={'status': instrument.status, 'notes': decision_notes},
            ip_address=request.META.get('REMOTE_ADDR')
        )

        return Response({
            'status': instrument.status,
            'message': 'Release rejected.',
            'instrument': InstrumentSerializer(instrument, context={'request': request}).data
        })

    @action(detail=True, methods=['get', 'post'])
    def remarks(self, request, pk=None):
        """List or add remarks for an instrument."""
        instrument = self.get_object()
        user = request.user

        if request.method == 'GET':
            qs = instrument.remarks.all()
            if getattr(user, 'role', None) == 'INSTITUTION':
                qs = qs.filter(is_internal=False)
            serializer = RemarkSerializer(qs, many=True)
            return Response(serializer.data)

        # POST: add new remark
        serializer = RemarkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        is_internal = serializer.validated_data.get('is_internal', False)

        # Institution users cannot post internal remarks
        if getattr(user, 'role', None) == 'INSTITUTION':
            is_internal = False

        remark = serializer.save(
            instrument=instrument,
            author=user,
            role=getattr(user, 'role', ''),
            is_internal=is_internal
        )

        record_audit_event(
            action='REMARK_ADDED',
            entity_type='Instrument',
            entity_id=str(instrument.id),
            actor_username=user.username,
            actor_role=getattr(user, 'role', ''),
            previous_state={},
            new_state={'remark_id': remark.id, 'remark_type': remark.remark_type, 'is_internal': remark.is_internal},
            ip_address=request.META.get('REMOTE_ADDR')
        )
        return Response(RemarkSerializer(remark).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get', 'post'])
    def documents(self, request, pk=None):
        """List or upload digital documents for an instrument with encryption & automated versioning."""
        instrument = self.get_object()
        user = request.user

        if request.method == 'GET':
            serializer = DocumentSerializer(instrument.documents.all(), many=True)
            return Response(serializer.data)

        # POST: upload document
        from .storage import process_and_save_document
        file_obj = request.FILES.get('file')
        if not file_obj:
            raise ValidationError({'file': 'A valid document file is required for upload.'})

        document_type = request.data.get('document_type', 'FDR_CERTIFICATE')
        doc = process_and_save_document(
            uploaded_file=file_obj,
            instrument=instrument,
            document_type=document_type,
            uploaded_by=user
        )

        return Response(DocumentSerializer(doc).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def field_sources(self, request, pk=None):
        """Retrieve all field provenance records for the instrument."""
        instrument = self.get_object()
        serializer = FieldSourceSerializer(instrument.field_sources.all(), many=True)
        return Response(serializer.data)


from django.http import HttpResponse, Http404
from rest_framework.views import APIView
from .storage import get_decrypted_document_bytes

class SecureDocumentDownloadView(APIView):
    """
    Secure document download endpoint with strict RBAC:
    - Decrypts Fernet-encrypted ciphertext on the fly outside web root.
    - Strictly blocks unauthorized cross-institution downloads (403 Forbidden).
    - Logs an immutable audit entry on every download.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        try:
            document = Document.objects.select_related('instrument__institution').get(pk=pk)
        except Document.DoesNotExist:
            raise Http404("Requested document not found.")

        user = request.user
        # Enforce RBAC data segregation: Institution users can ONLY download their own institution's documents
        if getattr(user, 'role', None) == 'INSTITUTION':
            if document.instrument.institution_id != getattr(user, 'institution_id', None):
                raise PermissionDenied("Access denied: You do not have permission to download documents belonging to another institution.")

        # Decrypt ciphertext from secure vault outside web root
        try:
            plain_bytes, file_name, mime_type = get_decrypted_document_bytes(document)
        except Exception as exc:
            return Response({'error': f"Failed to retrieve secure document: {str(exc)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Log audit entry
        record_audit_event(
            action='DOCUMENT_DOWNLOADED',
            entity_type='Document',
            entity_id=str(document.id),
            actor_username=user.username,
            actor_role=getattr(user, 'role', ''),
            previous_state={},
            new_state={
                'file_name': file_name,
                'sha256_hash': document.sha256_hash,
                'version': document.version,
                'instrument_id': document.instrument_id,
            },
            ip_address=request.META.get('REMOTE_ADDR')
        )

        response = HttpResponse(plain_bytes, content_type=mime_type)
        response['Content-Disposition'] = f'attachment; filename="{file_name}"'
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Document-SHA256'] = document.sha256_hash
        response['X-Document-Version'] = str(document.version)
        return response
