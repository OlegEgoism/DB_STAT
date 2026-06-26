from django.urls import path

from db_statistics import views

urlpatterns = [
    path("", views.home, name="home"),
    path("cluster/status/", views.cluster_status, name="cluster_status"),
    path("connections/", views.connections, name="connections"),
    path("connections/test/", views.test_connection, name="test_connection"),
    path("connections/delete/", views.delete_connection, name="delete_connection"),
    path("databases/size/", views.database_size, name="database_size"),
    path("databases/schemas/", views.database_schema_sizes, name="database_schema_sizes"),
    path("segments/info/", views.segments_info, name="segments_info"),
]
