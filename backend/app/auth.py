import hashlib
import secrets
from datetime import timedelta

from fastapi import Depends, HTTPException, Request, Response
from pwdlib import PasswordHash
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Activity, AuthSession, User, now

passwords = PasswordHash.recommended()
DUMMY_HASH = passwords.hash("constant-time-invalid-password")
COOKIE = "leetbug_session"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def utc(dt):
    return dt.replace(tzinfo=now().tzinfo) if dt.tzinfo is None else dt


def record_activity(db: Session, user: User):
    key = {"user_id": user.id, "day": now().date()}
    if not db.get(Activity, key):
        try:
            with db.begin_nested():
                db.add(Activity(**key))
                db.flush()
        except IntegrityError:
            pass
        db.commit()


def optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    token = request.cookies.get(COOKIE)
    session = db.get(AuthSession, hash_token(token)) if token else None
    if not session or utc(session.expires_at) <= now():
        return None
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        if not secrets.compare_digest(request.headers.get("X-CSRF-Token", ""), session.csrf_token):
            raise HTTPException(403, "Your session could not be verified. Refresh and try again.")
    request.state.auth_session = session
    return db.get(User, session.user_id)


def current_user(user: User | None = Depends(optional_user)) -> User:
    if not user:
        raise HTTPException(401, "Sign in to continue.")
    return user


def public_user(user: User) -> dict:
    return {"id": user.id, "email": user.email, "username": user.username,
            "bio": user.bio, "created_at": user.created_at}


def start_session(db: Session, response: Response, user: User):
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    db.execute(delete(AuthSession).where(AuthSession.expires_at < now()))
    db.add(AuthSession(token_hash=hash_token(token), user_id=user.id, csrf_token=csrf,
                       expires_at=now() + timedelta(days=settings.session_days)))
    db.commit()
    record_activity(db, user)
    response.set_cookie(COOKIE, token, max_age=settings.session_days * 86400, httponly=True,
                        secure=settings.cookie_secure, samesite="lax", path="/api")
    return {"user": public_user(user), "csrf_token": csrf}

