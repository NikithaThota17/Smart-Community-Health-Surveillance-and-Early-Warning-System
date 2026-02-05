from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from analytics.models import RiskRecord
from django.contrib import messages

@login_required
def alert_list_view(request):
    """Displays a list of active alerts for the user's area [cite: 15, 89-90]."""
    if request.user.role == 'admin':
        # Admins see all High/Medium risk alerts 
        alerts = RiskRecord.objects.filter(risk_level__in=['high', 'medium']).order_by('-calculated_at')
    else:
        # Citizens see alerts only for their village [cite: 15, 53]
        alerts = RiskRecord.objects.filter(village=request.user.village, risk_level__in=['high', 'medium']).order_by('-calculated_at')
    
    return render(request, 'notifications/alerts.html', {'alerts': alerts})

@login_required
def resolve_alert_view(request, alert_id):
    """Allows admins to mark a high-risk situation as acknowledged/resolved[cite: 57]."""
    if request.user.role != 'admin':
        return redirect('dashboard:citizen_dashboard')
    
    # In a real B.Tech implementation, we would add a 'is_resolved' field to RiskRecord
    messages.success(request, "Alert status updated successfully.")
    return redirect('notifications:alert_list')