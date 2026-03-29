from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from .models import Notification

@login_required
@user_passes_test(lambda u: u.is_superuser or u.role == 'admin')
def alert_list_view(request):
    """Admin view: list unresolved high/medium risk notifications."""
    alerts = Notification.objects.filter(
        category='risk_alert',
        is_resolved=False,
        risk_record__risk_level__in=['high', 'medium']
    ).select_related('village', 'risk_record').order_by('-created_at')

    return render(request, 'notifications/alerts.html', {'alerts': alerts})

@login_required
@user_passes_test(lambda u: u.is_superuser or u.role == 'admin')
def resolve_alert_view(request, alert_id):
    """Allows admins to mark an alert notification as resolved."""
    alert = get_object_or_404(Notification, id=alert_id)
    alert.is_resolved = True
    alert.resolved_at = timezone.now()
    alert.save(update_fields=['is_resolved', 'resolved_at'])

    messages.success(request, "Alert status updated successfully.")
    return redirect('notifications:alert_list')
