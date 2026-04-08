# EntraScribe

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688.svg)](https://fastapi.tiangolo.com/)

> Automatically generate professional descriptions for all Enterprise Applications in your Microsoft Entra ID tenant — powered by free AI (Groq / Gemini / Mistral) with automatic provider fallback. Secured via Azure AD. Open Source. Free to run.

---

## Features

- **Auto-generate** descriptions for all Entra ID Enterprise Apps via Microsoft Graph API
- **AI fallback chain**: Groq → Gemini → Mistral — uses whichever provider key you have
- **Write back** to Entra ID with a single click (or use Dry Run to preview only)
- **CSV export** for offline review or audit
- **Secure by default**: Azure AD token validation on every backend request
- **Docker-ready**: one command to run the full stack

---

## Prerequisites

- **Azure App Registration** with the following Microsoft Graph API permissions (Application type):
  - `Application.Read.All`
  - `Application.ReadWrite.All` (or `ServicePrincipalEndpoint.ReadWrite.All` for write)
- At least **one AI provider API key** (Groq is free at [console.groq.com](https://console.groq.com))
- Docker + Docker Compose

---

## Quick Start

```bash
# 1. Clone and enter the directory
git clone https://github.com/farpoint-tech/entrascribe.git
cd entrascribe

# 2. Configure your environment
cp .env.example .env
# Edit .env with your Azure credentials and at least one AI API key

# 3. Start everything
docker-compose up --build
```

Open **http://localhost:3000** → Sign in with Microsoft → done.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `AZURE_TENANT_ID` | Yes | Your Azure AD tenant ID |
| `AZURE_CLIENT_ID` | Yes | App Registration client ID |
| `AZURE_CLIENT_SECRET` | Yes | App Registration client secret |
| `GROQ_API_KEY` | At least one | Groq API key (free tier available) |
| `GEMINI_API_KEY` | At least one | Google Gemini API key |
| `MISTRAL_API_KEY` | At least one | Mistral API key |
| `ALLOWED_ORIGINS` | No | Comma-separated frontend origins (default: `http://localhost:3000`) |
| `SECRET_KEY` | Yes | Random 32-char string for internal use |
| `DRY_RUN` | No | Set `true` to skip Graph write calls (default: `false`) |

---

## Frontend Configuration

Before the first use, update `frontend/app.js` with your App Registration values:

```js
const CONFIG = {
  clientId: "your-client-id",   // App Registration client ID (NOT a secret)
  tenantId: "your-tenant-id",
  scopes: ["api://your-client-id/access_as_user"],
  // ...
};
```

These values are public (used by MSAL in the browser). The client secret lives only in `.env`.

---

## Dry Run Mode

Set `DRY_RUN=true` in `.env` to generate descriptions without writing them back to Entra ID. A yellow banner appears in the UI to confirm the mode is active. Useful for previewing results before committing.

---

## AI Provider Fallback

The system tries providers in order and skips any without a configured API key:

```
Groq (llama-3.3-70b-versatile)
  ↓ on rate limit or error
Gemini (gemini-1.5-flash)
  ↓ on rate limit or error
Mistral (mistral-small-latest)
  ↓ all exhausted
503 error returned
```

Each API response includes `provider_used` so you always know which provider was used.

---

## Architecture

```
frontend/          Vanilla HTML/CSS/JS + MSAL.js (served by nginx)
    ↓ Bearer token (Azure AD JWT)
backend/           FastAPI (Python 3.11)
    ├── auth.py    Validates Azure AD JWT on every request
    ├── graph.py   Microsoft Graph API (client_credentials flow)
    ├── ai.py      AI fallback chain (OpenAI-compatible clients)
    └── config.py  All settings from environment variables
```

---

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes with clear commit messages
4. Open a Pull Request

Please do not commit `.env` files or any secrets. See `.gitignore`.

---

## License

MIT — see [LICENSE](LICENSE).
