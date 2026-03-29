from datetime import timedelta

from django.utils import timezone

from notifications.models import Notification


DEFAULT_FIELD_VISIT_HOURS = 48


def _append_note(existing_text, new_line):
    existing_text = (existing_text or "").strip()
    return f"{existing_text}\n{new_line}".strip() if existing_text else new_line


def ensure_complaint_workflow_fields(complaint):
    changed_fields = []
    now = timezone.now()

    if complaint.assigned_health_worker_id and complaint.assigned_at is None:
        complaint.assigned_at = now
        changed_fields.append('assigned_at')

    if complaint.field_visit_required and complaint.assigned_health_worker_id:
        if complaint.field_visit_due_at is None:
            complaint.field_visit_due_at = now + timedelta(hours=DEFAULT_FIELD_VISIT_HOURS)
            changed_fields.append('field_visit_due_at')
        if complaint.status == 'submitted':
            complaint.status = 'assigned'
            changed_fields.append('status')

    if not complaint.field_visit_required and complaint.field_visit_due_at is not None:
        complaint.field_visit_due_at = None
        changed_fields.append('field_visit_due_at')

    if complaint.status == 'resolved' and complaint.resolved_at is None:
        complaint.resolved_at = now
        changed_fields.append('resolved_at')
    elif complaint.status != 'resolved' and complaint.resolved_at is not None:
        complaint.resolved_at = None
        changed_fields.append('resolved_at')

    return changed_fields


def create_assignment_notification(complaint, previous_worker_id=None):
    if not complaint.assigned_health_worker_id:
        return

    if previous_worker_id == complaint.assigned_health_worker_id and not complaint.field_visit_required:
        return

    due_text = (
        complaint.field_visit_due_at.strftime('%d %b %Y %H:%M')
        if complaint.field_visit_due_at else
        'No due time set'
    )
    title = 'Field Visit Assigned' if complaint.field_visit_required else 'Complaint Assigned'
    instructions = []
    if complaint.field_visit_required:
        instructions.append("Conduct a field visit and submit verification notes.")
    if complaint.camp_recommended:
        instructions.append("Coordinate a local health camp with PHC support.")
    if complaint.priority == 'high':
        instructions.append("Prioritize medicine-awareness and referral of severe cases.")
    if complaint.admin_action:
        instructions.append(f"Admin note: {complaint.admin_action}")

    instruction_text = " ".join(instructions) if instructions else "Review the complaint and take necessary action."
    message = (
        f"You have been assigned complaint #{complaint.id} for "
        f"{complaint.village.name if complaint.village else 'an unknown village'}. "
        f"Current status: {complaint.get_status_display()}. Due: {due_text}. "
        f"{instruction_text}"
    )

    Notification.objects.create(
        category='assignment',
        title=title,
        message=message,
        recipient=complaint.assigned_health_worker,
        complaint=complaint,
        village=complaint.village,
    )


def create_resolution_notification(complaint, title, message):
    Notification.objects.create(
        category='resolution' if complaint.status == 'resolved' else 'escalation',
        title=title,
        message=message,
        recipient=complaint.user,
        complaint=complaint,
        village=complaint.village,
    )


def apply_health_worker_follow_up(parent_complaint, report):
    now = timezone.now()
    updated_fields = []

    parent_complaint.field_visit_completed = bool(report.field_visit_completed)
    updated_fields.append('field_visit_completed')

    if report.field_visit_completed:
        parent_complaint.field_visit_required = False
        parent_complaint.field_visit_due_at = None
        updated_fields.extend(['field_visit_required', 'field_visit_due_at'])

        needs_escalation = any([
            report.affected_count >= 10,
            report.camp_recommended,
            report.water_contamination,
            report.unsafe_drinking_water,
            report.nearby_illness_cases,
            report.mosquito_severity == 'high',
        ])

        if needs_escalation:
            parent_complaint.status = 'escalated'
            parent_complaint.escalation_target = (
                parent_complaint.escalation_target or 'PHC / Medical Officer'
            )
            parent_complaint.admin_action = _append_note(
                parent_complaint.admin_action,
                'Auto-escalated after field visit due to elevated community risk indicators.'
            )
            updated_fields.extend(['status', 'escalation_target', 'admin_action'])
            create_resolution_notification(
                parent_complaint,
                'Complaint Escalated',
                (
                    f"Complaint #{parent_complaint.id} was escalated after the field visit. "
                    "The health team flagged elevated community-risk indicators."
                ),
            )
        else:
            parent_complaint.status = 'resolved'
            parent_complaint.resolved_at = now
            parent_complaint.admin_action = _append_note(
                parent_complaint.admin_action,
                'Auto-resolved after completed field visit with no major escalation indicators.'
            )
            updated_fields.extend(['status', 'resolved_at', 'admin_action'])
            create_resolution_notification(
                parent_complaint,
                'Complaint Resolved',
                (
                    f"Complaint #{parent_complaint.id} was resolved after the health worker completed "
                    "the field visit and reported no major escalation indicators."
                ),
            )
    else:
        parent_complaint.status = 'under_review'
        parent_complaint.admin_action = _append_note(
            parent_complaint.admin_action,
            'Field report submitted; awaiting completed visit confirmation.'
        )
        updated_fields.extend(['status', 'admin_action'])

    parent_complaint.save(update_fields=list(dict.fromkeys(updated_fields)))
