from django.contrib import admin

from .models import DatabaseConnection


@admin.register(DatabaseConnection)
class DatabaseConnectionAdmin(admin.ModelAdmin):
    list_display = ("name", "db_type", "host", "port", "database", "username", "updated_at")
    search_fields = ("name", "host", "database", "username")
    list_filter = ("db_type",)
