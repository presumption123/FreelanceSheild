"""Web UI routes — dashboard and client portal pages."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["web"])
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "web" / "templates"))


@router.get("/app", response_class=HTMLResponse)
@router.get("/app/{path:path}", response_class=HTMLResponse)
async def dashboard(_request: Request, path: str = ""):
    return templates.TemplateResponse("dashboard.html", {"request": _request})


@router.get("/portal/{invoice_id}/view", response_class=HTMLResponse)
async def portal_page(request: Request, invoice_id: str):
    token = request.query_params.get("token", "")
    return templates.TemplateResponse(
        "portal.html",
        {"request": request, "invoice_id": invoice_id, "token": token},
    )
