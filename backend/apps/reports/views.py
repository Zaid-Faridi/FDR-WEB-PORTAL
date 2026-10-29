"""
REST API Views for Phase 6:
- Officer Analytics & Risk-Ranked Dashboard
- Institution Dashboard (Strict Scoping)
- CSV & PDF Report Downloads
- On-Demand Weekly Summary Email Dispatch
"""
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.users.models import UserRole
from apps.common.dates import get_effective_date
from .analytics import get_officer_dashboard_metrics, get_institution_dashboard_metrics
from .generators import generate_csv_report, generate_pdf_report, REPORT_TITLES
from .services import dispatch_weekly_summary_email


class OfficerDashboardView(APIView):
    """
    Returns high-level KPI counts, 30/60/90-day expiry buckets, bank distribution,
    monthly expiry timeline forecast, and risk-ranked worklist.
    Accessible only to Scrutiny Officers, Approving Authority, and Admins.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        if getattr(user, 'role', None) == UserRole.INSTITUTION:
            raise PermissionDenied("Institutions do not have permission to access national officer analytics.")

        effective_date = get_effective_date()
        data = get_officer_dashboard_metrics(effective_date)
        return Response(data, status=status.HTTP_200_OK)


class InstitutionDashboardView(APIView):
    """
    Returns institution-specific portfolio summary and upcoming compliance deadlines.
    Strictly isolated: Institution users can only view their own institution's data.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        role = getattr(user, 'role', None)

        if role == UserRole.INSTITUTION:
            if not user.institution_id:
                raise PermissionDenied("User is not associated with an approved institution.")
            inst_id = user.institution_id
        else:
            # Officers / Admins can inspect a specific institution by ID
            query_inst_id = request.query_params.get('institution_id')
            if not query_inst_id:
                raise ValidationError({"institution_id": "Officers must provide ?institution_id=<id> to view institution dashboard."})
            inst_id = int(query_inst_id)

        effective_date = get_effective_date()
        data = get_institution_dashboard_metrics(inst_id, effective_date)
        return Response(data, status=status.HTTP_200_OK)


class ReportMetadataListView(APIView):
    """
    Lists all available audit and compliance reports.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        reports = [
            {
                'id': k,
                'title': v,
                'formats': ['csv', 'pdf'],
                'csv_url': f"/api/reports/{k}/csv/",
                'pdf_url': f"/api/reports/{k}/pdf/",
            }
            for k, v in REPORT_TITLES.items()
        ]
        return Response({'reports': reports}, status=status.HTTP_200_OK)


class ReportCSVDownloadView(APIView):
    """
    Exports specified report as an RFC-4180 CSV attachment.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, report_type):
        user = request.user
        if getattr(user, 'role', None) == UserRole.INSTITUTION:
            raise PermissionDenied("Institution users are not authorized to download national regulatory reports.")

        effective_date = get_effective_date()
        csv_text, filename = generate_csv_report(report_type, effective_date)

        response = HttpResponse(csv_text, content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['X-Content-Type-Options'] = 'nosniff'
        return response


class ReportPDFDownloadView(APIView):
    """
    Exports specified report as a styled executive PDF document.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, report_type):
        user = request.user
        if getattr(user, 'role', None) == UserRole.INSTITUTION:
            raise PermissionDenied("Institution users are not authorized to download national regulatory reports.")

        effective_date = get_effective_date()
        pdf_bytes, filename = generate_pdf_report(
            report_type,
            effective_date,
            requested_by=user.username
        )

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['X-Content-Type-Options'] = 'nosniff'
        return response


class SendWeeklySummaryEmailView(APIView):
    """
    On-demand endpoint for Admins/Officers to trigger the weekly compliance summary email.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if getattr(user, 'role', None) not in [UserRole.ADMIN, UserRole.SCRUTINY_OFFICER]:
            raise PermissionDenied("Only Bureau Administrators or Scrutiny Officers can trigger summary emails.")

        effective_date = get_effective_date()
        result = dispatch_weekly_summary_email(effective_date)
        return Response(result, status=status.HTTP_200_OK)
