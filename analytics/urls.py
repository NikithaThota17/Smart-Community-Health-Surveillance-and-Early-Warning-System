from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    # ML Engine Management
    path('trigger-analysis/', views.trigger_analysis, name='trigger_analysis'),
    
    # Data Export Endpoints [cite: 119-123]
    path('export/csv/', views.export_complaints_csv, name='export_complaints_csv'),
    path('export/pdf/', views.export_risk_pdf, name='export_risk_pdf'),
]