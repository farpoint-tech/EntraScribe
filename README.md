# EntraScribe

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688.svg)](https://fastapi.tiangolo.com/)

> Automatically generate professional descriptions for all Enterprise Applications in your Microsoft Entra ID tenant — powered by free AI (Groq / Gemini / Mistral) with automatic provider fallback. Secured via Azure AD. Open Source. Free to run.

---

## What This Tool Does

EntraScribe connects to your Microsoft Entra ID tenant, reads all Enterprise Applications, generates professional descriptions using AI, and writes them back — all with one click. No data leaves your tenant except to the AI provider you choose.

---

## Prerequisites

Before you start, make sure you have:

- [ ] **Admin access** to your Microsoft Entra ID tenant (Global Admin or Application Administrator)
- [ ] **Docker Desktop** installed → [docker.com/get-started](https://www.docker.com/get-started/)
- [ ] **Git** installed → [git-scm.com](https://git-scm.com/)
- [ ] At least **one free AI API key** (see Step 2 below)

---

## Step 1 — Azure App Registration (~15 minutes)

> You need to do this once. This tells Azure that EntraScribe is allowed to access your tenant.

### 1.1 Create the App Registration

1. Go to **[portal.azure.com](https://portal.azure.com)**
2. Navigate to **Entra ID → App registrations → New registration**
3. Fill in:
   ```
   Name:                    EntraScribe
   Supported account types: Accounts in this organizational directory only (Single tenant)
   Redirect URI:            Single-page application → http://localhost:3000
   ```
4. Click **Register**

### 1.2 Copy the IDs you need

On the App Registration overview page, copy these two values:

```
Application (client) ID  →  AZURE_CLIENT_ID
Directory (tenant) ID    →  AZURE_TENANT_ID
```

### 1.3 Create a Client Secret

1. Left menu → **Certificates & secrets → New client secret**
2. Description: `entrascribe-secret`, Expiry: 24 months
3. Click **Add**
4. **Copy the Value immediately** (only shown once!)

```
Value  →  AZURE_CLIENT_SECRET
```

### 1.4 Add API Permissions

1. Left menu → **API permissions → Add a permission → Microsoft Graph → Application permissions**
2. Search and add these two:
   - `Application.Read.All`
   - `Application.ReadWrite.All`
3. Click **Grant admin consent for [your tenant]** → Confirm

### 1.5 Expose an API scope (for frontend login)

1. Left menu → **Expose an API**
2. Click **Add** next to Application ID URI → Accept the default (`api://YOUR_CLIENT_ID`)
3. Click **Add a scope**:
   ```
   Scope name:             access_as_user
   Who can consent:        Admins and users
   Admin consent display:  Access EntraScribe
   State:                  Enabled
   ```
4. Click **Add scope**

---

## Step 2 — Get a Free AI API Key (~5 minutes)

You need at least one. Groq is recommended — it's the fastest and has a generous free tier.

| Provider | Sign up | Get key |
|---|---|---|
| **Groq** (recommended) | [console.groq.com](https://console.groq.com) | API Keys → Create API Key |
| Gemini | [aistudio.google.com](https://aistudio.google.com) | Get API Key |
| Mistral | [console.mistral.ai](https://console.mistral.ai) | API Keys → Create |

---

## Step 3 — Clone and Configure

```bash
# Clone the repo
git clone https://github.com/farpoint-tech/EntraScribe.git
cd EntraScribe

# Create your local config file
cp .env.example .env
```

Now open `.env` in any text editor and fill in your values:

```bash
# ── Microsoft Graph ───────────────────────────────
AZURE_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
AZURE_CLIENT_SECRET=your-secret-value-from-step-1.3

# ── AI Provider (fill in at least one) ───────────
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx

# ── App Settings ─────────────────────────────────
ALLOWED_ORIGINS=http://localhost:3000
SECRET_KEY=any-random-32-character-string-here
DRY_RUN=true
```

> **DRY_RUN=true** means the tool will generate descriptions but NOT write them back to Entra ID yet. Change to `false` when you're ready to go live.

---

## Step 4 — Configure the Frontend

Open `frontend/app.js` in a text editor. Find lines 12–15 and replace the placeholders:

```js
const CONFIG = {
  clientId: "YOUR_CLIENT_ID_HERE",   // ← paste AZURE_CLIENT_ID
  tenantId: "YOUR_TENANT_ID_HERE",   // ← paste AZURE_TENANT_ID
  scopes: ["api://YOUR_CLIENT_ID_HERE/access_as_user"],  // ← paste AZURE_CLIENT_ID twice
  ...
};
```

> These are **not secrets** — they are public values that MSAL needs in the browser to initiate login. Never put your `AZURE_CLIENT_SECRET` here.

---

## Step 5 — Start the App

```bash
docker-compose up --build
```

Wait until you see:
```
backend   | INFO:     Application startup complete.
```

Then open **[http://localhost:3000](http://localhost:3000)** in your browser.

---

## Step 6 — First Use

1. Click **Sign in with Microsoft**
2. Log in with your Entra ID account
3. Click **Refresh** — your Enterprise Apps will load
4. Select apps (or select all with the checkbox)
5. Click **Generate Descriptions** — AI descriptions appear in the table
6. Review the generated text
7. When happy: set `DRY_RUN=false` in `.env`, restart (`docker-compose restart`), then click **Write to Entra ID**

---

## Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `AZURE_TENANT_ID` | Yes | Entra ID → Overview → Directory (tenant) ID |
| `AZURE_CLIENT_ID` | Yes | App Registration → Application (client) ID |
| `AZURE_CLIENT_SECRET` | Yes | App Registration → Certificates & secrets → Value |
| `GROQ_API_KEY` | At least one | From console.groq.com |
| `GEMINI_API_KEY` | At least one | From aistudio.google.com |
| `MISTRAL_API_KEY` | At least one | From console.mistral.ai |
| `ALLOWED_ORIGINS` | No | Frontend URL (default: `http://localhost:3000`) |
| `SECRET_KEY` | Yes | Any random 32-character string |
| `DRY_RUN` | No | `true` = preview only, `false` = write to Entra ID |

---

## Dry Run Mode

When `DRY_RUN=true` (default), the app generates descriptions and shows them in the UI but makes **no changes** to your Entra ID tenant. A yellow banner confirms this mode is active. Use this to review results before going live.

---

## AI Provider Fallback

The system automatically tries providers in order. If one fails or hits a rate limit, it moves to the next:

```
Groq → Gemini → Mistral → error if all fail
```

Each response shows which provider was used (`provider_used` field).

---

## Troubleshooting

| Problem | Solution |
|---|---|
| Login fails / redirect error | Check Redirect URI in Azure is exactly `http://localhost:3000` and type is "Single-page application" |
| 401 Unauthorized on all API calls | Check `AZURE_CLIENT_ID` in `frontend/app.js` matches `.env` |
| Apps don't load | Verify `Application.Read.All` permission has admin consent granted |
| Write fails | Verify `Application.ReadWrite.All` has admin consent, and `DRY_RUN=false` |
| AI error 503 | At least one AI API key must be set in `.env` |
| Docker not starting | Run `docker-compose logs backend` to see the error |

---

## Architecture

```
http://localhost:3000    Vanilla HTML/JS + MSAL.js (nginx)
         ↓ Azure AD Bearer token on every request
http://localhost:8000    FastAPI backend (Python 3.11)
         ├── Validates Azure AD JWT (auth.py)
         ├── Reads/writes Enterprise Apps via Graph API (graph.py)
         └── Generates descriptions via AI fallback chain (ai.py)
```

---

## Security Notes

- Your `AZURE_CLIENT_SECRET` and AI API keys are **only in `.env`** — never in the frontend or committed to Git
- `.env` is in `.gitignore` — it will never be pushed to GitHub
- Azure AD token is validated on **every** backend request
- Use `DRY_RUN=true` until you're confident in the generated descriptions

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes with clear commit messages
4. Open a Pull Request

Do not commit `.env` files or any secrets.

---

## License

MIT — see [LICENSE](LICENSE).
