from datetime import datetime
from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from django.db import transaction

from .models import Instrument, Document, FieldSource, Remark, InstrumentStatus
from .serializers import (
    InstrumentSerializer,
    InstrumentCreateSerializer,
    DocumentSerializer,
    FieldSourceSerializer,
    RemarkSerializer,
    VerifyActionSerializer,
    DiscrepancyActionSerializer,
    ReleaseDecisionSerializer,
)
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
        Calls pluggable bank adapter, compares claimed vs confirmed attributes,
        records FieldSource updates, and updates instrument status.
        """
        user = request.user
        if getattr(user, 'role', None) not in ['SCRUTINY_OFFICER', 'ADMIN'] and not user.is_superuser:
            raise PermissionDenied("Only Scrutiny Officers or Administrators can trigger bank verification.")

        instrument = self.get_object()
        serializer = VerifyActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        notes = serializer.validated_data.get('notes', '')

        adapter = get_bank_adapter()
        req = FDRVerificationRequest(
            fdr_number=instrument.reference_number,
            bank_name=instrument.issuing_bank,
            branch_ifsc=instrument.branch_ifsc,
            claimed_amount=float(instrument.amount),
            claimed_deposit_date=str(instrument.issue_date),
            claimed_maturity_date=str(instrument.maturity_date),
            joint_holder_name=instrument.joint_holder_name,
            institution_id=str(instrument.institution.aicte_id)
        )

        bank_res = adapter.verify_fdr(req)
        prev_status = instrument.status
        now = timezone.now()

        with transaction.atomic():
            # Update or create BANK_CONFIRMED field sources
            if bank_res.confirmed_amount is not None:
                FieldSource.objects.create(
                    instrument=instrument,
                    field_name='amount',
                    field_value=str(bank_res.confirmed_amount),
                    value_source=DataProvenanceSource.BANK_CONFIRMED,
                    verified_at=now,
                    verified_by=user,
                    source_reference=bank_res.bank_reference_id,
                    is_confirmed=(bank_res.status_code == 'CONFIRMED'),
                )
            if bank_res.lien_marked is not None:
                FieldSource.objects.create(
                    instrument=instrument,
                    field_name='lien_in_favour_of_aicte',
                    field_value=str(bank_res.lien_marked),
                    value_source=DataProvenanceSource.BANK_CONFIRMED,
                    verified_at=now,
                    verified_by=user,
                    source_reference=bank_res.bank_reference_id,
                    is_confirmed=bool(bank_res.lien_marked),
                )
            if bank_res.confirmed_joint_holder:
                FieldSource.objects.create(
                    instrument=instrument,
                    field_name='joint_holder_name',
                    field_value=bank_res.confirmed_joint_holder,
                    value_source=DataProvenanceSource.BANK_CONFIRMED,
                    verified_at=now,
                    verified_by=user,
                    source_reference=bank_res.bank_reference_id,
                    is_confirmed=True,
                )

            # Determine new status
            if bank_res.status_code == 'CONFIRMED' and not bank_res.discrepancies:
                instrument.status = InstrumentStatus.VERIFIED
                instrument.lien_in_favour_of_aicte = bool(bank_res.lien_marked)
                instrument.save()

                Remark.objects.create(
                    instrument=instrument,
                    author=user,
                    role=getattr(user, 'role', ''),
                    remark_type='SCRUTINY_NOTE',
                    text=f"Bank verification confirmed via {adapter.adapter_name}. Ref: {bank_res.bank_reference_id}. {notes}".strip(),
                    is_internal=False
                )
            else:
                instrument.status = InstrumentStatus.DISCREPANCY
                instrument.save()

                discrepancy_msg = "; ".join(bank_res.discrepancies) if bank_res.discrepancies else "Discrepancy detected during bank reconciliation."
                Remark.objects.create(
                    instrument=instrument,
                    author=user,
                    role=getattr(user, 'role', ''),
                    remark_type='DISCREPANCY_FLAG',
                    text=f"Verification flagged discrepancies: {discrepancy_msg}. {notes}".strip(),
                    is_internal=False
                )

            # Record audit entry
            record_audit_event(
                action='INSTRUMENT_VERIFIED' if instrument.status == InstrumentStatus.VERIFIED else 'DISCREPANCY_DETECTED',
                entity_type='Instrument',
                entity_id=str(instrument.id),
                actor_username=user.username,
                actor_role=getattr(user, 'role', ''),
                previous_state={'status': prev_status},
                new_state={
                    'status': instrument.status,
                    'bank_reference_id': bank_res.bank_reference_id,
                    'adapter': adapter.adapter_name,
                    'discrepancies': bank_res.discrepancies,
                },
                ip_address=request.META.get('REMOTE_ADDR')
            )

        return Response({
            'status': instrument.status,
            'bank_verification': {
                'success': bank_res.success,
                'status_code': bank_res.status_code,
                'bank_reference_id': bank_res.bank_reference_id,
                'verified_at': bank_res.verified_at,
                'adapter_name': bank_res.adapter_name,
                'discrepancies': bank_res.discrepancies,
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

        prev_status = instrument.status
        instrument.status = InstrumentStatus.DISCREPANCY
        instrument.save()

        Remark.objects.create(
            instrument=instrument,
            author=user,
            role=getattr(user, 'role', ''),
            remark_type='DISCREPANCY_FLAG',
            text=f"Discrepancy flagged: {reason}" + (f" (Field: {field_name})" if field_name else ""),
            is_internal=False
        )

        record_audit_event(
            action='DISCREPANCY_FLAGGED',
            entity_type='Instrument',
            entity_id=str(instrument.id),
            actor_username=user.username,
            actor_role=getattr(user, 'role', ''),
            previous_state={'status': prev_status},
            new_state={'status': instrument.status, 'reason': reason, 'field_name': field_name},
            ip_address=request.META.get('REMOTE_ADDR')
        )

        return Response({
            'status': instrument.status,
            'message': 'Discrepancy flagged successfully.',
            'instrument': InstrumentSerializer(instrument, context={'request': request}).data
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
