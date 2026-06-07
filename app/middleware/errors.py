"""Global error handlers."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.exceptions import AppError


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError):
        detail: dict | str = {"error": exc.message}
        if hasattr(exc, "required_plan") and exc.required_plan:
            detail = {
                "error": exc.message,
                "requiredPlan": exc.required_plan,
                "upgradeUrl": "/settings/billing",
            }
        return JSONResponse(status_code=exc.status_code, content={"detail": detail})

    @app.exception_handler(ValueError)
    async def handle_value_error(_request: Request, exc: ValueError):
        return JSONResponse(status_code=400, content={"detail": {"error": str(exc)}})
