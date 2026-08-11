from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import User
from app.security import decode_session_token


def get_db():
    db=SessionLocal()
    try: yield db
    finally: db.close()


def current_user(request: Request, db: Session) -> User | None:
    payload=decode_session_token(request.cookies.get(settings.cookie_name))
    if not payload: return None
    return db.get(User, int(payload["uid"]))
