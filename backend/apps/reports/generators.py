"""
Report generation engines for AICTE FDR Management Portal.
Provides CSV and styled PDF exports for:
1. Pending verifications
2. Upcoming maturities
3. Missing mandatory documents
4. Overdue unrenewed cases
5. Cases needing urgent regulatory intervention
6. Institution-wise compliance summary
"""
import csv
import io
from datetime import date, timedelta
from decimal import Decimal
from django.db.models import Count, Sum, Q

from apps.instruments.models import Instrument, InstrumentStatus, DiscrepancySeverity
from apps.institutions.models import Institution

# ReportLab imports for PDF generation
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch


REPORT_TITLES = {
    'pending_verifications': 'Pending Verification & Scrutiny Audit Report',
    'upcoming_maturities': 'Upcoming FDR Maturities Report (90-Day Outlook)',
    'missing_documents': 'Missing Mandatory Documents & Certificates Audit',
    'overdue_cases': 'Overdue Unrenewed Deposit Cases Audit',
    'cases_needing_intervention': 'High-Risk Cases Needing Immediate Bureau Intervention',
    'institution_summary': 'Institution-Wise Security Deposit Portfolio Summary',
}


def get_report_dataset(report_type: str, effective_date: date) -> tuple[list[str], list[list[str]], str]:
    """
    Returns (headers, rows, report_title) for the requested report type.
    """
    title = REPORT_TITLES.get(report_type, f'AICTE FDR Report - {report_type}')

    if report_type == 'pending_verifications':
        headers = ['FDR Ref Number', 'Institution Name', 'Issuing Bank', 'Amount (INR)', 'Issue Date', 'Maturity Date', 'Status']
        qs = Instrument.objects.filter(
            status__in=[InstrumentStatus.SUBMITTED, InstrumentStatus.UNDER_SCRUTINY]
        ).select_related('institution').order_by('created_at')

        rows = []
        for i in qs:
            rows.append([
                i.reference_number,
                i.institution.name if i.institution else 'N/A',
                i.issuing_bank,
                f"₹{i.amount:,.2f}",
                i.issue_date.isoformat() if i.issue_date else 'N/A',
                i.maturity_date.isoformat() if i.maturity_date else 'N/A',
                i.status,
            ])
        return headers, rows, title

    elif report_type == 'upcoming_maturities':
        headers = ['FDR Ref Number', 'Institution Name', 'Issuing Bank', 'Amount (INR)', 'Maturity Date', 'Days Left', 'Status']
        qs = Instrument.objects.exclude(status__in=[
            InstrumentStatus.RELEASED,
            InstrumentStatus.REPLACED,
            InstrumentStatus.RENEWED,
        ]).filter(
            maturity_date__gte=effective_date,
            maturity_date__lte=effective_date + timedelta(days=90)
        ).select_related('institution').order_by('maturity_date')

        rows = []
        for i in qs:
            days_left = (i.maturity_date - effective_date).days if i.maturity_date else 0
            rows.append([
                i.reference_number,
                i.institution.name if i.institution else 'N/A',
                i.issuing_bank,
                f"₹{i.amount:,.2f}",
                i.maturity_date.isoformat() if i.maturity_date else 'N/A',
                f"{days_left} days",
                i.status,
            ])
        return headers, rows, title

    elif report_type == 'missing_documents':
        headers = ['FDR Ref Number', 'Institution Name', 'Issuing Bank', 'Amount (INR)', 'Missing Requirements', 'Status']
        qs = Instrument.objects.filter(
            discrepancies__rule_code__in=['DOC_MANDATORY_MISSING', 'DOC_LIEN_LETTER_MISSING'],
            discrepancies__is_resolved=False
        ).select_related('institution').distinct().order_by('institution__name')

        rows = []
        for i in qs:
            missing = [d.title for d in i.discrepancies.filter(is_resolved=False)]
            rows.append([
                i.reference_number,
                i.institution.name if i.institution else 'N/A',
                i.issuing_bank,
                f"₹{i.amount:,.2f}",
                "; ".join(missing) if missing else 'Mandatory Scan Missing',
                i.status,
            ])
        return headers, rows, title

    elif report_type == 'overdue_cases':
        headers = ['FDR Ref Number', 'Institution Name', 'Issuing Bank', 'Amount (INR)', 'Maturity Date', 'Days Overdue', 'Status']
        qs = Instrument.objects.exclude(status__in=[
            InstrumentStatus.RELEASED,
            InstrumentStatus.REPLACED,
            InstrumentStatus.RENEWED,
        ]).filter(
            maturity_date__lt=effective_date
        ).select_related('institution').order_by('maturity_date')

        rows = []
        for i in qs:
            days_overdue = (effective_date - i.maturity_date).days if i.maturity_date else 0
            rows.append([
                i.reference_number,
                i.institution.name if i.institution else 'N/A',
                i.issuing_bank,
                f"₹{i.amount:,.2f}",
                i.maturity_date.isoformat() if i.maturity_date else 'N/A',
                f"{days_overdue} days overdue",
                i.status,
            ])
        return headers, rows, title

    elif report_type == 'cases_needing_intervention':
        headers = ['FDR Ref Number', 'Institution Name', 'Risk Factors', 'Amount (INR)', 'Maturity Date', 'Compliance Hold', 'Status']
        qs = Instrument.objects.filter(
            Q(discrepancies__severity=DiscrepancySeverity.CRITICAL, discrepancies__is_resolved=False) |
            Q(compliance_hold=True) |
            Q(maturity_date__lt=effective_date, status=InstrumentStatus.MATURED)
        ).select_related('institution').distinct().order_by('created_at')

        rows = []
        for i in qs:
            factors = []
            if i.compliance_hold:
                factors.append(f"HOLD: {i.compliance_hold_reason or 'Compliance'}")
            crit_flags = i.discrepancies.filter(severity=DiscrepancySeverity.CRITICAL, is_resolved=False)
            if crit_flags.exists():
                factors.append(f"{crit_flags.count()} Critical Flags")
            if i.maturity_date and i.maturity_date < effective_date:
                factors.append("Overdue")

            rows.append([
                i.reference_number,
                i.institution.name if i.institution else 'N/A',
                "; ".join(factors) or 'Intervention Required',
                f"₹{i.amount:,.2f}",
                i.maturity_date.isoformat() if i.maturity_date else 'N/A',
                'YES' if i.compliance_hold else 'NO',
                i.status,
            ])
        return headers, rows, title

    elif report_type == 'institution_summary':
        headers = ['Institution AICTE ID', 'Institution Name', 'Total FDRs', 'Active FDRs', 'Expiring FDRs', 'Total Value (INR)']
        inst_qs = Institution.objects.all().order_by('name')

        rows = []
        for inst in inst_qs:
            fdr_qs = inst.instruments.all()
            total_count = fdr_qs.count()
            active_count = fdr_qs.filter(status=InstrumentStatus.ACTIVE).count()
            expiring_count = fdr_qs.filter(
                maturity_date__gte=effective_date,
                maturity_date__lte=effective_date + timedelta(days=90)
            ).count()
            tot_amt = fdr_qs.exclude(status__in=[InstrumentStatus.RELEASED, InstrumentStatus.REPLACED]).aggregate(total=Sum('amount'))['total'] or Decimal('0')

            rows.append([
                inst.aicte_id,
                inst.name,
                str(total_count),
                str(active_count),
                str(expiring_count),
                f"₹{tot_amt:,.2f}",
            ])
        return headers, rows, title

    else:
        # Default fallback: all instruments
        headers = ['FDR Ref Number', 'Institution Name', 'Issuing Bank', 'Amount (INR)', 'Maturity Date', 'Status']
        qs = Instrument.objects.all().select_related('institution').order_by('-created_at')
        rows = [
            [
                i.reference_number,
                i.institution.name if i.institution else 'N/A',
                i.issuing_bank,
                f"₹{i.amount:,.2f}",
                i.maturity_date.isoformat() if i.maturity_date else 'N/A',
                i.status
            ]
            for i in qs
        ]
        return headers, rows, title


def generate_csv_report(report_type: str, effective_date: date) -> tuple[str, str]:
    """
    Generates a RFC-4180 compliant CSV string.
    Returns (csv_text, filename).
    """
    headers, rows, title = get_report_dataset(report_type, effective_date)

    output = io.StringIO()
    writer = csv.writer(output)

    # Header metadata
    writer.writerow([f"AICTE FDR Management Portal - {title}"])
    writer.writerow([f"Generated On: {effective_date.isoformat()}", f"Total Records: {len(rows)}"])
    writer.writerow([])

    # Table columns and data
    writer.writerow(headers)
    for r in rows:
        writer.writerow(r)

    filename = f"aicte_{report_type}_{effective_date.strftime('%Y%m%d')}.csv"
    return output.getvalue(), filename


def generate_pdf_report(report_type: str, effective_date: date, requested_by: str = 'AICTE Officer') -> tuple[bytes, str]:
    """
    Generates an executive PDF report with AICTE branding, styled tables, and pagination.
    Returns (pdf_bytes, filename).
    """
    headers, rows, title = get_report_dataset(report_type, effective_date)
    buffer = io.BytesIO()

    # Use landscape letter for wide data tables
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Custom styles
    header_style = ParagraphStyle(
        'AICTEHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        textColor=colors.HexColor('#0f172a'),
        alignment=1,  # Center
        spaceAfter=4,
    )
    sub_style = ParagraphStyle(
        'AICTESubHeader',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=colors.HexColor('#f59e0b'),
        alignment=1,
        spaceAfter=14,
    )
    meta_style = ParagraphStyle(
        'AICTEMeta',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        textColor=colors.HexColor('#475569'),
    )
    cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor('#1e293b'),
    )
    cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor('#0f172a'),
    )
    header_cell_style = ParagraphStyle(
        'TableHeaderCell',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.white,
    )

    elements = []

    # Title & Sub-header
    elements.append(Paragraph("ALL INDIA COUNCIL FOR TECHNICAL EDUCATION", header_style))
    elements.append(Paragraph(f"Bureau of Approval & Regulation — {title}", sub_style))

    # Meta Info Bar
    meta_text = f"<b>Generated As Of:</b> {effective_date.strftime('%d %B %Y')} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Authorized User:</b> {requested_by} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Total Records:</b> {len(rows)}"
    elements.append(Paragraph(meta_text, meta_style))
    elements.append(Spacer(1, 10))

    # Format Table Data
    formatted_data = []

    # Header Row
    formatted_data.append([Paragraph(h, header_cell_style) for h in headers])

    # Body Rows
    for row_idx, r in enumerate(rows):
        formatted_row = []
        for col_idx, cell in enumerate(r):
            if col_idx == 0:
                formatted_row.append(Paragraph(str(cell), cell_bold))
            else:
                formatted_row.append(Paragraph(str(cell), cell_style))
        formatted_data.append(formatted_row)

    if not rows:
        formatted_data.append([Paragraph("No records found matching criteria.", cell_style)] * len(headers))

    # Calculate proportional column widths
    avail_width = 11 * inch - 72  # 720 points
    col_width = avail_width / len(headers)

    t = Table(formatted_data, colWidths=[col_width] * len(headers), repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#ffffff'), colors.HexColor('#f8fafc')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0, 1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
    ]))
    elements.append(t)

    # Disclaimer / Footer
    elements.append(Spacer(1, 15))
    footer_text = "CONFIDENTIAL — For Official Use Only of the AICTE Regulation Bureau and Authorized Technical Institutions. System-generated report."
    elements.append(Paragraph(footer_text, ParagraphStyle('Footer', parent=styles['Italic'], fontSize=7, textColor=colors.HexColor('#94a3b8'), alignment=1)))

    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    filename = f"aicte_{report_type}_{effective_date.strftime('%Y%m%d')}.pdf"
    return pdf_bytes, filename
