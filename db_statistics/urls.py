"""URL routes for the db_statistics app."""

from django.urls import path

from db_statistics import views

app_name = "db_statistics"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("dashboard/", views.dashboard, name="dashboard_home"),
    path("<slug:section>/", views.dashboard, name="dashboard_section"),
]
