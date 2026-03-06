from django.db import models
from locations.models import Village
from analytics.models import RiskRecord

class Notification(models.Model):
    # Link to the ML output that triggered the alert [cite: 54]
    risk_record = models.ForeignKey(RiskRecord, on_delete=models.CASCADE)
    village = models.ForeignKey(Village, on_delete=models.CASCADE)
    
    # Alert status tracking 
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Content of the notification 
    message = models.TextField()

    def __str__(self):
        status = "Resolved" if self.is_resolved else "Active"
        return f"Alert for {self.village.name} - {status}"