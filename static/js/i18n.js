(function () {
    'use strict';

    const language = String(window.DB_STAT_LANGUAGE || 'ru').toLowerCase();
    const translations = {
        'Авторизация': 'Sign in', 'Авторизация пользователя': 'User sign in', 'Войти': 'Sign in',
        'Логин/Login': 'Login', 'Почта/Email': 'Email', 'Ошибка 404': 'Error 404',
        'Страница не найдена': 'Page not found', 'Запрошенная страница не существует или была удалена.': 'The requested page does not exist or has been removed.',
        'Запрошенный адрес': 'Requested address', 'На главную': 'Home', 'Главная': 'Home', 'Главная страница': 'Home page',
        'Инфраструктура': 'Infrastructure', 'Данные': 'Data', 'Производительность': 'Performance', 'Администрирование': 'Administration',
        'База данных': 'Database', 'Сегменты': 'Segments', 'Схемы': 'Schemas', 'Таблицы': 'Tables', 'Представления': 'Views',
        'Временные таблицы': 'Temporary tables', 'Распределение': 'Distribution', 'Запросы': 'Queries', 'Активные запросы': 'Active queries',
        'Сессии': 'Sessions', 'Блокировки': 'Locks', 'Транзакции': 'Transactions', 'Память': 'Memory', 'Пользователи': 'Users',
        'Группы': 'Groups', 'Обслуживание': 'Maintenance', 'Аудит': 'Audit', 'Настройки': 'Settings', 'Видео': 'Video',
        'Настройки сайдбара': 'Interface settings', 'Свернуть сайдбар': 'Collapse sidebar', 'Свернуть/развернуть сайдбар': 'Collapse/expand sidebar',
        'Открыть главную страницу DB STAT': 'Open the DB STAT home page', 'Сессии и подключения': 'Sessions and connections',
        'Язык интерфейса': 'Interface language', 'Русский (RU)': 'Russian (RU)',
        'Язык применяется ко всему интерфейсу и сохраняется для следующих посещений.': 'The language applies to the entire interface and is saved for future visits.',
        'Выберите вкладки, которые нужно показывать в боковом меню для текущего пользователя.': 'Select the tabs to show in the sidebar for the current user.',
        'Выбрать все': 'Select all', 'Сохранить': 'Save', 'Уведомление': 'Notification', 'Новое подключение': 'New connection',
        'Название': 'Name', 'Хост': 'Host', 'Порт': 'Port', 'Тип БД': 'Database type', 'Пароль': 'Password', 'Пользователь': 'User',
        'Пользователь БД': 'Database user', 'Владелец': 'Owner', 'Информация о подключении': 'Connection information',
        'Информация о пользователе': 'User information', 'Почта': 'Email', 'Роль': 'Role', 'Новое подключение': 'New connection',
        'Удалить': 'Delete', 'Отмена': 'Cancel', 'Проверить': 'Test', 'Подключиться': 'Connect', 'Редактировать подключение': 'Edit connection',
        'Загрузка подключений...': 'Loading connections...', 'Нет доступных подключений': 'No connections available', 'Выйти': 'Sign out',
        'Описание разделов': 'Section overview', 'Размеры и структура': 'Sizes and structure', 'Состояние и конфигурация': 'Status and configuration',
        'Список схем': 'Schema list', 'Список таблиц': 'Table list', 'Список представлений': 'View list', 'Перекос данных': 'Data skew',
        'Активные временные таблицы': 'Active temporary tables', 'Долгие запросы': 'Long-running queries',
        'Пользователи и подключения': 'Users and connections', 'Кто кого блокирует': 'Blocking relationships', 'Параметры памяти': 'Memory settings',
        'Список пользователей': 'User list', 'Список групп': 'Group list', 'Очистка / анализ': 'Vacuum / analyze', 'Действия пользователя': 'User actions',
        'Нет данных': 'No data', 'Загрузка...': 'Loading...', 'Обновить': 'Refresh', 'Поиск': 'Search', 'Все': 'All', 'Да': 'Yes', 'Нет': 'No',
        'Параметр': 'Parameter', 'Значение': 'Value', 'Статус': 'Status', 'Состояние': 'State', 'Размер': 'Size', 'Всего': 'Total',
        'Схема': 'Schema', 'Таблица': 'Table', 'Индексы': 'Indexes', 'Строк': 'Rows', 'Строки': 'Rows', 'Длительность': 'Duration',
        'Дата': 'Date', 'Действие': 'Action', 'Информация': 'Information', 'События аудита не найдены': 'No audit events found',
        'Страница 1 из 1': 'Page 1 of 1', 'Страница 1': 'Page 1', 'Все действия': 'All actions', 'Свернуть график': 'Collapse chart',
        'Развернуть график': 'Expand chart', 'Выберите таблицу': 'Select a table', 'Таблицы не найдены': 'No tables found',
        'Пользователи не найдены': 'No users found', 'Группы не найдены': 'No groups found', 'Схемы не найдены': 'No schemas found',
        'Представления не найдены': 'No views found', 'Временные таблицы не найдены': 'No temporary tables found',
        'Транзакции не найдены': 'No transactions found', 'Блокировки не найдены': 'No locks found', 'Сессии не найдены': 'No sessions found',
        'Запросы не найдены': 'No queries found', 'Недоступно': 'Unavailable', 'Обновление...': 'Updating...',
        'Основные данные БД': 'Database basics', 'Активность БД': 'Database activity', 'Коммиты / Роллбеки': 'Commits / rollbacks',
        'Показатель': 'Metric', 'Слоты подключений': 'Connection slots', 'Использование': 'Usage', 'Пользователи и группы': 'Users and groups',
        'Тип': 'Type', 'Количество': 'Count', 'Установленные расширения': 'Installed extensions', 'Расширение': 'Extension', 'Версия': 'Version',
        'Комментарий': 'Comment', 'Состояние сегментов': 'Segment health', 'Информация о сегментах недоступна': 'Segment information is unavailable',
        'Детальная информация': 'Details', 'Сегмент': 'Segment', 'Режим': 'Mode', 'Распределение данных по схемам': 'Data distribution by schema',
        'Количество таблиц': 'Table count', 'Назад': 'Previous', 'Далее': 'Next', 'Вперёд': 'Next',
        'Распределение данных по таблицам': 'Data distribution by table', 'Количество индексов': 'Index count', 'Все типы': 'All types',
        'Обычное': 'Regular', 'Материализованное': 'Materialized', 'Материализованные / обычные': 'Materialized / regular',
        'Общий размер материализованных': 'Total materialized size', 'Представление': 'View', 'Выбор таблицы для анализа распределения': 'Select a table for distribution analysis',
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
        'Живых строк': 'Live rows', 'Мёртвых строк': 'Dead rows', 'Доля мёртвых строк': 'Dead-row share',
        'Последняя очистка (VACUUM)': 'Last VACUUM', 'Последний анализ (ANALYZE)': 'Last ANALYZE', 'Аудит действий': 'Action audit',
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
        'DB STAT — веб-панель для оперативного мониторинга и диагностики баз данных PostgreSQL и Greenplum. Она собирает ключевые технические показатели выбранного подключения и представляет их в едином, понятном интерфейсе.': 'DB STAT is a web dashboard for real-time monitoring and diagnostics of PostgreSQL and Greenplum databases. It collects key technical metrics for the selected connection and presents them in one clear interface.',
        'На панели можно оценить размеры баз, схем, таблиц и индексов, проверить активность пользователей и сессий, найти длительные или проблемные запросы, а также увидеть блокировки и простаивающие транзакции.': 'Use the dashboard to review database, schema, table, and index sizes; inspect user and session activity; find long-running or problematic queries; and identify locks and idle transactions.',
        'Для Greenplum доступны сведения о состоянии сегментов и распределении строк, помогающие обнаружить перекос данных. Раздел обслуживания показывает статистику VACUUM и ANALYZE, количество живых и мёртвых строк и время последних операций.': 'For Greenplum, segment health and row distribution data help reveal skew. The maintenance section shows VACUUM and ANALYZE statistics, live and dead row counts, and the latest operation times.',
        'DB STAT подходит для ежедневного контроля, первичной диагностики снижения производительности и административной проверки. Переключайтесь между сохранёнными подключениями, сравнивайте показатели и быстрее находите участки, которым требуется внимание.': 'DB STAT is designed for daily checks, initial performance diagnostics, and administrative review. Switch between saved connections, compare metrics, and quickly find areas that need attention.'
    };

    const patterns = [
        [/^Страница (\d+) из (\d+)$/, 'Page $1 of $2'], [/^(\d+) из (\d+) записей$/, '$1 of $2 records'],
        [/^(\d+) из (\d+)$/, '$1 of $2'],
        [/^(\d+) записей$/, '$1 records'], [/^(\d+) пользователей$/, '$1 users'], [/^(\d+) групп$/, '$1 groups'],
        [/^(\d+) таблиц$/, '$1 tables'], [/^(\d+) схем$/, '$1 schemas'], [/^(\d+) сегментов$/, '$1 segments'],
        [/^(\d+) представлений$/, '$1 views'], [/^(\d+) параметр(?:а|ов)?$/, '$1 parameters'], [/^(\d+) метрик(?:а|и)?$/, '$1 metrics'],
        [/^(\d+) показател(?:ь|я|ей)$/, '$1 metrics'], [/^(\d+) расширени(?:е|я|й)$/, '$1 extensions'],
        [/^Использование слотов подключений: (\d+) из (\d+), ([\d.]+)%$/, 'Connection slot usage: $1 of $2, $3%'],
        [/^Активность БД: коммиты ([\d.]+)%, роллбеки ([\d.]+)%$/, 'Database activity: commits $1%, rollbacks $2%']
    ];
    const phraseTranslations = [
        ['Не удалось получить обзор БД:', 'Failed to load database overview:'],
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
        ['статистики обслуживания', 'maintenance statistics'], ['аудита', 'audit']
    ];

    function translateText(value) {
        if (language !== 'en') return value;
        const leading = value.match(/^\s*/)[0];
        const trailing = value.match(/\s*$/)[0];
        const clean = value.trim();
        if (!clean) return value;
        if (translations[clean]) return leading + translations[clean] + trailing;
        for (const [pattern, replacement] of patterns) {
            if (pattern.test(clean)) return leading + clean.replace(pattern, replacement) + trailing;
        }
        let translated = clean;
        phraseTranslations.forEach(([source, target]) => { translated = translated.replace(source, target); });
        if (translated !== clean) return leading + translated + trailing;
        return value;
    }

    function translateElement(root) {
        if (language !== 'en' || !root) return;
        if (root.nodeType === Node.TEXT_NODE) {
            root.nodeValue = translateText(root.nodeValue);
            return;
        }
        if (root.nodeType !== Node.ELEMENT_NODE) return;
        ['title', 'aria-label', 'placeholder'].forEach(attribute => {
            if (root.hasAttribute(attribute)) root.setAttribute(attribute, translateText(root.getAttribute(attribute)));
        });
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
        let node;
        while ((node = walker.nextNode())) node.nodeValue = translateText(node.nodeValue);
    }

    window.DBStatI18n = {language, translate: translateText, translateElement};
    document.addEventListener('DOMContentLoaded', () => {
        translateElement(document.body);
        new MutationObserver(mutations => mutations.forEach(mutation => mutation.addedNodes.forEach(translateElement)))
            .observe(document.body, {childList: true, subtree: true});
    });
}());
