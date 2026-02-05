import csv
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from complaints.models import Complaint
from .logic import run_risk_analysis
from .models import RiskRecord

@user_passes_test(lambda u: u.is_superuser or u.role == 'admin')
def trigger_analysis(request):
    """Manually triggers the ML Risk Engine recalculation[cite: 113]."""
    try:
        run_risk_analysis()
        messages.success(request, "ML Risk Engine: Recalculation Complete.")
    except Exception as e:
        messages.error(request, f"Recalculation Failed: {str(e)}")
    
    return redirect('accounts:admin_dashboard')

@user_passes_test(lambda u: u.is_superuser or u.role == 'admin')
def export_complaints_csv(request):
    """Generates a CSV export of all collected health and sanitation data[cite: 119, 122]."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="health_surveillance_report.csv"'

    writer = csv.writer(response)
    # Header aligned with Feature List (Section D & E) [cite: 79-102]
    writer.writerow([
        'Timestamp', 'Village', 'Fever', 'Diarrhea', 'Vomiting', 
        'Affected Count', 'Mosquito Severity', 'Water Issue'
    ])

    complaints = Complaint.objects.all().select_related('village').order_by('-created_at')
    
    for c in complaints:
        writer.writerow([
            c.created_at.strftime("%Y-%m-%d %H:%M"),
            c.village.name if c.village else "Unknown",
            "Yes" if c.has_fever else "No",
            "Yes" if c.has_diarrhea else "No",
            "Yes" if c.has_vomiting else "No",
            c.affected_count,
            c.mosquito_severity,
            "Yes" if c.stagnant_water else "No"
        ])
    return response

@user_passes_test(lambda u: u.is_superuser or u.role == 'admin')
def export_risk_pdf(request):
    """Renders a print-optimized risk assessment report for PDF saving[cite: 120, 123]."""
    risks = RiskRecord.objects.all().select_related('village').order_by('-calculated_at')
    
    return render(request, 'analytics/admin_report_print.html', {
        'risks': risks,
        'report_date': timezone.now()
    })