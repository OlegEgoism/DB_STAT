import datetime
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from db_statistics.models import DBAudit


class PurgeAuditTests(TestCase):
    def setUp(self):
        now = timezone.now()
        DBAudit.objects.create(username="u", action_type="login", info="old", created=now - datetime.timedelta(days=400))
        DBAudit.objects.create(username="u", action_type="login", info="fresh", created=now - datetime.timedelta(days=2))

    def test_dry_run_deletes_nothing(self):
        out = StringIO()
        call_command("purge_audit", "--older-than-days", "365", stdout=out)

        self.assertEqual(DBAudit.objects.count(), 2)
        self.assertIn("1", out.getvalue())

    def test_yes_deletes_only_records_older_than_cutoff(self):
        call_command("purge_audit", "--older-than-days", "365", "--yes", stdout=StringIO())

        self.assertEqual(list(DBAudit.objects.values_list("info", flat=True)), ["fresh"])

    def test_refuses_too_short_retention(self):
        with self.assertRaises(CommandError):
            call_command("purge_audit", "--older-than-days", "7", "--yes", stdout=StringIO())

        self.assertEqual(DBAudit.objects.count(), 2)
