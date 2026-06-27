from django.urls import path

from db_statistics import views

urlpatterns = [
    path("", views.home, name="home"),
    path("cluster/status/", views.cluster_status, name="cluster_status"),
    path("connections/", views.connections, name="connections"),
    path("connections/test/", views.test_connection, name="test_connection"),
    path("connections/delete/", views.delete_connection, name="delete_connection"),
    path("databases/size/", views.database_size, name="database_size"),
    path("databases/overview/", views.database_overview, name="database_overview"),
    path("databases/schemas/", views.database_schema_sizes, name="database_schema_sizes"),
    path("tables/sizes/", views.database_table_sizes, name="database_table_sizes"),
    path("views/list/", views.database_views_list, name="database_views_list"),
    path("distribution/tables/", views.distribution_tables, name="distribution_tables"),
    path("distribution/info/", views.distribution_info, name="distribution_info"),
    path("temp-tables/sizes/", views.database_temp_table_sizes, name="database_temp_table_sizes"),
    path("queries/active/", views.active_queries, name="active_queries"),
    path("locks/blocking/", views.blocking_locks, name="blocking_locks"),
    path("segments/info/", views.segments_info, name="segments_info"),
]
