from django.urls import path

from db_statistics import views

urlpatterns = [
    path("", views.home, name="home"),
    path("cluster/status/", views.cluster_status, name="cluster_status"),
]
