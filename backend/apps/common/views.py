from rest_framework import viewsets, permissions, filters, status
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import AuditLog, AuditEntry
from .serializers import AuditLogSerializer, AuditEntrySerializer
from .audit import verify_audit_hash_chain
from .permissions import IsAdminUserRole


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only audit log endpoint for compliance, inspections, and vigilance reviews.
    Accessible to Scrutiny Officers, Approving Authority, and Admin.
    """
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['actor_username', 'action', 'entity_type', 'entity_id']
    ordering_fields = ['timestamp', 'action', 'entity_type']

    def get_queryset(self):
        user = self.request.user
        if getattr(user, 'role', None) == 'INSTITUTION':
            return AuditLog.objects.none()
        return AuditLog.objects.all()


class AuditEntryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Phase 7 Cryptographic Append-Only Audit Trail ViewSet:
    Exposes immutable hash-chained audit records.
    Accessible to Scrutiny Officers, Approving Authority, and Admin (denied to institutions).
    """
    queryset = AuditEntry.objects.all()
    serializer_class = AuditEntrySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['actor_username', 'action', 'object_type', 'object_id', 'entry_hash']
    ordering_fields = ['id', 'timestamp', 'action', 'object_type']

    def get_queryset(self):
        user = self.request.user
        if getattr(user, 'role', None) == 'INSTITUTION':
            return AuditEntry.objects.none()
        return AuditEntry.objects.all()


class VerifyAuditChainView(APIView):
    """
    Phase 7 Admin Cryptographic Audit Verification Endpoint:
    Traverses the entire hash chain from genesis to the latest record,
    validating previous_hash linkages and recomputing entry hashes.
    Immediately identifies any altered or broken audit entries.
    """
    permission_classes = [permissions.IsAuthenticated, IsAdminUserRole]

    def get(self, request):
        result = verify_audit_hash_chain()
        http_status = status.HTTP_200_OK if result['valid'] else status.HTTP_409_CONFLICT
        return Response(result, status=http_status)

