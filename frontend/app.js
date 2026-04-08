/**
 * EntraScribe — Frontend App
 *
 * Uses MSAL.js v3 for Azure AD authentication.
 * All API calls include the Bearer token from MSAL.
 * AI API keys are NEVER present in the frontend.
 *
 * Configure AZURE_CLIENT_ID and AZURE_TENANT_ID below
 * (these are NOT secrets — they are public app registration values).
 */

// ── Configuration ────────────────────────────────────────────────────────────
// These values are the App Registration client ID and tenant ID.
// They are intentionally public (used by MSAL in the browser).
// The client SECRET is only stored server-side in .env.
const CONFIG = {
  clientId: window.AZURE_CLIENT_ID || "YOUR_CLIENT_ID_HERE",
  tenantId: window.AZURE_TENANT_ID || "YOUR_TENANT_ID_HERE",
  backendUrl: window.BACKEND_URL || "http://localhost:8000",
  // Scopes requested from the user — matches the backend API audience
  scopes: ["api://YOUR_CLIENT_ID_HERE/access_as_user"],
};

// ── MSAL setup ───────────────────────────────────────────────────────────────
const msalConfig = {
  auth: {
    clientId: CONFIG.clientId,
    authority: `https://login.microsoftonline.com/${CONFIG.tenantId}`,
    redirectUri: window.location.origin,
  },
  cache: {
    cacheLocation: "sessionStorage",
    storeAuthStateInCookie: false,
  },
};

const msalInstance = new msal.PublicClientApplication(msalConfig);

// ── State ─────────────────────────────────────────────────────────────────────
let appsData = [];          // full list from /api/apps
let generatedMap = {};      // { app_id: {description, provider_used} }
let currentUser = null;

// ── Logging ───────────────────────────────────────────────────────────────────
function log(message, level = "info") {
  const ts = new Date().toLocaleTimeString("en-GB");
  const entry = document.createElement("div");
  entry.className = `log-entry ${level}`;
  entry.innerHTML = `<span class="ts">${ts}</span>${message}`;

  ["log-panel", "log-panel-full"].forEach((id) => {
    const panel = document.getElementById(id);
    if (panel) {
      panel.appendChild(entry.cloneNode(true));
      panel.scrollTop = panel.scrollHeight;
    }
  });
}

// ── API helper ────────────────────────────────────────────────────────────────
async function apiFetch(path, options = {}) {
  const token = await getAccessToken();
  const res = await fetch(`${CONFIG.backendUrl}${path}`, {
    ...options,
    headers: {
      "Authorization": `Bearer ${token}`,
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res;
}

async function getAccessToken() {
  const accounts = msalInstance.getAllAccounts();
  if (!accounts.length) throw new Error("Not authenticated");
  try {
    const result = await msalInstance.acquireTokenSilent({
      scopes: CONFIG.scopes,
      account: accounts[0],
    });
    return result.accessToken;
  } catch {
    // Silent refresh failed — interactive popup
    const result = await msalInstance.acquireTokenPopup({ scopes: CONFIG.scopes });
    return result.accessToken;
  }
}

// ── Auth ──────────────────────────────────────────────────────────────────────
async function init() {
  await msalInstance.initialize();

  // Handle redirect response (in case redirect flow is used)
  await msalInstance.handleRedirectPromise();

  const accounts = msalInstance.getAllAccounts();
  if (accounts.length > 0) {
    currentUser = accounts[0];
    showApp();
  } else {
    showLogin();
  }
}

function showLogin() {
  document.getElementById("page-login").style.display = "flex";
  document.getElementById("app-shell").style.display = "none";
}

function showApp() {
  document.getElementById("page-login").style.display = "none";
  document.getElementById("app-shell").style.display = "flex";
  document.getElementById("user-name").textContent = currentUser.name || currentUser.username;
  document.getElementById("user-email").textContent = currentUser.username;
  loadStatus();
  loadApps();
}

document.getElementById("btn-login").addEventListener("click", async () => {
  try {
    const result = await msalInstance.loginPopup({ scopes: CONFIG.scopes });
    currentUser = result.account;
    showApp();
  } catch (e) {
    log(`Login failed: ${e.message}`, "error");
  }
});

document.getElementById("btn-signout").addEventListener("click", () => {
  msalInstance.logoutPopup();
});

// ── Navigation ────────────────────────────────────────────────────────────────
document.querySelectorAll(".sidebar-nav a").forEach((link) => {
  link.addEventListener("click", (e) => {
    e.preventDefault();
    document.querySelectorAll(".sidebar-nav a").forEach((a) => a.classList.remove("active"));
    link.classList.add("active");
    const view = link.dataset.view;
    document.getElementById("view-dashboard").style.display = view === "dashboard" ? "block" : "none";
    document.getElementById("view-log").style.display = view === "log" ? "block" : "none";
    document.getElementById("view-title").textContent =
      view === "dashboard" ? "Enterprise Applications" : "Activity Log";
  });
});

// ── Status ────────────────────────────────────────────────────────────────────
async function loadStatus() {
  try {
    const res = await apiFetch("/api/status");
    const data = await res.json();
    const badge = document.getElementById("provider-badge");
    const active = data.providers.find((p) => p.available);
    if (active) {
      badge.textContent = `AI: ${active.name}`;
      badge.className = "provider-badge";
    } else {
      badge.textContent = "AI: no providers";
      badge.className = "provider-badge offline";
    }
    if (data.dry_run) {
      document.getElementById("dry-run-banner").style.display = "flex";
    }
  } catch (e) {
    log(`Failed to load status: ${e.message}`, "warning");
  }
}

// ── Apps ──────────────────────────────────────────────────────────────────────
async function loadApps() {
  log("Fetching Enterprise Applications from Entra ID...", "info");
  setButtonsEnabled(false);
  try {
    const res = await apiFetch("/api/apps");
    const data = await res.json();
    appsData = data.apps;
    generatedMap = {};
    renderTable(appsData);
    log(`Loaded ${appsData.length} applications`, "success");
  } catch (e) {
    log(`Failed to load apps: ${e.message}`, "error");
    document.getElementById("apps-tbody").innerHTML = `
      <tr><td colspan="6">
        <div class="empty-state">
          <h3>Failed to load applications</h3>
          <p>${e.message}</p>
        </div>
      </td></tr>`;
  }
}

function renderTable(apps) {
  const tbody = document.getElementById("apps-tbody");
  if (!apps.length) {
    tbody.innerHTML = `<tr><td colspan="6"><div class="empty-state">
      <h3>No applications found</h3><p>No Enterprise Apps returned from Entra ID.</p>
    </div></td></tr>`;
    return;
  }

  tbody.innerHTML = apps
    .map((app) => {
      const gen = generatedMap[app.id];
      const descCell = gen
        ? `<span class="description-cell has-desc">${escHtml(gen.description)}</span>`
        : `<span class="description-cell">${escHtml(app.description || "—")}</span>`;
      const statusBadge = gen
        ? `<span class="status-badge generated">Generated (${escHtml(gen.provider_used)})</span>`
        : app.description
        ? `<span class="status-badge written">Has description</span>`
        : "";
      return `
      <tr data-id="${escHtml(app.id)}">
        <td><input type="checkbox" class="app-checkbox" data-id="${escHtml(app.id)}" /></td>
        <td>
          <div class="app-name">${escHtml(app.displayName || "—")}</div>
          <div class="app-publisher">${escHtml(app.appId || "")}</div>
        </td>
        <td>${escHtml(app.publisherName || "—")}</td>
        <td>${escHtml(app.description || "—")}</td>
        <td>${descCell}</td>
        <td>${statusBadge}</td>
      </tr>`;
    })
    .join("");

  attachCheckboxListeners();
}

function attachCheckboxListeners() {
  document.querySelectorAll(".app-checkbox").forEach((cb) => {
    cb.addEventListener("change", updateSelectionCount);
  });
  updateSelectionCount();
}

function updateSelectionCount() {
  const checked = document.querySelectorAll(".app-checkbox:checked");
  const count = checked.length;
  document.getElementById("selected-count").textContent =
    count > 0 ? `${count} selected` : "";
  document.getElementById("btn-generate").disabled = count === 0;
  document.getElementById("btn-write").disabled = count === 0;
}

function getSelectedIds() {
  return Array.from(document.querySelectorAll(".app-checkbox:checked")).map(
    (cb) => cb.dataset.id
  );
}

document.getElementById("select-all").addEventListener("change", (e) => {
  document.querySelectorAll(".app-checkbox").forEach((cb) => {
    cb.checked = e.target.checked;
  });
  updateSelectionCount();
});

// ── Generate ──────────────────────────────────────────────────────────────────
document.getElementById("btn-generate").addEventListener("click", async () => {
  const ids = getSelectedIds();
  if (!ids.length) return;

  log(`Generating descriptions for ${ids.length} app(s)...`, "info");
  setButtonsEnabled(false);

  try {
    const res = await apiFetch("/api/apps/generate", {
      method: "POST",
      body: JSON.stringify({ app_ids: ids }),
    });
    const data = await res.json();

    data.results.forEach((r) => {
      if (r.error) {
        log(`  ✗ ${r.displayName}: ${r.error}`, "error");
      } else {
        generatedMap[r.id] = { description: r.description, provider_used: r.provider_used };
        log(`  ✓ ${r.displayName} [${r.provider_used}]`, "success");
      }
    });

    renderTable(appsData);
    log("Generation complete.", "success");
  } catch (e) {
    log(`Generation failed: ${e.message}`, "error");
  } finally {
    setButtonsEnabled(true);
  }
});

// ── Write ─────────────────────────────────────────────────────────────────────
document.getElementById("btn-write").addEventListener("click", async () => {
  const ids = getSelectedIds();
  const updates = ids
    .filter((id) => generatedMap[id])
    .map((id) => ({ id, description: generatedMap[id].description }));

  if (!updates.length) {
    log("No generated descriptions to write. Run Generate first.", "warning");
    return;
  }

  log(`Writing ${updates.length} description(s) to Entra ID...`, "info");
  setButtonsEnabled(false);

  try {
    const res = await apiFetch("/api/apps/write", {
      method: "POST",
      body: JSON.stringify({ updates }),
    });
    const data = await res.json();

    data.results.forEach((r) => {
      const app = appsData.find((a) => a.id === r.id);
      const name = app ? app.displayName : r.id;
      if (r.dry_run) {
        log(`  (dry run) ${name}`, "warning");
      } else {
        log(`  ✓ Written: ${name}`, "success");
      }
    });

    log("Write complete.", "success");
  } catch (e) {
    log(`Write failed: ${e.message}`, "error");
  } finally {
    setButtonsEnabled(true);
  }
});

// ── Export ────────────────────────────────────────────────────────────────────
document.getElementById("btn-export").addEventListener("click", async () => {
  log("Exporting CSV...", "info");
  try {
    const token = await getAccessToken();
    const res = await fetch(`${CONFIG.backendUrl}/api/apps/export`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "entrascribe-export.csv";
    a.click();
    URL.revokeObjectURL(url);
    log("CSV downloaded.", "success");
  } catch (e) {
    log(`Export failed: ${e.message}`, "error");
  }
});

// ── Refresh ───────────────────────────────────────────────────────────────────
document.getElementById("btn-refresh").addEventListener("click", loadApps);

// ── Utilities ─────────────────────────────────────────────────────────────────
function escHtml(str) {
  if (str == null) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function setButtonsEnabled(enabled) {
  ["btn-generate", "btn-write", "btn-refresh", "btn-export"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.disabled = !enabled;
  });
}

// ── Bootstrap ─────────────────────────────────────────────────────────────────
init().catch((e) => {
  console.error("App init failed:", e);
  log(`Initialisation error: ${e.message}`, "error");
});
