from django import forms
from .models import Complaint


class CitizenComplaintForm(forms.ModelForm):
    class Meta:
        model = Complaint
        fields = [
            'has_fever', 'has_diarrhea', 'has_vomiting', 'has_headache', 'has_body_pain',
            'has_cough', 'has_cold', 'has_skin_rash', 'has_fatigue', 'has_breathing_difficulty',
            'mosquito_severity', 'stagnant_water', 'waste_issue', 'water_contamination',
            'drainage_issue', 'garbage_dumping', 'foul_smell', 'unsafe_drinking_water', 'nearby_illness_cases',
            'report_image', 'description'
        ]
        widgets = {
            'mosquito_severity': forms.Select(attrs={
                'class': 'w-full p-4 bg-slate-50 border border-slate-200 rounded-2xl outline-none focus:border-[#0F766E]'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full p-4 bg-slate-50 border border-slate-200 rounded-2xl outline-none focus:border-[#0F766E]',
                'rows': 3,
                'placeholder': 'Explain your symptoms or environmental concerns...'
            }),
            'report_image': forms.ClearableFileInput(attrs={
                'class': 'w-full p-4 border border-dashed border-slate-200 rounded-2xl'
            }),
        }

class HealthWorkerReportForm(forms.ModelForm):
    linked_complaint = forms.ModelChoiceField(
        queryset=Complaint.objects.none(),
        required=False,
        empty_label="Select linked citizen complaint",
        widget=forms.Select(attrs={'class': 'w-full p-4 bg-slate-50 border border-slate-200 rounded-2xl'})
    )

    class Meta:
        model = Complaint
        fields = [
            'linked_complaint',
            'affected_count', 'mosquito_severity', 'stagnant_water', 
            'waste_issue', 'water_contamination', 'drainage_issue', 'garbage_dumping',
            'foul_smell', 'unsafe_drinking_water', 'nearby_illness_cases',
            'field_visit_required', 'field_visit_completed', 'camp_recommended',
            'verification_notes', 'report_image', 'description'
        ]
        widgets = {
            'affected_count': forms.NumberInput(attrs={
                'class': 'w-full p-4 bg-slate-50 border border-slate-200 rounded-2xl outline-none focus:border-[#0F766E]',
                'placeholder': 'Number of people affected'
            }),
            'mosquito_severity': forms.Select(attrs={'class': 'w-full p-4 bg-slate-50 border border-slate-200 rounded-2xl'}),
            'description': forms.Textarea(attrs={'class': 'w-full p-4 bg-slate-50 border border-slate-200 rounded-2xl', 'rows': 3}),
            'verification_notes': forms.Textarea(attrs={
                'class': 'w-full p-4 bg-slate-50 border border-slate-200 rounded-2xl',
                'rows': 3,
                'placeholder': 'Enter field verification findings and symptoms seen in the community'
            }),
        }

    def __init__(self, *args, **kwargs):
        village = kwargs.pop('village', None)
        super().__init__(*args, **kwargs)
        if village is not None:
            self.fields['linked_complaint'].queryset = Complaint.objects.filter(
                village=village,
                report_source='citizen',
            ).exclude(status='resolved').order_by('-created_at')


class AdminActionForm(forms.ModelForm):
    class Meta:
        model = Complaint
        fields = [
            'status',
            'priority',
            'assigned_health_worker',
            'field_visit_required',
            'field_visit_completed',
            'camp_recommended',
            'admin_action',
            'escalation_target',
        ]
        widgets = {
            'status': forms.Select(attrs={'class': 'w-full p-3 bg-slate-50 border border-slate-200 rounded-xl'}),
            'priority': forms.Select(attrs={'class': 'w-full p-3 bg-slate-50 border border-slate-200 rounded-xl'}),
            'assigned_health_worker': forms.Select(attrs={'class': 'w-full p-3 bg-slate-50 border border-slate-200 rounded-xl'}),
            'admin_action': forms.Textarea(attrs={
                'class': 'w-full p-3 bg-slate-50 border border-slate-200 rounded-xl',
                'rows': 4,
                'placeholder': 'Describe the action taken for this complaint'
            }),
            'escalation_target': forms.TextInput(attrs={
                'class': 'w-full p-3 bg-slate-50 border border-slate-200 rounded-xl',
                'placeholder': 'PHC / Medical Officer / District Health Office'
            }),
        }

    def __init__(self, *args, **kwargs):
        health_workers = kwargs.pop('health_workers', None)
        super().__init__(*args, **kwargs)
        queryset = health_workers if health_workers is not None else self.fields['assigned_health_worker'].queryset.none()
        self.fields['assigned_health_worker'].queryset = queryset
        self.fields['assigned_health_worker'].required = False
