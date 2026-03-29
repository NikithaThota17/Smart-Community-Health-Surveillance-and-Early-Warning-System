import os
import google.generativeai as genai
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from .forms import CitizenComplaintForm, HealthWorkerReportForm, AdminActionForm
from .models import Complaint
from .workflow import (
    apply_health_worker_follow_up,
    create_assignment_notification,
    create_resolution_notification,
    ensure_complaint_workflow_fields,
)
from analytics.logic import run_risk_analysis

User = get_user_model()

gemini_api_key = os.getenv("GEMINI_API_KEY")
if gemini_api_key:
    genai.configure(api_key=gemini_api_key)


SYMPTOM_LABELS = [
    ("has_fever", "fever"),
    ("has_diarrhea", "diarrhea"),
    ("has_vomiting", "vomiting"),
    ("has_headache", "headache"),
    ("has_body_pain", "body pain"),
    ("has_cough", "cough"),
    ("has_cold", "cold"),
    ("has_skin_rash", "skin rash"),
    ("has_fatigue", "fatigue"),
    ("has_breathing_difficulty", "breathing difficulty"),
]

ENVIRONMENT_LABELS = [
    ("stagnant_water", "stagnant water"),
    ("waste_issue", "waste accumulation"),
    ("water_contamination", "water contamination"),
    ("drainage_issue", "drainage issue"),
    ("garbage_dumping", "garbage dumping"),
    ("foul_smell", "foul smell"),
    ("unsafe_drinking_water", "unsafe drinking water"),
    ("nearby_illness_cases", "nearby illness cases"),
]


def _selected_labels(instance, label_map):
    return [label for field_name, label in label_map if getattr(instance, field_name)]


def _fallback_citizen_advice(complaint):
    symptoms = _selected_labels(complaint, SYMPTOM_LABELS)
    environment = _selected_labels(complaint, ENVIRONMENT_LABELS)
    advice = []

    if {"diarrhea", "vomiting"} & set(symptoms):
        advice.append("Use ORS or other safe fluids and avoid unsafe drinking water.")
    if {"fever", "body pain", "headache"} & set(symptoms):
        advice.append("Monitor temperature, rest well, and contact the ASHA worker if symptoms continue.")
    if "breathing difficulty" in symptoms:
        advice.append("Seek urgent medical evaluation if breathing discomfort increases.")
    if {"stagnant water", "garbage dumping"} & set(environment):
        advice.append("Remove stagnant water and improve waste disposal around the household.")
    if "water contamination" in environment or "unsafe drinking water" in environment:
        advice.append("Boil or filter drinking water until the source is verified as safe.")

    if not advice:
        advice.append("Maintain hygiene, monitor symptoms, and report any worsening condition immediately.")

    return "\n".join(f"- {line}" for line in advice[:4])


def _fallback_health_worker_advice(report):
    actions = []
    if report.affected_count >= 10:
        actions.append("Plan an immediate village screening round for symptomatic households.")
    if report.camp_recommended:
        actions.append("Coordinate a focused village health camp with PHC support.")
    if report.stagnant_water or report.mosquito_severity == "high":
        actions.append("Escalate vector control and larval source reduction activities.")
    if report.water_contamination or report.unsafe_drinking_water:
        actions.append("Request water quality testing and promote safe drinking water instructions.")
    if report.nearby_illness_cases:
        actions.append("Track nearby households for possible cluster formation over the next 48 hours.")

    if not actions:
        actions.append("Continue local surveillance and submit daily field verification updates.")

    return "\n".join(f"- {line}" for line in actions[:4])


def _generate_gemini_text(prompt, fallback_text):
    if not gemini_api_key:
        return fallback_text

    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        return (response.text or "").strip() or fallback_text
    except Exception:
        return fallback_text


def _build_citizen_prompt(complaint):
    symptoms = _selected_labels(complaint, SYMPTOM_LABELS) or ["general discomfort"]
    environment = _selected_labels(complaint, ENVIRONMENT_LABELS) or ["no major sanitation issue reported"]
    return (
        "You are assisting a rural public-health complaint system. "
        f"A citizen from {complaint.village.name} reported symptoms: {', '.join(symptoms)}. "
        f"Environmental factors: {', '.join(environment)}. "
        "Give concise first-level guidance in 4 bullet points. "
        "Avoid diagnosis. Include hydration, sanitation, monitoring, and when to contact an ASHA worker or PHC."
    )


def _build_health_worker_prompt(report):
    environment = _selected_labels(report, ENVIRONMENT_LABELS) or ["no major sanitation issue reported"]
    return (
        "You are assisting an ASHA worker in a village surveillance system. "
        f"The health worker reported {report.affected_count} affected people in {report.village.name}. "
        f"Environmental factors: {', '.join(environment)}. "
        f"Field visit required: {report.field_visit_required}. Camp recommended: {report.camp_recommended}. "
        "Provide 4 short bullet points covering community actions, monitoring, escalation, and safety measures."
    )

@login_required
def citizen_complaint_view(request):
    if request.user.role != 'citizen':
        messages.warning(request, "Access restricted to Citizens.")
        return redirect('accounts:user_dashboard')

    # SAFETY CHECK: Prevent "RelatedObjectDoesNotExist"
    if not request.user.village:
        messages.error(request, "Your profile is missing a Village. Please update your profile first.")
        return redirect('accounts:profile')

    if request.method == 'POST':
        form = CitizenComplaintForm(request.POST, request.FILES)
        if form.is_valid():
            complaint = form.save(commit=False)
            complaint.user = request.user
            complaint.village = request.user.village
            complaint.report_source = 'citizen'
            complaint.status = 'submitted'
            complaint.priority = 'high' if complaint.symptom_count >= 4 or complaint.has_breathing_difficulty else 'medium'
            prompt = _build_citizen_prompt(complaint)
            fallback_text = _fallback_citizen_advice(complaint)
            complaint.ai_suggestion = _generate_gemini_text(prompt, fallback_text)
            complaint.medication_guidance = fallback_text
            complaint.save()
            run_risk_analysis(village_ids=[complaint.village_id])
            return render(request, 'complaints/complaint_success.html', {
                'ai_advice': complaint.ai_suggestion,
                'complaint': complaint
            })
    else:
        form = CitizenComplaintForm()
    
    return render(request, 'complaints/submit_complaint.html', {'form': form})

@login_required
def health_worker_report_view(request):
    """View for Health Workers to submit community-level data with AI insights."""
    if request.user.role != 'health_worker':
        messages.warning(request, "Access restricted to Health Workers.")
        return redirect('accounts:user_dashboard')

    if not request.user.village:
        messages.error(request, "Your profile is missing a Village. Please update your profile first.")
        return redirect('accounts:profile')

    if request.method == 'POST':
        form = HealthWorkerReportForm(request.POST, request.FILES, village=request.user.village)
        if form.is_valid():
            report = form.save(commit=False)
            report.user = request.user
            report.village = request.user.village
            report.report_source = 'health_worker'
            report.parent_complaint = form.cleaned_data.get('linked_complaint')
            report.status = 'verified' if report.field_visit_completed else 'under_review'
            if report.affected_count >= 15 or report.camp_recommended:
                report.priority = 'high'
            elif report.affected_count >= 5:
                report.priority = 'medium'
            else:
                report.priority = 'low'

            prompt = _build_health_worker_prompt(report)
            fallback_text = _fallback_health_worker_advice(report)
            report.ai_suggestion = _generate_gemini_text(prompt, fallback_text)
            report.medication_guidance = "Share precautionary guidance with affected households and route severe cases to the nearest PHC."
            report.save()
            if report.parent_complaint_id:
                apply_health_worker_follow_up(report.parent_complaint, report)
            run_risk_analysis(village_ids=[report.village_id])
            return render(request, 'complaints/complaint_success.html', {
                'ai_advice': report.ai_suggestion,
                'complaint': report 
            })
    else:
        form = HealthWorkerReportForm(village=request.user.village)
    
    return render(request, 'complaints/health_worker_report.html', {'form': form})

@login_required
def my_submissions_view(request):
    submissions = Complaint.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'complaints/my_submissions.html', {'submissions': submissions})

def complaint_success_view(request):
    return render(request, 'complaints/complaint_success.html')


@login_required
def admin_complaint_action_view(request, complaint_id):
    if not (request.user.is_superuser or request.user.role == 'admin'):
        messages.warning(request, "Access restricted to administrators.")
        return redirect('accounts:user_dashboard')

    complaint = get_object_or_404(
        Complaint.objects.select_related('user', 'village__mandal__district', 'assigned_health_worker'),
        id=complaint_id,
    )
    health_workers = User.objects.filter(role='health_worker').order_by('email')

    if request.method == 'POST':
        previous_worker_id = complaint.assigned_health_worker_id
        previous_status = complaint.status
        previous_field_visit_required = complaint.field_visit_required
        form = AdminActionForm(request.POST, instance=complaint, health_workers=health_workers)
        if form.is_valid():
            complaint = form.save(commit=False)
            missing_worker_for_assignment = complaint.status == 'assigned' and not complaint.assigned_health_worker
            missing_worker_for_field_visit = complaint.field_visit_required and not complaint.assigned_health_worker
            if missing_worker_for_assignment or missing_worker_for_field_visit:
                form.add_error('assigned_health_worker', 'Please assign a health worker for this action.')
                messages.error(request, "Please assign a health worker before saving this action.")
            else:
                ensure_complaint_workflow_fields(complaint)
                complaint.save()
                if complaint.assigned_health_worker and not complaint.assigned_health_worker.village and complaint.village:
                    complaint.assigned_health_worker.village = complaint.village
                    complaint.assigned_health_worker.save(update_fields=['village'])

                if (
                    complaint.assigned_health_worker_id and (
                        previous_worker_id != complaint.assigned_health_worker_id
                        or previous_field_visit_required != complaint.field_visit_required
                        or previous_status != complaint.status
                    )
                ):
                    create_assignment_notification(complaint, previous_worker_id=previous_worker_id)

                if complaint.status == 'resolved' and previous_status != 'resolved':
                    create_resolution_notification(
                        complaint,
                        'Complaint Resolved',
                        f"Complaint #{complaint.id} has been resolved by the administration.",
                    )
                elif complaint.status == 'escalated' and previous_status != 'escalated':
                    create_resolution_notification(
                        complaint,
                        'Complaint Escalated',
                        f"Complaint #{complaint.id} has been escalated for higher-level action.",
                    )

                messages.success(request, "Admin action updated successfully.")
                return redirect('accounts:admin_dashboard')
        else:
            messages.error(request, "Please correct the highlighted fields and save again.")
    else:
        form = AdminActionForm(instance=complaint, health_workers=health_workers)

    return render(request, 'complaints/admin_action.html', {
        'complaint': complaint,
        'form': form,
    })
