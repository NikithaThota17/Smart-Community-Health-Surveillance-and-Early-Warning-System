from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # 1. Django Admin
    path('admin/', admin.site.urls),
    
    # 2. Landing Page (Before Login) [cite: 56]
    path('', TemplateView.as_view(template_name='landing.html'), name='home'),
    
    # 3. Authentication & Profiles 
    path('accounts/', include('accounts.urls')),
    
    # 4. Location Management (Dynamic Dropdowns) 
    path('locations/', include('locations.urls')), 
    
    # 5. Dashboards (Admin/Citizen/Health Worker) [cite: 57]
    path('dashboard/', include('dashboard.urls')),
    
    # 6. Data Collection (Symptoms & Reports) 
    path('complaints/', include('complaints.urls')),
    
    # 7. ML Engine & Risk Recalculation 
    path('analytics/', include('analytics.urls')),
    
    # 8. Notifications & Alerts 
    path('notifications/', include('notifications.urls')),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) # Added for Profile Pictures