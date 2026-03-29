import os
import sqlite3
from functools import wraps

from flask import Flask, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

try:
    import psycopg
    from psycopg.rows import dict_row
except Exception:  # pragma: no cover
    psycopg = None
    dict_row = None


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
SQLITE_DB_PATH = os.path.join(BASE_DIR, "project_manager.db")

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DB_KIND = "postgres" if DATABASE_URL else "sqlite"
DB_INITIALIZED = False

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-me")


def to_driver_sql(sql):
    if DB_KIND == "postgres":
        return sql.replace("?", "%s")
    return sql


def db_execute(sql, params=()):
    db = get_db()
    return db.execute(to_driver_sql(sql), params)


def db_execute_many(statements):
    db = get_db()
    cursor = db.cursor()
    for stmt in statements:
        query = stmt.strip()
        if query:
            cursor.execute(query)
    db.commit()


def get_db():
    if "db" in g:
        return g.db

    if DB_KIND == "postgres":
        if psycopg is None:
            raise RuntimeError("psycopg is not installed. Add it to requirements to use DATABASE_URL.")
        g.db = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    else:
        g.db = sqlite3.connect(SQLITE_DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    schema_file = "schema_postgres.sql" if DB_KIND == "postgres" else "schema.sql"
    schema_path = os.path.join(BASE_DIR, schema_file)
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    if DB_KIND == "sqlite":
        db = get_db()
        db.executescript(schema_sql)
        db.commit()
    else:
        # psycopg does not support sqlite-style executescript; run statements one by one.
        statements = [stmt for stmt in schema_sql.split(";") if stmt.strip()]
        db_execute_many(statements)


@app.before_request
def ensure_db():
    global DB_INITIALIZED
    if DB_INITIALIZED:
        return

    if DB_KIND == "sqlite":
        if not os.path.exists(SQLITE_DB_PATH):
            init_db()
    else:
        init_db()
    DB_INITIALIZED = True


def row_dict(row):
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    return dict(row)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


@app.context_processor
def inject_user():
    user = None
    if "user_id" in session:
        user = get_user_by_id(session["user_id"])
    return {"current_user": user}


def get_user_by_id(user_id):
    return db_execute("SELECT id, name, email FROM users WHERE id = ?", (user_id,)).fetchone()


def user_can_access_project(project_id, user_id):
    row = db_execute(
        """
        SELECT p.id
        FROM projects p
        LEFT JOIN project_members pm ON pm.project_id = p.id
        WHERE p.id = ? AND (p.owner_id = ? OR pm.user_id = ?)
        LIMIT 1
        """,
        (project_id, user_id, user_id),
    ).fetchone()
    return row is not None


def get_projects_for_user(user_id, query=""):
    rows = db_execute(
        """
        SELECT DISTINCT p.*,
        (
            SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id
        ) AS total_tasks,
        (
            SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id AND t.status = 'done'
        ) AS done_tasks
        FROM projects p
        LEFT JOIN project_members pm ON pm.project_id = p.id
        WHERE (p.owner_id = ? OR pm.user_id = ?)
          AND (? = '' OR p.name LIKE ? OR p.description LIKE ?)
        ORDER BY p.updated_at DESC, p.created_at DESC
        """,
        (user_id, user_id, query, f"%{query}%", f"%{query}%"),
    ).fetchall()

    data = []
    for row in rows:
        item = row_dict(row)
        total = item["total_tasks"] or 0
        done = item["done_tasks"] or 0
        item["progress"] = round((done / total) * 100, 2) if total else 0
        data.append(item)
    return data


def get_project_members(project_id):
    return db_execute(
        """
        SELECT u.id, u.name, u.email
        FROM users u
        INNER JOIN project_members pm ON pm.user_id = u.id
        WHERE pm.project_id = ?
        ORDER BY u.name
        """,
        (project_id,),
    ).fetchall()


def get_project_payload(project_id, user_id):
    if not user_can_access_project(project_id, user_id):
        return None

    project = db_execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if not project:
        return None

    members = [row_dict(m) for m in get_project_members(project_id)]
    non_members = [
        row_dict(row)
        for row in db_execute(
            """
            SELECT id, name, email
            FROM users
            WHERE id NOT IN (SELECT user_id FROM project_members WHERE project_id = ?)
            ORDER BY name
            """,
            (project_id,),
        ).fetchall()
    ]

    tasks = db_execute(
        """
        SELECT t.*, u.name AS assignee_name, c.name AS creator_name
        FROM tasks t
        LEFT JOIN users u ON u.id = t.assigned_to
        LEFT JOIN users c ON c.id = t.created_by
        WHERE t.project_id = ?
        ORDER BY
            CASE t.priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
            t.due_date ASC,
            t.created_at DESC
        """,
        (project_id,),
    ).fetchall()

    tasks_data = [row_dict(task) for task in tasks]
    comments_by_task = {}
    if tasks_data:
        task_ids = [task["id"] for task in tasks_data]
        placeholders = ",".join(["?"] * len(task_ids))
        comments = db_execute(
            f"""
            SELECT cm.*, u.name AS author_name
            FROM comments cm
            INNER JOIN users u ON u.id = cm.user_id
            WHERE cm.task_id IN ({placeholders})
            ORDER BY cm.created_at ASC
            """,
            tuple(task_ids),
        ).fetchall()
        for comment in comments:
            comment_data = row_dict(comment)
            comments_by_task.setdefault(comment_data["task_id"], []).append(comment_data)

    status_groups = {"todo": [], "in_progress": [], "done": []}
    for task in tasks_data:
        task["comments"] = comments_by_task.get(task["id"], [])
        status_groups[task["status"]].append(task)

    project_data = row_dict(project)
    return {
        "project": project_data,
        "members": members,
        "non_members": non_members,
        "status_groups": status_groups,
        "is_owner": project_data["owner_id"] == user_id,
    }


def json_error(message, status=400):
    return jsonify({"ok": False, "message": message}), status


@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        if not name or not email or not password:
            flash("Name, email, and password are required.", "error")
            return redirect(url_for("signup"))

        exists = db_execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if exists:
            flash("Email already registered. Please log in.", "error")
            return redirect(url_for("login"))

        db = get_db()
        db_execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password)),
        )
        db.commit()
        flash("Account created successfully. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        user = db_execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not user or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "error")
            return redirect(url_for("login"))

        session.clear()
        session["user_id"] = user["id"]
        flash("Welcome back!", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]
    query = request.args.get("q", "").strip()
    initial_data = {
        "view": "dashboard",
        "query": query,
        "projects": get_projects_for_user(user_id, query),
        "current_user": row_dict(get_user_by_id(user_id)),
    }
    return render_template("react_app.html", title="Dashboard", initial_data=initial_data)


@app.route("/projects/<int:project_id>")
@login_required
def project_detail(project_id):
    user_id = session["user_id"]
    payload = get_project_payload(project_id, user_id)
    if not payload:
        flash("Access denied.", "error")
        return redirect(url_for("dashboard"))

    initial_data = {
        "view": "project",
        "project_id": project_id,
        "current_user": row_dict(get_user_by_id(user_id)),
        "project_payload": payload,
    }
    return render_template("react_app.html", title=payload["project"]["name"], initial_data=initial_data)


@app.route("/api/me")
@login_required
def api_me():
    return jsonify({"ok": True, "user": row_dict(get_user_by_id(session["user_id"]))})


@app.route("/api/projects", methods=["GET", "POST"])
@login_required
def api_projects():
    db = get_db()
    user_id = session["user_id"]

    if request.method == "GET":
        query = request.args.get("q", "").strip()
        return jsonify({"ok": True, "projects": get_projects_for_user(user_id, query)})

    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    description = (payload.get("description") or "").strip()
    if not name:
        return json_error("Project name is required.")

    if DB_KIND == "postgres":
        project_id = db_execute(
            "INSERT INTO projects (name, description, owner_id) VALUES (?, ?, ?) RETURNING id",
            (name, description, user_id),
        ).fetchone()["id"]
    else:
        cursor = db_execute(
            "INSERT INTO projects (name, description, owner_id) VALUES (?, ?, ?)",
            (name, description, user_id),
        )
        project_id = cursor.lastrowid

    db_execute(
        "INSERT INTO project_members (project_id, user_id, role) VALUES (?, ?, ?)",
        (project_id, user_id, "owner"),
    )
    db.commit()

    project = db_execute(
        """
        SELECT p.*,
               0 AS total_tasks,
               0 AS done_tasks
        FROM projects p
        WHERE p.id = ?
        """,
        (project_id,),
    ).fetchone()
    project_data = row_dict(project)
    project_data["progress"] = 0
    return jsonify({"ok": True, "project": project_data})


@app.route("/api/projects/<int:project_id>", methods=["GET", "PUT", "DELETE"])
@login_required
def api_project(project_id):
    user_id = session["user_id"]
    db = get_db()
    project = db_execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if not project:
        return json_error("Project not found.", 404)
    if not user_can_access_project(project_id, user_id):
        return json_error("Access denied.", 403)

    if request.method == "GET":
        payload = get_project_payload(project_id, user_id)
        return jsonify({"ok": True, "payload": payload})

    if request.method == "PUT":
        body = request.get_json(silent=True) or {}
        name = (body.get("name") or "").strip()
        description = (body.get("description") or "").strip()
        if not name:
            return json_error("Project name is required.")

        db_execute(
            "UPDATE projects SET name = ?, description = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (name, description, project_id),
        )
        db.commit()
        return jsonify({"ok": True})

    if project["owner_id"] != user_id:
        return json_error("Only the project owner can delete this project.", 403)

    db_execute("DELETE FROM projects WHERE id = ?", (project_id,))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/projects/<int:project_id>/members", methods=["POST"])
@login_required
def api_add_member(project_id):
    user_id = session["user_id"]
    db = get_db()
    project = db_execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if not project:
        return json_error("Project not found.", 404)
    if project["owner_id"] != user_id:
        return json_error("Only the project owner can add members.", 403)

    body = request.get_json(silent=True) or {}
    member_id = body.get("user_id")
    try:
        member_id = int(member_id)
    except (TypeError, ValueError):
        member_id = None
    if not member_id:
        return json_error("User id is required.")

    exists = db_execute(
        "SELECT 1 FROM project_members WHERE project_id = ? AND user_id = ?",
        (project_id, member_id),
    ).fetchone()
    if exists:
        return json_error("User already exists in project.")

    db_execute(
        "INSERT INTO project_members (project_id, user_id, role) VALUES (?, ?, 'member')",
        (project_id, member_id),
    )
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/projects/<int:project_id>/members/<int:member_id>", methods=["DELETE"])
@login_required
def api_remove_member(project_id, member_id):
    user_id = session["user_id"]
    db = get_db()
    project = db_execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if not project:
        return json_error("Project not found.", 404)
    if project["owner_id"] != user_id:
        return json_error("Only the project owner can remove members.", 403)
    if member_id == project["owner_id"]:
        return json_error("Owner cannot be removed.", 400)

    db_execute(
        "DELETE FROM project_members WHERE project_id = ? AND user_id = ?",
        (project_id, member_id),
    )
    db_execute(
        "UPDATE tasks SET assigned_to = NULL WHERE project_id = ? AND assigned_to = ?",
        (project_id, member_id),
    )
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/projects/<int:project_id>/tasks", methods=["POST"])
@login_required
def api_create_task(project_id):
    user_id = session["user_id"]
    if not user_can_access_project(project_id, user_id):
        return json_error("Access denied.", 403)

    body = request.get_json(silent=True) or {}
    title = (body.get("title") or "").strip()
    description = (body.get("description") or "").strip()
    due_date = (body.get("due_date") or "").strip() or None
    priority = body.get("priority", "medium")
    assigned_to = body.get("assigned_to")
    try:
        assigned_to = int(assigned_to) if assigned_to not in (None, "") else None
    except (TypeError, ValueError):
        assigned_to = None

    if not title:
        return json_error("Task title is required.")
    if priority not in {"low", "medium", "high"}:
        priority = "medium"

    db = get_db()
    if assigned_to:
        allowed = db_execute(
            "SELECT 1 FROM project_members WHERE project_id = ? AND user_id = ?",
            (project_id, assigned_to),
        ).fetchone()
        if not allowed:
            assigned_to = None

    db_execute(
        """
        INSERT INTO tasks (project_id, title, description, due_date, priority, assigned_to, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (project_id, title, description, due_date, priority, assigned_to, user_id),
    )
    db_execute("UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (project_id,))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/tasks/<int:task_id>", methods=["PUT", "DELETE"])
@login_required
def api_task(task_id):
    user_id = session["user_id"]
    db = get_db()
    task = db_execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        return json_error("Task not found.", 404)
    if not user_can_access_project(task["project_id"], user_id):
        return json_error("Access denied.", 403)

    if request.method == "DELETE":
        db_execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        db_execute("UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (task["project_id"],))
        db.commit()
        return jsonify({"ok": True})

    body = request.get_json(silent=True) or {}
    title = (body.get("title") or "").strip()
    description = (body.get("description") or "").strip()
    due_date = (body.get("due_date") or "").strip() or None
    priority = body.get("priority", "medium")
    status = body.get("status", "todo")
    assigned_to = body.get("assigned_to")
    try:
        assigned_to = int(assigned_to) if assigned_to not in (None, "") else None
    except (TypeError, ValueError):
        assigned_to = None

    if not title:
        return json_error("Task title is required.")
    if priority not in {"low", "medium", "high"}:
        priority = "medium"
    if status not in {"todo", "in_progress", "done"}:
        status = "todo"
    if assigned_to:
        allowed = db_execute(
            "SELECT 1 FROM project_members WHERE project_id = ? AND user_id = ?",
            (task["project_id"], assigned_to),
        ).fetchone()
        if not allowed:
            assigned_to = None

    db_execute(
        """
        UPDATE tasks
        SET title = ?, description = ?, due_date = ?, priority = ?, status = ?, assigned_to = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (title, description, due_date, priority, status, assigned_to, task_id),
    )
    db_execute("UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (task["project_id"],))
    db.commit()
    return jsonify({"ok": True})


@app.route("/tasks/<int:task_id>/move", methods=["POST"])
@app.route("/api/tasks/<int:task_id>/move", methods=["POST"])
@login_required
def move_task(task_id):
    user_id = session["user_id"]
    db = get_db()
    task = db_execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        return json_error("Task not found.", 404)
    if not user_can_access_project(task["project_id"], user_id):
        return json_error("Access denied.", 403)

    payload = request.get_json(silent=True) or {}
    new_status = payload.get("status")
    if new_status not in {"todo", "in_progress", "done"}:
        return json_error("Invalid status.")

    db_execute(
        "UPDATE tasks SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (new_status, task_id),
    )
    db_execute("UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (task["project_id"],))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/tasks/<int:task_id>/comments", methods=["POST"])
@login_required
def api_add_comment(task_id):
    user_id = session["user_id"]
    content = (request.get_json(silent=True) or {}).get("content", "").strip()
    if not content:
        return json_error("Comment cannot be empty.")

    db = get_db()
    task = db_execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        return json_error("Task not found.", 404)
    if not user_can_access_project(task["project_id"], user_id):
        return json_error("Access denied.", 403)

    db_execute(
        "INSERT INTO comments (task_id, user_id, content) VALUES (?, ?, ?)",
        (task_id, user_id, content),
    )
    db.commit()
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True)
