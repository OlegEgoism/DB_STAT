"""Формирование общего диагностического PDF-отчёта по выбранной базе данных."""

import importlib.util
import io
import logging
import os
import time
from datetime import datetime
from threading import Lock
from xml.sax.saxutils import escape

import psycopg2
from django.conf import settings
from django.db import DatabaseError, close_old_connections, connection
from django.http import FileResponse, JsonResponse
from django.utils import timezone, translation
from django.utils.translation import gettext as _, pgettext
from django.views.decorators.http import require_http_methods

from db_statistics.job_locks import with_job_lock
from db_statistics.models import ReportJob
from db_statistics.queries import report_sql
from db_statistics.views.audit import _connection_audit_fields, _format_audit_details, _write_audit
from db_statistics.views.auth import _current_db_user, _require_payload_connection
from db_statistics.views.helpers import _format_bytes, _read_json_body
from db_statistics.views.pool import _fetch_db_rows, _safe_db_error_message

logger = logging.getLogger(__name__)
_report_job_schema_lock = Lock()


def _ensure_report_job_table():
    """Создаёт таблицу отчётов, если её нет, и добавляет колонку language, если её нет.

    Миграция 0001 создаёт db_report_job со всеми колонками. Но установка, созданная до появления
    колонки language, при обновлении отмечается применённой без изменения таблицы: команда migrate
    проверяет только наличие таблиц (см. db_statistics/management/commands/migrate.py). Недостающую
    колонку добавляет эта функция при старте и при обращении к отчётам.
    """
    table_name = ReportJob._meta.db_table
    with _report_job_schema_lock:
        try:
            tables = connection.introspection.table_names()
            if table_name not in tables:
                with connection.schema_editor() as schema_editor:
                    schema_editor.create_model(ReportJob)
                return
            with connection.cursor() as cursor:
                columns = {column.name for column in connection.introspection.get_table_description(cursor, table_name)}
            if "language" not in columns:
                with connection.schema_editor() as schema_editor:
                    schema_editor.add_field(ReportJob, ReportJob._meta.get_field("language"))
        except DatabaseError:
            # Другой процесс приложения мог создать таблицу между проверкой и
            # DDL. Подавляем только этот безопасный race, остальные ошибки
            # должны остаться видимыми в журнале.
            if table_name not in connection.introspection.table_names():
                raise
            with connection.cursor() as cursor:
                columns = {column.name for column in connection.introspection.get_table_description(cursor, table_name)}
            if "language" not in columns:
                raise


def _serialize_report_job(job):
    return {
        "id": str(job.pk),
        "kind": "report",
        "operation": "database_report",
        "connection_id": job.connection_id,
        "connection_name": job.connection.name,
        "database": job.connection.database,
        "username": job.user.login if job.user else "—",
        "status": job.status,
        "message": job.message,
        "filename": job.filename,
        "language": job.language,
        "download_url": f"/reports/database.pdf?job_id={job.pk}&download=1" if job.status == "completed" else None,
        "duration_seconds": job.duration_seconds,
        "created": job.created.isoformat(),
        "started": job.started.isoformat() if job.started else None,
        "finished": job.finished.isoformat() if job.finished else None,
    }


def _submit_report_job(job_id):
    settings.REPORT_JOB_EXECUTOR.submit(_run_report_job, str(job_id))


@with_job_lock
def _run_report_job(job_id):
    close_old_connections()
    claimed = ReportJob.objects.filter(pk=job_id, status="queued").update(status="running", message="PDF-отчёт формируется", started=timezone.now())
    if not claimed:
        close_old_connections()
        return
    job = ReportJob.objects.select_related("connection", "user").get(pk=job_id)
    started_at = time.monotonic()
    try:
        # Язык отчёта задан при постановке задачи; весь текст PDF и итоговое сообщение формируются на нём.
        with translation.override(job.language):
            sections = _report_sections(job.connection)
            pdf = _build_pdf(job.connection, job.user, sections)
            message = _completion_message(sections)
        filename = f"db-report-{job.connection_id}-{datetime.now():%Y%m%d-%H%M%S}.pdf"
        ReportJob.objects.filter(pk=job_id).update(status="completed", message=message, content=pdf.getvalue(), filename=filename, duration_seconds=round(time.monotonic() - started_at, 3), finished=timezone.now())
        _write_audit(
            "database_report", _format_audit_details([("Действие", "Формирование PDF-отчёта"), *_connection_audit_fields(job.connection, server_label=True), ("Разделов", len(sections) + 1), ("Результат", "отчёт сформирован")]), username=job.user.login if job.user else "system"
        )
    except Exception:
        logger.exception("Не удалось сформировать PDF-отчёт job_id=%s", job_id)
        ReportJob.objects.filter(pk=job_id).update(status="failed", message="Не удалось сформировать PDF-отчёт. Подробности см. в журнале сервера", duration_seconds=round(time.monotonic() - started_at, 3), finished=timezone.now())
    finally:
        close_old_connections()


def _completion_message(sections):
    """Итоговое сообщение задачи. Статус остаётся «completed», но неполный отчёт назван прямо.

    Раздел считается не собранным, если для него заполнено предупреждение
    (см. _collect). Без таких разделов сообщение прежнее.
    Вызывается внутри translation.override(язык задачи).
    """
    failed_titles = [section["title"] for section in sections if section["warning"]]
    if not failed_titles:
        return _("PDF-отчёт готов к скачиванию")
    titles = ", ".join(failed_titles)
    return _("Готов, но неполный: не собраны разделы: {titles}").format(titles=titles)


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
        return _fetch_db_rows(db_connection, query, params, background=True), None
    except psycopg2.Error as exc:
        message = _("Не удалось собрать раздел «{title}»").format(title=title)
        if translation.get_language() == "en":
            logger.warning("Could not collect PDF section %s: %s", title, exc)
            return [], message
        return [], _safe_db_error_message(message, exc)


def _report_sections(db_connection):
    definitions = [
        (_("Общая информация"), report_sql.REPORT_GENERAL_INFO_SQL, None, [_("Версия"), _("База данных"), _("Размер"), _("Кодировка"), _("Часовой пояс"), _("Запуск"), _("Время работы"), _("Подключения"), _("Максимум подключений")]),
        (_("Размеры схем"), report_sql.REPORT_SCHEMA_SIZES_SQL, None, [_("Схема"), _("Владелец"), _("Таблиц"), _("Байт"), _("Размер")]),
        (
            _("Сводка производительности"),
            report_sql.REPORT_PERFORMANCE_SUMMARY_SQL,
            None,
            [
                _("Подключения"),
                _("Транзакции COMMIT"),
                _("Транзакции ROLLBACK"),
                _("Попадания в кэш"),
                _("Чтения с диска"),
                _("Cache hit, %"),
                _("Возвращено строк"),
                _("Получено строк"),
                _("Вставлено строк"),
                _("Обновлено строк"),
                _("Удалено строк"),
                _("Временных файлов"),
                _("Временные данные"),
                _("Deadlock"),
                _("Время чтения, мс"),
                _("Время записи, мс"),
                _("Статистика с"),
            ],
        ),
        (_("Крупнейшие таблицы"), report_sql.REPORT_LARGEST_TABLES_SQL, None, [_("Схема"), _("Таблица"), _("Владелец"), _("Байт"), _("Размер"), _("Индексы, байт"), _("Индексы"), _("Строк")]),
        (_("Временные таблицы"), report_sql.REPORT_TEMP_TABLES_SQL, None, [_("Схема"), _("Таблица"), _("Владелец"), _("Байт"), _("Размер")]),
        (_("Активные запросы"), report_sql.REPORT_ACTIVE_QUERIES_SQL, None, ["PID", _("Пользователь"), _("Состояние"), _("Длительность"), "SQL"]),
        (_("Активные сессии"), report_sql.REPORT_ACTIVE_SESSIONS_SQL, None, ["PID", _("Пользователь"), _("База"), _("Приложение"), _("Клиент"), _("Состояние"), _("Длительность")]),
        (_("Блокировки"), report_sql.REPORT_LOCKS_SQL, None, [_("Заблокирован PID"), _("Пользователь"), _("Блокирует PID"), _("Пользователь"), _("Длительность"), "SQL"]),
        (_("Незавершённые транзакции"), report_sql.REPORT_IDLE_TRANSACTIONS_SQL, None, ["PID", _("Пользователь"), _("Приложение"), _("Клиент"), _("Состояние"), _("Возраст"), "SQL"]),
        (_("Ожидания сессий"), report_sql.REPORT_WAIT_EVENTS_SQL, None, [_("Тип ожидания"), _("Событие"), _("Сессий")]),
        (_("Эффективность доступа к таблицам"), report_sql.REPORT_TABLE_ACCESS_SQL, None, [_("Схема"), _("Таблица"), _("Seq scan"), _("Index scan"), _("Индексы, %"), _("Живые"), _("Мёртвые"), _("Мёртвые, %"), "Autovacuum", "Autoanalyze"]),
        (_("Память"), report_sql.REPORT_MEMORY_SQL, None, [_("Параметр"), _("Значение"), _("Единица")]),
        (_("Обслуживание"), report_sql.REPORT_MAINTENANCE_SQL, None, [_("Схема"), _("Таблица"), _("Живые"), _("Мёртвые"), "VACUUM", "Autovacuum", "ANALYZE", "Autoanalyze"]),
        (_("Пользователи"), report_sql.REPORT_USERS_SQL, None, [_("Пользователь"), _("Вход"), "Superuser", _("Создание БД"), _("Создание ролей"), _("Лимит")]),
        (_("Группы"), report_sql.REPORT_GROUPS_SQL, None, [_("Группа"), _("Участников"), _("Участники")]),
    ]
    extension_rows, _extension_warning = _collect(db_connection, "pg_stat_statements", report_sql.REPORT_PG_STAT_STATEMENTS_CHECK_SQL)
    if extension_rows:
        definitions.append((_("Ресурсоёмкие запросы"), report_sql.REPORT_EXPENSIVE_QUERIES_SQL, None, [_("Вызовов"), _("Общее время, мс"), _("Среднее время, мс"), _("Строк"), "SQL"]))
    if db_connection.is_greenplum_compatible:
        definitions.append((_("Сегменты Greenplum/Greengage"), report_sql.REPORT_GP_SEGMENTS_SQL, None, ["Content", "DBID", _("Роль"), _("Предпочтительная"), _("Режим"), _("Статус"), _("Хост"), _("Порт")]))
    else:
        definitions.append((_("Сегменты Greenplum/Greengage"), None, None, [pgettext("Greenplum fallback column", "Состояние")]))

    sections = []
    for title, query, params, headers in definitions:
        if query is None:
            sections.append({"title": title, "headers": headers, "rows": [[_("Не применимо для PostgreSQL")]], "warning": None})
            continue
        rows, warning = _collect(db_connection, title, query, params)
        if title == _("Общая информация") and rows:
            row = list(rows[0])
            row[2] = _format_bytes(int(row[2] or 0))
            rows = [[headers[index], value] for index, value in enumerate(row)]
            headers = [_("Показатель"), _("Значение")]
        elif title == _("Сводка производительности") and rows:
            row = list(rows[0])
            row[12] = _format_bytes(int(row[12] or 0))
            rows = [[headers[index], value] for index, value in enumerate(row)]
            headers = [_("Показатель"), _("Значение")]
        sections.append({"title": title, "headers": headers, "rows": rows, "warning": warning})
    return sections


def _performance_conclusion(sections):
    by_title = {section["title"]: section for section in sections}
    result = []
    severity = 0

    def add(level, message, weight=1):
        nonlocal severity
        severity = max(severity, weight)
        result.append((level, message))

    summary = dict(by_title.get(_("Сводка производительности"), {}).get("rows", []))
    general = dict(by_title.get(_("Общая информация"), {}).get("rows", []))
    locks = by_title.get(_("Блокировки"), {}).get("rows", [])
    transactions = by_title.get(_("Незавершённые транзакции"), {}).get("rows", [])
    access = by_title.get(_("Эффективность доступа к таблицам"), {}).get("rows", [])

    def as_number(value):
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0

    def number(mapping, key):
        return as_number(mapping.get(key))

    if locks:
        add(_("Критично"), _("Обнаружено блокировок: {count}. Проверьте блокирующие сессии.").format(count=len(locks)), 2)

    cache_hit = number(summary, _("Cache hit, %"))
    if cache_hit and cache_hit < 90:
        add(_("Критично"), _("Cache hit равен {cache_hit:.1f}%. Высокая доля чтения с диска может ограничивать производительность.").format(cache_hit=cache_hit), 2)
    elif cache_hit and cache_hit < 95:
        add(_("Внимание"), _("Cache hit равен {cache_hit:.1f}%. Проверьте самые читаемые запросы и размер кэша.").format(cache_hit=cache_hit))

    commits = number(summary, _("Транзакции COMMIT"))
    rollbacks = number(summary, _("Транзакции ROLLBACK"))
    rollback_ratio = 100 * rollbacks / (commits + rollbacks) if commits + rollbacks else 0
    if rollback_ratio >= 10:
        add(_("Критично"), _("Доля откатов составляет {rollback_ratio:.1f}%. Проверьте ошибки приложения и конфликты транзакций.").format(rollback_ratio=rollback_ratio), 2)
    elif rollback_ratio >= 5:
        add(_("Внимание"), _("Доля откатов составляет {rollback_ratio:.1f}%.").format(rollback_ratio=rollback_ratio))

    connections = number(summary, _("Подключения"))
    max_connections = number(general, _("Максимум подключений"))
    connection_ratio = 100 * connections / max_connections if max_connections else 0
    if connection_ratio >= 90:
        add(_("Критично"), _("Использовано {connection_ratio:.1f}% доступных подключений.").format(connection_ratio=connection_ratio), 2)
    elif connection_ratio >= 75:
        add(_("Внимание"), _("Использовано {connection_ratio:.1f}% доступных подключений.").format(connection_ratio=connection_ratio))

    deadlocks = int(number(summary, _("Deadlock")))
    if deadlocks:
        add(_("Внимание"), _("С момента сброса статистики зарегистрировано deadlock: {count}.").format(count=deadlocks))

    bloated = [row for row in access if len(row) > 7 and as_number(row[7]) >= 20 and as_number(row[6]) >= 100000]
    if bloated:
        add(_("Внимание"), _("У {count} крупных таблиц не менее 20% мёртвых строк. Проверьте autovacuum.").format(count=len(bloated)))

    sequential = [row for row in access if len(row) > 5 and as_number(row[5]) >= 100000 and as_number(row[4]) < 80 and as_number(row[2]) > 100]
    if sequential:
        add(_("Внимание"), _("Для {count} крупных таблиц доля index scan ниже 80%. Проверьте планы запросов и индексы.").format(count=len(sequential)))

    long_transactions = [row for row in transactions if len(row) > 5 and hasattr(row[5], "total_seconds") and row[5].total_seconds() >= 900]
    if long_transactions:
        add(_("Внимание"), _("Транзакций старше 15 минут: {count}. Они могут удерживать блокировки и мешать очистке.").format(count=len(long_transactions)))

    if not result:
        result.append((_("Норма"), _("По доступному снимку критические отклонения производительности не обнаружены.")))

    status = _("Требует внимания") if severity == 2 else _("Есть замечания") if severity == 1 else _("Стабильно")
    result.insert(0, (_("Итог"), _("Оценка: {status}. Заключение основано на текущем снимке и накопительной статистике PostgreSQL.").format(status=status)))
    warnings = [section["title"] for section in sections if section["warning"]]
    if warnings:
        result.append((_("Информация"), _("Часть разделов недоступна: ") + ", ".join(warnings) + "."))
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
    title = ParagraphStyle("ReportTitle", parent=heading, fontSize=20, leading=23, alignment=TA_CENTER, spaceAfter=8)
    buffer = io.BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm, topMargin=14 * mm, bottomMargin=14 * mm, title=_("Отчёт по базе {database}").format(database=db_connection.database))
    story = [Paragraph("DB STAT", title), Paragraph(_("Диагностика базы данных"), title), Spacer(1, 3 * mm)]
    cover = [
        [_("Подключение"), db_connection.name],
        [_("СУБД"), db_connection.db_type],
        [_("База данных"), db_connection.database],
        [_("Сервер"), f"{db_connection.host}:{db_connection.port}"],
        [_("Пользователь отчёта"), db_user.login],
        [_("Сформирован"), datetime.now().astimezone().strftime("%d.%m.%Y %H:%M:%S %Z")],
    ]
    conclusion = _performance_conclusion(sections)
    story.extend([_pdf_table(cover, normal, bold, header=False), Spacer(1, 4 * mm), Paragraph(_("Заключение о производительности"), heading), _pdf_table([[_("Уровень"), _("Вывод")], *conclusion], normal, bold), PageBreak()])
    for section in sections:
        story.append(Paragraph(_text(section["title"]), heading))
        if section["warning"]:
            story.append(Paragraph(_text(section["warning"]), normal))
        elif not section["rows"]:
            story.append(Paragraph(_("На момент формирования отчёта данные отсутствуют."), normal))
        else:
            story.append(_pdf_table([section["headers"], *section["rows"]], normal, bold))
        story.extend([Spacer(1, 5 * mm)])

    def page(canvas, doc):
        canvas.saveState()
        canvas.setFont(regular, 7)
        canvas.setFillColor(colors.grey)
        canvas.drawString(12 * mm, 7 * mm, f"DB STAT · {db_connection.name} · {db_connection.database}")
        canvas.drawRightString(landscape(A4)[0] - 12 * mm, 7 * mm, _("Страница {page}").format(page=doc.page))
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


@require_http_methods(["GET", "POST"])
def database_pdf_report(request):
    """Ставит PDF в очередь, возвращает состояние или скачивает результат."""
    db_user = _current_db_user(request)
    if not db_user:
        return JsonResponse({"ok": False, "message": "Требуется вход в приложение"}, status=401)
    _ensure_report_job_table()
    if request.method == "GET":
        if not request.GET.get("job_id"):
            jobs = ReportJob.objects.select_related("connection", "user").defer("content").filter(user=db_user).order_by("-created")
            return JsonResponse({"ok": True, "reports": [_serialize_report_job(job) for job in jobs]})
        try:
            job = ReportJob.objects.select_related("connection", "user").filter(pk=request.GET.get("job_id"), user=db_user).first()
        except (TypeError, ValueError):
            job = None
        if not job:
            return JsonResponse({"ok": False, "message": "Задача формирования отчёта не найдена"}, status=404)
        if request.GET.get("download") == "1":
            if job.status != "completed" or not job.content:
                return JsonResponse({"ok": False, "message": "PDF-отчёт ещё не готов"}, status=409)
            return FileResponse(io.BytesIO(bytes(job.content)), as_attachment=True, filename=job.filename, content_type="application/pdf")
        return JsonResponse({"ok": True, "job": _serialize_report_job(job)})

    payload = _read_json_body(request)
    db_connection, error_response = _require_payload_connection(request, payload)
    if error_response:
        return error_response
    if importlib.util.find_spec("reportlab") is None:
        return JsonResponse({"ok": False, "message": "Модуль ReportLab не установлен. Выполните pip install -r requirements.txt и перезапустите приложение"}, status=503)
    language = "en" if translation.get_language() == "en" else "ru"
    existing = ReportJob.objects.select_related("connection", "user").defer("content").filter(user=db_user, connection=db_connection, language=language, status__in=("queued", "running")).first()
    if existing:
        return JsonResponse({"ok": True, "job": _serialize_report_job(existing)}, status=202)
    job = ReportJob.objects.create(user=db_user, connection=db_connection, language=language)
    _submit_report_job(job.pk)
    return JsonResponse({"ok": True, "job": _serialize_report_job(job)}, status=202)
