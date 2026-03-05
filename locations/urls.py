from django.urls import path
from . import views

app_name = "locations"

urlpatterns = [
    path("ajax/load-states/", views.load_states, name="ajax_load_states"),
    path("ajax/load-districts/", views.load_districts, name="ajax_load_districts"),
    path("ajax/load-mandals/", views.load_mandals, name="ajax_load_mandals"),
    path("ajax/load-villages/", views.load_villages, name="ajax_load_villages"),
]
