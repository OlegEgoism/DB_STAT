from django.test import SimpleTestCase, override_settings

from db_statistics.checks import check_encryption_key_separate


class EncryptionKeyCheckTests(SimpleTestCase):
    @override_settings(DEBUG=False, SECRET_KEY="a" * 50, DB_CONNECTION_ENCRYPTION_KEY="a" * 50)
    def test_warns_when_key_equals_secret_in_production(self):
        warnings = check_encryption_key_separate(None)

        self.assertEqual([w.id for w in warnings], ["db_statistics.W004"])

    @override_settings(DEBUG=False, SECRET_KEY="a" * 50, DB_CONNECTION_ENCRYPTION_KEY="b" * 50)
    def test_no_warning_when_key_is_separate(self):
        self.assertEqual(check_encryption_key_separate(None), [])

    @override_settings(DEBUG=True, SECRET_KEY="a" * 50, DB_CONNECTION_ENCRYPTION_KEY="a" * 50)
    def test_no_warning_in_debug_mode(self):
        self.assertEqual(check_encryption_key_separate(None), [])
