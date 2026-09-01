#!/usr/bin/env python3
"""Простой интерактивный генератор лицензий DB STAT."""

import os
import secrets
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "db.settings")

import django  # noqa: E402
from django.core.management import call_command  # noqa: E402
from django.core.management.base import CommandError  # noqa: E402


def ask(prompt):
    """Запрашивает обязательное текстовое значение."""
    while True:
        value = input(f"{prompt}: ").strip()
        if value:
            return value
        print("Значение не может быть пустым.")


def ask_date(prompt):
    """Запрашивает календарную дату формата YYYY-MM-DD."""
    while True:
        value = ask(prompt)
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            print("Некорректная дата. Используйте формат YYYY-MM-DD, например 2027-12-31.")


def _safe_filename(value):
    return "".join(character if character.isalnum() or character in "-_" else "-" for character in value).strip("-") or "customer"


def _issuer_credentials(issuer_dir, public_key):
    """Создаёт один постоянный ключ издателя без дополнительных вопросов."""
    private_key = issuer_dir / "db-stat-private.pem"
    password_file = issuer_dir / "key-password"
    if private_key.is_file() and password_file.is_file() and public_key.is_file():
        return private_key, password_file.read_text(encoding="utf-8").strip()
    if private_key.exists() or password_file.exists() or public_key.exists():
        raise CommandError("Найден неполный комплект ключей. Удалите его или восстановите недостающие файлы")
    issuer_dir.mkdir(parents=True, exist_ok=True)
    issuer_dir.chmod(0o700)
    password = secrets.token_urlsafe(48)
    password_file.write_text(password, encoding="utf-8")
    password_file.chmod(0o600)
    os.environ["DB_STAT_ISSUER_KEY_PASSWORD"] = password
    try:
        call_command("generate_license_keys", private_key=str(private_key), public_key=str(public_key), password_env="DB_STAT_ISSUER_KEY_PASSWORD")
    finally:
        os.environ.pop("DB_STAT_ISSUER_KEY_PASSWORD", None)
    return private_key, password


def main(*, scripts_dir=SCRIPTS_DIR, issuer_dir=None, public_key=None):
    django.setup()
    scripts_dir = Path(scripts_dir)
    issuer_dir = Path(issuer_dir or scripts_dir / ".license-issuer")
    public_key = Path(public_key or PROJECT_ROOT / "license-public.pem")

    print("\n=== Создание лицензии DB STAT ===\n")
    organization = ask("Название организации")
    valid_from = ask_date("Дата действия с (YYYY-MM-DD)")
    valid_until = ask_date("Дата действия по, включительно (YYYY-MM-DD)")
    while valid_until < valid_from:
        print("Дата действия по не может быть раньше даты действия с.")
        valid_until = ask_date("Дата действия по, включительно (YYYY-MM-DD)")

    private_key, password = _issuer_credentials(issuer_dir, public_key)
    scripts_dir.mkdir(parents=True, exist_ok=True)
    output = scripts_dir / f"{_safe_filename(organization)}-{valid_until.isoformat()}.license"
    counter = 2
    while output.exists():
        output = scripts_dir / f"{_safe_filename(organization)}-{valid_until.isoformat()}-{counter}.license"
        counter += 1

    os.environ["DB_STAT_ISSUER_KEY_PASSWORD"] = password
    try:
        call_command("generate_license", organization=organization, valid_from=valid_from.isoformat(), valid_until=valid_until.isoformat(), private_key=str(private_key), output=str(output), password_env="DB_STAT_ISSUER_KEY_PASSWORD")
    finally:
        os.environ.pop("DB_STAT_ISSUER_KEY_PASSWORD", None)

    print(f"\nГотово. Файл лицензии сохранён:\n{output}")
    print(f"Открытый ключ приложения:\n{public_key}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CommandError, KeyboardInterrupt) as error:
        print(f"\nОшибка: {error}", file=sys.stderr)
        raise SystemExit(1) from error
