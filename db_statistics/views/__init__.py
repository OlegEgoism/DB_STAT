"""db/urls.py resolves handler404 as the string "db_statistics.views.page_not_found",
which Django imports lazily as this package's attribute — every other view is
imported directly from its own submodule (see db_statistics/urls.py) and does
not need to be re-exported here.
"""

from db_statistics.views.additional import page_not_found

__all__ = ["page_not_found"]
