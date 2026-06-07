"""Session-based authentication service."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.exceptions import ConflictError, ForbiddenError, UnauthorizedError
from app.lib.password import check_password_breached, hash_password, verify_password
from app.models import EmailVerificationToken, PasswordResetToken, Session as UserSession, User


SESSION_COOKIE_NAME = "fls_session"
SESSION_DURATION_DAYS = 30


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session, user: User, ip_address: str | None = None, user_agent: str | None = None) -> tuple[UserSession, str]:
    token = secrets.token_urlsafe(32)
    session = UserSession(
        user_id=user.id,
        token=_hash_token(token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=SESSION_DURATION_DAYS),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session, token


def validate_session(db: Session, raw_token: str | None) -> tuple[UserSession, User] | None:
    if not raw_token:
        return None
    token_hash = _hash_token(raw_token)
    session = (
        db.query(UserSession)
        .filter(UserSession.token == token_hash, UserSession.expires_at > datetime.now(timezone.utc))
        .first()
    )
    if not session:
        return None
    user = db.query(User).filter(User.id == session.user_id, User.deleted_at.is_(None)).first()
    if not user:
        return None
    return session, user


def invalidate_session(db: Session, session_id: str) -> None:
    db.query(UserSession).filter(UserSession.id == session_id).delete()
    db.commit()


async def signup(db: Session, email: str, password: str, name: str) -> tuple[User, str]:
    if db.query(User).filter(User.email == email.lower()).first():
        raise ConflictError("Email already registered")
    if await check_password_breached(password):
        raise ForbiddenError("This password has appeared in a data breach. Please choose a different password.")

    user = User(
        email=email.lower(),
        password_hash=hash_password(password),
        name=name.strip(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    verify_token = secrets.token_hex(32)
    db.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=_hash_token(verify_token),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
    )
    db.commit()
    return user, verify_token


def login(db: Session, email: str, password: str) -> User:
    user = db.query(User).filter(User.email == email.lower(), User.deleted_at.is_(None)).first()
    if not user or not user.password_hash or not verify_password(user.password_hash, password):
        raise UnauthorizedError("Invalid email or password")
    return user


def request_password_reset(db: Session, email: str) -> str | None:
    user = db.query(User).filter(User.email == email.lower()).first()
    if not user:
        return None
    token = secrets.token_hex(32)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=_hash_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    db.commit()
    return token


def reset_password(db: Session, token: str, new_password: str) -> None:
    token_hash = _hash_token(token)
    record = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.expires_at > datetime.now(timezone.utc),
        )
        .first()
    )
    if not record:
        raise UnauthorizedError("Invalid or expired reset token")
    user = db.query(User).filter(User.id == record.user_id).first()
    if not user:
        raise UnauthorizedError("Invalid or expired reset token")
    user.password_hash = hash_password(new_password)
    db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id).delete()
    db.commit()


def verify_email(db: Session, token: str) -> None:
    token_hash = _hash_token(token)
    record = (
        db.query(EmailVerificationToken)
        .filter(
            EmailVerificationToken.token_hash == token_hash,
            EmailVerificationToken.expires_at > datetime.now(timezone.utc),
        )
        .first()
    )
    if not record:
        raise UnauthorizedError("Invalid or expired verification token")
    user = db.query(User).filter(User.id == record.user_id).first()
    if user:
        user.email_verified = datetime.now(timezone.utc)
    db.query(EmailVerificationToken).filter(EmailVerificationToken.user_id == record.user_id).delete()
    db.commit()


def require_verified_for_enforcement(user: User) -> None:
    if not user.email_verified:
        raise ForbiddenError("Email verification required before sending enforcement communications")
