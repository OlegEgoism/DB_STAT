import base64
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from cryptography.hazmat.primitives import serialization
from django.core.management.base import BaseCommand, CommandError

from db_statistics.licensing import activation_hash, canonical_payload


class Command(BaseCommand):
    help = "Выпускает подписанный файл лицензии DB STAT"

    def add_arguments(self, parser):
        parser.add_argument("--organization", required=True)
        parser.add_argument("--valid-from", required=True, help="Дата YYYY-MM-DD")
        parser.add_argument("--valid-until", required=True, help="Дата YYYY-MM-DD (не включительно)")
        parser.add_argument("--private-key", required=True)
        parser.add_argument("--output", required=True)
        parser.add_argument("--password-env", default="LICENSE_PRIVATE_KEY_PASSWORD")

    def handle(self, *args, **options):
        try:
            valid_from = datetime.strptime(options["valid_from"], "%Y-%m-%d").replace(tzinfo=UTC)
            valid_until = datetime.strptime(options["valid_until"], "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError as exc:
            raise CommandError("Даты должны иметь формат YYYY-MM-DD") from exc
        if valid_until <= valid_from:
            raise CommandError("Дата окончания должна быть позже даты начала")
        password = os.getenv(options["password_env"], "").encode()
        if not password:
            raise CommandError(f"Задайте пароль закрытого ключа в переменной {options['password_env']}")
        try:
            private_key = serialization.load_pem_private_key(Path(options["private_key"]).read_bytes(), password=password)
        except (OSError, ValueError) as exc:
            raise CommandError("Не удалось прочитать закрытый ключ") from exc
        payload = {"schema_version": 1, "license_id": str(uuid4()), "product": "db-stat", "organization": options["organization"].strip(), "issued_at": datetime.now(UTC).isoformat(), "valid_from": valid_from.isoformat(), "valid_until": valid_until.isoformat()}
        if not payload["organization"]:
            raise CommandError("Название организации не может быть пустым")
        signature = private_key.sign(canonical_payload(payload))
        unique_hash = activation_hash(payload)
        document = {"payload": payload, "activation_hash": unique_hash, "signature": base64.urlsafe_b64encode(signature).decode("ascii")}
        output = Path(options["output"])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Лицензия: {output}\nХеш активации: {unique_hash}"))
