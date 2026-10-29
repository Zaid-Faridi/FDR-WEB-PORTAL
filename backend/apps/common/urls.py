from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import AuditLogViewSet, AuditEntryViewSet, VerifyAuditChainView

router = DefaultRouter()
router.register(r'audit-logs', AuditLogViewSet, basename='audit-log')
router.register(r'audit-entries', AuditEntryViewSet, basename='audit-entry')

urlpatterns = [
    path('audit/verify-chain/', VerifyAuditChainView.as_view(), name='verify-audit-chain'),
] + router.urls

