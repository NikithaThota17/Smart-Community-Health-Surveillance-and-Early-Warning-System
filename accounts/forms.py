from django import forms
from .models import User

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'profile_picture']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'w-full p-4 bg-slate-50 border border-slate-200 rounded-2xl outline-none focus:border-[#0F766E]'}),
            'first_name': forms.TextInput(attrs={'class': 'w-full p-4 bg-slate-50 border border-slate-200 rounded-2xl outline-none focus:border-[#0F766E]'}),
            'last_name': forms.TextInput(attrs={'class': 'w-full p-4 bg-slate-50 border border-slate-200 rounded-2xl outline-none focus:border-[#0F766E]'}),
        }