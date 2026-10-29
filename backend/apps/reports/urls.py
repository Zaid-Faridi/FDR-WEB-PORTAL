"""
URL Routing for Reports, Dashboards & Analytics.
"""
from django.urls import path
from .views import (
    OfficerDashboardView,
    InstitutionDashboardView,
    ReportMetadataListView,
    ReportCSVDownloadView,
    ReportPDFDownloadView,
    SendWeeklySummaryEmailView,
    ImpactMetricsView,
)

urlpatterns = [
    # Dashboards
    path('officer-dashboard/', OfficerDashboardView.as_view(), name='officer-dashboard'),
    path('institution-dashboard/', InstitutionDashboardView.as_view(), name='institution-dashboard'),

    # Phase 8: Impact & ROI Analytics
    path('impact-metrics/', ImpactMetricsView.as_view(), name='impact-metrics'),

    # Reports Listing & Downloads
    path('list/', ReportMetadataListView.as_view(), name='report-list'),
    path('<str:report_type>/csv/', ReportCSVDownloadView.as_view(), name='report-download-csv'),
    path('<str:report_type>/pdf/', ReportPDFDownloadView.as_view(), name='report-download-pdf'),

    # Weekly Summary Email On-Demand Trigger
    path('send-weekly-summary/', SendWeeklySummaryEmailView.as_view(), name='send-weekly-summary-email'),
]
