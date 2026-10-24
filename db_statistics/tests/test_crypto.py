from cryptography.fernet import Fernet
from django.test import SimpleTestCase

from db_statistics.models import ENCRYPTED_PASSWORD_PREFIX, _legacy_connection_password_cipher, _pbkdf2_cipher_for_secret, decrypt_connection_password, encrypt_connection_password


class ConnectionPasswordCryptoTests(SimpleTestCase):
    def test_roundtrip_stores_prefixed_token_and_returns_plain_text(self):
        stored = encrypt_connection_password("s3cret")

        self.assertTrue(stored.startswith(ENCRYPTED_PASSWORD_PREFIX))
        self.assertNotIn("s3cret", stored)
        self.assertEqual(decrypt_connection_password(stored), "s3cret")

    def test_already_encrypted_value_is_not_encrypted_twice(self):
        stored = encrypt_connection_password("s3cret")

        self.assertEqual(encrypt_connection_password(stored), stored)

    def test_legacy_sha256_token_still_decrypts(self):
        token = _legacy_connection_password_cipher().encrypt(b"old-password").decode("utf-8")

        self.assertEqual(decrypt_connection_password(f"{ENCRYPTED_PASSWORD_PREFIX}{token}"), "old-password")

    def test_token_from_foreign_key_returns_empty_string(self):
        token = Fernet(Fernet.generate_key()).encrypt(b"x").decode("utf-8")

        self.assertEqual(decrypt_connection_password(f"{ENCRYPTED_PASSWORD_PREFIX}{token}"), "")

    def test_pbkdf2_key_is_derived_once_per_secret_not_per_call(self):
        # PBKDF2 стоит ~50 мс; если бы ключ выводился на каждый вызов, это вернулось бы регрессией.
        stored = encrypt_connection_password("s3cret")
        _pbkdf2_cipher_for_secret.cache_clear()

        for _ in range(5):
            decrypt_connection_password(stored)

        self.assertEqual(_pbkdf2_cipher_for_secret.cache_info().misses, 1)

    def test_plain_text_password_is_returned_unchanged(self):
        self.assertEqual(decrypt_connection_password("plain"), "plain")
        self.assertEqual(decrypt_connection_password(""), "")
