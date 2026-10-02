# Deployment guide

ProjectFlow is an ASGI app. Use a Python hosting service with Node.js available during build and a managed PostgreSQL database.

## Configure the service

- Build command: `pip install -r requirements.txt && npm --prefix frontend install && npm --prefix frontend run build`
- Start command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
- Set environment variables: `DATABASE_URL`, `JWT_SECRET_KEY`, `APP_ENV=production`, `FRONTEND_URL`, and `GEMINI_API_KEY` when enabling AI.
- Do not upload `.env` or `project_manager.db` to the public repository.
- Keep the JWT secret stable across service instances, but generate a different secret for each environment.
- Use the database URL and SSL settings supplied by the PostgreSQL host.

## First deployment

The build command creates `static/dist`, which FastAPI serves as the frontend. SQLAlchemy creates missing tables at startup. To import existing data, configure the hosted PostgreSQL URL locally and run `python -m backend.migrate_sqlite` once against an empty database before starting the service. Do not run the importer against an already populated target. Keep a backup of the SQLite source.

## Check the service

Visit `/health` to check the process and `/docs` for the API reference. Set `APP_ENV=development` only for local work; production hides internal error details from browser responses while writing full traces to server logs.
