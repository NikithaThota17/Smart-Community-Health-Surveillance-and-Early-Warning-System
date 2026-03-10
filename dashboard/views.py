from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from analytics.models import RiskRecord
from complaints.models import Complaint
from django.db.models import Count
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count, Sum
from django.db.models import OuterRef, Subquery
from accounts.models import User
from complaints.models import Complaint
from analytics.models import RiskRecord
from locations.models import Village


def _latest_risk_records_queryset():
    latest_record_id = RiskRecord.objects.filter(
        village=OuterRef('village')
    ).order_by('-calculated_at', '-id').values('id')[:1]

    return RiskRecord.objects.filter(
        id=Subquery(latest_record_id)
    ).select_related('village__mandal__district')

@user_passes_test(lambda u: u.is_superuser or u.role == 'admin')
@login_required
def admin_dashboard(request):
    """Finalized Master Dashboard with ML Integration."""
    if request.user.role != 'admin':
        return redirect('accounts:user_dashboard')

    # 1. Real-time Summary Cards [cite: 303-308]
    latest_risks = _latest_risk_records_queryset()
    top_risk_villages = latest_risks.order_by('-probability_score', '-calculated_at')[:10]
    context = {
        'total_complaints': Complaint.objects.count(),
        'total_users': User.objects.count(),
        'high_risk_count': latest_risks.filter(risk_level='high').count(),
        'total_villages': Village.objects.filter(is_active=True).count(),
    }

    # 2. Risk Distribution for Pie Chart [latest snapshot]
    risk_stats = latest_risks.values('risk_level').annotate(count=Count('id'))
    context['pie_labels'] = [r['risk_level'].upper() for r in risk_stats]
    context['pie_data'] = [r['count'] for r in risk_stats]

    # 3. Area-wise Trends for Bar Chart [latest snapshot]
    area_stats = top_risk_villages
    context['bar_labels'] = [r.village.name for r in area_stats]
    context['bar_data'] = [r.probability_score * 100 for r in area_stats] # Score as percentage

    # 4. Critical Alerts Table [latest high-risk only]
    context['high_risk_villages'] = latest_risks.filter(risk_level='high').order_by('-probability_score', '-calculated_at')

    return render(request, 'dashboard/admin_dashboard.html', context)


@login_required
def citizen_dashboard_view(request):
    # Fetch the latest risk for the user's specific village
    user_village = request.user.village
    latest_risk = RiskRecord.objects.filter(village=user_village).order_by('-calculated_at').first()
    
    context = {
        'risk': latest_risk,
    }
    return render(request, 'dashboard/citizen_dashboard.html', context)
