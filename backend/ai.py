"""AI description generation with automatic provider fallback.

Provider chain: Groq → Gemini → Mistral
- Providers without an API key are skipped.
- On RateLimitError, the next provider is tried automatically.
- All responses include `description` and `provider_used` fields.
"""

import logging
import os
from typing import Any

from fastapi import HTTPException
from openai import AsyncOpenAI, RateLimitError

from config import settings

logger = logging.getLogger(__name__)

PROVIDER_CHAIN = [
    {
        "name": "groq",
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
        "env": "GROQ_API_KEY",
    },
    {
        "name": "gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "model": "gemini-1.5-flash",
        "env": "GEMINI_API_KEY",
    },
    {
        "name": "mistral",
        "base_url": "https://api.mistral.ai/v1",
        "model": "mistral-small-latest",
        "env": "MISTRAL_API_KEY",
    },
]

_SYSTEM_PROMPT = (
    "Generate a clear, concise, professional description (max 250 characters) "
    "for the following Microsoft Entra ID Enterprise Application.\n\n"
    "Rules:\n"
    "- Explain what the app does and its business purpose\n"
    "- Written for IT administrators and end users\n"
    "- No marketing language — factual and specific\n"
    "- Respond with description text ONLY"
)


def _build_user_prompt(app: dict[str, Any]) -> str:
    return (
        f"App Name:      {app.get('displayName', 'Unknown')}\n"
        f"Publisher:     {app.get('publisherName', 'Unknown')}\n"
        f"Homepage:      {app.get('homepage', 'N/A')}\n"
        f"Existing Info: {app.get('notes', 'N/A')}"
    )


def _get_api_key(provider: dict[str, str]) -> str:
    """Return API key from settings (not from os.environ directly)."""
    env_field = provider["env"].lower()  # e.g. GROQ_API_KEY → groq_api_key
    return getattr(settings, env_field, "")


def get_provider_status() -> list[dict[str, Any]]:
    """Return availability status for all providers."""
    return [
        {"name": p["name"], "available": bool(_get_api_key(p))}
        for p in PROVIDER_CHAIN
    ]


async def generate_description(app: dict[str, Any]) -> dict[str, str]:
    """Generate an AI description for an Enterprise App.

    Returns:
        {"description": str, "provider_used": str}

    Raises:
        HTTPException(503) if all providers are exhausted.
    """
    user_prompt = _build_user_prompt(app)
    last_error: Exception | None = None

    for provider in PROVIDER_CHAIN:
        api_key = _get_api_key(provider)
        if not api_key:
            logger.debug("Skipping provider %s: no API key configured", provider["name"])
            continue

        try:
            client = AsyncOpenAI(
                base_url=provider["base_url"],
                api_key=api_key,
            )
            response = await client.chat.completions.create(
                model=provider["model"],
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=100,
                temperature=0.3,
            )
            description = response.choices[0].message.content.strip()
            # Enforce 250-char limit as a safeguard
            description = description[:250]
            logger.info(
                "Generated description via %s for app '%s'",
                provider["name"],
                app.get("displayName", "?"),
            )
            return {"description": description, "provider_used": provider["name"]}

        except RateLimitError as exc:
            logger.warning("Rate limit hit on provider %s, trying next", provider["name"])
            last_error = exc
            continue
        except Exception as exc:
            logger.error(
                "Unexpected error from provider %s: %s",
                provider["name"],
                type(exc).__name__,
            )
            last_error = exc
            continue

    raise HTTPException(
        status_code=503,
        detail={
            "error": "all_providers_exhausted",
            "message": "All AI providers failed or are unavailable. Check your API keys.",
        },
    )
