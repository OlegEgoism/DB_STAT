import base64
import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from db_statistics.licensing import LicenseError, activation_hash, canonical_payload, verify_license


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
