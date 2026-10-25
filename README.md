# <img src="static/img/favicon.svg" width="64">  DB STAT

**Русский** | [English](README.en.md)

DB STAT — веб-приложение для мониторинга и диагностики баз данных PostgreSQL, Greenplum и Greengage: запросы, блокировки, размеры, обслуживание и PDF-отчёты в одном окне.

[Видео на YouTube](https://youtu.be/9NN8SoxMOZA)

<table>
  <tr>
    <td align="center"><img src="screenshots/db.png" width="420" alt="Дашборд базы"><br><sub>База данных — размер и активность</sub></td>
    <td align="center"><img src="screenshots/session.png" width="420" alt="Сессии"><br><sub>Сессии — кто и что делает сейчас</sub></td>
  </tr>
  <tr>
    <td align="center"><img src="screenshots/memory.png" width="420" alt="Память"><br><sub>Память — параметры и использование</sub></td>
    <td align="center"><img src="screenshots/service.png" width="420" alt="Обслуживание"><br><sub>Обслуживание — VACUUM и ANALYZE</sub></td>
  </tr>
</table>

## Возможности

- Активные запросы, сессии и блокировки; завершение процессов (для администратора).
- Размеры баз, схем и таблиц, временные и TOAST-таблицы.
- VACUUM и ANALYZE в фоне; PDF-отчёт по подключению на русском или английском.
- Журнал аудита; роли «Администратор» и «Аналитик».

## Установка и запуск

Подробная инструкция — в [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## Лицензия

[MIT](LICENSE)
