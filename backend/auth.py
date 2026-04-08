"""Azure AD JWT validation middleware.

Every protected endpoint depends on get_current_user().
Tokens are validated against the tenant's JWKS endpoint.
No token value is ever written to logs.
"""

import logging
from typing import Any

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from config import settings

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=True)

_JWKS_URI = (
    f"https://login.microsoftonline.com/{settings.azure_tenant_id}"
    "/discovery/v2.0/keys"
)
_ISSUER = (
    f"https://login.microsoftonline.com/{settings.azure_tenant_id}/v2.0"
)

# Simple in-process cache for JWKS to avoid fetching on every request.
_jwks_cache: dict[str, Any] | None = None


async def _get_jwks() -> dict[str, Any]:
    global _jwks_cache
    if _jwks_cache is None:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(_JWKS_URI)
            response.raise_for_status()
            _jwks_cache = response.json()
    return _jwks_cache


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict[str, Any]:
    """Validate the Bearer token and return the decoded claims."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        jwks = await _get_jwks()
        # Decode header to find the key id
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        # Find matching key in JWKS
        rsa_key: dict[str, str] = {}
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "n": key["n"],
                    "e": key["e"],
                }
                break

        if not rsa_key:
            logger.warning("No matching JWKS key found for kid=%s", kid)
            raise credentials_exception

        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=settings.azure_client_id,
            issuer=_ISSUER,
        )
        return payload

    except JWTError as exc:
        logger.warning("JWT validation failed: %s", type(exc).__name__)
        raise credentials_exception from exc
    except httpx.HTTPError as exc:
        logger.error("Failed to fetch JWKS: %s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable",
        ) from exc
