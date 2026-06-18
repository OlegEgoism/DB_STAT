from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import DatabaseConnectionForm
from .models import DatabaseConnection
from .services import DatabaseInspectionError, inspect_database


def home(request):
    form = DatabaseConnectionForm()
    connections = DatabaseConnection.objects.all()
    return render(request, "db_statistics/home.html", {"connections": connections, "form": form})


def create_connection(request):
    if request.method != "POST":
        return redirect("home")

    form = DatabaseConnectionForm(request.POST)
    if form.is_valid():
        connection = form.save()
        messages.success(request, "Подключение создано.")
        response = render(request, "db_statistics/partials/connection_card.html", {"connection": connection})
        response["HX-Redirect"] = reverse("home")
        return response

    response = render(request, "db_statistics/partials/connection_form.html", {"form": form})
    response.status_code = 422
    return response


def connection_detail(request, pk):
    connection = get_object_or_404(DatabaseConnection, pk=pk)
    context = {"connection": connection}
    try:
        context["metadata"] = inspect_database(connection)
        context["is_connected"] = True
    except DatabaseInspectionError as exc:
        context["error"] = exc
        context["is_connected"] = False
    return render(request, "db_statistics/detail.html", context)
