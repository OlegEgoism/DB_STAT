import logging

from django.conf import settings
from django.test import SimpleTestCase

from db_statistics.logging_filters import ServiceUnavailableWarningFilter


def _response_record(level, message, args, status_code):
    """Запись, похожая на ту, что Django пишет через log_response для ответов 4xx/5xx."""
    record = logging.LogRecord(name="django.request", level=level, pathname=__file__, lineno=1, msg=message, args=args, exc_info=None)
    record.status_code = status_code
    return record


class ServiceUnavailableWarningFilterTests(SimpleTestCase):
    def setUp(self):
        self.filter = ServiceUnavailableWarningFilter()

    def test_503_response_is_lowered_to_warning_and_keeps_path(self):
        record = _response_record(logging.ERROR, "%s: %s", ("Service Unavailable", "/reports/database.pdf"), 503)

        self.assertTrue(self.filter.filter(record))

        self.assertEqual(record.levelno, logging.WARNING)
        self.assertEqual(record.levelname, "WARNING")
        self.assertEqual(record.getMessage(), "Service Unavailable: /reports/database.pdf")

    def test_503_detected_by_message_when_status_attribute_missing(self):
        record = logging.LogRecord(name="django.request", level=logging.ERROR, pathname=__file__, lineno=1, msg="%s: %s", args=("Service Unavailable", "/api/locks/"), exc_info=None)

        self.filter.filter(record)

        self.assertEqual(record.levelno, logging.WARNING)

    def test_500_response_stays_error(self):
        record = _response_record(logging.ERROR, "%s: %s", ("Internal Server Error", "/api/sessions/"), 500)

        self.assertTrue(self.filter.filter(record))

        self.assertEqual(record.levelno, logging.ERROR)
        self.assertEqual(record.levelname, "ERROR")

    def test_other_5xx_stays_error(self):
        record = _response_record(logging.ERROR, "%s: %s", ("Bad Gateway", "/api/x/"), 502)

        self.filter.filter(record)

        self.assertEqual(record.levelno, logging.ERROR)

    def test_non_error_records_are_not_touched(self):
        record = _response_record(logging.WARNING, "%s: %s", ("Not Found", "/missing/"), 404)

        self.filter.filter(record)

        self.assertEqual(record.levelno, logging.WARNING)

    def test_settings_attach_filter_to_django_request_logger(self):
        request_logger = settings.LOGGING["loggers"]["django.request"]

        self.assertIn("service_unavailable_as_warning", request_logger["filters"])
        self.assertEqual(settings.LOGGING["filters"]["service_unavailable_as_warning"]["()"], "db_statistics.logging_filters.ServiceUnavailableWarningFilter")
