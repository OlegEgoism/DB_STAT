from django.conf import settings
from django.test import RequestFactory, TestCase

from db_statistics.models import DBConnection, DBFavorite, DBUser
from db_statistics.views.auth import _current_db_user
from db_statistics.views.pagination import _search_and_favorites_filter


class CurrentUserPerRequestTests(TestCase):
    def setUp(self):
        self.user = DBUser.objects.create_user(login="cache_user", email="cache_user@example.com", password="pw-cache-12345")

    def _request(self):
        request = RequestFactory().post("/")
        request.session = {settings.SESSION_USER_ID_KEY: self.user.pk}
        return request

    def test_user_is_loaded_once_per_request(self):
        request = self._request()

        with self.assertNumQueries(1):
            first = _current_db_user(request)
            second = _current_db_user(request)

        self.assertEqual(first, self.user)
        self.assertEqual(second, self.user)

    def test_each_request_gets_its_own_lookup(self):
        _current_db_user(self._request())

        with self.assertNumQueries(1):
            _current_db_user(self._request())


class SearchAndFavoritesFilterTests(TestCase):
    def setUp(self):
        self.user = DBUser.objects.create_user(login="filter_user", email="filter_user@example.com", password="pw-filter-12345")
        self.connection = DBConnection.objects.create(name="filter", host="db.internal", port=5432, database="app", username="reader", password="pw")
        self.request = RequestFactory().post("/")
        self.request.session = {settings.SESSION_USER_ID_KEY: self.user.pk}

    def _filter(self, payload, search=""):
        return _search_and_favorites_filter(self.request, payload, self.connection, search, ("t.relname",), "table", ("t.nspname", "t.relname"))

    def test_search_adds_ilike_condition_and_params(self):
        where_sql, params = self._filter({}, search="orders")

        self.assertIn("ILIKE", where_sql)
        self.assertEqual(params, ["%orders%"])

    def test_no_search_and_no_favorites_filter_gives_no_condition(self):
        where_sql, params = self._filter({})

        self.assertNotIn("ILIKE", where_sql)
        self.assertNotIn("FALSE", where_sql)
        self.assertEqual(params, [])

    def test_favorites_only_without_favorites_matches_nothing(self):
        where_sql, _params = self._filter({"favorites_only": True})

        self.assertIn("AND FALSE", where_sql)

    def test_favorites_only_builds_condition_from_saved_keys(self):
        DBFavorite.objects.create(user=self.user, connection=self.connection, object_type="table", object_key="app\x1forders")

        where_sql, params = self._filter({"favorites_only": True})

        self.assertIn("t.nspname = %s AND t.relname = %s", where_sql)
        self.assertEqual(params, ["app", "orders"])

    def test_search_and_favorites_params_keep_order(self):
        DBFavorite.objects.create(user=self.user, connection=self.connection, object_type="table", object_key="app\x1forders")

        _where_sql, params = self._filter({"favorites_only": True}, search="ord")

        self.assertEqual(params, ["%ord%", "app", "orders"])
