from rest_framework import viewsets, permissions, filters
from .models import AuditLog
from .serializers import AuditLogSerializer

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
        # Institution users cannot access the global system audit log
        if getattr(user, 'role', None) == 'INSTITUTION':
            return AuditLog.objects.none()
        return AuditLog.objects.all()
