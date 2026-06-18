from django import forms

from .models import DatabaseConnection


class DatabaseConnectionForm(forms.ModelForm):
    class Meta:
        model = DatabaseConnection
        fields = ["name", "db_type", "host", "port", "database", "username", "password"]
        widgets = {"password": forms.PasswordInput(render_value=True)}
