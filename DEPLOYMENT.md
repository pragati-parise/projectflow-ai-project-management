# Deployment Guide

## Is This Necessary?
- `Procfile` + `gunicorn`: recommended for production hosting.
- env-based `SECRET_KEY`: required for secure production.
- PostgreSQL migration: optional, but strongly recommended for cloud hosting stability.

## Environment Variables
- `SECRET_KEY`: required in production.
- `DATABASE_URL`: optional.
  - If not set, app uses local SQLite (`project_manager.db`).
  - If set, app uses PostgreSQL and initializes `schema_postgres.sql`.

## Run Locally
```bash
pip install -r requirements.txt
python app.py
```

## Run With Gunicorn (production-like local run)
```bash
gunicorn app:app
```

## Render Hosting
1. Push project to GitHub.
2. Create a new Web Service in Render.
3. Build command:
   - `pip install -r requirements.txt`
4. Start command:
   - `gunicorn app:app`
5. Add env vars in Render:
   - `SECRET_KEY=<strong-secret>`
   - Optional: `DATABASE_URL=<managed-postgres-url>`

## Notes
- SQLite is fine for local/dev.
- For real production, use PostgreSQL to avoid data reset/locking issues.
