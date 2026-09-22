from datetime import timedelta
from types import SimpleNamespace

from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from db_statistics.models import DBConnection, DBUser, ReportJob
from db_statistics.views.reports import _build_pdf, _performance_conclusion


class ReportHistoryTests(TestCase):
    def setUp(self):
        self.user = DBUser.objects.create_user("analyst", "analyst@example.com", "password")
        self.other_user = DBUser.objects.create_user("other", "other@example.com", "password")
        self.connection = DBConnection.objects.create(name="Production", host="db", database="analytics", username="reader", password="secret")
        session = self.client.session
        session[settings.SESSION_USER_ID_KEY] = self.user.pk
        session.save()

    def test_report_history_is_newest_first_and_only_contains_current_user_reports(self):
        older = ReportJob.objects.create(user=self.user, connection=self.connection, status="completed", content=b"pdf", filename="older.pdf")
        newer = ReportJob.objects.create(user=self.user, connection=self.connection, status="running")
        ReportJob.objects.create(user=self.other_user, connection=self.connection, status="completed", content=b"private", filename="private.pdf")
        ReportJob.objects.filter(pk=older.pk).update(created=timezone.now() - timedelta(days=1))

        response = self.client.get(reverse("database_pdf_report"))

        self.assertEqual(response.status_code, 200)
        reports = response.json()["reports"]
        self.assertEqual([report["id"] for report in reports], [str(newer.pk), str(older.pk)])
        self.assertEqual(reports[0]["database"], "analytics")
        self.assertIsNone(reports[0]["download_url"])
        self.assertTrue(reports[1]["download_url"].endswith(f"job_id={older.pk}&download=1"))

    def test_report_history_requires_authentication(self):
        self.client.logout()

        response = self.client.get(reverse("database_pdf_report"))

        self.assertEqual(response.status_code, 401)


class PerformanceConclusionTests(TestCase):
    def test_conclusion_detects_major_performance_risks(self):
        sections = [
            {"title": "Сводка производительности", "rows": [["Подключения", 95], ["Cache hit, %", 82], ["Транзакции COMMIT", 800], ["Транзакции ROLLBACK", 200], ["Deadlock", 3]], "warning": None},
            {"title": "Общая информация", "rows": [["Максимум подключений", 100]], "warning": None},
            {"title": "Блокировки", "rows": [[101, "user", 202]], "warning": None},
            {"title": "Незавершённые транзакции", "rows": [[101, "user", "idle", timedelta(minutes=20), "SELECT 1"]], "warning": None},
            {"title": "Проблемные таблицы", "rows": [["public", "events", 500, 10, 2, 1_000_000, 300_000, 23]], "warning": None},
        ]

        conclusion = _performance_conclusion(sections)

        self.assertEqual(conclusion[0][0], "Итог")
        self.assertIn("Требует внимания", conclusion[0][1])
        self.assertTrue(any("Cache hit" in finding for _, finding in conclusion))
        self.assertTrue(any("откатов" in finding for _, finding in conclusion))
        self.assertTrue(any("старше 15 минут" in finding for _, finding in conclusion))

    def test_conclusion_reports_stable_snapshot_without_findings(self):
        sections = [
            {"title": "Сводка производительности", "rows": [["Подключения", 10], ["Cache hit, %", 99], ["Транзакции COMMIT", 1000], ["Транзакции ROLLBACK", 1], ["Deadlock", 0]], "warning": None},
            {"title": "Общая информация", "rows": [["Максимум подключений", 100]], "warning": None},
            {"title": "Блокировки", "rows": [], "warning": None},
            {"title": "Незавершённые транзакции", "rows": [], "warning": None},
            {"title": "Проблемные таблицы", "rows": [], "warning": None},
        ]

        conclusion = _performance_conclusion(sections)

        self.assertIn("Стабильно", conclusion[0][1])
        self.assertEqual(conclusion[1][0], "Норма")

    def test_pdf_is_built_with_performance_conclusion(self):
        sections = [
            {"title": "Сводка производительности", "headers": ["Показатель", "Значение"], "rows": [["Cache hit, %", 99]], "warning": None},
            {"title": "Общая информация", "headers": ["Показатель", "Значение"], "rows": [["Максимум подключений", 100]], "warning": None},
        ]
        db_connection = SimpleNamespace(name="Production", db_type="PostgreSQL", database="analytics", host="db", port=5432)
        db_user = SimpleNamespace(login="analyst")

        pdf = _build_pdf(db_connection, db_user, sections)

        self.assertTrue(pdf.read().startswith(b"%PDF"))
