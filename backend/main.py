"""EntraScribe — FastAPI backend.

All endpoints require a valid Azure AD Bearer token.
Rate limiting is applied per endpoint via slowapi.
AI API keys are never exposed to the frontend.
"""

import csv
import io
import logging
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from ai import generate_description, get_provider_status
from auth import get_current_user
from config import settings
from graph import get_service_principals, update_service_principal

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# ── Rate limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="EntraScribe",
    description="Auto-generate descriptions for Microsoft Entra ID Enterprise Apps.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ──────────────────────────────────────────────────────────────────────
origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


# ── Request / Response models ─────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    app_ids: list[str]


class GenerateResult(BaseModel):
    id: str
    displayName: str
    description: str
    provider_used: str


class WriteUpdate(BaseModel):
    id: str
    description: str


class WriteRequest(BaseModel):
    updates: list[WriteUpdate]


class WriteResult(BaseModel):
    id: str
    success: bool
    dry_run: bool


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/api/status")
@limiter.limit("60/minute")
async def get_status(
    request: Request,
    _user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Return active AI provider status and dry_run flag."""
    return {
        "providers": get_provider_status(),
        "dry_run": settings.dry_run,
    }


@app.get("/api/apps")
@limiter.limit("30/minute")
async def list_apps(
    request: Request,
    _user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Return all Enterprise Applications from the tenant."""
    apps = await get_service_principals()
    return {"apps": apps, "count": len(apps)}


@app.post("/api/apps/generate")
@limiter.limit("60/minute")
async def generate_descriptions(
    request: Request,
    body: GenerateRequest,
    _user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Generate AI descriptions for the given app IDs.

    Fetches app metadata from Graph, then calls the AI fallback chain.
    Always returns description + provider_used per app.
    """
    if not body.app_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="app_ids is empty")

    all_apps = await get_service_principals()
    app_map = {a["id"]: a for a in all_apps}

    results: list[dict[str, Any]] = []
    for app_id in body.app_ids:
        app = app_map.get(app_id)
        if not app:
            logger.warning("app_id not found: %s", app_id)
            results.append(
                {
                    "id": app_id,
                    "displayName": "Unknown",
                    "description": "",
                    "provider_used": "",
                    "error": "app_not_found",
                }
            )
            continue

        generated = await generate_description(app)
        results.append(
            {
                "id": app_id,
                "displayName": app.get("displayName", ""),
                "description": generated["description"],
                "provider_used": generated["provider_used"],
            }
        )

    return {"results": results}


@app.post("/api/apps/write")
@limiter.limit("10/minute")
async def write_descriptions(
    request: Request,
    body: WriteRequest,
    _user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Write descriptions back to Entra ID via Graph PATCH.

    Skipped (dry_run=true returned) when DRY_RUN env var is set.
    """
    if not body.updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="updates is empty")

    results: list[dict[str, Any]] = []
    for update in body.updates:
        written = await update_service_principal(update.id, update.description)
        results.append(
            {
                "id": update.id,
                "success": True,
                "dry_run": not written,
            }
        )

    return {"results": results}


@app.get("/api/apps/export")
@limiter.limit("10/minute")
async def export_csv(
    request: Request,
    _user: dict[str, Any] = Depends(get_current_user),
) -> StreamingResponse:
    """Export all apps as a CSV with id, displayName, description, publisherName."""
    apps = await get_service_principals()

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["id", "displayName", "description", "publisherName", "homepage"],
        extrasaction="ignore",
    )
    writer.writeheader()
    for app in apps:
        writer.writerow(
            {
                "id": app.get("id", ""),
                "displayName": app.get("displayName", ""),
                "description": app.get("description", ""),
                "publisherName": app.get("publisherName", ""),
                "homepage": app.get("homepage", ""),
            }
        )

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=entrascribe-export.csv"},
    )
