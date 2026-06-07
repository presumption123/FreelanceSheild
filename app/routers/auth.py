"""Authentication routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import clear_session_cookie, get_current_user, set_session_cookie
from app.models import User
from app.schemas import LoginRequest, MessageResponse, PasswordResetConfirmRequest, PasswordResetRequest, SignupRequest, UserResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=MessageResponse)
async def signup(data: SignupRequest, response: Response, db: Annotated[Session, Depends(get_db)]):
    user, verify_token = await auth_service.signup(db, data.email, data.password, data.name)
    session, token = auth_service.create_session(db, user)
    set_session_cookie(response, token)
    return MessageResponse(
        message="Account created. Please verify your email.",
        data={"userId": user.id, "verificationToken": verify_token},
    )


@router.post("/login", response_model=UserResponse)
def login(data: LoginRequest, response: Response, db: Annotated[Session, Depends(get_db)]):
    user = auth_service.login(db, data.email, data.password)
    _, token = auth_service.create_session(db, user)
    set_session_cookie(response, token)
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        plan=user.plan.value,
        jurisdictionCode=user.jurisdiction_code,
        emailVerified=user.email_verified is not None,
        businessName=user.business_name,
    )


@router.post("/logout", response_model=MessageResponse)
def logout(response: Response):
    clear_session_cookie(response)
    return MessageResponse(message="Logged out")


@router.get("/me", response_model=UserResponse)
def me(user: Annotated[User, Depends(get_current_user)]):
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        plan=user.plan.value,
        jurisdictionCode=user.jurisdiction_code,
        emailVerified=user.email_verified is not None,
        businessName=user.business_name,
    )


@router.post("/verify-email", response_model=MessageResponse)
def verify_email(token: str, db: Annotated[Session, Depends(get_db)]):
    auth_service.verify_email(db, token)
    return MessageResponse(message="Email verified successfully")


@router.post("/password-reset", response_model=MessageResponse)
def password_reset(data: PasswordResetRequest, db: Annotated[Session, Depends(get_db)]):
    token = auth_service.request_password_reset(db, data.email)
    return MessageResponse(
        message="If that email exists, a reset link has been sent.",
        data={"token": token} if token else None,
    )


@router.post("/password-reset/confirm", response_model=MessageResponse)
def password_reset_confirm(data: PasswordResetConfirmRequest, db: Annotated[Session, Depends(get_db)]):
    auth_service.reset_password(db, data.token, data.password)
    return MessageResponse(message="Password updated successfully")
