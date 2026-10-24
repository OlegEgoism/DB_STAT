from django.test import TestCase

from db_statistics.models import DBConnection
from db_statistics.views.pool import _pool_key


class PoolKeyTests(TestCase):
    def setUp(self):
        self.connection = DBConnection.objects.create(name="pk", host="db.internal", port=5432, database="app", username="reader", password="first-secret")

    def test_pool_key_does_not_contain_plain_password(self):
        key = _pool_key(self.connection, True)

        self.assertNotIn("first-secret", repr(key))

    def test_pool_key_changes_when_password_changes(self):
        before = _pool_key(self.connection, True)
        self.connection.password = "second-secret"
        self.connection.save()

        self.assertNotEqual(before, _pool_key(self.connection, True))

    def test_pool_key_is_stable_for_same_settings(self):
        self.assertEqual(_pool_key(self.connection, True), _pool_key(self.connection, True))
