from django.contrib import admin
from .models import State, District, Mandal, Village

@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ('name', 'state')
    list_filter = ('state',)

@admin.register(Mandal)
class MandalAdmin(admin.ModelAdmin):
    list_display = ('name', 'district')
    list_filter = ('district__state', 'district')

@admin.register(Village)
class VillageAdmin(admin.ModelAdmin):
    list_display = ('name', 'mandal', 'is_active')
    list_filter = ('is_active', 'mandal__district')