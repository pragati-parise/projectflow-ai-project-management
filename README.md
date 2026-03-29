# ProjectFlow - Full Stack Project Management Tool

ProjectFlow is a full stack project management app where users can create projects, manage tasks, assign teammates, set deadlines, and track progress.

## Features
- User authentication (signup, login, logout)
- Dashboard with project search
- Create, edit, delete projects
- Task management inside each project:
  - Create, edit, delete tasks
  - Due dates
  - Priority levels: low, medium, high
  - Drag-and-drop status board: To Do, In Progress, Done
- Team collaboration:
  - Add/remove project members
  - Task comments
- Dark/Light mode toggle

## Tech Stack
- Frontend: React.js (CDN), JavaScript, HTML, CSS
- Backend: Python, Flask
- API: Flask JSON endpoints (`/api/*`)
- Database: SQLite (default), PostgreSQL (optional via `DATABASE_URL`)
- Production server: Gunicorn

## Project Structure
```txt
app.py
schema.sql
schema_postgres.sql
requirements.txt
Procfile
templates/
static/
```

## Local Setup
1. Clone the repo
2. Install dependencies
3. Run app

```bash
pip install -r requirements.txt
python app.py
```

Open: `http://127.0.0.1:5000`

## Environment Variables
Create a `.env` from `.env.example` or set these in your host:

- `SECRET_KEY` (required for production)
- `DATABASE_URL` (optional)
  - Not set -> uses SQLite (`project_manager.db`)
  - Set -> uses PostgreSQL

Example:
```env
SECRET_KEY=replace-with-a-long-random-secret
DATABASE_URL=postgresql://username:password@hostname:5432/database_name
```

## Deploy (Render)
1. Push this repo to GitHub
2. Create a new Render Web Service from the repo
3. Build command:
   - `pip install -r requirements.txt`
4. Start command:
   - `gunicorn app:app`
5. Add env vars:
   - `SECRET_KEY`
   - optional `DATABASE_URL`

## Notes
- SQLite is good for local development.
- PostgreSQL is recommended for production.
