"""Форматирование и разбор размеров и длительностей для отображения и отчётов.

Модуль не зависит от Django и
моделей: это чистые функции над значениями из PostgreSQL и psycopg2.
"""


def _parse_pg_size_to_bytes(value, default_unit="B"):
    """Преобразует значение размера PostgreSQL в байты"""
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    parts = text.split()
    if len(parts) == 1:
        number_part = "".join(ch for ch in text if ch.isdigit() or ch in ".,-")
        unit_part = text[len(number_part) :].strip() or default_unit
    else:
        number_part, unit_part = parts[0], parts[1]
    try:
        number = float(number_part.replace(",", ""))
    except ValueError:
        return None
    unit = unit_part.lower()
    multipliers = {"b": 1, "byte": 1, "bytes": 1, "kb": 1024, "kib": 1024, "mb": 1024**2, "mib": 1024**2, "gb": 1024**3, "gib": 1024**3, "tb": 1024**4, "tib": 1024**4}
    return int(number * multipliers.get(unit, 1))


def _format_duration(value):
    """Форматирует интервал времени (timedelta) для отображения"""
    return str(value).split(".")[0] if value else "—"


def _duration_seconds(value):
    """Возвращает продолжительность интервала в секундах (0, если значение отсутствует)"""
    return max(int(value.total_seconds()), 0) if value else 0


def _format_bytes(size_bytes):
    """Форматирует размер в байтах для отображения"""
    if size_bytes is None:
        return "—"
    value = float(size_bytes)
    for unit in ["Б", "КБ", "МБ", "ГБ"]:
        if value < 1024:
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{value:.2f} ТБ"
