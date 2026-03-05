from django import forms
from .models import Complaint

class CitizenComplaintForm(forms.ModelForm):
    class Meta:
        model = Complaint
        fields = [
            'has_fever', 'has_diarrhea', 'has_vomiting', 'has_headache', 'has_body_pain',
            'mosquito_severity', 'stagnant_water', 'waste_issue', 'water_contamination',
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
    class Meta:
        model = Complaint
        fields = [
            'affected_count', 'mosquito_severity', 'stagnant_water', 
            'waste_issue', 'water_contamination', 'report_image', 'description'
        ]
        widgets = {
            'affected_count': forms.NumberInput(attrs={
                'class': 'w-full p-4 bg-slate-50 border border-slate-200 rounded-2xl outline-none focus:border-[#0F766E]',
                'placeholder': 'Number of people affected'
            }),
            'mosquito_severity': forms.Select(attrs={'class': 'w-full p-4 bg-slate-50 border border-slate-200 rounded-2xl'}),
            'description': forms.Textarea(attrs={'class': 'w-full p-4 bg-slate-50 border border-slate-200 rounded-2xl', 'rows': 3}),
        }