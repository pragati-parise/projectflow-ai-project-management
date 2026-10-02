# ProjectFlow — AI-Powered Project Management Tool

ProjectFlow helps a small team plan projects, assign work, track progress on a Kanban board, and get practical suggestions from Gemini.

## Features

- Email/password registration and login, hashed passwords, seven-day JWT access tokens, and logout.
- Create, edit, search, and delete projects; review progress and due dates.
- Add already registered teammates by email and remove members as the project owner.
- Create, edit, assign, filter, and delete tasks with status, priority, due date, and comments.
- Move task cards between To do, In progress, and Completed by dragging them.
- Switch between light and dark appearance.
- Review Gemini task breakdown suggestions before choosing to save them.
- Ask Gemini workspace questions using the authenticated user's assigned tasks, or project questions using that project's task details.
- Responsive React interface that can be deployed as a separate static site or bundled with FastAPI.

## Stack and architecture

- Frontend: React 18, JavaScript, HTML, CSS, and Vite. Run it separately in development with `npm run dev`.
- Backend: Python 3.12, FastAPI, Pydantic, REST APIs.
- Database: PostgreSQL through SQLAlchemy ORM and psycopg 3.
- Authentication: JWT bearer tokens and bcrypt password hashes.
- AI: Google Gemini API, called only by the backend.

```text
frontend/src/main.jsx + React + Vite (`npm run dev`)
                              │ API proxy + JWT
                              ▼
                 backend/main.py (FastAPI, port 8000)
                      │              │
      backend/auth.py, models.py     Gemini service call
                      │              │
              backend/database.py   Google Gemini
                      │
            PostgreSQL (SQLAlchemy)
```

## Folder structure

```text
backend/
  auth.py             Password hashing, JWT, database dependency, access checks
  database.py         PostgreSQL engine and SQLAlchemy session
  main.py             FastAPI routes, validation, and Gemini endpoints
  migrate_sqlite.py   One-time importer for the existing SQLite data
  models.py           Users, projects, project members, tasks, comments
  schemas.py          Pydantic request validation
static/
  index.html          Legacy fallback page (not used by Vite development)
  dist/               Vite production build output (generated)
frontend/
  package.json        React/Vite scripts and dependencies
  vite.config.js      Dev server and FastAPI API proxy
  index.html
  src/main.jsx
  src/projectflow.css
app.py                Deployment-compatible ASGI import (app:app)
requirements.txt
.env.example
```

## Database schema

- `users`: account name, unique email, bcrypt password hash.
- `projects`: name, description, owner, due date, status, timestamps.
- `project_members`: project/user many-to-many membership and role; a unique constraint prevents duplicates.
- `tasks`: project, title, description, status, priority, due date, optional assigned user, creator.
- `comments`: task, author, comment text, and timestamp.

Users can own projects and belong to other projects. Only project members can see project details. Owners manage project details and membership. A task assignee must be a project member.

## API endpoints

Authentication:

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/logout`
- `GET /auth/me`

Projects and teams:

- `GET /projects?q=...`, `POST /projects`
- `GET /projects/{project_id}`, `PUT /projects/{project_id}`, `DELETE /projects/{project_id}`
- `GET /projects/{project_id}/members`
- `POST /projects/{project_id}/members` with `{ "email": "person@example.com" }`
- `DELETE /projects/{project_id}/members/{user_id}`

Tasks and AI:

- `GET /projects/{project_id}/tasks?q=...&status=...&priority=...`
- `GET /tasks/mine` for tasks assigned to the authenticated user across projects.
- `POST /projects/{project_id}/tasks`
- `PUT /tasks/{task_id}`, `DELETE /tasks/{task_id}`
- `POST /tasks/{task_id}/comments`
- `POST /ai/task-breakdown`
- `POST /ai/project-assistant`
- `GET /health`
- Interactive API reference: `/docs`

Protected endpoints require `Authorization: Bearer <token>`. Request and response validation is documented in FastAPI's `/docs` page.

## Environment variables

Copy `.env.example` to `.env` for local work only if `.env` does not already exist, then replace the placeholder values. Do not overwrite an existing `.env` because it may contain local secrets and settings.

- `DATABASE_URL`: PostgreSQL connection URL. Local example: `postgresql://projectflow:your-password@localhost:5432/projectflow`.
- `JWT_SECRET_KEY`: long, random secret used to sign login tokens.
- `GEMINI_API_KEY`: Google AI Studio API key. Keep it on the backend only.
- `APP_ENV`: use `development` locally and `production` when deployed.
- `FRONTEND_URL`: comma-separated allowed browser origins. The default allows the local FastAPI URL.

Never commit `.env`. Only `.env.example` with placeholders belongs in Git.

## Authentication and collaboration flows

1. Registration validates the email and password, stores only a bcrypt hash, and returns a signed JWT. Login verifies the hash and returns a JWT; React sends it as a bearer token. Logout removes the token from the browser.
2. Creating a project also adds its owner to `project_members`. The project owner enters a registered user's email to add them; an unregistered email gets a clear register-first error.
3. The assignment menu is populated from the current project's members. The API repeats this check on every create/edit, so non-members cannot be assigned through a crafted request.
4. The board updates task status through the task API. AI breakdown suggestions remain in React until the user confirms selected tasks.
5. For workspace assistant questions, the API includes the authenticated user's assigned tasks. For project-specific questions, it checks project access and includes only that project and its tasks in the Gemini prompt.

## Deployment

Deploy the Vite frontend as a Render Static Site and FastAPI as a separate Render Web Service, with Neon PostgreSQL as the database. Follow [DEPLOYMENT.md](DEPLOYMENT.md) for the required build settings, URLs, CORS origin, and environment variables. The frontend's `VITE_API_URL` is public configuration; database and API secrets belong only in the backend environment.
