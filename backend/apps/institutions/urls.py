from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    InstitutionViewSet,
    AICTEInstitutionSyncView,
    AICTEInstitutionWebhookView,
)

router = DefaultRouter()
router.register(r'', InstitutionViewSet, basename='institution')

urlpatterns = [
    # Phase 8 Integration Endpoints
    path('sync/', AICTEInstitutionSyncView.as_view(), name='institution-sync'),
    path('webhook/', AICTEInstitutionWebhookView.as_view(), name='institution-webhook'),
] + router.urls
