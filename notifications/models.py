from django.db import models
from django.conf import settings
from locations.models import Village
from analytics.models import RiskRecord

class Notification(models.Model):
    CATEGORY_CHOICES = [
        ('risk_alert', 'Risk Alert'),
        ('assignment', 'Assignment'),
        ('resolution', 'Resolution'),
        ('escalation', 'Escalation'),
        ('system', 'System'),
    ]

    # Link to the ML output that triggered the alert [cite: 54]
    risk_record = models.ForeignKey(RiskRecord, on_delete=models.CASCADE, null=True, blank=True)
    village = models.ForeignKey(Village, on_delete=models.CASCADE, null=True, blank=True)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='workflow_notifications',
    )
    complaint = models.ForeignKey(
        'complaints.Complaint',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
    )
    
    # Alert status tracking 
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='risk_alert')
    title = models.CharField(max_length=120, blank=True, default='')
    is_read = models.BooleanField(default=False)
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Content of the notification 
    message = models.TextField()

    def __str__(self):
        status = "Resolved" if self.is_resolved else "Active"
        target = self.village.name if self.village else self.title or "Workflow Notification"
        return f"Alert for {target} - {status}"
