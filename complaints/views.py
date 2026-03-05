import google.generativeai as genai
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import CitizenComplaintForm, HealthWorkerReportForm
from .models import Complaint

# Use environment variables for keys in a real project
genai.configure(api_key="AIzaSyA-wbm4CPmGo4pIaRV-PXkI16o29LTkfBU")

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
            
            # 1. Prepare AI Prompt
            symptoms = []
            if complaint.has_fever: symptoms.append("Fever")
            if complaint.has_diarrhea: symptoms.append("Diarrhea")
            if complaint.has_vomiting: symptoms.append("Vomiting")
            
            prompt = (f"User in {complaint.village.name} reported {', '.join(symptoms)}. "
                      f"Environment: Stagnant water={complaint.stagnant_water}. "
                      f"Give 3 short 'Do's' and 3 short 'Don'ts' for community health safety.")
            
            # 2. Call Gemini AI
            try:
                model = genai.GenerativeModel('gemini-pro')
                response = model.generate_content(prompt)
                complaint.ai_suggestion = response.text
            except Exception:
                complaint.ai_suggestion = "Stay hydrated and keep surroundings clean of stagnant water."
            
            # 3. Save and Redirect
            complaint.save()
            return render(request, 'complaints/complaint_success.html', {
                'ai_advice': complaint.ai_suggestion,
                'complaint': complaint # Useful for displaying the uploaded image
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

    if request.method == 'POST':
        form = HealthWorkerReportForm(request.POST, request.FILES)
        if form.is_valid():
            report = form.save(commit=False)
            report.user = request.user
            report.village = request.user.village
            
            # --- GEMINI AI LOGIC FOR HEALTH WORKER ---
            # Professional prompt for community-level data
            prompt = (f"Health Worker reported {report.affected_count} affected people in {report.village.name}. "
                      f"Environmental issues: Stagnant water={report.stagnant_water}, Mosquitoes={report.mosquito_severity}. "
                      f"Give 3 professional 'Community Actions' and 3 'Safety Measures' for this area.")
            
            try:
                model = genai.GenerativeModel('gemini-pro')
                response = model.generate_content(prompt)
                report.ai_suggestion = response.text
            except Exception:
                report.ai_suggestion = "Ensure community water sources are tested and vector control measures are escalated."
            
            report.save()
            # Redirect to success page with AI data and the report object
            return render(request, 'complaints/complaint_success.html', {
                'ai_advice': report.ai_suggestion,
                'complaint': report 
            })
    else:
        form = HealthWorkerReportForm()
    
    return render(request, 'complaints/health_worker_report.html', {'form': form})

@login_required
def my_submissions_view(request):
    submissions = Complaint.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'complaints/my_submissions.html', {'submissions': submissions})

def complaint_success_view(request):
    return render(request, 'complaints/complaint_success.html')