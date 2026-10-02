import logging
import os
import re
import traceback
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth import accessible_project, create_token, current_user, get_db, passwords, verify_password
from .database import Base, engine
from .models import Comment, Project, ProjectMember, Task, User
from .schemas import (AssistantInput, BreakdownInput, CommentInput, LoginInput, MemberInput,
                      ProjectInput, TaskInput, UserCreate)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("projectflow")
APP_ENV = os.getenv("APP_ENV", "development").lower()
app = FastAPI(title="ProjectFlow API", version="1.0.0", debug=False)
origins = [value.strip() for value in os.getenv("FRONTEND_URL", "http://localhost:8000,http://127.0.0.1:8000").split(",") if value.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory=Path(__file__).resolve().parent.parent / "static"), name="static")


@app.on_event("startup")
def create_tables():
    Base.metadata.create_all(bind=engine)


@app.exception_handler(Exception)
async def debug_errors(request: Request, exc: Exception):
    logger.exception("Unhandled error for %s %s", request.method, request.url.path)
    if APP_ENV == "development":
        return JSONResponse(status_code=500, content={"detail": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()})
    return JSONResponse(status_code=500, content={"detail": "The server could not complete the request."})


def user_json(user):
    return {"id": user.id, "name": user.name, "email": user.email}


def task_json(db, task):
    assigned = db.get(User, task.assigned_to) if task.assigned_to else None
    creator = db.get(User, task.created_by)
    comments = db.query(Comment).filter_by(task_id=task.id).order_by(Comment.created_at).all()
    return {"id": task.id, "project_id": task.project_id, "title": task.title, "description": task.description,
            "status": task.status, "priority": task.priority, "due_date": task.due_date,
            "assigned_to": task.assigned_to, "assignee_name": assigned.name if assigned else None,
            "assignee_email": assigned.email if assigned else None, "creator_name": creator.name if creator else None,
            "comments": [{"id": c.id, "content": c.content, "author_name": c.user.name, "created_at": c.created_at} for c in comments]}


def project_json(db, project, user):
    tasks = db.query(Task).filter_by(project_id=project.id).all()
    total, done = len(tasks), sum(task.status == "done" for task in tasks)
    overdue = sum(task.due_date is not None and task.due_date < date.today() and task.status != "done" for task in tasks)
    members = db.query(ProjectMember).filter_by(project_id=project.id).all()
    return {"id": project.id, "name": project.name, "description": project.description, "owner_id": project.owner_id,
            "due_date": project.due_date, "status": project.status, "created_at": project.created_at,
            "updated_at": project.updated_at, "total_tasks": total, "done_tasks": done, "overdue_tasks": overdue,
            "progress": round(done * 100 / total) if total else 0,
            "members": [user_json(m.user) for m in members], "is_owner": project.owner_id == user.id}


@app.get("/", include_in_schema=False)
def frontend():
    project_root = Path(__file__).resolve().parent.parent
    built_frontend = project_root / "static" / "dist" / "index.html"
    if APP_ENV == "production" and built_frontend.exists():
        return FileResponse(built_frontend)
    return {"message": "ProjectFlow API is running", "docs": "/docs", "frontend_dev_url": "http://127.0.0.1:5173"}


@app.post("/auth/register", status_code=201)
def register(data: UserCreate, db: Session = Depends(get_db)):
    email = str(data.email).lower()
    if db.query(User).filter_by(email=email).first():
        raise HTTPException(status_code=409, detail="This email is already registered. Please sign in.")
    user = User(name=data.name.strip(), email=email, password_hash=passwords.hash(data.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="This email is already registered.") from error
    db.refresh(user)
    return {"token": create_token(user.id), "user": user_json(user)}


@app.post("/auth/login")
def login(data: LoginInput, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(email=str(data.email).lower()).first()
    if not user:
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    try:
        valid, legacy_hash = verify_password(data.password, user.password_hash)
    except (ValueError, TypeError):
        valid, legacy_hash = False, False
    if not valid:
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    if legacy_hash:
        user.password_hash = passwords.hash(data.password.strip())
        db.commit()
    return {"token": create_token(user.id), "user": user_json(user)}


@app.post("/auth/logout")
def logout(_user: User = Depends(current_user)):
    # JWTs are stateless; removing the token in the React client ends this session.
    return {"message": "Signed out."}


@app.get("/auth/me")
def me(user: User = Depends(current_user)):
    return user_json(user)


@app.get("/projects")
def list_projects(q: str = "", db: Session = Depends(get_db), user: User = Depends(current_user)):
    member_ids = db.query(ProjectMember.project_id).filter_by(user_id=user.id)
    query = db.query(Project).filter(or_(Project.owner_id == user.id, Project.id.in_(member_ids)))
    if q.strip():
        pattern = f"%{q.strip()}%"
        query = query.filter(or_(Project.name.ilike(pattern), Project.description.ilike(pattern)))
    return {"projects": [project_json(db, p, user) for p in query.order_by(Project.updated_at.desc()).all()]}


@app.post("/projects", status_code=201)
def create_project(data: ProjectInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    project = Project(name=data.name.strip(), description=data.description.strip(), due_date=data.due_date, status=data.status, owner_id=user.id)
    db.add(project)
    db.flush()
    db.add(ProjectMember(project_id=project.id, user_id=user.id, role="owner"))
    db.commit()
    db.refresh(project)
    return project_json(db, project, user)


@app.get("/projects/{project_id}")
def get_project(project_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    project = accessible_project(db, project_id, user)
    result = project_json(db, project, user)
    result["tasks"] = [task_json(db, t) for t in db.query(Task).filter_by(project_id=project_id).order_by(Task.created_at.desc()).all()]
    result["status_groups"] = {status: [task for task in result["tasks"] if task["status"] == status] for status in ("todo", "in_progress", "done")}
    # Only current team members are included; account discovery happens by email.
    return result


@app.put("/projects/{project_id}")
def update_project(project_id: int, data: ProjectInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    project = accessible_project(db, project_id, user)
    if project.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only the project owner can edit project details.")
    project.name, project.description, project.due_date, project.status = data.name.strip(), data.description.strip(), data.due_date, data.status
    db.commit()
    return project_json(db, project, user)


@app.delete("/projects/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    project = accessible_project(db, project_id, user)
    if project.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only the project owner can delete this project.")
    db.delete(project)
    db.commit()
    return {"message": "Project deleted."}


@app.get("/projects/{project_id}/members")
def list_members(project_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    accessible_project(db, project_id, user)
    return {"members": [user_json(m.user) for m in db.query(ProjectMember).filter_by(project_id=project_id).all()]}


@app.post("/projects/{project_id}/members", status_code=201)
def add_member(project_id: int, data: MemberInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    project = accessible_project(db, project_id, user)
    if project.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only the project owner can add members.")
    member = db.query(User).filter_by(email=str(data.email).lower()).first()
    if not member:
        raise HTTPException(status_code=404, detail="No account uses this email. Ask them to register first.")
    if db.query(ProjectMember).filter_by(project_id=project_id, user_id=member.id).first():
        raise HTTPException(status_code=409, detail="This user is already a project member.")
    db.add(ProjectMember(project_id=project_id, user_id=member.id, role="member"))
    db.commit()
    return {"member": user_json(member)}


@app.delete("/projects/{project_id}/members/{user_id}")
def remove_member(project_id: int, user_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    project = accessible_project(db, project_id, user)
    if project.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only the project owner can remove members.")
    if user_id == project.owner_id:
        raise HTTPException(status_code=400, detail="The project owner cannot be removed.")
    membership = db.query(ProjectMember).filter_by(project_id=project_id, user_id=user_id).first()
    if not membership:
        raise HTTPException(status_code=404, detail="Project member not found.")
    db.query(Task).filter_by(project_id=project_id, assigned_to=user_id).update({Task.assigned_to: None})
    db.delete(membership)
    db.commit()
    return {"message": "Member removed."}


@app.get("/projects/{project_id}/tasks")
def list_tasks(project_id: int, q: str = "", status: str = "", priority: str = "", db: Session = Depends(get_db), user: User = Depends(current_user)):
    accessible_project(db, project_id, user)
    query = db.query(Task).filter_by(project_id=project_id)
    if q.strip(): query = query.filter(or_(Task.title.ilike(f"%{q.strip()}%"), Task.description.ilike(f"%{q.strip()}%")))
    if status: query = query.filter_by(status=status)
    if priority: query = query.filter_by(priority=priority)
    return {"tasks": [task_json(db, task) for task in query.order_by(Task.created_at.desc()).all()]}


@app.get("/tasks/mine")
def list_my_tasks(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.query(Task, Project.name).join(Project, Project.id == Task.project_id).filter(Task.assigned_to == user.id).order_by(Task.due_date.asc().nullslast(), Task.created_at.desc()).all()
    return {"tasks": [{**task_json(db, task), "project_name": project_name} for task, project_name in rows]}


def validate_task_data(db, project_id, data):
    if data.status not in {"todo", "in_progress", "done"}:
        raise HTTPException(status_code=422, detail="Status must be todo, in_progress, or done.")
    if data.priority not in {"low", "medium", "high"}:
        raise HTTPException(status_code=422, detail="Priority must be low, medium, or high.")
    if data.assigned_to is not None and not db.query(ProjectMember).filter_by(project_id=project_id, user_id=data.assigned_to).first():
        raise HTTPException(status_code=422, detail="Assigned user must belong to this project.")


@app.post("/projects/{project_id}/tasks", status_code=201)
def create_task(project_id: int, data: TaskInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    accessible_project(db, project_id, user)
    validate_task_data(db, project_id, data)
    task = Task(project_id=project_id, title=data.title.strip(), description=data.description.strip(), status=data.status,
                priority=data.priority, due_date=data.due_date, assigned_to=data.assigned_to, created_by=user.id)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task_json(db, task)


@app.put("/tasks/{task_id}")
def update_task(task_id: int, data: TaskInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    task = db.get(Task, task_id)
    if not task: raise HTTPException(status_code=404, detail="Task not found.")
    accessible_project(db, task.project_id, user)
    validate_task_data(db, task.project_id, data)
    for field in ("title", "description", "status", "priority", "due_date", "assigned_to"):
        value = getattr(data, field)
        setattr(task, field, value.strip() if field in {"title", "description"} else value)
    db.commit()
    return task_json(db, task)


@app.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    task = db.get(Task, task_id)
    if not task: raise HTTPException(status_code=404, detail="Task not found.")
    accessible_project(db, task.project_id, user)
    db.delete(task)
    db.commit()
    return {"message": "Task deleted."}


@app.post("/tasks/{task_id}/comments", status_code=201)
def add_comment(task_id: int, data: CommentInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    task = db.get(Task, task_id)
    if not task: raise HTTPException(status_code=404, detail="Task not found.")
    accessible_project(db, task.project_id, user)
    comment = Comment(task_id=task_id, user_id=user.id, content=data.content.strip())
    db.add(comment)
    db.commit()
    return {"message": "Comment added."}


def gemini_answer(prompt: str) -> str:
    from google import genai
    key = os.getenv("GEMINI_API_KEY", "")
    if not key: raise HTTPException(status_code=503, detail="GEMINI_API_KEY is not configured. Add it to your backend environment.")
    try:
        # Keep the client alive for the complete request, then close it cleanly.
        with genai.Client(api_key=key) as client:
            try:
                response = client.models.generate_content(model="gemini-3.8-flash", contents=prompt)
            except Exception as error:
                # Google can temporarily return 503 when a model is overloaded.
                if getattr(error, "code", None) != 503:
                    raise
                logger.warning("Gemini 3.8 Flash is unavailable; retrying with Gemini 3.7 Flash.")
                response = client.models.generate_content(model="gemini-3.7-flash", contents=prompt)
        answer = response.text or "The AI returned an empty response. Please try again."
        return re.sub(r"\\?\*+", "", answer)
    except Exception as error:
        logger.exception("Gemini request failed")
        if APP_ENV == "development": raise HTTPException(status_code=502, detail=f"Gemini API request failed: {type(error).__name__}: {error}") from error
        raise HTTPException(status_code=502, detail="The AI assistant is temporarily unavailable.") from error


@app.post("/ai/task-breakdown")
def task_breakdown(data: BreakdownInput, _user: User = Depends(current_user)):
    text = gemini_answer("Act as a practical project manager. Break this requirement into 5 to 10 concise, actionable tasks. Return only a numbered list of task titles, one per line. Do not claim anything has been saved. Requirement:\n" + data.requirement)
    suggestions = [line.strip().lstrip("-•0123456789. )") for line in text.splitlines() if line.strip()]
    return {"suggestions": suggestions, "message": text}


@app.post("/ai/project-assistant")
def project_assistant(data: AssistantInput, db: Session = Depends(get_db), user: User = Depends(current_user)):
    context = ""
    if data.project_id is not None:
        project = accessible_project(db, data.project_id, user)
        tasks = db.query(Task).filter_by(project_id=project.id).all()
        context = f"Project: {project.name}\nDescription: {project.description}\nStatus: {project.status}\nTasks:\n" + "\n".join(
            f"- {t.title}; status={t.status}; priority={t.priority}; due={t.due_date}; assignee={t.assignee.name if t.assignee else 'unassigned'}" for t in tasks)
        if not tasks: context += "\nNo tasks exist yet."
    else:
        rows = (db.query(Task, Project.name)
                .join(Project, Project.id == Task.project_id)
                .filter(Task.assigned_to == user.id)
                .order_by(Task.due_date.asc().nullslast(), Task.created_at.desc())
                .all())
        context = f"User: {user.name}\nTasks assigned to this user across their workspace:\n" + "\n".join(
            f"- {task.title}; project={project_name}; status={task.status}; priority={task.priority}; due date={task.due_date or 'not set'}"
            for task, project_name in rows)
        if not rows:
            context += "\nNo tasks are currently assigned to this user."
    answer = gemini_answer("You are a practical project-management assistant. Use the supplied task and project facts to answer specifically. For focus questions, recommend a next step using task status, priority, deadline, and dependencies; explain assumptions when dependencies are unknown. If a due date is not set, say so. Never invent facts. If relevant facts are missing, state exactly what is missing and then offer clearly labeled general advice. Write plain text only: do not use Markdown, asterisks, or bold markers.\n\n" + context + "\n\nUser question: " + data.question)
    return {"answer": answer}


@app.get("/health")
def health():
    return {"status": "ok", "app": "ProjectFlow"}
