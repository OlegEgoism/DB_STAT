from django.conf import settings
from django.shortcuts import redirect

from db_statistics.licensing import license_status


class LicenseRequiredMiddleware:
    """Не допускает работу приложения до загрузки действующей лицензии."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        static_path = f"/{settings.STATIC_URL.lstrip('/')}"
        if request.path.startswith(("/license/", static_path)):
            return self.get_response(request)
        if not license_status().valid:
            return redirect("license_activation")
        return self.get_response(request)
