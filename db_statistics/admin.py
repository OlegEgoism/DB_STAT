from django import forms
from django.conf import settings
from django.contrib import admin
from django.contrib.auth.password_validation import validate_password
from django.urls import reverse
from django.utils.html import format_html_join

from db_statistics.models import DBAudit, DBConnection, DBFavorite, DBUser, DBUserSidebarSettings, MaintenanceJob

SIDEBAR_TAB_LABELS = settings.SIDEBAR_TAB_LABELS


class BaseAdmin(admin.ModelAdmin):
    """Базовые настройки"""

    readonly_fields = ("created", "updated")
    date_hierarchy = "created"
    list_per_page = 20


class DBUserAdminForm(forms.ModelForm):
    """Форма пользователя с явным заданием пароля вместо прямого редактирования хэша"""

    password1 = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput,
        required=False,
        help_text="Обязателен для нового пользователя. При редактировании оставьте пустым, чтобы не менять текущий пароль.",
    )
    password2 = forms.CharField(
        label="Подтверждение пароля", widget=forms.PasswordInput, required=False
    )

    class Meta:
        model = DBUser
        fields = ("login", "email", "role", "is_active", "is_staff", "is_superuser", "connections", "groups", "user_permissions")

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 != password2:
            raise forms.ValidationError("Пароли не совпадают")
        return password2

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("password1") and (
            self.instance.pk is None or not self.instance.password
        ):
            self.add_error("password1", "Укажите пароль для нового пользователя")
        return cleaned_data

    def _post_clean(self):
        super()._post_clean()
        password1 = self.cleaned_data.get("password1")
        if password1:
            try:
                validate_password(password1, self.instance)
            except forms.ValidationError as error:
                self.add_error("password1", error)

    def save(self, commit=True):
        user = super().save(commit=False)
        password1 = self.cleaned_data.get("password1")
        if password1:
            user.set_password(password1)
            user.failed_login_attempts = 0
            user.lockout_until = None
        if commit:
            user.save()
            self.save_m2m()
        return user


@admin.register(DBUser)
class DBUserAdmin(BaseAdmin):
    """Пользователь"""

    form = DBUserAdminForm
    list_display = ("login", "email", "role", "count_column", "is_active", "is_staff", "created", "updated")
    list_filter = ("is_active", "role", "is_staff", "is_superuser")
    list_editable = ("is_active",)
    search_fields = ("login", "email")
    search_help_text = "Поиск по: логин, почта"
    fields = ("login", "email", "role", "is_active", "password1", "password2", "is_staff", "is_superuser", "connections", "groups", "user_permissions", "created", "updated")
    filter_horizontal = ("connections", "groups", "user_permissions")

    @admin.display(description="Количество подключений")
    def count_column(self, obj):
        return str(obj.connections.count())


@admin.register(DBUserSidebarSettings)
class DBUserSidebarSettingsAdmin(BaseAdmin):
    """Настройки сайдбара"""

    list_display = ("user", "visible_tabs_display", "created", "updated")
    search_fields = ("user__login", "user__email")
    search_help_text = "Поиск по: логин, почта"
    fields = ("user", "visible_tabs_display", "created", "updated")
    readonly_fields = BaseAdmin.readonly_fields + ("visible_tabs_display", "user")

    @admin.display(description="Видимые вкладки")
    def visible_tabs_display(self, obj):
        stored_tabs = obj.visible_tabs.get("visible_tabs", []) if isinstance(obj.visible_tabs, dict) else obj.visible_tabs
        labels = [SIDEBAR_TAB_LABELS.get(tab, tab) for tab in stored_tabs or []]
        return ", ".join(labels) or "Все вкладки"


@admin.register(DBConnection)
class DBConnectionAdmin(BaseAdmin):
    """Подключение"""

    list_display = ("name", "host", "port", "username", "database", "created_user", "users_count", "is_active", "created", "updated")
    list_filter = ("is_active", "db_type")
    list_editable = ("is_active",)
    search_fields = ("name", "host", "database", "username", "dbuser__login")
    search_help_text = "Поиск по: названию, хосту, базе данных, пользователю БД, логину пользователя DB STAT"
    fields = ("name", "host", "port", "database", "username", "db_type", "created_user", "users_logins", "is_active", "created", "updated")
    readonly_fields = BaseAdmin.readonly_fields + ("name", "host", "port", "database", "username", "db_type", "created_user", "users_logins")

    def get_queryset(self, request):
        """Предзагружает назначенных пользователей для списка подключений"""
        return super().get_queryset(request).prefetch_related("dbuser_set")

    @admin.display(description="Доступ к этому подключению")
    def users_logins(self, obj):
        """Показывает логины пользователей с ссылками на их карточки"""
        users = obj.dbuser_set.all()
        if not users:
            return "—"
        return format_html_join(
            ", ",
            '<a href="{}">{}</a>',
            (
                (reverse("admin:db_statistics_dbuser_change", args=(user.pk,)), user.login)
                for user in users
            ),
        )

    @admin.display(description="Количество пользователей")
    def users_count(self, obj):
        return obj.dbuser_set.count()


@admin.register(DBFavorite)
class DBFavoriteAdmin(BaseAdmin):
    """Избранные объекты"""

    list_display = ("user", "connection", "object_type", "object_key", "created", "updated")
    list_filter = ("object_type", "connection")
    search_fields = ("user__login",)
    search_help_text = "Поиск по: логин"
    date_hierarchy = "created"
    list_per_page = 20
    fields = ("user", "connection", "object_type", "object_key", "created", "updated")
    readonly_fields = ("user", "connection", "object_type", "object_key", "created", "updated")
    ordering = ("-created",)


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


@admin.register(MaintenanceJob)
class MaintenanceJobAdmin(admin.ModelAdmin):
    """Фоновые операции обслуживания"""
    list_display = ("id", "operation", "connection", "schema_name", "table_name", "status", "created", "finished")
    list_filter = ("status", "operation", "connection")
    search_fields = ("schema_name", "table_name", "user__login", "connection__name")
    search_help_text = "Поиск по: схема, таблица, логин, название подключения"
    date_hierarchy = "created"
    list_per_page = 20
    readonly_fields = tuple(field.name for field in MaintenanceJob._meta.fields)
    ordering = ("-created",)
