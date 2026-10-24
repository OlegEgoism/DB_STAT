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


def add_missing_columns(connection):
    """Добавляет колонки, которых нет в таблицах старой установки. Возвращает список «таблица.колонка».

    Колонки появлялись в моделях по ходу развития (например, failed_login_attempts, language), а
    --run-syncdb их в существующие таблицы не добавлял. Поле с default или null=True добавляется без
    потери данных: редактор схемы Django подставляет значение по умолчанию для существующих строк.
    """
    from django.apps import apps

    missing = []
    with connection.cursor() as cursor:
        for model in apps.get_app_config(APP_LABEL).get_models():
            existing = {column.name for column in connection.introspection.get_table_description(cursor, model._meta.db_table)}
            for field in model._meta.local_concrete_fields:
                if field.column not in existing:
                    missing.append((model, field))
    if missing:
        with connection.schema_editor() as editor:
            for model, field in missing:
                editor.add_field(model, field)
    return [f"{model._meta.db_table}.{field.column}" for model, field in missing]


def adopt_legacy_baseline(connection):
    """Отмечает 0001_initial применённой, если таблицы установки уже созданы. Возвращает True, если отметила.

    Вместе с отметкой сверяет колонки моделей с таблицами: установка, созданная раньше, должна
    получить недостающие колонки до того, как приложение начнёт их использовать.
    """
    recorder = MigrationRecorder(connection)
    if (APP_LABEL, BASELINE) in recorder.applied_migrations():
        return False
    executor = MigrationExecutor(connection)
    migration = executor.loader.get_migration(APP_LABEL, BASELINE)
    applied, _state = executor.detect_soft_applied(None, migration)
    if applied:
        add_missing_columns(connection)
        recorder.record_applied(APP_LABEL, BASELINE)
    return applied


class Command(django_migrate.Command):
    help = django_migrate.Command.help + " Для установок, созданных до миграций, сначала отмечает 0001_initial db_statistics и добавляет недостающие колонки."

    def handle(self, *args, **options):
        connection = connections[options["database"]]
        if adopt_legacy_baseline(connection) and options["verbosity"] >= 1:
            self.stdout.write(f"Установка создана до миграций: {APP_LABEL} {BASELINE} отмечена применённой (таблицы уже существуют).")
        return super().handle(*args, **options)
