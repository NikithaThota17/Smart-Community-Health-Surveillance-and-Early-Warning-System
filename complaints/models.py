from django.db import models
from django.conf import settings
from locations.models import Village

class Complaint(models.Model):
    REPORT_SOURCE_CHOICES = [
        ('citizen', 'Citizen Report'),
        ('health_worker', 'Health Worker Report'),
    ]
    SEVERITY_CHOICES = [('low', 'Low'), ('medium', 'Medium'), ('high', 'High')]
    STATUS_CHOICES = [
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('assigned', 'Assigned to Health Worker'),
        ('verified', 'Verified by Health Worker'),
        ('actioned', 'Admin Actioned'),
        ('resolved', 'Resolved'),
        ('escalated', 'Escalated'),
    ]
    
    # User and Location Links
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    village = models.ForeignKey(Village, on_delete=models.CASCADE, null=True, blank=True)
    report_source = models.CharField(max_length=20, choices=REPORT_SOURCE_CHOICES, default='citizen')
    parent_complaint = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='follow_up_reports',
    )
    
    # Citizen specific: Symptom Checkboxes [cite: 79-80]
    has_fever = models.BooleanField(default=False)
    has_diarrhea = models.BooleanField(default=False)
    has_vomiting = models.BooleanField(default=False)
    has_headache = models.BooleanField(default=False)
    has_body_pain = models.BooleanField(default=False)
    has_cough = models.BooleanField(default=False)
    has_cold = models.BooleanField(default=False)
    has_skin_rash = models.BooleanField(default=False)
    has_fatigue = models.BooleanField(default=False)
    has_breathing_difficulty = models.BooleanField(default=False)
    
    # Health Worker specific: Community impact [cite: 97]
    affected_count = models.PositiveIntegerField(default=0)
    
    # Environmental indicators [cite: 81-85]
    mosquito_severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='low')
    stagnant_water = models.BooleanField(default=False)
    waste_issue = models.BooleanField(default=False)
    water_contamination = models.BooleanField(default=False)
    drainage_issue = models.BooleanField(default=False)
    garbage_dumping = models.BooleanField(default=False)
    foul_smell = models.BooleanField(default=False)
    unsafe_drinking_water = models.BooleanField(default=False)
    nearby_illness_cases = models.BooleanField(default=False)
    
    # NEW: Visual evidence and AI intelligence 
    report_image = models.ImageField(upload_to='complaints/', null=True, blank=True)
    ai_suggestion = models.TextField(blank=True, null=True)
    medication_guidance = models.TextField(blank=True, null=True)
    
    description = models.TextField(blank=True, null=True)
    personal_risk_score = models.FloatField(null=True, blank=True)
    personal_risk_level = models.CharField(max_length=10, choices=SEVERITY_CHOICES, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='submitted')
    priority = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='medium')
    assigned_health_worker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_complaints',
    )
    field_visit_required = models.BooleanField(default=False)
    field_visit_completed = models.BooleanField(default=False)
    assigned_at = models.DateTimeField(null=True, blank=True)
    field_visit_due_at = models.DateTimeField(null=True, blank=True)
    camp_recommended = models.BooleanField(default=False)
    admin_action = models.TextField(blank=True, null=True)
    escalation_target = models.CharField(max_length=120, blank=True, null=True)
    verification_notes = models.TextField(blank=True, null=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        village_name = self.village.name if self.village else "Unknown Village"
        return f"Report by {self.user.email} in {village_name} ({self.created_at})"

    @property
    def symptom_count(self):
        return sum(
            [
                self.has_fever,
                self.has_diarrhea,
                self.has_vomiting,
                self.has_headache,
                self.has_body_pain,
                self.has_cough,
                self.has_cold,
                self.has_skin_rash,
                self.has_fatigue,
                self.has_breathing_difficulty,
            ]
        )

    @property
    def is_pending_field_visit(self):
        return (
            self.field_visit_required
            and not self.field_visit_completed
            and self.status in {'assigned', 'under_review', 'submitted'}
        )

    @property
    def is_overdue(self):
        if not self.field_visit_due_at or not self.is_pending_field_visit:
            return False
        from django.utils import timezone
        return self.field_visit_due_at < timezone.now()
