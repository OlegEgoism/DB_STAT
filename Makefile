.DEFAULT_GOAL := help

PYTHON ?= python
MANAGE := $(PYTHON) manage.py

IMAGE_NAME ?= db-stat
CONTAINER_NAME ?= db-stat
VOLUME_NAME ?= db-stat-data
PORT ?= 8000
SQLITE_NAME ?= db.sqlite3

.PHONY: help install migrations migrate run shell admin \
        lint lint-fix format hooks hooks-run collectstatic \
        docker-build docker-run docker-stop clean reset-db

help: ## Показать список доступных команд
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Установить зависимости из requirements.txt
	pip install -r requirements.txt

migrations: ## Сгенерировать миграции по изменениям моделей
	$(MANAGE) makemigrations

migrate: ## Применить миграции к базе данных
	$(MANAGE) migrate

run: ## Запустить сервер разработки
	$(MANAGE) runserver

shell: ## Открыть интерактивную Django-оболочку
	$(MANAGE) shell

admin: ## Создать первого администратора (см. INITIAL_ADMIN_* в .env)
	$(MANAGE) ensure_initial_admin

lint: ## Проверить код без исправлений
	$(PYTHON) -m ruff check .

lint-fix: ## Проверить код и исправить автоматически исправимое
	$(PYTHON) -m ruff check . --fix

format: ## Отформатировать код
	$(PYTHON) -m ruff format .

hooks: ## Установить Git pre-commit hook для автоматического запуска Ruff
	$(PYTHON) -m pre_commit install

hooks-run: ## Запустить все pre-commit проверки вручную для всего проекта
	$(PYTHON) -m pre_commit run --all-files

collectstatic: ## Собрать статику (как при сборке Docker-образа)
	$(MANAGE) collectstatic --noinput

docker-build: ## Собрать Docker-образ
	docker build -t $(IMAGE_NAME) .

docker-run: ## Запустить контейнер (порт 8000, том db-stat-data для SQLite)
	docker run --name $(CONTAINER_NAME) --rm -p $(PORT):8000 -v $(VOLUME_NAME):/app/data $(IMAGE_NAME)

docker-stop: ## Остановить запущенный контейнер
	docker stop $(CONTAINER_NAME)

clean: ## Удалить кэши и локально собранную статику
	rm -rf staticfiles .ruff_cache
	find . -type d -name "__pycache__" -not -path "./.venv/*" -exec rm -rf {} +

reset-db: ## ОПАСНО: удалить SQLite БД и все миграции db_statistics (кроме __init__.py)
	@echo "Будут удалены: $(SQLITE_NAME) (+ -shm/-wal) и файлы миграций db_statistics, кроме __init__.py."
	@read -p "Продолжить? [y/N] " confirm; \
	if [ "$$confirm" = "y" ] || [ "$$confirm" = "Y" ]; then \
		rm -f $(SQLITE_NAME) $(SQLITE_NAME)-shm $(SQLITE_NAME)-wal; \
		find db_statistics/migrations -type f -name "*.py" ! -name "__init__.py" -delete; \
		echo "Готово. Дальше: make migrations && make migrate"; \
	else \
		echo "Отменено."; \
	fi
