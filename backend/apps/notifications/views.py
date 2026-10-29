import logging
from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.common.dates import (
    get_simulated_date_info,
    set_simulated_date,
    get_effective_date,
)
from apps.notifications.models import (
    Notification,
    ReminderRule,
    EscalationRule,
    EscalationRecord,
)
from apps.notifications.serializers import (
    NotificationSerializer,
    ReminderRuleSerializer,
    EscalationRuleSerializer,
    EscalationRecordSerializer,
    SimulatedDateRequestSerializer,
)
from apps.notifications.services import run_monitoring_job

logger = logging.getLogger(__name__)


class NotificationViewSet(viewsets.ModelViewSet):
    """
    User notifications and alerts viewset.
    Institutions see their own alerts; Officers/Admin see regulatory notifications.
    """
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        role = getattr(user, 'role', '')

        if role == 'ADMIN' or user.is_superuser:
            return Notification.objects.all().select_related('instrument', 'recipient')
        elif role == 'INSTITUTION':
            if hasattr(user, 'institution') and user.institution:
                return Notification.objects.filter(
                    models_q_institution(user)
                ).select_related('instrument', 'recipient')
            return Notification.objects.filter(recipient=user).select_related('instrument', 'recipient')
        elif role in ['SCRUTINY_OFFICER', 'APPROVING_AUTHORITY']:
            from django.db.models import Q
            return Notification.objects.filter(
                Q(recipient=user) |
                Q(recipient_role=role) |
                Q(recipient_role='ALL') |
                Q(recipient_role='')
            ).select_related('instrument', 'recipient')
        return Notification.objects.filter(recipient=user)

    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        notif = self.get_object()
        notif.mark_as_read()
        return Response({'status': 'marked_read', 'id': notif.id, 'is_read': True})

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        qs = self.get_queryset().filter(is_read=False)
        count = qs.update(is_read=True, read_at=timezone.now())
        return Response({'status': 'marked_all_read', 'count': count})

    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        count = self.get_queryset().filter(is_read=False).count()
        return Response({'unread_count': count})


def models_q_institution(user):
    from django.db.models import Q
    return (
        Q(recipient=user) |
        Q(instrument__institution=user.institution) |
        (Q(recipient_role='INSTITUTION') & Q(instrument__institution=user.institution))
    )


class ReminderRuleViewSet(viewsets.ModelViewSet):
    """
    Admin configuration for reminder offsets and channels.
    """
    queryset = ReminderRule.objects.all()
    serializer_class = ReminderRuleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def check_permissions(self, request):
        super().check_permissions(request)
        if request.method not in permissions.SAFE_METHODS:
            role = getattr(request.user, 'role', '')
            if role != 'ADMIN' and not request.user.is_superuser:
                raise PermissionDenied("Only Administrators can modify reminder rules.")


class EscalationRuleViewSet(viewsets.ModelViewSet):
    """
    Admin configuration for regulatory escalation rules.
    """
    queryset = EscalationRule.objects.all()
    serializer_class = EscalationRuleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def check_permissions(self, request):
        super().check_permissions(request)
        if request.method not in permissions.SAFE_METHODS:
            role = getattr(request.user, 'role', '')
            if role != 'ADMIN' and not request.user.is_superuser:
                raise PermissionDenied("Only Administrators can modify escalation rules.")


class EscalationRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Audit log of triggered regulatory escalations.
    """
    queryset = EscalationRecord.objects.all().select_related('instrument', 'rule')
    serializer_class = EscalationRecordSerializer
    permission_classes = [permissions.IsAuthenticated]


class SimulatedDateView(APIView):
    """
    Demo Testing Tool:
    Allows Administrators to view or set a simulated system date.
    All business date computations, reminders, and maturity checks
    will evaluate against this simulated date when active.
    STRICTLY GUARDED: Blocked in production environments.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        role = getattr(request.user, 'role', '')
        if role != 'ADMIN' and not request.user.is_superuser:
            raise PermissionDenied("Only Administrators can view or manage simulated demo dates.")
        return Response(get_simulated_date_info())

    def post(self, request):
        role = getattr(request.user, 'role', '')
        if role != 'ADMIN' and not request.user.is_superuser:
            raise PermissionDenied("Only Administrators can modify the simulated demo date.")

        serializer = SimulatedDateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target = serializer.validated_data.get('simulated_date')

        info = set_simulated_date(target, username=request.user.username)
        return Response(info, status=status.HTTP_200_OK)


class RunMonitoringJobView(APIView):
    """
    On-Demand Trigger:
    Allows Administrators or Scrutiny Officers to manually trigger
    the daily FDR lifecycle & monitoring job immediately.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        role = getattr(request.user, 'role', '')
        if role not in ['ADMIN', 'SCRUTINY_OFFICER'] and not request.user.is_superuser:
            raise PermissionDenied("Only Administrators or Scrutiny Officers can trigger the monitoring job.")

        target_date_str = request.data.get('effective_date')
        eff_date = None
        if target_date_str:
            from datetime import datetime
            try:
                eff_date = datetime.strptime(target_date_str.strip(), '%Y-%m-%d').date()
            except ValueError:
                raise ValidationError(f"Invalid effective_date '{target_date_str}'. Expected YYYY-MM-DD.")

        result = run_monitoring_job(effective_date=eff_date, triggered_by=request.user.username)
        return Response(result, status=status.HTTP_200_OK)
