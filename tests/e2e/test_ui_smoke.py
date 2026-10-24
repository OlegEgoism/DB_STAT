"""Браузерные smoke-тесты: вход, сохранённое подключение, вкладки данных, поиск и выход.

Нужны запущенное приложение (E2E_BASE_URL) и PostgreSQL из E2E_PG_*. Тесты сохраняют
подключение к этой базе и на время теста поиска создают в ней две таблицы с TOAST-данными.
Каждый тест работает в своём контексте браузера, подготовка идемпотентна, поэтому тесты
можно запускать по отдельности и в любом порядке.
"""

import os
import re

import psycopg2
import pytest
from playwright.sync_api import expect
from psycopg2 import sql

ADMIN_LOGIN = os.getenv("E2E_ADMIN_LOGIN", "admin")
ADMIN_PASSWORD = os.getenv("E2E_ADMIN_PASSWORD", "admin12345")

PG_HOST = os.getenv("E2E_PG_HOST", "127.0.0.1")
PG_PORT = int(os.getenv("E2E_PG_PORT", "5432"))
PG_USER = os.getenv("E2E_PG_USER", "postgres")
PG_PASSWORD = os.getenv("E2E_PG_PASSWORD", "")
PG_DATABASE = os.getenv("E2E_PG_DATABASE", "postgres")

CONNECTION_NAME = "E2E PostgreSQL"
# Две таблицы с именами, которые поиск различает: по «e2e_toast_probe» найдётся только первая.
TOAST_PROBE_TABLES = ("e2e_toast_probe", "e2e_toast_other")
# Загрузка запросов к PostgreSQL может занять заметное время, поэтому ждём дольше обычного.
SLOW_TIMEOUT_MS = 10_000

HOME_URL = re.compile(r"^https?://[^/]+/$")
LOGIN_URL = re.compile(r"/login/$")

# Вкладки с данными: пункт меню, тело таблицы, счётчик записей.
DATA_TABS = [("tables", "tableSizesTableBody", "tableSizesCount"), ("temp-tables", "tempTablesTableBody", "tempTablesCount"), ("toast-tables", "toastTablesTableBody", "toastTablesCount")]


def login(page):
    page.goto("/login/")
    page.locator("#identifierInput").fill(ADMIN_LOGIN)
    page.locator("#passwordInput").fill(ADMIN_PASSWORD)
    # Имя кнопки «Войти» в доступности содержит глиф иконки, поэтому находим её по форме.
    page.locator("form button[type='submit']").click()
    expect(page).to_have_url(HOME_URL)
    expect(page.locator("#logoutForm")).to_be_attached()
    wait_for_connection_list(page)


def wait_for_connection_list(page):
    # До ответа /connections/ селектор подключений показывает «Загрузка подключений...».
    expect(page.locator("#connectionSelectLabel")).not_to_have_text("Загрузка подключений...", timeout=SLOW_TIMEOUT_MS)


def create_saved_connection(page):
    """Сохраняет подключение к PostgreSQL тем же запросом, что отправляет форма «Новое подключение»."""
    payload = {"name": CONNECTION_NAME, "host": PG_HOST, "port": PG_PORT, "database": PG_DATABASE, "user": PG_USER, "password": PG_PASSWORD, "db_type": "PostgreSQL"}
    result = page.evaluate(
        """async (payload) => {
            const csrf = document.cookie.split('; ').find(item => item.startsWith('csrftoken='));
            const response = await fetch('/connections/', {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf ? csrf.split('=')[1] : ''},
                body: JSON.stringify(payload),
            });
            return {status: response.status, body: await response.json()};
        }""",
        payload,
    )
    # 201 — подключение создано; 200 — оно уже было и обновлено на месте.
    assert result["status"] in (200, 201), result
    assert result["body"]["ok"] is True, result


def select_connection(page):
    page.locator("#connectionSelectToggle").click()
    page.locator("#connectionSelectMenu").get_by_role("option", name=CONNECTION_NAME, exact=True).click()
    expect(page.locator("#connectionSelectLabel")).to_have_text(CONNECTION_NAME)


def open_home_with_connection(page):
    login(page)
    create_saved_connection(page)
    page.reload()
    wait_for_connection_list(page)
    select_connection(page)


def open_tab(page, tab_id):
    page.locator(f'#sidebar .nav-item[data-page="{tab_id}"]').click()
    expect(page.locator(f"#page-{tab_id}")).to_have_class(re.compile(r"\bactive\b"))


def is_toast_list_request(response):
    return response.request.method == "POST" and response.url.endswith("/toast-tables/sizes/")


@pytest.fixture
def toast_probe_tables():
    """Создаёт таблицы с крупными случайными значениями: PostgreSQL выносит их в TOAST.

    Значения случайные (md5), иначе сжатие уместит их в страницу основной таблицы и TOAST-таблица
    окажется пустой. Таблицы удаляются после теста.
    """
    connection = psycopg2.connect(host=PG_HOST, port=PG_PORT, user=PG_USER, password=PG_PASSWORD, dbname=PG_DATABASE, connect_timeout=5)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            for table in TOAST_PROBE_TABLES:
                cursor.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(table)))
                cursor.execute(sql.SQL("CREATE TABLE {} (id integer PRIMARY KEY, payload text)").format(sql.Identifier(table)))
                cursor.execute(sql.SQL("INSERT INTO {} (id, payload) VALUES (1, (SELECT string_agg(md5(random()::text), '') FROM generate_series(1, 4000)))").format(sql.Identifier(table)))
        yield TOAST_PROBE_TABLES
    finally:
        with connection.cursor() as cursor:
            for table in TOAST_PROBE_TABLES:
                cursor.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(table)))
        connection.close()


def test_login_page_rejects_wrong_password(page):
    page.goto("/login/")
    expect(page.get_by_role("heading", name="DB STAT")).to_be_visible()

    page.locator("#identifierInput").fill(ADMIN_LOGIN)
    page.locator("#passwordInput").fill("wrong-password-e2e")
    page.locator("form button[type='submit']").click()

    expect(page.locator(".alert-danger")).to_contain_text("Неверный логин, почта или пароль")
    expect(page).to_have_url(LOGIN_URL)


def test_admin_login_opens_home_without_js_errors(page):
    js_errors = []

    def remember_console_error(message):
        if message.type == "error":
            js_errors.append(message.text)

    page.on("console", remember_console_error)
    page.on("pageerror", lambda error: js_errors.append(str(error)))

    login(page)

    sidebar = page.locator("#sidebar")
    for tab_id in ("database-overview", "tables", "temp-tables", "toast-tables", "settings"):
        expect(sidebar.locator(f'.nav-item[data-page="{tab_id}"]')).to_be_attached()
    expect(sidebar.locator('.nav-item[data-page="settings"]')).to_be_visible()
    assert js_errors == []


def test_saved_connection_appears_in_selector_after_reload(page):
    login(page)
    create_saved_connection(page)
    page.reload()
    wait_for_connection_list(page)

    page.locator("#connectionSelectToggle").click()
    expect(page.locator("#connectionSelectMenu").get_by_role("option", name=CONNECTION_NAME, exact=True)).to_be_visible()


def test_data_tabs_finish_loading_without_undefined(page):
    open_home_with_connection(page)

    for tab_id, body_id, count_id in DATA_TABS:
        open_tab(page, tab_id)
        body = page.locator(f"#{body_id}")
        count = page.locator(f"#{count_id}")
        expect(body).not_to_contain_text("Загрузка", timeout=SLOW_TIMEOUT_MS)
        # Счётчик остаётся «Нет данных», пока запрос не отрисован: при ошибке он тоже не меняется.
        expect(count).not_to_have_text("Нет данных", timeout=SLOW_TIMEOUT_MS)
        expect(body).not_to_contain_text("undefined")


def test_toast_tab_search_filters_rows(page, toast_probe_tables):
    first, second = toast_probe_tables
    open_home_with_connection(page)
    open_tab(page, "toast-tables")
    body = page.locator("#toastTablesTableBody")
    expect(body).to_contain_text(first, timeout=SLOW_TIMEOUT_MS)
    expect(body).to_contain_text(second)

    search = page.locator("#toastTableSearchInput")
    with page.expect_response(is_toast_list_request) as response_info:
        search.fill(first)
    assert response_info.value.ok
    expect(body.locator("tr")).to_have_count(1, timeout=SLOW_TIMEOUT_MS)
    expect(body).to_contain_text(first)
    expect(body).not_to_contain_text(second)

    with page.expect_response(is_toast_list_request) as response_info:
        search.fill("e2e-no-such-table")
    assert response_info.value.ok
    expect(body).not_to_contain_text(first, timeout=SLOW_TIMEOUT_MS)


def test_logout_returns_to_login_and_protects_home(page):
    login(page)

    page.locator("#logoutForm button[type='submit']").click()
    expect(page).to_have_url(LOGIN_URL)
    expect(page.locator("#identifierInput")).to_be_visible()

    page.goto("/")
    expect(page).to_have_url(LOGIN_URL)
