# Deploy ProjectFlow with a separate frontend, API, and Neon database

This repository can deploy as two Render services from the same GitHub repository:

1. A Render Static Site builds `frontend/` and publishes `static/dist/`.
2. A Render Web Service runs FastAPI from the repository root.
3. Both connect through the public API URL; FastAPI permits the frontend origin through `FRONTEND_URL`.
4. FastAPI connects to Neon PostgreSQL using `DATABASE_URL`.

## Create the Neon database

1. Sign in to the Neon Console and create a project for ProjectFlow.
2. Select a region near the Render API region.
3. Use the default database and role, or create names for them in Neon.
4. In the project's **Connect** dialog, select the branch, database, and role. Choose the pooled connection string for the app and copy it securely.
5. Do not commit or share the connection string; it contains the database password.

Neon creates an empty database. SQLAlchemy creates the ProjectFlow tables when FastAPI starts. Existing local PostgreSQL data is not copied automatically.

## Deploy the FastAPI backend to Render

Create a **Web Service** linked to this repository and branch `main`. Leave **Root Directory** empty so Render runs from the repository root.

- Runtime: Python 3
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app:app --host 0.0.0.0 --port $PORT`

Add these environment variables to the backend service:

- `DATABASE_URL`: Neon pooled connection string
- `JWT_SECRET_KEY`: a long, random secret unique to this deployment
- `APP_ENV`: `production`
- `FRONTEND_URL`: the exact public origin of the Render Static Site, for example `https://projectflow-frontend.onrender.com`
- `GEMINI_API_KEY`: optional; add it only if AI features should be enabled

Deploy the service and copy its public URL, for example `https://projectflow-api.onrender.com`. Check `https://<backend-url>/health` and `/docs`.

## Deploy the React frontend to Render

Create a **Static Site** linked to the same repository and branch `main`. Leave **Root Directory** empty.

- Build command: `npm ci --prefix frontend && npm run build --prefix frontend`
- Publish directory: `static/dist`

Add these build-time environment variables to the Static Site:

- `VITE_API_URL`: the full backend origin copied above, such as `https://projectflow-api.onrender.com` (no trailing slash)
- `VITE_ASSET_BASE`: `/`

Deploy. Open the Static Site URL, register an account, and try normal project and task actions. The frontend URL must match the backend's `FRONTEND_URL` exactly, including `https://` and without a trailing slash. If that URL changes, update `FRONTEND_URL` and redeploy the backend.

## Notes

- `VITE_API_URL` is public frontend configuration, not a secret. Never put database passwords, JWT secrets, or Gemini keys in `VITE_*` variables.
- Render Static Site environment variables are baked into the frontend during its build. If the backend URL changes, update `VITE_API_URL` and rebuild/redeploy the Static Site.
- The local Vite dev server continues to proxy API calls to `127.0.0.1:8000` when `VITE_API_URL` is unset.
- On Render's Free web service plan, the backend can spin down after 15 minutes without traffic. The next request may take about a minute to wake it.
- If you need existing local data, migrate/export it to Neon before inviting users. The SQLite importer only imports SQLite data; it does not copy the existing local PostgreSQL database.
