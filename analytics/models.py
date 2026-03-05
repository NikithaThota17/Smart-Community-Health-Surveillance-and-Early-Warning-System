from django.db import models
from locations.models import Village

class RiskRecord(models.Model):
    """Stores output from the ML Risk Engine[cite: 198]."""
    RISK_LEVELS = [
        ('low', 'Low Risk'),
        ('medium', 'Medium Risk'),
        ('high', 'High Risk'),
    ]

    village = models.ForeignKey(Village, on_delete=models.CASCADE)
    probability_score = models.FloatField()  # Raw Logistic Regression output (0.0 - 1.0) [cite: 195]
    risk_level = models.CharField(max_length=10, choices=RISK_LEVELS)
    calculated_at = models.DateTimeField(auto_now_add=True)
    
    # Feature tracking for audit and charts [cite: 147-151]
    total_complaints = models.IntegerField()
    symptom_count = models.IntegerField()

    def __str__(self):
        return f"{self.village.name} - {self.risk_level} ({self.calculated_at.strftime('%Y-%m-%d')})"

    class Meta:
        ordering = ['-calculated_at']