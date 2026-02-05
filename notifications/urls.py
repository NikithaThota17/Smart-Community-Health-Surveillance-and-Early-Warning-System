from django.urls import path
from .views import alert_list_view, resolve_alert_view

app_name = 'notifications'

urlpatterns = [
    # View all active health alerts [cite: 322-330]
    path('alerts/', alert_list_view, name='alert_list'),
    # Admin only: Mark alert as resolved [cite: 57]
    path('resolve/<int:alert_id>/', resolve_alert_view, name='resolve_alert'),
]