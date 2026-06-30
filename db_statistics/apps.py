from django.apps import AppConfig


class DbStatisticsConfig(AppConfig):
    name = 'db_statistics'
    verbose_name = 'Информация о базе данных'

    def ready(self):
        from db_statistics.segment_health_worker import start_segment_health_worker

        start_segment_health_worker()
