"""Authentication middleware and dependencies."""

from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.constants.plans import require_plan
from app.database import get_db
from app.models import Plan, User
from app.services.auth_service import SESSION_COOKIE_NAME, create_session, validate_session


async def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    fls_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> User:
    result = validate_session(db, fls_session)
    if not result:
        raise HTTPException(status_code=401, detail={"error": "Unauthorized"})
    _, user = result
    return user


async def get_optional_user(
    db: Annotated[Session, Depends(get_db)],
    fls_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> User | None:
    result = validate_session(db, fls_session)
    if not result:
        return None
    _, user = result
    return user


def set_session_cookie(response: Response, token: str) -> None:
    from app.config import get_settings

    settings = get_settings()
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        path="/",
        max_age=30 * 24 * 60 * 60,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")


def require_plan_dependency(min_plan: Plan):
    async def _dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        require_plan(user, min_plan)
        return user

    return _dependency
