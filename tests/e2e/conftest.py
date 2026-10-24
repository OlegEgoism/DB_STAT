"""Фикстуры браузерных smoke-тестов.

Тесты обращаются к уже запущенному приложению по адресу E2E_BASE_URL (по умолчанию
http://127.0.0.1:8000). Перед тестами ждём ответа 200 от /healthz/. Если сервер так и не
ответил, тесты пропускаются. При E2E_REQUIRE_SERVER=1 (так настроен CI) они падают, чтобы
недоступный сервер не выглядел как успешный прогон.

Каталог tests/e2e намеренно без __init__.py: так `manage.py test` не находит эти тесты,
и они не требуют pytest и Chromium в обычных Django-тестах.
"""

import http.client
import os
import time
import urllib.error
import urllib.request

import pytest
from playwright.sync_api import sync_playwright

DEFAULT_BASE_URL = "http://127.0.0.1:8000"

# Прокси из окружения здесь только мешает: приложение локальное, поэтому запросы идут напрямую.
_DIRECT_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _is_server_up(base_url):
    try:
        with _DIRECT_OPENER.open(f"{base_url}/healthz/", timeout=2) as response:
            return response.status == 200
    except (urllib.error.URLError, http.client.HTTPException, OSError):
        return False


@pytest.fixture(scope="session")
def base_url():
    """Адрес приложения. Ждёт /healthz/ и пропускает тесты, если сервера нет."""
    url = os.getenv("E2E_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    wait_seconds = float(os.getenv("E2E_SERVER_WAIT_SECONDS", "5"))
    deadline = time.monotonic() + wait_seconds
    while not _is_server_up(url):
        if time.monotonic() >= deadline:
            message = f"Приложение не отвечает на {url}/healthz/. Запустите runserver или задайте E2E_BASE_URL."
            if os.getenv("E2E_REQUIRE_SERVER") == "1":
                pytest.fail(message)
            pytest.skip(message)
        time.sleep(0.5)
    return url


@pytest.fixture(scope="session")
def chromium_browser():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture
def page(chromium_browser, base_url):
    """Новый контекст на каждый тест: cookie и localStorage между тестами не переносятся.

    Язык задаём русский: Django выбирает язык по Accept-Language, а Playwright по умолчанию
    шлёт en-US, и интерфейс стал бы английским.
    """
    context = chromium_browser.new_context(base_url=base_url, locale="ru-RU", viewport={"width": 1366, "height": 900})
    context.set_default_timeout(15_000)
    try:
        yield context.new_page()
    finally:
        context.close()
