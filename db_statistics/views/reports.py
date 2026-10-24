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
    """Создаёт таблицу отчётов в старых установках без Django-миграций.

    Исторически миграции этого приложения не поставлялись и его таблицы
    создавались через syncdb. Поэтому обычное добавление migration приводит к
    конфликту истории на существующих БД. Проверка позволяет безопасно
    обновиться без ручного удаления или пересоздания SQLite-файла.
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
        sections = _report_sections(job.connection, job.language)
        pdf = _build_pdf(job.connection, job.user, sections, job.language)
        filename = f"db-report-{job.connection_id}-{datetime.now():%Y%m%d-%H%M%S}.pdf"
        ReportJob.objects.filter(pk=job_id).update(status="completed", message=_completion_message(sections, job.language), content=pdf.getvalue(), filename=filename, duration_seconds=round(time.monotonic() - started_at, 3), finished=timezone.now())
        _write_audit(
            "database_report", _format_audit_details([("Действие", "Формирование PDF-отчёта"), *_connection_audit_fields(job.connection, server_label=True), ("Разделов", len(sections) + 1), ("Результат", "отчёт сформирован")]), username=job.user.login if job.user else "system"
        )
    except Exception:
        logger.exception("Не удалось сформировать PDF-отчёт job_id=%s", job_id)
        ReportJob.objects.filter(pk=job_id).update(status="failed", message="Не удалось сформировать PDF-отчёт. Подробности см. в журнале сервера", duration_seconds=round(time.monotonic() - started_at, 3), finished=timezone.now())
    finally:
        close_old_connections()


def _completion_message(sections, language="ru"):
    """Итоговое сообщение задачи. Статус остаётся «completed», но неполный отчёт назван прямо.

    Раздел считается не собранным, если для него заполнено предупреждение
    (см. _collect). Без таких разделов сообщение прежнее.
    """
    failed_titles = [section["title"] for section in sections if section["warning"]]
    if not failed_titles:
        return "PDF-отчёт готов к скачиванию"
    titles = ", ".join(failed_titles)
    return _label(language, f"Готов, но неполный: не собраны разделы: {titles}", f"Ready, but incomplete: sections not collected: {titles}")


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


def _label(language, russian, english):
    return english if language == "en" else russian


def _collect(db_connection, title, query, params=None, language="ru"):
    try:
        return _fetch_db_rows(db_connection, query, params, background=True), None
    except psycopg2.Error as exc:
        if language == "en":
            logger.warning("Could not collect PDF section %s: %s", title, exc)
            return [], f"Could not collect the “{title}” section."
        return [], _safe_db_error_message(f"Не удалось собрать раздел «{title}»", exc)


def _report_sections(db_connection, language="ru"):
    def t(ru, en):
        return _label(language, ru, en)

    definitions = [
        (
            t("Общая информация", "General information"),
            report_sql.REPORT_GENERAL_INFO_SQL,
            None,
            [
                t("Версия", "Version"),
                t("База данных", "Database"),
                t("Размер", "Size"),
                t("Кодировка", "Encoding"),
                t("Часовой пояс", "Time zone"),
                t("Запуск", "Started"),
                t("Время работы", "Uptime"),
                t("Подключения", "Connections"),
                t("Максимум подключений", "Maximum connections"),
            ],
        ),
        (t("Размеры схем", "Schema sizes"), report_sql.REPORT_SCHEMA_SIZES_SQL, None, [t("Схема", "Schema"), t("Владелец", "Owner"), t("Таблиц", "Tables"), t("Байт", "Bytes"), t("Размер", "Size")]),
        (
            t("Сводка производительности", "Performance summary"),
            report_sql.REPORT_PERFORMANCE_SUMMARY_SQL,
            None,
            [
                t("Подключения", "Connections"),
                t("Транзакции COMMIT", "Committed transactions"),
                t("Транзакции ROLLBACK", "Rolled back transactions"),
                t("Попадания в кэш", "Buffer cache hits"),
                t("Чтения с диска", "Disk block reads"),
                t("Cache hit, %", "Cache hit, %"),
                t("Возвращено строк", "Rows returned"),
                t("Получено строк", "Rows fetched"),
                t("Вставлено строк", "Rows inserted"),
                t("Обновлено строк", "Rows updated"),
                t("Удалено строк", "Rows deleted"),
                t("Временных файлов", "Temporary files"),
                t("Временные данные", "Temporary data"),
                t("Deadlock", "Deadlocks"),
                t("Время чтения, мс", "Read time, ms"),
                t("Время записи, мс", "Write time, ms"),
                t("Статистика с", "Statistics since"),
            ],
        ),
        (
            t("Крупнейшие таблицы", "Largest tables"),
            report_sql.REPORT_LARGEST_TABLES_SQL,
            None,
            [t("Схема", "Schema"), t("Таблица", "Table"), t("Владелец", "Owner"), t("Байт", "Bytes"), t("Размер", "Size"), t("Индексы, байт", "Indexes, bytes"), t("Индексы", "Indexes"), t("Строк", "Rows")],
        ),
        (t("Временные таблицы", "Temporary tables"), report_sql.REPORT_TEMP_TABLES_SQL, None, [t("Схема", "Schema"), t("Таблица", "Table"), t("Владелец", "Owner"), t("Байт", "Bytes"), t("Размер", "Size")]),
        (t("Активные запросы", "Active queries"), report_sql.REPORT_ACTIVE_QUERIES_SQL, None, ["PID", t("Пользователь", "User"), t("Состояние", "State"), t("Длительность", "Duration"), "SQL"]),
        (t("Активные сессии", "Active sessions"), report_sql.REPORT_ACTIVE_SESSIONS_SQL, None, ["PID", t("Пользователь", "User"), t("База", "Database"), t("Приложение", "Application"), t("Клиент", "Client"), t("Состояние", "State"), t("Длительность", "Duration")]),
        (t("Блокировки", "Locks"), report_sql.REPORT_LOCKS_SQL, None, [t("Заблокирован PID", "Blocked PID"), t("Пользователь", "User"), t("Блокирует PID", "Blocking PID"), t("Пользователь", "User"), t("Длительность", "Duration"), "SQL"]),
        (t("Незавершённые транзакции", "Open transactions"), report_sql.REPORT_IDLE_TRANSACTIONS_SQL, None, ["PID", t("Пользователь", "User"), t("Приложение", "Application"), t("Клиент", "Client"), t("Состояние", "State"), t("Возраст", "Age"), "SQL"]),
        (t("Ожидания сессий", "Session waits"), report_sql.REPORT_WAIT_EVENTS_SQL, None, [t("Тип ожидания", "Wait type"), t("Событие", "Event"), t("Сессий", "Sessions")]),
        (
            t("Эффективность доступа к таблицам", "Table access efficiency"),
            report_sql.REPORT_TABLE_ACCESS_SQL,
            None,
            [t("Схема", "Schema"), t("Таблица", "Table"), t("Seq scan", "Seq scans"), t("Index scan", "Index scans"), t("Индексы, %", "Index usage, %"), t("Живые", "Live rows"), t("Мёртвые", "Dead rows"), t("Мёртвые, %", "Dead rows, %"), "Autovacuum", "Autoanalyze"],
        ),
        (t("Память", "Memory"), report_sql.REPORT_MEMORY_SQL, None, [t("Параметр", "Parameter"), t("Значение", "Value"), t("Единица", "Unit")]),
        (t("Обслуживание", "Maintenance"), report_sql.REPORT_MAINTENANCE_SQL, None, [t("Схема", "Schema"), t("Таблица", "Table"), t("Живые", "Live rows"), t("Мёртвые", "Dead rows"), "VACUUM", "Autovacuum", "ANALYZE", "Autoanalyze"]),
        (t("Пользователи", "Users"), report_sql.REPORT_USERS_SQL, None, [t("Пользователь", "User"), t("Вход", "Login"), "Superuser", t("Создание БД", "Create DB"), t("Создание ролей", "Create roles"), t("Лимит", "Limit")]),
        (t("Группы", "Groups"), report_sql.REPORT_GROUPS_SQL, None, [t("Группа", "Group"), t("Участников", "Member count"), t("Участники", "Members")]),
    ]
    extension_rows, _ = _collect(db_connection, "pg_stat_statements", report_sql.REPORT_PG_STAT_STATEMENTS_CHECK_SQL, language=language)
    if extension_rows:
        definitions.append((t("Ресурсоёмкие запросы", "Expensive queries"), report_sql.REPORT_EXPENSIVE_QUERIES_SQL, None, [t("Вызовов", "Calls"), t("Общее время, мс", "Total time, ms"), t("Среднее время, мс", "Mean time, ms"), t("Строк", "Rows"), "SQL"]))
    if db_connection.is_greenplum_compatible:
        definitions.append(
            (
                t("Сегменты Greenplum/Greengage", "Greenplum/Greengage segments"),
                report_sql.REPORT_GP_SEGMENTS_SQL,
                None,
                ["Content", "DBID", t("Роль", "Role"), t("Предпочтительная", "Preferred role"), t("Режим", "Mode"), t("Статус", "Status"), t("Хост", "Host"), t("Порт", "Port")],
            )
        )
    else:
        definitions.append((t("Сегменты Greenplum/Greengage", "Greenplum/Greengage segments"), None, None, [t("Состояние", "Status")]))

    sections = []
    for title, query, params, headers in definitions:
        if query is None:
            sections.append({"title": title, "headers": headers, "rows": [[t("Не применимо для PostgreSQL", "Not applicable to PostgreSQL")]], "warning": None})
            continue
        rows, warning = _collect(db_connection, title, query, params, language)
        if title == t("Общая информация", "General information") and rows:
            row = list(rows[0])
            row[2] = _format_bytes(int(row[2] or 0))
            rows = [[headers[index], value] for index, value in enumerate(row)]
            headers = [t("Показатель", "Metric"), t("Значение", "Value")]
        elif title == t("Сводка производительности", "Performance summary") and rows:
            row = list(rows[0])
            row[12] = _format_bytes(int(row[12] or 0))
            rows = [[headers[index], value] for index, value in enumerate(row)]
            headers = [t("Показатель", "Metric"), t("Значение", "Value")]
        sections.append({"title": title, "headers": headers, "rows": rows, "warning": warning})
    return sections


def _performance_conclusion(sections, language="ru"):
    def t(ru, en):
        return _label(language, ru, en)

    by_title = {section["title"]: section for section in sections}
    result = []
    severity = 0

    def add(level, message, weight=1):
        nonlocal severity
        severity = max(severity, weight)
        result.append((level, message))

    summary = dict(by_title.get(t("Сводка производительности", "Performance summary"), {}).get("rows", []))
    general = dict(by_title.get(t("Общая информация", "General information"), {}).get("rows", []))
    locks = by_title.get(t("Блокировки", "Locks"), {}).get("rows", [])
    transactions = by_title.get(t("Незавершённые транзакции", "Open transactions"), {}).get("rows", [])
    access = by_title.get(t("Эффективность доступа к таблицам", "Table access efficiency"), {}).get("rows", [])

    def as_number(value):
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0

    def number(mapping, key):
        return as_number(mapping.get(key))

    if locks:
        add(t("Критично", "Critical"), t(f"Обнаружено блокировок: {len(locks)}. Проверьте блокирующие сессии.", f"Locks detected: {len(locks)}. Inspect blocking sessions."), 2)

    cache_hit = number(summary, t("Cache hit, %", "Cache hit, %"))
    if cache_hit and cache_hit < 90:
        add(t("Критично", "Critical"), t(f"Cache hit равен {cache_hit:.1f}%. Высокая доля чтения с диска может ограничивать производительность.", f"Cache hit is {cache_hit:.1f}%. A high disk-read share may be limiting performance."), 2)
    elif cache_hit and cache_hit < 95:
        add(t("Внимание", "Warning"), t(f"Cache hit равен {cache_hit:.1f}%. Проверьте самые читаемые запросы и размер кэша.", f"Cache hit is {cache_hit:.1f}%. Review the most read-intensive queries and cache sizing."))

    commits = number(summary, t("Транзакции COMMIT", "Committed transactions"))
    rollbacks = number(summary, t("Транзакции ROLLBACK", "Rolled back transactions"))
    rollback_ratio = 100 * rollbacks / (commits + rollbacks) if commits + rollbacks else 0
    if rollback_ratio >= 10:
        add(t("Критично", "Critical"), t(f"Доля откатов составляет {rollback_ratio:.1f}%. Проверьте ошибки приложения и конфликты транзакций.", f"Rollback rate is {rollback_ratio:.1f}%. Check application errors and transaction conflicts."), 2)
    elif rollback_ratio >= 5:
        add(t("Внимание", "Warning"), t(f"Доля откатов составляет {rollback_ratio:.1f}%.", f"Rollback rate is {rollback_ratio:.1f}%."))

    connections = number(summary, t("Подключения", "Connections"))
    max_connections = number(general, t("Максимум подключений", "Maximum connections"))
    connection_ratio = 100 * connections / max_connections if max_connections else 0
    if connection_ratio >= 90:
        add(t("Критично", "Critical"), t(f"Использовано {connection_ratio:.1f}% доступных подключений.", f"{connection_ratio:.1f}% of available connections are in use."), 2)
    elif connection_ratio >= 75:
        add(t("Внимание", "Warning"), t(f"Использовано {connection_ratio:.1f}% доступных подключений.", f"{connection_ratio:.1f}% of available connections are in use."))

    deadlocks = int(number(summary, t("Deadlock", "Deadlocks")))
    if deadlocks:
        add(t("Внимание", "Warning"), t(f"С момента сброса статистики зарегистрировано deadlock: {deadlocks}.", f"Deadlocks since statistics reset: {deadlocks}."))

    bloated = [row for row in access if len(row) > 7 and as_number(row[7]) >= 20 and as_number(row[6]) >= 100000]
    if bloated:
        add(t("Внимание", "Warning"), t(f"У {len(bloated)} крупных таблиц не менее 20% мёртвых строк. Проверьте autovacuum.", f"{len(bloated)} large tables have at least 20% dead rows. Check autovacuum."))

    sequential = [row for row in access if len(row) > 5 and as_number(row[5]) >= 100000 and as_number(row[4]) < 80 and as_number(row[2]) > 100]
    if sequential:
        add(t("Внимание", "Warning"), t(f"Для {len(sequential)} крупных таблиц доля index scan ниже 80%. Проверьте планы запросов и индексы.", f"{len(sequential)} large tables have index scan usage below 80%. Review query plans and indexes."))

    long_transactions = [row for row in transactions if len(row) > 5 and hasattr(row[5], "total_seconds") and row[5].total_seconds() >= 900]
    if long_transactions:
        add(t("Внимание", "Warning"), t(f"Транзакций старше 15 минут: {len(long_transactions)}. Они могут удерживать блокировки и мешать очистке.", f"Transactions older than 15 minutes: {len(long_transactions)}. They may hold locks and delay vacuum."))

    if not result:
        result.append((t("Норма", "Normal"), t("По доступному снимку критические отклонения производительности не обнаружены.", "No critical performance deviations were found in the available snapshot.")))

    status = t("Требует внимания", "Needs attention") if severity == 2 else t("Есть замечания", "Observations found") if severity == 1 else t("Стабильно", "Stable")
    result.insert(0, (t("Итог", "Overall"), t(f"Оценка: {status}. Заключение основано на текущем снимке и накопительной статистике PostgreSQL.", f"Assessment: {status}. The conclusion is based on the current snapshot and cumulative PostgreSQL statistics.")))
    warnings = [section["title"] for section in sections if section["warning"]]
    if warnings:
        result.append((t("Информация", "Information"), t("Часть разделов недоступна: ", "Some sections are unavailable: ") + ", ".join(warnings) + "."))
    return result


def _build_pdf(db_connection, db_user, sections, language="ru"):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

    def t(ru, en):
        return _label(language, ru, en)

    regular, bold = _register_fonts()
    styles = getSampleStyleSheet()
    normal = ParagraphStyle("ReportNormal", parent=styles["BodyText"], fontName=regular, fontSize=7, leading=9)
    heading = ParagraphStyle("ReportHeading", parent=styles["Heading1"], fontName=bold, fontSize=15, leading=18, textColor=colors.HexColor("#1d4ed8"), spaceAfter=8)
    title = ParagraphStyle("ReportTitle", parent=heading, fontSize=20, leading=23, alignment=TA_CENTER, spaceAfter=8)
    buffer = io.BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm, topMargin=14 * mm, bottomMargin=14 * mm, title=t(f"Отчёт по базе {db_connection.database}", f"Database report: {db_connection.database}"))
    story = [Paragraph("DB STAT", title), Paragraph(t("Диагностика базы данных", "Database diagnostics"), title), Spacer(1, 3 * mm)]
    cover = [
        [t("Подключение", "Connection"), db_connection.name],
        [t("СУБД", "DBMS"), db_connection.db_type],
        [t("База данных", "Database"), db_connection.database],
        [t("Сервер", "Server"), f"{db_connection.host}:{db_connection.port}"],
        [t("Пользователь отчёта", "Report user"), db_user.login],
        [t("Сформирован", "Generated"), datetime.now().astimezone().strftime("%d.%m.%Y %H:%M:%S %Z")],
    ]
    conclusion = _performance_conclusion(sections, language)
    story.extend([_pdf_table(cover, normal, bold, header=False), Spacer(1, 4 * mm), Paragraph(t("Заключение о производительности", "Performance conclusion"), heading), _pdf_table([[t("Уровень", "Level"), t("Вывод", "Finding")], *conclusion], normal, bold), PageBreak()])
    for section in sections:
        story.append(Paragraph(_text(section["title"]), heading))
        if section["warning"]:
            story.append(Paragraph(_text(section["warning"]), normal))
        elif not section["rows"]:
            story.append(Paragraph(t("На момент формирования отчёта данные отсутствуют.", "No data was available when the report was generated."), normal))
        else:
            story.append(_pdf_table([section["headers"], *section["rows"]], normal, bold))
        story.extend([Spacer(1, 5 * mm)])

    def page(canvas, doc):
        canvas.saveState()
        canvas.setFont(regular, 7)
        canvas.setFillColor(colors.grey)
        canvas.drawString(12 * mm, 7 * mm, f"DB STAT · {db_connection.name} · {db_connection.database}")
        canvas.drawRightString(landscape(A4)[0] - 12 * mm, 7 * mm, t(f"Страница {doc.page}", f"Page {doc.page}"))
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
            jobs = ReportJob.objects.select_related("connection", "user").filter(user=db_user).order_by("-created")
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
    existing = ReportJob.objects.select_related("connection", "user").filter(user=db_user, connection=db_connection, language=language, status__in=("queued", "running")).first()
    if existing:
        return JsonResponse({"ok": True, "job": _serialize_report_job(existing)}, status=202)
    job = ReportJob.objects.create(user=db_user, connection=db_connection, language=language)
    _submit_report_job(job.pk)
    return JsonResponse({"ok": True, "job": _serialize_report_job(job)}, status=202)
