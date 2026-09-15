"""Формирование общего диагностического PDF-отчёта по выбранной базе данных."""

import importlib.util
import io
import os
from datetime import datetime
from xml.sax.saxutils import escape

import psycopg2
from django.http import FileResponse, JsonResponse
from django.views.decorators.http import require_http_methods

from db_statistics.views.audit import _connection_audit_fields, _format_audit_details, _write_audit
from db_statistics.views.auth import _current_db_user, _require_payload_connection
from db_statistics.views.helpers import _format_bytes, _read_json_body
from db_statistics.views.pool import _fetch_db_rows, _safe_db_error_message

_MAX_ROWS = 50


def _register_fonts():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    windows_fonts = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")
    candidates = [("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"), (os.path.join(windows_fonts, "arial.ttf"), os.path.join(windows_fonts, "arialbd.ttf"))]
    regular, bold = next(((regular, bold) for regular, bold in candidates if os.path.exists(regular) and os.path.exists(bold)), (None, None))
    if not regular:
        raise RuntimeError("Не найден шрифт DejaVu Sans или Arial для формирования PDF")
    if "DBStatSans" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("DBStatSans", regular))
        pdfmetrics.registerFont(TTFont("DBStatSans-Bold", bold))
    return "DBStatSans", "DBStatSans-Bold"


def _text(value, limit=500):
    value = "—" if value in (None, "") else str(value)
    return escape(value[:limit] + ("…" if len(value) > limit else ""))


def _collect(db_connection, title, query, params=None):
    try:
        return _fetch_db_rows(db_connection, query, params), None
    except psycopg2.Error as exc:
        return [], _safe_db_error_message(f"Не удалось собрать раздел «{title}»", exc)


def _report_sections(db_connection):
    user_schemas = "namespace.nspname NOT IN ('pg_catalog', 'information_schema') AND namespace.nspname NOT LIKE 'pg_toast%%'"
    definitions = [
        (
            "Общая информация",
            """SELECT version(), current_database(), pg_database_size(current_database()), current_setting('server_encoding'), current_setting('TimeZone'), pg_postmaster_start_time(), now() - pg_postmaster_start_time(), (SELECT count(*) FROM pg_stat_activity), current_setting('max_connections')""",
            None,
            ["Версия", "База данных", "Размер", "Кодировка", "Часовой пояс", "Запуск", "Время работы", "Подключения", "Максимум подключений"],
        ),
        (
            "Размеры схем",
            f"""SELECT namespace.nspname, pg_get_userbyid(namespace.nspowner), count(rel.oid), COALESCE(sum(pg_total_relation_size(rel.oid)), 0), pg_size_pretty(COALESCE(sum(pg_total_relation_size(rel.oid)), 0)) FROM pg_namespace namespace LEFT JOIN pg_class rel ON rel.relnamespace=namespace.oid AND rel.relkind IN ('r','p','m') WHERE {user_schemas} GROUP BY namespace.nspname, namespace.nspowner ORDER BY 4 DESC LIMIT {_MAX_ROWS}""",
            None,
            ["Схема", "Владелец", "Таблиц", "Байт", "Размер"],
        ),
        (
            "Крупнейшие таблицы",
            f"""SELECT namespace.nspname, rel.relname, pg_get_userbyid(rel.relowner), pg_total_relation_size(rel.oid), pg_size_pretty(pg_total_relation_size(rel.oid)), pg_indexes_size(rel.oid), pg_size_pretty(pg_indexes_size(rel.oid)), GREATEST(rel.reltuples::bigint,0) FROM pg_class rel JOIN pg_namespace namespace ON namespace.oid=rel.relnamespace WHERE rel.relkind IN ('r','p') AND {user_schemas} ORDER BY 4 DESC LIMIT {_MAX_ROWS}""",
            None,
            ["Схема", "Таблица", "Владелец", "Байт", "Размер", "Индексы, байт", "Индексы", "Строк"],
        ),
        (
            "Временные таблицы",
            f"""SELECT namespace.nspname, rel.relname, pg_get_userbyid(rel.relowner), pg_total_relation_size(rel.oid), pg_size_pretty(pg_total_relation_size(rel.oid)) FROM pg_class rel JOIN pg_namespace namespace ON namespace.oid=rel.relnamespace WHERE rel.relkind IN ('r','p') AND (rel.relpersistence='t' OR namespace.nspname LIKE 'pg_temp_%%') ORDER BY 4 DESC LIMIT {_MAX_ROWS}""",
            None,
            ["Схема", "Таблица", "Владелец", "Байт", "Размер"],
        ),
        ("Активные запросы", f"""SELECT pid, usename, state, now()-query_start, query FROM pg_stat_activity WHERE state='active' AND pid<>pg_backend_pid() ORDER BY query_start LIMIT {_MAX_ROWS}""", None, ["PID", "Пользователь", "Состояние", "Длительность", "SQL"]),
        (
            "Активные сессии",
            f"""SELECT pid, usename, datname, application_name, COALESCE(client_addr::text,'local'), state, now()-backend_start FROM pg_stat_activity ORDER BY backend_start LIMIT {_MAX_ROWS}""",
            None,
            ["PID", "Пользователь", "База", "Приложение", "Клиент", "Состояние", "Длительность"],
        ),
        (
            "Блокировки",
            f"""SELECT blocked.pid, blocked.usename, blocker.pid, blocker.usename, now()-blocked.query_start, blocked.query FROM pg_stat_activity blocked CROSS JOIN LATERAL unnest(pg_blocking_pids(blocked.pid)) blocker_pid JOIN pg_stat_activity blocker ON blocker.pid=blocker_pid ORDER BY blocked.query_start LIMIT {_MAX_ROWS}""",
            None,
            ["Заблокирован PID", "Пользователь", "Блокирует PID", "Пользователь", "Длительность", "SQL"],
        ),
        (
            "Незавершённые транзакции",
            f"""SELECT pid, usename, application_name, COALESCE(client_addr::text,'local'), state, now()-xact_start, query FROM pg_stat_activity WHERE xact_start IS NOT NULL AND pid<>pg_backend_pid() ORDER BY xact_start LIMIT {_MAX_ROWS}""",
            None,
            ["PID", "Пользователь", "Приложение", "Клиент", "Состояние", "Возраст", "SQL"],
        ),
        (
            "Память",
            """SELECT name, setting, unit, short_desc FROM pg_settings WHERE name IN ('shared_buffers','work_mem','maintenance_work_mem','effective_cache_size','temp_buffers','statement_mem','max_statement_mem','gp_vmem_protect_limit') ORDER BY name""",
            None,
            ["Параметр", "Значение", "Единица", "Описание"],
        ),
        (
            "Обслуживание",
            f"""SELECT schemaname, relname, n_live_tup, n_dead_tup, last_vacuum, last_autovacuum, last_analyze, last_autoanalyze FROM pg_stat_user_tables ORDER BY n_dead_tup DESC LIMIT {_MAX_ROWS}""",
            None,
            ["Схема", "Таблица", "Живые", "Мёртвые", "VACUUM", "Autovacuum", "ANALYZE", "Autoanalyze"],
        ),
        ("Пользователи", f"""SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, rolconnlimit FROM pg_roles WHERE rolcanlogin ORDER BY rolname LIMIT {_MAX_ROWS}""", None, ["Пользователь", "Вход", "Superuser", "Создание БД", "Создание ролей", "Лимит"]),
        (
            "Группы",
            f"""SELECT role.rolname, count(member.oid), COALESCE(string_agg(member.rolname, ', ' ORDER BY member.rolname),'—') FROM pg_roles role LEFT JOIN pg_auth_members membership ON membership.roleid=role.oid LEFT JOIN pg_roles member ON member.oid=membership.member WHERE NOT role.rolcanlogin GROUP BY role.rolname ORDER BY role.rolname LIMIT {_MAX_ROWS}""",
            None,
            ["Группа", "Участников", "Участники"],
        ),
    ]
    if db_connection.is_greenplum_compatible:
        definitions.append(("Сегменты Greenplum/Greengage", "SELECT content, dbid, role, preferred_role, mode, status, hostname, port FROM gp_segment_configuration ORDER BY content, role", None, ["Content", "DBID", "Роль", "Предпочтительная", "Режим", "Статус", "Хост", "Порт"]))
    else:
        definitions.append(("Сегменты Greenplum/Greengage", None, None, ["Состояние"]))

    sections = []
    for title, query, params, headers in definitions:
        if query is None:
            sections.append({"title": title, "headers": headers, "rows": [["Не применимо для PostgreSQL"]], "warning": None})
            continue
        rows, warning = _collect(db_connection, title, query, params)
        if title == "Общая информация" and rows:
            row = list(rows[0])
            row[2] = _format_bytes(int(row[2] or 0))
            rows = [[headers[index], value] for index, value in enumerate(row)]
            headers = ["Показатель", "Значение"]
        sections.append({"title": title, "headers": headers, "rows": rows, "warning": warning})
    return sections


def _recommendations(sections):
    by_title = {section["title"]: section for section in sections}
    result = []
    locks = by_title["Блокировки"]["rows"]
    temps = by_title["Временные таблицы"]["rows"]
    maintenance = by_title["Обслуживание"]["rows"]
    if locks:
        result.append(("Критично", f"Обнаружены блокировки: {len(locks)}. Проверьте блокирующие сессии и длительность их транзакций."))
    if sum(int(row[3] or 0) for row in temps) > 1024**3:
        result.append(("Внимание", "Объём временных таблиц превышает 1 ГБ. Проверьте длительные запросы и настройки памяти."))
    bloated = [row for row in maintenance if int(row[3] or 0) > max(int(row[2] or 0) * 0.2, 100000)]
    if bloated:
        result.append(("Внимание", f"Для {len(bloated)} таблиц обнаружено значительное количество мёртвых строк. Проверьте autovacuum."))
    if not result:
        result.append(("Норма", "По доступным показателям критические отклонения не обнаружены."))
    warnings = [section["title"] for section in sections if section["warning"]]
    if warnings:
        result.append(("Информация", "Часть разделов недоступна: " + ", ".join(warnings) + "."))
    return result


def _build_pdf(db_connection, db_user, sections):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

    regular, bold = _register_fonts()
    styles = getSampleStyleSheet()
    normal = ParagraphStyle("ReportNormal", parent=styles["BodyText"], fontName=regular, fontSize=7, leading=9)
    heading = ParagraphStyle("ReportHeading", parent=styles["Heading1"], fontName=bold, fontSize=15, leading=18, textColor=colors.HexColor("#1d4ed8"), spaceAfter=8)
    title = ParagraphStyle("ReportTitle", parent=heading, fontSize=23, leading=28, alignment=TA_CENTER, spaceAfter=14)
    buffer = io.BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm, topMargin=14 * mm, bottomMargin=14 * mm, title=f"Отчёт по базе {db_connection.database}")
    story = [Spacer(1, 25 * mm), Paragraph("DB STAT", title), Paragraph("Общий диагностический отчёт по базе данных", title), Spacer(1, 8 * mm)]
    cover = [
        ["Подключение", db_connection.name],
        ["СУБД", db_connection.db_type],
        ["База данных", db_connection.database],
        ["Сервер", f"{db_connection.host}:{db_connection.port}"],
        ["Пользователь отчёта", db_user.login],
        ["Сформирован", datetime.now().astimezone().strftime("%d.%m.%Y %H:%M:%S %Z")],
    ]
    story.extend([_pdf_table(cover, normal, bold, header=False), PageBreak()])
    for section in sections:
        story.append(Paragraph(_text(section["title"]), heading))
        if section["warning"]:
            story.append(Paragraph(_text(section["warning"]), normal))
        elif not section["rows"]:
            story.append(Paragraph("На момент формирования отчёта данные отсутствуют.", normal))
        else:
            story.append(_pdf_table([section["headers"], *section["rows"]], normal, bold))
        story.extend([Spacer(1, 5 * mm)])
    story.extend([PageBreak(), Paragraph("Рекомендации", heading), _pdf_table([["Уровень", "Рекомендация"], *_recommendations(sections)], normal, bold)])

    def page(canvas, doc):
        canvas.saveState()
        canvas.setFont(regular, 7)
        canvas.setFillColor(colors.grey)
        canvas.drawString(12 * mm, 7 * mm, f"DB STAT · {db_connection.name} · {db_connection.database}")
        canvas.drawRightString(landscape(A4)[0] - 12 * mm, 7 * mm, f"Страница {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=page, onLaterPages=page)
    buffer.seek(0)
    return buffer


def _pdf_table(rows, normal, bold, header=True):
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Table, TableStyle

    data = [[Paragraph(_text(cell), ParagraphStyle("cell", parent=normal, fontName=bold if header and row_index == 0 else normal.fontName)) for cell in row] for row_index, row in enumerate(rows)]
    table = Table(data, repeatRows=1 if header else 0, hAlign="LEFT", spaceAfter=3 * mm)
    commands = [("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
    if header:
        commands.extend([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f0ff")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1e3a8a"))])
    table.setStyle(TableStyle(commands))
    return table


@require_http_methods(["POST"])
def database_pdf_report(request):
    """Собирает все диагностические разделы и возвращает готовый PDF."""
    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    db_user = _current_db_user(request)
    if not db_user:
        return JsonResponse({"ok": False, "message": "Требуется вход в приложение"}, status=401)
    if importlib.util.find_spec("reportlab") is None:
        return JsonResponse({"ok": False, "message": "Модуль ReportLab не установлен. Выполните pip install -r requirements.txt и перезапустите приложение"}, status=503)
    sections = _report_sections(db_connection)
    pdf = _build_pdf(db_connection, db_user, sections)
    _write_audit("database_report", _format_audit_details([("Действие", "Формирование PDF-отчёта"), *_connection_audit_fields(db_connection, server_label=True), ("Разделов", len(sections) + 1), ("Результат", "отчёт сформирован")]), db_user=db_user)
    filename = f"db-report-{db_connection.pk}-{datetime.now():%Y%m%d-%H%M%S}.pdf"
    return FileResponse(pdf, as_attachment=True, filename=filename, content_type="application/pdf")
