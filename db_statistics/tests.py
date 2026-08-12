from types import SimpleNamespace
from unittest.mock import mock_open, patch

from django.test import SimpleTestCase, override_settings

from db_statistics.google_docs import _connection_text, export_connection_to_google_doc


class GoogleDocsExportTests(SimpleTestCase):
    def setUp(self):
        self.connection = SimpleNamespace(name="Аналитика", db_type="PostgreSQL", host="db.internal", port=5432, database="reports", username="reader", password="super-secret")
        self.user = SimpleNamespace(login="admin")

    def test_connection_text_omits_password(self):
        exported_text = _connection_text(self.connection, self.user)

        self.assertIn("Название: Аналитика", exported_text)
        self.assertIn("Пользователь БД: reader", exported_text)
        self.assertNotIn("super-secret", exported_text)
        self.assertNotIn("Пароль", exported_text)

    @override_settings(GOOGLE_DOCS_EXPORT_ENABLED=False)
    def test_disabled_export_does_not_read_credentials(self):
        with patch("builtins.open") as open_file:
            result = export_connection_to_google_doc(self.connection, self.user)

        self.assertFalse(result.exported)
        self.assertIn("отключён", result.message)
        open_file.assert_not_called()

    @override_settings(GOOGLE_DOCS_EXPORT_ENABLED=True, GOOGLE_DOCS_DOCUMENT_ID="document-id", GOOGLE_SERVICE_ACCOUNT_FILE="/credentials.json", GOOGLE_SERVICE_ACCOUNT_JSON="")
    @patch("db_statistics.google_docs._authorized_json")
    @patch("db_statistics.google_docs._service_account_token", return_value="access-token")
    def test_export_appends_connection_to_configured_document(self, token, authorized_json):
        authorized_json.side_effect = [{"body": {"content": [{"endIndex": 12}]}}, {}]

        with patch("builtins.open", mock_open(read_data='{"client_email": "service@example.com"}')):
            result = export_connection_to_google_doc(self.connection, self.user)

        self.assertTrue(result.exported)
        token.assert_called_once_with({"client_email": "service@example.com"})
        update_url, _access_token = authorized_json.call_args_list[1].args
        update_payload = authorized_json.call_args_list[1].kwargs["payload"]
        self.assertEqual(update_url, "https://docs.googleapis.com/v1/documents/document-id:batchUpdate")
        self.assertEqual(update_payload["requests"][0]["insertText"]["location"]["index"], 11)
        self.assertNotIn("super-secret", update_payload["requests"][0]["insertText"]["text"])

    @override_settings(GOOGLE_DOCS_EXPORT_ENABLED=True, GOOGLE_DOCS_DOCUMENT_ID="document-id", GOOGLE_SERVICE_ACCOUNT_FILE="", GOOGLE_SERVICE_ACCOUNT_JSON="")
    def test_enabled_export_reports_missing_credentials(self):
        result = export_connection_to_google_doc(self.connection, self.user)

        self.assertFalse(result.exported)
        self.assertIn("GOOGLE_SERVICE_ACCOUNT_JSON", result.message)
