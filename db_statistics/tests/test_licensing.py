import base64
import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse

from db_statistics.licensing import LicenseError, LicenseStatus, activation_hash, canonical_payload, verify_license
from db_statistics.views_additional import license_activation
from scripts.create_license import main as create_license_interactively


class LicensingTests(SimpleTestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        self.private_key = Ed25519PrivateKey.generate()
        self.public_key_path = self.directory / "public.pem"
        self.public_key_path.write_bytes(self.private_key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
        self.license_path = self.directory / "installed.license"
        self.settings_override = override_settings(LICENSE_PUBLIC_KEY_FILE=self.public_key_path, LICENSE_FILE=self.license_path)
        self.settings_override.enable()

    def tearDown(self):
        self.settings_override.disable()
        self.temporary_directory.cleanup()

    def _license(self, *, organization="ООО Тест", valid_from=None, valid_until=None):
        now = datetime.now(UTC)
        payload = {"schema_version": 1, "license_id": "test-license-id", "product": "db-stat", "organization": organization, "issued_at": now.isoformat(), "valid_from": (valid_from or now - timedelta(days=1)).isoformat(), "valid_until": (valid_until or now + timedelta(days=30)).isoformat()}
        signature = self.private_key.sign(canonical_payload(payload))
        return json.dumps({"payload": payload, "activation_hash": activation_hash(payload), "signature": base64.urlsafe_b64encode(signature).decode("ascii")}).encode()

    def test_valid_license_contains_organization_and_unique_hash(self):
        status = verify_license(self._license())

        self.assertTrue(status.valid)
        self.assertEqual(status.organization, "ООО Тест")
        self.assertEqual(len(status.activation_hash), 64)

    def test_modified_license_is_rejected(self):
        document = json.loads(self._license())
        document["payload"]["organization"] = "Подменённая организация"

        with self.assertRaisesRegex(LicenseError, "подпись"):
            verify_license(json.dumps(document).encode())

    def test_expired_license_is_rejected(self):
        now = datetime.now(UTC)

        with self.assertRaisesRegex(LicenseError, "истёк"):
            verify_license(self._license(valid_from=now - timedelta(days=2), valid_until=now - timedelta(days=1)))

    def test_license_end_date_is_inclusive_and_next_day_is_rejected(self):
        document = json.loads(self._license())
        document["payload"]["valid_from"] = "2020-01-01"
        document["payload"]["valid_until"] = "2026-01-01"
        document["activation_hash"] = activation_hash(document["payload"])
        document["signature"] = base64.urlsafe_b64encode(self.private_key.sign(canonical_payload(document["payload"]))).decode("ascii")
        data = json.dumps(document).encode()

        self.assertTrue(verify_license(data, now=datetime(2026, 1, 1, 23, 59, 59, tzinfo=UTC)).valid)
        with self.assertRaisesRegex(LicenseError, "истёк"):
            verify_license(data, now=datetime(2026, 1, 2, tzinfo=UTC))

    def test_license_status_includes_remaining_days(self):
        now = datetime(2026, 1, 1, 12, tzinfo=UTC)
        document = json.loads(self._license())
        document["payload"]["valid_from"] = "2026-01-01"
        document["payload"]["valid_until"] = "2026-01-10"
        document["activation_hash"] = activation_hash(document["payload"])
        document["signature"] = base64.urlsafe_b64encode(self.private_key.sign(canonical_payload(document["payload"]))).decode("ascii")

        status = verify_license(json.dumps(document).encode(), now=now)

        self.assertEqual(status.days_remaining, 10)
        self.assertEqual(status.valid_until, "2026-01-10")

    def test_first_start_redirects_to_activation_and_upload_installs_file(self):
        response = self.client.get(reverse("home"))
        self.assertRedirects(response, reverse("license_activation"), fetch_redirect_response=False)

        response = self.client.post(reverse("license_activation"), {"license_file": SimpleUploadedFile("customer.license", self._license(), content_type="application/json")})

        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.assertTrue(self.license_path.is_file())
        self.assertEqual(self.license_path.stat().st_mode & 0o777, 0o600)

    def test_expired_installed_license_blocks_application_with_403(self):
        now = datetime.now(UTC)
        self.license_path.write_bytes(self._license(valid_from=now - timedelta(days=2), valid_until=now - timedelta(days=1)))

        response = self.client.get(reverse("home"))
        self.assertRedirects(response, reverse("license_activation"), fetch_redirect_response=False)
        activation_response = self.client.get(reverse("license_activation"))

        self.assertEqual(activation_response.status_code, 403)
        self.assertContains(activation_response, "Срок действия лицензии истёк", status_code=403)

    def test_only_administrator_can_replace_active_license(self):
        request = RequestFactory().post(reverse("license_activation"), {"license_file": SimpleUploadedFile("replacement.license", self._license())})
        active_status = LicenseStatus(True, True, "Лицензия активна")

        with patch("db_statistics.views_additional.license_status", return_value=active_status), patch("db_statistics.views_additional._current_db_user", return_value=None):
            response = license_activation(request)

        self.assertEqual(response.status_code, 403)
        self.assertIn("только Администратор", json.loads(response.content)["message"])

    def test_license_interface_has_english_translations(self):
        source = (Path(__file__).resolve().parents[2] / "static" / "js" / "i18n.js").read_text(encoding="utf-8")

        self.assertIn("'Активация DB STAT': 'DB STAT activation'", source)
        self.assertIn("'Срок действия лицензии истёк': 'The license has expired'", source)
        self.assertIn("'Загрузить новый ключ лицензии': 'Upload a new license key'", source)
        self.assertIn("'Настройки меню': 'Menu settings'", source)

    def test_settings_are_split_into_four_logical_tabs(self):
        source = (Path(__file__).resolve().parents[2] / "templates" / "includes" / "_main_content.html").read_text(encoding="utf-8")

        self.assertEqual(source.count('class="tab-pane fade'), 4)
        for pane_id in ("settingsLicensePane", "settingsThemePane", "settingsLanguagePane", "settingsMenuPane"):
            self.assertIn(f'id="{pane_id}"', source)

    def test_interactive_script_creates_keys_and_license(self):
        issuer_dir = self.directory / "issuer"
        private_key = issuer_dir / "db-stat-private.pem"
        public_key = self.directory / "public-created.pem"
        output = self.directory / "ООО-Интерактив-2026-12-31.license"
        answers = iter(["ООО Интерактив", "2026-01-01", "2026-12-31"])

        with patch("builtins.input", side_effect=lambda _prompt: next(answers)):
            result = create_license_interactively(scripts_dir=self.directory, issuer_dir=issuer_dir, public_key=public_key)

        self.assertEqual(result, 0)
        self.assertTrue(private_key.is_file())
        self.assertTrue(public_key.is_file())
        self.assertTrue(output.is_file())
        self.assertEqual(set(json.loads(output.read_bytes())), {"organization", "valid_from", "valid_until", "activation_hash", "signature"})
        with override_settings(LICENSE_PUBLIC_KEY_FILE=public_key):
            status = verify_license(output.read_bytes(), now=datetime(2026, 6, 1, tzinfo=UTC))
            modified_document = json.loads(output.read_bytes())
            modified_document["organization"] = "Изменённая организация"
            with self.assertRaisesRegex(LicenseError, "подпись"):
                verify_license(json.dumps(modified_document).encode(), now=datetime(2026, 6, 1, tzinfo=UTC))
        self.assertEqual(status.organization, "ООО Интерактив")
