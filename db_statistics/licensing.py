"""Проверка и установка офлайн-лицензий DB STAT."""

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from django.conf import settings


class LicenseError(ValueError):
    """Файл лицензии отсутствует, повреждён или не действует."""


@dataclass(frozen=True)
class LicenseStatus:
    installed: bool
    valid: bool
    message: str
    organization: str = ""
    valid_from: str = ""
    valid_until: str = ""
    activation_hash: str = ""


def canonical_payload(payload):
    """Возвращает стабильное байтовое представление подписываемых данных."""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def activation_hash(payload):
    """Вычисляет публичный уникальный идентификатор содержимого лицензии."""
    return hashlib.sha256(canonical_payload(payload)).hexdigest()


def _parse_datetime(value, field_name):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise LicenseError(f"Поле {field_name} содержит некорректную дату") from exc
    if parsed.tzinfo is None:
        raise LicenseError(f"Поле {field_name} должно содержать часовой пояс")
    return parsed.astimezone(UTC)


def verify_license(data, *, now=None):
    """Проверяет подпись, идентификатор, продукт и срок лицензии."""
    try:
        document = json.loads(data.decode("utf-8"))
        payload = document["payload"]
        signature = base64.urlsafe_b64decode(document["signature"].encode("ascii"))
    except (AttributeError, KeyError, TypeError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise LicenseError("Некорректный формат файла лицензии") from exc
    if not isinstance(payload, dict) or payload.get("product") != "db-stat" or payload.get("schema_version") != 1:
        raise LicenseError("Файл предназначен для другого продукта или версии")
    public_key_path = Path(settings.LICENSE_PUBLIC_KEY_FILE)
    try:
        public_key = serialization.load_pem_public_key(public_key_path.read_bytes())
    except (OSError, ValueError) as exc:
        raise LicenseError("Открытый ключ лицензирования не настроен") from exc
    try:
        public_key.verify(signature, canonical_payload(payload))
    except (InvalidSignature, TypeError, ValueError) as exc:
        raise LicenseError("Цифровая подпись лицензии недействительна") from exc
    expected_hash = activation_hash(payload)
    if document.get("activation_hash") != expected_hash:
        raise LicenseError("Уникальный хеш лицензии повреждён")
    valid_from = _parse_datetime(payload.get("valid_from"), "valid_from")
    valid_until = _parse_datetime(payload.get("valid_until"), "valid_until")
    if valid_until <= valid_from:
        raise LicenseError("Дата окончания должна быть позже даты начала")
    current_time = now or datetime.now(UTC)
    if current_time < valid_from:
        raise LicenseError("Срок действия лицензии ещё не наступил")
    if current_time >= valid_until:
        raise LicenseError("Срок действия лицензии истёк")
    return LicenseStatus(True, True, "Лицензия активна", str(payload.get("organization", "")), valid_from.isoformat(), valid_until.isoformat(), expected_hash)


def license_status():
    """Возвращает состояние установленной лицензии без возбуждения исключений."""
    path = Path(settings.LICENSE_FILE)
    if not path.is_file():
        return LicenseStatus(False, False, "Лицензия не установлена")
    try:
        return verify_license(path.read_bytes())
    except (OSError, LicenseError) as exc:
        return LicenseStatus(True, False, str(exc))


def install_license(data):
    """Проверяет и атомарно устанавливает полученный файл лицензии."""
    status = verify_license(data)
    destination = Path(settings.LICENSE_FILE)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(f"{destination.suffix}.tmp")
    temporary.write_bytes(data)
    os.chmod(temporary, 0o600)
    temporary.replace(destination)
    return status
