import json
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from db_statistics.view_helpers import _list_query_params, _read_json_body


class ReadJsonBodyTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_returns_dictionary_payload(self):
        request = self.factory.post("/", data=json.dumps({"page": 2}), content_type="application/json")
        self.assertEqual(_read_json_body(request), {"page": 2})

    def test_rejects_valid_non_object_json(self):
        request = self.factory.post("/", data="[]", content_type="application/json")
        self.assertEqual(_read_json_body(request), {})


class ListQueryParamsTests(SimpleTestCase):
    @patch("db_statistics.view_helpers._pagination_page_sizes", return_value=[10, 20])
    def test_invalid_page_and_non_string_search_use_safe_values(self, _page_sizes):
        values = _list_query_params({"page": "not-a-number", "page_size": "invalid", "search": 42}, {"name": "name"}, "name")

        self.assertEqual(values, (1, 10, 0, "42", "name", "DESC"))
