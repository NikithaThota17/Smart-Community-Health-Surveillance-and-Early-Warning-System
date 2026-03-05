from django.db import models
from django.conf import settings
from locations.models import Village

class Complaint(models.Model):
    SEVERITY_CHOICES = [('low', 'Low'), ('medium', 'Medium'), ('high', 'High')]
    
    # User and Location Links
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    village = models.ForeignKey(Village, on_delete=models.CASCADE, null=True, blank=True)
    
    # Citizen specific: Symptom Checkboxes [cite: 79-80]
    has_fever = models.BooleanField(default=False)
    has_diarrhea = models.BooleanField(default=False)
    has_vomiting = models.BooleanField(default=False)
    has_headache = models.BooleanField(default=False)
    has_body_pain = models.BooleanField(default=False)
    
    # Health Worker specific: Community impact [cite: 97]
    affected_count = models.PositiveIntegerField(default=0)
    
    # Environmental indicators [cite: 81-85]
    mosquito_severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='low')
    stagnant_water = models.BooleanField(default=False)
    waste_issue = models.BooleanField(default=False)
    water_contamination = models.BooleanField(default=False)
    
    # NEW: Visual evidence and AI intelligence 
    report_image = models.ImageField(upload_to='complaints/', null=True, blank=True)
    ai_suggestion = models.TextField(blank=True, null=True)
    
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Report by {self.user.email} in {self.village.name} ({self.created_at})"