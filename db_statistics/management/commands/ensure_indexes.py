from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Создаёт индексы из Meta.indexes моделей db_statistics, которых ещё нет в базе (для уже существующих таблиц)"

    def handle(self, *args, **options):
        # --run-syncdb создаёт индексы только для новых таблиц. Для таблиц, которые уже есть
        # в установке, новые индексы добавляет эта команда. Уже существующие индексы не трогаются,
        # поэтому команда безопасна для повторного запуска (её вызывает docker-entrypoint.sh).
        created = []
        with connection.cursor() as cursor:
            for model in apps.get_app_config("db_statistics").get_models():
                if not model._meta.indexes:
                    continue
                table = model._meta.db_table
                existing = {name for name, info in connection.introspection.get_constraints(cursor, table).items() if info["index"]}
                missing = [index for index in model._meta.indexes if index.name not in existing]
                if not missing:
                    continue
                with connection.schema_editor() as editor:
                    for index in missing:
                        editor.add_index(model, index)
                        created.append(index.name)
        if connection.vendor == "sqlite":
            with connection.cursor() as cursor:
                # Обновляет статистику планировщика SQLite по новым индексам.
                cursor.execute("PRAGMA optimize")
        if created:
            self.stdout.write(self.style.SUCCESS(f"Создано индексов: {len(created)}: {', '.join(created)}"))
        else:
            self.stdout.write("Все индексы уже есть")
