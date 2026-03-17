from django.contrib import admin

from .models import Complaint


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'report_source',
        'user',
        'village',
        'priority',
        'status',
        'assigned_health_worker',
        'created_at',
    )
    list_filter = ('report_source', 'priority', 'status', 'village__mandal__district')
    search_fields = ('user__email', 'village__name', 'description', 'verification_notes')
