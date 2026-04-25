/* ================================================================
   Atelier — Claude Workspace Dashboard
   Vanilla JS SPA — no dependencies, no CDN
   ================================================================ */
'use strict';

/* === ICONS (Lucide subset, inline SVG) ========================== */
const I = {};
const _icon = (path) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${path}</svg>`;
I.home      = _icon('<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>');
I.box       = _icon('<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" x2="12" y1="22.08" y2="12"/>');
I.plug      = _icon('<path d="M12 22v-5"/><path d="M9 8V2"/><path d="M15 8V2"/><path d="M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8z"/>');
I.layers    = _icon('<polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>');
I.tools     = _icon('<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>');
I.search    = _icon('<circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>');
I.plus      = _icon('<line x1="12" x2="12" y1="5" y2="19"/><line x1="5" x2="19" y1="12" y2="12"/>');
I.play      = _icon('<polygon points="6 3 20 12 6 21 6 3"/>');
I.refresh   = _icon('<path d="M21.5 2v6h-6"/><path d="M2.5 22v-6h6"/><path d="M2 11.5a10 10 0 0 1 18.8-4.3"/><path d="M22 12.5a10 10 0 0 1-18.8 4.3"/>');
I.edit      = _icon('<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>');
I.trash     = _icon('<polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>');
I.copy      = _icon('<rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>');
I.eye       = _icon('<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/>');
I.eyeoff    = _icon('<path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><line x1="2" x2="22" y1="2" y2="22"/>');
I.check     = _icon('<polyline points="20 6 9 17 4 12"/>');
I.x         = _icon('<line x1="18" x2="6" y1="6" y2="18"/><line x1="6" x2="18" y1="6" y2="18"/>');
I.alert     = _icon('<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3z"/><line x1="12" x2="12" y1="9" y2="13"/><line x1="12" x2="12.01" y1="17" y2="17"/>');
I.info      = _icon('<circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="16" y2="12"/><line x1="12" x2="12.01" y1="8" y2="8"/>');
I.success   = _icon('<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>');
I.folder    = _icon('<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>');
I.terminal  = _icon('<polyline points="4 17 10 11 4 5"/><line x1="12" x2="20" y1="19" y2="19"/>');
I.zap       = _icon('<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>');
I.download  = _icon('<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>');
I.up        = _icon('<polyline points="18 15 12 9 6 15"/>');
I.down      = _icon('<polyline points="6 9 12 15 18 9"/>');
I.right     = _icon('<polyline points="9 18 15 12 9 6"/>');
I.dots      = _icon('<circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/>');
I.more      = _icon('<circle cx="12" cy="5" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="12" cy="19" r="1"/>');
I.code      = _icon('<polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>');
I.book      = _icon('<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>');
I.shield    = _icon('<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>');
I.sliders   = _icon('<line x1="4" x2="4" y1="21" y2="14"/><line x1="4" x2="4" y1="10" y2="3"/><line x1="12" x2="12" y1="21" y2="12"/><line x1="12" x2="12" y1="8" y2="3"/><line x1="20" x2="20" y1="21" y2="16"/><line x1="20" x2="20" y1="12" y2="3"/><line x1="1" x2="7" y1="14" y2="14"/><line x1="9" x2="15" y1="8" y2="8"/><line x1="17" x2="23" y1="16" y2="16"/>');
I.archive   = _icon('<polyline points="21 8 21 21 3 21 3 8"/><rect width="22" height="5" x="1" y="3"/><line x1="10" x2="14" y1="12" y2="12"/>');
I.key       = _icon('<path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0 3 3L22 7l-3-3m-3.5 3.5L19 4"/>');
I.history   = _icon('<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>');
I.sparkle   = _icon('<path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3z"/>');
I.menu      = _icon('<line x1="4" x2="20" y1="6" y2="6"/><line x1="4" x2="20" y1="12" y2="12"/><line x1="4" x2="20" y1="18" y2="18"/>');
I.activity  = _icon('<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>');
I.cpu       = _icon('<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" x2="9" y1="2" y2="4"/><line x1="15" x2="15" y1="2" y2="4"/><line x1="9" x2="9" y1="20" y2="22"/><line x1="15" x2="15" y1="20" y2="22"/><line x1="20" x2="22" y1="9" y2="9"/><line x1="20" x2="22" y1="14" y2="14"/><line x1="2" x2="4" y1="9" y2="9"/><line x1="2" x2="4" y1="14" y2="14"/>');
I.message   = _icon('<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>');

/* === THEMES ======================================================= */
const THEMES = [
  { id: 'atelier',        label: 'Atelier',        desc: 'Sombre · violet & ocre',        accent: '#a78bfa', warm: '#f4a672', bg: '#0a0a0f' },
  { id: 'atelier-clair',  label: 'Atelier clair',  desc: 'Clair · violet',                accent: '#7c3aed', warm: '#c2410c', bg: '#f8f7fb' },
  { id: 'marine',         label: 'Marine',         desc: 'Sombre · bleu profond',         accent: '#60a5fa', warm: '#fbbf24', bg: '#08101c' },
  { id: 'foret',          label: 'Forêt',          desc: 'Sombre · vert émeraude',        accent: '#34d399', warm: '#fbbf24', bg: '#08120e' },
  { id: 'brique',         label: 'Brique',         desc: 'Sombre · orange chaud',         accent: '#fb923c', warm: '#facc15', bg: '#120a08' },
];

function applyTheme(id, { save = true } = {}) {
  const valid = THEMES.find(t => t.id === id) ? id : 'atelier';
  if (valid === 'atelier') document.documentElement.removeAttribute('data-theme');
  else document.documentElement.setAttribute('data-theme', valid);
  try { localStorage.setItem('atelier-theme', valid); } catch {}
  if (save) API.post('/api/ui-state', { theme: valid }).catch(() => {});
}

function getCurrentTheme() {
  try {
    const stored = localStorage.getItem('atelier-theme');
    if (stored && THEMES.find(t => t.id === stored)) return stored;
  } catch {}
  return 'atelier';
}

// Appliquer immédiatement au chargement depuis le cache local (évite le flash)
applyTheme(getCurrentTheme(), { save: false });

/* === HELPERS ====================================================== */
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
const escapeHtml = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmtDate = (iso) => {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    if (isNaN(d)) return iso;
    const now = new Date();
    const diff = (now - d) / 1000;
    if (diff < 60) return 'à l\'instant';
    if (diff < 3600) return Math.round(diff / 60) + ' min';
    if (diff < 86400) return Math.round(diff / 3600) + ' h';
    if (diff < 86400 * 7) return Math.round(diff / 86400) + ' j';
    return d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' });
  } catch { return iso; }
};
const fmtNum = (n) => (n == null) ? '—' : new Intl.NumberFormat('fr-FR').format(n);
const fmtBytes = (b) => {
  if (b == null) return '—';
  if (b < 1024) return b + ' o';
  if (b < 1024 * 1024) return (b / 1024).toFixed(1) + ' Kio';
  return (b / 1024 / 1024).toFixed(1) + ' Mio';
};
const debounce = (fn, ms) => {
  let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
};

/* === API ========================================================= */
const API = {
  async _req(method, url, body) {
    const opts = { method, headers: {} };
    if (body !== undefined) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    let r;
    try { r = await fetch(url, opts); }
    catch (e) { throw new Error('Serveur injoignable'); }
    if (!r.ok) {
      let msg = `HTTP ${r.status}`;
      try { const j = await r.json(); if (j.error) msg = j.error; } catch {}
      throw new Error(msg);
    }
    const ct = r.headers.get('content-type') || '';
    return ct.includes('json') ? r.json() : r.text();
  },
  get(url) { return this._req('GET', url); },
  post(url, body = {}) { return this._req('POST', url, body); },
  del(url) { return this._req('DELETE', url); },
};

const safe = (url, fallback) => API.get(url).catch(() => fallback);

/* === STATE ======================================================= */
const STATE = {
  workspaces: [],
  mcps: [],
  envKeys: [],
  envFile: null,
  envExists: false,
  templates: [],
  plugins: { enabled: {}, count: 0 },
  skills: [],
  stats: {},
  wsMcps: {},      // ws_id -> {active, has_file}
  sanity: null,
  journalCount: 0,
  filter: { mcp: '' },
  loading: true,
};

/* === TOAST ======================================================= */
function toast(msg, type = 'info', duration = 3000) {
  const root = $('#toast-root');
  const el = document.createElement('div');
  el.className = `toast toast-${type === true ? 'error' : type === 'error' ? 'error' : type === 'success' ? 'success' : 'info'}`;
  const icon = type === 'error' || type === true ? I.alert : type === 'success' ? I.success : I.info;
  el.innerHTML = `<span class="toast-icon">${icon}</span><div class="toast-content">${escapeHtml(msg)}</div>`;
  root.appendChild(el);
  setTimeout(() => {
    el.classList.add('toast-out');
    setTimeout(() => el.remove(), 200);
  }, duration);
}
const toastErr = (msg) => toast(msg, 'error');
const toastOk = (msg) => toast(msg, 'success');

/* === MODAL ======================================================= */
function openModal({ title, body, footer = null, wide = false, onClose = null, closeOnBackdrop = false }) {
  const root = $('#modal-root');
  root.innerHTML = '';
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  const modal = document.createElement('div');
  modal.className = 'modal' + (wide ? ' modal-wide' : '');
  modal.innerHTML = `
    <div class="modal-header">
      <h2 class="modal-title">${escapeHtml(title)}</h2>
      <button class="icon-btn" data-close aria-label="Fermer">${I.x}</button>
    </div>
    <div class="modal-body"></div>
    ${footer ? `<div class="modal-footer"></div>` : ''}
  `;
  modal.querySelector('.modal-body').append(...(Array.isArray(body) ? body : [body]));
  if (footer) modal.querySelector('.modal-footer').append(...(Array.isArray(footer) ? footer : [footer]));
  overlay.appendChild(modal);
  root.appendChild(overlay);

  const close = () => { root.innerHTML = ''; document.removeEventListener('keydown', onKey); if (onClose) onClose(); };
  const onKey = (e) => { if (e.key === 'Escape') close(); };
  document.addEventListener('keydown', onKey);
  modal.querySelector('[data-close]').addEventListener('click', close);
  // Fermeture sur clic du voile : OFF par défaut pour éviter la perte de saisie.
  // Les éventuels appels qui veulent ce comportement passent closeOnBackdrop:true.
  if (closeOnBackdrop) {
    overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
  }
  return { modal, close };
}

function confirmDialog(message, onYes, { danger = false } = {}) {
  const body = document.createElement('div');
  body.innerHTML = `<p style="margin:0;color:var(--text-muted)">${escapeHtml(message)}</p>`;
  const cancel = btn('Annuler', 'btn-ghost');
  const ok = btn(danger ? 'Supprimer' : 'Confirmer', danger ? 'btn-danger' : 'btn-primary');
  const { close } = openModal({ title: 'Confirmation', body, footer: [cancel, ok] });
  cancel.addEventListener('click', close);
  ok.addEventListener('click', () => { close(); onYes(); });
}

function btn(label, cls = 'btn', icon = null) {
  const b = document.createElement('button');
  b.type = 'button';
  b.className = 'btn ' + cls;
  // Pas de <span> vide quand on n'a qu'une icône (sinon le gap décentre le SVG)
  if (label) {
    b.innerHTML = (icon || '') + `<span>${escapeHtml(label)}</span>`;
  } else {
    b.innerHTML = icon || '';
  }
  return b;
}

function el(tag, cls, html) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html != null) e.innerHTML = html;
  return e;
}

/* === SIDEBAR ===================================================== */
const NAV_ITEMS = [
  { section: 'Espace de travail' },
  { id: 'home',      label: 'Accueil',     route: '#/',          icon: I.home,    key: 'h' },
  { id: 'mcps',      label: 'MCPs',        route: '#/mcps',      icon: I.box,     key: 'm' },
  { id: 'plugins',   label: 'Plugins',     route: '#/plugins',   icon: I.plug,    key: 'p' },
  { id: 'skills',    label: 'Skills',      route: '#/skills',    icon: I.sparkle, key: 'k' },
  { id: 'templates', label: 'Templates',   route: '#/templates', icon: I.layers,  key: 't' },
  { section: 'Système' },
  { id: 'tools',     label: 'Outils',      route: '#/tools',     icon: I.tools,   key: 'o' },
  { id: 'aide',      label: 'Aide',        route: '#/aide',      icon: I.book,    key: 'a' },
];

function renderSidebar() {
  const nav = $('#sidebar-nav');
  nav.innerHTML = '';
  for (const item of NAV_ITEMS) {
    if (item.section) {
      nav.appendChild(el('div', 'nav-section', escapeHtml(item.section)));
      continue;
    }
    const a = document.createElement('a');
    a.href = item.route;
    a.className = 'nav-link';
    a.dataset.id = item.id;
    a.innerHTML = `${item.icon}<span>${escapeHtml(item.label)}</span>${item.key ? `<kbd>g ${item.key}</kbd>` : ''}`;
    nav.appendChild(a);
  }
  updateActiveNav();
}

function updateActiveNav() {
  const route = location.hash || '#/';
  for (const link of $$('.nav-link', $('#sidebar'))) {
    const itemId = link.dataset.id;
    const isActive = (itemId === 'home' && route === '#/') ||
                     (itemId !== 'home' && route.startsWith('#/' + itemId)) ||
                     (itemId === 'home' && route.startsWith('#/workspace/'));
    link.classList.toggle('active', isActive);
  }
}

/* === BREADCRUMB & TOPBAR ACTIONS ================================= */
function setBreadcrumbs(items) {
  const bc = $('#breadcrumbs');
  bc.innerHTML = items.map((it, i) => {
    const last = i === items.length - 1;
    const sep = i > 0 ? `<span class="breadcrumb-sep">/</span>` : '';
    const cls = 'breadcrumb-item' + (last ? ' current' : '');
    if (it.href && !last) {
      return `${sep}<a href="${it.href}" class="${cls}">${escapeHtml(it.label)}</a>`;
    }
    return `${sep}<span class="${cls}">${escapeHtml(it.label)}</span>`;
  }).join('');
}

function setTopbarActions(actions = []) {
  const c = $('#topbar-actions');
  c.innerHTML = '';
  for (const a of actions) c.appendChild(a);
}

/* === DATA LOADING ================================================ */
async function loadAll() {
  const [ws, mcps, env, tpls, plugins, skills] = await Promise.all([
    safe('/api/workspaces', { workspaces: [] }),
    safe('/api/mcps',       { mcps: [] }),
    safe('/api/env',        { keys: [], file: null, exists: false }),
    safe('/api/templates',  { templates: [] }),
    safe('/api/plugins',    { enabled: {}, count: 0 }),
    safe('/api/skills',     { global: [] }),
  ]);
  STATE.workspaces = ws.workspaces || [];
  STATE.mcps = mcps.mcps || [];
  STATE.envKeys = env.keys || [];
  STATE.envFile = env.file;
  STATE.envExists = env.exists;
  STATE.templates = tpls.templates || [];
  STATE.plugins = plugins;
  STATE.skills = skills.global || [];

  // Per-ws MCP status (parallel)
  const wsMcps = await Promise.all(
    STATE.workspaces.map(w => safe(`/api/workspaces/${w.id}/mcps`, { active: [], has_file: false }).then(r => [w.id, r]))
  );
  STATE.wsMcps = Object.fromEntries(wsMcps);

  STATE.loading = false;
  // Offline detector
  try { await API.get('/api/workspaces'); $('#offline-banner').hidden = true; }
  catch { $('#offline-banner').hidden = false; }
}

/* === ROUTER ====================================================== */
async function route() {
  updateActiveNav();
  if (STATE.loading) await loadAll();
  const hash = location.hash || '#/';
  const content = $('#content');
  content.innerHTML = '<div class="page-loader"><div class="spinner"></div><span>Chargement…</span></div>';
  try {
    if (hash === '#/') return await renderHome();
    if (hash === '#/mcps') return await renderMCPs();
    if (hash === '#/plugins') return await renderPlugins();
    if (hash === '#/skills') return await renderSkills();
    if (hash === '#/templates') return await renderTemplates();
    if (hash === '#/tools') return await renderTools();
    if (hash === '#/aide') return await renderHelp();
    const m = hash.match(/^#\/workspace\/([a-zA-Z0-9_-]+)$/);
    if (m) return await renderWorkspace(m[1]);
    location.hash = '#/';
  } catch (e) {
    content.innerHTML = `<div class="error-box">Erreur : ${escapeHtml(e.message)}</div>`;
  }
}

window.addEventListener('hashchange', route);

/* ================================================================
   PAGE: HOME
   ================================================================ */
async function renderHome() {
  setBreadcrumbs([{ label: 'Accueil' }]);
  const newWsBtn = btn('Nouveau workspace', 'btn-primary', I.plus);
  newWsBtn.addEventListener('click', () => modalNewWorkspace());
  const importBtn = btn('Importer config', 'btn', I.download);
  importBtn.title = 'Importer MCPs et workspaces depuis ~/.claude/';
  importBtn.addEventListener('click', () => modalSetupWizard());
  const registerBtn = btn('+ Dossier', 'btn-ghost btn-sm', I.folder);
  registerBtn.title = 'Enregistrer un dossier existant comme workspace';
  registerBtn.addEventListener('click', () => modalRegisterExisting());
  const syncAllBtn = btn('Sync tous', 'btn', I.refresh);
  syncAllBtn.addEventListener('click', async () => {
    syncAllBtn.disabled = true;
    try { const r = await API.post('/api/sync-all', {}); toastOk('Sync terminé pour ' + Object.keys(r.results || {}).length + ' workspace(s)'); }
    catch (e) { toastErr(e.message); }
    finally { syncAllBtn.disabled = false; }
  });
  setTopbarActions([registerBtn, importBtn, syncAllBtn, newWsBtn]);

  const c = $('#content');
  c.innerHTML = '';
  const page = el('div', 'page');

  // Header
  page.appendChild(el('div', 'page-header', `
    <div class="page-header-text">
      <div class="page-eyebrow"><span class="index">00.</span><span>Accueil</span></div>
      <h1 class="page-title">Atelier</h1>
      <p class="page-subtitle">Pilotage des workspaces, MCPs, plugins et skills Claude Code.</p>
    </div>
  `));

  // KPI row
  const stats = await safe('/api/stats', {});
  STATE.stats = stats;
  const wsCount = STATE.workspaces.length;
  const mcpCount = STATE.mcps.filter(m => m.status !== 'désactivé').length;
  const pluginCount = STATE.plugins.count || Object.keys(STATE.plugins.enabled || {}).length;
  const totalSessions = Object.values(stats).reduce((s, x) => s + (x.sessions || 0), 0);

  const kpis = el('div', 'kpi-row');
  kpis.innerHTML = `
    <div class="kpi-card" data-index="01.">
      <div class="kpi-label">Workspaces</div>
      <div class="kpi-value tabular">${wsCount}</div>
      <div class="kpi-detail"><span class="dot dot-ok"></span>${totalSessions} session${totalSessions > 1 ? 's' : ''} cumulées</div>
    </div>
    <div class="kpi-card" data-index="02.">
      <div class="kpi-label">MCPs actifs</div>
      <div class="kpi-value tabular">${mcpCount}</div>
      <div class="kpi-detail">${STATE.mcps.length} dans le registre</div>
    </div>
    <div class="kpi-card" data-index="03.">
      <div class="kpi-label">Plugins</div>
      <div class="kpi-value tabular">${pluginCount}</div>
      <div class="kpi-detail">${STATE.skills.length} skill${STATE.skills.length > 1 ? 's' : ''} global</div>
    </div>
  `;
  page.appendChild(kpis);

  // Two-column grid : workspaces + sanity/journal
  const grid = el('div', 'home-grid');
  const left = el('div');
  const right = el('div', 'stack');

  // Workspaces section
  left.appendChild(el('div', 'section-label', '<span class="num">A.</span> Workspaces <span class="right">' + wsCount + ' total</span>'));
  if (wsCount === 0) {
    const empty = el('div', 'empty');
    empty.innerHTML = `
      <div class="empty-title">Pas encore de workspace dans Atelier</div>
      <p class="muted">Tu peux <strong>créer un nouveau workspace</strong>, <strong>importer ta config Claude existante</strong> (MCPs et projets de <code>~/.claude/</code>), ou <strong>enregistrer un dossier déjà présent</strong> sur ton disque.</p>
    `;
    const ea = el('div', 'empty-action');
    ea.style.display = 'flex'; ea.style.gap = 'var(--sp-2)'; ea.style.justifyContent = 'center'; ea.style.flexWrap = 'wrap';
    const b1 = btn('Importer ma config Claude', 'btn-primary', I.download);
    b1.addEventListener('click', () => modalSetupWizard());
    const b2 = btn('Enregistrer un dossier', 'btn', I.folder);
    b2.addEventListener('click', () => modalRegisterExisting());
    const b3 = btn('Créer depuis template', 'btn-ghost', I.plus);
    b3.addEventListener('click', () => modalNewWorkspace());
    ea.append(b1, b2, b3);
    empty.appendChild(ea);
    left.appendChild(empty);
  } else {
    const wsGrid = el('div', 'workspace-grid');
    for (const w of STATE.workspaces) wsGrid.appendChild(workspaceCard(w));
    left.appendChild(wsGrid);
  }

  // Sanity check
  const sanityCard = el('div', 'card sanity-card');
  sanityCard.innerHTML = `<div class="card-header"><h3 class="card-title">${I.shield} Sanity check</h3><button class="icon-btn" data-refresh aria-label="Rafraîchir">${I.refresh}</button></div>`;
  const sanityBody = el('div');
  sanityCard.appendChild(sanityBody);
  right.appendChild(sanityCard);
  loadSanity(sanityBody);
  sanityCard.querySelector('[data-refresh]').addEventListener('click', () => loadSanity(sanityBody));

  // Journal
  const journalCard = el('div', 'card');
  journalCard.innerHTML = `<div class="card-header"><h3 class="card-title">${I.book} Journal</h3><button class="icon-btn btn-danger" data-clear aria-label="Tout effacer">${I.trash}</button></div>`;
  const jForm = el('form', 'journal-form');
  jForm.innerHTML = `<textarea class="textarea" placeholder="Note rapide… (Ctrl+Entrée pour valider)" rows="2"></textarea>`;
  const jSubmit = btn('Enregistrer', 'btn btn-sm', null);
  jSubmit.style.alignSelf = 'flex-end';
  jForm.appendChild(jSubmit);
  jForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const ta = jForm.querySelector('textarea');
    const t = ta.value.trim();
    if (!t) return;
    try {
      await API.post('/api/journal', { text: t });
      ta.value = ''; toastOk('Note enregistrée'); loadJournal(jList);
    } catch (err) { toastErr(err.message); }
  });
  jForm.querySelector('textarea').addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.key === 'Enter') jSubmit.click();
  });
  journalCard.appendChild(jForm);
  const jList = el('div', 'journal-list');
  journalCard.appendChild(jList);
  right.appendChild(journalCard);
  loadJournal(jList);
  journalCard.querySelector('[data-clear]').addEventListener('click', () => {
    confirmDialog('Effacer toutes les entrées du journal ?', async () => {
      try { await API.del('/api/journal'); loadJournal(jList); toastOk('Journal effacé'); }
      catch (e) { toastErr(e.message); }
    }, { danger: true });
  });

  grid.appendChild(left);
  grid.appendChild(right);
  page.appendChild(grid);
  c.appendChild(page);
}

function workspaceCard(w) {
  const card = el('div', 'workspace-card');
  card.tabIndex = 0;
  const stats = STATE.stats[w.id] || {};
  const mcpsInfo = STATE.wsMcps[w.id] || { active: [] };
  const last = stats.last ? fmtDate(stats.last) : 'jamais';
  card.innerHTML = `
    <div class="workspace-card-header">
      <span class="workspace-emoji">${escapeHtml(w.emoji || '📁')}</span>
      <div style="flex:1;min-width:0">
        <h3 class="workspace-name">${escapeHtml(w.label || w.id)}</h3>
        <div class="workspace-id mono">${escapeHtml(w.id)}</div>
      </div>
    </div>
    <p class="workspace-desc">${escapeHtml(w.description || '—')}</p>
    <div class="workspace-meta">
      <span class="workspace-meta-item">${I.cpu}<span>${mcpsInfo.active.length} MCP${mcpsInfo.active.length > 1 ? 's' : ''}</span></span>
      <span class="workspace-meta-item">${I.message}<span>${stats.sessions || 0} session${(stats.sessions || 0) > 1 ? 's' : ''}</span></span>
      <span class="workspace-meta-item">${I.history}<span>${last}</span></span>
    </div>
  `;
  const actions = el('div', 'workspace-actions');
  const launch = btn('Lancer', 'btn-primary btn-sm', I.play);
  launch.addEventListener('click', async (e) => {
    e.stopPropagation();
    try { const r = await API.post(`/api/launch/${w.id}`, {}); toastOk(r.message || 'Lancé'); }
    catch (err) { toastErr(err.message); }
  });
  const detail = btn('Détail', 'btn-sm', I.right);
  detail.addEventListener('click', (e) => { e.stopPropagation(); location.hash = `#/workspace/${w.id}`; });
  actions.appendChild(launch);
  actions.appendChild(detail);
  card.appendChild(actions);
  card.addEventListener('click', () => { location.hash = `#/workspace/${w.id}`; });
  card.addEventListener('keydown', (e) => { if (e.key === 'Enter') location.hash = `#/workspace/${w.id}`; });
  return card;
}

async function loadSanity(host) {
  host.innerHTML = '<div style="padding:var(--sp-3);color:var(--text-dim);font-size:12px">Vérification…</div>';
  try {
    const r = await API.get('/api/sanity-check');
    if (!r.findings.length && Object.keys(r.missing_env || {}).length === 0) {
      host.innerHTML = `<div class="sanity-empty">${I.success}<div>Tout est en ordre.</div></div>`;
      return;
    }
    const list = el('div', 'sanity-list');
    for (const f of r.findings) {
      const item = el('div', 'sanity-item');
      item.innerHTML = `
        <div class="row" style="justify-content:space-between">
          <strong class="mono" style="font-size:12px">${escapeHtml(f.workspace)}</strong>
          <span class="badge badge-warn">désync</span>
        </div>
        ${f.missing_sync.length ? `<div class="dim">à sync : <span class="mono">${f.missing_sync.map(escapeHtml).join(', ')}</span></div>` : ''}
        ${f.stale.length ? `<div class="dim">obsolètes : <span class="mono">${f.stale.map(escapeHtml).join(', ')}</span></div>` : ''}
      `;
      list.appendChild(item);
    }
    for (const [mcpId, vars] of Object.entries(r.missing_env || {})) {
      const item = el('div', 'sanity-item err');
      item.innerHTML = `
        <div class="row" style="justify-content:space-between">
          <strong class="mono" style="font-size:12px">${escapeHtml(mcpId)}</strong>
          <span class="badge badge-err">env manquant</span>
        </div>
        <div class="dim">${vars.map(escapeHtml).join(', ')}</div>
      `;
      list.appendChild(item);
    }
    host.innerHTML = '';
    host.appendChild(list);
  } catch (e) {
    host.innerHTML = `<div class="error-box">${escapeHtml(e.message)}</div>`;
  }
}

async function loadJournal(host) {
  host.innerHTML = '<div class="dim" style="font-size:12px">Chargement…</div>';
  try {
    const r = await API.get('/api/journal');
    const entries = (r.entries || []).slice().reverse().slice(0, 8);
    if (!entries.length) {
      host.innerHTML = '<div class="dim" style="font-size:12px;padding:var(--sp-2)">Aucune entrée pour le moment.</div>';
      return;
    }
    host.innerHTML = '';
    for (const e of entries) {
      const item = el('div', 'journal-entry');
      item.innerHTML = `<div class="journal-ts">${escapeHtml(e.ts)}</div><div class="journal-text">${escapeHtml(e.text)}</div>`;
      host.appendChild(item);
    }
  } catch (e) {
    host.innerHTML = `<div class="error-box">${escapeHtml(e.message)}</div>`;
  }
}

/* ================================================================
   PAGE: WORKSPACE DETAIL
   ================================================================ */
async function renderWorkspace(wsId) {
  const w = STATE.workspaces.find(x => x.id === wsId);
  if (!w) {
    $('#content').innerHTML = `<div class="error-box">Workspace introuvable : ${escapeHtml(wsId)}</div>`;
    return;
  }
  setBreadcrumbs([
    { label: 'Workspaces', href: '#/' },
    { label: w.label || w.id },
  ]);

  const launch = btn('Lancer', 'btn-primary', I.play);
  launch.addEventListener('click', async () => {
    try { const r = await API.post(`/api/launch/${w.id}`, {}); toastOk(r.message || 'Lancé'); }
    catch (e) { toastErr(e.message); }
  });
  const resume = btn('Reprendre', 'btn', I.history);
  resume.addEventListener('click', async () => {
    try { const r = await API.post(`/api/launch-resume/${w.id}`, {}); toastOk(r.message || 'Reprise'); }
    catch (e) { toastErr(e.message); }
  });
  const sync = btn('Sync MCPs', 'btn', I.refresh);
  sync.addEventListener('click', async () => {
    try {
      const r = await API.post(`/api/workspaces/${w.id}/sync-mcps`, {});
      toastOk('Sync : ' + (r.applied || []).length + ' MCP(s) appliqués');
    } catch (e) { toastErr(e.message); }
  });
  setTopbarActions([resume, sync, launch]);

  const c = $('#content');
  c.innerHTML = '';
  const page = el('div', 'page');

  // ── Header (full width) ──
  const header = el('div', 'ws-header');
  header.innerHTML = `
    <div class="ws-header-top">
      <div class="ws-emoji">${escapeHtml(w.emoji || '📁')}</div>
      <div class="ws-title-block">
        <div class="page-eyebrow"><span class="index">WS</span><span>${escapeHtml(w.id)}</span></div>
        <h1 class="ws-title">${escapeHtml(w.label || w.id)}</h1>
        <div class="ws-path">${escapeHtml(w.path || '')}</div>
        ${w.description ? `<p class="muted" style="margin-top:8px;font-size:13.5px">${escapeHtml(w.description)}</p>` : ''}
      </div>
    </div>
  `;
  // Secondary actions (smaller, in header right side)
  const headerActions = el('div', 'ws-actions');
  const editBtn = btn('Modifier', 'btn-sm btn-ghost', I.edit);
  editBtn.addEventListener('click', () => modalEditWorkspace(w));
  const dupBtn = btn('Dupliquer', 'btn-sm btn-ghost', I.copy);
  dupBtn.addEventListener('click', () => modalDuplicateWorkspace(w));
  const exportBtn = btn('Exporter', 'btn-sm btn-ghost', I.download);
  exportBtn.addEventListener('click', () => { window.location.href = `/api/workspaces/${w.id}/export`; });
  const openBtn = btn('Dossier', 'btn-sm btn-ghost', I.folder);
  openBtn.addEventListener('click', async () => {
    try { const r = await API.post('/api/open', { target: `workspace-dir:${w.id}` }); toastOk(r.message); }
    catch (e) { toastErr(e.message); }
  });
  const delBtn = btn('Supprimer', 'btn-sm btn-ghost btn-danger', I.trash);
  delBtn.addEventListener('click', () => modalDeleteWorkspace(w));
  headerActions.append(editBtn, dupBtn, exportBtn, openBtn, delBtn);
  header.appendChild(headerActions);
  page.appendChild(header);

  // ── Stats tiles (full width) ──
  const stats = STATE.stats[w.id] || {};
  const tiles = el('div', 'ws-info-grid');
  tiles.innerHTML = `
    <div class="info-tile"><div class="info-tile-label">Sessions</div><div class="info-tile-value tabular">${stats.sessions || 0}</div></div>
    <div class="info-tile"><div class="info-tile-label">Messages</div><div class="info-tile-value tabular">${fmtNum(stats.messages || 0)}</div></div>
    <div class="info-tile"><div class="info-tile-label">Tokens in</div><div class="info-tile-value tabular">${fmtNum(stats.input_tokens || 0)}</div></div>
    <div class="info-tile"><div class="info-tile-label">Tokens out</div><div class="info-tile-value tabular">${fmtNum(stats.output_tokens || 0)}</div></div>
    <div class="info-tile"><div class="info-tile-label">Coût ~$</div><div class="info-tile-value tabular">${stats.cost_usd != null ? stats.cost_usd.toFixed(2) : '—'}</div></div>
    <div class="info-tile"><div class="info-tile-label">Dernière</div><div class="info-tile-value" style="font-size:14px">${stats.last ? fmtDate(stats.last) : '—'}</div></div>
  `;
  page.appendChild(tiles);

  // ── Config toolbar (horizontal full width) ──
  page.appendChild(el('div', 'section-label', '<span class="num">A.</span> Configuration'));
  const cfgBar = el('div', 'config-bar');
  const cfgItems = [
    { label: 'CLAUDE.md',     icon: I.book,    action: () => openWsFile(w.id, 'CLAUDE.md') },
    { label: 'notes.md',      icon: I.book,    action: () => openWsFile(w.id, 'notes.md') },
    { label: 'settings.json', icon: I.code,    action: () => modalEditSettings(w.id) },
    { label: 'Permissions',   icon: I.shield,  action: () => modalPermissions(w.id) },
    { label: 'Hooks',         icon: I.zap,     action: () => modalHooks(w.id) },
  ];
  for (const it of cfgItems) {
    const b = el('button', 'config-btn', `${it.icon}<span>${escapeHtml(it.label)}</span>`);
    b.addEventListener('click', it.action);
    cfgBar.appendChild(b);
  }
  page.appendChild(cfgBar);

  // ── Trio MCPs / Skills / Plugins (full width, 3 columns) ──
  page.appendChild(el('div', 'section-label', '<span class="num">B.</span> Extensions actives'));
  const trio = el('div', 'ws-trio');

  const mcpsCard = el('div', 'card ws-card');
  mcpsCard.innerHTML = `<div class="card-header"><h3 class="card-title">${I.cpu} MCPs scopés</h3></div>`;
  const mcpsList = el('div', 'stack');
  mcpsCard.appendChild(mcpsList);
  trio.appendChild(mcpsCard);
  renderWsMCPs(w.id, mcpsList);

  const skillsCard = el('div', 'card ws-card');
  skillsCard.innerHTML = `<div class="card-header"><h3 class="card-title">${I.sparkle} Skills</h3></div>`;
  const skillsList = el('div', 'stack');
  skillsCard.appendChild(skillsList);
  trio.appendChild(skillsCard);
  loadWsSkills(w.id, skillsList);

  const pluginsCard = el('div', 'card ws-card');
  pluginsCard.innerHTML = `<div class="card-header"><h3 class="card-title">${I.plug} Plugins</h3></div>`;
  const pluginsList = el('div', 'stack');
  pluginsCard.appendChild(pluginsList);
  trio.appendChild(pluginsCard);
  loadWsPlugins(w.id, pluginsList);

  page.appendChild(trio);

  // ── Sessions (full width, 2 columns sur grand écran) ──
  const bottom = el('div', 'ws-bottom');

  const sessBlock = el('div');
  sessBlock.appendChild(el('div', 'section-label', '<span class="num">C.</span> Sessions récentes'));
  const sessHost = el('div', 'session-list');
  sessBlock.appendChild(sessHost);
  loadSessions(w.id, sessHost);
  bottom.appendChild(sessBlock);

  const filesBlock = el('div');
  filesBlock.appendChild(el('div', 'section-label', '<span class="num">D.</span> Agents & commandes'));
  const fileItems = el('div', 'stack');
  filesBlock.appendChild(fileItems);
  loadFileItems(w.id, fileItems);
  bottom.appendChild(filesBlock);

  page.appendChild(bottom);
  c.appendChild(page);
}

async function loadSessions(wsId, host) {
  host.innerHTML = '<div class="dim" style="font-size:12px">Chargement…</div>';
  try {
    const r = await API.get(`/api/workspaces/${wsId}/sessions`);
    const sessions = (r.sessions || []).slice(0, 5);
    if (!sessions.length) {
      host.innerHTML = '<div class="empty"><div class="empty-title">Aucune session</div><p class="muted">Lance Claude Code dans ce workspace pour commencer.</p></div>';
      return;
    }
    host.innerHTML = '';
    for (const s of sessions) {
      const row = el('div', 'session-row');
      row.innerHTML = `
        <div class="session-info">
          <div class="session-msg">${escapeHtml(s.first_message || '(vide)')}</div>
          <div class="session-meta">${fmtDate(s.mtime)} · ${s.messages} msg · ${fmtNum(s.input_tokens || 0)} in / ${fmtNum(s.output_tokens || 0)} out</div>
        </div>
        <span class="badge">${escapeHtml(s.file.slice(0, 8))}</span>
      `;
      row.addEventListener('click', () => modalSession(wsId, s.file));
      host.appendChild(row);
    }
  } catch (e) {
    host.innerHTML = `<div class="error-box">${escapeHtml(e.message)}</div>`;
  }
}

async function modalSession(wsId, filename) {
  let r;
  try { r = await API.get(`/api/workspaces/${wsId}/sessions/${filename}`); }
  catch (e) { toastErr(e.message); return; }
  const body = el('div', 'stack');
  body.style.maxHeight = '70vh'; body.style.overflowY = 'auto';
  for (const m of r.messages || []) {
    const item = el('div', 'list-row');
    item.style.flexDirection = 'column'; item.style.alignItems = 'stretch'; item.style.gap = '6px';
    item.innerHTML = `
      <div class="row"><span class="badge ${m.role === 'user' ? 'badge-info' : 'badge-accent'}">${m.role}</span><span class="dim mono" style="font-size:10.5px">${escapeHtml(m.timestamp || '')}</span></div>
      <div style="font-size:13px;white-space:pre-wrap;line-height:1.5;color:var(--text)">${escapeHtml(m.text)}</div>
    `;
    body.appendChild(item);
  }
  if (!(r.messages || []).length) body.innerHTML = '<div class="dim">Session vide.</div>';
  const close = btn('Fermer', 'btn-ghost');
  const { close: doClose } = openModal({ title: filename, body, footer: close, wide: true });
  close.addEventListener('click', doClose);
}

function renderWsMCPs(wsId, host) {
  const info = STATE.wsMcps[wsId] || { active: [] };
  if (!info.active.length) {
    host.innerHTML = '<div class="dim" style="font-size:12.5px">Aucun MCP actif. Configure-les depuis la page MCPs ou via "Sync MCPs".</div>';
    return;
  }
  host.innerHTML = '';
  for (const mcpId of info.active) {
    const m = STATE.mcps.find(x => x.id === mcpId);
    const row = el('div', 'list-row');
    row.innerHTML = `
      <span class="dot ${m && m.status === 'connecté' ? 'dot-ok' : 'dot-info'}"></span>
      <div class="list-row-main">
        <div class="list-row-name mono">${escapeHtml(mcpId)}</div>
        ${m ? `<div class="list-row-desc">${escapeHtml(m.description || m.transport || '')}</div>` : ''}
      </div>
    `;
    const test = btn('Test', 'btn-sm btn-ghost');
    test.addEventListener('click', async () => {
      try { const r = await API.post(`/api/mcps/${mcpId}/test`, {}); toast(`[${mcpId}] ${r.ok ? '✓' : '✗'} ${r.message}`, r.ok ? 'success' : 'error'); }
      catch (e) { toastErr(e.message); }
    });
    row.appendChild(test);
    host.appendChild(row);
  }
}

async function loadWsSkills(wsId, host) {
  host.innerHTML = '<div class="dim" style="font-size:12px">Chargement…</div>';
  try {
    const r = await API.get(`/api/workspaces/${wsId}/skills`);
    const local = r.local || [];
    const global = r.global_available || [];
    host.innerHTML = '';
    if (!local.length && !global.length) {
      host.innerHTML = '<div class="dim" style="font-size:12.5px">Aucun skill disponible.</div>';
      return;
    }
    for (const s of local) {
      const row = el('div', 'list-row');
      row.innerHTML = `
        <div class="list-row-main">
          <div class="list-row-name">${escapeHtml(s.name || s.id)}</div>
          <div class="list-row-desc">${escapeHtml(s.description || '')}</div>
        </div>
      `;
      const editBtn2 = btn('Éditer', 'btn-sm btn-ghost', I.edit);
      editBtn2.addEventListener('click', () => modalEditSkill(`workspace:${wsId}`, s.id));
      const rem = btn('', 'btn-sm btn-ghost btn-icon-only', I.x);
      rem.title = 'Retirer';
      rem.addEventListener('click', () => {
        confirmDialog('Retirer ce skill du workspace ?', async () => {
          try { await API.del(`/api/skills/workspace:${wsId}/${s.id}`); toastOk('Skill retiré'); route(); }
          catch (e) { toastErr(e.message); }
        }, { danger: true });
      });
      row.appendChild(editBtn2); row.appendChild(rem);
      host.appendChild(row);
    }
    if (global.length) {
      host.appendChild(el('div', 'dim', `<small>Disponibles globalement :</small>`));
      for (const s of global) {
        const row = el('div', 'list-row');
        row.innerHTML = `
          <div class="list-row-main">
            <div class="list-row-name">${escapeHtml(s.name || s.id)}</div>
            <div class="list-row-desc">${escapeHtml(s.description || '')}</div>
          </div>
        `;
        const copy = btn('+ ici', 'btn-sm', I.copy);
        copy.addEventListener('click', async () => {
          try { await API.post('/api/skills/copy', { name: s.id, workspace: wsId }); toastOk('Skill copié'); route(); }
          catch (e) { toastErr(e.message); }
        });
        row.appendChild(copy);
        host.appendChild(row);
      }
    }
  } catch (e) { host.innerHTML = `<div class="error-box">${escapeHtml(e.message)}</div>`; }
}

async function loadWsPlugins(wsId, host) {
  host.innerHTML = '<div class="dim" style="font-size:12px">Chargement…</div>';
  try {
    const r = await API.get(`/api/workspaces/${wsId}/plugins`);
    const plugins = r.plugins || {};
    const ids = Object.keys(plugins).sort();
    if (!ids.length) {
      host.innerHTML = '<div class="dim" style="font-size:12.5px">Aucun plugin global.</div>';
      return;
    }
    host.innerHTML = '';
    for (const pid of ids) {
      const p = plugins[pid];
      const [shortId, mkt] = pid.includes('@') ? pid.split('@') : [pid, null];
      const state = p.overridden ? (p.effective ? 'on' : 'off') : (p.effective ? 'inherit-on' : 'inherit-off');
      const row = el('div', 'ws-plugin-row');
      row.innerHTML = `
        <span class="scope-state-badge state-${state}"></span>
        <div class="ws-plugin-main">
          <div class="ws-plugin-name">${escapeHtml(shortId)}</div>
          <div class="ws-plugin-meta">
            ${mkt ? `<span class="dim mono" style="font-size:10.5px">${escapeHtml(mkt)}</span>` : ''}
            <span class="badge ${p.overridden ? 'badge-accent' : ''}" style="font-size:10px">${p.overridden ? 'override' : 'hérité'}</span>
            <span class="badge ${p.effective ? 'badge-ok' : 'badge-err'}" style="font-size:10px">${p.effective ? 'actif' : 'inactif'}</span>
          </div>
        </div>
      `;
      const seg = el('div', 'seg-control');
      seg.innerHTML = `
        <button data-set="on" class="${state === 'on' ? 'is-active' : ''}" title="Forcer actif">A</button>
        <button data-set="off" class="${state === 'off' ? 'is-active' : ''}" title="Forcer inactif">I</button>
        <button data-set="reset" class="${state.startsWith('inherit') ? 'is-active' : ''}" title="Hériter du global">↺</button>
      `;
      seg.querySelectorAll('button').forEach(b => {
        b.addEventListener('click', async () => {
          const next = { 'on': true, 'off': false, 'reset': null }[b.dataset.set];
          try { await API.post(`/api/workspaces/${wsId}/plugins`, { plugin_id: pid, enabled: next }); loadWsPlugins(wsId, host); }
          catch (e) { toastErr(e.message); }
        });
      });
      row.appendChild(seg);
      host.appendChild(row);
    }
  } catch (e) { host.innerHTML = `<div class="error-box">${escapeHtml(e.message)}</div>`; }
}

async function loadFileItems(wsId, host) {
  host.innerHTML = '';
  for (const kind of ['agents', 'commands']) {
    const block = el('div', 'card');
    block.style.padding = 'var(--sp-3)';
    block.innerHTML = `<div class="card-header" style="margin-bottom:var(--sp-2)"><h4 class="card-title" style="font-size:12.5px;text-transform:uppercase;letter-spacing:0.1em;color:var(--text-dim);font-family:var(--font-mono)">${kind}</h4></div>`;
    const list = el('div', 'stack');
    block.appendChild(list);
    const add = btn('+ Nouveau', 'btn-sm btn-ghost');
    add.addEventListener('click', () => modalEditFileItem(kind, `workspace:${wsId}`, null));
    block.appendChild(add);
    host.appendChild(block);
    try {
      const data = await API.get(`/api/${kind}/workspace/${wsId}`);
      const items = data.workspace || data.items || [];
      if (!items.length) {
        list.innerHTML = `<div class="dim" style="font-size:12px;padding:var(--sp-2)">Aucun ${kind === 'agents' ? 'agent' : 'commande'}</div>`;
        continue;
      }
      for (const it of items) {
        const row = el('div', 'list-row');
        row.innerHTML = `
          <div class="list-row-main">
            <div class="list-row-name mono">${escapeHtml(it.name || it.id)}</div>
            <div class="list-row-desc">${escapeHtml(it.description || '')}</div>
          </div>
        `;
        const ed = btn('', 'btn-sm btn-icon-only btn-ghost', I.edit);
        ed.addEventListener('click', () => modalEditFileItem(kind, `workspace:${wsId}`, it.id));
        const rm = btn('', 'btn-sm btn-icon-only btn-ghost', I.trash);
        rm.addEventListener('click', () => confirmDialog('Supprimer ?', async () => {
          try { await API.del(`/api/${kind}/workspace:${wsId}/${it.id}`); toastOk('Supprimé'); loadFileItems(wsId, host); }
          catch (e) { toastErr(e.message); }
        }, { danger: true }));
        row.append(ed, rm);
        list.appendChild(row);
      }
    } catch (e) {
      list.innerHTML = `<div class="error-box">${escapeHtml(e.message)}</div>`;
    }
  }
}

async function openWsFile(wsId, filename) {
  let data;
  try { data = await API.get(`/api/workspaces/${wsId}/config`); }
  catch (e) { toastErr(e.message); return; }
  const content = (data.files || {})[filename] || '';
  const body = el('div');
  body.innerHTML = `<div class="dim" style="font-size:11.5px;margin-bottom:6px">${escapeHtml(data.path || '')}/${escapeHtml(filename)}</div>`;
  const ta = el('textarea', 'textarea textarea-code');
  ta.rows = 18; ta.value = content || '';
  body.appendChild(ta);
  const cancel = btn('Annuler', 'btn-ghost');
  const save = btn('Enregistrer', 'btn-primary');
  const { close } = openModal({ title: filename, body, footer: [cancel, save], wide: true });
  cancel.addEventListener('click', close);
  save.addEventListener('click', async () => {
    try { await API.post(`/api/workspaces/${wsId}/file`, { filename, content: ta.value }); toastOk('Enregistré'); close(); }
    catch (e) { toastErr(e.message); }
  });
}

/* ================================================================
   PAGE: MCPs
   ================================================================ */
async function renderMCPs() {
  setBreadcrumbs([{ label: 'MCPs' }]);
  const newBtn = btn('Nouveau MCP', 'btn-primary', I.plus);
  newBtn.addEventListener('click', () => modalNewMCP());
  const importBtn = btn('Importer', 'btn', I.download);
  importBtn.addEventListener('click', () => modalImportMCPs());
  setTopbarActions([importBtn, newBtn]);

  const c = $('#content');
  c.innerHTML = '';
  const page = el('div', 'page');

  page.appendChild(el('div', 'page-header', `
    <div class="page-header-text">
      <div class="page-eyebrow"><span class="index">01.</span><span>Catalogue</span></div>
      <h1 class="page-title">MCPs</h1>
      <p class="page-subtitle">Servers Model Context Protocol — synchronisés vers les workspaces.</p>
    </div>
  `));

  // Bandeau conflits éventuels avec ~/.claude/
  const conflictsBanner = el('div');
  page.appendChild(conflictsBanner);
  (async () => {
    try {
      const r = await API.get('/api/mcps/conflicts');
      const total = (r.conflicts || []).length + (r.orphans || []).length;
      if (!total) return;
      const banner = el('div', 'mcp-conflict-banner');
      banner.innerHTML = `
        <div class="mcp-conflict-icon">${I.alert}</div>
        <div class="mcp-conflict-text">
          <strong>${total} MCP(s) trouvé(s) dans ta config Claude globale</strong>
          <span class="dim">${(r.conflicts || []).length} doublon(s) avec le registre Atelier · ${(r.orphans || []).length} orphelin(s) à migrer</span>
        </div>
      `;
      const fixBtn = btn('Examiner', 'btn-sm btn-primary', I.right);
      fixBtn.addEventListener('click', () => modalGlobalConflicts());
      banner.appendChild(fixBtn);
      conflictsBanner.appendChild(banner);
    } catch {}
  })();

  const toolbar = el('div', 'mcp-toolbar');
  toolbar.innerHTML = `<input class="input input-search" type="search" placeholder="Filtrer par nom, transport, workspace…" />`;
  const filterStatus = el('select', 'select');
  filterStatus.innerHTML = `<option value="">Tous statuts</option><option>connecté</option><option>disponible</option><option>à configurer</option><option>désactivé</option>`;
  filterStatus.style.maxWidth = '180px';
  toolbar.appendChild(filterStatus);
  const filterTransport = el('select', 'select');
  filterTransport.innerHTML = `<option value="">Tous transports</option><option>stdio</option><option>http</option><option>sse</option>`;
  filterTransport.style.maxWidth = '160px';
  toolbar.appendChild(filterTransport);
  page.appendChild(toolbar);

  const grid = el('div', 'mcp-grid');
  page.appendChild(grid);

  const renderList = () => {
    const q = toolbar.querySelector('input').value.trim().toLowerCase();
    const sf = filterStatus.value;
    const tf = filterTransport.value;
    const list = STATE.mcps.filter(m => {
      if (sf && m.status !== sf) return false;
      if (tf && (m.transport || 'stdio') !== tf) return false;
      if (q) {
        const hay = `${m.id} ${m.name || ''} ${m.description || ''} ${(m.workspaces || []).join(' ')} ${m.transport || ''}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
    grid.innerHTML = '';
    if (!list.length) {
      const empty = el('div', 'empty');
      empty.innerHTML = `<div class="empty-title">Aucun MCP</div><p class="muted">Crée ton premier MCP ou importe depuis Claude Code.</p>`;
      grid.appendChild(empty);
      return;
    }
    for (const m of list) grid.appendChild(mcpCard(m));
  };
  toolbar.querySelector('input').addEventListener('input', debounce(renderList, 100));
  filterStatus.addEventListener('change', renderList);
  filterTransport.addEventListener('change', renderList);
  renderList();

  c.appendChild(page);
}

function mcpCard(m) {
  const card = el('div', 'mcp-card');
  const statusClass = m.status === 'connecté' ? 'badge-ok' : m.status === 'disponible' ? 'badge-info' : m.status === 'désactivé' ? 'badge-err' : 'badge-warn';
  const transportColor = m.transport === 'http' ? 'badge-info' : m.transport === 'sse' ? 'badge-accent' : 'badge';
  const isHttp = m.transport === 'http' || m.transport === 'sse';
  const cmd = isHttp ? (m.url || '—') : (m.command || '—') + (m.args && m.args.length ? ' ' + m.args.join(' ') : '');
  const headerCount = Object.keys(m.headers || {}).length;
  const envCount = Object.keys(m.env || {}).length;
  const extraBadges = [];
  if (m.cwd) extraBadges.push(`<span class="badge" title="cwd : ${escapeHtml(m.cwd)}">cwd</span>`);
  if (headerCount) extraBadges.push(`<span class="badge badge-info" title="${headerCount} header(s)">${headerCount} hdr</span>`);
  if (envCount) extraBadges.push(`<span class="badge" title="${envCount} variable(s) d'env">${envCount} env</span>`);
  card.innerHTML = `
    <div class="mcp-card-header">
      <div style="min-width:0">
        <h3 class="mcp-name">${escapeHtml(m.name || m.id)}</h3>
        <div class="dim mono" style="font-size:11px;margin-top:2px">${escapeHtml(m.id)}</div>
      </div>
      <span class="badge ${statusClass}">${escapeHtml(m.status || 'à configurer')}</span>
    </div>
    ${m.description ? `<p class="mcp-desc">${escapeHtml(m.description)}</p>` : ''}
    <div class="row" style="gap:6px">
      <span class="badge ${transportColor}">${escapeHtml(m.transport || 'stdio')}</span>
      ${extraBadges.join('')}
      ${(m.workspaces || []).slice(0, 4).map(ws => `<span class="chip">${escapeHtml(ws)}</span>`).join('')}
      ${(m.workspaces || []).length > 4 ? `<span class="chip">+${(m.workspaces || []).length - 4}</span>` : ''}
    </div>
    <div class="mcp-cmd" title="${escapeHtml(cmd)}">${escapeHtml(cmd)}</div>
    ${m.cwd ? `<div class="dim mono" style="font-size:10.5px;padding:2px 8px;background:var(--bg);border-radius:4px;border:1px solid var(--border)" title="working directory">cd: ${escapeHtml(m.cwd)}</div>` : ''}
  `;
  const footer = el('div', 'mcp-card-footer');
  const test = btn('Tester', 'btn-sm', I.zap);
  test.addEventListener('click', async () => {
    test.disabled = true;
    try { const r = await API.post(`/api/mcps/${m.id}/test`, {}); toast(`[${m.id}] ${r.ok ? '✓' : '✗'} ${r.message}`, r.ok ? 'success' : 'error', 5000); }
    catch (e) { toastErr(e.message); }
    finally { test.disabled = false; }
  });
  const ed = btn('Modifier', 'btn-sm btn-ghost', I.edit);
  ed.addEventListener('click', () => modalNewMCP(m));
  const rm = btn('', 'btn-sm btn-ghost btn-icon-only btn-danger', I.trash);
  rm.title = 'Supprimer';
  rm.addEventListener('click', () => confirmDialog(`Supprimer ${m.id} ?`, async () => {
    try { await API.del(`/api/mcps/${m.id}`); toastOk('Supprimé'); STATE.loading = true; route(); }
    catch (e) { toastErr(e.message); }
  }, { danger: true }));
  footer.append(test, ed, rm);
  card.appendChild(footer);
  return card;
}

function modalNewMCP(existing = null) {
  const isEdit = !!existing;
  const m = existing || { id: '', name: '', description: '', transport: 'stdio', command: '', args: [], env: {}, cwd: '', url: '', headers: {}, workspaces: [], status: 'à configurer', notes: '', author: '' };

  const kvToText = (obj) => Object.entries(obj || {}).map(([k, v]) => `${k}=${v}`).join('\n');

  const body = el('div');
  body.innerHTML = `
    <div class="tabs">
      <div class="tab active" data-tab="form">Formulaire</div>
      <div class="tab" data-tab="json">JSON brut</div>
    </div>
    <div data-tab-body="form">
      <div class="field-row">
        <div class="field"><label class="field-label">ID *</label><input class="input mono" name="id" value="${escapeHtml(m.id)}" ${isEdit ? 'readonly' : ''} placeholder="mon-mcp"></div>
        <div class="field"><label class="field-label">Nom</label><input class="input" name="name" value="${escapeHtml(m.name || '')}"></div>
      </div>
      <div class="field"><label class="field-label">Description</label><input class="input" name="description" value="${escapeHtml(m.description || '')}"></div>
      <div class="field-row">
        <div class="field"><label class="field-label">Transport</label><select class="select" name="transport">${['stdio','http','sse'].map(t => `<option ${m.transport===t?'selected':''}>${t}</option>`).join('')}</select></div>
        <div class="field"><label class="field-label">Statut</label><select class="select" name="status">${['à configurer','disponible','connecté','désactivé'].map(t => `<option ${m.status===t?'selected':''}>${t}</option>`).join('')}</select></div>
      </div>

      <!-- Champs stdio -->
      <div class="field" data-stdio><label class="field-label">Command *</label><input class="input mono" name="command" value="${escapeHtml(m.command || '')}" placeholder="npx, uvx, python..."></div>
      <div class="field" data-stdio><label class="field-label">Args (un par ligne)</label><textarea class="textarea" name="args" rows="3" placeholder="-y&#10;@scope/package&#10;--option">${escapeHtml((m.args || []).join('\n'))}</textarea></div>
      <div class="field" data-stdio>
        <label class="field-label">CWD <span class="dim" style="font-weight:400">— working directory du process (optionnel, supporte <code class="mono">\${VAR}</code>)</span></label>
        <input class="input mono" name="cwd" value="${escapeHtml(m.cwd || '')}" placeholder="C:\\path\\to\\dir ou \${HOME}/data">
      </div>

      <!-- Champs http/sse -->
      <div class="field" data-http><label class="field-label">URL *</label><input class="input mono" name="url" value="${escapeHtml(m.url || '')}" placeholder="https://api.example.com/mcp"></div>
      <div class="field" data-http>
        <label class="field-label">Headers <span class="dim" style="font-weight:400">— KEY=VALUE par ligne, supporte <code class="mono">\${VAR}</code></span></label>
        <textarea class="textarea" name="headers" rows="3" placeholder="Authorization=Bearer \${API_TOKEN}&#10;X-API-Key=\${MY_KEY}">${escapeHtml(kvToText(m.headers))}</textarea>
      </div>

      <!-- Commun -->
      <div class="field"><label class="field-label">Env <span class="dim" style="font-weight:400">— KEY=VALUE par ligne, supporte <code class="mono">\${VAR}</code></span></label><textarea class="textarea" name="env" rows="3" placeholder="OPENAI_API_KEY=\${OPENAI_API_KEY}&#10;DEBUG=1">${escapeHtml(kvToText(m.env))}</textarea></div>
      <div class="field"><label class="field-label">Workspaces ciblés <span class="dim" style="font-weight:400">— <code class="mono">*</code> pour tous, sinon liste séparée par virgule</span></label><input class="input mono" name="workspaces" value="${escapeHtml((m.workspaces || []).join(','))}" placeholder="dev,homeassistant ou *"></div>
      <div class="field-row">
        <div class="field"><label class="field-label">Auteur</label><input class="input" name="author" value="${escapeHtml(m.author || '')}"></div>
        <div class="field"><label class="field-label">Notes</label><input class="input" name="notes" value="${escapeHtml(m.notes || '')}"></div>
      </div>
    </div>
    <div data-tab-body="json" hidden>
      <div class="field"><label class="field-label">JSON complet du MCP</label><textarea class="textarea" name="raw" rows="18"></textarea></div>
    </div>
  `;
  const updateTransportFields = () => {
    const t = body.querySelector('[name=transport]').value;
    body.querySelectorAll('[data-stdio]').forEach(e => e.style.display = t === 'stdio' ? '' : 'none');
    body.querySelectorAll('[data-http]').forEach(e => e.style.display = t !== 'stdio' ? '' : 'none');
  };
  body.querySelector('[name=transport]').addEventListener('change', updateTransportFields);
  updateTransportFields();
  body.querySelector('[name=raw]').value = JSON.stringify(m, null, 2);
  for (const tab of body.querySelectorAll('.tab')) {
    tab.addEventListener('click', () => {
      body.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      body.querySelectorAll('[data-tab-body]').forEach(b => b.hidden = b.dataset.tabBody !== tab.dataset.tab);
    });
  }

  const cancel = btn('Annuler', 'btn-ghost');
  const save = btn(isEdit ? 'Mettre à jour' : 'Créer', 'btn-primary');
  const { close } = openModal({ title: isEdit ? `Modifier ${m.id}` : 'Nouveau MCP', body, footer: [cancel, save], wide: true });
  cancel.addEventListener('click', close);

  const parseKV = (text) => {
    const out = {};
    for (const line of text.split('\n').map(s => s.trim()).filter(Boolean)) {
      const [k, ...rest] = line.split('=');
      if (k) out[k.trim()] = rest.join('=').trim();
    }
    return out;
  };

  save.addEventListener('click', async () => {
    let payload;
    const activeTab = body.querySelector('.tab.active').dataset.tab;
    if (activeTab === 'json') {
      try { payload = JSON.parse(body.querySelector('[name=raw]').value); }
      catch (e) { toastErr('JSON invalide : ' + e.message); return; }
    } else {
      const get = (n) => body.querySelector(`[name=${n}]`).value;
      const argsRaw = get('args').split('\n').map(s => s.trim()).filter(Boolean);
      const wsRaw = get('workspaces').split(',').map(s => s.trim()).filter(Boolean);
      payload = {
        id: get('id').trim(),
        name: get('name').trim() || get('id').trim(),
        description: get('description').trim(),
        transport: get('transport'),
        status: get('status'),
        command: get('command').trim(),
        args: argsRaw,
        cwd: get('cwd').trim(),
        url: get('url').trim(),
        headers: parseKV(get('headers')),
        env: parseKV(get('env')),
        workspaces: wsRaw,
        author: get('author').trim(),
        notes: get('notes').trim(),
      };
    }
    try {
      await API.post('/api/mcps', payload);
      toastOk(isEdit ? 'MCP mis à jour' : 'MCP créé');
      close(); STATE.loading = true; route();
    } catch (e) { toastErr(e.message); }
  });
}

/* ================================================================
   FIRST-RUN WIZARD — assistant de premier lancement
   ================================================================ */
function markOnboarded() {
  API.post('/api/ui-state', { onboarded: true }).catch(() => {});
}
function resetOnboarded() {
  API.post('/api/ui-state', { onboarded: false }).catch(() => {});
}

async function startFirstRunWizard() {
  let stepIdx = 0;
  let scanResult = null;
  let importedItems = { mcps: 0, workspaces: 0 };

  const root = $('#modal-root');
  root.innerHTML = '';
  const overlay = el('div', 'firstrun-overlay');
  const wiz = el('div', 'firstrun');
  overlay.appendChild(wiz);
  root.appendChild(overlay);

  const steps = [
    { id: 'welcome',   render: renderWelcome },
    { id: 'theme',     render: renderThemeStep },
    { id: 'import',    render: renderImportStep },
    { id: 'workspace', render: renderWorkspaceStep },
    { id: 'tips',      render: renderTipsStep },
  ];

  const close = (markDone = true) => {
    if (markDone) markOnboarded();
    overlay.classList.add('firstrun-closing');
    setTimeout(() => { root.innerHTML = ''; }, 220);
    document.removeEventListener('keydown', onKey);
  };
  const onKey = (e) => { if (e.key === 'Escape') close(false); };
  document.addEventListener('keydown', onKey);

  const goNext = () => { stepIdx = Math.min(stepIdx + 1, steps.length - 1); render(); };
  const goPrev = () => { stepIdx = Math.max(stepIdx - 1, 0); render(); };

  const render = () => {
    wiz.innerHTML = '';

    // Header avec progression
    const header = el('div', 'firstrun-header');
    header.innerHTML = `
      <div class="firstrun-brand">
        <span class="brand-mark"></span>
        <span class="brand-name">atelier</span>
      </div>
      <div class="firstrun-steps">
        ${steps.map((s, i) => `<span class="firstrun-step-dot${i === stepIdx ? ' is-active' : ''}${i < stepIdx ? ' is-done' : ''}"></span>`).join('')}
      </div>
      <button class="firstrun-skip" data-skip>Passer le tutoriel</button>
    `;
    header.querySelector('[data-skip]').addEventListener('click', () => close(true));
    wiz.appendChild(header);

    // Body
    const body = el('div', 'firstrun-body');
    wiz.appendChild(body);
    steps[stepIdx].render(body);

    // Footer nav
    const footer = el('div', 'firstrun-footer');
    if (stepIdx > 0) {
      const back = btn('← Précédent', 'btn-ghost');
      back.addEventListener('click', goPrev);
      footer.appendChild(back);
    } else {
      footer.appendChild(el('div'));  // spacer
    }
    const indicator = el('div', 'firstrun-indicator');
    indicator.innerHTML = `<span class="dim mono" style="font-size:11px">Étape ${stepIdx + 1} / ${steps.length}</span>`;
    footer.appendChild(indicator);
    if (stepIdx < steps.length - 1) {
      const next = btn('Continuer →', 'btn-primary');
      next.addEventListener('click', goNext);
      footer.appendChild(next);
    } else {
      const done = btn('Commencer à utiliser Atelier', 'btn-primary', I.sparkle);
      done.addEventListener('click', () => close(true));
      footer.appendChild(done);
    }
    wiz.appendChild(footer);
  };

  // ───── Step 1 : Welcome ─────
  function renderWelcome(host) {
    host.innerHTML = `
      <div class="firstrun-hero">
        <div class="firstrun-hero-mark">
          <div class="brand-mark" style="width:48px;height:48px"></div>
        </div>
        <h1>Bienvenue dans Atelier</h1>
        <p class="firstrun-lead">Le tableau de bord local pour piloter ton écosystème <strong>Claude Code</strong> : workspaces, MCPs, skills, plugins, templates — tout au même endroit.</p>
      </div>
      <div class="firstrun-features">
        <div class="firstrun-feature">
          <div class="firstrun-feature-icon">${I.box}</div>
          <h3>Centralisé</h3>
          <p>Un registre, plusieurs workspaces. Configure une fois, distribue partout via Sync.</p>
        </div>
        <div class="firstrun-feature">
          <div class="firstrun-feature-icon">${I.shield}</div>
          <h3>100% local</h3>
          <p>Tout est sur ta machine, bind 127.0.0.1 strict. Aucune donnée n'est envoyée ailleurs.</p>
        </div>
        <div class="firstrun-feature">
          <div class="firstrun-feature-icon">${I.zap}</div>
          <h3>Rapide</h3>
          <p>Vanilla JS, stdlib Python, zéro dépendance. Lancement instantané.</p>
        </div>
      </div>
      <div class="firstrun-checklist">
        <div class="firstrun-checklist-title">Ce qu'on va faire ensemble :</div>
        <ul>
          <li>${I.check}<span>Choisir un thème qui te plaît</span></li>
          <li>${I.check}<span>Détecter et importer ta config Claude existante (si tu en as une)</span></li>
          <li>${I.check}<span>Créer ton premier workspace (optionnel)</span></li>
          <li>${I.check}<span>Apprendre les raccourcis essentiels</span></li>
        </ul>
        <div class="dim" style="font-size:11.5px;margin-top:var(--sp-2)">⏱️ 2 minutes max — tu peux passer à tout moment.</div>
      </div>
    `;
  }

  // ───── Step 2 : Theme ─────
  function renderThemeStep(host) {
    host.innerHTML = `
      <div class="firstrun-step-header">
        <div class="firstrun-step-eyebrow">Étape 2 · Apparence</div>
        <h2>Choisis ton ambiance</h2>
        <p>Tu pourras la changer à tout moment depuis <strong>Outils → Apparence</strong>.</p>
      </div>
      <div class="theme-grid"></div>
    `;
    const grid = host.querySelector('.theme-grid');
    const current = getCurrentTheme();
    for (const t of THEMES) {
      const card = el('button', 'theme-card' + (t.id === current ? ' is-active' : ''));
      card.type = 'button';
      card.dataset.theme = t.id;
      card.innerHTML = `
        <div class="theme-preview" style="--p-bg:${t.bg};--p-accent:${t.accent};--p-warm:${t.warm}">
          <div class="theme-preview-sidebar"></div>
          <div class="theme-preview-main">
            <div class="theme-preview-bar"></div>
            <div class="theme-preview-card"></div>
            <div class="theme-preview-dot"></div>
          </div>
        </div>
        <div class="theme-card-info">
          <div class="theme-card-name">${escapeHtml(t.label)}</div>
          <div class="theme-card-desc">${escapeHtml(t.desc)}</div>
        </div>
        <div class="theme-card-check">${I.check}</div>
      `;
      card.addEventListener('click', () => {
        applyTheme(t.id);
        grid.querySelectorAll('.theme-card').forEach(c => c.classList.toggle('is-active', c.dataset.theme === t.id));
      });
      grid.appendChild(card);
    }
  }

  // ───── Step 3 : Import config Claude ─────
  async function renderImportStep(host) {
    host.innerHTML = `
      <div class="firstrun-step-header">
        <div class="firstrun-step-eyebrow">Étape 3 · Onboarding</div>
        <h2>Importer ta config Claude existante</h2>
        <p>On va scanner <code class="mono">~/.claude/</code> pour trouver les MCPs et projets déjà configurés.</p>
      </div>
      <div class="firstrun-scan"><div class="page-loader"><div class="spinner"></div><span>Scan en cours…</span></div></div>
    `;
    const scanHost = host.querySelector('.firstrun-scan');

    if (!scanResult) {
      try { scanResult = await API.get('/api/setup/scan'); }
      catch (e) { scanHost.innerHTML = `<div class="error-box">${escapeHtml(e.message)}</div>`; return; }
    }

    const newMcps = (scanResult.mcps || []).filter(m => !m.already_registered);
    const newProjects = (scanResult.projects || []).filter(p => !p.already_registered && p.path_exists);

    if (newMcps.length === 0 && newProjects.length === 0) {
      scanHost.innerHTML = `
        <div class="callout callout-info" style="margin:0">
          <div>
            <strong>Rien à importer.</strong>
            ${scanResult.mcps.length || scanResult.projects.length
              ? ' Ce qui était dans ta config Claude est déjà connu d\'Atelier.'
              : ' Aucun MCP ni projet trouvé dans <code class="mono">~/.claude/</code> — c\'est un démarrage propre, c\'est parfait.'}
          </div>
        </div>
        <p class="muted" style="margin-top:var(--sp-3);font-size:13px">Tu pourras toujours importer plus tard depuis <strong>Outils → Onboarding</strong> ou <strong>MCPs → Importer</strong>.</p>
      `;
      return;
    }

    scanHost.innerHTML = `
      <div class="callout callout-info" style="margin-bottom:var(--sp-4)">
        <div>Trouvé <strong>${newMcps.length}</strong> nouveau(x) MCP(s) et <strong>${newProjects.length}</strong> projet(s) à importer.</div>
      </div>
      <div class="firstrun-import-summary">
        ${newMcps.length ? `<div class="firstrun-import-block"><h4>${I.cpu} MCPs (${newMcps.length})</h4><ul>${newMcps.slice(0, 6).map(m => `<li><span class="mono">${escapeHtml(m.id)}</span> <span class="dim" style="font-size:11px">${escapeHtml(m.transport || 'stdio')}</span></li>`).join('')}${newMcps.length > 6 ? `<li class="dim">…et ${newMcps.length - 6} autre(s)</li>` : ''}</ul></div>` : ''}
        ${newProjects.length ? `<div class="firstrun-import-block"><h4>${I.box} Workspaces (${newProjects.length})</h4><ul>${newProjects.slice(0, 6).map(p => {
          const guessId = (p.path || '').split(/[\\/]/).filter(Boolean).pop() || 'workspace';
          return `<li><span class="mono">${escapeHtml(guessId)}</span> <span class="dim" style="font-size:11px">${p.sessions} sessions</span></li>`;
        }).join('')}${newProjects.length > 6 ? `<li class="dim">…et ${newProjects.length - 6} autre(s)</li>` : ''}</ul></div>` : ''}
      </div>
      <div class="firstrun-import-actions">
        <button class="btn btn-primary" data-import-all>${I.download}<span>Tout importer (${newMcps.length + newProjects.length})</span></button>
        <button class="btn btn-ghost" data-pick>Choisir manuellement…</button>
      </div>
      <div class="firstrun-import-result" hidden></div>
    `;

    scanHost.querySelector('[data-import-all]').addEventListener('click', async () => {
      const btnEl = scanHost.querySelector('[data-import-all]');
      btnEl.disabled = true;
      btnEl.innerHTML = `<div class="spinner" style="width:12px;height:12px"></div><span>Import en cours…</span>`;
      const mcps = newMcps.map(m => ({
        id: m.id, name: m.id,
        transport: m.transport || (m.url ? 'http' : 'stdio'),
        command: m.command || '', args: m.args || [], env: m.env || {},
        cwd: m.cwd || '', url: m.url || '', headers: m.headers || {},
        status: 'disponible',
      }));
      const projects = newProjects.map(p => {
        const guessId = (p.path || '').split(/[\\/]/).filter(Boolean).pop() || 'workspace';
        const id = guessId.toLowerCase().replace(/[^a-z0-9_-]/g, '-').slice(0, 40);
        return { id, path: p.path, label: id, emoji: '📁', description: '' };
      });
      try {
        const r = await API.post('/api/setup/import', { mcps, projects });
        importedItems.mcps = (r.mcps || []).filter(x => x.ok).length;
        importedItems.workspaces = (r.workspaces || []).filter(x => x.ok).length;
        STATE.loading = true;
        const result = scanHost.querySelector('.firstrun-import-result');
        result.hidden = false;
        result.innerHTML = `
          <div class="callout" style="background:var(--ok-soft);border-color:rgba(52,211,153,0.3);border-left-color:var(--ok);margin-top:var(--sp-3)">
            <div>${I.check} <strong>Import réussi</strong> : ${importedItems.mcps} MCP(s), ${importedItems.workspaces} workspace(s) ajoutés.</div>
          </div>
        `;
        scanHost.querySelector('.firstrun-import-actions').style.display = 'none';
      } catch (e) {
        toastErr(e.message);
        btnEl.disabled = false;
        btnEl.innerHTML = `${I.download}<span>Tout importer</span>`;
      }
    });
    scanHost.querySelector('[data-pick]').addEventListener('click', () => {
      close(true);
      // Petit délai pour laisser la fermeture se finir avant d'ouvrir l'autre modale
      setTimeout(() => modalSetupWizard(), 280);
    });
  }

  // ───── Step 4 : Premier workspace ─────
  async function renderWorkspaceStep(host) {
    // Refresh state si on a importé
    if (importedItems.workspaces > 0 || importedItems.mcps > 0) {
      try {
        const ws = await API.get('/api/workspaces');
        STATE.workspaces = ws.workspaces || [];
      } catch {}
    }
    const wsCount = STATE.workspaces.length;

    host.innerHTML = `
      <div class="firstrun-step-header">
        <div class="firstrun-step-eyebrow">Étape 4 · Workspace</div>
        <h2>${wsCount > 0 ? 'Tes workspaces sont prêts' : 'Crée ton premier workspace'}</h2>
        <p>${wsCount > 0
          ? `Tu as déjà <strong>${wsCount}</strong> workspace${wsCount > 1 ? 's' : ''} configuré${wsCount > 1 ? 's' : ''}. Tu peux passer à la suite ou en ajouter un nouveau.`
          : 'Un workspace = un dossier projet où Claude Code va tourner. Tu peux en créer un depuis un template, ou enregistrer un dossier existant.'}</p>
      </div>
      <div class="firstrun-ws-actions">
        <button class="firstrun-ws-card" data-act="new">
          <div class="firstrun-ws-icon">${I.plus}</div>
          <h4>Créer depuis un template</h4>
          <p>Démarre un nouveau projet avec une structure prête (CLAUDE.md, settings, etc.)</p>
        </button>
        <button class="firstrun-ws-card" data-act="register">
          <div class="firstrun-ws-icon">${I.folder}</div>
          <h4>Enregistrer un dossier existant</h4>
          <p>Pointe Atelier vers un projet déjà sur ton disque, sans le déplacer.</p>
        </button>
        <button class="firstrun-ws-card" data-act="skip">
          <div class="firstrun-ws-icon">${I.right}</div>
          <h4>Plus tard</h4>
          <p>Tu pourras créer tes workspaces à tout moment depuis l'Accueil.</p>
        </button>
      </div>
      ${wsCount > 0 ? `<div class="firstrun-ws-list">
        <div class="dim mono" style="font-size:10.5px;letter-spacing:0.16em;text-transform:uppercase;margin-bottom:var(--sp-2)">Workspaces actuels</div>
        <div class="row" style="gap:6px;flex-wrap:wrap">
          ${STATE.workspaces.slice(0, 8).map(w => `<span class="chip">${escapeHtml(w.emoji || '📁')} ${escapeHtml(w.label || w.id)}</span>`).join('')}
          ${STATE.workspaces.length > 8 ? `<span class="chip dim">+${STATE.workspaces.length - 8}</span>` : ''}
        </div>
      </div>` : ''}
    `;
    host.querySelector('[data-act="new"]').addEventListener('click', () => {
      close(true); setTimeout(() => modalNewWorkspace(), 280);
    });
    host.querySelector('[data-act="register"]').addEventListener('click', () => {
      close(true); setTimeout(() => modalRegisterExisting(), 280);
    });
    host.querySelector('[data-act="skip"]').addEventListener('click', goNext);
  }

  // ───── Step 5 : Tips & shortcuts ─────
  function renderTipsStep(host) {
    host.innerHTML = `
      <div class="firstrun-step-header">
        <div class="firstrun-step-eyebrow">Étape 5 · C'est parti !</div>
        <h2>Quelques astuces pour bien démarrer</h2>
        <p>Tu peux toujours retrouver ces infos (et bien plus) sur la page <strong>Aide</strong>.</p>
      </div>
      <div class="firstrun-tips">
        <div class="firstrun-tip">
          <div class="firstrun-tip-key"><kbd>/</kbd> ou <kbd>Ctrl</kbd>+<kbd>K</kbd></div>
          <div>Ouvre la <strong>palette de recherche</strong> globale — workspaces, MCPs, skills, templates, actions rapides.</div>
        </div>
        <div class="firstrun-tip">
          <div class="firstrun-tip-key"><kbd>g</kbd> + lettre</div>
          <div>Navigation par chord : <kbd>g h</kbd> = Accueil, <kbd>g m</kbd> = MCPs, <kbd>g k</kbd> = Skills, <kbd>g a</kbd> = Aide…</div>
        </div>
        <div class="firstrun-tip">
          <div class="firstrun-tip-key"><kbd>n</kbd> · <kbd>m</kbd> · <kbd>s</kbd></div>
          <div><kbd>n</kbd> = nouveau workspace, <kbd>m</kbd> = nouveau MCP, <kbd>s</kbd> = sync tous les workspaces.</div>
        </div>
        <div class="firstrun-tip">
          <div class="firstrun-tip-key">${I.key}</div>
          <div>Stocke tes secrets dans <code class="mono">.env.local</code>, et utilise <code class="mono">\${VAR}</code> dans tes MCPs. Va dans <strong>Outils → Variables d'env</strong> pour les gérer en GUI.</div>
        </div>
        <div class="firstrun-tip">
          <div class="firstrun-tip-key">${I.refresh}</div>
          <div>Après chaque modif d'un MCP, clique <strong>Sync tous</strong> sur l'Accueil pour distribuer les configs vers les workspaces ciblés.</div>
        </div>
        <div class="firstrun-tip">
          <div class="firstrun-tip-key">${I.book}</div>
          <div>Coincé ? La page <strong>Aide</strong> (<kbd>g a</kbd>) couvre tout : MCPs, skills, scope plugins, dépannage.</div>
        </div>
      </div>
      ${(importedItems.mcps + importedItems.workspaces > 0) ? `
        <div class="callout" style="background:var(--ok-soft);border-color:rgba(52,211,153,0.3);border-left-color:var(--ok);margin-top:var(--sp-4)">
          <div>${I.check} Setup terminé : <strong>${importedItems.mcps}</strong> MCP(s), <strong>${importedItems.workspaces}</strong> workspace(s) importés. Bon travail !</div>
        </div>` : ''}
    `;
  }

  render();
}

/* ================================================================
   SYSTEM UPDATE — vérification & application via git
   ================================================================ */
const UPDATE_CHECK_KEY = 'atelier-last-update-check';
const UPDATE_CHECK_INTERVAL_MS = 6 * 60 * 60 * 1000;  // 6h

async function checkForUpdates({ force = false } = {}) {
  // Anti-spam : ne check le distant qu'une fois par UPDATE_CHECK_INTERVAL_MS
  let shouldCheckRemote = force;
  if (!force) {
    try {
      const last = parseInt(localStorage.getItem(UPDATE_CHECK_KEY) || '0', 10);
      shouldCheckRemote = (Date.now() - last) > UPDATE_CHECK_INTERVAL_MS;
    } catch { shouldCheckRemote = true; }
  }

  let info;
  try { info = await API.get(`/api/system/version?check=${shouldCheckRemote ? '1' : '0'}`); }
  catch { return null; }

  if (shouldCheckRemote && info.fetched) {
    try { localStorage.setItem(UPDATE_CHECK_KEY, String(Date.now())); } catch {}
  }
  STATE.systemVersion = info;
  return info;
}

function renderUpdateBadge(info) {
  // Retire l'ancien badge si présent
  const existing = $('#nav-update-badge');
  if (existing) existing.remove();

  if (!info || !info.is_git || !info.behind || info.behind <= 0) return;

  // Insère un bouton de mise à jour dans le footer de la sidebar
  const footer = $('.sidebar-footer');
  if (!footer) return;
  const badge = el('button', 'update-badge');
  badge.id = 'nav-update-badge';
  badge.type = 'button';
  badge.innerHTML = `
    <span class="update-badge-dot"></span>
    <span class="update-badge-text">${info.behind} mise${info.behind > 1 ? 's' : ''} à jour disponible${info.behind > 1 ? 's' : ''}</span>
    <span class="update-badge-icon">${I.right}</span>
  `;
  badge.addEventListener('click', () => modalSystemUpdate());
  footer.insertBefore(badge, footer.firstChild);
}

async function modalSystemUpdate() {
  const body = el('div');
  body.innerHTML = `<div class="page-loader"><div class="spinner"></div><span>Vérification…</span></div>`;
  const closeBtn = btn('Fermer', 'btn-ghost');
  const { close } = openModal({ title: 'Mises à jour Atelier', body, footer: closeBtn, wide: true });
  closeBtn.addEventListener('click', close);

  // Force un fetch frais à l'ouverture
  const info = await checkForUpdates({ force: true });
  if (!info) {
    body.innerHTML = `<div class="error-box">Impossible de vérifier les mises à jour.</div>`;
    return;
  }

  if (!info.is_git) {
    body.innerHTML = `
      <div class="callout callout-info">
        <div>
          <strong>Auto-update indisponible.</strong>
          ${escapeHtml(info.reason || 'Cette installation n\'est pas un dépôt git.')}
          <p style="margin:var(--sp-2) 0 0">Pour activer l'auto-update, clone le repo officiel d'Atelier dans <code class="mono">C:\\claude-workspace</code>.</p>
        </div>
      </div>
    `;
    return;
  }

  if (info.fetch_error) {
    body.innerHTML = `
      <div class="error-box" style="margin-bottom:var(--sp-3)">${escapeHtml(info.fetch_error)}</div>
      <p class="muted">Vérifie ta connexion réseau et que le remote git est accessible.</p>
    `;
    return;
  }

  // Clean le loader avant d'appendChild les vraies sections
  body.innerHTML = '';

  // ───── Header avec version locale (uniquement si updates dispos ou modifs locales) ─────
  if (info.behind > 0 || (info.dirty && info.behind > 0)) {
    const head = el('div');
    head.innerHTML = `
      <div class="update-version-header">
        <div>
          <div class="dim mono" style="font-size:10.5px;letter-spacing:0.16em;text-transform:uppercase">Version locale</div>
          <div class="row" style="gap:var(--sp-2);margin-top:4px">
            <span class="mono" style="font-size:14px;font-weight:600">${escapeHtml(info.head)}</span>
            ${info.branch ? `<span class="badge mono">${escapeHtml(info.branch)}</span>` : ''}
          </div>
          ${info.head_message ? `<div class="dim" style="font-size:12px;margin-top:4px">${escapeHtml(info.head_message)}</div>` : ''}
        </div>
        ${info.upstream ? `<div class="dim mono" style="font-size:11px;text-align:right">Tracking<br>${escapeHtml(info.upstream)}</div>` : ''}
      </div>
    `;
    body.appendChild(head);
  }

  // ───── Si déjà à jour ─────
  if (info.behind === 0) {
    body.appendChild(el('div', 'update-uptodate', `
      ${I.check}
      <div>
        <strong>Tu es à jour</strong>
        <span class="dim">Branche <code class="mono">${escapeHtml(info.upstream || 'origin')}</code></span>
      </div>
    `));
    return;
  }

  // ───── Mises à jour disponibles ─────
  body.appendChild(el('div', 'section-label', `<span class="num">▾</span> ${info.behind} commit${info.behind > 1 ? 's' : ''} à venir`));

  const commitList = el('div', 'update-commits');
  for (const c of info.commits) {
    const item = el('div', 'update-commit');
    item.innerHTML = `
      <div class="update-commit-meta">
        <span class="mono" style="color:var(--accent);font-weight:600">${escapeHtml(c.sha)}</span>
        <span class="dim" style="font-size:11px">${escapeHtml(c.relative)} · ${escapeHtml(c.author || '?')}</span>
      </div>
      <div class="update-commit-msg">${escapeHtml(c.subject)}</div>
    `;
    commitList.appendChild(item);
  }
  if (info.behind > info.commits.length) {
    commitList.appendChild(el('div', 'dim', `<small>…et ${info.behind - info.commits.length} commit(s) plus anciens</small>`));
  }
  body.appendChild(commitList);

  // Avertissement modifs locales
  if (info.dirty) {
    body.appendChild(el('div', 'callout callout-warn', `
      <div>
        <strong>Mise à jour bloquée :</strong> tu as ${info.dirty_files.length}+ modification(s) locale(s) non committée(s). Commit ou stash d'abord.
        <ul class="help-list" style="margin-top:6px">${info.dirty_files.slice(0, 6).map(f => `<li class="mono" style="font-size:11px">${escapeHtml(f)}</li>`).join('')}</ul>
      </div>
    `));
    return;
  }

  // Action button
  body.appendChild(el('div', 'callout callout-info', `
    <div>
      Atelier va exécuter <code class="mono">git pull --ff-only</code>. Tes données personnelles (registre, workspaces, .env.local) sont préservées via <code class="mono">.gitignore</code>.
    </div>
  `));

  const updateRow = el('div');
  updateRow.style.cssText = 'display:flex;justify-content:flex-end;gap:var(--sp-2);margin-top:var(--sp-4)';
  const applyBtn = btn(`Appliquer la mise à jour`, 'btn-primary', I.download);
  applyBtn.addEventListener('click', async () => {
    applyBtn.disabled = true;
    applyBtn.innerHTML = `<div class="spinner" style="width:12px;height:12px"></div><span>Application en cours…</span>`;
    let r;
    try { r = await API.post('/api/system/update', {}); }
    catch (e) {
      toastErr('Erreur : ' + e.message);
      applyBtn.disabled = false;
      applyBtn.innerHTML = `${I.download}<span>Réessayer</span>`;
      return;
    }
    if (!r.ok) {
      toastErr(r.error || 'Échec');
      applyBtn.disabled = false;
      applyBtn.innerHTML = `${I.download}<span>Réessayer</span>`;
      return;
    }
    // Succès
    body.innerHTML = `
      <div class="callout" style="background:var(--ok-soft);border-color:rgba(52,211,153,0.3);border-left-color:var(--ok)">
        <div>
          ${I.check} <strong>Mise à jour appliquée</strong> · <span class="mono">${escapeHtml(r.from)}</span> → <span class="mono">${escapeHtml(r.to)}</span>
          <p style="margin:var(--sp-2) 0 0">${escapeHtml(r.message)}</p>
        </div>
      </div>
      <div class="section-label" style="margin-top:var(--sp-4)"><span class="num">▾</span> ${(r.files_changed || []).length} fichier(s) modifié(s)</div>
      <div class="update-files">
        ${(r.files_changed || []).slice(0, 30).map(f => {
          const isPy = f.endsWith('.py');
          const cls = isPy ? 'text-warn' : 'dim';
          return `<div class="mono ${cls}" style="font-size:11.5px;padding:3px 0">${isPy ? '🔧 ' : '✓ '}${escapeHtml(f)}</div>`;
        }).join('')}
        ${(r.files_changed || []).length > 30 ? `<div class="dim" style="font-size:11px">…et ${r.files_changed.length - 30} autre(s)</div>` : ''}
      </div>
      ${r.needs_restart ? `
        <div class="callout callout-warn" style="margin-top:var(--sp-4)">
          <div>
            <strong>Redémarrage requis</strong> — des fichiers Python ont changé. Ferme la fenêtre console du dashboard et relance <code class="mono">scripts/start-dashboard.bat</code>.
          </div>
        </div>` : `
        <div style="margin-top:var(--sp-4);text-align:center">
          <button class="btn btn-primary" onclick="location.reload()">${I.refresh}<span>Recharger la page</span></button>
        </div>
      `}
    `;
    // Rafraîchit le badge
    setTimeout(() => checkForUpdates({ force: true }).then(renderUpdateBadge), 500);
  });
  updateRow.appendChild(applyBtn);
  body.appendChild(updateRow);
}

/* ================================================================
   GLOBAL MCP CONFLICTS — détection des doublons avec ~/.claude
   ================================================================ */
async function modalGlobalConflicts() {
  const body = el('div');
  body.innerHTML = `<div class="page-loader"><div class="spinner"></div><span>Scan des fichiers Claude globaux…</span></div>`;
  const closeBtn = btn('Fermer', 'btn-ghost');
  const { close } = openModal({ title: 'Conflits avec la config Claude globale', body, footer: closeBtn, wide: true });
  closeBtn.addEventListener('click', close);

  const refresh = async () => {
    body.innerHTML = `<div class="page-loader"><div class="spinner"></div><span>Scan…</span></div>`;
    let data;
    try { data = await API.get('/api/mcps/conflicts'); }
    catch (e) { body.innerHTML = `<div class="error-box">${escapeHtml(e.message)}</div>`; return; }

    body.innerHTML = '';

    // Intro
    body.appendChild(el('div', 'callout callout-info', `
      <div>
        <strong>Pourquoi c'est important ?</strong>
        Les MCPs déclarés dans <code class="mono">~/.claude.json</code> ou <code class="mono">~/.claude/settings.json</code> sont actifs <strong>globalement</strong>, partout. Si Atelier en sync un avec le même nom dans un workspace, Claude Code voit la définition deux fois (project &gt; user). Ça marche, mais tu peux te retrouver avec une vieille version qui traîne.
      </div>
    `));

    // ─── Section CONFLITS (même ID dans les deux) ───
    const conflicts = data.conflicts || [];
    body.appendChild(el('div', 'section-label', `<span class="num">A.</span> Doublons (${conflicts.length})`));

    if (!conflicts.length) {
      body.appendChild(el('div', 'callout', `<div>${I.check} Aucun doublon : ton registre Atelier et ta config Claude globale sont disjoints.</div>`));
    } else {
      body.appendChild(el('p', 'muted', `<small>Ces MCPs sont présents dans Atelier <strong>et</strong> dans la config Claude globale. Tu peux les retirer de la config globale (Atelier reste la source de vérité) — un backup <code class="mono">.bak</code> est créé automatiquement.</small>`));
      const list = el('div', 'conflict-list');
      for (const c of conflicts) {
        const item = el('div', 'conflict-item');
        item.innerHTML = `
          <div class="conflict-main">
            <div class="row" style="gap:var(--sp-2);align-items:center">
              <strong class="mono" style="font-size:13px">${escapeHtml(c.id)}</strong>
              <span class="badge badge-warn">${escapeHtml(c.global_transport)}</span>
              <span class="badge">${escapeHtml(c.source_label)}</span>
            </div>
            <div class="dim mono" style="font-size:11px;margin-top:4px">${escapeHtml(c.global_command || c.global_url || '—')}</div>
            <div class="dim" style="font-size:11.5px;margin-top:4px">
              Atelier : statut <strong>${escapeHtml(c.registry_status)}</strong>${c.registry_workspaces.length ? ` · scope <span class="mono">${c.registry_workspaces.map(escapeHtml).join(', ')}</span>` : ' · <span class="text-warn">aucun workspace ciblé</span>'}
            </div>
          </div>
        `;
        const removeBtn = btn('Retirer du global', 'btn-sm btn-danger', I.trash);
        removeBtn.title = `Retire ${c.id} de ${c.source_label}`;
        removeBtn.addEventListener('click', () => confirmDialog(
          `Retirer "${c.id}" de ${c.source_label} ? La définition reste dans le registre Atelier (un backup .bak est créé).`,
          async () => {
            try {
              await API.post('/api/mcps/conflicts/remove', { id: c.id, source: c.source });
              toastOk(`${c.id} retiré de ${c.source_label}`);
              await refresh();
            } catch (e) { toastErr(e.message); }
          },
          { danger: true }
        ));
        item.appendChild(removeBtn);
        list.appendChild(item);
      }
      body.appendChild(list);
    }

    // ─── Section ORPHELINS (dans Claude global mais pas dans Atelier) ───
    const orphans = data.orphans || [];
    body.appendChild(el('div', 'section-label', `<span class="num">B.</span> Orphelins (${orphans.length})`));

    if (!orphans.length) {
      body.appendChild(el('div', 'callout', `<div>${I.check} Aucun MCP global non géré par Atelier.</div>`));
    } else {
      body.appendChild(el('p', 'muted', `<small>Ces MCPs sont présents dans la config Claude globale mais Atelier ne les connaît pas. Tu peux les <strong>migrer</strong> vers Atelier (import + retrait de la source) ou simplement les <strong>retirer</strong> s'ils sont obsolètes.</small>`));
      const list = el('div', 'conflict-list');
      for (const o of orphans) {
        const item = el('div', 'conflict-item');
        item.innerHTML = `
          <div class="conflict-main">
            <div class="row" style="gap:var(--sp-2);align-items:center">
              <strong class="mono" style="font-size:13px">${escapeHtml(o.id)}</strong>
              <span class="badge">${escapeHtml(o.transport)}</span>
              <span class="badge">${escapeHtml(o.source_label)}</span>
            </div>
            <div class="dim mono" style="font-size:11px;margin-top:4px">${escapeHtml(o.command || o.url || '—')}</div>
          </div>
        `;
        const actions = el('div', 'row');
        actions.style.gap = '4px';
        const migrate = btn('Migrer', 'btn-sm btn-primary', I.download);
        migrate.title = 'Importer dans le registre Atelier puis retirer de la source';
        migrate.addEventListener('click', () => confirmDialog(
          `Migrer "${o.id}" vers Atelier ? Il sera importé dans le registre (sans workspace ciblé) et retiré de ${o.source_label}.`,
          async () => {
            try {
              await API.post('/api/mcps/conflicts/migrate', { id: o.id, source: o.source });
              toastOk(`${o.id} migré vers Atelier`);
              STATE.loading = true;
              await refresh();
            } catch (e) { toastErr(e.message); }
          }
        ));
        const remove = btn('', 'btn-sm btn-ghost btn-icon-only btn-danger', I.trash);
        remove.title = `Retirer ${o.id} de ${o.source_label}`;
        remove.addEventListener('click', () => confirmDialog(
          `Retirer "${o.id}" de ${o.source_label} ? Action irréversible (un backup .bak est créé).`,
          async () => {
            try {
              await API.post('/api/mcps/conflicts/remove', { id: o.id, source: o.source });
              toastOk(`${o.id} retiré de ${o.source_label}`);
              await refresh();
            } catch (e) { toastErr(e.message); }
          },
          { danger: true }
        ));
        actions.append(migrate, remove);
        item.appendChild(actions);
        list.appendChild(item);
      }
      body.appendChild(list);
    }

    // Footer info
    body.appendChild(el('div', 'dim', `<small style="font-size:11px;margin-top:var(--sp-4);display:block">Sources scannées : ${data.sources.map(s => `<code class="mono" style="font-size:10px">${escapeHtml(s.split(/[\\\\/]/).slice(-2).join('/'))}</code>`).join(', ')}</small>`));
  };

  await refresh();
}

/* ================================================================
   ONBOARDING WIZARD — scan ~/.claude/ et import en lot
   ================================================================ */
async function modalSetupWizard() {
  const body = el('div');
  body.innerHTML = `
    <div class="page-loader"><div class="spinner"></div><span>Scan de la config Claude…</span></div>
  `;
  const cancel = btn('Annuler', 'btn-ghost');
  const importBtn = btn('Importer la sélection', 'btn-primary', I.download);
  importBtn.disabled = true;
  const { close } = openModal({ title: 'Importer la config Claude existante', body, footer: [cancel, importBtn], wide: true });
  cancel.addEventListener('click', close);

  let scan;
  try { scan = await API.get('/api/setup/scan'); }
  catch (e) { body.innerHTML = `<div class="error-box">${escapeHtml(e.message)}</div>`; return; }

  const mcps = scan.mcps || [];
  const projects = scan.projects || [];
  const newMcps = mcps.filter(m => !m.already_registered);
  const newProjects = projects.filter(p => !p.already_registered && p.path_exists);

  // Build form
  body.innerHTML = '';
  body.appendChild(el('div', 'wizard-intro', `
    <p style="margin:0 0 var(--sp-2);font-size:13px">Le scan a trouvé <strong>${mcps.length}</strong> MCP(s) et <strong>${projects.length}</strong> projet(s) Claude Code. Coche ceux que tu veux importer dans Atelier.</p>
    <p class="dim" style="margin:0;font-size:12px">Les éléments déjà enregistrés sont grisés.</p>
  `));

  // ─── MCPs section ───
  body.appendChild(el('div', 'section-label', `<span class="num">A.</span> MCPs (${newMcps.length} nouveaux / ${mcps.length} total)`));
  if (mcps.length === 0) {
    body.appendChild(el('div', 'dim', '<small>Aucun MCP trouvé dans ~/.claude/settings.json ou settings.local.json.</small>'));
  } else {
    const mcpList = el('div', 'wizard-list');
    for (const m of mcps) {
      const item = el('label', 'wizard-item' + (m.already_registered ? ' is-registered' : ''));
      const cb = `<input type="checkbox" data-kind="mcp" data-id="${escapeHtml(m.id)}" ${m.already_registered ? 'disabled' : 'checked'}>`;
      item.innerHTML = `
        ${cb}
        <div class="wizard-item-main">
          <div class="wizard-item-name mono">${escapeHtml(m.id)}</div>
          <div class="wizard-item-meta">
            <span class="badge badge-info">${escapeHtml(m.transport || 'stdio')}</span>
            ${m.already_registered ? '<span class="badge badge-warn">déjà importé</span>' : '<span class="badge badge-ok">nouveau</span>'}
            ${m.command ? `<span class="dim mono" style="font-size:11px">${escapeHtml(m.command)}${(m.args || []).length ? ' …' : ''}</span>` : ''}
            ${m.url ? `<span class="dim mono" style="font-size:11px">${escapeHtml(m.url)}</span>` : ''}
          </div>
        </div>
      `;
      // Stash data on element
      item._mcp = m;
      mcpList.appendChild(item);
    }
    body.appendChild(mcpList);
  }

  // ─── Projects section ───
  body.appendChild(el('div', 'section-label', `<span class="num">B.</span> Workspaces (${newProjects.length} nouveaux / ${projects.length} total)`));
  if (projects.length === 0) {
    body.appendChild(el('div', 'dim', '<small>Aucun projet trouvé dans ~/.claude/projects/.</small>'));
  } else {
    const projList = el('div', 'wizard-list');
    for (const p of projects) {
      const guessId = (p.path || '').split(/[\\\/]/).filter(Boolean).pop() || 'workspace';
      const id = guessId.toLowerCase().replace(/[^a-z0-9_-]/g, '-').slice(0, 40);
      const disabled = p.already_registered || !p.path_exists;
      const item = el('label', 'wizard-item' + (disabled ? ' is-registered' : ''));
      const cb = `<input type="checkbox" data-kind="project" data-encoded="${escapeHtml(p.encoded)}" ${disabled ? 'disabled' : 'checked'}>`;
      const tags = [];
      if (p.already_registered) tags.push('<span class="badge badge-warn">déjà importé</span>');
      else if (!p.path_exists) tags.push('<span class="badge badge-err">dossier introuvable</span>');
      else tags.push('<span class="badge badge-ok">nouveau</span>');
      tags.push(`<span class="badge">${p.sessions} session${p.sessions > 1 ? 's' : ''}</span>`);
      tags.push(`<span class="badge">source: ${p.path_source}</span>`);
      item.innerHTML = `
        ${cb}
        <div class="wizard-item-main">
          <div class="wizard-item-name">
            <span class="mono">${escapeHtml(id)}</span>
            <span class="dim" style="font-size:11px;margin-left:6px">${escapeHtml(p.path || '(chemin inconnu)')}</span>
          </div>
          <div class="wizard-item-meta">${tags.join(' ')}</div>
        </div>
        <input type="text" class="input mono wizard-id-input" value="${escapeHtml(id)}" ${disabled ? 'disabled' : ''} style="max-width:160px;font-size:12px">
      `;
      item._proj = p;
      projList.appendChild(item);
    }
    body.appendChild(projList);
  }

  // Toolbar de sélection
  const tools = el('div', 'wizard-tools');
  const selAll = btn('Tout cocher', 'btn-sm btn-ghost');
  const selNone = btn('Tout décocher', 'btn-sm btn-ghost');
  selAll.addEventListener('click', () => body.querySelectorAll('input[type=checkbox]:not(:disabled)').forEach(cb => cb.checked = true));
  selNone.addEventListener('click', () => body.querySelectorAll('input[type=checkbox]:not(:disabled)').forEach(cb => cb.checked = false));
  tools.append(selAll, selNone);
  body.insertBefore(tools, body.children[1]);

  importBtn.disabled = (newMcps.length + newProjects.length === 0);

  importBtn.addEventListener('click', async () => {
    importBtn.disabled = true;
    const selectedMcps = [];
    const selectedProjects = [];
    for (const item of body.querySelectorAll('.wizard-item')) {
      const cb = item.querySelector('input[type=checkbox]');
      if (!cb.checked || cb.disabled) continue;
      if (cb.dataset.kind === 'mcp') {
        const m = item._mcp;
        selectedMcps.push({
          id: m.id,
          name: m.id,
          transport: m.transport || (m.url ? 'http' : 'stdio'),
          command: m.command || '',
          args: m.args || [],
          env: m.env || {},
          url: m.url || '',
          status: 'disponible',
        });
      } else if (cb.dataset.kind === 'project') {
        const p = item._proj;
        const idInput = item.querySelector('.wizard-id-input');
        const idValue = (idInput.value || '').trim() || 'workspace';
        selectedProjects.push({
          id: idValue,
          path: p.path,
          label: idValue,
          emoji: '📁',
          description: '',
        });
      }
    }
    if (!selectedMcps.length && !selectedProjects.length) {
      toastErr('Aucun élément sélectionné');
      importBtn.disabled = false;
      return;
    }
    try {
      const r = await API.post('/api/setup/import', { mcps: selectedMcps, projects: selectedProjects });
      const mcpsOk = (r.mcps || []).filter(x => x.ok).length;
      const wsOk = (r.workspaces || []).filter(x => x.ok).length;
      toastOk(`Import : ${mcpsOk} MCP(s), ${wsOk} workspace(s)`);
      close();
      STATE.loading = true;
      route();
    } catch (e) {
      toastErr(e.message);
      importBtn.disabled = false;
    }
  });
}

function modalRegisterExisting() {
  const body = el('div');
  body.innerHTML = `
    <p class="muted" style="margin-top:0">Enregistre un dossier existant comme workspace, sans créer de fichiers.</p>
    <div class="field"><label class="field-label">ID *</label><input class="input mono" name="id" placeholder="mon-projet"></div>
    <div class="field"><label class="field-label">Chemin absolu *</label><input class="input mono" name="path" placeholder="C:\\path\\to\\folder"></div>
    <div class="field-row">
      <div class="field"><label class="field-label">Label</label><input class="input" name="label"></div>
      <div class="field"><label class="field-label">Emoji</label><input class="input" name="emoji" value="📁"></div>
    </div>
    <div class="field"><label class="field-label">Description</label><input class="input" name="description"></div>
  `;
  const cancel = btn('Annuler', 'btn-ghost');
  const ok = btn('Enregistrer', 'btn-primary', I.plus);
  const { close } = openModal({ title: 'Enregistrer un dossier existant', body, footer: [cancel, ok] });
  cancel.addEventListener('click', close);
  ok.addEventListener('click', async () => {
    const get = n => body.querySelector(`[name=${n}]`).value.trim();
    const payload = { id: get('id'), path: get('path'), label: get('label'), emoji: get('emoji'), description: get('description') };
    if (!payload.id || !payload.path) { toastErr('ID et chemin requis'); return; }
    try {
      const r = await API.post('/api/setup/import', { mcps: [], projects: [payload] });
      const ws = (r.workspaces || [])[0];
      if (!ws || !ws.ok) { toastErr((ws && ws.error) || 'Échec'); return; }
      toastOk('Workspace enregistré');
      close(); STATE.loading = true;
      location.hash = `#/workspace/${ws.id}`;
    } catch (e) { toastErr(e.message); }
  });
}

function modalImportMCPs() {
  const body = el('div');
  body.innerHTML = `
    <p class="muted" style="margin-top:0">Colle un objet MCP, un tableau, ou la section <code>mcpServers</code> d'un fichier Claude.</p>
    <div class="field"><label class="field-label">JSON</label><textarea class="textarea" name="raw" rows="14" placeholder='{"mcpServers": {...}}'></textarea></div>
    <div class="field"><label class="field-label">Workspaces cibles (optionnel — surchage)</label><input class="input mono" name="ws" placeholder="dev,homeassistant ou *"></div>
  `;
  const cancel = btn('Annuler', 'btn-ghost');
  const imp = btn('Importer', 'btn-primary', I.download);
  const { close } = openModal({ title: 'Importer des MCPs', body, footer: [cancel, imp], wide: true });
  cancel.addEventListener('click', close);
  imp.addEventListener('click', async () => {
    let obj;
    try { obj = JSON.parse(body.querySelector('[name=raw]').value); }
    catch (e) { toastErr('JSON invalide : ' + e.message); return; }
    const ws = body.querySelector('[name=ws]').value.split(',').map(s => s.trim()).filter(Boolean);
    if (ws.length) obj.workspaces = ws;
    try {
      const r = await API.post('/api/mcps/import', obj);
      const ok = (r.results || []).filter(x => x.ok).length;
      toastOk(`${ok} MCP(s) importés`);
      close(); STATE.loading = true; route();
    } catch (e) { toastErr(e.message); }
  });
}

/* ================================================================
   PAGE: PLUGINS
   ================================================================ */
async function renderPlugins() {
  setBreadcrumbs([{ label: 'Plugins' }]);
  const installBtn = btn('Installer', 'btn-primary', I.plus);
  installBtn.addEventListener('click', () => modalInstallPlugin());
  setTopbarActions([installBtn]);

  const c = $('#content');
  c.innerHTML = '';
  const page = el('div', 'page');
  page.appendChild(el('div', 'page-header', `
    <div class="page-header-text">
      <div class="page-eyebrow"><span class="index">02.</span><span>Extensions</span></div>
      <h1 class="page-title">Plugins</h1>
      <p class="page-subtitle">Plugins Claude Code installés et leur scope par workspace.</p>
    </div>
  `));

  // Installed
  page.appendChild(el('div', 'section-label', '<span class="num">A.</span> Installés'));
  const installedHost = el('div');
  page.appendChild(installedHost);
  loadInstalledPlugins(installedHost);

  // Per-plugin scope manager
  page.appendChild(el('div', 'section-label', '<span class="num">B.</span> Scope par workspace'));
  const scopeHost = el('div');
  page.appendChild(scopeHost);
  renderPluginScope(scopeHost);

  c.appendChild(page);
}

async function loadInstalledPlugins(host) {
  host.innerHTML = '<div class="page-loader"><div class="spinner"></div></div>';
  try {
    const data = await API.get('/api/plugins/installed');
    // API renvoie {cross, on_disk, marketplaces, orphans_on_disk}
    const installed = data.cross || [];
    const orphans = data.orphans_on_disk || [];
    // Stash les marketplaces pour le bouton Installer
    STATE.marketplaces = data.marketplaces || [];

    if (!installed.length && !orphans.length) {
      host.innerHTML = '<div class="empty"><div class="empty-title">Aucun plugin installé</div><p class="muted">Clique sur <strong>Installer</strong> pour parcourir les marketplaces.</p></div>';
      return;
    }
    host.innerHTML = '';

    if (installed.length) {
      const wrap = el('div', 'table-frame');
      wrap.innerHTML = `
        <table class="table">
          <thead><tr><th>Plugin</th><th>Description</th><th>État</th><th></th></tr></thead>
          <tbody></tbody>
        </table>
      `;
      const tb = wrap.querySelector('tbody');
      for (const p of installed) {
        const tr = el('tr');
        const [shortId, mkt] = p.id.includes('@') ? p.id.split('@') : [p.id, null];
        const absent = !p.on_disk ? '<span class="badge badge-warn" title="Absent du disque" style="margin-left:6px">absent</span>' : '';
        tr.innerHTML = `
          <td>
            <div><strong style="font-size:13px">${escapeHtml(shortId)}</strong>${absent}</div>
            ${mkt ? `<div class="dim mono" style="font-size:10.5px">${escapeHtml(mkt)}</div>` : ''}
          </td>
          <td><div class="muted" style="font-size:12.5px;max-width:520px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escapeHtml(p.description || '')}">${escapeHtml(p.description || '—')}</div></td>
          <td></td>
          <td style="text-align:right"></td>
        `;
        const sw = el('label', 'switch', `<input type="checkbox" ${p.enabled ? 'checked' : ''}><span class="switch-slider"></span>`);
        sw.querySelector('input').addEventListener('change', async (ev) => {
          const url = ev.target.checked ? '/api/plugins/enable' : '/api/plugins/disable';
          try { await API.post(url, { plugin_id: p.id }); toastOk('Mis à jour'); }
          catch (e) { toastErr(e.message); ev.target.checked = !ev.target.checked; }
        });
        tr.children[2].appendChild(sw);

        const actions = tr.children[3];
        const rm = btn('', 'btn-sm btn-ghost btn-icon-only btn-danger', I.trash);
        rm.title = 'Désinstaller';
        rm.addEventListener('click', () => confirmDialog(`Désinstaller ${p.id} ?`, async () => {
          try {
            await API.post('/api/plugins/uninstall-soft', { plugin_id: p.id, remove_files: false });
            toastOk('Désinstallé'); STATE.loading = true; route();
          } catch (e) { toastErr(e.message); }
        }, { danger: true }));
        actions.appendChild(rm);
        tb.appendChild(tr);
      }
      host.appendChild(wrap);
    }

    if (orphans.length) {
      const orphHeader = el('div', 'dim');
      orphHeader.style.cssText = 'font-size:12px;margin:var(--sp-3) 0 var(--sp-2)';
      orphHeader.textContent = `${orphans.length} dossier(s) orphelin(s) sur disque (présents mais non listés dans settings.json)`;
      host.appendChild(orphHeader);
      const wrap = el('div', 'table-frame');
      wrap.innerHTML = `<table class="table"><thead><tr><th>Dossier</th><th>Chemin</th></tr></thead><tbody></tbody></table>`;
      const tb = wrap.querySelector('tbody');
      for (const o of orphans) {
        const tr = el('tr');
        tr.innerHTML = `<td><span class="mono">${escapeHtml(o.dir_name)}</span></td><td><span class="dim mono" style="font-size:11.5px">${escapeHtml(o.rel_path)}</span></td>`;
        tb.appendChild(tr);
      }
      host.appendChild(wrap);
    }
  } catch (e) { host.innerHTML = `<div class="error-box">${escapeHtml(e.message)}</div>`; }
}

async function renderPluginScope(host) {
  host.innerHTML = '<div class="page-loader"><div class="spinner"></div></div>';

  const pluginIds = Object.keys(STATE.plugins.enabled || {});
  if (!pluginIds.length) {
    host.innerHTML = '<div class="dim" style="font-size:12.5px;padding:var(--sp-3)">Aucun plugin installé pour configurer le scope.</div>';
    return;
  }
  if (!STATE.workspaces.length) {
    host.innerHTML = '<div class="dim" style="font-size:12.5px;padding:var(--sp-3)">Aucun workspace.</div>';
    return;
  }

  // UI : sélecteur plugin + filtre workspace + actions de masse + liste
  host.innerHTML = `
    <div class="scope-toolbar">
      <div class="field" style="flex:2;margin:0;min-width:240px">
        <label class="field-label">Plugin</label>
        <select class="select" name="plugin">
          ${pluginIds.map(id => `<option value="${escapeHtml(id)}">${escapeHtml(id.split('@')[0])}${id.includes('@') ? ` <span>· ${escapeHtml(id.split('@')[1])}</span>` : ''}</option>`).join('')}
        </select>
      </div>
      <div class="field" style="flex:1;margin:0;min-width:200px">
        <label class="field-label">Filtrer workspaces</label>
        <input class="input input-search" name="filter" placeholder="Recherche…">
      </div>
      <div class="scope-bulk">
        <span class="dim" style="font-size:11px;text-transform:uppercase;letter-spacing:0.1em">Masse :</span>
        <button class="btn btn-sm" data-bulk="on">Activer tout</button>
        <button class="btn btn-sm" data-bulk="off">Désactiver tout</button>
        <button class="btn btn-sm btn-ghost" data-bulk="reset">Réinitialiser</button>
      </div>
    </div>
    <div class="scope-summary"></div>
    <div class="scope-list"></div>
  `;

  const sel = host.querySelector('[name=plugin]');
  const filterInput = host.querySelector('[name=filter]');
  const summaryEl = host.querySelector('.scope-summary');
  const listEl = host.querySelector('.scope-list');

  let cache = {};  // ws_id -> {global, effective, overridden}
  let currentPid = sel.value;

  const fetchData = async (pid) => {
    cache = {};
    const r = await Promise.all(STATE.workspaces.map(async w => {
      try { const data = await API.get(`/api/workspaces/${w.id}/plugins`); return [w.id, (data.plugins || {})[pid]]; }
      catch { return [w.id, null]; }
    }));
    cache = Object.fromEntries(r);
  };

  const stateOf = (info) => {
    if (!info) return 'inherit';
    if (info.overridden) return info.effective ? 'on' : 'off';
    return info.effective ? 'inherit-on' : 'inherit-off';
  };

  const render = () => {
    const filter = (filterInput.value || '').trim().toLowerCase();
    const filtered = STATE.workspaces.filter(w => !filter || (`${w.id} ${w.label || ''}`).toLowerCase().includes(filter));

    // Stats résumé
    let active = 0, disabled = 0, inheritOn = 0, inheritOff = 0;
    for (const w of STATE.workspaces) {
      const s = stateOf(cache[w.id]);
      if (s === 'on') active++;
      else if (s === 'off') disabled++;
      else if (s === 'inherit-on') inheritOn++;
      else inheritOff++;
    }
    summaryEl.innerHTML = `
      <div class="row" style="gap:var(--sp-3);font-size:12px;margin:var(--sp-3) 0;color:var(--text-muted)">
        <span><strong class="text-ok tabular">${active}</strong> override actif</span>
        <span><strong class="text-err tabular">${disabled}</strong> override désactivé</span>
        <span class="dim"><strong class="tabular">${inheritOn + inheritOff}</strong> hérités du global (${inheritOn} actifs)</span>
      </div>
    `;

    if (!filtered.length) {
      listEl.innerHTML = '<div class="dim" style="padding:var(--sp-3);font-size:12.5px">Aucun workspace ne correspond.</div>';
      return;
    }

    listEl.innerHTML = '';
    for (const w of filtered) {
      const info = cache[w.id];
      const state = stateOf(info);
      const row = el('div', 'scope-row');
      row.innerHTML = `
        <span class="workspace-emoji" style="font-size:20px">${escapeHtml(w.emoji || '📁')}</span>
        <div class="scope-row-main">
          <div class="scope-row-name">${escapeHtml(w.label || w.id)}</div>
          <div class="dim mono" style="font-size:10.5px">${escapeHtml(w.id)}</div>
        </div>
        <div class="scope-state-badge state-${state}"></div>
        <div class="seg-control">
          <button data-set="on" class="${state === 'on' ? 'is-active' : ''}" title="Activé pour ce workspace">Actif</button>
          <button data-set="off" class="${state === 'off' ? 'is-active' : ''}" title="Désactivé pour ce workspace">Inactif</button>
          <button data-set="reset" class="${state.startsWith('inherit') ? 'is-active' : ''}" title="Hériter du global (${info && info.global ? 'actif' : 'inactif'} actuellement)">Hériter</button>
        </div>
      `;
      row.querySelectorAll('button[data-set]').forEach(b => {
        b.addEventListener('click', async () => {
          const next = { 'on': true, 'off': false, 'reset': null }[b.dataset.set];
          try {
            await API.post(`/api/workspaces/${w.id}/plugins`, { plugin_id: currentPid, enabled: next });
            // Update cache locally pour réactivité
            const newInfo = next === null
              ? { global: info?.global, effective: info?.global, overridden: false }
              : { global: info?.global, effective: next, overridden: true };
            cache[w.id] = newInfo;
            render();
          } catch (e) { toastErr(e.message); }
        });
      });
      listEl.appendChild(row);
    }
  };

  const reload = async () => {
    // Pas d'effacement de listEl pour préserver scroll/hauteur ; juste un voile
    listEl.classList.add('is-loading');
    await fetchData(currentPid);
    listEl.classList.remove('is-loading');
    render();
  };

  // Bulk actions
  for (const b of host.querySelectorAll('[data-bulk]')) {
    b.addEventListener('click', async () => {
      const action = b.dataset.bulk;
      const filter = (filterInput.value || '').trim().toLowerCase();
      const targets = STATE.workspaces.filter(w => !filter || (`${w.id} ${w.label || ''}`).toLowerCase().includes(filter));
      if (!targets.length) return;
      const verb = { on: 'activer', off: 'désactiver', reset: 'réinitialiser' }[action];
      confirmDialog(`${verb[0].toUpperCase()}${verb.slice(1)} le plugin pour ${targets.length} workspace(s) ?`, async () => {
        const value = action === 'on' ? true : action === 'off' ? false : null;
        const errs = [];
        for (const w of targets) {
          try { await API.post(`/api/workspaces/${w.id}/plugins`, { plugin_id: currentPid, enabled: value }); }
          catch (e) { errs.push(`${w.id}: ${e.message}`); }
        }
        if (errs.length) toastErr(errs.length + ' échec(s)'); else toastOk('Action de masse terminée');
        await reload();
      });
    });
  }

  sel.addEventListener('change', async () => {
    currentPid = sel.value;
    await reload();
  });
  filterInput.addEventListener('input', debounce(render, 100));

  await reload();
}

async function modalInstallPlugin() {
  const body = el('div');
  body.innerHTML = `<div class="page-loader"><div class="spinner"></div><span>Chargement des marketplaces…</span></div>`;
  const cancel = btn('Fermer', 'btn-ghost');
  const { close } = openModal({ title: 'Installer un plugin', body, footer: cancel, wide: true });
  cancel.addEventListener('click', close);

  // Récupère les marketplaces disponibles
  let marketplaces = STATE.marketplaces;
  if (!marketplaces || !marketplaces.length) {
    try { const data = await API.get('/api/plugins/installed'); marketplaces = data.marketplaces || []; STATE.marketplaces = marketplaces; }
    catch (e) { body.innerHTML = `<div class="error-box">${escapeHtml(e.message)}</div>`; return; }
  }

  // Fallback : marketplace officielle Claude Code
  if (!marketplaces.length) {
    marketplaces = [{ id: 'claude-plugins-official' }];
  }

  // Statut "déjà installé"
  const installed = STATE.plugins?.enabled || {};
  const isInstalled = (mktId, plugId) => `${plugId}@${mktId}` in installed || plugId in installed;

  body.innerHTML = `
    <div class="row" style="gap:var(--sp-3);margin-bottom:var(--sp-4)">
      <div class="field" style="flex:1;margin:0">
        <label class="field-label">Marketplace</label>
        <select class="select" name="mkt">
          ${marketplaces.map(m => `<option value="${escapeHtml(m.id)}">${escapeHtml(m.id)}</option>`).join('')}
        </select>
      </div>
      <div class="field" style="flex:2;margin:0">
        <label class="field-label">Filtrer</label>
        <input class="input input-search" name="filter" placeholder="Rechercher…">
      </div>
    </div>
    <div class="tabs">
      <div class="tab active" data-tab="all">Tous</div>
      <div class="tab" data-tab="first_party">Officiels</div>
      <div class="tab" data-tab="external">Externes</div>
      <div class="tab" data-tab="manual">Spec manuel</div>
    </div>
    <div data-pane="all" class="plugin-browser"></div>
    <div data-pane="first_party" class="plugin-browser" hidden></div>
    <div data-pane="external" class="plugin-browser" hidden></div>
    <div data-pane="manual" hidden>
      <p class="muted" style="margin-top:0">Spec : <code class="mono">marketplace@plugin</code> ou URL git.</p>
      <div class="field"><label class="field-label">Spec</label><input class="input mono" name="spec" placeholder="claude-plugins-official@code-review"></div>
      <button class="btn btn-primary" data-install-spec>Installer</button>
    </div>
  `;

  // Tabs
  for (const tab of body.querySelectorAll('.tab')) {
    tab.addEventListener('click', () => {
      body.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      body.querySelectorAll('[data-pane]').forEach(p => p.hidden = p.dataset.pane !== tab.dataset.tab);
    });
  }

  // Manual install
  body.querySelector('[data-install-spec]').addEventListener('click', async () => {
    const spec = body.querySelector('[name=spec]').value.trim();
    if (!spec) { toastErr('Spec requis'); return; }
    await doInstall(spec, body);
  });

  const renderPlugin = (p, mktId, kind) => {
    const installed = isInstalled(mktId, p.id);
    const item = el('div', 'plugin-item' + (installed ? ' is-installed' : ''));
    const components = p.components || {};
    const compStr = Object.entries(components).filter(([_, n]) => n > 0).map(([k, n]) => `${n} ${k}`).join(' · ');
    item.innerHTML = `
      <div class="plugin-item-main">
        <div class="row" style="gap:var(--sp-2);align-items:flex-start">
          <strong style="font-size:13px">${escapeHtml(p.name || p.id)}</strong>
          ${p.version ? `<span class="badge mono">${escapeHtml(p.version)}</span>` : ''}
          ${kind === 'external' ? '<span class="badge badge-warn">externe</span>' : '<span class="badge badge-accent">officiel</span>'}
          ${installed ? '<span class="badge badge-ok">installé</span>' : ''}
        </div>
        <div class="muted" style="font-size:12px;margin-top:4px">${escapeHtml(p.description || '—')}</div>
        <div class="dim mono" style="font-size:11px;margin-top:4px">${escapeHtml(p.id)}${p.author ? ' · ' + escapeHtml(p.author) : ''}${compStr ? ' · ' + escapeHtml(compStr) : ''}</div>
      </div>
      <div class="plugin-item-actions"></div>
    `;
    const actions = item.querySelector('.plugin-item-actions');
    if (p.has_readme) {
      const readme = btn('README', 'btn-sm btn-ghost', I.book);
      readme.addEventListener('click', () => modalPluginReadme(mktId, kind, p.id, p.name));
      actions.appendChild(readme);
    }
    if (!installed) {
      const inst = btn('Installer', 'btn-sm btn-primary', I.download);
      inst.addEventListener('click', async () => {
        inst.disabled = true;
        await doInstall(`${p.id}@${mktId}`, body);
      });
      actions.appendChild(inst);
    }
    return item;
  };

  const renderMarketplace = async (mktId) => {
    const panes = {
      all: body.querySelector('[data-pane=all]'),
      first_party: body.querySelector('[data-pane=first_party]'),
      external: body.querySelector('[data-pane=external]'),
    };
    Object.values(panes).forEach(p => p.innerHTML = '<div class="page-loader"><div class="spinner"></div></div>');
    let data;
    try { data = await API.get(`/api/plugins/marketplace/${mktId}`); }
    catch (e) { Object.values(panes).forEach(p => p.innerHTML = `<div class="error-box">${escapeHtml(e.message)}</div>`); return; }
    if (data.error) {
      Object.values(panes).forEach(p => p.innerHTML = `<div class="error-box">${escapeHtml(data.error)}</div>`);
      return;
    }

    const filter = (body.querySelector('[name=filter]').value || '').trim().toLowerCase();
    const filterFn = (p) => !filter || (`${p.id} ${p.name || ''} ${p.description || ''}`).toLowerCase().includes(filter);

    const renderList = (host, items, kind) => {
      host.innerHTML = '';
      const filtered = items.filter(filterFn);
      if (!filtered.length) { host.innerHTML = '<div class="dim" style="padding:var(--sp-3);font-size:12.5px">Aucun plugin.</div>'; return; }
      for (const p of filtered) host.appendChild(renderPlugin(p, mktId, kind));
    };

    renderList(panes.all, [...(data.first_party || []).map(p => ({ ...p, _kind: 'first_party' })), ...(data.external || []).map(p => ({ ...p, _kind: 'external' }))].sort((a, b) => (a.name || a.id).localeCompare(b.name || b.id)), null);
    // Hack: re-render all with proper kind
    panes.all.innerHTML = '';
    const merged = [...(data.first_party || []).map(p => [p, 'first_party']), ...(data.external || []).map(p => [p, 'external'])];
    merged.sort(([a], [b]) => (a.name || a.id).localeCompare(b.name || b.id));
    const filteredAll = merged.filter(([p]) => filterFn(p));
    if (!filteredAll.length) panes.all.innerHTML = '<div class="dim" style="padding:var(--sp-3);font-size:12.5px">Aucun plugin.</div>';
    else for (const [p, kind] of filteredAll) panes.all.appendChild(renderPlugin(p, mktId, kind));

    renderList(panes.first_party, data.first_party || [], 'first_party');
    renderList(panes.external, data.external || [], 'external');
  };

  const select = body.querySelector('[name=mkt]');
  const filterInput = body.querySelector('[name=filter]');
  select.addEventListener('change', () => renderMarketplace(select.value));
  filterInput.addEventListener('input', debounce(() => renderMarketplace(select.value), 150));
  await renderMarketplace(select.value);

  async function doInstall(spec, container) {
    const toastId = toast(`Installation de ${spec}…`, 'info', 60000);
    try {
      const r = await API.post('/api/plugins/install', { spec });
      if (r.ok) {
        toastOk(`Plugin installé : ${spec}`);
        // Refresh marketplaces + plugins state
        STATE.loading = true;
        // Refresh just the modal view
        await renderMarketplace(select.value);
        // And refresh the underlying plugins page list
        if (location.hash === '#/plugins') route();
      } else {
        toastErr(r.stderr || r.error || 'Échec');
      }
    } catch (e) { toastErr(e.message); }
  }
}

async function modalPluginReadme(mktId, kind, pluginId, name) {
  let data;
  try { data = await API.get(`/api/plugins/marketplace/${mktId}/${kind}/${pluginId}/readme`); }
  catch (e) { toastErr(e.message); return; }
  const body = el('div');
  body.style.fontSize = '13px';
  body.innerHTML = `<pre style="background:var(--surface-2);padding:var(--sp-4);border-radius:var(--r-sm);max-height:60vh;overflow:auto;white-space:pre-wrap;font-family:var(--font-mono);font-size:12px;line-height:1.6">${escapeHtml(data.content || '')}</pre>`;
  const closeBtn = btn('Fermer', 'btn-ghost');
  const { close } = openModal({ title: `README · ${name || pluginId}`, body, footer: closeBtn, wide: true });
  closeBtn.addEventListener('click', close);
}

/* ================================================================
   PAGE: AIDE
   ================================================================ */
async function renderHelp() {
  setBreadcrumbs([{ label: 'Aide' }]);
  setTopbarActions([]);

  const c = $('#content');
  c.innerHTML = '';
  const page = el('div', 'page');
  page.appendChild(el('div', 'page-header', `
    <div class="page-header-text">
      <div class="page-eyebrow"><span class="index">??</span><span>Documentation</span></div>
      <h1 class="page-title">Aide & guide d'utilisation</h1>
      <p class="page-subtitle">Tout ce qu'il faut savoir pour piloter ton écosystème Claude Code depuis Atelier.</p>
    </div>
  `));

  // Table des matières
  const toc = el('nav', 'help-toc');
  toc.innerHTML = `
    <div class="help-toc-title">Sommaire</div>
    <ol>
      <li><a href="#h-overview">Vue d'ensemble du dashboard</a></li>
      <li><a href="#h-onboarding">Premier lancement & import depuis Claude</a></li>
      <li><a href="#h-workspaces">Workspaces : créer, importer, gérer</a></li>
      <li><a href="#h-mcps">MCPs : configurer un Model Context Protocol</a></li>
      <li><a href="#h-skills">Skills : créer, multi-fichiers, copier</a></li>
      <li><a href="#h-plugins">Plugins : installation et scope</a></li>
      <li><a href="#h-templates">Templates : modèles de workspaces</a></li>
      <li><a href="#h-env">Variables d'environnement (.env.local)</a></li>
      <li><a href="#h-scope">Lier MCPs / skills / plugins à un workspace</a></li>
      <li><a href="#h-tools">Outils & maintenance</a></li>
      <li><a href="#h-shortcuts">Raccourcis clavier</a></li>
      <li><a href="#h-troubleshoot">Dépannage</a></li>
    </ol>
  `;
  toc.addEventListener('click', (e) => {
    const a = e.target.closest('a');
    if (!a) return;
    e.preventDefault();
    const target = $(a.getAttribute('href'));
    if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
  page.appendChild(toc);

  // Contenu : sections HTML
  const content = el('div', 'help-content');
  content.innerHTML = `
    <section id="h-overview">
      <h2>${I.home}<span>1. Vue d'ensemble du dashboard</span></h2>
      <p>Atelier est un <strong>tableau de bord local</strong> qui pilote ton écosystème Claude Code : workspaces (projets), MCPs (serveurs Model Context Protocol), skills, plugins, templates et hooks. Tout est servi par un petit serveur Python sur <code class="mono">127.0.0.1:4777</code> — aucune donnée ne sort de ta machine.</p>
      <div class="help-grid help-grid-3">
        <div class="help-tile">
          <div class="help-tile-icon">${I.box}</div>
          <h4>Workspaces</h4>
          <p>Tes projets Claude Code. Chaque workspace = un dossier disque + un id technique. Tu peux les créer depuis un template, les importer depuis un dossier existant, ou les récupérer du registre Claude.</p>
        </div>
        <div class="help-tile">
          <div class="help-tile-icon">${I.cpu}</div>
          <h4>MCPs</h4>
          <p>Serveurs externes qui enrichissent Claude (Filesystem, GitHub, base de données…). Configurés dans le registre central <code class="mono">mcp/registry.json</code> puis distribués vers les workspaces ciblés.</p>
        </div>
        <div class="help-tile">
          <div class="help-tile-icon">${I.sparkle}</div>
          <h4>Skills</h4>
          <p>Modules de compétences invocables par Claude. Globaux (pour tous les projets) ou copiés localement dans un workspace.</p>
        </div>
        <div class="help-tile">
          <div class="help-tile-icon">${I.plug}</div>
          <h4>Plugins</h4>
          <p>Extensions Claude Code installées via la CLI. Tu peux les <strong>overrider</strong> par workspace (forcer actif/inactif, ou hériter du global).</p>
        </div>
        <div class="help-tile">
          <div class="help-tile-icon">${I.layers}</div>
          <h4>Templates</h4>
          <p>Modèles de structure pour créer rapidement des workspaces. Supportent les placeholders <code class="mono">{{label}}</code>, <code class="mono">{{description}}</code>, etc.</p>
        </div>
        <div class="help-tile">
          <div class="help-tile-icon">${I.tools}</div>
          <h4>Outils</h4>
          <p>Variables d'env, hooks globaux, sauvegardes, accès rapide aux fichiers de config. Tout ce qui est transverse au système.</p>
        </div>
      </div>
    </section>

    <section id="h-onboarding">
      <h2>${I.download}<span>2. Premier lancement & import depuis Claude</span></h2>
      <p>Si tu utilises déjà Claude Code, Atelier peut <strong>récupérer ta config existante</strong> en un clic. Trois portes d'entrée :</p>
      <div class="help-step">
        <div class="help-step-num">1</div>
        <div>
          <h4>Wizard "Importer config"</h4>
          <p>Sur la page <strong>Accueil</strong> ou <strong>Outils → Onboarding</strong>, clique sur <em>Importer ma config Claude</em>. Le scanner lit <code class="mono">~/.claude/settings.json</code> et <code class="mono">~/.claude/projects/</code>, te liste les MCPs et workspaces trouvés, et tu coches ceux que tu veux importer. Les éléments déjà connus sont grisés.</p>
        </div>
      </div>
      <div class="help-step">
        <div class="help-step-num">2</div>
        <div>
          <h4>Enregistrer un dossier existant</h4>
          <p>Pour pointer Atelier vers un projet déjà sur disque (sans le déplacer), utilise <em>Enregistrer un dossier</em>. Tu donnes l'ID, le label et le chemin absolu — aucun fichier n'est touché, juste un enregistrement dans <code class="mono">data/workspaces.json</code>.</p>
        </div>
      </div>
      <div class="help-step">
        <div class="help-step-num">3</div>
        <div>
          <h4>Coller du JSON MCP</h4>
          <p>Si tu as un bloc <code class="mono">{"mcpServers": {...}}</code> ou un objet MCP brut, colle-le via <strong>MCPs → Importer</strong> ou <strong>Outils → Onboarding → Coller du JSON</strong>. Atelier détecte automatiquement le format.</p>
        </div>
      </div>
      <div class="callout callout-info">
        <strong>Bon à savoir :</strong> l'import ne touche jamais à <code class="mono">~/.claude/settings.json</code>. Atelier maintient son propre registre dans <code class="mono">mcp/registry.json</code> et distribue ensuite vers les <code class="mono">.mcp.json</code> de chaque workspace via <em>Sync</em>.
      </div>
    </section>

    <section id="h-workspaces">
      <h2>${I.box}<span>3. Workspaces</span></h2>
      <h3>Créer un nouveau workspace</h3>
      <p>Bouton <em>Nouveau workspace</em> sur la Home (ou raccourci <kbd>n</kbd>). Tu fournis :</p>
      <ul class="help-list">
        <li><strong>ID</strong> — identifiant technique (a-z, 0-9, _, -). Sert de nom de dossier et de clé interne.</li>
        <li><strong>Label</strong> — libellé lisible affiché dans l'UI.</li>
        <li><strong>Emoji</strong> — pictogramme pour repérer visuellement le projet.</li>
        <li><strong>Description</strong> et <strong>Outils / contexte</strong> — utilisés comme placeholders dans le template.</li>
        <li><strong>Template</strong> — sélectionne un modèle parmi ceux de la page Templates.</li>
      </ul>
      <p>Atelier crée le dossier <code class="mono">workspaces/&lt;id&gt;/</code>, copie le template en remplaçant les placeholders, génère un <code class="mono">launch-&lt;id&gt;.bat</code> dans <code class="mono">scripts/</code>, et enregistre l'entrée.</p>

      <h3>Importer un dossier existant</h3>
      <p>Si ton projet est déjà ailleurs sur le disque (ex. <code class="mono">D:\\projets\\monapp</code>), utilise <em>+ Dossier</em> sur la Home. Aucun fichier n'est créé ni copié, juste un enregistrement.</p>

      <h3>Lancer Claude Code dans un workspace</h3>
      <p>Bouton <strong>Lancer</strong> ouvre une nouvelle console et exécute <code class="mono">claude</code> dans le dossier. <strong>Reprendre</strong> fait <code class="mono">claude -c</code> pour continuer la dernière session.</p>

      <h3>Page détail d'un workspace</h3>
      <p>Clique sur une carte workspace pour voir : statistiques (sessions, tokens, coût), MCPs scopés, skills locaux, plugins overridés, agents/commandes, et accès rapide aux fichiers de config (<code class="mono">CLAUDE.md</code>, <code class="mono">settings.json</code>, permissions, hooks).</p>

      <div class="callout callout-warn">
        <strong>Suppression :</strong> par défaut, supprimer un workspace ne retire que l'enregistrement (le dossier reste sur disque). Coche <em>Supprimer aussi le dossier</em> pour purger physiquement — irréversible.
      </div>
    </section>

    <section id="h-mcps">
      <h2>${I.cpu}<span>4. MCPs (Model Context Protocol)</span></h2>
      <p>Les MCPs sont des serveurs externes que Claude peut interroger pour accéder à des données ou fonctionnalités. Atelier centralise leur config dans un registre, puis les distribue aux workspaces.</p>

      <h3>Ajouter un MCP</h3>
      <p>Page <strong>MCPs → Nouveau MCP</strong>. Le formulaire change selon le transport choisi.</p>

      <h4>Transport <code class="mono">stdio</code> (le plus courant)</h4>
      <p>Le MCP est un programme local lancé par Claude. Tu fournis :</p>
      <ul class="help-list">
        <li><strong>Command</strong> — exécutable (ex. <code class="mono">npx</code>, <code class="mono">uvx</code>, <code class="mono">python</code>).</li>
        <li><strong>Args</strong> — un argument par ligne (ex. <code class="mono">-y</code>, <code class="mono">@modelcontextprotocol/server-filesystem</code>, <code class="mono">/path/to/dir</code>).</li>
        <li><strong>CWD</strong> (optionnel) — répertoire de travail du process. Utile si le MCP a besoin de fichiers relatifs à un dossier précis.</li>
        <li><strong>Env</strong> — variables d'env, format <code class="mono">KEY=VALUE</code> ou <code class="mono">KEY=\${VAR}</code> pour interpoler depuis <code class="mono">.env.local</code>.</li>
      </ul>

      <h4>Transport <code class="mono">http</code> ou <code class="mono">sse</code></h4>
      <ul class="help-list">
        <li><strong>URL</strong> — endpoint du serveur MCP.</li>
        <li><strong>Headers</strong> — auth & headers custom, format <code class="mono">KEY=VALUE</code> par ligne. Ex. <code class="mono">Authorization=Bearer \${API_TOKEN}</code>.</li>
      </ul>

      <h3>Tester un MCP</h3>
      <p>Bouton <em>Tester</em> sur la card. Pour stdio, lance le process 2.5s pour vérifier qu'il démarre. Pour http/sse, fait un GET sur l'URL. Le statut affiché t'indique si la commande est trouvée et si l'env est complet.</p>

      <h3>Vue JSON brut</h3>
      <p>L'onglet <em>JSON brut</em> de la modale te permet d'éditer toute la config en un coup, utile pour copier-coller depuis un README de MCP.</p>

      <div class="callout callout-info">
        <strong>Le registre vs Claude :</strong> le fichier <code class="mono">mcp/registry.json</code> est la source de vérité d'Atelier. Il liste les MCPs et leur scope (workspaces ciblés via <code class="mono">workspaces: ["dev","prod"]</code> ou <code class="mono">["*"]</code>). À chaque <em>Sync</em>, Atelier régénère les <code class="mono">.mcp.json</code> dans les workspaces concernés en interpolant les <code class="mono">\${VAR}</code>.
      </div>
    </section>

    <section id="h-skills">
      <h2>${I.sparkle}<span>5. Skills</span></h2>
      <p>Un skill = un dossier contenant <code class="mono">SKILL.md</code> (frontmatter + instructions Markdown). Optionnellement des fichiers de référence (<code class="mono">references/</code>, <code class="mono">examples/</code>).</p>

      <h3>Créer un skill</h3>
      <p>Page <strong>Skills → Nouveau skill</strong>. Tu choisis le scope (global ou workspace), un nom court, une description (1 phrase), et le corps optionnel. Atelier crée le dossier et le <code class="mono">SKILL.md</code> avec le bon frontmatter.</p>

      <h3>Édition multi-fichiers</h3>
      <p>Sur une carte de skill, le bouton <em>Éditer</em> ouvre une modale avec :</p>
      <ul class="help-list">
        <li>Arborescence des fichiers à gauche (<code class="mono">SKILL.md</code> en premier, marqué d'une étoile)</li>
        <li>Éditeur de contenu à droite avec sauvegarde par <kbd>Ctrl+S</kbd></li>
        <li>Bouton <strong>+</strong> pour ajouter un fichier (sélection ou création de sous-dossier)</li>
      </ul>
      <p><code class="mono">SKILL.md</code> est protégé contre la suppression — pour s'en débarrasser, supprime le skill entier.</p>

      <h3>Copier un skill global vers un workspace</h3>
      <p>Bouton <em>Copier dans…</em> ouvre une liste cochable des workspaces. Atelier <code class="mono">copytree</code> le skill dans <code class="mono">&lt;workspace&gt;/.claude/skills/&lt;name&gt;/</code>, où Claude Code le découvre automatiquement.</p>

      <div class="callout callout-info">
        Les skills <strong>globaux</strong> sont dans <code class="mono">~/.claude/skills/</code>, disponibles dans tous les projets. Les skills <strong>locaux</strong> à un workspace sont dans <code class="mono">&lt;workspace&gt;/.claude/skills/</code> et ne s'appliquent que là.
      </div>
    </section>

    <section id="h-plugins">
      <h2>${I.plug}<span>6. Plugins</span></h2>
      <p>Les plugins Claude Code sont gérés par la CLI <code class="mono">claude plugin</code>. Atelier propose un browser et la gestion du scope par workspace.</p>

      <h3>Installer un plugin</h3>
      <p><strong>Plugins → Installer</strong> ouvre le browser :</p>
      <ul class="help-list">
        <li>Sélecteur de marketplace (auto-détection depuis <code class="mono">~/.claude/plugins/marketplaces/</code>)</li>
        <li>Onglets : <em>Tous</em>, <em>Officiels</em>, <em>Externes</em>, <em>Spec manuel</em></li>
        <li>Filtre de recherche par nom/description</li>
        <li>Bouton <strong>README</strong> pour lire la doc avant install</li>
        <li>Bouton <strong>Installer</strong> qui appelle <code class="mono">claude plugin install &lt;plugin&gt;@&lt;mkt&gt;</code></li>
      </ul>

      <h3>Activer / désactiver / désinstaller</h3>
      <p>Dans la table <em>Installés</em>, le toggle ON/OFF appelle <code class="mono">claude plugin enable/disable</code>. La poubelle désinstalle (avec confirmation).</p>

      <h3>Scope par workspace</h3>
      <p>Section <strong>B. Scope par workspace</strong> : sélectionne un plugin, vois la liste de tous les workspaces. Pour chacun, 3 états :</p>
      <ul class="help-list">
        <li><strong class="text-ok">Actif</strong> — override local : forcer activé pour ce workspace même si désactivé globalement</li>
        <li><strong class="text-err">Inactif</strong> — override local : forcer désactivé pour ce workspace</li>
        <li><strong>Hériter</strong> — pas d'override : suit l'état global du plugin</li>
      </ul>
      <p>Actions de masse (Activer / Désactiver / Réinitialiser pour tous les workspaces filtrés) en haut de la section.</p>
    </section>

    <section id="h-templates">
      <h2>${I.layers}<span>7. Templates</span></h2>
      <p>Un template = un dossier dans <code class="mono">templates/&lt;id&gt;/</code> qui sera copié à chaque création de workspace. Le fichier <code class="mono">.template.json</code> contient les méta (label, description, emoji).</p>

      <h3>Édition complète depuis le GUI</h3>
      <p>Bouton <em>Éditer</em> sur une carte template ouvre la modale avec arborescence + éditeur, comme pour les skills. Tu peux ajouter/modifier/supprimer des fichiers et organiser des sous-dossiers.</p>

      <h3>Placeholders</h3>
      <p>Dans le contenu des fichiers texte du template, ces marqueurs sont remplacés à la création par les <strong>infos saisies dans le formulaire "Nouveau workspace"</strong> :</p>
      <ul class="help-list">
        <li><code class="mono">{{name}}</code> → champ <strong>ID</strong></li>
        <li><code class="mono">{{label}}</code> → champ <strong>Label</strong></li>
        <li><code class="mono">{{description}}</code> → champ <strong>Description</strong></li>
        <li><code class="mono">{{tools}}</code> → champ <strong>Outils / contexte</strong></li>
        <li><code class="mono">{{emoji}}</code> → champ <strong>Emoji</strong></li>
        <li><code class="mono">{{date}}</code> → date du jour à la création (ISO)</li>
      </ul>
    </section>

    <section id="h-env">
      <h2>${I.key}<span>8. Variables d'environnement (.env.local)</span></h2>
      <p>Pour ne <strong>jamais</strong> committer de secrets dans tes registres ou templates, Atelier utilise <code class="mono">C:\\claude-workspace\\.env.local</code> comme stockage centralisé.</p>

      <h3>Format</h3>
      <pre class="help-code">OPENAI_API_KEY=sk-...
GITHUB_TOKEN=ghp_...
DB_PASSWORD=mon_mdp
# Les commentaires sont OK</pre>

      <h3>Édition depuis le GUI</h3>
      <p>Page <strong>Outils → Variables d'environnement</strong> :</p>
      <ul class="help-list">
        <li>Variables groupées par préfixe (<code class="mono">OPENAI_*</code>, <code class="mono">DB_*</code>…)</li>
        <li>Filtre rapide par nom</li>
        <li>Bouton œil pour révéler la valeur masquée</li>
        <li>Ajout/suppression atomique avec backup</li>
      </ul>

      <h3>Interpolation <code class="mono">\${VAR}</code></h3>
      <p>Dans n'importe quel champ MCP (<code class="mono">command</code>, <code class="mono">args</code>, <code class="mono">env</code>, <code class="mono">cwd</code>, <code class="mono">url</code>, <code class="mono">headers</code>), tu peux écrire <code class="mono">\${MA_VAR}</code> et Atelier le remplacera par la valeur depuis <code class="mono">.env.local</code> au moment de la sync vers le workspace. Si la variable est manquante, le sanity check te le signale.</p>

      <div class="callout callout-warn">
        <strong>Important :</strong> ajoute <code class="mono">.env.local</code> dans ton <code class="mono">.gitignore</code> ! Atelier ne le fait pas pour toi. Le fichier reste local à ta machine.
      </div>
    </section>

    <section id="h-scope">
      <h2>${I.activity}<span>9. Lier MCPs / skills / plugins à un workspace</span></h2>
      <p>Trois mécaniques différentes selon le type :</p>

      <h3>MCP → workspace</h3>
      <p>Dans la modale d'édition d'un MCP, champ <strong>Workspaces ciblés</strong> :</p>
      <ul class="help-list">
        <li>Liste séparée par virgules : <code class="mono">dev,homeassistant,audit</code></li>
        <li>Wildcard : <code class="mono">*</code> ou <code class="mono">all</code> pour tous les workspaces</li>
        <li>Vide : MCP enregistré mais inactif partout</li>
      </ul>
      <p>Après modification, clique <em>Sync</em> sur la Home (ou <em>Sync MCPs</em> sur la page workspace) pour régénérer les <code class="mono">.mcp.json</code>.</p>

      <h3>Skill → workspace</h3>
      <p>Skills globaux : disponibles partout par défaut. Pour avoir une variante locale spécifique, utilise <em>Copier dans…</em> sur la carte du skill global ou <em>+ ici</em> dans la section Skills d'un workspace.</p>

      <h3>Plugin → workspace</h3>
      <p>Soit depuis la <strong>page Plugins → Scope par workspace</strong> (vue par plugin), soit depuis la <strong>page workspace → Plugins</strong> (vue par workspace). Les deux contrôlent le même fichier <code class="mono">.claude/settings.json</code> du workspace.</p>
    </section>

    <section id="h-tools">
      <h2>${I.tools}<span>10. Outils & maintenance</span></h2>
      <ul class="help-list">
        <li><strong>Apparence</strong> — choix du thème (Atelier sombre/clair, Marine, Forêt, Brique). Persisté localement.</li>
        <li><strong>Onboarding</strong> — wizards d'import (vu en section 2).</li>
        <li><strong>Accès rapide</strong> — boutons pour ouvrir directement les fichiers de config dans l'explorateur ou le bloc-notes.</li>
        <li><strong>Hooks globaux</strong> — édition des hooks Claude Code de <code class="mono">~/.claude/settings.json</code>.</li>
        <li><strong>Sauvegardes</strong> — copie horodatée de <code class="mono">~/.claude.json</code> et <code class="mono">~/.claude/settings.json</code> dans <code class="mono">backups/</code>.</li>
        <li><strong>Skills globaux</strong> — vue rapide depuis Outils (sinon page Skills dédiée).</li>
        <li><strong>Maintenance</strong> — nettoyage des <code class="mono">.bat</code> orphelins (workspaces supprimés mais script de lancement encore présent).</li>
      </ul>
    </section>

    <section id="h-shortcuts">
      <h2>${I.zap}<span>11. Raccourcis clavier</span></h2>
      <table class="help-shortcuts">
        <tr><td><kbd>/</kbd> ou <kbd>Ctrl</kbd>+<kbd>K</kbd></td><td>Ouvrir la palette de recherche globale</td></tr>
        <tr><td><kbd>g</kbd> puis <kbd>h</kbd></td><td>Aller à l'<strong>Accueil</strong></td></tr>
        <tr><td><kbd>g</kbd> puis <kbd>m</kbd></td><td>Aller aux <strong>MCPs</strong></td></tr>
        <tr><td><kbd>g</kbd> puis <kbd>p</kbd></td><td>Aller aux <strong>Plugins</strong></td></tr>
        <tr><td><kbd>g</kbd> puis <kbd>k</kbd></td><td>Aller aux <strong>Skills</strong></td></tr>
        <tr><td><kbd>g</kbd> puis <kbd>t</kbd></td><td>Aller aux <strong>Templates</strong></td></tr>
        <tr><td><kbd>g</kbd> puis <kbd>o</kbd></td><td>Aller aux <strong>Outils</strong></td></tr>
        <tr><td><kbd>g</kbd> puis <kbd>a</kbd></td><td>Aller à l'<strong>Aide</strong> (cette page)</td></tr>
        <tr><td><kbd>n</kbd></td><td>Nouveau workspace</td></tr>
        <tr><td><kbd>m</kbd></td><td>Nouveau MCP</td></tr>
        <tr><td><kbd>s</kbd></td><td>Sync tous les workspaces</td></tr>
        <tr><td><kbd>Ctrl</kbd>+<kbd>S</kbd></td><td>Sauvegarder le fichier en cours d'édition (modales template/skill)</td></tr>
        <tr><td><kbd>Esc</kbd></td><td>Fermer une modale ou la palette</td></tr>
      </table>
      <div class="callout callout-info">
        Les raccourcis clavier <strong>ignorent</strong> les zones de saisie : tu peux taper sans déclencher les chords.
      </div>
    </section>

    <section id="h-troubleshoot">
      <h2>${I.alert}<span>12. Dépannage</span></h2>

      <h3>"Serveur hors ligne" en bas de page</h3>
      <p>Le serveur Python n'a pas démarré ou a crashé. Relance <code class="mono">scripts\\start-dashboard.bat</code> et vérifie les logs dans <code class="mono">logs\\dashboard.log</code>.</p>

      <h3>Sanity check signale "désync"</h3>
      <p>Le registre MCP a changé mais les workspaces n'ont pas été re-synchronisés. Clique <em>Sync tous</em> sur la Home, ou <em>Sync MCPs</em> sur le workspace concerné.</p>

      <h3>Sanity check signale "env manquant"</h3>
      <p>Un <code class="mono">\${VAR}</code> dans une config MCP n'est pas défini dans <code class="mono">.env.local</code>. Va dans <strong>Outils → Variables d'environnement</strong> et ajoute la valeur.</p>

      <h3>Plugin présent dans le matrix mais "absent du disque"</h3>
      <p>Le plugin est listé dans <code class="mono">~/.claude/settings.json</code> mais son dossier a été supprimé. Désinstalle-le proprement via le bouton poubelle pour nettoyer la config.</p>

      <h3>Test MCP échoue avec "Commande introuvable"</h3>
      <p>L'exécutable de la commande n'est pas dans le PATH. Vérifie que <code class="mono">node</code> / <code class="mono">python</code> / <code class="mono">uvx</code> sont accessibles depuis un terminal système. Sur Windows, <code class="mono">npx</code> s'appelle parfois <code class="mono">npx.cmd</code>.</p>

      <h3>MCPs en doublon entre Atelier et la config Claude globale</h3>
      <p>Si tu avais des MCPs dans <code class="mono">~/.claude.json</code> ou <code class="mono">~/.claude/settings.json</code> avant d'utiliser Atelier, ils peuvent maintenant exister à deux endroits. Ouvre <strong>Outils → Onboarding → Conflits Claude global</strong> pour les détecter et les nettoyer (avec backup automatique). Une bannière jaune apparaît aussi sur la page MCPs si des conflits sont présents.</p>

      <h3>Réinitialiser un workspace cassé</h3>
      <p>Supprime via le GUI <strong>sans</strong> cocher la purge — ça retire seulement l'entrée du registre, le dossier reste intact. Tu peux ensuite réimporter avec <em>+ Dossier</em>.</p>

      <h3>Backup avant manipulation risquée</h3>
      <p><strong>Outils → Sauvegardes → Sauvegarder maintenant</strong> copie <code class="mono">~/.claude.json</code> et <code class="mono">~/.claude/settings.json</code> dans <code class="mono">backups/</code> avec timestamp. À faire avant tout import massif ou bidouille manuelle.</p>
    </section>
  `;
  page.appendChild(content);

  c.appendChild(page);
}

/* ================================================================
   PAGE: SKILLS
   ================================================================ */
async function renderSkills() {
  setBreadcrumbs([{ label: 'Skills' }]);
  const newBtn = btn('Nouveau skill', 'btn-primary', I.plus);
  newBtn.addEventListener('click', () => modalNewSkill());
  setTopbarActions([newBtn]);

  const c = $('#content');
  c.innerHTML = '';
  const page = el('div', 'page');

  page.appendChild(el('div', 'page-header', `
    <div class="page-header-text">
      <div class="page-eyebrow"><span class="index">04.</span><span>Capacités</span></div>
      <h1 class="page-title">Skills</h1>
      <p class="page-subtitle">Modules de compétences activables par Claude — globaux ou scopés à un workspace.</p>
    </div>
  `));

  // Help collapsible
  const help = el('details', 'help-card');
  help.innerHTML = `
    <summary>
      <span class="help-icon">${I.info}</span>
      <span class="help-title">Comment ça marche ?</span>
      <span class="help-toggle">${I.down}</span>
    </summary>
    <div class="help-body">
      <div class="help-grid">
        <div>
          <h4>Qu'est-ce qu'un skill ?</h4>
          <p>Un dossier contenant un fichier <code class="mono">SKILL.md</code> (frontmatter <code class="mono">name</code> + <code class="mono">description</code> + corps Markdown). Optionnellement, des fichiers de référence (<code class="mono">references/*.md</code>, <code class="mono">examples/</code>, etc.) que Claude peut consulter.</p>
        </div>
        <div>
          <h4>Global vs workspace</h4>
          <p><strong>Global</strong> : <code class="mono">~/.claude/skills/&lt;name&gt;/</code> — disponible partout.<br><strong>Workspace</strong> : <code class="mono">&lt;workspace&gt;/.claude/skills/&lt;name&gt;/</code> — actif uniquement dans ce projet.<br>Le bouton « Copier dans… » duplique un skill global vers un workspace.</p>
        </div>
        <div>
          <h4>Édition multi-fichiers</h4>
          <p>Le bouton <strong>Éditer</strong> ouvre l'arborescence du skill avec un éditeur. Tu peux ajouter des fichiers <code class="mono">references/api.md</code>, <code class="mono">examples/usage.py</code>, etc. <code class="mono">SKILL.md</code> est obligatoire et ne peut pas être supprimé.</p>
        </div>
        <div>
          <h4>Activation</h4>
          <p>Les skills sont auto-découverts par Claude Code au démarrage — pas besoin de les enregistrer manuellement. Vérifie qu'ils apparaissent avec <code class="mono">/help</code> ou via le menu skills.</p>
        </div>
      </div>
    </div>
  `;
  page.appendChild(help);

  // Toolbar
  const toolbar = el('div');
  toolbar.style.cssText = 'display:flex;gap:var(--sp-3);align-items:center;margin-bottom:var(--sp-4);flex-wrap:wrap';
  toolbar.innerHTML = `
    <input class="input input-search" name="filter" placeholder="Rechercher un skill…" style="flex:1;min-width:240px;max-width:480px">
    <span class="dim mono" style="font-size:11px;letter-spacing:0.1em" data-count></span>
  `;
  page.appendChild(toolbar);

  const grid = el('div', 'skill-grid');
  page.appendChild(grid);

  const skills = STATE.skills.slice().sort((a, b) => (a.name || a.id).localeCompare(b.name || b.id));
  // Fetch usage for each (parallel)
  const usageMap = {};
  await Promise.all(skills.map(async s => {
    try { const r = await API.get(`/api/skills/${s.id}/usage`); usageMap[s.id] = r.workspaces || []; }
    catch { usageMap[s.id] = []; }
  }));

  const renderList = () => {
    const filter = (toolbar.querySelector('[name=filter]').value || '').trim().toLowerCase();
    const filtered = filter
      ? skills.filter(s => (`${s.id} ${s.name || ''} ${s.description || ''}`).toLowerCase().includes(filter))
      : skills;
    toolbar.querySelector('[data-count]').textContent = `${filtered.length} / ${skills.length}`;
    grid.innerHTML = '';
    if (!filtered.length) {
      const empty = el('div', 'empty');
      empty.innerHTML = `<div class="empty-title">Aucun skill ${filter ? 'ne correspond' : 'global'}</div><p class="muted">${filter ? 'Modifie ton filtre.' : 'Crée ton premier skill.'}</p>`;
      grid.appendChild(empty);
      return;
    }
    for (const s of filtered) grid.appendChild(skillCard(s, usageMap[s.id] || []));
  };
  toolbar.querySelector('[name=filter]').addEventListener('input', debounce(renderList, 100));
  renderList();

  c.appendChild(page);
}

function skillCard(s, usedInWorkspaces) {
  const card = el('div', 'skill-card');
  const usageText = usedInWorkspaces.length
    ? `<span class="badge badge-info">${usedInWorkspaces.length} workspace${usedInWorkspaces.length > 1 ? 's' : ''}</span>`
    : '<span class="badge">global seul</span>';
  card.innerHTML = `
    <div class="skill-card-header">
      <div class="skill-icon">${I.sparkle}</div>
      <div style="flex:1;min-width:0">
        <h3 class="skill-name">${escapeHtml(s.name || s.id)}</h3>
        <div class="dim mono" style="font-size:11px;margin-top:2px">${escapeHtml(s.id)}</div>
      </div>
      ${usageText}
    </div>
    <p class="skill-desc">${escapeHtml(s.description || 'Pas de description')}</p>
    ${usedInWorkspaces.length ? `<div class="skill-ws-list">${usedInWorkspaces.map(w => `<span class="chip">${escapeHtml(w)}</span>`).join('')}</div>` : ''}
  `;
  const actions = el('div', 'skill-actions');
  const ed = btn('Éditer', 'btn-sm btn-primary', I.edit);
  ed.addEventListener('click', () => modalEditSkillFiles('global', s.id));
  const copy = btn('Copier dans…', 'btn-sm btn-ghost', I.copy);
  copy.addEventListener('click', () => modalCopySkillToWorkspace(s));
  const open = btn('', 'btn-sm btn-ghost btn-icon-only', I.folder);
  open.title = 'Ouvrir le dossier';
  open.addEventListener('click', async () => {
    try { const r = await API.post('/api/open', { target: `skill-global:${s.id}` }); toastOk(r.message); }
    catch (e) { toastErr(e.message); }
  });
  const rm = btn('', 'btn-sm btn-ghost btn-icon-only btn-danger', I.trash);
  rm.title = 'Supprimer';
  rm.addEventListener('click', () => confirmDialog(`Supprimer le skill ${s.id} ? (les copies dans les workspaces ne seront pas affectées)`, async () => {
    try { await API.del(`/api/skills/global/${s.id}`); toastOk('Supprimé'); STATE.loading = true; route(); }
    catch (e) { toastErr(e.message); }
  }, { danger: true }));
  actions.append(ed, copy, open, rm);
  card.appendChild(actions);
  return card;
}

function modalCopySkillToWorkspace(skill) {
  const body = el('div');
  if (!STATE.workspaces.length) {
    body.innerHTML = '<p class="muted">Aucun workspace disponible.</p>';
    const close = btn('Fermer', 'btn-ghost');
    const { close: doClose } = openModal({ title: 'Copier dans un workspace', body, footer: close });
    close.addEventListener('click', doClose);
    return;
  }
  body.innerHTML = `
    <p class="muted" style="margin-top:0">Choisis le ou les workspaces où copier <strong class="mono">${escapeHtml(skill.id)}</strong> :</p>
    <div class="ws-pick-list"></div>
  `;
  const list = body.querySelector('.ws-pick-list');
  for (const w of STATE.workspaces) {
    const item = el('label', 'wizard-item');
    item.innerHTML = `
      <input type="checkbox" data-ws="${escapeHtml(w.id)}">
      <div class="wizard-item-main">
        <div class="wizard-item-name">${escapeHtml(w.emoji || '📁')} ${escapeHtml(w.label || w.id)}</div>
        <div class="wizard-item-meta"><span class="dim mono" style="font-size:11px">${escapeHtml(w.id)}</span></div>
      </div>
    `;
    list.appendChild(item);
  }
  const cancel = btn('Annuler', 'btn-ghost');
  const ok = btn('Copier', 'btn-primary', I.copy);
  const { close } = openModal({ title: `Copier ${skill.id}`, body, footer: [cancel, ok], wide: true });
  cancel.addEventListener('click', close);
  ok.addEventListener('click', async () => {
    const targets = Array.from(body.querySelectorAll('input[type=checkbox]:checked')).map(cb => cb.dataset.ws);
    if (!targets.length) { toastErr('Sélectionne au moins un workspace'); return; }
    let okCount = 0, errs = [];
    for (const wsId of targets) {
      try { await API.post('/api/skills/copy', { name: skill.id, workspace: wsId }); okCount++; }
      catch (e) { errs.push(`${wsId}: ${e.message}`); }
    }
    if (okCount) toastOk(`${okCount} copie(s) effectuée(s)`);
    if (errs.length) toastErr(errs[0]);
    close(); STATE.loading = true; route();
  });
}

async function modalEditSkillFiles(scope, name) {
  const body = el('div');
  body.innerHTML = `<div class="page-loader"><div class="spinner"></div><span>Chargement du skill…</span></div>`;
  const closeBtn = btn('Fermer', 'btn-ghost');
  const { close } = openModal({ title: `Skill · ${name}`, body, footer: closeBtn, wide: true });
  closeBtn.addEventListener('click', close);

  let detail;
  try { detail = await API.get(`/api/skills/${scope}/${name}`); }
  catch (e) { body.innerHTML = `<div class="error-box">${escapeHtml(e.message)}</div>`; return; }

  body.innerHTML = `
    <div class="dim mono" style="font-size:11px;margin-bottom:var(--sp-3)">${escapeHtml(detail.path)}</div>
    <div class="tpl-editor">
      <aside class="tpl-tree">
        <div class="tpl-tree-header">
          <span class="section-label" style="margin:0;flex:1">Fichiers</span>
          <button class="icon-btn" data-add-file title="Nouveau fichier">${I.plus}</button>
        </div>
        <div class="tpl-tree-list"></div>
      </aside>
      <main class="tpl-pane">
        <div class="tpl-pane-empty">Sélectionne un fichier ou clique sur <strong>+</strong> pour en créer un.</div>
      </main>
    </div>
  `;

  const treeList = body.querySelector('.tpl-tree-list');
  const pane = body.querySelector('.tpl-pane');
  let files = detail.files.slice();
  let currentPath = 'SKILL.md';  // Ouvre SKILL.md par défaut

  const renderTree = () => {
    treeList.innerHTML = '';
    if (!files.length) {
      treeList.innerHTML = '<div class="dim" style="padding:var(--sp-3);font-size:12px">Aucun fichier</div>';
      return;
    }
    files.sort((a, b) => {
      // SKILL.md toujours en premier
      if (a.path === 'SKILL.md') return -1;
      if (b.path === 'SKILL.md') return 1;
      return a.path.localeCompare(b.path);
    });
    for (const f of files) {
      const item = el('div', 'tpl-tree-item' + (f.path === currentPath ? ' is-active' : ''));
      const isMain = f.path === 'SKILL.md';
      item.innerHTML = `
        <span class="tpl-tree-name mono">${isMain ? '⭐ ' : ''}${escapeHtml(f.path)}</span>
        <span class="dim mono" style="font-size:10px">${fmtBytes(f.size)}</span>
      `;
      item.addEventListener('click', () => openFile(f.path));
      if (!isMain) {
        const rm = el('button', 'icon-btn tpl-tree-del', I.x);
        rm.title = 'Supprimer';
        rm.addEventListener('click', (e) => {
          e.stopPropagation();
          confirmDialog(`Supprimer ${f.path} ?`, async () => {
            try {
              await API.del(`/api/skills/${scope}/${name}/file?path=${encodeURIComponent(f.path)}`);
              files = files.filter(x => x.path !== f.path);
              if (currentPath === f.path) { currentPath = 'SKILL.md'; openFile('SKILL.md'); }
              renderTree(); toastOk('Supprimé');
            } catch (err) { toastErr(err.message); }
          }, { danger: true });
        });
        item.appendChild(rm);
      }
      treeList.appendChild(item);
    }
  };

  const openFile = async (path) => {
    currentPath = path;
    renderTree();
    pane.innerHTML = `<div class="page-loader"><div class="spinner"></div></div>`;
    let data;
    try { data = await API.get(`/api/skills/${scope}/${name}/file?path=${encodeURIComponent(path)}`); }
    catch (e) { pane.innerHTML = `<div class="error-box">${escapeHtml(e.message)}</div>`; return; }
    if (data.binary || data.error) {
      pane.innerHTML = `<div class="error-box">${escapeHtml(data.error || 'Fichier binaire non éditable')}</div>`;
      return;
    }
    pane.innerHTML = `
      <div class="tpl-pane-header">
        <span class="mono" style="font-size:13px;flex:1">${escapeHtml(path)}</span>
        <span class="dim mono" style="font-size:11px">${fmtBytes(data.size)}</span>
        <button class="btn btn-sm btn-primary" data-save-file>Enregistrer</button>
      </div>
      <textarea class="textarea textarea-code tpl-editor-textarea" spellcheck="false"></textarea>
    `;
    const ta = pane.querySelector('textarea');
    ta.value = data.content;
    ta.focus();
    pane.querySelector('[data-save-file]').addEventListener('click', async () => {
      try {
        const r = await API.post(`/api/skills/${scope}/${name}/file`, { path, content: ta.value });
        const f = files.find(x => x.path === path);
        if (f) f.size = r.size;
        renderTree(); toastOk('Enregistré');
      } catch (e) { toastErr(e.message); }
    });
    ta.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        pane.querySelector('[data-save-file]').click();
      }
    });
  };

  body.querySelector('[data-add-file]').addEventListener('click', () => {
    const folders = new Set(['']);
    for (const f of files) {
      const parts = f.path.split('/');
      for (let i = 1; i < parts.length; i++) folders.add(parts.slice(0, i).join('/'));
    }
    const folderList = Array.from(folders).sort();
    const fbody = el('div');
    fbody.innerHTML = `
      <p class="muted" style="margin-top:0">Ajout d'un fichier de référence (ex. <code class="mono">references/api.md</code>, <code class="mono">examples/usage.py</code>).</p>
      <div class="field-row">
        <div class="field" style="flex:2"><label class="field-label">Dossier</label><select class="select" name="folder">${folderList.map(f => `<option value="${escapeHtml(f)}">${f === '' ? '/ (racine)' : escapeHtml('/' + f)}</option>`).join('')}<option value="__new__">＋ Nouveau sous-dossier…</option></select></div>
        <div class="field" style="flex:3"><label class="field-label">Nom du fichier *</label><input class="input mono" name="filename"></div>
      </div>
      <div class="field" data-new-folder hidden><label class="field-label">Nouveau sous-dossier</label><input class="input mono" name="new_folder" placeholder="references"></div>
      <div class="field"><label class="field-label">Contenu initial</label><textarea class="textarea textarea-code" name="content" rows="6"></textarea></div>
      <div class="dim" style="font-size:11.5px"><strong>Aperçu :</strong> <span class="mono" data-preview>—</span></div>
    `;
    const fSel = fbody.querySelector('[name=folder]');
    const fName = fbody.querySelector('[name=filename]');
    const fNew = fbody.querySelector('[name=new_folder]');
    const fNewField = fbody.querySelector('[data-new-folder]');
    const prev = fbody.querySelector('[data-preview]');
    const upd = () => {
      const folder = fSel.value === '__new__' ? fNew.value.trim().replace(/^\/+|\/+$/g, '') : fSel.value;
      const filename = fName.value.trim();
      prev.textContent = [folder, filename].filter(Boolean).join('/') || '—';
    };
    fSel.addEventListener('change', () => { fNewField.hidden = fSel.value !== '__new__'; if (fSel.value === '__new__') fNew.focus(); upd(); });
    [fName, fNew].forEach(i => i.addEventListener('input', upd));

    const cancel = btn('Annuler', 'btn-ghost');
    const create = btn('Créer', 'btn-primary', I.plus);
    const { close: closeAdd } = openModal({ title: 'Nouveau fichier dans le skill', body: fbody, footer: [cancel, create] });
    cancel.addEventListener('click', closeAdd);
    setTimeout(() => fName.focus(), 50);
    create.addEventListener('click', async () => {
      const folder = fSel.value === '__new__' ? fNew.value.trim().replace(/^\/+|\/+$/g, '') : fSel.value;
      const filename = fName.value.trim();
      if (!filename) { toastErr('Nom de fichier requis'); return; }
      const path = [folder, filename].filter(Boolean).join('/');
      const content = fbody.querySelector('[name=content]').value;
      try {
        const r = await API.post(`/api/skills/${scope}/${name}/file`, { path, content });
        files.push({ path: r.path, size: r.size });
        renderTree(); closeAdd(); toastOk('Fichier créé');
        openFile(r.path);
      } catch (e) { toastErr(e.message); }
    });
  });

  renderTree();
  // Auto-ouvre SKILL.md
  if (files.find(f => f.path === 'SKILL.md')) openFile('SKILL.md');
}

/* ================================================================
   PAGE: TEMPLATES
   ================================================================ */
async function renderTemplates() {
  setBreadcrumbs([{ label: 'Templates' }]);
  setTopbarActions([]);

  const c = $('#content');
  c.innerHTML = '';
  const page = el('div', 'page');
  page.appendChild(el('div', 'page-header', `
    <div class="page-header-text">
      <div class="page-eyebrow"><span class="index">03.</span><span>Bibliothèque</span></div>
      <h1 class="page-title">Templates</h1>
      <p class="page-subtitle">Modèles réutilisables pour créer de nouveaux workspaces.</p>
    </div>
  `));

  // Note "Comment utiliser" (collapsible)
  const help = el('details', 'help-card');
  help.innerHTML = `
    <summary>
      <span class="help-icon">${I.info}</span>
      <span class="help-title">Comment ça marche ?</span>
      <span class="help-toggle">${I.down}</span>
    </summary>
    <div class="help-body">
      <div class="help-grid">
        <div>
          <h4>Qu'est-ce qu'un template ?</h4>
          <p>Un dossier dans <code class="mono">C:\\claude-workspace\\templates\\&lt;id&gt;\\</code> contenant l'arborescence à dupliquer pour chaque nouveau workspace. Tous les fichiers texte sont copiés et leurs placeholders sont remplacés à la création.</p>
        </div>
        <div>
          <h4>Le fichier <code class="mono">.template.json</code></h4>
          <p>Méta du template (label, description, emoji). Géré automatiquement par cet éditeur — tu n'as pas à le toucher à la main.</p>
        </div>
        <div>
          <h4>Placeholders disponibles</h4>
          <p style="margin-bottom:var(--sp-2)">À l'intérieur des fichiers du template, ces marqueurs sont remplacés à la création par les <strong>infos saisies dans le formulaire « Nouveau workspace »</strong> :</p>
          <ul class="help-list">
            <li><code class="mono">{{name}}</code> → champ <strong>ID</strong> du workspace (ex. <code class="mono">audit-prod</code>)</li>
            <li><code class="mono">{{label}}</code> → champ <strong>Label</strong> (ex. <code class="mono">Audit Prod</code>)</li>
            <li><code class="mono">{{description}}</code> → champ <strong>Description</strong></li>
            <li><code class="mono">{{tools}}</code> → champ <strong>Outils / contexte</strong></li>
            <li><code class="mono">{{emoji}}</code> → champ <strong>Emoji</strong></li>
            <li><code class="mono">{{date}}</code> → date du jour à la création (ISO)</li>
          </ul>
        </div>
        <div>
          <h4>Bonnes pratiques</h4>
          <ul class="help-list">
            <li>Inclure systématiquement un <code class="mono">CLAUDE.md</code> avec le contexte projet</li>
            <li>Ajouter un <code class="mono">.gitignore</code> adapté</li>
            <li>Pour les configs MCP partagées, utiliser plutôt le registre global et lier via le scope MCPs</li>
            <li>Garder les templates &lt; 50 fichiers pour rester rapides à créer</li>
          </ul>
        </div>
      </div>
    </div>
  `;
  page.appendChild(help);

  const tpls = STATE.templates;
  if (!tpls.length) {
    page.appendChild(el('div', 'empty', `<div class="empty-title">Aucun template</div><p class="muted">Crée un dossier dans <code>templates/</code> avec un <code>.template.json</code>.</p>`));
  } else {
    const grid = el('div', 'template-grid');
    for (const t of tpls) {
      const card = el('div', 'template-card');
      card.innerHTML = `
        <div class="template-emoji">${escapeHtml(t.emoji || '📦')}</div>
        <h3 class="template-name">${escapeHtml(t.label || t.id)}</h3>
        <p class="template-desc">${escapeHtml(t.description || '—')}</p>
        <div class="template-meta">${t.file_count} fichier${t.file_count > 1 ? 's' : ''} · <span class="mono">${escapeHtml(t.id)}</span></div>
      `;
      const actions = el('div', 'template-actions');
      const ed = btn('Éditer', 'btn-sm btn-primary', I.edit);
      ed.addEventListener('click', () => modalEditTemplate(t.id));
      const open = btn('Dossier', 'btn-sm btn-ghost', I.folder);
      open.title = 'Ouvrir dans l\'explorateur';
      open.addEventListener('click', async () => {
        try { const r = await API.post('/api/open', { target: `template:${t.id}` }); toastOk(r.message || 'Ouvert'); }
        catch (e) { toastErr(e.message); }
      });
      const dup = btn('', 'btn-sm btn-ghost btn-icon-only', I.copy);
      dup.title = 'Dupliquer';
      dup.addEventListener('click', () => modalDuplicateTemplate(t));
      const rm = btn('', 'btn-sm btn-ghost btn-icon-only btn-danger', I.trash);
      rm.title = 'Supprimer';
      rm.addEventListener('click', () => confirmDialog(`Supprimer le template ${t.id} ?`, async () => {
        try { await API.del(`/api/templates/${t.id}`); toastOk('Supprimé'); STATE.loading = true; route(); }
        catch (e) { toastErr(e.message); }
      }, { danger: true }));
      actions.append(ed, open, dup, rm);
      card.appendChild(actions);
      grid.appendChild(card);
    }
    page.appendChild(grid);
  }
  c.appendChild(page);
}

async function modalEditTemplate(tplId) {
  const body = el('div');
  body.innerHTML = `<div class="page-loader"><div class="spinner"></div><span>Chargement du template…</span></div>`;
  const closeBtn = btn('Fermer', 'btn-ghost');
  const { close } = openModal({ title: `Template · ${tplId}`, body, footer: closeBtn, wide: true });
  closeBtn.addEventListener('click', close);

  let detail;
  try { detail = await API.get(`/api/templates/${tplId}`); }
  catch (e) { body.innerHTML = `<div class="error-box">${escapeHtml(e.message)}</div>`; return; }

  body.innerHTML = `
    <div class="tpl-meta-bar">
      <input class="input" name="emoji" value="${escapeHtml(detail.emoji || '📦')}" maxlength="4" style="max-width:60px;text-align:center;font-size:18px">
      <input class="input" name="label" value="${escapeHtml(detail.label || '')}" placeholder="Label" style="flex:1;min-width:160px">
      <input class="input" name="description" value="${escapeHtml(detail.description || '')}" placeholder="Description" style="flex:2;min-width:200px">
      <button class="btn btn-sm btn-primary" data-save-meta>Enregistrer</button>
    </div>
    <div class="dim mono" style="font-size:11px;margin-bottom:var(--sp-3)">${escapeHtml(detail.path)}</div>
    <div class="tpl-editor">
      <aside class="tpl-tree">
        <div class="tpl-tree-header">
          <span class="section-label" style="margin:0;flex:1">Fichiers</span>
          <button class="icon-btn" data-add-file title="Nouveau fichier">${I.plus}</button>
        </div>
        <div class="tpl-tree-list"></div>
      </aside>
      <main class="tpl-pane">
        <div class="tpl-pane-empty">Sélectionne un fichier ou clique sur <strong>+</strong> pour en créer un.</div>
      </main>
    </div>
  `;

  // Save meta
  body.querySelector('[data-save-meta]').addEventListener('click', async () => {
    const get = n => body.querySelector(`[name=${n}]`).value.trim();
    try {
      await API.post(`/api/templates/${tplId}/meta`, { label: get('label'), description: get('description'), emoji: get('emoji') });
      toastOk('Méta enregistrée');
      STATE.loading = true;  // Refresh list later
    } catch (e) { toastErr(e.message); }
  });

  const treeList = body.querySelector('.tpl-tree-list');
  const pane = body.querySelector('.tpl-pane');
  let files = detail.files.slice();
  let currentPath = null;

  const renderTree = () => {
    treeList.innerHTML = '';
    if (!files.length) {
      treeList.innerHTML = '<div class="dim" style="padding:var(--sp-3);font-size:12px">Aucun fichier</div>';
      return;
    }
    files.sort((a, b) => a.path.localeCompare(b.path));
    for (const f of files) {
      const item = el('div', 'tpl-tree-item' + (f.path === currentPath ? ' is-active' : ''));
      item.innerHTML = `
        <span class="tpl-tree-name mono">${escapeHtml(f.path)}</span>
        <span class="dim mono" style="font-size:10px">${fmtBytes(f.size)}</span>
      `;
      item.addEventListener('click', () => openFile(f.path));
      const rm = el('button', 'icon-btn tpl-tree-del', I.x);
      rm.title = 'Supprimer';
      rm.addEventListener('click', (e) => {
        e.stopPropagation();
        confirmDialog(`Supprimer ${f.path} ?`, async () => {
          try {
            await API.del(`/api/templates/${tplId}/file?path=${encodeURIComponent(f.path)}`);
            files = files.filter(x => x.path !== f.path);
            if (currentPath === f.path) { currentPath = null; pane.innerHTML = '<div class="tpl-pane-empty">Sélectionne un fichier.</div>'; }
            renderTree(); toastOk('Supprimé');
          } catch (err) { toastErr(err.message); }
        }, { danger: true });
      });
      item.appendChild(rm);
      treeList.appendChild(item);
    }
  };

  const openFile = async (path) => {
    currentPath = path;
    renderTree();
    pane.innerHTML = `<div class="page-loader"><div class="spinner"></div></div>`;
    let data;
    try { data = await API.get(`/api/templates/${tplId}/file?path=${encodeURIComponent(path)}`); }
    catch (e) { pane.innerHTML = `<div class="error-box">${escapeHtml(e.message)}</div>`; return; }
    if (data.binary || data.error) {
      pane.innerHTML = `<div class="error-box">${escapeHtml(data.error || 'Fichier binaire non éditable')}</div>`;
      return;
    }
    pane.innerHTML = `
      <div class="tpl-pane-header">
        <span class="mono" style="font-size:13px;flex:1">${escapeHtml(path)}</span>
        <span class="dim mono" style="font-size:11px">${fmtBytes(data.size)}</span>
        <button class="btn btn-sm btn-primary" data-save-file>Enregistrer</button>
      </div>
      <textarea class="textarea textarea-code tpl-editor-textarea" spellcheck="false"></textarea>
    `;
    const ta = pane.querySelector('textarea');
    ta.value = data.content;
    ta.focus();
    pane.querySelector('[data-save-file]').addEventListener('click', async () => {
      try {
        const r = await API.post(`/api/templates/${tplId}/file`, { path, content: ta.value });
        const f = files.find(x => x.path === path);
        if (f) f.size = r.size;
        renderTree();
        toastOk('Enregistré');
      } catch (e) { toastErr(e.message); }
    });
    // Ctrl+S to save
    ta.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        pane.querySelector('[data-save-file]').click();
      }
    });
  };

  // Add file — sélecteur dossier + nom de fichier
  body.querySelector('[data-add-file]').addEventListener('click', () => {
    // Liste des dossiers existants dans le template (extrait des paths fichiers)
    const folders = new Set(['']);  // racine
    for (const f of files) {
      const parts = f.path.split('/');
      for (let i = 1; i < parts.length; i++) {
        folders.add(parts.slice(0, i).join('/'));
      }
    }
    const folderList = Array.from(folders).sort();

    const fbody = el('div');
    fbody.innerHTML = `
      <p class="muted" style="margin-top:0">Choisis le dossier où placer le fichier (ou crée un nouveau sous-dossier).</p>
      <div class="field-row">
        <div class="field" style="flex:2">
          <label class="field-label">Dossier</label>
          <select class="select" name="folder">
            ${folderList.map(f => `<option value="${escapeHtml(f)}">${f === '' ? '/ (racine)' : escapeHtml('/' + f)}</option>`).join('')}
            <option value="__new__">＋ Nouveau sous-dossier…</option>
          </select>
        </div>
        <div class="field" style="flex:3">
          <label class="field-label">Nom du fichier *</label>
          <input class="input mono" name="filename" placeholder="CLAUDE.md, settings.json…">
        </div>
      </div>
      <div class="field" data-new-folder hidden>
        <label class="field-label">Nom du sous-dossier (peut contenir <code class="mono">/</code>)</label>
        <input class="input mono" name="new_folder" placeholder="config/sub">
      </div>
      <div class="field"><label class="field-label">Contenu initial</label><textarea class="textarea textarea-code" name="content" rows="8" placeholder="# {{label}}&#10;&#10;{{description}}"></textarea></div>
      <div class="dim" style="font-size:11.5px"><strong>Aperçu :</strong> <span class="mono" data-preview>—</span></div>
    `;

    const folderSel = fbody.querySelector('[name=folder]');
    const filenameInput = fbody.querySelector('[name=filename]');
    const newFolderField = fbody.querySelector('[data-new-folder]');
    const newFolderInput = fbody.querySelector('[name=new_folder]');
    const preview = fbody.querySelector('[data-preview]');

    const updatePreview = () => {
      const folder = folderSel.value === '__new__'
        ? newFolderInput.value.trim().replace(/^\/+|\/+$/g, '')
        : folderSel.value;
      const filename = filenameInput.value.trim();
      const full = [folder, filename].filter(Boolean).join('/');
      preview.textContent = full || '—';
    };

    folderSel.addEventListener('change', () => {
      newFolderField.hidden = folderSel.value !== '__new__';
      if (folderSel.value === '__new__') newFolderInput.focus();
      updatePreview();
    });
    [filenameInput, newFolderInput].forEach(i => i.addEventListener('input', updatePreview));

    const cancel = btn('Annuler', 'btn-ghost');
    const create = btn('Créer', 'btn-primary', I.plus);
    const { close: closeAdd } = openModal({ title: 'Nouveau fichier dans le template', body: fbody, footer: [cancel, create] });
    cancel.addEventListener('click', closeAdd);
    setTimeout(() => filenameInput.focus(), 50);

    create.addEventListener('click', async () => {
      const folder = folderSel.value === '__new__'
        ? newFolderInput.value.trim().replace(/^\/+|\/+$/g, '')
        : folderSel.value;
      const filename = filenameInput.value.trim();
      if (!filename) { toastErr('Nom de fichier requis'); return; }
      if (folderSel.value === '__new__' && !folder) { toastErr('Nom du sous-dossier requis'); return; }
      const path = [folder, filename].filter(Boolean).join('/');
      const content = fbody.querySelector('[name=content]').value;
      try {
        const r = await API.post(`/api/templates/${tplId}/file`, { path, content });
        files.push({ path: r.path, size: r.size });
        renderTree();
        closeAdd();
        toastOk('Fichier créé');
        openFile(r.path);
      } catch (e) { toastErr(e.message); }
    });
  });

  renderTree();
}

function modalDuplicateTemplate(src) {
  const body = el('div');
  body.innerHTML = `
    <div class="field-row">
      <div class="field"><label class="field-label">Nouvel ID *</label><input class="input mono" name="id" placeholder="mon-template"></div>
      <div class="field"><label class="field-label">Emoji</label><input class="input" name="emoji" value="📦"></div>
    </div>
    <div class="field"><label class="field-label">Label</label><input class="input" name="label" placeholder="Mon template"></div>
    <div class="field"><label class="field-label">Description</label><input class="input" name="description"></div>
  `;
  const cancel = btn('Annuler', 'btn-ghost');
  const ok = btn('Dupliquer', 'btn-primary', I.copy);
  const { close } = openModal({ title: `Dupliquer ${src.label || src.id}`, body, footer: [cancel, ok] });
  cancel.addEventListener('click', close);
  ok.addEventListener('click', async () => {
    const get = n => body.querySelector(`[name=${n}]`).value.trim();
    const payload = { source: src.id, id: get('id'), emoji: get('emoji'), label: get('label'), description: get('description') };
    try { await API.post('/api/templates/duplicate', payload); toastOk('Dupliqué'); close(); STATE.loading = true; route(); }
    catch (e) { toastErr(e.message); }
  });
}

/* ================================================================
   PAGE: TOOLS
   ================================================================ */
async function renderTools() {
  setBreadcrumbs([{ label: 'Outils' }]);
  setTopbarActions([]);

  const c = $('#content');
  c.innerHTML = '';
  const page = el('div', 'page');
  page.appendChild(el('div', 'page-header', `
    <div class="page-header-text">
      <div class="page-eyebrow"><span class="index">04.</span><span>Système</span></div>
      <h1 class="page-title">Outils</h1>
      <p class="page-subtitle">Accès rapide aux fichiers de configuration et utilitaires.</p>
    </div>
  `));

  const stack = el('div', 'tools-stack');

  // Apparence — sélecteur de thème
  stack.appendChild(el('div', 'section-label', '<span class="num">A.</span> Apparence & assistance'));
  const themeCard = el('div', 'card');
  themeCard.innerHTML = `<p class="muted" style="margin:0 0 var(--sp-3);font-size:13px">Choisis l'ambiance visuelle de ton dashboard. Le choix est mémorisé localement.</p>`;
  const themeGrid = el('div', 'theme-grid');
  const current = getCurrentTheme();
  for (const t of THEMES) {
    const card = el('button', 'theme-card' + (t.id === current ? ' is-active' : ''));
    card.type = 'button';
    card.dataset.theme = t.id;
    card.innerHTML = `
      <div class="theme-preview" style="--p-bg:${t.bg};--p-accent:${t.accent};--p-warm:${t.warm}">
        <div class="theme-preview-sidebar"></div>
        <div class="theme-preview-main">
          <div class="theme-preview-bar"></div>
          <div class="theme-preview-card"></div>
          <div class="theme-preview-dot"></div>
        </div>
      </div>
      <div class="theme-card-info">
        <div class="theme-card-name">${escapeHtml(t.label)}</div>
        <div class="theme-card-desc">${escapeHtml(t.desc)}</div>
      </div>
      <div class="theme-card-check">${I.check}</div>
    `;
    card.addEventListener('click', () => {
      applyTheme(t.id);
      themeGrid.querySelectorAll('.theme-card').forEach(c => c.classList.toggle('is-active', c.dataset.theme === t.id));
      toastOk(`Thème : ${t.label}`);
    });
    themeGrid.appendChild(card);
  }
  themeCard.appendChild(themeGrid);

  // Bouton "Rejouer le tutoriel"
  const tutorialRow = el('div');
  tutorialRow.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:var(--sp-3);margin-top:var(--sp-4);padding-top:var(--sp-3);border-top:1px solid var(--border)';
  tutorialRow.innerHTML = `
    <div>
      <div style="font-size:13px;font-weight:500;margin-bottom:2px">Tutoriel d'introduction</div>
      <div class="dim" style="font-size:11.5px">Le wizard de premier lancement (thème, import config, raccourcis…)</div>
    </div>
  `;
  const replayBtn = btn('Rejouer le tutoriel', 'btn-sm', I.sparkle);
  replayBtn.addEventListener('click', () => {
    resetOnboarded();
    startFirstRunWizard();
  });
  tutorialRow.appendChild(replayBtn);
  themeCard.appendChild(tutorialRow);

  // Vérifier les mises à jour
  const updateRow = el('div');
  updateRow.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:var(--sp-3);margin-top:var(--sp-3);padding-top:var(--sp-3);border-top:1px solid var(--border)';
  updateRow.innerHTML = `
    <div>
      <div style="font-size:13px;font-weight:500;margin-bottom:2px">Mises à jour</div>
      <div class="dim" style="font-size:11.5px">Synchronisation avec le dépôt git officiel d'Atelier</div>
    </div>
  `;
  const updateBtn = btn('Vérifier maintenant', 'btn-sm', I.refresh);
  updateBtn.addEventListener('click', () => modalSystemUpdate());
  updateRow.appendChild(updateBtn);
  themeCard.appendChild(updateRow);

  stack.appendChild(themeCard);

  // Onboarding / Import
  stack.appendChild(el('div', 'section-label', '<span class="num">B.</span> Onboarding'));
  const onbCard = el('div', 'card');
  onbCard.innerHTML = `<p class="muted" style="margin:0 0 var(--sp-3) 0;font-size:13px">Récupère MCPs et projets d'une installation Claude Code existante (ou enregistre un dossier déjà sur disque).</p>`;
  const onbRow = el('div', 'row');
  const onbScan = btn('Scanner ~/.claude/', 'btn-primary', I.download);
  onbScan.addEventListener('click', () => modalSetupWizard());
  const onbReg = btn('Enregistrer un dossier', 'btn', I.folder);
  onbReg.addEventListener('click', () => modalRegisterExisting());
  const onbMcp = btn('Coller du JSON MCP', 'btn-ghost', I.code);
  onbMcp.addEventListener('click', () => modalImportMCPs());
  const onbConflicts = btn('Conflits Claude global', 'btn-ghost', I.alert);
  onbConflicts.title = 'Détecter et nettoyer les MCPs en doublon avec ~/.claude/';
  onbConflicts.addEventListener('click', () => modalGlobalConflicts());
  onbRow.append(onbScan, onbReg, onbMcp, onbConflicts);
  onbCard.appendChild(onbRow);
  stack.appendChild(onbCard);

  // Quick open
  stack.appendChild(el('div', 'section-label', '<span class="num">C.</span> Accès rapide'));
  const quick = el('div', 'quick-grid');
  const quickItems = [
    { label: '~/.claude.json', target: 'claude-json' },
    { label: '~/.claude/settings.json', target: 'claude-settings' },
    { label: 'Root CLAUDE.md', target: 'root-claude-md' },
    { label: 'mcp/registry.json', target: 'registry' },
    { label: '.env.local', target: 'env-local' },
    { label: 'workspaces.json', target: 'workspaces-json' },
    { label: 'memory/', target: 'global-memory' },
  ];
  for (const it of quickItems) {
    const b = el('button', 'quick-btn', `${I.folder}<span>${escapeHtml(it.label)}</span>`);
    b.addEventListener('click', async () => {
      try { const r = await API.post('/api/open', { target: it.target }); toastOk(r.message); }
      catch (e) { toastErr(e.message); }
    });
    quick.appendChild(b);
  }
  stack.appendChild(quick);

  // Hooks globaux
  stack.appendChild(el('div', 'section-label', '<span class="num">D.</span> Hooks globaux'));
  const hooksCard = el('div', 'card');
  hooksCard.innerHTML = `<div class="dim" style="font-size:12px">Édition complète via la modale</div>`;
  const hooksBtn = btn('Éditer hooks globaux', 'btn', I.zap);
  hooksBtn.addEventListener('click', () => modalHooks(null));
  hooksCard.appendChild(hooksBtn);
  stack.appendChild(hooksCard);

  // Env vars
  stack.appendChild(el('div', 'section-label', '<span class="num">E.</span> Variables d\'environnement'));
  const envHost = el('div');
  stack.appendChild(envHost);
  loadEnvVars(envHost);

  // Backups
  stack.appendChild(el('div', 'section-label', '<span class="num">F.</span> Sauvegardes'));
  const backupHost = el('div');
  stack.appendChild(backupHost);
  loadBackups(backupHost);

  // Skills
  stack.appendChild(el('div', 'section-label', '<span class="num">G.</span> Skills globaux'));
  const skillsHost = el('div');
  stack.appendChild(skillsHost);
  renderGlobalSkills(skillsHost);

  // Cleanup
  stack.appendChild(el('div', 'section-label', '<span class="num">H.</span> Maintenance'));
  const maint = el('div', 'card');
  const maintBtn = btn('Nettoyer .bat orphelins', 'btn', I.trash);
  maintBtn.addEventListener('click', async () => {
    try { const r = await API.post('/api/cleanup/orphan-bats', {}); toastOk(`${(r.removed || []).length} fichier(s) supprimé(s)`); }
    catch (e) { toastErr(e.message); }
  });
  maint.appendChild(maintBtn);
  stack.appendChild(maint);

  page.appendChild(stack);
  c.appendChild(page);
}

async function loadEnvVars(host) {
  host.innerHTML = '<div class="page-loader"><div class="spinner"></div></div>';
  try {
    const r = await API.get('/api/env/values');
    const vals = r.values || {};
    const allKeys = Object.keys(vals).sort((a, b) => a.localeCompare(b));
    const wrap = el('div', 'card');
    wrap.innerHTML = `<div class="card-header"><h3 class="card-title">${allKeys.length} variable${allKeys.length > 1 ? 's' : ''}</h3></div>`;

    // Toolbar : ajout + filtre
    const toolbar = el('div');
    toolbar.style.cssText = 'display:flex;gap:var(--sp-2);margin-bottom:var(--sp-3);flex-wrap:wrap';
    toolbar.innerHTML = `<input class="input input-search" name="filter" placeholder="Filtrer…" style="flex:1;min-width:200px">`;
    wrap.appendChild(toolbar);

    const addRow = el('form');
    addRow.style.cssText = 'display:flex;gap:8px;margin-bottom:var(--sp-3)';
    addRow.innerHTML = `<input class="input mono" name="k" placeholder="KEY (ex. OPENAI_API_KEY)" style="max-width:260px"><input class="input" name="v" placeholder="value" style="flex:1">`;
    const addBtn = btn('Ajouter', 'btn-primary btn-sm', I.plus);
    addRow.appendChild(addBtn);
    addRow.addEventListener('submit', async (e) => {
      e.preventDefault();
      const k = addRow.querySelector('[name=k]').value.trim();
      const v = addRow.querySelector('[name=v]').value;
      if (!k) return;
      try { await API.post('/api/env', { key: k, value: v }); toastOk('Ajouté'); loadEnvVars(host); }
      catch (e) { toastErr(e.message); }
    });
    wrap.appendChild(addRow);

    if (!allKeys.length) {
      wrap.appendChild(el('div', 'dim', '<small>Aucune variable. Le fichier sera créé au premier ajout.</small>'));
      host.innerHTML = ''; host.appendChild(wrap);
      return;
    }

    const listHost = el('div');
    wrap.appendChild(listHost);

    const renderList = () => {
      const filter = (toolbar.querySelector('[name=filter]').value || '').trim().toLowerCase();
      const keys = filter
        ? allKeys.filter(k => k.toLowerCase().includes(filter) || (vals[k] || '').toLowerCase().includes(filter))
        : allKeys;
      if (!keys.length) {
        listHost.innerHTML = '<div class="dim" style="padding:var(--sp-3);font-size:12.5px">Aucun résultat.</div>';
        return;
      }
      // Groupement par préfixe avant le premier "_"
      const groups = {};
      for (const k of keys) {
        const prefix = k.includes('_') ? k.split('_')[0] : '_misc';
        (groups[prefix] = groups[prefix] || []).push(k);
      }
      const groupNames = Object.keys(groups).sort((a, b) => {
        if (a === '_misc') return 1;
        if (b === '_misc') return -1;
        return a.localeCompare(b);
      });

      listHost.innerHTML = '';
      for (const grpName of groupNames) {
        const grpHeader = el('div');
        grpHeader.style.cssText = 'font-family:var(--font-mono);font-size:10px;letter-spacing:0.16em;text-transform:uppercase;color:var(--text-dim);padding:var(--sp-3) 4px var(--sp-2);display:flex;align-items:center;gap:var(--sp-2)';
        grpHeader.innerHTML = `<span>${grpName === '_misc' ? 'Divers' : escapeHtml(grpName)}</span><span class="tabular dim" style="font-size:9.5px">(${groups[grpName].length})</span><span style="flex:1;height:1px;background:linear-gradient(90deg,var(--border),transparent)"></span>`;
        listHost.appendChild(grpHeader);

        const tbl = el('div', 'table-frame');
        tbl.style.marginBottom = 'var(--sp-2)';
        tbl.innerHTML = `<table class="table"><tbody></tbody></table>`;
        const tb = tbl.querySelector('tbody');
        for (const k of groups[grpName]) {
          const tr = el('tr');
          tr.innerHTML = `
            <td style="width:280px"><span class="mono" style="font-size:12.5px">${escapeHtml(k)}</span></td>
            <td class="mono" style="font-size:12.5px;color:var(--text-muted);max-width:520px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"><span data-revealed="0" data-real="${escapeHtml(vals[k])}">••••••••</span></td>
            <td style="text-align:right;width:80px"></td>
          `;
          const valSpan = tr.querySelector('[data-real]');
          const eyeBtn = el('button', 'icon-btn btn-icon-only', I.eye);
          eyeBtn.title = 'Afficher / masquer';
          eyeBtn.addEventListener('click', () => {
            const shown = valSpan.dataset.revealed === '1';
            valSpan.textContent = shown ? '••••••••' : valSpan.dataset.real;
            valSpan.dataset.revealed = shown ? '0' : '1';
            eyeBtn.innerHTML = shown ? I.eye : I.eyeoff;
          });
          const rm = el('button', 'icon-btn btn-icon-only btn-danger', I.trash);
          rm.title = 'Supprimer';
          rm.addEventListener('click', () => confirmDialog(`Supprimer ${k} ?`, async () => {
            try { await API.del('/api/env/' + encodeURIComponent(k)); toastOk('Supprimé'); loadEnvVars(host); }
            catch (e) { toastErr(e.message); }
          }, { danger: true }));
          tr.children[2].append(eyeBtn, rm);
          tb.appendChild(tr);
        }
        listHost.appendChild(tbl);
      }
    };
    toolbar.querySelector('[name=filter]').addEventListener('input', debounce(renderList, 100));
    renderList();

    host.innerHTML = ''; host.appendChild(wrap);
  } catch (e) { host.innerHTML = `<div class="error-box">${escapeHtml(e.message)}</div>`; }
}

async function loadBackups(host) {
  host.innerHTML = '<div class="page-loader"><div class="spinner"></div></div>';
  try {
    const r = await API.get('/api/backups');
    const wrap = el('div', 'card');
    wrap.innerHTML = `<div class="card-header"><h3 class="card-title">${r.items.length} sauvegarde${r.items.length > 1 ? 's' : ''}</h3></div>`;
    const b = btn('Sauvegarder maintenant', 'btn-primary btn-sm', I.archive);
    b.style.marginBottom = 'var(--sp-3)';
    b.addEventListener('click', async () => {
      try { const r2 = await API.post('/api/backup', {}); toastOk(r2.message); loadBackups(host); }
      catch (e) { toastErr(e.message); }
    });
    wrap.appendChild(b);
    if (!r.items.length) {
      wrap.appendChild(el('div', 'dim', '<small>Aucune sauvegarde pour le moment.</small>'));
    } else {
      const list = el('div', 'stack');
      for (const it of r.items.slice(0, 10)) {
        const row = el('div', 'list-row');
        row.innerHTML = `<div class="list-row-main"><div class="list-row-name mono">${escapeHtml(it.name)}</div><div class="list-row-desc">${fmtDate(it.mtime)} · ${fmtBytes(it.size)}</div></div>`;
        list.appendChild(row);
      }
      wrap.appendChild(list);
    }
    host.innerHTML = ''; host.appendChild(wrap);
  } catch (e) { host.innerHTML = `<div class="error-box">${escapeHtml(e.message)}</div>`; }
}

function renderGlobalSkills(host) {
  const skills = STATE.skills;
  const wrap = el('div', 'card');
  wrap.innerHTML = `<div class="card-header"><h3 class="card-title">${skills.length} skill${skills.length > 1 ? 's' : ''}</h3></div>`;
  const newBtn = btn('Nouveau skill', 'btn-primary btn-sm', I.plus);
  newBtn.style.marginBottom = 'var(--sp-3)';
  newBtn.addEventListener('click', () => modalNewSkill());
  wrap.appendChild(newBtn);
  if (!skills.length) {
    wrap.appendChild(el('div', 'dim', '<small>Aucun skill global.</small>'));
  } else {
    const list = el('div', 'stack');
    for (const s of skills) {
      const row = el('div', 'list-row');
      row.innerHTML = `<div class="list-row-main"><div class="list-row-name">${escapeHtml(s.name || s.id)}</div><div class="list-row-desc">${escapeHtml(s.description || '')}</div></div>`;
      const ed = btn('Éditer', 'btn-sm btn-ghost', I.edit);
      ed.addEventListener('click', () => modalEditSkill('global', s.id));
      const rm = btn('', 'btn-sm btn-ghost btn-icon-only btn-danger', I.trash);
      rm.title = 'Supprimer';
      rm.addEventListener('click', () => confirmDialog(`Supprimer ${s.id} ?`, async () => {
        try { await API.del(`/api/skills/global/${s.id}`); toastOk('Supprimé'); STATE.loading = true; route(); }
        catch (e) { toastErr(e.message); }
      }, { danger: true }));
      row.append(ed, rm);
      list.appendChild(row);
    }
    wrap.appendChild(list);
  }
  host.appendChild(wrap);
}

/* ================================================================
   MODALS — workspace, skill, settings, hooks, etc.
   ================================================================ */
function modalNewWorkspace() {
  const body = el('div');
  body.innerHTML = `
    <div class="field-row">
      <div class="field"><label class="field-label">ID *</label><input class="input mono" name="id" placeholder="mon-projet"></div>
      <div class="field"><label class="field-label">Emoji</label><input class="input" name="emoji" value="📁"></div>
    </div>
    <div class="field"><label class="field-label">Label</label><input class="input" name="label" placeholder="Mon Projet"></div>
    <div class="field"><label class="field-label">Description</label><input class="input" name="description"></div>
    <div class="field"><label class="field-label">Outils / contexte</label><input class="input" name="tools" placeholder="Python, Docker, n8n..."></div>
    <div class="field"><label class="field-label">Template</label><select class="select" name="template">${STATE.templates.map(t => `<option value="${escapeHtml(t.id)}">${escapeHtml(t.emoji || '📦')} ${escapeHtml(t.label || t.id)}</option>`).join('') || '<option value="blank">Blank</option>'}</select></div>
  `;
  const cancel = btn('Annuler', 'btn-ghost');
  const create = btn('Créer', 'btn-primary', I.plus);
  const { close } = openModal({ title: 'Nouveau workspace', body, footer: [cancel, create] });
  cancel.addEventListener('click', close);
  create.addEventListener('click', async () => {
    const get = n => body.querySelector(`[name=${n}]`).value.trim();
    const payload = { id: get('id'), emoji: get('emoji'), label: get('label'), description: get('description'), tools: get('tools'), template: get('template') || 'blank' };
    if (!payload.id) { toastErr('ID requis'); return; }
    try { await API.post('/api/workspaces', payload); toastOk('Workspace créé'); close(); STATE.loading = true; location.hash = `#/workspace/${payload.id}`; }
    catch (e) { toastErr(e.message); }
  });
}

function modalEditWorkspace(w) {
  const body = el('div');
  body.innerHTML = `
    <div class="field-row">
      <div class="field"><label class="field-label">Label</label><input class="input" name="label" value="${escapeHtml(w.label || '')}"></div>
      <div class="field"><label class="field-label">Emoji</label><input class="input" name="emoji" value="${escapeHtml(w.emoji || '📁')}"></div>
    </div>
    <div class="field"><label class="field-label">Description</label><input class="input" name="description" value="${escapeHtml(w.description || '')}"></div>
    <div class="field"><label class="field-label">Path</label><input class="input mono" name="path" value="${escapeHtml(w.path || '')}"></div>
  `;
  const cancel = btn('Annuler', 'btn-ghost');
  const save = btn('Enregistrer', 'btn-primary');
  const { close } = openModal({ title: `Modifier ${w.id}`, body, footer: [cancel, save] });
  cancel.addEventListener('click', close);
  save.addEventListener('click', async () => {
    const get = n => body.querySelector(`[name=${n}]`).value.trim();
    try { await API.post(`/api/workspaces/${w.id}/update`, { label: get('label'), emoji: get('emoji'), description: get('description'), path: get('path') }); toastOk('Mis à jour'); close(); STATE.loading = true; route(); }
    catch (e) { toastErr(e.message); }
  });
}

function modalDuplicateWorkspace(w) {
  const body = el('div');
  body.innerHTML = `
    <div class="field"><label class="field-label">Nouvel ID *</label><input class="input mono" name="id" placeholder="${escapeHtml(w.id)}-copy"></div>
    <div class="field"><label class="field-label">Label</label><input class="input" name="label" value="${escapeHtml((w.label || w.id) + ' (copie)')}"></div>
    <div class="field"><label class="field-label">Description</label><input class="input" name="description" value="${escapeHtml(w.description || '')}"></div>
  `;
  const cancel = btn('Annuler', 'btn-ghost');
  const dup = btn('Dupliquer', 'btn-primary', I.copy);
  const { close } = openModal({ title: `Dupliquer ${w.id}`, body, footer: [cancel, dup] });
  cancel.addEventListener('click', close);
  dup.addEventListener('click', async () => {
    const get = n => body.querySelector(`[name=${n}]`).value.trim();
    try { await API.post('/api/workspaces/duplicate', { source: w.id, id: get('id'), label: get('label'), description: get('description'), emoji: w.emoji }); toastOk('Dupliqué'); close(); STATE.loading = true; location.hash = `#/workspace/${get('id')}`; }
    catch (e) { toastErr(e.message); }
  });
}

function modalDeleteWorkspace(w) {
  const body = el('div');
  body.innerHTML = `
    <p style="margin-top:0">Action irréversible — confirme l'ID du workspace pour valider.</p>
    <div class="field"><label class="field-label">Tape <code class="mono">${escapeHtml(w.id)}</code> pour confirmer</label><input class="input mono" name="confirm" autocomplete="off"></div>
    <label class="row" style="cursor:pointer;font-size:13px"><input type="checkbox" name="purge"> <span>Supprimer aussi le dossier sur disque (purge)</span></label>
  `;
  const cancel = btn('Annuler', 'btn-ghost');
  const del = btn('Supprimer', 'btn-danger', I.trash);
  const { close } = openModal({ title: 'Supprimer le workspace', body, footer: [cancel, del] });
  cancel.addEventListener('click', close);
  del.addEventListener('click', async () => {
    if (body.querySelector('[name=confirm]').value !== w.id) { toastErr('ID incorrect'); return; }
    const purge = body.querySelector('[name=purge]').checked;
    try { await API.del(`/api/workspaces/${w.id}${purge ? '?purge=true' : ''}`); toastOk('Supprimé'); close(); STATE.loading = true; location.hash = '#/'; }
    catch (e) { toastErr(e.message); }
  });
}

function modalEditSettings(wsId) {
  (async () => {
    let data;
    try { data = await API.get(`/api/workspaces/${wsId}/settings`); }
    catch (e) { toastErr(e.message); return; }
    const body = el('div');
    body.innerHTML = `<div class="dim" style="font-size:11.5px;margin-bottom:6px">${escapeHtml(data.path)}</div>`;
    const ta = el('textarea', 'textarea textarea-code');
    ta.rows = 16; ta.value = data.content || '{}';
    body.appendChild(ta);
    const cancel = btn('Annuler', 'btn-ghost');
    const save = btn('Enregistrer', 'btn-primary');
    const { close } = openModal({ title: 'settings.json', body, footer: [cancel, save], wide: true });
    cancel.addEventListener('click', close);
    save.addEventListener('click', async () => {
      try { JSON.parse(ta.value); }
      catch (e) { toastErr('JSON invalide : ' + e.message); return; }
      try { await API.post(`/api/workspaces/${wsId}/settings`, { content: ta.value }); toastOk('Enregistré'); close(); }
      catch (e) { toastErr(e.message); }
    });
  })();
}

function modalPermissions(wsId) {
  (async () => {
    let settings = {};
    try { settings = JSON.parse((await API.get(`/api/workspaces/${wsId}/settings`)).content) || {}; } catch {}
    const perms = settings.permissions || {};
    const allow = (perms.allow || []).join('\n');
    const deny = (perms.deny || []).join('\n');
    const body = el('div');
    body.innerHTML = `
      <p class="muted" style="margin-top:0">Une règle par ligne. Ex : <code class="mono">Bash(npm:*)</code>, <code class="mono">mcp__*</code></p>
      <div class="field"><label class="field-label text-ok">Allow</label><textarea class="textarea" name="allow" rows="6">${escapeHtml(allow)}</textarea></div>
      <div class="field"><label class="field-label text-err">Deny</label><textarea class="textarea" name="deny" rows="6">${escapeHtml(deny)}</textarea></div>
    `;
    const cancel = btn('Annuler', 'btn-ghost');
    const save = btn('Enregistrer', 'btn-primary');
    const { close } = openModal({ title: 'Permissions', body, footer: [cancel, save], wide: true });
    cancel.addEventListener('click', close);
    save.addEventListener('click', async () => {
      const a = body.querySelector('[name=allow]').value.split('\n').map(s => s.trim()).filter(Boolean);
      const d = body.querySelector('[name=deny]').value.split('\n').map(s => s.trim()).filter(Boolean);
      const value = (a.length || d.length) ? { allow: a, deny: d } : null;
      try { await API.post(`/api/workspaces/${wsId}/settings/permissions`, { value }); toastOk('Enregistré'); close(); }
      catch (e) { toastErr(e.message); }
    });
  })();
}

function modalHooks(wsId) {
  (async () => {
    let current = {};
    if (wsId) {
      try { const s = JSON.parse((await API.get(`/api/workspaces/${wsId}/settings`)).content); current = s.hooks || {}; } catch {}
    } else {
      try { current = (await API.get('/api/hooks/global')).hooks || {}; } catch {}
    }
    const body = el('div');
    body.innerHTML = `
      <p class="muted" style="margin-top:0">JSON des hooks Claude Code. ${wsId ? 'Spécifique au workspace.' : 'Configuration globale.'}</p>
      <div class="field"><textarea class="textarea textarea-code" name="hooks" rows="14">${escapeHtml(JSON.stringify(current, null, 2))}</textarea></div>
    `;
    const cancel = btn('Annuler', 'btn-ghost');
    const save = btn('Enregistrer', 'btn-primary');
    const { close } = openModal({ title: wsId ? `Hooks · ${wsId}` : 'Hooks globaux', body, footer: [cancel, save], wide: true });
    cancel.addEventListener('click', close);
    save.addEventListener('click', async () => {
      let hooks;
      try { hooks = JSON.parse(body.querySelector('[name=hooks]').value); }
      catch (e) { toastErr('JSON invalide : ' + e.message); return; }
      try {
        if (wsId) await API.post(`/api/workspaces/${wsId}/settings/hooks`, { value: Object.keys(hooks).length ? hooks : null });
        else await API.post('/api/hooks/global', { hooks });
        toastOk('Enregistré'); close();
      } catch (e) { toastErr(e.message); }
    });
  })();
}

function modalNewSkill() {
  const body = el('div');
  body.innerHTML = `
    <div class="field-row">
      <div class="field" style="flex:2"><label class="field-label">Nom * (a-z, 0-9, _, -)</label><input class="input mono" name="name" placeholder="mon-skill"></div>
      <div class="field" style="flex:1"><label class="field-label">Scope</label><select class="select" name="scope"><option value="global">Global</option>${STATE.workspaces.map(w => `<option value="workspace:${escapeHtml(w.id)}">Workspace · ${escapeHtml(w.id)}</option>`).join('')}</select></div>
    </div>
    <div class="field"><label class="field-label">Description * (1 phrase)</label><input class="input" name="description" placeholder="Ce skill aide à…"></div>
    <div class="field"><label class="field-label">Instructions (corps du SKILL.md, optionnel)</label><textarea class="textarea textarea-code" name="body" rows="10" placeholder="Décris ici comment Claude doit utiliser ce skill : étapes, règles, exemples…"></textarea></div>
    <div class="dim" style="font-size:11.5px">Tu pourras ajouter d'autres fichiers (références, exemples) en éditant le skill après création.</div>
  `;
  const cancel = btn('Annuler', 'btn-ghost');
  const ok = btn('Créer', 'btn-primary', I.plus);
  const { close } = openModal({ title: 'Nouveau skill', body, footer: [cancel, ok], wide: true });
  cancel.addEventListener('click', close);
  ok.addEventListener('click', async () => {
    const get = n => body.querySelector(`[name=${n}]`).value;
    const payload = { name: get('name').trim(), scope: get('scope'), description: get('description').trim(), body: get('body') };
    if (!payload.name) { toastErr('Nom requis'); return; }
    if (!payload.description) { toastErr('Description requise'); return; }
    try {
      await API.post('/api/skills', payload);
      toastOk('Skill créé'); close();
      STATE.loading = true;
      // Navigue vers la page Skills si on était ailleurs
      if (location.hash !== '#/skills') location.hash = '#/skills'; else route();
    } catch (e) { toastErr(e.message); }
  });
}

function modalEditSkill(scope, name) {
  (async () => {
    let data;
    try { data = await API.get(`/api/skills/${scope}/${name}/content`); }
    catch (e) { toastErr(e.message); return; }
    const body = el('div');
    body.innerHTML = `<div class="dim mono" style="font-size:11.5px;margin-bottom:6px">${escapeHtml(data.path || '')}</div>`;
    const ta = el('textarea', 'textarea textarea-code');
    ta.rows = 18; ta.value = data.content || '';
    body.appendChild(ta);
    const cancel = btn('Annuler', 'btn-ghost');
    const save = btn('Enregistrer', 'btn-primary');
    const { close } = openModal({ title: `Skill ${scope}/${name}`, body, footer: [cancel, save], wide: true });
    cancel.addEventListener('click', close);
    save.addEventListener('click', async () => {
      try { await API.post(`/api/skills/${scope}/${name}/content`, { content: ta.value }); toastOk('Enregistré'); close(); }
      catch (e) { toastErr(e.message); }
    });
  })();
}

function modalEditFileItem(kind, scope, name) {
  (async () => {
    let initial = { name: '', description: '', content: '' };
    if (name) {
      try { const r = await API.get(`/api/${kind}/${scope}/${name}/content`); initial = { name, description: r.description || '', content: r.content || '' }; }
      catch (e) { toastErr(e.message); return; }
    }
    const body = el('div');
    body.innerHTML = `
      <div class="field"><label class="field-label">Nom *</label><input class="input mono" name="name" value="${escapeHtml(initial.name)}" ${name ? 'readonly' : ''}></div>
      <div class="field"><label class="field-label">Description</label><input class="input" name="description" value="${escapeHtml(initial.description)}"></div>
      <div class="field"><label class="field-label">Contenu</label><textarea class="textarea textarea-code" name="body" rows="14">${escapeHtml(initial.content)}</textarea></div>
    `;
    const cancel = btn('Annuler', 'btn-ghost');
    const save = btn('Enregistrer', 'btn-primary');
    const { close } = openModal({ title: `${name ? 'Modifier' : 'Nouveau'} ${kind === 'agents' ? 'agent' : 'commande'}`, body, footer: [cancel, save], wide: true });
    cancel.addEventListener('click', close);
    save.addEventListener('click', async () => {
      const get = n => body.querySelector(`[name=${n}]`).value;
      try {
        if (name) {
          await API.post(`/api/${kind}/${scope}/${name}/content`, { content: get('body') });
        } else {
          const wsMatch = scope.match(/^workspace:(.+)$/);
          const payload = { name: get('name').trim(), description: get('description').trim(), content: get('body') };
          if (wsMatch) payload.workspace = wsMatch[1];
          await API.post(`/api/${kind}`, payload);
        }
        toastOk('Enregistré'); close(); route();
      } catch (e) { toastErr(e.message); }
    });
  })();
}

/* ================================================================
   COMMAND PALETTE
   ================================================================ */
function openPalette() {
  const root = $('#palette-root');
  root.innerHTML = '';
  const overlay = el('div', 'palette-overlay');
  const palette = el('div', 'palette');
  palette.innerHTML = `
    <input class="palette-input" type="text" placeholder="Recherche · workspaces · MCPs · skills · templates…" />
    <div class="palette-list"></div>
    <div class="palette-hint"><span><kbd>↑</kbd> <kbd>↓</kbd> naviguer</span><span><kbd>↵</kbd> ouvrir</span><span><kbd>Esc</kbd> fermer</span></div>
  `;
  overlay.appendChild(palette);
  root.appendChild(overlay);
  const input = palette.querySelector('input');
  const list = palette.querySelector('.palette-list');
  let active = 0; let results = [];

  const close = () => { root.innerHTML = ''; document.removeEventListener('keydown', onKey); };
  const goto = (r) => {
    if (r.route) { location.hash = r.route; }
    else if (r.kind === 'action') { r.action(); }
    close();
  };
  const render = () => {
    list.innerHTML = '';
    if (!results.length) {
      list.innerHTML = '<div class="palette-empty">Aucun résultat</div>';
      return;
    }
    results.forEach((r, i) => {
      const item = el('div', 'palette-item' + (i === active ? ' active' : ''));
      item.innerHTML = `<span class="kind">${escapeHtml(r.kind)}</span><span class="label">${escapeHtml(r.label)}</span>`;
      item.addEventListener('click', () => goto(r));
      list.appendChild(item);
    });
  };
  const search = debounce(async (q) => {
    if (!q) {
      results = [
        { kind: 'page', label: 'Accueil', route: '#/' },
        { kind: 'page', label: 'MCPs', route: '#/mcps' },
        { kind: 'page', label: 'Plugins', route: '#/plugins' },
        { kind: 'page', label: 'Templates', route: '#/templates' },
        { kind: 'page', label: 'Outils', route: '#/tools' },
        { kind: 'action', label: 'Nouveau workspace', action: () => modalNewWorkspace() },
        { kind: 'action', label: 'Nouveau MCP', action: () => modalNewMCP() },
        { kind: 'action', label: 'Sync tous les workspaces', action: async () => { try { await API.post('/api/sync-all', {}); toastOk('Sync OK'); } catch (e) { toastErr(e.message); } } },
      ];
      active = 0; render(); return;
    }
    try {
      const r = await API.get(`/api/search?q=${encodeURIComponent(q)}`);
      results = (r.results || []).map(x => ({ kind: x.kind, label: x.label || x.id, route: x.route }));
    } catch { results = []; }
    active = 0; render();
  }, 120);

  input.addEventListener('input', () => search(input.value));
  search('');

  const onKey = (e) => {
    if (e.key === 'Escape') return close();
    if (e.key === 'ArrowDown') { active = Math.min(active + 1, results.length - 1); render(); e.preventDefault(); }
    if (e.key === 'ArrowUp') { active = Math.max(active - 1, 0); render(); e.preventDefault(); }
    if (e.key === 'Enter' && results[active]) { goto(results[active]); }
  };
  document.addEventListener('keydown', onKey);
  overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
  setTimeout(() => input.focus(), 50);
}

/* ================================================================
   KEYBOARD SHORTCUTS
   ================================================================ */
let lastKey = null; let lastKeyAt = 0;
document.addEventListener('keydown', (e) => {
  // ignore inputs
  if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) {
    if (e.key === 'Escape') e.target.blur();
    return;
  }
  if (e.key === '/' || (e.key === 'k' && (e.metaKey || e.ctrlKey))) {
    e.preventDefault(); openPalette(); return;
  }
  if (e.key === 'n') return modalNewWorkspace();
  if (e.key === 'm') return modalNewMCP();
  if (e.key === 's') {
    API.post('/api/sync-all', {}).then(() => toastOk('Sync terminé')).catch(e => toastErr(e.message));
    return;
  }
  // 'g' chord -> next key navigates
  if (e.key === 'g') { lastKey = 'g'; lastKeyAt = Date.now(); return; }
  if (lastKey === 'g' && Date.now() - lastKeyAt < 1000) {
    const map = { h: '#/', m: '#/mcps', p: '#/plugins', k: '#/skills', t: '#/templates', o: '#/tools', a: '#/aide' };
    if (map[e.key]) { location.hash = map[e.key]; lastKey = null; e.preventDefault(); return; }
    lastKey = null;
  }
});

/* ================================================================
   INIT
   ================================================================ */
function init() {
  renderSidebar();
  $('#open-palette').addEventListener('click', openPalette);
  $('#sidebar-toggle').addEventListener('click', () => $('#sidebar').classList.toggle('open'));
  document.addEventListener('click', (e) => {
    if (window.innerWidth <= 900 && !e.target.closest('#sidebar') && !e.target.closest('#sidebar-toggle')) {
      $('#sidebar').classList.remove('open');
    }
  });
  route().then(async () => {
    // Charger l'état UI depuis le serveur (source de vérité)
    let uiState = null;
    try { uiState = await API.get('/api/ui-state'); } catch {}

    // Synchroniser le thème serveur → local si différent du cache LS
    if (uiState?.theme && uiState.theme !== getCurrentTheme()) {
      applyTheme(uiState.theme, { save: false });
    }

    // Premier lancement : déclenche le wizard
    if (uiState && !uiState.onboarded) {
      setTimeout(() => startFirstRunWizard(), 400);
    }

    // Vérification de mise à jour en arrière-plan (non-bloquante)
    setTimeout(() => {
      checkForUpdates().then(renderUpdateBadge).catch(() => {});
    }, 1500);
  });
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
else init();
