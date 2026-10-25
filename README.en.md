# <img src="static/img/favicon.svg" width="64">  DB STAT

[Русский](README.md) | **English**

DB STAT is a web application for monitoring and diagnosing PostgreSQL, Greenplum and Greengage databases: queries, locks, sizes, maintenance and PDF reports in one window.

[Video on YouTube](https://youtu.be/9NN8SoxMOZA)

<table>
  <tr>
    <td align="center"><img src="screenshots/db.png" width="420" alt="Database dashboard"><br><sub>Database — size and activity</sub></td>
    <td align="center"><img src="screenshots/session.png" width="420" alt="Sessions"><br><sub>Sessions — who is doing what right now</sub></td>
  </tr>
  <tr>
    <td align="center"><img src="screenshots/memory.png" width="420" alt="Memory"><br><sub>Memory — parameters and usage</sub></td>
    <td align="center"><img src="screenshots/service.png" width="420" alt="Maintenance"><br><sub>Maintenance — VACUUM and ANALYZE</sub></td>
  </tr>
</table>

## Features

- Active queries, sessions and locks; terminating processes (administrators only).
- Sizes of databases, schemas and tables, temporary and TOAST tables.
- VACUUM and ANALYZE in the background; PDF report for a connection in Russian or English.
- Audit log; the roles "Administrator" and "Analyst".

## Image Docker

db-stat - [olegegoism/db-stat](https://hub.docker.com/r/olegegoism/db-stat)

## Installation and running

Detailed instructions are in [docs/DEVELOPMENT.en.md](docs/DEVELOPMENT.en.md).

## License

[MIT](LICENSE)
