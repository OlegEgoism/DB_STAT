import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Генерирует пару Ed25519-ключей для выпуска лицензий"

    def add_arguments(self, parser):
        parser.add_argument("--private-key", required=True)
        parser.add_argument("--public-key", required=True)
        parser.add_argument("--password-env", default="LICENSE_PRIVATE_KEY_PASSWORD")

    def handle(self, *args, **options):
        private_path = Path(options["private_key"])
        public_path = Path(options["public_key"])
        if private_path.exists() or public_path.exists():
            raise CommandError("Файл ключа уже существует; перезапись запрещена")
        password = os.getenv(options["password_env"], "").encode()
        if not password:
            raise CommandError(f"Задайте пароль закрытого ключа в переменной {options['password_env']}")
        private_key = Ed25519PrivateKey.generate()
        private_path.parent.mkdir(parents=True, exist_ok=True)
        public_path.parent.mkdir(parents=True, exist_ok=True)
        private_path.write_bytes(private_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.BestAvailableEncryption(password)))
        private_path.chmod(0o600)
        public_path.write_bytes(private_key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
        public_path.chmod(0o644)
        self.stdout.write(self.style.SUCCESS(f"Закрытый ключ: {private_path}\nОткрытый ключ: {public_path}"))
