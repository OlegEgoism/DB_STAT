"""runserver, который перед стартом возвращает прерванные фоновые задачи в очередь.

Без этого после аварийной остановки dev-сервера задачи VACUUM/ANALYZE и PDF-отчёты
оставались бы в статусе «Выполняется», пока кто-нибудь не запустит
recover_maintenance_jobs вручную.

Наследуемся от runserver из django.contrib.staticfiles, а не от голого
django.core.management.commands.runserver: тот класс сам наследуется от core, а
staticfiles-вариант добавляет раздачу статики из STATICFILES_DIRS. Голый
наследник заменил бы его и тихо сломал бы статику в режиме разработки. Чтобы
эта команда вообще выбиралась Django, db_statistics стоит перед staticfiles в
INSTALLED_APPS (см. db/settings.py).
"""

import logging
import os

from django.contrib.staticfiles.management.commands.runserver import Command as StaticfilesRunserverCommand
from django.core.management import call_command

logger = logging.getLogger(__name__)


def should_recover_on_start(environ, use_reloader):
    """Нужно ли восстанавливать задачи в этом процессе перед стартом сервера.

    С автоперезагрузкой (поведение по умолчанию) процесс-родитель только следит
    за файлами, а запросы обслуживает дочерний процесс, в котором Django
    выставляет RUN_MAIN=true. Восстановление выполняется только там, иначе
    родитель и потомок сбрасывали бы одни и те же задачи. Без автоперезагрузки
    (--noreload) единственный процесс сразу обслуживает запросы.
    """
    return environ.get("RUN_MAIN") == "true" or not use_reloader


def recover_jobs_on_start():
    """Запускает восстановление задач. Ошибка не должна мешать запуску сервера."""
    try:
        call_command("recover_maintenance_jobs")
    except Exception:
        logger.warning("Не удалось восстановить прерванные фоновые задачи при запуске runserver", exc_info=True)


class Command(StaticfilesRunserverCommand):
    help = "Запускает сервер разработки; сначала возвращает прерванные фоновые задачи в очередь"

    def handle(self, *args, **options):
        if should_recover_on_start(os.environ, options.get("use_reloader", True)):
            recover_jobs_on_start()
        super().handle(*args, **options)
