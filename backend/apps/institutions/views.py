from rest_framework import viewsets, permissions, filters
from .models import Institution
from .serializers import InstitutionSerializer
from apps.common.permissions import IsAdminUserRole

class InstitutionViewSet(viewsets.ModelViewSet):
    """
    CRUD API for AICTE-approved technical institutions.
    - All authenticated users can view/list institutions.
    - Only Admins can create, update or delete institution master profiles.
    """
    queryset = Institution.objects.all()
    serializer_class = InstitutionSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['aicte_id', 'name', 'state', 'district']
    ordering_fields = ['name', 'aicte_id', 'state', 'created_at']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUserRole()]
        return [permissions.IsAuthenticated()]
