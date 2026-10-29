from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.notifications.views import (
    NotificationViewSet,
    ReminderRuleViewSet,
    EscalationRuleViewSet,
    EscalationRecordViewSet,
    SimulatedDateView,
    RunMonitoringJobView,
)

router = DefaultRouter()
router.register(r'notifications', NotificationViewSet, basename='notification')
router.register(r'reminder-rules', ReminderRuleViewSet, basename='reminder-rule')
router.register(r'escalation-rules', EscalationRuleViewSet, basename='escalation-rule')
router.register(r'escalations', EscalationRecordViewSet, basename='escalation-record')

urlpatterns = [
    path('admin/simulated-date/', SimulatedDateView.as_view(), name='admin-simulated-date'),
    path('admin/run-monitoring-job/', RunMonitoringJobView.as_view(), name='admin-run-monitoring-job'),
    path('', include(router.urls)),
]
