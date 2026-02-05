from django.urls import path
from .views import (
    citizen_complaint_view, 
    health_worker_report_view, 
    complaint_success_view,
    my_submissions_view
)

app_name = 'complaints'

urlpatterns = [
    path('submit/', citizen_complaint_view, name='submit_complaint'),
    path('field-report/', health_worker_report_view, name='health_worker_report'),
    path('success/', complaint_success_view, name='complaint_success'),
    path('history/', my_submissions_view, name='my_submissions'),
]