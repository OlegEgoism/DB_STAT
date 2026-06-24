from django.urls import path

from db_statistics import views

app_name = "db_statistics"

urlpatterns = [
    path("", views.connection_list, name="connections"),
    path("connections/<int:pk>/delete/", views.connection_delete, name="connection_delete"),
]
