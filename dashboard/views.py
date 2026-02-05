from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from analytics.models import RiskRecord
from complaints.models import Complaint
from django.db.models import Count
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count, Sum
from accounts.models import User
from complaints.models import Complaint
from analytics.models import RiskRecord
from locations.models import Village

@user_passes_test(lambda u: u.is_superuser or u.role == 'admin')
@login_required
def admin_dashboard(request):
    """Finalized Master Dashboard with ML Integration."""
    if request.user.role != 'admin':
        return redirect('accounts:user_dashboard')

    # 1. Real-time Summary Cards [cite: 303-308]
    context = {
        'total_complaints': Complaint.objects.count(),
        'total_users': User.objects.count(),
        'high_risk_count': RiskRecord.objects.filter(risk_level='high').count(),
        'total_villages': Village.objects.filter(is_active=True).count(),
    }

    # 2. Risk Distribution for Pie Chart [cite: 319-321]
    risk_stats = RiskRecord.objects.values('risk_level').annotate(count=Count('id'))
    context['pie_labels'] = [r['risk_level'].upper() for r in risk_stats]
    context['pie_data'] = [r['count'] for r in risk_stats]

    # 3. Area-wise Trends for Bar Chart [cite: 311-314]
    area_stats = RiskRecord.objects.all().select_related('village')[:10]
    context['bar_labels'] = [r.village.name for r in area_stats]
    context['bar_data'] = [r.probability_score * 100 for r in area_stats] # Score as percentage

    # 4. Critical Alerts Table [cite: 211-215]
    context['high_risk_villages'] = RiskRecord.objects.filter(risk_level='high').order_by('-calculated_at')

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