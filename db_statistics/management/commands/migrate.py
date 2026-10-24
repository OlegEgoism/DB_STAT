"""migrate, который переводит установку, созданную до миграций, на историю миграций db_statistics.

До появления миграций таблицы создавал `migrate --run-syncdb`, и в django_migrations нет записи
о 0001_initial. Django проверяет согласованность истории до любых действий команды, поэтому обычный
`migrate` (и `migrate --fake-initial`) на такой базе падает с InconsistentMigrationHistory:
admin.0001_initial уже применена, а она зависит от AUTH_USER_MODEL, то есть от db_statistics.0001_initial.

Поэтому перед миграцией здесь 0001_initial отмечается применённой, но только если все её таблицы уже
есть в базе (та же проверка, что делает --fake-initial). На пустой базе и на частично созданной схеме
запись не добавляется: миграция выполняется обычным образом или падает так же, как и раньше.
"""

from django.core.management.commands import migrate as django_migrate
from django.db import connections
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder

APP_LABEL = "db_statistics"
BASELINE = "0001_initial"


def adopt_legacy_baseline(connection):
    """Отмечает 0001_initial применённой, если таблицы установки уже созданы. Возвращает True, если отметила."""
    recorder = MigrationRecorder(connection)
    if (APP_LABEL, BASELINE) in recorder.applied_migrations():
        return False
    executor = MigrationExecutor(connection)
    migration = executor.loader.get_migration(APP_LABEL, BASELINE)
    applied, _state = executor.detect_soft_applied(None, migration)
    if applied:
        recorder.record_applied(APP_LABEL, BASELINE)
    return applied


class Command(django_migrate.Command):
    help = django_migrate.Command.help + " Для установок, созданных до миграций, сначала отмечает 0001_initial db_statistics, если её таблицы уже есть."

    def handle(self, *args, **options):
        if adopt_legacy_baseline(connections[options["database"]]) and options["verbosity"] >= 1:
            self.stdout.write(f"Установка создана до миграций: {APP_LABEL} {BASELINE} отмечена применённой (таблицы уже существуют).")
        return super().handle(*args, **options)
