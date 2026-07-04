from django.contrib import admin

from db_statistics.models import DBAudit, DBConnection, DBUser, DBNotification


class BaseAdmin(admin.ModelAdmin):
    """Базовые настройки"""

    readonly_fields = ("created", "updated")
    date_hierarchy = "created"
    list_per_page = 20


@admin.register(DBUser)
class DBUserAdmin(BaseAdmin):
    """Пользователь"""

    list_display = ("login", "email", "role", "count_column", "is_active", "created", "updated")
    list_filter = ("is_active", "role")
    list_editable = ("is_active",)
    search_fields = ("login", "email")
    search_help_text = "Поиск по: логин, почта"
    fields = ("login", "email", "role", "is_active", "connections", "created", "updated")
    filter_horizontal = ("connections",)

    @admin.display(description="Количество подключений")
    def count_column(self, obj):
        return str(obj.connections.count())


@admin.register(DBConnection)
class DBConnectionAdmin(BaseAdmin):
    """Подключение"""

    list_display = ("name", "host", "port", "username", "database", "created_user", "users_count", "is_active", "created", "updated")
    list_filter = ("is_active", "db_type")
    list_editable = ("is_active",)
    search_fields = ("name", "database", "username")
    search_help_text = "Поиск по: названию, базе данных, пользователю"
    fields = ("name", "host", "port", "database", "username", "db_type", "created_user", "is_active", "created", "updated")

    @admin.display(description="Количество пользователей")
    def users_count(self, obj):
        return obj.dbuser_set.count()


@admin.register(DBAudit)
class DBAuditAdmin(admin.ModelAdmin):
    """Аудит"""

    list_display = ("username", "action_type", "short_info", "created")
    list_filter = ("action_type",)
    search_fields = ("username", "info")
    search_help_text = "Поиск по: пользователю, информации"
    date_hierarchy = "created"
    list_per_page = 20
    fields = ("username", "action_type", "info", "created")
    readonly_fields = ("username", "action_type", "info", "created")
    ordering = ("-created",)

    @admin.display(description="Информация")
    def short_info(self, obj):
        return obj.info[:120] + ("…" if len(obj.info) > 120 else "")


@admin.register(DBNotification)
class DBNotificationAdmin(BaseAdmin):
    """Настройки уведомлений"""

    list_display = ("connection", "users_count", "is_active", "created", "updated")
    list_filter = ("is_active",)
    list_editable = ("is_active",)
    search_fields = ("connection",)
    search_help_text = "Поиск по: базе данных"
    fields = ("connection", "interval_update", "segment_monitor", "temp_tables_monitor", "query_monitor", "query_threshold", "lock_monitor", "lock_threshold", "transaction_monitor", "transactions_threshold", "is_active", "user", "created", "updated")
    filter_horizontal = ("user",)

    @admin.display(description="Количество пользователей")
    def users_count(self, obj):
        return obj.user.count()
