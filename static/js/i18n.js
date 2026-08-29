(function () {
    'use strict';

    const language = String(window.DB_STAT_LANGUAGE || 'ru').toLowerCase();
    const translations = {
        'Авторизация': 'Sign in', 'Авторизация пользователя': 'User sign in', 'Войти': 'Sign in',
        'Время сессии (часы)': 'Session duration (hours)', 'Ошибка 404': 'Error 404',
        'Страница не найдена': 'Page not found', 'Запрошенная страница не существует или была удалена.': 'The requested page does not exist or has been removed.',
        'Запрошенный адрес': 'Requested address', 'На главную': 'Home', 'Главная': 'Home', 'Главная страница': 'Home page',
        'Инфраструктура': 'Infrastructure', 'Данные': 'Data', 'Производительность': 'Performance', 'Администрирование': 'Administration', 'Дополнительно': 'Additional',
        'База данных': 'Database', 'Сегменты': 'Segments', 'Схемы': 'Schemas', 'Таблицы': 'Tables', 'Представления': 'Views', 'Функции': 'Functions',
        'Временные таблицы': 'Temporary tables', 'Распределение': 'Distribution', 'Запросы': 'Queries', 'Активные запросы': 'Active queries',
        'Сессии': 'Sessions', 'Блокировки': 'Locks', 'Транзакции': 'Transactions', 'Память': 'Memory', 'Пользователи': 'Users',
        'Группы': 'Groups', 'Обслуживание': 'Maintenance', 'Аудит': 'Audit', 'Избранные': 'Favorites', 'Избранное': 'Favorites', 'Настройки': 'Settings', 'Видео': 'Video',
        'Настройки сайдбара': 'Interface settings', 'Свернуть сайдбар': 'Collapse sidebar', 'Свернуть/развернуть сайдбар': 'Collapse/expand sidebar',
        'Открыть главную страницу DB STAT': 'Open the DB STAT home page', 'Сессии и подключения': 'Sessions and connections',
        'До завершения сессии': 'Session time remaining',
        'Язык интерфейса': 'Interface language', 'Русский (RU)': 'Russian (RU)',
        'Тема оформления': 'Appearance theme', 'Белая': 'White', 'Тёмная': 'Dark', 'Светло-серая': 'Light gray',
        'Светло-синяя': 'Light blue', 'Светло-коричневая': 'Light brown', 'Светло-зелёная': 'Light green',
        'Спокойная прохладная палитра': 'Calm cool palette', 'Тёплая естественная палитра': 'Warm natural palette', 'Свежая природная палитра': 'Fresh natural palette',
        'Стандартная светлая тема': 'Standard light theme', 'Комфортная работа при слабом освещении': 'Comfortable in low light', 'Мягкий нейтральный фон': 'Soft neutral background',
        'Выберите цветовую схему интерфейса. Тема применяется сразу и сохраняется для следующих посещений.': 'Choose the interface color scheme. The theme is applied immediately and saved for future visits.',
        'Язык применяется ко всему интерфейсу и сохраняется для следующих посещений.': 'The language applies to the entire interface and is saved for future visits.',
        'Выберите вкладки, которые нужно показывать в боковом меню. Перетаскивайте вкладки внутри блоков, а сами блоки — за заголовок, чтобы настроить последовательность их отображения.': 'Select the tabs to show in the sidebar. Drag tabs within sections, and drag section headers to change the section order.',
        'Выбрать все': 'Select all', 'Сохранить': 'Save', 'Уведомление': 'Notification', 'Новое подключение': 'New connection',
        'Подтверждение завершения': 'Confirm termination', 'Подтвердите завершение процесса.': 'Confirm process termination.',
        'Операция может прервать выполняющуюся работу пользователя.': 'This action may interrupt the user’s current work.', 'Закрыть': 'Close',
        'Перетащить вкладку': 'Drag tab', 'Перетащить блок': 'Drag section',
        'Название': 'Name', 'Хост': 'Host', 'Порт': 'Port', 'Тип БД': 'Database type', 'Пароль': 'Password', 'Пользователь': 'User',
        'Пользователь БД': 'Database user', 'Владелец': 'Owner', 'Информация о подключении': 'Connection information',
        'Информация о пользователе': 'User information', 'Почта': 'Email', 'Роль': 'Role',
        'Удалить': 'Delete', 'Отмена': 'Cancel', 'Проверить': 'Test', 'Подключиться': 'Connect', 'Редактировать подключение': 'Edit connection',
        'Загрузка подключений...': 'Loading connections...', 'Нет доступных подключений': 'No connections available', 'Выйти': 'Sign out',
        'Описание разделов': 'Section overview', 'Размеры и структура': 'Sizes and structure', 'Состояние и конфигурация': 'Status and configuration',
        'Список схем': 'Schema list', 'Список таблиц': 'Table list', 'Список представлений': 'View list', 'Список функций': 'Function list', 'Перекос данных': 'Data skew',
        'Активные временные таблицы': 'Active temporary tables', 'Долгие запросы': 'Long-running queries',
        'Пользователи и подключения': 'Users and connections', 'Кто кого блокирует': 'Blocking relationships', 'Параметры памяти': 'Memory settings',
        'Список пользователей': 'User list', 'Список групп': 'Group list', 'Очистка / анализ': 'Vacuum / analyze', 'Действия пользователя': 'User actions',
        'Избранные объекты': 'Favorite objects', 'Сохранённые объекты подключения': 'Saved objects for the connection',
        'Нет данных': 'No data', 'Обновить': 'Refresh', 'Поиск': 'Search', 'Все': 'All', 'Да': 'Yes', 'Нет': 'No',
        'Параметр': 'Parameter', 'Значение': 'Value', 'Статус': 'Status', 'Состояние': 'State', 'Размер': 'Size', 'Всего': 'Total', 'Все записи': 'All records', 'Только избранные': 'Favorites only',
        'Схема': 'Schema', 'Таблица': 'Table', 'Индексы': 'Indexes', 'Строк': 'Rows', 'Длительность': 'Duration', 'Тип объекта': 'Object type', 'Объект': 'Object', 'Идентификатор объекта': 'Object identifier',
        'Дата': 'Date', 'Действие': 'Action', 'Действия': 'Actions', 'Информация': 'Information', 'События аудита не найдены': 'No audit events found',
        'Страница 1 из 1': 'Page 1 of 1', 'Страница 1': 'Page 1', 'Свернуть график': 'Collapse chart',
        'Развернуть график': 'Expand chart', 'Выберите таблицу': 'Select a table', 'Таблицы не найдены': 'No tables found',
        'Показать список таблиц': 'Show table list', 'Таблицы базы данных': 'Database tables',
        'Пользователи не найдены': 'No users found', 'Группы не найдены': 'No groups found', 'Схемы не найдены': 'No schemas found',
        'Представления не найдены': 'No views found', 'Функции не найдены': 'No functions found', 'Временные таблицы не найдены': 'No temporary tables found',
        'Транзакции не найдены': 'No transactions found', 'Блокировки не найдены': 'No locks found',
        'Недоступно': 'Unavailable', 'Обновление...': 'Updating...',
        'Основные данные БД': 'Database basics', 'Активность БД': 'Database activity', 'Коммиты / Роллбеки': 'Commits / rollbacks',
        'Показатель': 'Metric', 'Слоты подключений': 'Connection slots', 'Использование': 'Usage', 'Пользователи и группы': 'Users and groups',
        'Тип': 'Type', 'Количество': 'Count', 'Установленные расширения': 'Installed extensions', 'Расширение': 'Extension', 'Версия': 'Version',
        'Комментарий': 'Comment', 'Состояние сегментов': 'Segment health', 'Информация о сегментах недоступна': 'Segment information is unavailable',
        'Детальная информация': 'Details', 'Сегмент': 'Segment', 'Режим': 'Mode', 'Распределение данных по схемам': 'Data distribution by schema',
        'Количество таблиц': 'Table count', 'Назад': 'Previous', 'Далее': 'Next', 'Вперёд': 'Next',
        'Распределение данных по таблицам': 'Data distribution by table', 'Количество индексов': 'Index count', 'Все типы': 'All types',
        'Обычное': 'Regular', 'Материализованное': 'Materialized', 'Материализованные / обычные': 'Materialized / regular',
        'Общий размер материализованных': 'Total materialized size', 'Представление': 'View', 'Функция': 'Function', 'Возвращаемый тип': 'Return type', 'Аргументы': 'Arguments', 'Выбор таблицы для анализа распределения': 'Select a table for distribution analysis',
        'Распределение данных': 'Data distribution', 'Сегментов': 'Segments', 'Коэффициент перекоса': 'Skew ratio', 'Всего строк': 'Total rows',
        'Распределение строк по сегментам': 'Row distribution by segment', 'Количество строк': 'Row count', 'Доля': 'Share',
        'Распределение данных по временным таблицам': 'Data distribution by temporary table', 'Обновление': 'Refresh', 'Вручную': 'Manual',
        'Активные сессии пользователей и подключения': 'Active user sessions and connections', 'Активные': 'Active', 'Простаивают': 'Idle',
        'Простой в транзакции': 'Idle in transaction', 'Клиенты': 'Clients', 'База': 'Database', 'Приложение': 'Application', 'Клиент': 'Client',
        'Ожидание': 'Wait', 'Длит. сессии': 'Session duration', 'Заблок. пользователь': 'Blocked user', 'Блок. пользователь': 'Blocking user',
        'Заблок. PID': 'Blocked PID', 'Длит. блокировки': 'Block duration', 'Заблокированный SQL': 'Blocked SQL', 'Блок. PID': 'Blocking PID',
        'Длит. блокирующего': 'Blocker duration', 'Блокирующий SQL': 'Blocking SQL', 'Простаивающие в транзакции': 'Idle in transaction',
        'Длит. транзакции': 'Transaction duration', 'Длит. простоя': 'Idle duration', 'Детализация размеров': 'Size breakdown',
        'Общий размер БД': 'Total database size', 'Метрика': 'Metric', 'Использование памяти': 'Memory usage',
        'Суперпользователи / обычные': 'Superusers / regular users', 'Создают БД / без права': 'Can create databases / cannot',
        'Репликация / без права': 'Replication / no permission', 'Суперпользователь': 'Superuser', 'Создаёт БД': 'Creates databases',
        'Создаёт роли': 'Creates roles', 'Наследование': 'Inheritance', 'Репликация': 'Replication', 'Лимит подключений': 'Connection limit',
        'Действует до': 'Valid until', 'Группы по количеству участников': 'Groups by member count', 'Привилегированные группы': 'Privileged groups',
        'Привилегированные / обычные': 'Privileged / regular', 'Группа': 'Group', 'Участников': 'Members',
        'Статистика обслуживания': 'Maintenance statistics', 'Живые/мёртвые строки': 'Live/dead rows', 'Тепловая карта статуса обслуживания': 'Maintenance status heatmap',
        'Статус рассчитывается по текущей доле мёртвых строк, а не по дате последнего VACUUM. После новых UPDATE/DELETE таблица может снова потребовать очистки.': 'Status is calculated from the current dead-row ratio, not the last VACUUM date. New UPDATE/DELETE activity may make the table require cleanup again.',
        'Живых строк': 'Live rows', 'Мёртвых строк': 'Dead rows', 'Доля мёртвых строк': 'Dead-row share',
        'Последняя очистка (VACUUM)': 'Last VACUUM', 'Последний анализ (ANALYZE)': 'Last ANALYZE', 'Аудит действий': 'Action audit',
        'Выполняется': 'Running', 'VACUUM таблицы': 'Table VACUUM', 'VACUUM FULL таблицы': 'Table VACUUM FULL',
        'ANALYZE таблицы': 'Table ANALYZE', 'EXPLAIN ANALYZE таблицы': 'Table EXPLAIN ANALYZE',
        'Результат обслуживания': 'Maintenance result', 'Операция': 'Operation', 'Статус': 'Status',
        'Успешно завершено': 'Completed successfully', 'Ошибка': 'Error', 'План выполнения': 'Execution plan',
        'Статистика после выполнения': 'Post-operation statistics', 'Живых строк, оценка': 'Live rows, estimate',
        'Мёртвых строк, оценка': 'Dead rows, estimate',
        'Значения получены из pg_stat_user_tables после операции и являются оценкой статистики, а не физическим подсчётом версий строк.': 'Values come from pg_stat_user_tables after the operation and are statistical estimates, not a physical count of row versions.',
        'Операция выполняется': 'Operation in progress', 'Операция успешно завершена': 'Operation completed successfully',
        'Задача обслуживания не найдена': 'Maintenance job not found', 'Не выбрана таблица для обслуживания': 'No table selected for maintenance',
        'Неизвестная операция обслуживания': 'Unknown maintenance operation', 'Выберите подключение': 'Select a connection',
        'Выберите сохранённое подключение для загрузки статистики обслуживания': 'Select a saved connection to load maintenance statistics',
        'Дата и время': 'Date and time', 'Загрузка аудита...': 'Loading audit...',
        'Активность БД по транзакциям': 'Database transaction activity',
        'Использование слотов подключений': 'Connection slot usage',
        'Текущие подключения': 'Current connections', 'Максимум подключений': 'Maximum connections',
        'Коммитов': 'Commits', 'Роллбеков': 'Rollbacks', 'Всего транзакций': 'Total transactions',
        'Откат (Rollback), %': 'Rollbacks, %', 'Доля попаданий в кэш': 'Cache hit ratio',
        'Возраст транзакций (XID)': 'Transaction age (XID)', 'Время работы БД': 'Database uptime',
        'Запущена': 'Started at', 'Версия сервера': 'Server version', 'Кодировка сервера': 'Server encoding',
        'Часовой пояс': 'Time zone', 'Резерв подключений суперпользователя': 'Reserved superuser connections',
        'Таймаут запроса': 'Statement timeout', 'Таймаут ожидания блокировки': 'Lock timeout',
        'Таймаут простоя в транзакции': 'Idle-in-transaction timeout',
        'Уровень изоляции по умолчанию': 'Default isolation level', 'Формат даты': 'Date format',
        'Размер индексов': 'Index size', 'Размер БД без индексов': 'Database size without indexes',
        'Размер временных таблиц': 'Temporary table size', 'Размер материализованных представлений': 'Materialized view size',
        'Память на один запрос': 'Memory per statement', 'Максимальная память на запрос': 'Maximum memory per statement',
        'Лимит виртуальной памяти сегмента': 'Segment virtual memory limit',
        'Нет данных об основных данных БД': 'No database basics available', 'Нет данных об активности БД': 'No database activity data available',
        'Нет данных о подключении': 'No connection data available', 'Нет данных о размерах БД': 'No database size data available',
        'Нет данных о параметрах памяти': 'No memory settings available', 'Нет данных о пользователях и группах': 'No user or group data available',
        'Нет установленных расширений': 'No extensions installed', 'Нет данных о слотах подключений': 'No connection slot data available',
        'Загрузка размеров БД...': 'Loading database overview...', 'Не удалось получить размеры БД': 'Failed to load database overview',
        'Выберите сохранённое подключение для загрузки размеров БД': 'Select a saved connection to load the database overview',
        'DB STAT — веб-панель для оперативного мониторинга и диагностики баз данных PostgreSQL, Greenplum и Greengage. Она собирает ключевые технические показатели выбранного подключения и представляет их в едином, понятном интерфейсе.': 'DB STAT is a web dashboard for real-time monitoring and diagnostics of PostgreSQL, Greenplum, and Greengage databases. It collects key technical metrics for the selected connection and presents them in one clear interface.',
        'На панели можно оценить размеры баз, схем, таблиц и индексов, проверить активность пользователей и сессий, найти длительные или проблемные запросы, а также увидеть блокировки и простаивающие транзакции.': 'Use the dashboard to review database, schema, table, and index sizes; inspect user and session activity; find long-running or problematic queries; and identify locks and idle transactions.',
        'Для Greenplum и Greengage доступны сведения о состоянии сегментов и распределении строк, помогающие обнаружить перекос данных. Раздел обслуживания показывает статистику VACUUM и ANALYZE, количество живых и мёртвых строк и время последних операций.': 'For Greenplum and Greengage, segment health and row distribution data help reveal skew. The maintenance section shows VACUUM and ANALYZE statistics, live and dead row counts, and the latest operation times.',
        'DB STAT подходит для ежедневного контроля, первичной диагностики снижения производительности и административной проверки. Переключайтесь между сохранёнными подключениями, сравнивайте показатели и быстрее находите участки, которым требуется внимание.': 'DB STAT is designed for daily checks, initial performance diagnostics, and administrative review. Switch between saved connections, compare metrics, and quickly find areas that need attention.',
        'Сохранённые схемы, таблицы, представления, функции, пользователи и группы для быстрого доступа.': 'Saved schemas, tables, views, functions, users, and groups for quick access.'
    };

    Object.assign(translations, {
        'Активна': 'Active', 'Отключена': 'Disabled', 'Простаивает': 'Idle', 'Простой в отменённой транзакции': 'Idle in aborted transaction',
        'Все пользователи': 'All users', 'Все сегменты': 'All segments', 'Остальные': 'Other', 'Процент': 'Percent',
        '10 сек': '10 sec', '30 сек': '30 sec', '5 сек': '5 sec', '60 сек': '60 sec',
        'Активные запросы не найдены': 'No active queries found', 'Активные сессии и подключения не найдены': 'No active sessions or connections found',
        'Завершить': 'Terminate',
        'Завершение активного запроса': 'Active query termination', 'Завершение активной сессии': 'Active session termination',
        'Указан некорректный PID запроса': 'Invalid query PID', 'Указан некорректный PID сессии': 'Invalid session PID',
        'Не удалось завершить активный запрос': 'Failed to terminate the active query',
        'Не удалось завершить сессию пользователя': 'Failed to terminate the user session',
        'Детализация размеров не найдена': 'No size breakdown found', 'Использование памяти не найдено': 'No memory usage data found',
        'Параметры памяти не найдены': 'No memory settings found', 'Статистика обслуживания не найдена': 'No maintenance statistics found',
        'Нет данных о распределении строк': 'No row distribution data', 'Нет данных о распределении данных по схемам': 'No schema distribution data',
        'Нет данных о распределении данных по таблицам': 'No table distribution data',
        'Нет данных о распределении данных по временным таблицам': 'No temporary-table distribution data',
        'Анимация разборки и сборки жёсткого диска': 'Hard drive disassembly and assembly animation',
        'Обновить аудит': 'Refresh audit', 'Фильтр действий аудита': 'Audit action filter',
        'Развернуть раздел': 'Expand section', 'Свернуть раздел': 'Collapse section', 'Развернуть сайдбар': 'Expand sidebar',
        'Например: Production GP': 'For example: Production GP', 'Начните вводить схему или название таблицы': 'Start typing a schema or table name',
        'Поиск по группе...': 'Search by group...', 'Поиск по пользователю...': 'Search by user...',
        'Поиск по схеме...': 'Search by schema...', 'Поиск по схеме или таблице...': 'Search by schema or table...',
        'Поиск по схеме или представлению...': 'Search by schema or view...', 'Поиск по названию функции...': 'Search by function name...',
        'Поиск по данным функции...': 'Search function data...',
        'Детализация размеров базы данных': 'Database size breakdown',
        'Обычные и материализованные представления': 'Regular and materialized views',
        'Пользователи с правом репликации': 'Users with replication permission',
        'Пользователи с правом создания БД': 'Users with database creation permission',
        'Суперпользователи среди пользователей': 'Superusers among users',
        'Обычные пользователи': 'Regular users', 'Суперпользователи': 'Superusers', 'Могут создавать БД': 'Can create databases',
        'Не могут создавать БД': 'Cannot create databases', 'Могут выполнять репликацию': 'Can replicate', 'Без права репликации': 'No replication permission',
        'Обычные группы': 'Regular groups', 'Все действия': 'All actions', 'Логин': 'Login',
        'Вход': 'Sign in', 'Выход': 'Sign out', 'Создание подключения': 'Connection created', 'Изменение подключения': 'Connection updated',
        'Удаление подключения': 'Connection deleted', 'Проверка подключения': 'Connection tested', 'Проверка нового подключения': 'New connection test',
        'Настройки сайдбара пользователя': 'User sidebar settings',
        'Материализованное представление': 'Materialized view', 'Партиционированная таблица': 'Partitioned table',
        'Добавить в избранное': 'Add to favorites', 'Удалить из избранного': 'Remove from favorites',
        'Добавление в избранные объекты': 'Add to favorites', 'Удаление из избранных объектов': 'Remove from favorites',
        'Объект добавлен в избранные объекты': 'Object added to favorites', 'Объект удалён из избранных объектов': 'Object removed from favorites',
        'Не удалось загрузить избранное': 'Failed to load favorites', 'Некорректный объект избранного': 'Invalid favorite object',
        'Выберите подключение для просмотра избранных объектов': 'Select a connection to view favorite objects',
        'Для выбранного подключения нет избранных объектов': 'There are no favorite objects for the selected connection',
        'Без лимита': 'Unlimited', 'Бессрочно': 'Never expires', 'Никогда': 'Never',
        'Администратор': 'Administrator', 'Аналитик': 'Analyst', 'Б': 'B', 'КБ': 'KB', 'МБ': 'MB', 'ГБ': 'GB', 'ТБ': 'TB',
        'Буферы': 'Buffers', 'Защита OOM': 'OOM protection', 'Кэш данных': 'Data cache', 'Лимит запроса': 'Statement limit',
        'Макс. лимит': 'Maximum limit', 'Максимальная память запроса': 'Maximum statement memory', 'Память запроса': 'Statement memory',
        'Память обслуживания': 'Maintenance memory', 'Память операций': 'Operation memory', 'Очистка / создание индекса': 'Vacuum / index creation',
        'Сортировка/Hash': 'Sort/Hash', 'высокий': 'high', 'средний': 'medium', 'норм.': 'normal',
        'Общее количество сегментов': 'Total segments', 'Cегменты работают': 'Segments running', 'Cегменты не работают': 'Segments down',
        'Cинхронизированные сегменты': 'Synchronized segments', 'Основные сегменты': 'Primary segments',
        'Зеркальные сегменты': 'Mirror segments', 'Процент здоровья': 'Health percentage',
        'Здоровье кластера': 'Cluster health', 'Критические проблемы': 'Critical issues',
        'Выбранная таблица не найдена': 'Selected table not found', 'Таблица не выбрана': 'No table selected',
        'Ошибка запроса': 'Request error', 'Ошибка': 'Error', 'Успешно': 'Successful', 'Неизвестный пользователь': 'Unknown user',
        'Неизвестный тип действия': 'Unknown action type', 'Некорректный JSON': 'Invalid JSON', 'Подключение не выбрано': 'No connection selected',
        'Требуется вход в приложение': 'Sign-in required', 'Заполните все обязательные поля': 'Fill in all required fields',
        'Выход из приложения: активный пользователь не найден': 'Signed out: no active user was found',
        'Поддерживаются только языки RU и EN': 'Only RU and EN are supported',
        'Редактировать подключение может только его создатель': 'Only the connection creator can edit it',
        'Удалять подключение может только его создатель': 'Only the connection creator can delete it',
        'Удалять подключения может только Администратор': 'Only an Administrator can delete connections',
        'Создавать подключения может только Администратор': 'Only an Administrator can create connections',
        'Сохранять подключения может только Администратор': 'Only an Administrator can save connections',
        'Проверять новое подключение может только Администратор': 'Only an Administrator can test a new connection',
        'Создавать и редактировать подключения может только Администратор': 'Only an Administrator can create and edit connections',
        'Действие доступно только Администратору': 'This action is available to Administrators only',
        'Эта функция доступна только для подключений типа Greenplum или Greengage': 'This feature is only available for Greenplum or Greengage connections',
        'Некорректные параметры сортировки': 'Invalid sort parameters',
        'Выберите хотя бы одну вкладку для сайдбара': 'Select at least one sidebar tab',
        'Настройки сайдбара сохранены': 'Sidebar settings saved',
        'Тема оформления сохранена': 'Appearance theme saved',
        'Заполните все обязательные поля для проверки': 'Fill in all required fields before testing',
        'Не удалось загрузить список доступных подключений': 'Failed to load available connections',
        'Не удалось загрузить список таблиц': 'Failed to load the table list', 'Не удалось загрузить таблицы': 'Failed to load tables',
        'Не удалось получить активные запросы': 'Failed to load active queries',
        'Не удалось получить активные сессии и подключения': 'Failed to load active sessions and connections',
        'Не удалось получить аудит': 'Failed to load audit events', 'Не удалось получить блокировки': 'Failed to load locks',
        'Не удалось получить временные таблицы': 'Failed to load temporary tables', 'Не удалось получить параметры памяти': 'Failed to load memory settings',
        'Не удалось получить представления': 'Failed to load views', 'Не удалось получить функции': 'Failed to load functions', 'Не удалось получить размеры схем': 'Failed to load schema sizes',
        'Не удалось получить размеры таблиц': 'Failed to load table sizes', 'Не удалось получить распределение': 'Failed to load distribution data',
        'Не удалось получить список групп': 'Failed to load groups', 'Не удалось получить список пользователей': 'Failed to load users',
        'Не удалось получить статистику обслуживания': 'Failed to load maintenance statistics',
        'Не удалось получить транзакции': 'Failed to load transactions', 'Не удалось сохранить настройки сайдбара': 'Failed to save sidebar settings',
        'Не удалось получить обзор БД': 'Failed to load database overview',
        'Не удалось получить информацию о сегментах': 'Failed to load segment information',
        'Выберите сохранённое подключение для загрузки активных сессий и подключений': 'Select a saved connection to load active sessions and connections',
        'Выберите сохранённое подключение для загрузки памяти': 'Select a saved connection to load memory data', 'Выберите сохранённое подключение для загрузки функций': 'Select a saved connection to load functions',
        'Выберите сохранённое подключение для загрузки списка таблиц': 'Select a saved connection to load the table list',
        'Выберите сохранённое подключение для загрузки таблиц': 'Select a saved connection to load tables',
        'Загрузка активных сессий и подключений...': 'Loading active sessions and connections...',
        'Загрузка памяти...': 'Loading memory data...', 'Загрузка функций...': 'Loading functions...', 'Загрузка распределения строк по сегментам...': 'Loading row distribution across segments...',
        'Загрузка таблиц...': 'Loading tables...',
        'Проверьте доступность подключения и повторите попытку.': 'Check the connection and try again.',
        'Сегменты недоступны для выбранного подключения': 'Segments are unavailable for the selected connection',
        'Информация о сегментах недоступна для выбранного подключения.': 'Segment information is unavailable for the selected connection.',
        'Информация о сегментах недоступна: выберите сохранённое подключение Greenplum или Greengage.': 'Segment information is unavailable: select a saved Greenplum or Greengage connection.',
        'Выбранное подключение не похоже на Greenplum/Greengage или у пользователя нет доступа к gp_segment_configuration. Выберите подключение Greenplum/Greengage или проверьте права доступа.': 'The selected connection does not appear to be Greenplum/Greengage, or the user cannot access gp_segment_configuration. Select a Greenplum/Greengage connection or check permissions.',
        'Активные временные таблицы и занимаемый ими объём.': 'Active temporary tables and their storage usage.',
        'Активные запросы с длительностью, SQL и ручным/автообновлением.': 'Active queries with duration, SQL, and manual or automatic refresh.',
        'Активные сессии и подключения пользователей: состояние, длительность, запросы.': 'Active user sessions and connections: state, duration, and queries.',
        'Анализ распределения строк по сегментам и перекоса данных.': 'Analysis of row distribution across segments and data skew.',
        'Группы ролей, привилегии и количество участников.': 'Role groups, privileges, and member counts.',
        'История действий пользователя с фильтром по типу события.': 'User action history filtered by event type.',
        'Кто кого блокирует, длительность блокировок и блокирующие SQL.': 'Blocking relationships, lock duration, and blocking SQL.',
        'Обычные и материализованные представления, их размеры и строки.': 'Regular and materialized views, their sizes, and row counts.', 'Список функций базы данных, возвращаемые типы и аргументы.': 'Database functions with their return types and arguments.',
        'Основные параметры БД, слоты подключений, активность транзакций, доля попаданий в кэш, пользователи и группы.': 'Database basics, connection slots, transaction activity, cache hit ratio, users, and groups.',
        'Параметры памяти и детализация размеров данных и индексов.': 'Memory settings and a breakdown of data and index sizes.',
        'Персональная настройка бокового меню.': 'Personal sidebar configuration.',
        'Пользователи, права, лимиты подключений и срок действия ролей.': 'Users, privileges, connection limits, and role expiration.',
        'Простаивающие транзакции, длительность транзакции и простоя.': 'Idle transactions, transaction duration, and idle duration.',
        'Размеры таблиц, индексы, количество строк и сортировка по метрикам.': 'Table and index sizes, row counts, and metric sorting.',
        'Состояние и конфигурация сегментов Greenplum.': 'Greenplum segment health and configuration.',
        'Список схем, владельцы, количество таблиц и распределение размера.': 'Schemas, owners, table counts, and size distribution.',
        'Статистика VACUUM/ANALYZE, живые и мёртвые строки.': 'VACUUM/ANALYZE statistics and live/dead rows.'
    });

    const inlineTranslations = Object.entries(translations)
        .filter(([source]) => /[А-Яа-яЁё]/.test(source) && !/[<>]/.test(source))
        .sort(([left], [right]) => right.length - left.length);

    const patterns = [
        [/^Страница (\d+) из (\d+)$/, 'Page $1 of $2'], [/^(\d+) из (\d+) записей$/, '$1 of $2 records'],
        [/^(\d+) из (\d+)$/, '$1 of $2'],
        [/^(\d+) записей$/, '$1 records'], [/^(\d+) объект(?:а|ов)?$/, '$1 objects'], [/^(\d+) пользователей$/, '$1 users'], [/^(\d+) групп$/, '$1 groups'],
        [/^(\d+) таблиц$/, '$1 tables'], [/^(\d+) схем$/, '$1 schemas'], [/^(\d+) сегментов$/, '$1 segments'],
        [/^(\d+) представлений$/, '$1 views'], [/^(\d+) функций$/, '$1 functions'], [/^(\d+) параметр(?:а|ов)?$/, '$1 parameters'], [/^(\d+) метрик(?:а|и)?$/, '$1 metrics'],
        [/^(\d+) показател(?:ь|я|ей)$/, '$1 metrics'], [/^(\d+) расширени(?:е|я|й)$/, '$1 extensions'],
        [/^(\d+) активных запросов для (.+)$/, 'Active queries for $2: $1'], [/^(\d+) активных запросов$/, 'Active queries: $1'],
        [/^(\d+) сесси(?:я|и|й) для (.+)$/, 'Sessions for $2: $1'], [/^(\d+) сесси(?:я|и|й)$/, 'Sessions: $1'],
        [/^(\d+) транзакци(?:я|и|й) для (.+)$/, 'Transactions for $2: $1'], [/^(\d+) транзакци(?:я|и|й)$/, 'Transactions: $1'],
        [/^(\d+) блокировок \(заблок\.: (.+), блок\.: (.+)\)$/, 'Locks (blocked: $2, blocking: $3): $1'],
        [/^(\d+) блокировок \(заблок\.: (.+)\)$/, 'Locks (blocked: $2): $1'],
        [/^(\d+) блокировок \(блок\.: (.+)\)$/, 'Locks (blocking: $2): $1'], [/^(\d+) блокировок$/, 'Locks: $1'],
        [/^(\d+) из (\d+) таблиц$/, '$1 of $2 tables'], [/^(\d+) из (\d+) схем$/, '$1 of $2 schemas'],
        [/^(\d+) из (\d+) представлений$/, '$1 of $2 views'], [/^(\d+) из (\d+) функций$/, '$1 of $2 functions'], [/^(\d+) из (\d+) временных таблиц$/, '$1 of $2 temporary tables'],
        [/^(\d+) из (\d+) пользователей$/, '$1 of $2 users'],
        [/^От (\d+) до (\d+) часов\.$/, 'From $1 to $2 hours.'],
        [/^Время сессии должно быть от (\d+) до (\d+) часов$/, 'Session duration must be between $1 and $2 hours'],
        [/^Сегмент (\d+)$/, 'Segment $1'], [/^Живых строк (.+), мёртвых строк (.+)$/, 'Live rows $1, dead rows $2'],
        [/^Материализованные представления: (.+), обычные представления: (.+)$/, 'Materialized views: $1, regular views: $2'],
        [/^Детализация размеров: данные (.+)%, индексы (.+)%$/, 'Size breakdown: data $1%, indexes $2%'],
        [/^Распределение данных по схемам, всего (.+)$/, 'Schema data distribution, total $1'],
        [/^Распределение данных по таблицам, всего (.+)$/, 'Table data distribution, total $1'],
        [/^Распределение данных по временным таблицам, всего (.+)$/, 'Temporary-table data distribution, total $1'],
        [/^Удалить подключение "(.+)"\?$/, 'Delete connection "$1"?'],
        [/^Завершить активный запрос с PID (\d+)\?$/, 'Terminate active query with PID $1?'],
        [/^Завершить сессию пользователя с PID (\d+)\?$/, 'Terminate user session with PID $1?'],
        [/^Завершить запрос PID (\d+)$/, 'Terminate query PID $1'],
        [/^Завершить сессию PID (\d+)$/, 'Terminate session PID $1'],
        [/^Запрос с PID (\d+) завершён$/, 'Query with PID $1 was terminated'],
        [/^Сессия с PID (\d+) завершена$/, 'Session with PID $1 was terminated'],
        [/^Активный запрос с PID (\d+) не найден$/, 'Active query with PID $1 was not found'],
        [/^Сессия с PID (\d+) не найдена$/, 'Session with PID $1 was not found'],
        [/^Не удалось завершить запрос с PID (\d+)$/, 'Failed to terminate query with PID $1'],
        [/^Не удалось завершить сессию с PID (\d+)$/, 'Failed to terminate session with PID $1'],
        [/^Все сегменты подняты и синхронизированы$/, 'All segments are up and synchronized'],
        [/^Есть проблемы: (\d+) сегментов не подняты$/, 'Problems detected: $1 segments are down'],
        [/^Подключено к (.+)$/, 'Connected to $1'], [/^Проверка подключения "(.+)"\.\.\.$/, 'Testing connection "$1"...'],
        [/^Проверка (.+)\.\.\.$/, 'Testing $1...'], [/^Подключение "(.+)" проверено и сохранено$/, 'Connection "$1" tested and saved'],
        [/^Подключение "(.+)" удалено из локального списка$/, 'Connection "$1" removed from the local list'],
        [/^заблок\.: (.+)$/, 'blocked: $1'], [/^блок\.: (.+)$/, 'blocking: $1'],
        [/^Использование слотов подключений: (\d+) из (\d+), ([\d.]+)%$/, 'Connection slot usage: $1 of $2, $3%'],
        [/^Активность БД: коммиты ([\d.]+)%, роллбеки ([\d.]+)%$/, 'Database activity: commits $1%, rollbacks $2%'],
        [/^Перетащить блок (.+)$/, 'Drag $1 section'],
        [/^(VACUUM(?: FULL)?) для (.+) запущен в фоне$/, '$1 for $2 started in the background'],
        [/^(VACUUM(?: FULL)?) для (.+) завершён$/, '$1 for $2 completed'],
        [/^(VACUUM(?: FULL)?) для (.+): (.+)$/, '$1 for $2: $3']
    ];
    const phraseTranslations = [
        ['запущено в фоновом режиме', 'started in the background'], ['успешно завершено', 'completed successfully'],
        ['ошибка выполнения', 'execution failed'], ['операция завершилась с ошибкой', 'operation failed'],
        ['Проверка нового подключения', 'New connection test'], ['Изменение подключения', 'Connection update'],
        ['Создание подключения', 'Connection creation'], ['Удаление подключения', 'Connection deletion'],
        ['Подключение к', 'Connection to'], ['Подключение ', 'Connection '], [' удалено', ' deleted'], [' успешно', ' successfully'],
        ['Не удалось получить статус обслуживания:', 'Failed to get maintenance job status:'],
        ['Не удалось запустить обслуживание:', 'Failed to start maintenance:'],
        ['Не удалось подключиться к', 'Failed to connect to'],
        ['Не удалось получить список ', 'Failed to load '],
        ['Не удалось завершить запрос с PID ', 'Failed to terminate the query with PID '],
        ['Не удалось завершить сессию с PID ', 'Failed to terminate the session with PID '],
        ['Подробности см. в журнале сервера приложения.', 'See the application server log for details.'],
        ['Выберите сохранённое подключение для загрузки ', 'Select a saved connection to load '],
        ['Выберите подключение или дождитесь загрузки ', 'Select a connection or wait for '],
        ['Выберите сохранённое подключение для расчёта ', 'Select a saved connection to calculate '],
        ['Выберите таблицу для расчёта ', 'Select a table to calculate '], ['Загрузка ', 'Loading '],
        ['основных данных БД', 'database basics'], ['активности БД', 'database activity'], ['слотов подключений', 'connection slots'],
        ['пользователей и групп', 'users and groups'], ['установленных расширений', 'installed extensions'],
        ['информации о сегментах', 'segment information'], ['размеров схем', 'schema sizes'], ['размеров таблиц', 'table sizes'],
        ['представлений', 'views'], ['распределения', 'distribution'], ['временных таблиц', 'temporary tables'],
        ['активных запросов', 'active queries'], ['активных сессий', 'active sessions'], ['блокировок', 'locks'],
        ['транзакций', 'transactions'], ['размеров БД', 'database sizes'], ['параметров памяти', 'memory settings'],
        ['использования памяти', 'memory usage'], ['пользователей', 'users'], ['групп', 'groups'],
        ['статистики обслуживания', 'maintenance statistics'], ['аудита', 'audit'],
        ['Действие:', 'Action:'], ['Подключение:', 'Connection:'], ['ID подключения:', 'Connection ID:'], ['Тип БД:', 'Database type:'], ['Сервер:', 'Server:'], ['База данных:', 'Database:'],
        ['Пользователь БД:', 'Database user:'], ['Пользователь:', 'User:'], ['Хост:', 'Host:'], ['Порт:', 'Port:'],
        ['Пользователь сессии:', 'Session user:'], ['База сессии:', 'Session database:'], ['Приложение:', 'Application:'],
        ['Клиент:', 'Client:'], ['Состояние:', 'State:'], ['Тип backend:', 'Backend type:'], ['Начало сессии:', 'Session started:'],
        ['Начало транзакции:', 'Transaction started:'], ['Начало запроса:', 'Query started:'],
        ['Последнее изменение состояния:', 'Last state change:'], ['Ожидание:', 'Wait event:'],
        ['Длительность сессии:', 'Session duration:'], ['Длительность запроса:', 'Query duration:'], ['SQL:', 'SQL:'],
        ['Схема:', 'Schema:'], ['Таблица:', 'Table:'], ['Результат:', 'Result:'], ['Ошибка:', 'Error:'], ['Отображаемые вкладки:', 'Visible tabs:'], ['Предыдущие вкладки:', 'Previous tabs:'],
        ['Пользователь вошёл в приложение:', 'User signed in:'], ['Пользователь вышел из приложения:', 'User signed out:'],
        ['Настройки сайдбара пользователя изменены:', 'User sidebar settings changed:'],
        ['Ошибка', 'Error'], ['Успешно', 'Successful']
    ];

    function translateText(value) {
        if (language !== 'en') return value;
        const leading = value.match(/^\s*/)[0];
        const trailing = value.match(/\s*$/)[0];
        const clean = value.trim();
        if (!clean) return value;
        const decoration = clean.match(/^([^\p{L}\p{N}]+)\s*(.+)$/u);
        if (decoration && /[А-Яа-яЁё]/.test(decoration[2])) {
            return leading + decoration[1] + translateText(decoration[2]).trimStart() + trailing;
        }
        if (translations[clean]) return leading + translations[clean] + trailing;
        for (const [pattern, replacement] of patterns) {
            if (pattern.test(clean)) return leading + clean.replace(pattern, replacement) + trailing;
        }
        let translated = clean;
        phraseTranslations.forEach(([source, target]) => { translated = translated.split(source).join(target); });
        if (/[А-Яа-яЁё]/.test(translated)) {
            inlineTranslations.forEach(([source, target]) => { translated = translated.split(source).join(target); });
        }
        if (translated !== clean) return leading + translated + trailing;
        return value;
    }

    function translateAttributes(element) {
        ['title', 'aria-label', 'placeholder'].forEach(attribute => {
            if (!element.hasAttribute(attribute)) return;
            const current = element.getAttribute(attribute);
            const translated = translateText(current);
            if (translated !== current) element.setAttribute(attribute, translated);
        });
    }

    function translateElement(root) {
        if (language !== 'en' || !root) return;
        if (root.nodeType === Node.TEXT_NODE) {
            if (root.parentElement && root.parentElement.closest('[data-i18n-skip]')) return;
            const translated = translateText(root.nodeValue);
            if (translated !== root.nodeValue) root.nodeValue = translated;
            return;
        }
        if (root.nodeType !== Node.ELEMENT_NODE) return;
        if (root.closest('[data-i18n-skip]')) return;
        translateAttributes(root);
        // translateAttributes(root) above only covers the root element itself; without this,
        // every title/aria-label/placeholder on a DESCENDANT element (i.e. virtually every
        // static attribute rendered by the server, plus anything built via innerHTML) would
        // never be inspected, since the TreeWalker below only visits text nodes, not elements.
        root.querySelectorAll('[title], [aria-label], [placeholder]').forEach(element => {
            if (element.closest('[data-i18n-skip]')) return;
            translateAttributes(element);
        });
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
        let node;
        while ((node = walker.nextNode())) {
            const translated = translateText(node.nodeValue);
            if (translated !== node.nodeValue) node.nodeValue = translated;
        }
    }

    window.DBStatI18n = {language, translate: translateText, translateElement};
    document.addEventListener('DOMContentLoaded', () => {
        document.title = translateText(document.title);
        translateElement(document.body);
        new MutationObserver(mutations => mutations.forEach(mutation => {
            mutation.addedNodes.forEach(translateElement);
            if (mutation.type === 'attributes' || mutation.type === 'characterData') translateElement(mutation.target);
        })).observe(document.body, {attributes: true, attributeFilter: ['title', 'aria-label', 'placeholder'], characterData: true, childList: true, subtree: true});
    });
}());
