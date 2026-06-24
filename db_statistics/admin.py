from django.contrib import admin

from db_statistics.models import DBUser, DBConnection


class BaseAdmin(admin.ModelAdmin):
    readonly_fields = ("created", "updated")
    date_hierarchy = "created"
    list_per_page = 20


@admin.register(DBUser)
class DBUserAdmin(BaseAdmin):
    list_display = ("login", "email", "role", "count_column", "is_active", "created", "updated")
    list_filter = ("role", "is_active")
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
    list_display = ("name", "host", "port", "username", "database", "users_count", "is_active", "created", "updated")
    list_filter = ("db_type", "is_active")
    list_editable = ("is_active",)
    search_fields = ("name", "database", "username")
    search_help_text = "Поиск по: названию, базе данных, пользователю"
    fields = ("name", "host", "port", "database", "username", "password", "db_type", "is_active", "created", "updated")

    @admin.display(description="Количество пользователей")
    def users_count(self, obj):
        return obj.dbuser_set.count()
