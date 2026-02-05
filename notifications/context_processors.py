from .models import Notification

def alert_notifications(request):
    """
    Global context processor to push high-risk alerts to the UI. [cite: 54]
    """
    if request.user.is_authenticated and request.user.role == 'citizen' and request.user.village:
        # Check for unresolved high-risk alerts for the user's village [cite: 323]
        active_alert = Notification.objects.filter(
            village=request.user.village, 
            is_resolved=False,
            risk_record__risk_level='high'
        ).first()
        
        if active_alert:
            return {'GLOBAL_ALERT': active_alert.message}
            
    return {'GLOBAL_ALERT': None}