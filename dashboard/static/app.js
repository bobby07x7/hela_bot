// Hela Bot Dashboard - vanilla JS client for the JWT-protected /api/* endpoints.
// No build step, no framework - this is a real static file the FastAPI app serves.

const API_BASE = "/api";
const TOKEN_KEY = "hela_dashboard_token";

function getToken() { return localStorage.getItem(TOKEN_KEY); }
function setToken(t) { localStorage.setItem(TOKEN_KEY, t); }
function clearToken() { localStorage.removeItem(TOKEN_KEY); }

async function api(path, options = {}) {
  const headers = Object.assign({ "Content-Type": "application/json" }, options.headers || {});
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(API_BASE + path, { ...options, headers });
  if (res.status === 401) {
    clearToken();
    showLogin();
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }
  return res.status === 204 ? null : res.json();
}

// --------------------------------------------------------------- screens --

function showLogin() {
  document.getElementById("login-screen").classList.remove("hidden");
  document.getElementById("app-screen").classList.add("hidden");
}

function showApp() {
  document.getElementById("login-screen").classList.add("hidden");
  document.getElementById("app-screen").classList.remove("hidden");
  loadOverview();
}

document.getElementById("login-btn").addEventListener("click", async () => {
  const password = document.getElementById("login-password").value;
  const errorEl = document.getElementById("login-error");
  errorEl.textContent = "";
  try {
    const res = await fetch(API_BASE + "/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    if (!res.ok) throw new Error("Incorrect password");
    const data = await res.json();
    setToken(data.access_token);
    showApp();
  } catch (err) {
    errorEl.textContent = err.message;
  }
});

document.getElementById("login-password").addEventListener("keydown", (e) => {
  if (e.key === "Enter") document.getElementById("login-btn").click();
});

document.getElementById("logout-btn").addEventListener("click", () => {
  clearToken();
  showLogin();
});

// ----------------------------------------------------------------- tabs --

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.add("hidden"));
    btn.classList.add("active");
    const tab = btn.dataset.tab;
    document.getElementById(`tab-${tab}`).classList.remove("hidden");
    loadTab(tab);
  });
});

function loadTab(tab) {
  if (tab === "overview") loadOverview();
  else if (tab === "users") loadUsers();
  else if (tab === "groups") loadGroups();
  else if (tab === "ui") loadUiEditor();
  else if (tab === "tickets") loadTickets();
  else if (tab === "market") loadMarket();
  else if (tab === "audit") loadAudit();
}

// -------------------------------------------------------------- overview --

async function loadOverview() {
  const stats = await api("/stats");
  const grid = document.getElementById("stats-grid");
  const cards = [
    ["Users", stats.users], ["Groups", stats.groups], ["Guilds", stats.guilds],
    ["Open tickets", stats.open_tickets], ["Active listings", stats.active_market_listings],
  ];
  grid.innerHTML = cards.map(([label, value]) =>
    `<div class="stat-card"><div class="value">${value}</div><div class="label">${label}</div></div>`
  ).join("");

  const badge = document.getElementById("maintenance-badge");
  const toggle = document.getElementById("maintenance-toggle");
  badge.classList.toggle("hidden", !stats.maintenance_mode);
  toggle.checked = stats.maintenance_mode;
}

document.getElementById("maintenance-toggle").addEventListener("change", async (e) => {
  await api("/maintenance", { method: "POST", body: JSON.stringify({ enabled: e.target.checked }) });
  loadOverview();
});

// ------------------------------------------------------------------ users --

async function loadUsers(q) {
  const query = q ? `?q=${encodeURIComponent(q)}` : "";
  const data = await api("/users" + query);
  const tbody = document.getElementById("users-tbody");
  tbody.innerHTML = data.users.map((u) => `
    <tr>
      <td>${u.telegram_id}</td>
      <td>${escapeHtml(u.first_name || u.username || "-")}</td>
      <td>${u.balance}</td>
      <td>${u.level}</td>
      <td>${u.permission_level}</td>
      <td>${u.is_premium ? '<span class="pill yes">yes</span>' : '<span class="pill no">no</span>'}</td>
      <td>${u.is_banned ? '<span class="pill yes">banned</span>' : '<span class="pill no">no</span>'}</td>
      <td>
        <button class="small-btn" onclick="adjustBalance(${u.telegram_id})">+/- coins</button>
        <button class="small-btn ${u.is_banned ? "" : "danger"}" onclick="toggleBan(${u.telegram_id}, ${u.is_banned})">
          ${u.is_banned ? "Unban" : "Ban"}
        </button>
      </td>
    </tr>
  `).join("");
}

document.getElementById("user-search-btn").addEventListener("click", () => {
  loadUsers(document.getElementById("user-search").value);
});

async function adjustBalance(telegramId) {
  const raw = prompt("Adjust balance by (use negative to subtract):", "0");
  if (raw === null) return;
  const delta = parseInt(raw, 10);
  if (Number.isNaN(delta)) return alert("Enter a whole number.");
  await api(`/users/${telegramId}/balance`, { method: "POST", body: JSON.stringify({ delta }) });
  loadUsers();
}

async function toggleBan(telegramId, isBanned) {
  if (isBanned) {
    await api(`/users/${telegramId}/unban`, { method: "POST" });
  } else {
    const reason = prompt("Ban reason (optional):", "");
    await api(`/users/${telegramId}/ban`, { method: "POST", body: JSON.stringify({ reason: reason || null }) });
  }
  loadUsers();
}

// ----------------------------------------------------------------- groups --

async function loadGroups() {
  const data = await api("/groups");
  const tbody = document.getElementById("groups-tbody");
  tbody.innerHTML = data.groups.map((g) => `
    <tr>
      <td>${g.chat_id}</td>
      <td>${escapeHtml(g.title || "-")}</td>
      <td>${g.force_join_enabled ? '<span class="pill yes">on</span>' : '<span class="pill no">off</span>'}</td>
      <td>${g.is_banned ? '<span class="pill yes">banned</span>' : '<span class="pill no">no</span>'}</td>
      <td>
        <button class="small-btn ${g.is_banned ? "" : "danger"}" onclick="toggleGroupBan(${g.chat_id}, ${g.is_banned})">
          ${g.is_banned ? "Unban" : "Ban"}
        </button>
      </td>
    </tr>
  `).join("");
}

async function toggleGroupBan(chatId, isBanned) {
  const path = isBanned ? "unban" : "ban";
  await api(`/groups/${chatId}/${path}`, { method: "POST" });
  loadGroups();
}

// -------------------------------------------------------------- UI editor --

let uiEntriesCache = {};

async function loadUiEditor() {
  const data = await api("/ui");
  uiEntriesCache = data.entries;
  renderUiList(document.getElementById("ui-search").value || "");
}

document.getElementById("ui-search").addEventListener("input", (e) => renderUiList(e.target.value));

function renderUiList(filter) {
  const list = document.getElementById("ui-list");
  const keys = Object.keys(uiEntriesCache).filter((k) => k.includes(filter.toLowerCase())).sort();
  list.innerHTML = keys.map((key) => {
    const entry = uiEntriesCache[key];
    return `
      <div class="ui-entry">
        <div class="key">${key} ${entry.is_overridden ? '<span class="overridden-tag">(edited)</span>' : ""}</div>
        <textarea id="ui-text-${cssId(key)}">${escapeHtml(entry.current)}</textarea>
        <div class="row">
          <button class="small-btn" onclick="saveUiKey('${key}')">Save</button>
          ${entry.is_overridden ? `<button class="small-btn danger" onclick="resetUiKey('${key}')">Revert to default</button>` : ""}
        </div>
      </div>
    `;
  }).join("");
}

function cssId(key) { return key.replace(/[^a-zA-Z0-9]/g, "_"); }

async function saveUiKey(key) {
  const content = document.getElementById(`ui-text-${cssId(key)}`).value;
  await api(`/ui/${encodeURIComponent(key)}`, { method: "PUT", body: JSON.stringify({ content }) });
  loadUiEditor();
}

async function resetUiKey(key) {
  await api(`/ui/${encodeURIComponent(key)}`, { method: "DELETE" });
  loadUiEditor();
}

// -------------------------------------------------------------- broadcast --

document.getElementById("broadcast-btn").addEventListener("click", async () => {
  const text = document.getElementById("broadcast-text").value.trim();
  const statusEl = document.getElementById("broadcast-status");
  if (!text) return;
  statusEl.textContent = "Queuing...";
  try {
    const res = await api("/broadcast", { method: "POST", body: JSON.stringify({ message: text }) });
    statusEl.textContent = `Queued as broadcast #${res.broadcast_id} - delivery happens within ~10s.`;
    document.getElementById("broadcast-text").value = "";
  } catch (err) {
    statusEl.textContent = "Error: " + err.message;
  }
});

// ---------------------------------------------------------------- tickets --

async function loadTickets() {
  const data = await api("/tickets");
  const list = document.getElementById("tickets-list");
  list.innerHTML = data.tickets.map((t) => `
    <div class="ticket-card">
      <h3>#${t.id} - ${escapeHtml(t.subject)}</h3>
      <div class="muted">User ${t.user_id} - status: ${t.status} - opened ${new Date(t.created_at).toLocaleString()}</div>
      <div class="row">
        <input id="ticket-reply-${t.id}" placeholder="Reply to this ticket..." />
        <button class="small-btn" onclick="replyTicket(${t.id})">Send</button>
        ${t.status !== "closed" ? `<button class="small-btn danger" onclick="closeTicket(${t.id})">Close</button>` : ""}
      </div>
    </div>
  `).join("") || '<p class="muted">No tickets yet.</p>';
}

async function replyTicket(id) {
  const input = document.getElementById(`ticket-reply-${id}`);
  const message = input.value.trim();
  if (!message) return;
  await api(`/tickets/${id}/reply`, { method: "POST", body: JSON.stringify({ message }) });
  input.value = "";
  alert("Reply queued - delivered to the user's DM within ~10s.");
}

async function closeTicket(id) {
  await api(`/tickets/${id}/close`, { method: "POST" });
  loadTickets();
}

// ----------------------------------------------------------------- market --

async function loadMarket() {
  const data = await api("/market");
  const tbody = document.getElementById("market-tbody");
  tbody.innerHTML = data.listings.map((m) => `
    <tr>
      <td>${m.id}</td><td>${m.seller_telegram_id}</td><td>${escapeHtml(m.item_key)}</td>
      <td>${m.quantity}</td><td>${m.price_per_unit}</td>
    </tr>
  `).join("") || '<tr><td colspan="5" class="muted">No active listings.</td></tr>';
}

// ------------------------------------------------------------------ audit --

async function loadAudit() {
  const data = await api("/audit-logs");
  const tbody = document.getElementById("audit-tbody");
  tbody.innerHTML = data.logs.map((a) => `
    <tr>
      <td>${new Date(a.created_at).toLocaleString()}</td>
      <td>${a.actor_id === 0 ? "dashboard" : a.actor_id}</td>
      <td>${escapeHtml(a.action)}</td>
      <td>${escapeHtml(a.target || "-")}</td>
      <td class="muted">${escapeHtml(JSON.stringify(a.meta || {}))}</td>
    </tr>
  `).join("") || '<tr><td colspan="5" class="muted">No audit entries yet.</td></tr>';
}

// ------------------------------------------------------------------ utils --

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str == null ? "" : String(str);
  return div.innerHTML;
}

// ------------------------------------------------------------------- boot --

if (getToken()) {
  showApp();
} else {
  showLogin();
}
