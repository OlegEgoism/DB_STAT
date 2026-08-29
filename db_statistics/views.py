"""Compatibility exports for the interface-specific view modules.

New code should import views from the module matching the sidebar section.
"""

from db_statistics.views_additional import audit_events, connections, delete_connection, favorites, home, language_settings, login, logout, page_not_found, sidebar_settings, test_connection
from db_statistics.views_administration import database_groups_list, database_users_list, maintenance_jobs, maintenance_operation, maintenance_stats, memory_overview
from db_statistics.views_data import database_functions_list, database_schema_sizes, database_table_sizes, database_temp_table_sizes, database_views_list, distribution_info, distribution_tables
from db_statistics.views_infrastructure import database_overview, segments_info
from db_statistics.views_performance import active_queries, active_sessions, blocking_locks, idle_transactions, terminate_active_query, terminate_active_session

__all__ = [
    "database_overview",
    "segments_info",
    "database_schema_sizes",
    "database_table_sizes",
    "database_views_list",
    "database_functions_list",
    "distribution_tables",
    "distribution_info",
    "database_temp_table_sizes",
    "active_queries",
    "terminate_active_query",
    "active_sessions",
    "terminate_active_session",
    "blocking_locks",
    "idle_transactions",
    "memory_overview",
    "database_users_list",
    "database_groups_list",
    "maintenance_stats",
    "maintenance_operation",
    "maintenance_jobs",
    "maintenance_vacuum",
    "page_not_found",
    "home",
    "login",
    "logout",
    "sidebar_settings",
    "favorites",
    "language_settings",
    "audit_events",
    "connections",
    "test_connection",
    "delete_connection",
]

# Обратная совместимость для импортов прежнего VACUUM-only endpoint.
maintenance_vacuum = maintenance_operation
