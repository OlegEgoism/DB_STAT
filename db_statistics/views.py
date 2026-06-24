from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from db_statistics.forms import DBConnectionForm
from db_statistics.models import DBConnection
from db_statistics.services import load_segment_dashboard


@require_http_methods(["GET", "POST"])
def connection_list(request):
    """Главная страница: CRUD подключений и стартовый дашборд сегментов."""

    editing_connection = None
    if request.method == "POST":
        connection_id = request.POST.get("connection_id")
        if connection_id:
            editing_connection = get_object_or_404(DBConnection, pk=connection_id)
            form = DBConnectionForm(request.POST, instance=editing_connection)
            success_message = "Подключение обновлено"
        else:
            form = DBConnectionForm(request.POST)
            success_message = "Подключение создано"

        if form.is_valid():
            saved_connection = form.save()
            messages.success(request, success_message)
            return redirect(f"{reverse('db_statistics:connections')}?connection={saved_connection.pk}")
    else:
        edit_id = request.GET.get("edit")
        if edit_id:
            editing_connection = get_object_or_404(DBConnection, pk=edit_id)
            form = DBConnectionForm(instance=editing_connection)
        else:
            form = DBConnectionForm()

    connections = DBConnection.objects.order_by("name", "host")
    selected_connection = None
    dashboard = None
    selected_id = request.GET.get("connection")

    if selected_id:
        selected_connection = get_object_or_404(DBConnection, pk=selected_id)
    elif connections.exists():
        selected_connection = connections.first()

    if selected_connection and selected_connection.is_active:
        dashboard = load_segment_dashboard(selected_connection)

    return render(
        request,
        "db_statistics/connections.html",
        {
            "connections": connections,
            "dashboard": dashboard,
            "editing_connection": editing_connection,
            "form": form,
            "selected_connection": selected_connection,
        },
    )


@require_POST
def connection_delete(request, pk):
    connection = get_object_or_404(DBConnection, pk=pk)
    connection.delete()
    messages.success(request, "Подключение удалено")
    return redirect("db_statistics:connections")
