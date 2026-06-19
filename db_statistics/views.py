from django.http import Http404
from django.shortcuts import render

DASHBOARD_SECTIONS = {
    "dashboard",
    "segments",
    "cluster-health",
    "databases",
    "tables",
    "distribution",
    "temp-tables",
    "queries",
    "locks",
    "transactions",
    "memory",
    "bloat",
    "maintenance",
}


def dashboard(request, section="dashboard"):
    """Render the monitoring dashboard with the requested section selected."""
    if section not in DASHBOARD_SECTIONS:
        raise Http404("Dashboard section does not exist")

    return render(request, "te6.html", {"initial_page": section})
