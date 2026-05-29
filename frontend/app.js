const API_BASE = "/api";
const THEME_STORAGE_KEY = "interface-theme";
const LIGHT_THEME = "light";
const DARK_THEME = "dark";

function readTheme() {
  try {
    const theme = localStorage.getItem(THEME_STORAGE_KEY);
    if (theme === LIGHT_THEME || theme === DARK_THEME) {
      return theme;
    }
  } catch (e) {
    return DARK_THEME;
  }
  return DARK_THEME;
}

function saveTheme(theme) {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch (e) {
    // Theme switching should still work for the current page if storage is unavailable.
  }
}

function applyTheme(theme) {
  const nextTheme = theme === LIGHT_THEME ? LIGHT_THEME : DARK_THEME;
  document.documentElement.dataset.theme = nextTheme;
  document.documentElement.style.colorScheme = nextTheme;
}

function getActiveTheme() {
  return document.documentElement.dataset.theme === LIGHT_THEME ? LIGHT_THEME : DARK_THEME;
}

function updateThemeToggle(toggle) {
  const isLight = getActiveTheme() === LIGHT_THEME;
  toggle.setAttribute("aria-pressed", String(isLight));
  toggle.setAttribute("aria-label", isLight ? "Включить темную тему" : "Включить светлую тему");
  toggle.title = isLight ? "Включить темную тему" : "Включить светлую тему";
  toggle.innerHTML = `
    <span class="theme-toggle__track" aria-hidden="true">
      <span class="theme-toggle__thumb"></span>
    </span>
    <span class="theme-toggle__text">${isLight ? "Светлая" : "Темная"}</span>
  `;
}

function initThemeToggle() {
  const header = document.querySelector(".header");
  if (!header || document.querySelector(".theme-toggle")) return;

  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "theme-toggle";
  updateThemeToggle(toggle);
  toggle.addEventListener("click", () => {
    const nextTheme = getActiveTheme() === LIGHT_THEME ? DARK_THEME : LIGHT_THEME;
    applyTheme(nextTheme);
    saveTheme(nextTheme);
    updateThemeToggle(toggle);
  });

  const nav = header.querySelector(".nav");
  (nav || header).appendChild(toggle);
}

applyTheme(readTheme());
document.addEventListener("DOMContentLoaded", initThemeToggle);

function getToken() {
  return localStorage.getItem("token");
}

function setToken(token) {
  localStorage.setItem("token", token);
}

function logout() {
  localStorage.removeItem("token");
  window.location.href = "/index.html";
}

async function apiRequest(path, options = {}) {
  const token = getToken();
  const headers = options.headers || {};
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch(path.startsWith("http") ? path : `${API_BASE}${path}`, {
    ...options,
    headers,
    body: options.body ? (options.body instanceof FormData ? options.body : JSON.stringify(options.body)) : undefined,
  });
  if (!res.ok) {
    const msg = await res.text();
    throw new Error(msg || "Request failed");
  }
  return res.status === 204 ? null : res.json();
}

async function ensureAuthenticated() {
  const token = getToken();
  if (!token) {
    window.location.href = "/index.html";
    return null;
  }
  try {
    return await apiRequest("/auth/me");
  } catch (e) {
    logout();
    return null;
  }
}

function setUserBadge(user) {
  const badge = document.getElementById("user-badge");
  if (badge && user) {
    badge.textContent = `${user.full_name} · ${user.role}`;
  }
}

function showMessage(text, tone = "info") {
  const el = document.getElementById("message");
  if (!el) return;
  el.textContent = text;
  el.className = `muted ${tone}`;
}

function statusPill(status, passed) {
  if (passed === true) return `<span class="pill success">зачет</span>`;
  if (passed === false) return `<span class="pill danger">незачет</span>`;
  if (status === "completed") return `<span class="pill success">завершен</span>`;
  if (status === "not_started") return `<span class="pill info">не начат</span>`;
  return `<span class="pill info">${status}</span>`;
}
