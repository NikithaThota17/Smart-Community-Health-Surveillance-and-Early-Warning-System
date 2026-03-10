from django.contrib.auth import authenticate, login, logout, get_user_model
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Count
import random
from django.db.models import Sum, Count
from django.core.paginator import Paginator
from django.db.models import OuterRef, Subquery
from complaints.models import Complaint
# App-specific imports
from .models import EmailOTP
from .forms import ProfileUpdateForm
from locations.models import Country, Village
from complaints.models import Complaint
from analytics.models import RiskRecord

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

        # Check if user exists
        if User.objects.filter(email=email).exists():
            messages.info(request, 'Account already exists. Please login.')
            return redirect('accounts:login')

        # Create inactive user
        user = User.objects.create_user(
            email=email,
            password=password,
            role=role,
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

@user_passes_test(lambda u: u.is_superuser or u.role == 'admin')
@login_required
def admin_dashboard(request):
    """Finalized Master Dashboard with Chart.js Data Integration."""
    if request.user.role != 'admin':
        return redirect('accounts:user_dashboard')

    # 1. Summary Statistics [cite: 303-308]
    latest_risks = _latest_risk_records_queryset()
    top_risk_villages = latest_risks.order_by('-probability_score', '-calculated_at')[:10]

    context = {
        'total_complaints': Complaint.objects.count(),
        'total_users': User.objects.count(),
        'high_risk_count': latest_risks.filter(risk_level='high').count(),
        'total_villages': Village.objects.filter(is_active=True).count(),
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

    return render(request, 'dashboard/admin_dashboard.html', context)


@user_passes_test(lambda u: u.is_superuser or u.role == 'admin')
@login_required
def admin_risk_history(request):
    """Full historical risk logs with filters and pagination."""
    if request.user.role != 'admin':
        return redirect('accounts:user_dashboard')

    risk_level = request.GET.get('risk_level', '')
    village_id = request.GET.get('village', '')

    records = RiskRecord.objects.all().select_related('village__mandal__district')

    if risk_level in {'high', 'medium', 'low'}:
        records = records.filter(risk_level=risk_level)
    if village_id.isdigit():
        records = records.filter(village_id=int(village_id))

    paginator = Paginator(records, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page_obj,
        'villages': Village.objects.filter(is_active=True).order_by('name'),
        'selected_risk_level': risk_level,
        'selected_village': village_id,
    }
    return render(request, 'dashboard/admin_risk_history.html', context)

@login_required
def user_dashboard(request):
    user_village = request.user.village

    risk = None
    if user_village:
        risk = RiskRecord.objects.filter(
            village=user_village
        ).order_by('-calculated_at').first()

    return render(
        request,
        'dashboard/citizen_dashboard.html',
        {'risk': risk}
    )


# =========================================================
# PROFILE
# =========================================================

@login_required
def profile_view(request):
    if request.method == 'POST':
        form = ProfileUpdateForm(
            request.POST,
            request.FILES,
            instance=request.user
        )

        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('accounts:profile')

    else:
        form = ProfileUpdateForm(instance=request.user)

    return render(
        request,
        'accounts/profile.html',
        {'form': form}
    )



@login_required
def health_worker_dashboard_view(request):
    if request.user.role != 'health_worker':
        return redirect('accounts:user_dashboard')
    
    # Community Stats for the Health Worker's Village
    village = request.user.village
    village_reports = Complaint.objects.filter(village=village)
    
    context = {
        'village_name': village.name if village else "Not Assigned",
        'total_area_reports': village_reports.count(),
        'total_affected': village_reports.aggregate(Sum('affected_count'))['affected_count__sum'] or 0,
        'recent_reports': village_reports.order_by('-created_at')[:5],
        # Logic for trend indicator (Simplified for B.Tech demo)
        'trend': "Rising" if village_reports.filter(has_fever=True).count() > 5 else "Stable"
    }
    return render(request, 'dashboard/health_worker_dashboard.html', context)
