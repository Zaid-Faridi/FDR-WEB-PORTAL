from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from apps.instruments.views import SecureDocumentDownloadView

urlpatterns = [
    path('admin/', admin.site.urls),

    # OpenAPI 3.0 Documentation Endpoints
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # Core System Health & Telemetry
    path('api/', include('apps.core.urls')),

    # JWT Authentication & User Management
    path('api/', include('apps.users.urls')),

    # Technical Institutions
    path('api/institutions/', include('apps.institutions.urls')),

    # Security Deposit & FDR Instruments
    path('api/instruments/', include('apps.instruments.urls')),
    path('api/documents/<int:pk>/download/', SecureDocumentDownloadView.as_view(), name='secure-document-download'),

    # Common Audit & Logs
    path('api/', include('apps.common.urls')),

    # Notifications, Reminders, Escalations & Admin Demo Controls
    path('api/', include('apps.notifications.urls')),
]

