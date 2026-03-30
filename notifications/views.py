from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from .models import Notification
from complaints.models import Complaint
from complaints.workflow import ensure_complaint_workflow_fields, create_assignment_notification


User = get_user_model()


def _village_health_workers(village):
    if not village:
        return User.objects.filter(role='health_worker').order_by('id')
    return User.objects.filter(role='health_worker').filter(
        Q(village=village) | Q(village__isnull=True)
    ).order_by('id')


def _pick_worker_for_village(village):
    open_states = ['submitted', 'under_review', 'assigned', 'verified', 'actioned']
    workers = _village_health_workers(village).annotate(
        open_case_count=Count('assigned_complaints', filter=Q(assigned_complaints__status__in=open_states))
    ).order_by('open_case_count', 'id')
    return workers.first()


def _pending_case_for_village(village):
    if not village:
        return None
    return Complaint.objects.filter(
        village=village,
        report_source='citizen',
        status__in=['submitted', 'under_review', 'assigned'],
    ).select_related('user', 'assigned_health_worker', 'village').order_by('-created_at').first()


def _create_bulk_notifications(users, title, message, village=None):
    users = list(users)
    if not users:
        return 0
    Notification.objects.bulk_create([
        Notification(
            category='system',
            title=title,
            message=message,
            recipient=user,
            village=village,
        )
        for user in users
    ])
    return len(users)

@login_required
@user_passes_test(lambda u: u.is_superuser or u.role == 'admin')
def alert_list_view(request):
    """Admin view: list unresolved high/medium risk notifications."""
    alerts = Notification.objects.filter(
        category='risk_alert',
        is_resolved=False,
        risk_record__risk_level__in=['high', 'medium']
    ).select_related('village', 'risk_record').order_by('-risk_record__calculated_at', '-id')

    return render(request, 'notifications/alerts.html', {'alerts': alerts})

@login_required
@user_passes_test(lambda u: u.is_superuser or u.role == 'admin')
def resolve_alert_view(request, alert_id):
    """Allows admins to mark an alert notification as resolved."""
    if request.method != 'POST':
        messages.error(request, "Invalid request method for resolving alerts.")
        return redirect('notifications:alert_list')

    alert = get_object_or_404(Notification, id=alert_id, category='risk_alert')
    action_taken = (request.POST.get('action_taken') or '').strip()
    action_note = (request.POST.get('action_note') or '').strip()
    allowed_actions = {
        'field_visit_assigned': 'Field visit assigned',
        'camp_planned': 'Health camp planned',
        'medicines_distributed': 'Medicines distributed',
        'awareness_sent': 'Citizen awareness alert sent',
        'monitor_only': 'Monitored, no field escalation needed',
    }
    if action_taken not in allowed_actions:
        messages.error(request, "Please select what action was taken before resolving.")
        return redirect('notifications:alert_list')

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
    action_text = allowed_actions[action_taken]
    note_text = f" Note: {action_note}" if action_note else ""

    workflow_result = "No extra workflow action recorded."
    if action_taken == 'field_visit_assigned':
        case = _pending_case_for_village(alert.village)
        worker = _pick_worker_for_village(alert.village)
        if case and worker:
            prev_worker = case.assigned_health_worker_id
            case.assigned_health_worker = worker
            case.field_visit_required = True
            if case.status in {'submitted', 'under_review'}:
                case.status = 'assigned'
            note_line = (
                f"Alert follow-up action by admin {actor}: field visit assigned through Alerts."
            )
            case.admin_action = f"{(case.admin_action or '').strip()}\n{note_line}".strip()
            ensure_complaint_workflow_fields(case)
            case.save()
            create_assignment_notification(case, previous_worker_id=prev_worker)
            workflow_result = (
                f"Assigned field visit for complaint #{case.id} to "
                f"{worker.get_full_name() or worker.email}."
            )
        elif worker and not case:
            Notification.objects.create(
                category='assignment',
                title='Field Visit Requested',
                message=(
                    f"Admin {actor} requested a proactive field visit for {village_name} "
                    f"after risk alert assessment."
                ),
                recipient=worker,
                village=alert.village,
            )
            workflow_result = f"Sent proactive field-visit request to {worker.get_full_name() or worker.email}."
        else:
            workflow_result = "No health worker available for assignment in this village."

    elif action_taken == 'camp_planned':
        workers = _village_health_workers(alert.village)
        sent = _create_bulk_notifications(
            users=workers,
            title='Health Camp Plan',
            message=(
                f"Admin {actor} planned a health camp for {village_name}. "
                "Please coordinate outreach, screening, and attendance support."
            ),
            village=alert.village,
        )
        workflow_result = f"Camp-planning notice sent to {sent} health worker(s)."

    elif action_taken == 'medicines_distributed':
        citizens = User.objects.filter(role='citizen', village=alert.village)
        sent = _create_bulk_notifications(
            users=citizens,
            title='Medicine Distribution Update',
            message=(
                f"Medicine distribution support has been initiated in {village_name}. "
                "Contact your local health worker/PHC for guidance and follow-up."
            ),
            village=alert.village,
        )
        workflow_result = f"Medicine-distribution advisory sent to {sent} citizen(s)."

    elif action_taken == 'awareness_sent':
        citizens = User.objects.filter(role='citizen', village=alert.village)
        sent = _create_bulk_notifications(
            users=citizens,
            title='Public Health Advisory',
            message=(
                f"Health advisory for {village_name}: use safe water, maintain hygiene, "
                "monitor symptoms, and contact ASHA/PHC if condition worsens."
            ),
            village=alert.village,
        )
        workflow_result = f"Awareness advisory sent to {sent} citizen(s)."

    elif action_taken == 'monitor_only':
        workflow_result = "Monitoring-only closure recorded with no downstream task creation."

    Notification.objects.create(
        category='system',
        title='Risk Alert Resolved',
        message=(
            f"Admin {actor} marked risk alert as resolved for {village_name} "
            f"(risk level: {level}). Action: {action_text}.{note_text} {workflow_result}"
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
