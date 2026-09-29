"""Local authentication boundary and role authorization helpers."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from .db import SessionLocal, get_user_in_tenant
from .models import User
from .schemas import Role


def get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def current_user(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    session: Session = Depends(get_db),
) -> User:
    if not x_user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="X-User-Id is required")
    user = get_user_in_tenant(session, x_user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown or inactive user")
    return user


def require_roles(*allowed: Role):
    allowed_values = {role.value for role in allowed}

    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in allowed_values:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role is not authorized")
        return user

    return dependency


@dataclass(frozen=True)
class ServiceActor:
    user_id: str
    tenant_id: str
    role: Role


def actor_from_user(user: User) -> ServiceActor:
    return ServiceActor(user_id=user.id, tenant_id=user.tenant_id, role=Role(user.role))
