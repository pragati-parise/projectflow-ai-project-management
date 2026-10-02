"""Copy existing ProjectFlow records from project_manager.db into PostgreSQL.

Run once before using the new app against an empty PostgreSQL database:
    python -m backend.migrate_sqlite [path-to-old-sqlite-file]
The source SQLite file is only read; account password hashes are preserved.
"""
import sqlite3
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import text

from .database import Base, SessionLocal, engine
from .models import Comment, Project, ProjectMember, Task, User


def as_date(value):
    return date.fromisoformat(value) if value else None


def as_datetime(value):
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def rows(connection, table):
    return [dict(row) for row in connection.execute(f"SELECT * FROM {table}").fetchall()]


def migrate(source_path: Path):
    if not source_path.exists():
        raise FileNotFoundError(f"SQLite database not found: {source_path}")
    Base.metadata.create_all(bind=engine)
    source = sqlite3.connect(source_path)
    source.row_factory = sqlite3.Row
    db = SessionLocal()
    try:
        if db.query(User).count():
            raise RuntimeError("Target PostgreSQL already contains users. Migration only runs into an empty database.")
        db.rollback()  # end the read transaction opened by the empty-target check
        with db.begin():
            for row in rows(source, "users"):
                db.add(User(id=row["id"], name=row["name"], email=row["email"], password_hash=row["password_hash"], created_at=as_datetime(row.get("created_at"))))
            for row in rows(source, "projects"):
                db.add(Project(id=row["id"], name=row["name"], description=row["description"] or "", owner_id=row["owner_id"],
                               created_at=as_datetime(row.get("created_at")), updated_at=as_datetime(row.get("updated_at"))))
            for row in rows(source, "project_members"):
                db.add(ProjectMember(id=row["id"], project_id=row["project_id"], user_id=row["user_id"], role=row["role"], added_at=as_datetime(row.get("added_at"))))
            for row in rows(source, "tasks"):
                db.add(Task(id=row["id"], project_id=row["project_id"], title=row["title"], description=row["description"] or "",
                            status=row["status"], priority=row["priority"], due_date=as_date(row["due_date"]),
                            assigned_to=row["assigned_to"], created_by=row["created_by"],
                            created_at=as_datetime(row.get("created_at")), updated_at=as_datetime(row.get("updated_at"))))
            if "comments" in {r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}:
                for row in rows(source, "comments"):
                    db.add(Comment(id=row["id"], task_id=row["task_id"], user_id=row["user_id"], content=row["content"], created_at=as_datetime(row.get("created_at"))))
        with engine.begin() as connection:
            for table in ("users", "projects", "project_members", "tasks", "comments"):
                connection.execute(text(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE((SELECT MAX(id) FROM {table}), 1), true)"))
        print("Migration complete. Existing IDs, password hashes, memberships, tasks, and comments were copied.")
    finally:
        db.close()
        source.close()


if __name__ == "__main__":
    default_source = Path(__file__).resolve().parent.parent / "project_manager.db"
    migrate(Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else default_source)
