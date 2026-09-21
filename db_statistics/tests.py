from datetime import timedelta

from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from db_statistics.models import DBConnection, DBUser, ReportJob


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
