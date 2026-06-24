from django.shortcuts import render


def home(request):
    """Главная страница мониторинга БД."""
    return render(request, "home.html")


def cluster_status(request):
    """HTMX-фрагмент с текущим статусом кластера.

    Пока данные моковые; дальше сюда можно подключить результаты SQL-проверок
    PostgreSQL/Greenplum из раздела мониторинга работоспособности.
    """
    return render(
        request,
        "partials/_cluster_status.html",
        {"cluster_status_color": "green", "cluster_status_text": "Кластер работает"},
    )
