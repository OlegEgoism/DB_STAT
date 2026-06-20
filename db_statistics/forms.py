from django import forms

from db_statistics.models import DBConnection


class DBConnectionForm(forms.ModelForm):
    """Форма создания и редактирования подключения к БД."""

    password = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput(render_value=True, attrs={"autocomplete": "new-password"}),
    )

    class Meta:
        model = DBConnection
        fields = ["name", "db_type", "host", "port", "database", "username", "password", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "Production Greenplum"}),
            "host": forms.TextInput(attrs={"placeholder": "db.example.local"}),
            "database": forms.TextInput(attrs={"placeholder": "postgres"}),
            "username": forms.TextInput(attrs={"placeholder": "gpadmin"}),
        }
