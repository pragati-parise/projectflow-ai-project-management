import os
import hashlib
import hmac
from datetime import datetime, timedelta, timezone

from jose import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import User

passwords = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer = HTTPBearer(auto_error=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_token(user_id: int) -> str:
    secret = os.getenv("JWT_SECRET_KEY", "")
    if not secret:
        raise RuntimeError("JWT_SECRET_KEY is missing from the environment")
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(user_id), "iat": now, "exp": now + timedelta(days=7)}, secret, algorithm="HS256")


def verify_password(plain_password: str, stored_hash: str) -> tuple[bool, bool]:
    """Check a new bcrypt hash or a Werkzeug hash from the former Flask app.

    The second result says the hash uses the old scheme and should be upgraded.
    """
    if stored_hash.startswith("scrypt:"):
        method, salt, expected = stored_hash.split("$", 2)
        _, n, r, p = method.split(":")
        candidate = hashlib.scrypt(plain_password.strip().encode(), salt=salt.encode(), n=int(n), r=int(r), p=int(p), maxmem=132 * 1024 * 1024, dklen=len(bytes.fromhex(expected)))
        return hmac.compare_digest(candidate.hex(), expected), True
    if stored_hash.startswith("pbkdf2:"):
        method, salt, expected = stored_hash.split("$", 2)
        _, algorithm, iterations = method.split(":")
        candidate = hashlib.pbkdf2_hmac(algorithm, plain_password.strip().encode(), salt.encode(), int(iterations), dklen=len(bytes.fromhex(expected)))
        return hmac.compare_digest(candidate.hex(), expected), True
    try:
        return passwords.verify(plain_password, stored_hash), False
    except Exception:
        return False, False


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if not credentials:
        raise HTTPException(status_code=401, detail="Sign in to continue.")
    try:
        payload = jwt.decode(credentials.credentials, os.environ["JWT_SECRET_KEY"], algorithms=["HS256"])
        user_id = int(payload["sub"])
    except Exception as error:
        raise HTTPException(status_code=401, detail=f"Invalid or expired login token: {error}") from error
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Account no longer exists.")
    return user


def accessible_project(db: Session, project_id: int, user: User):
    from .models import Project, ProjectMember

    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    if project.owner_id != user.id and not db.query(ProjectMember).filter_by(project_id=project_id, user_id=user.id).first():
        raise HTTPException(status_code=403, detail="You do not have access to this project.")
    return project
