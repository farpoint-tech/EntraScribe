"""Microsoft Graph API integration.

Uses client_credentials flow to obtain a Graph token (separate from the
user's delegated token used for authentication).

DRY_RUN=true skips all write (PATCH) operations.
"""

import logging
from typing import Any

import httpx

from config import settings

logger = logging.getLogger(__name__)

_GRAPH_BASE = "https://graph.microsoft.com/v1.0"
_TOKEN_URL = (
    f"https://login.microsoftonline.com/{settings.azure_tenant_id}/oauth2/v2.0/token"
)
_SP_SELECT = (
    "id,displayName,description,notes,homepage,publisherName,appId,tags,servicePrincipalType"
)

# Simple in-process token cache
_graph_token_cache: dict[str, Any] | None = None


async def _get_graph_token() -> str:
    """Obtain a Graph API access token via client_credentials flow."""
    global _graph_token_cache
    import time

    if _graph_token_cache and _graph_token_cache.get("expires_at", 0) > time.time() + 60:
        return _graph_token_cache["access_token"]

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            _TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": settings.azure_client_id,
                "client_secret": settings.azure_client_secret,
                "scope": "https://graph.microsoft.com/.default",
            },
        )
        response.raise_for_status()
        data = response.json()

    import time as _time
    _graph_token_cache = {
        "access_token": data["access_token"],
        "expires_at": _time.time() + data.get("expires_in", 3600),
    }
    return _graph_token_cache["access_token"]


async def get_service_principals() -> list[dict[str, Any]]:
    """Return all service principals (Enterprise Apps) from the tenant.

    Paginates automatically. Excludes Microsoft first-party apps
    (tag 'WindowsAzureActiveDirectoryIntegratedApp' only; publisherName
    filtering is left to the caller via the UI).
    """
    token = await _get_graph_token()
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{_GRAPH_BASE}/servicePrincipals?$select={_SP_SELECT}&$top=999"

    results: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=30) as client:
        while url:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            results.extend(data.get("value", []))
            url = data.get("@odata.nextLink")

    logger.info("Fetched %d service principals from Graph", len(results))
    return results


async def update_service_principal(sp_id: str, description: str) -> bool:
    """Write a description back to a service principal.

    Returns True on success, False if DRY_RUN is active.
    Raises httpx.HTTPStatusError on Graph API error.
    """
    if settings.dry_run:
        logger.info("DRY_RUN: skipping PATCH for sp_id=%s", sp_id)
        return False

    token = await _get_graph_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    url = f"{_GRAPH_BASE}/servicePrincipals/{sp_id}"

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.patch(url, headers=headers, json={"description": description})
        response.raise_for_status()

    logger.info("Updated description for sp_id=%s", sp_id)
    return True
