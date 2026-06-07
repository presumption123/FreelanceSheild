"""Shared application exceptions."""

from fastapi import HTTPException, status


class AppError(Exception):
    """Base application error."""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ConflictError(AppError):
    def __init__(self, message: str):
        super().__init__(message, status_code=409)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=404)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(message, status_code=401)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Forbidden"):
        super().__init__(message, status_code=403)


class InvalidStateTransitionError(AppError):
    def __init__(self, message: str):
        super().__init__(message, status_code=422)


class PlanLimitError(AppError):
    def __init__(self, message: str, required_plan: str | None = None):
        super().__init__(message, status_code=403)
        self.required_plan = required_plan


def app_error_handler(_request, exc: AppError):
    detail: dict | str = {"error": exc.message}
    if isinstance(exc, PlanLimitError) and exc.required_plan:
        detail = {"error": exc.message, "requiredPlan": exc.required_plan, "upgradeUrl": "/settings/billing"}
    return HTTPException(status_code=exc.status_code, detail=detail)
