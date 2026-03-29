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
    if request.method != 'POST':
        messages.error(request, "Invalid request method for resolving alerts.")
        return redirect('notifications:alert_list')

    alert = get_object_or_404(Notification, id=alert_id, category='risk_alert')
    now = timezone.now()

    duplicates_qs = Notification.objects.filter(
        category='risk_alert',
        is_resolved=False,
        village_id=alert.village_id,
    )
    if alert.village_id is None:
        duplicates_qs = Notification.objects.filter(
            category='risk_alert',
            is_resolved=False,
            id=alert.id,
        )
    resolved_count = duplicates_qs.update(is_resolved=True, resolved_at=now)

    actor = request.user.get_full_name() or request.user.email
    village_name = alert.village.name if alert.village else "Unknown village"
    level = alert.risk_record.risk_level if alert.risk_record else "unknown"
    Notification.objects.create(
        category='system',
        title='Risk Alert Resolved',
        message=(
            f"Admin {actor} marked risk alert as resolved for {village_name} "
            f"(risk level: {level})."
        ),
        village=alert.village,
        risk_record=alert.risk_record,
    )

    if resolved_count:
        messages.success(request, f"Resolved {resolved_count} active alert(s) for {village_name}.")
    else:
        messages.info(request, "This alert was already resolved.")
    return redirect('notifications:alert_list')


@login_required
@user_passes_test(lambda u: u.role == 'health_worker')
def worker_notifications_view(request):
    notifications = Notification.objects.filter(
        recipient=request.user,
    ).select_related('complaint', 'village').order_by('-created_at')
    return render(
        request,
        'notifications/worker_notifications.html',
        {'notifications': notifications}
    )


@login_required
@user_passes_test(lambda u: u.role == 'citizen')
def citizen_alert_history_view(request):
    alerts = Notification.objects.filter(
        category='risk_alert',
        village=request.user.village,
    ).select_related('risk_record', 'village').order_by('-created_at')
    return render(
        request,
        'notifications/citizen_alert_history.html',
        {'alerts': alerts}
    )
