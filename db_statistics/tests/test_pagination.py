from django.test import TestCase

from db_statistics.views.pagination import _list_query_params

SORT_COLUMNS = {"name": "role_info.rolname", "size_bytes": "size_bytes"}


class ListQueryParamsTests(TestCase):
    def test_unknown_sort_key_falls_back_to_default_column(self):
        _page, _size, _offset, _search, sort_column, _direction = _list_query_params({"sort": "name; DROP TABLE x"}, SORT_COLUMNS, "size_bytes")

        self.assertEqual(sort_column, "size_bytes")

    def test_sort_column_comes_only_from_whitelist(self):
        _page, _size, _offset, _search, sort_column, _direction = _list_query_params({"sort": "name"}, SORT_COLUMNS, "size_bytes")

        self.assertEqual(sort_column, "role_info.rolname")

    def test_direction_is_asc_only_when_requested(self):
        self.assertEqual(_list_query_params({"direction": "asc"}, SORT_COLUMNS, "size_bytes")[5], "ASC")
        self.assertEqual(_list_query_params({"direction": "anything"}, SORT_COLUMNS, "size_bytes")[5], "DESC")

    def test_page_is_clamped_and_offset_derived_from_it(self):
        page, page_size, offset, *_rest = _list_query_params({"page": "-4", "page_size": "20"}, SORT_COLUMNS, "size_bytes")

        self.assertEqual(page, 1)
        self.assertEqual(page_size, 20)
        self.assertEqual(offset, 0)

    def test_page_size_outside_allowed_options_uses_default(self):
        _page, page_size, *_rest = _list_query_params({"page_size": "7"}, SORT_COLUMNS, "size_bytes")

        self.assertEqual(page_size, 10)
