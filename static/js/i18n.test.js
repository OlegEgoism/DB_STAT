const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

global.window = {DB_STAT_LANGUAGE: 'en'};
global.document = {addEventListener() {}};
require('./i18n.js');

const {translate} = window.DBStatI18n;
const hasRussianText = value => /[А-Яа-яЁё]/.test(value);
const templatesDirectory = path.resolve(__dirname, '../../templates');
const templateFiles = [];

function collectTemplates(directory) {
    fs.readdirSync(directory, {withFileTypes: true}).forEach(entry => {
        const entryPath = path.join(directory, entry.name);
        if (entry.isDirectory()) collectTemplates(entryPath);
        else if (entry.name.endsWith('.html')) templateFiles.push(entryPath);
    });
}

collectTemplates(templatesDirectory);
const templateStrings = new Set();
templateFiles.forEach(file => {
    const source = fs.readFileSync(file, 'utf8');
    for (const match of source.matchAll(/>([^<]+)</g)) {
        const value = match[1].replace(/\s+/g, ' ').trim();
        if (hasRussianText(value) && !value.includes('{{') && !value.includes('{%')) templateStrings.add(value);
    }
    for (const match of source.matchAll(/(?:title|aria-label|placeholder)="([^"]+)"/g)) {
        if (hasRussianText(match[1]) && !match[1].includes('{%')) templateStrings.add(match[1]);
    }
});

templateStrings.forEach(value => {
    assert.equal(hasRussianText(translate(value)), false, `Missing template translation: ${value}`);
});

const dynamicStrings = [
    '5 активных запросов для alice', '4 сессии для analyst', '3 транзакции для admin', '2 блокировок (заблок.: user)',
    '15 из 30 таблиц', '7 из 20 схем', '8 из 10 представлений', '3 из 8 временных таблиц', '10 из 12 пользователей',
    'Использование слотов подключений: 4 из 100, 4.00%', 'Активность БД: коммиты 98.00%, роллбеки 2.00%',
    'Детализация размеров: данные 75.00%, индексы 25.00%', 'Живых строк 100, мёртвых строк 2',
    'Материализованные представления: 3, обычные представления: 8', 'Распределение данных по таблицам, всего 15 GB',
    'Все сегменты подняты и синхронизированы', 'Есть проблемы: 2 сегментов не подняты',
    'Действие: Проверка нового подключения; Подключение: Main; Результат: Успешно',
    'Настройки сайдбара пользователя изменены: Пользователь: admin; Отображаемые вкладки: База данных, Сегменты, Схемы, Таблицы, Представления, Временные таблицы, Распределение, Активные запросы, Сессии, Блокировки, Транзакции, Память, Пользователи, Группы, Обслуживание, Аудит; Предыдущие вкладки: База данных, Сегменты, Схемы, Таблицы, Представления, Временные таблицы, Распределение, Активные запросы, Сессии, Блокировки, Транзакции, Память, Пользователи, Группы, Обслуживание, Аудит',
    'User sidebar settings changed: User: admin; Visible tabs: База данных, Сегменты, Схемы, Таблицы, Представления, Временные таблицы, Распределение, Активные запросы, Сессии, Блокировки, Транзакции, Память, Пользователи, Группы, Обслуживание, Аудит',
    'Сегменты недоступны для выбранного подключения',
    'Выбранное подключение не похоже на Greenplum или у пользователя нет доступа к gp_segment_configuration. Выберите Greenplum-подключение или проверьте права доступа.',
    'Не удалось получить размеры таблиц: permission denied', '⚠️ Заполните все обязательные поля',
    '✅ Подключение "Main" проверено и сохранено', 'Удалить подключение "Main"?'
];

dynamicStrings.forEach(value => {
    assert.equal(hasRussianText(translate(value)), false, `Missing dynamic translation: ${value}`);
});

console.log(`Verified ${templateStrings.size} template strings and ${dynamicStrings.length} dynamic strings.`);
