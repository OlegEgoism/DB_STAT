#!/usr/bin/env python3
"""Интерактивный мастер выпуска офлайн-лицензии DB STAT."""

import getpass
import os
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "db.settings")

import django  # noqa: E402
from django.core.management import call_command  # noqa: E402
from django.core.management.base import CommandError  # noqa: E402


def ask(prompt, default=None):
    """Запрашивает непустое значение, при наличии показывая значение по умолчанию."""
    suffix = f" [{default}]" if default else ""
    while True:
        value = input(f"{prompt}{suffix}: ").strip()
        if value:
            return value
        if default is not None:
            return str(default)
        print("Значение не может быть пустым.")


def ask_yes_no(prompt, *, default=False):
    """Запрашивает подтверждение да/нет."""
    hint = "Y/n" if default else "y/N"
    while True:
        value = input(f"{prompt} [{hint}]: ").strip().lower()
        if not value:
            return default
        if value in {"y", "yes", "д", "да"}:
            return True
        if value in {"n", "no", "н", "нет"}:
            return False
        print("Введите y/yes/да или n/no/нет.")


def ask_date(prompt, default=None):
    """Запрашивает календарную дату формата YYYY-MM-DD."""
    while True:
        value = ask(prompt, default)
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            print("Некорректная дата. Используйте формат YYYY-MM-DD, например 2027-12-31.")


def ask_password(*, confirmation=False):
    """Без отображения на экране запрашивает пароль закрытого ключа."""
    while True:
        password = getpass.getpass("Пароль закрытого ключа: ")
        if not password:
            print("Пароль не может быть пустым.")
            continue
        if confirmation and password != getpass.getpass("Повторите пароль: "):
            print("Пароли не совпадают.")
            continue
        return password


def main():
    django.setup()
    print("\n=== Мастер создания лицензии DB STAT ===\n")

    default_private = Path.home() / "db-stat-license-secrets" / "db-stat-private.pem"
    private_key = Path(ask("Путь к закрытому ключу", default_private)).expanduser().resolve()
    password = ""
    if not private_key.exists():
        print(f"Закрытый ключ не найден: {private_key}")
        if not ask_yes_no("Создать новую пару Ed25519-ключей?", default=True):
            print("Создание лицензии отменено.")
            return 1
        public_key = Path(ask("Путь для открытого ключа", PROJECT_ROOT / "license-public.pem")).expanduser().resolve()
        password = ask_password(confirmation=True)
        os.environ["DB_STAT_ISSUER_KEY_PASSWORD"] = password
        try:
            call_command("generate_license_keys", private_key=str(private_key), public_key=str(public_key), password_env="DB_STAT_ISSUER_KEY_PASSWORD")
        finally:
            os.environ.pop("DB_STAT_ISSUER_KEY_PASSWORD", None)
        print("Сохраните закрытый ключ и пароль в защищённом хранилище. Клиенту передаётся только открытый ключ.\n")
    else:
        password = ask_password()

    organization = ask("Название организации")
    valid_from = ask_date("Первый день действия", datetime.now().date().isoformat())
    valid_until = ask_date("Последний день действия (включительно)")
    while valid_until < valid_from:
        print("Последний день действия не может быть раньше первого.")
        valid_until = ask_date("Последний день действия (включительно)")

    safe_name = "".join(character if character.isalnum() or character in "-_" else "-" for character in organization).strip("-") or "customer"
    output = Path(ask("Путь к файлу лицензии", PROJECT_ROOT / f"{safe_name}.license")).expanduser().resolve()
    if output.exists() and not ask_yes_no(f"Файл {output} уже существует. Перезаписать?"):
        print("Создание лицензии отменено.")
        return 1

    os.environ["DB_STAT_ISSUER_KEY_PASSWORD"] = password
    try:
        call_command("generate_license", organization=organization, valid_from=valid_from.isoformat(), valid_until=valid_until.isoformat(), private_key=str(private_key), output=str(output), password_env="DB_STAT_ISSUER_KEY_PASSWORD")
    finally:
        os.environ.pop("DB_STAT_ISSUER_KEY_PASSWORD", None)

    print(f"\nГотово. Передайте клиенту файл:\n{output}")
    print("Закрытый ключ и его пароль клиенту не передаются.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CommandError, KeyboardInterrupt) as error:
        print(f"\nОшибка: {error}", file=sys.stderr)
        raise SystemExit(1) from error
