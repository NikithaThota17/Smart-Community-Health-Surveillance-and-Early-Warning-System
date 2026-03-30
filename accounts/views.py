from django.contrib.auth import authenticate, login, logout, get_user_model
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
import random
from django.db.models import Sum, Count
from django.core.paginator import Paginator
from django.db.models import OuterRef, Subquery
from complaints.models import Complaint
# App-specific imports
from .models import EmailOTP
from .forms import ProfileUpdateForm
from locations.models import Country, District, Mandal, Village
from complaints.models import Complaint
from analytics.models import RiskRecord
from notifications.models import Notification
from complaints.risk_utils import compute_personal_risk

User = get_user_model()


def _latest_risk_records_queryset():
    """Return one latest RiskRecord per village."""
    latest_record_id = RiskRecord.objects.filter(
        village=OuterRef('village')
    ).order_by('-calculated_at', '-id').values('id')[:1]

    return RiskRecord.objects.filter(
        id=Subquery(latest_record_id)
    ).select_related('village__mandal__district')


# =========================================================
# AUTHENTICATION VIEWS
# =========================================================

def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, email=email, password=password)

        if user:
            if not user.is_active:
                messages.error(request, 'Please verify your email via OTP first.')
                return redirect('accounts:verify_otp')

            login(request, user)

            # Increment login count
            user.login_count += 1
            user.save()

            # --- STANDARDIZED ROLE REDIRECT  ---
            if request.user.role == 'admin':
                return redirect('accounts:admin_dashboard')
            elif request.user.role == 'health_worker':
                return redirect('accounts:health_worker_dashboard')
            else:
                return redirect('accounts:user_dashboard')

        messages.error(request, 'Invalid email or password.')

    return render(request, 'accounts/login.html')


def signup_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        role = request.POST.get('role')
        village_id = request.POST.get('village')
        first_name = (request.POST.get('first_name') or '').strip()
        last_name = (request.POST.get('last_name') or '').strip()

        if not first_name or not last_name:
            messages.error(request, 'First name and last name are required.')
            return redirect('accounts:signup')

        # Check if user exists
        if User.objects.filter(email=email).exists():
            messages.info(request, 'Account already exists. Please login.')
            return redirect('accounts:login')

        # Create inactive user
        user = User.objects.create_user(
            email=email,
            password=password,
            role=role,
            first_name=first_name,
            last_name=last_name,
            is_active=False
        )

        # Assign village if selected
        if village_id:
            village = get_object_or_404(Village, id=village_id)
            user.village = village
            user.save()

        # Generate OTP
        otp = str(random.randint(100000, 999999))

        EmailOTP.objects.update_or_create(
            user=user,
            defaults={'otp': otp}
        )

        try:
            send_mail(
                'Verify your Health Surveillance Account',
                f'Your Verification OTP is: {otp}',
                settings.EMAIL_HOST_USER,
                [email],
                fail_silently=False
            )

            request.session['verify_user'] = user.id
            return redirect('accounts:verify_otp')

        except Exception:
            messages.error(request, 'Email sending failed. Check SMTP settings.')
            return redirect('accounts:signup')

    return render(request, 'accounts/signup.html', {
        'countries': Country.objects.all()
    })


def verify_otp_view(request):
    user_id = request.session.get('verify_user')

    if not user_id:
        return redirect('accounts:signup')

    user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        entered_otp = request.POST.get('otp')
        otp_obj = EmailOTP.objects.filter(user=user).first()

        if otp_obj and not otp_obj.is_expired() and entered_otp == otp_obj.otp:
            user.is_active = True
            user.is_verified = True
            user.save()

            otp_obj.delete()
            del request.session['verify_user']

            return render(request, 'accounts/verify_success.html')

        messages.error(request, 'Invalid or expired OTP.')

    return render(request, 'accounts/verify_otp.html')


def logout_view(request):
    logout(request)
    return redirect('accounts:login')


# =========================================================
# DASHBOARDS
# =========================================================

@login_required
@user_passes_test(lambda u: u.is_superuser or u.role == 'admin')
def admin_dashboard(request):
    """Finalized Master Dashboard with Chart.js Data Integration."""
    if not (request.user.is_superuser or request.user.role == 'admin'):
        return redirect('accounts:user_dashboard')

    # 1. Summary Statistics [cite: 303-308]
    latest_risks = _latest_risk_records_queryset()
    top_risk_villages = latest_risks.order_by('-probability_score', '-calculated_at')[:10]

    context = {
        'total_complaints': Complaint.objects.count(),
        'total_users': User.objects.count(),
        'high_risk_count': latest_risks.filter(risk_level='high').count(),
        'total_villages': Village.objects.filter(is_active=True).count(),
        'pending_complaints': Complaint.objects.filter(report_source='citizen').exclude(status='resolved').count(),
        'verified_field_reports_count': Complaint.objects.filter(report_source='health_worker', status__in=['verified', 'actioned', 'resolved']).count(),
        'pending_field_visits_count': Complaint.objects.filter(field_visit_required=True, field_visit_completed=False).count(),
        'active_alert_count': Notification.objects.filter(category='risk_alert', is_resolved=False).count(),
    }

    # 2. Area-wise Trends (Bar Chart: latest risk snapshot by village)
    context['bar_labels'] = [r.village.name for r in top_risk_villages]
    context['bar_data'] = [float(r.probability_score * 100) for r in top_risk_villages]

    # 3. Global Risk Distribution (Pie Chart from latest snapshot only)
    risk_stats = latest_risks.values('risk_level').annotate(count=Count('id'))
    risk_map = {r['risk_level']: r['count'] for r in risk_stats}
    context['pie_labels'] = ['HIGH RISK', 'MEDIUM RISK', 'LOW RISK']
    context['pie_data'] = [
        risk_map.get('high', 0),
        risk_map.get('medium', 0),
        risk_map.get('low', 0)
    ]

    # 4. Critical Node Monitoring Table (latest high-risk villages only)
    context['high_risk_villages'] = latest_risks.filter(risk_level='high').order_by('-probability_score', '-calculated_at')
    recent_new_citizen = Complaint.objects.filter(
        report_source='citizen',
        status='submitted',
    ).select_related(
        'user', 'village__mandal__district', 'assigned_health_worker'
    ).order_by('-created_at')[:8]
    if not recent_new_citizen:
        recent_new_citizen = Complaint.objects.filter(report_source='citizen').select_related(
            'user', 'village__mandal__district', 'assigned_health_worker'
        ).order_by('-created_at')[:8]
    context['recent_citizen_complaints'] = recent_new_citizen
    context['recent_health_worker_reports'] = Complaint.objects.filter(report_source='health_worker').select_related(
        'user', 'village__mandal__district', 'parent_complaint__user'
    ).order_by('-created_at')[:6]
    context['admin_workflow_notifications'] = Notification.objects.filter(
        recipient=request.user
    ).exclude(
        category='risk_alert'
    ).select_related('complaint', 'village').order_by('-created_at')[:8]

    return render(request, 'dashboard/admin_dashboard.html', context)


@login_required
@user_passes_test(lambda u: u.is_superuser or u.role == 'admin')
def admin_risk_history(request):
    """Admin workflow history: assignments, field visits, and notifications."""
    if not (request.user.is_superuser or request.user.role == 'admin'):
        return redirect('accounts:user_dashboard')

    status = request.GET.get('status', '')
    category = request.GET.get('category', '')
    village_id = request.GET.get('village', '')

    action_records = Complaint.objects.filter(
        Q(assigned_health_worker__isnull=False) |
        Q(field_visit_required=True) |
        Q(field_visit_completed=True) |
        Q(admin_action__isnull=False)
    ).select_related(
        'user', 'village__mandal__district', 'assigned_health_worker'
    ).order_by('-id')

    if status in {'submitted', 'under_review', 'assigned', 'verified', 'actioned', 'resolved', 'escalated'}:
        action_records = action_records.filter(status=status)
    if village_id.isdigit():
        action_records = action_records.filter(village_id=int(village_id))

    notification_records = Notification.objects.filter(
        category__in=['assignment', 'resolution', 'escalation', 'system']
    ).select_related(
        'recipient', 'complaint', 'village', 'risk_record'
    ).order_by('-created_at')

    if category in {'assignment', 'resolution', 'escalation', 'system'}:
        notification_records = notification_records.filter(category=category)
    if village_id.isdigit():
        notification_records = notification_records.filter(village_id=int(village_id))

    paginator = Paginator(action_records, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    context = {
        'page_obj': page_obj,
        'notification_records': notification_records[:80],
        'villages': Village.objects.filter(is_active=True).order_by('name'),
        'selected_status': status,
        'selected_category': category,
        'selected_village': village_id,
    }
    return render(request, 'dashboard/admin_risk_history.html', context)

@login_required
def user_dashboard(request):
    user_village = request.user.village

    risk = None
    latest_submission = None
    personal_risk_level = None
    personal_risk_score = None
    personal_risk_guidance = None
    if user_village:
        risk = RiskRecord.objects.filter(
            village=user_village
        ).order_by('-calculated_at').first()
        latest_submission = Complaint.objects.filter(
            user=request.user,
            report_source='citizen'
        ).order_by('-created_at').first()
        if latest_submission:
            score = latest_submission.personal_risk_score
            level = latest_submission.personal_risk_level
            guidance = None
            if score is None or not level:
                score, level, guidance = compute_personal_risk(latest_submission)
            else:
                _, _, guidance = compute_personal_risk(latest_submission)
            personal_risk_score = score
            personal_risk_level = level
            personal_risk_guidance = guidance

    return render(
        request,
        'dashboard/citizen_dashboard.html',
        {
            'risk': risk,
            'latest_submission': latest_submission,
            'personal_risk_level': personal_risk_level,
            'personal_risk_score': personal_risk_score,
            'personal_risk_guidance': personal_risk_guidance,
        }
    )


# =========================================================
# PROFILE
# =========================================================

@login_required
def profile_view(request):
    def _location_context_for_user(user, selected_district_id="", selected_mandal_id="", selected_village_id=""):
        districts = District.objects.filter(state__name='Andhra Pradesh').order_by('name')
        mandals = Mandal.objects.none()
        villages = Village.objects.none()

        if not selected_village_id and user.village_id:
            selected_village_id = str(user.village_id)
        if not selected_mandal_id and user.village_id:
            selected_mandal_id = str(user.village.mandal_id)
        if not selected_district_id and user.village_id:
            selected_district_id = str(user.village.mandal.district_id)

        if selected_district_id and selected_district_id.isdigit():
            mandals = Mandal.objects.filter(district_id=int(selected_district_id)).order_by('name')
        if selected_mandal_id and selected_mandal_id.isdigit():
            villages = Village.objects.filter(mandal_id=int(selected_mandal_id), is_active=True).order_by('name')

        return {
            'districts': districts,
            'mandals': mandals,
            'villages': villages,
            'selected_district_id': selected_district_id,
            'selected_mandal_id': selected_mandal_id,
            'selected_village_id': selected_village_id,
        }

    if request.method == 'POST':
        form = ProfileUpdateForm(
            request.POST,
            request.FILES,
            instance=request.user
        )
        village_id = (request.POST.get('village') or '').strip()
        is_admin_user = request.user.is_superuser or request.user.role == 'admin'
        change_location = False if is_admin_user else ((request.POST.get('change_location') == '1') or bool(village_id))
        district_id = (request.POST.get('district') or '').strip()
        mandal_id = (request.POST.get('mandal') or '').strip()

        if form.is_valid():
            user = form.save(commit=False)

            if change_location:
                if not village_id:
                    messages.error(request, 'Please select a village to update location.')
                else:
                    village = get_object_or_404(Village, id=village_id, is_active=True)
                    user.village = village
                    user.save()
                    messages.success(request, 'Profile and location updated successfully.')
                    return redirect('accounts:profile')
            else:
                user.save()
                messages.success(request, 'Profile updated successfully.')
                return redirect('accounts:profile')
        else:
            messages.error(request, 'Please correct the highlighted profile fields and try again.')

    else:
        form = ProfileUpdateForm(instance=request.user)
        change_location = False
        district_id = ''
        mandal_id = ''
        village_id = ''

    location_context = _location_context_for_user(
        request.user,
        selected_district_id=district_id,
        selected_mandal_id=mandal_id,
        selected_village_id=village_id,
    )
    return render(
        request,
        'accounts/profile.html',
        {
            'form': form,
            'change_location': change_location,
            **location_context,
        }
    )



@login_required
def health_worker_dashboard_view(request):
    if request.user.role != 'health_worker':
        return redirect('accounts:user_dashboard')
    
    village = request.user.village
    latest_area_risk = RiskRecord.objects.filter(village=village).order_by('-calculated_at').first() if village else None
    assigned_base_qs = Complaint.objects.filter(assigned_health_worker=request.user).select_related(
        'user', 'village', 'assigned_health_worker', 'parent_complaint__user'
    )
    village_reports = Complaint.objects.filter(village=village).select_related(
        'user', 'assigned_health_worker', 'parent_complaint__user'
    ) if village else Complaint.objects.none()
    citizen_reports = village_reports.filter(report_source='citizen').order_by('-created_at')
    field_reports = village_reports.filter(report_source='health_worker').order_by('-created_at')
    # Fallback: if location is missing or no village citizen reports exist yet,
    # still show citizen cases assigned by admin.
    if not village or not citizen_reports.exists():
        citizen_reports = assigned_base_qs.filter(report_source='citizen').order_by('-created_at')
    if not village or not field_reports.exists():
        field_reports = assigned_base_qs.filter(report_source='health_worker').order_by('-created_at')
    assigned_cases = assigned_base_qs.order_by('-created_at')[:5]
    pending_field_visits = Complaint.objects.filter(
        assigned_health_worker=request.user,
        field_visit_required=True,
        field_visit_completed=False,
    ).select_related('user', 'village').order_by('field_visit_due_at', '-created_at')[:5]
    workflow_notifications = Notification.objects.filter(
        recipient=request.user,
        is_resolved=False,
    ).select_related('complaint', 'village').order_by('-created_at')[:5]

    symptom_summary = citizen_reports.aggregate(
        fever_cases=Count('id', filter=Q(has_fever=True)),
        diarrhea_cases=Count('id', filter=Q(has_diarrhea=True)),
        cough_cases=Count('id', filter=Q(has_cough=True)),
        breathing_cases=Count('id', filter=Q(has_breathing_difficulty=True)),
    )
    
    context = {
        'village_name': village.name if village else "Not Assigned",
        'latest_area_risk': latest_area_risk,
        'total_area_reports': village_reports.count(),
        'total_affected': field_reports.aggregate(Sum('affected_count'))['affected_count__sum'] or 0,
        'recent_reports': field_reports[:5],
        'citizen_alerts': citizen_reports[:6],
        'assigned_cases': assigned_cases,
        'pending_field_visits': pending_field_visits,
        'workflow_notifications': workflow_notifications,
        'symptom_summary': symptom_summary,
        'trend': "Rising" if citizen_reports.filter(has_fever=True).count() > 5 else "Stable"
    }
    return render(request, 'dashboard/health_worker_dashboard.html', context)
