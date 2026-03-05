from django.urls import path
from .views import  citizen_dashboard_view ,admin_dashboard

app_name = 'dashboard'

urlpatterns = [
    # General dashboard redirect handled by accounts app
    path('admin/', admin_dashboard, name='admin_dashboard'),
    path('citizen/', citizen_dashboard_view, name='citizen_dashboard'),
]