# <img src="static/img/favicon.svg" width="64">  DB STAT

[Русский](README.md) | **English**

DB STAT is a web application for monitoring and diagnosing PostgreSQL, Greenplum and Greengage databases: queries, locks, sizes, maintenance and PDF reports in one window.

[Video on YouTube](https://youtu.be/9NN8SoxMOZA)

<table>
  <tr>
    <td align="center"><img src="screenshots/db.png" width="420" alt="Database dashboard"><br><sub>Database — size and activity</sub></td>
    <td align="center"><img src="screenshots/session.png" width="420" alt="Sessions"><br><sub>Sessions — who is doing what right now</sub></td>
  </tr>
</table>

## Features

- Active queries, sessions and locks; terminating processes (administrators only).
- Sizes of databases, schemas and tables, temporary and TOAST tables.
- VACUUM and ANALYZE in the background; PDF report for a connection in Russian or English.
- Audit log; the roles "Administrator" and "Analyst".

## Installation and running

Detailed instructions are in [docs/DEVELOPMENT.en.md](docs/DEVELOPMENT.en.md).

## First sign-in

1. Open the application in a browser (by default http://localhost:8000).
2. Sign in as the administrator. The login and password are set on the first start.
3. Add a connection: in the top bar click **+**, fill in the fields and click **Connect**.

Only an administrator creates connections. Greenplum tabs appear only for Greenplum and Greengage connections.

## Security

- Set `SECRET_KEY`, `DB_CONNECTION_ENCRYPTION_KEY` and `INITIAL_ADMIN_PASSWORD`. The default values are insecure.
- Do not expose the application to the internet without HTTPS.
- Create a separate account for each person.

## Frequently asked questions

- **503 "connection limit exceeded".** Too many parallel requests to one database.
- **"locked by another transaction".** The database is busy with another process. The application reports the reason after a few seconds.
- **The PDF has no "Expensive queries" section.** The `pg_stat_statements` extension is not installed on the database.

## For developers

Installation, configuration, Docker and development — in [docs/DEVELOPMENT.en.md](docs/DEVELOPMENT.en.md).

## License

[MIT](LICENSE)
