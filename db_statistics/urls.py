from django.urls import path, re_path

from db_statistics import views_additional, views_administration, views_data, views_infrastructure, views_performance

urlpatterns = [
    path("", views_additional.home, name="home"),
    path("login/", views_additional.login, name="login"),
    path("logout/", views_additional.logout, name="logout"),
    path("audit/events/", views_additional.audit_events, name="audit_events"),
    path(
        "settings/sidebar/", views_additional.sidebar_settings, name="sidebar_settings"
    ),
    path(
        "settings/language/",
        views_additional.language_settings,
        name="language_settings",
    ),
    path("favorites/", views_additional.favorites, name="favorites"),
    path("connections/", views_additional.connections, name="connections"),
    path("connections/test/", views_additional.test_connection, name="test_connection"),
    path(
        "connections/delete/",
        views_additional.delete_connection,
        name="delete_connection",
    ),
    path(
        "databases/overview/",
        views_infrastructure.database_overview,
        name="database_overview",
    ),
    path(
        "databases/schemas/",
        views_data.database_schema_sizes,
        name="database_schema_sizes",
    ),
    path("tables/sizes/", views_data.database_table_sizes, name="database_table_sizes"),
    path("views/list/", views_data.database_views_list, name="database_views_list"),
    path(
        "functions/list/",
        views_data.database_functions_list,
        name="database_functions_list",
    ),
    path(
        "distribution/tables/",
        views_data.distribution_tables,
        name="distribution_tables",
    ),
    path("distribution/info/", views_data.distribution_info, name="distribution_info"),
    path(
        "temp-tables/sizes/",
        views_data.database_temp_table_sizes,
        name="database_temp_table_sizes",
    ),
    path("queries/active/", views_performance.active_queries, name="active_queries"),
    path(
        "queries/terminate/",
        views_performance.terminate_active_query,
        name="terminate_active_query",
    ),
    path("sessions/active/", views_performance.active_sessions, name="active_sessions"),
    path(
        "sessions/terminate/",
        views_performance.terminate_active_session,
        name="terminate_active_session",
    ),
    path("locks/blocking/", views_performance.blocking_locks, name="blocking_locks"),
    path(
        "transactions/idle/",
        views_performance.idle_transactions,
        name="idle_transactions",
    ),
    path(
        "memory/overview/", views_administration.memory_overview, name="memory_overview"
    ),
    path(
        "memory/runtime/",
        views_administration.runtime_memory_usage,
        name="runtime_memory_usage",
    ),
    path(
        "maintenance/stats/",
        views_administration.maintenance_stats,
        name="maintenance_stats",
    ),
    path(
        "maintenance/vacuum/",
        views_administration.maintenance_vacuum,
        name="maintenance_vacuum",
    ),
    path(
        "users/list/",
        views_administration.database_users_list,
        name="database_users_list",
    ),
    path(
        "groups/list/",
        views_administration.database_groups_list,
        name="database_groups_list",
    ),
    path("segments/info/", views_infrastructure.segments_info, name="segments_info"),
    # Последний маршрут позволяет проверять фирменную 404-страницу и при DEBUG=True.
    re_path(r"^.*$", views_additional.page_not_found, name="page_not_found"),
]
