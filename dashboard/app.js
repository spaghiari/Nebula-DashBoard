/* ================================================================
   Nebula — Claude Workspace Dashboard
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
I.brain     = _icon('<path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2z"/><path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2z"/>');

/* === THEMES ======================================================= */
const THEMES = [
  { id: 'nebula',        label: 'Nebula',        desc: 'Sombre · violet & ocre',        accent: '#a78bfa', warm: '#f4a672', bg: '#0a0a0f' },
  { id: 'nebula-clair',  label: 'Nebula clair',  desc: 'Clair · violet',                accent: '#7c3aed', warm: '#c2410c', bg: '#f8f7fb' },
  { id: 'marine',         label: 'Marine',         desc: 'Sombre · bleu profond',         accent: '#60a5fa', warm: '#fbbf24', bg: '#08101c' },
  { id: 'solarized',     label: 'Solarized',     desc: 'Sombre · cyan & ambre',         accent: '#2aa198', warm: '#b58900', bg: '#002b36' },
  { id: 'cuivre',        label: 'Cuivre',        desc: 'Sombre · bronze chaleureux',    accent: '#d97706', warm: '#fde68a', bg: '#1a0e05' },
];

function applyTheme(id, { save = true } = {}) {
  const valid = THEMES.find(t => t.id === id) ? id : 'nebula';
  if (valid === 'nebula') document.documentElement.removeAttribute('data-theme');
  else document.documentElement.setAttribute('data-theme', valid);
  try { localStorage.setItem('nebula-theme', valid); } catch {}
  if (save) API.post('/api/ui-state', { theme: valid }).catch(() => {});
}

function getCurrentTheme() {
  try {
    const stored = localStorage.getItem('nebula-theme');
    if (stored && THEMES.find(t => t.id === stored)) return stored;
  } catch {}
  return 'nebula';
}

// Appliquer immédiatement au chargement depuis le cache local (évite le flash)
applyTheme(getCurrentTheme(), { save: false });

/* === HELPERS ====================================================== */
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
const escapeHtml = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
// Filtre une URL avant de l'injecter dans un href : bloque javascript:, data:, vbscript:
const safeUrl = (u) => {
  const s = String(u ?? '').trim();
  return /^(https?:\/\/|\/|#|mailto:)/i.test(s) ? s : '';
};
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
    // X-Nebula-XHR : header custom posable seulement par fetch/XHR same-origin.
    // Bloque les attaques CSRF basiques sur les routes sensibles
    // (un <form> ou <img> ne peut pas le poser).
    const opts = { method, headers: { 'X-Nebula-XHR': '1' } };
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
  skillsLibrary: [],
  stats: {},
  wsMcps: {},      // ws_id -> {active, has_file}
  sanity: null,
  journalCount: 0,
  filter: { mcp: '' },
  loading: true,
  pagePollers: [],   // setInterval ids actifs sur la page courante (cleared à chaque navigation)
  pageTimeouts: [],  // setTimeout ids en attente sur la page courante
  uiState: null,     // {theme, onboarded} chargé depuis /api/ui-state au démarrage
  tour: null,        // Tour guidé actif : { name, step, definition }
};

// Enregistre un poller à nettoyer lors du prochain changement de page
function registerPagePoller(intervalId) {
  STATE.pagePollers.push(intervalId);
}
// Enregistre un setTimeout à nettoyer lors du prochain changement de page
function registerPageTimeout(timeoutId) {
  STATE.pageTimeouts.push(timeoutId);
  return timeoutId;
}
function clearPagePollers() {
  for (const id of STATE.pagePollers) clearInterval(id);
  for (const id of STATE.pageTimeouts) clearTimeout(id);
  STATE.pagePollers = [];
  STATE.pageTimeouts = [];
}

/* === TOAST / SNACKBAR ============================================ */
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

// Snackbar : toast avec un bouton d'action (ex: UNDO sur suppression)
function snackbar(msg, { actionLabel, onAction, type = 'success', duration = 8000 } = {}) {
  const root = $('#toast-root');
  const el = document.createElement('div');
  el.className = `toast toast-${type} toast-action`;
  const icon = type === 'error' ? I.alert : type === 'success' ? I.success : I.info;
  let timer = null;
  const close = () => {
    if (timer) { clearTimeout(timer); timer = null; }
    el.classList.add('toast-out');
    setTimeout(() => el.remove(), 200);
  };
  el.innerHTML = `<span class="toast-icon">${icon}</span><div class="toast-content">${escapeHtml(msg)}</div>`;
  if (actionLabel && typeof onAction === 'function') {
    const btnEl = document.createElement('button');
    btnEl.className = 'toast-action-btn';
    btnEl.type = 'button';
    btnEl.textContent = actionLabel;
    btnEl.addEventListener('click', () => {
      close();
      try { onAction(); } catch (e) { toastErr(e.message); }
    });
    el.appendChild(btnEl);
  }
  root.appendChild(el);
  timer = setTimeout(close, duration);
}

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
  { id: 'reflexive', label: 'Reflexive',   route: '#/reflexive', icon: I.brain,   key: 'r' },
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
  const [ws, mcps, env, tpls, plugins, skills, uiState, library] = await Promise.all([
    safe('/api/workspaces', { workspaces: [] }),
    safe('/api/mcps',       { mcps: [] }),
    safe('/api/env',        { keys: [], file: null, exists: false }),
    safe('/api/templates',  { templates: [] }),
    safe('/api/plugins',    { enabled: {}, count: 0 }),
    safe('/api/skills',     { global: [] }),
    safe('/api/ui-state',   { theme: 'nebula', onboarded: false }),
    safe('/api/skills-library', { skills: [] }),
  ]);
  STATE.workspaces = ws.workspaces || [];
  STATE.mcps = mcps.mcps || [];
  STATE.envKeys = env.keys || [];
  STATE.envFile = env.file;
  STATE.envExists = env.exists;
  STATE.templates = tpls.templates || [];
  STATE.plugins = plugins;
  STATE.skills = skills.global || [];
  STATE.skillsLibrary = library.skills || [];
  STATE.uiState = uiState;

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
  clearPagePollers();
  updateActiveNav();
  const hash = location.hash || '#/';
  // Ancres intra-page (ex. #h-env depuis le TOC d'Aide) : on laisse le
  // navigateur scroller, on ne re-render rien — sinon on perd la page courante.
  if (hash && !hash.startsWith('#/')) return;
  if (STATE.loading) await loadAll();
  const content = $('#content');
  content.innerHTML = '<div class="page-loader"><div class="spinner"></div><span>Chargement…</span></div>';
  try {
    if (hash === '#/') return await renderHome();
    if (hash === '#/mcps') return await renderMCPs();
    if (hash === '#/plugins') return await renderPlugins();
    if (hash === '#/skills') return await renderSkills();
    if (hash === '#/templates') return await renderTemplates();
    if (hash === '#/tools') return await renderTools();
    if (hash === '#/aide' || hash.startsWith('#/aide/')) return await renderHelp();
    if (hash === '#/reflexive' || hash.startsWith('#/reflexive/')) return await renderReflexive();
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
// Bandeau "Mise en route" sur Home — affiché tant que la checklist n'est pas complète.
// Retourne null si tout est OK (≥6/6 étapes faites) → la home reste épurée pour les users avancés.
function buildHomeQuickstart() {
  // Mêmes 6 critères que dans buildOnboardingChecklist (Outils → A. Démarrage)
  const onboardedDone = !!(STATE.uiState && STATE.uiState.onboarded);
  const themePicked = (function() {
    try { return !!localStorage.getItem('nebula-theme'); } catch { return false; }
  })();
  const hasMcps = (STATE.mcps || []).length > 0;
  const hasWorkspaces = (STATE.workspaces || []).length > 0;
  const hasScopedMcps =
    (STATE.mcps || []).some(m => (m.workspaces || []).length > 0) ||
    Object.values(STATE.wsMcps || {}).some(x => (x.active || []).length > 0);
  const hasPlugins = (STATE.plugins && STATE.plugins.count > 0) || false;

  const steps = [
    { done: onboardedDone, label: 'Wizard d\'introduction', cta: { label: 'Rejouer', fn: () => { resetOnboarded(); startFirstRunWizard(); } } },
    { done: themePicked,   label: 'Thème choisi',          cta: { label: 'Choisir', fn: () => { location.hash = '#/tools'; } } },
    { done: hasMcps,       label: 'Au moins 1 MCP',        cta: { label: 'Scanner ~/.claude/', fn: () => modalSetupWizard() } },
    { done: hasWorkspaces, label: 'Au moins 1 workspace',  cta: { label: 'Enregistrer un dossier', fn: () => modalRegisterExisting() } },
    { done: hasScopedMcps, label: 'MCPs scopés',           cta: { label: 'Aller aux MCPs', fn: () => { location.hash = '#/mcps'; } } },
    { done: hasPlugins,    label: '1 plugin actif',        cta: { label: 'Voir plugins', fn: () => { location.hash = '#/plugins'; } } },
  ];
  const doneCount = steps.filter(s => s.done).length;
  if (doneCount >= steps.length) return null;  // Tout OK → pas de bandeau

  const nextStep = steps.find(s => !s.done);
  const card = el('div', 'home-quickstart');
  card.innerHTML = `
    <div class="home-quickstart-head">
      <div>
        <div class="home-quickstart-title">🚀 Mise en route — ${doneCount} / ${steps.length}</div>
        <div class="home-quickstart-sub">Continue la configuration : <strong>${escapeHtml(nextStep.label)}</strong></div>
      </div>
      <div class="home-quickstart-actions"></div>
    </div>
    <div class="home-quickstart-bar"><div class="home-quickstart-fill" style="width:${(doneCount / steps.length) * 100}%"></div></div>
    <div class="home-quickstart-steps">
      ${steps.map(s => `<span class="home-quickstart-step ${s.done ? 'is-done' : ''}" title="${escapeHtml(s.label)}">${s.done ? '✓' : '○'} ${escapeHtml(s.label)}</span>`).join('')}
    </div>
  `;

  const actions = card.querySelector('.home-quickstart-actions');
  const ctaBtn = btn(nextStep.cta.label, 'btn-sm btn-primary');
  ctaBtn.addEventListener('click', nextStep.cta.fn);
  const moreBtn = btn('Voir checklist complète', 'btn-sm btn-ghost');
  moreBtn.addEventListener('click', () => { location.hash = '#/tools'; });
  actions.append(ctaBtn, moreBtn);

  return card;
}

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
      <h1 class="page-title">Nebula</h1>
      <p class="page-subtitle">Pilotage des workspaces, MCPs, plugins et skills Claude Code.</p>
    </div>
  `));

  // Banner "Première fois ?" — uniquement si tour jamais lancé ET install vide
  let tourDone = false;
  try { tourDone = localStorage.getItem('nebula-tour-completed') === '1'; } catch {}
  const isFreshInstall = (STATE.workspaces.length === 0 && STATE.mcps.length === 0);
  if (!tourDone && isFreshInstall) {
    const banner = el('div', 'callout callout-info');
    banner.style.cssText = 'margin-bottom:var(--sp-4);background:linear-gradient(90deg,rgba(167,139,250,0.08),rgba(124,58,237,0.04));border-color:var(--accent)';
    banner.innerHTML = `
      <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
        <div style="font-size:32px">🎯</div>
        <div style="flex:1;min-width:240px">
          <strong style="font-size:14px">Première fois sur Nebula ?</strong>
          <p style="margin:4px 0 0;font-size:12.5px">Une visite guidée interactive de ~2 min te montre l'essentiel : workspaces, MCPs, skills, templates. Avec spotlight sur les vrais éléments de l'UI.</p>
        </div>
      </div>
    `;
    const launchBtn = btn('🎯 Démarrer la visite', 'btn-primary', null);
    const dismissBtn = btn('Plus tard', 'btn-ghost btn-sm', null);
    dismissBtn.addEventListener('click', () => {
      try { localStorage.setItem('nebula-tour-completed', '1'); } catch {}
      banner.remove();
    });
    launchBtn.addEventListener('click', () => startTour('main'));
    const actions = el('div');
    actions.style.cssText = 'display:flex;gap:8px;margin-top:8px';
    actions.append(launchBtn, dismissBtn);
    banner.querySelector('div > div:last-child').appendChild(actions);
    page.appendChild(banner);
  }

  // Bandeau "Mise en route" si la checklist d'onboarding n'est pas à 100 %
  const quickstart = buildHomeQuickstart();
  if (quickstart) page.appendChild(quickstart);

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
      <div class="empty-title">Pas encore de workspace dans Nebula</div>
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
  right.appendChild(el('div', 'section-label', '<span class="num">B.</span> Sanity check'));
  const sanityCard = el('div', 'card sanity-card');
  sanityCard.innerHTML = `<div class="card-header"><h3 class="card-title">${I.shield} Sanity check</h3><button class="icon-btn" data-refresh aria-label="Rafraîchir">${I.refresh}</button></div>`;
  const sanityBody = el('div');
  sanityCard.appendChild(sanityBody);
  right.appendChild(sanityCard);
  loadSanity(sanityBody);
  sanityCard.querySelector('[data-refresh]').addEventListener('click', () => loadSanity(sanityBody));

  // Journal
  right.appendChild(el('div', 'section-label', '<span class="num">C.</span> Journal'));
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
      attachSessionPreview(row, wsId, s.file);
      host.appendChild(row);
    }
  } catch (e) {
    host.innerHTML = `<div class="error-box">${escapeHtml(e.message)}</div>`;
  }
}

// Cache des previews déjà fetched pour éviter les re-fetch (clé: `${wsId}:${file}`)
const _sessionPreviewCache = new Map();

function attachSessionPreview(row, wsId, file) {
  let timer = null;
  let tooltip = null;
  const cacheKey = `${wsId}:${file}`;

  const hide = () => {
    if (timer) { clearTimeout(timer); timer = null; }
    if (tooltip) { tooltip.remove(); tooltip = null; }
  };

  const showTooltip = (messages) => {
    if (tooltip) tooltip.remove();
    tooltip = el('div', 'session-preview-tooltip');
    if (!messages || !messages.length) {
      tooltip.innerHTML = '<div class="dim">(aucun message)</div>';
    } else {
      const items = messages.slice(0, 3).map(m => {
        const role = m.role || m.type || '?';
        const text = String(m.text || m.content || '').slice(0, 220);
        const more = String(m.text || m.content || '').length > 220 ? '…' : '';
        const roleClass = role === 'user' ? 'preview-user' : role === 'assistant' ? 'preview-assistant' : 'preview-other';
        return `<div class="preview-msg ${roleClass}">
          <div class="preview-role">${escapeHtml(role)}</div>
          <div class="preview-text">${escapeHtml(text)}${more}</div>
        </div>`;
      }).join('');
      const total = messages.length;
      tooltip.innerHTML = `${items}${total > 3 ? `<div class="preview-more">+${total - 3} message(s) — clic pour ouvrir</div>` : ''}`;
    }
    document.body.appendChild(tooltip);
    // Position : à droite de la row si possible, sinon à gauche
    const r = row.getBoundingClientRect();
    const tw = 380;
    const left = (r.right + tw + 16 < window.innerWidth) ? r.right + 8 : Math.max(8, r.left - tw - 8);
    tooltip.style.left = `${left}px`;
    tooltip.style.top = `${Math.max(8, Math.min(window.innerHeight - 200, r.top))}px`;
  };

  row.addEventListener('mouseenter', () => {
    timer = registerPageTimeout(setTimeout(async () => {
      if (!row.isConnected) return;  // garde-fou : navigation entretemps
      if (_sessionPreviewCache.has(cacheKey)) {
        showTooltip(_sessionPreviewCache.get(cacheKey));
        return;
      }
      try {
        const r = await API.get(`/api/workspaces/${wsId}/sessions/${file}`);
        if (!row.isConnected) return;
        const msgs = r.messages || [];
        _sessionPreviewCache.set(cacheKey, msgs);
        showTooltip(msgs);
      } catch { /* silencieux : pas de tooltip si erreur réseau */ }
    }, 500));
  });
  row.addEventListener('mouseleave', hide);
  row.addEventListener('click', hide);  // hide avant d'ouvrir le modal
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
    // Action bar : ajouter depuis le magasin
    const actionBar = el('div');
    actionBar.style.cssText = 'display:flex;justify-content:flex-end;margin-bottom:8px';
    const addFromLibrary = btn('+ Ajouter depuis le magasin', 'btn-sm btn-primary', '📚');
    addFromLibrary.addEventListener('click', () => modalAddSkillFromLibrary(wsId));
    actionBar.appendChild(addFromLibrary);
    host.appendChild(actionBar);
    if (!local.length && !global.length) {
      host.appendChild(el('div', 'dim', '<span style="font-size:12.5px">Aucun skill installé. Clique « Ajouter depuis le magasin » pour en piocher dans la bibliothèque.</span>'));
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
  const recipesBtn = btn('Recettes', 'btn', I.sparkle);
  recipesBtn.title = 'Catalogue de MCPs populaires pré-configurés';
  recipesBtn.addEventListener('click', () => modalMcpRecipes());
  setTopbarActions([recipesBtn, importBtn, newBtn]);

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

  // Bandeau .env.local manquant si des MCPs utilisent ${VAR}
  const usesInterpolation = (STATE.mcps || []).some(m => {
    const fields = [m.command || '', (m.args || []).join(' '), m.url || '',
                    Object.entries(m.env || {}).map(([k, v]) => `${k}=${v}`).join(' '),
                    Object.entries(m.headers || {}).map(([k, v]) => `${k}=${v}`).join(' '),
                    m.cwd || ''];
    return fields.some(s => /\$\{[A-Z0-9_]+\}/.test(s));
  });
  if (usesInterpolation && !STATE.envExists) {
    const envBanner = el('div', 'callout callout-warn');
    envBanner.style.cssText = 'margin-bottom:var(--sp-3);display:flex;align-items:center;gap:12px;flex-wrap:wrap';
    envBanner.innerHTML = `
      <div style="font-size:24px">⚠</div>
      <div style="flex:1;min-width:240px">
        <strong>Tes MCPs utilisent <code class="mono">\${VAR}</code> mais <code class="mono">.env.local</code> n'existe pas</strong>
        <p style="margin:4px 0 0;font-size:12.5px">Les variables ne seront pas substituées et les MCPs vont planter à la sync. Crée <code class="mono">.env.local</code> à la racine et ajoute tes secrets.</p>
      </div>
    `;
    const goEnv = btn('Configurer .env.local', 'btn-sm btn-primary', I.key);
    goEnv.addEventListener('click', () => { location.hash = '#/tools'; });
    envBanner.appendChild(goEnv);
    page.appendChild(envBanner);
  }

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
          <span class="dim">${(r.conflicts || []).length} doublon(s) avec le registre Nebula · ${(r.orphans || []).length} orphelin(s) à migrer</span>
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

  // Auto-refresh des MCPs toutes les 30s tant que la page est active.
  // Le poller est nettoyé automatiquement via clearPagePollers() au changement de page.
  const liveDot = el('span', 'live-dot');
  liveDot.title = 'Auto-refresh actif (toutes les 30s)';
  liveDot.style.cssText = 'display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--success,#10b981);margin-left:8px;vertical-align:middle;animation:pulse 2s ease-in-out infinite';
  const eyebrow = page.querySelector('.page-eyebrow');
  if (eyebrow) eyebrow.appendChild(liveDot);

  const pollerId = setInterval(async () => {
    try {
      const r = await API.get('/api/mcps');
      const next = r.mcps || [];
      // Re-render seulement si le contenu a changé (évite reflow inutile)
      if (JSON.stringify(next) !== JSON.stringify(STATE.mcps)) {
        STATE.mcps = next;
        renderList();
      }
    } catch { /* silencieux : un blip réseau ne doit pas spammer */ }
  }, 30000);
  registerPagePoller(pollerId);

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
  const ed = btn('Modifier', 'btn-sm btn-ghost', I.edit);
  ed.addEventListener('click', () => modalNewMCP(m));
  const rm = btn('', 'btn-sm btn-ghost btn-icon-only btn-danger', I.trash);
  rm.title = 'Supprimer';
  rm.addEventListener('click', () => confirmDialog(`Supprimer ${m.id} ?`, async () => {
    try { await API.del(`/api/mcps/${m.id}`); toastOk('Supprimé'); STATE.loading = true; route(); }
    catch (e) { toastErr(e.message); }
  }, { danger: true }));
  footer.append(ed, rm);
  card.appendChild(footer);
  return card;
}

// ── Recettes MCP : catalogue 1-clic ──────────────────────────────────────────
async function modalMcpRecipes() {
  const body = el('div');
  body.innerHTML = `<div class="page-loader"><div class="spinner"></div><span>Chargement…</span></div>`;
  const close = btn('Fermer', 'btn-ghost');
  const { close: doClose } = openModal({
    title: 'Recettes MCP — installation 1-clic', body, footer: close, wide: true,
  });
  close.addEventListener('click', doClose);

  let data;
  try { data = await API.get('/api/mcps/recipes'); }
  catch (e) {
    body.innerHTML = `<div class="error-box">${escapeHtml(e.message)}</div>`;
    return;
  }
  const recipes = data.recipes || [];
  const publicRecipes = recipes.filter(r => r.source !== 'local');
  const localRecipes = recipes.filter(r => r.source === 'local');
  const existingIds = new Set((STATE.mcps || []).map(m => m.id));

  body.innerHTML = '';

  // Bandeau d'aide
  const intro = el('div');
  intro.style.cssText = 'margin:0 0 var(--sp-3) 0;font-size:13px;color:var(--text-muted)';
  intro.innerHTML = `
    Sélection de MCPs pré-configurés. Clique pour installer en remplissant les paramètres requis (token, chemin…).<br>
    <span style="font-size:12px">Tu peux ajouter tes propres recettes locales (gitignored) via le bouton ci-dessous.</span>
  `;
  body.appendChild(intro);

  // Bandeau "Recettes locales" (toujours visible avec bouton)
  const localBar = el('div', 'recipes-local-bar');
  localBar.innerHTML = `
    <div>
      <div style="font-size:12px;font-weight:500">📝 Mes recettes locales</div>
      <div class="dim" style="font-size:11px">${localRecipes.length} recette(s) dans <code class="mono" style="font-size:11px">dashboard/data/mcp_recipes.local.json</code> (gitignored)</div>
    </div>
  `;
  const newLocalBtn = btn('+ Nouvelle recette', 'btn-sm btn-primary', I.plus);
  newLocalBtn.title = 'Créer une recette locale via formulaire (gitignored)';
  newLocalBtn.addEventListener('click', () => {
    doClose();
    modalEditRecipe(null);
  });
  const editLocalBtn = btn('Ouvrir JSON brut', 'btn-sm btn-ghost', I.edit || I.code);
  editLocalBtn.title = 'Éditer mcp_recipes.local.json directement (avancé)';
  localBar.append(newLocalBtn, editLocalBtn);
  body.appendChild(localBar);

  const openLocalFile = async () => {
    try {
      if (!data.local_file_exists) {
        await API.post('/api/mcps/recipes/ensure-local', {});
        toastOk('Fichier créé avec un template (OPNsense en exemple)');
      }
      const r = await API.post('/api/open', { target: 'mcp-recipes-local' });
      if (r.message) toastOk(r.message);
    } catch (e) { toastErr(e.message); }
  };
  // Branche le bouton du bandeau (défini plus haut) sur openLocalFile
  editLocalBtn.addEventListener('click', openLocalFile);

  const renderSection = (title, list) => {
    if (!list.length) return;
    const isLocal = list[0].source === 'local';
    const label = el('div', 'section-label');
    label.style.cssText = 'margin-top:var(--sp-3);margin-bottom:var(--sp-2)';
    label.innerHTML = `<span class="num">${isLocal ? '🔒' : '📦'}</span> ${title} <span class="right" style="color:var(--text-muted);font-weight:400">${list.length} recette${list.length > 1 ? 's' : ''}</span>`;
    body.appendChild(label);

    const grid = el('div', 'recipes-grid');
    for (const r of list) {
      // Compte combien d'instances de cette recette sont déjà installées
      // (recettes = templates : on peut en créer plusieurs avec des creds différents)
      const instances = (STATE.mcps || []).filter(m =>
        m.id === r.id || m.id.startsWith(r.id + '-')
      ).length;
      const card = el('div', 'recipe-card' + (isLocal ? ' is-local' : ''));
      const paramCount = (r.params || []).length;
      card.innerHTML = `
        ${isLocal ? '<button class="recipe-edit-btn" type="button" title="Éditer la définition de cette recette">✎</button><button class="recipe-delete-btn" type="button" title="Supprimer cette recette locale">🗑</button>' : ''}
        <div class="recipe-emoji">${escapeHtml(r.emoji || '🔌')}</div>
        <div class="recipe-body">
          <div class="recipe-name">${escapeHtml(r.name)}${instances > 0 ? ` <span class="badge badge-info" style="margin-left:6px" title="Tu as déjà ${instances} instance(s) de cette recette installée(s)">${instances}× installée${instances > 1 ? 's' : ''}</span>` : ''}</div>
          <div class="recipe-desc">${escapeHtml(r.description || '')}</div>
          <div class="recipe-meta">
            <span class="badge">${escapeHtml(r.transport || 'stdio')}</span>
            ${paramCount > 0 ? `<span class="badge badge-info">${paramCount} param${paramCount > 1 ? 's' : ''} requis</span>` : '<span class="badge badge-ok">prêt à l\'emploi</span>'}
            ${safeUrl(r.docs_url) ? `<a class="badge" href="${escapeHtml(safeUrl(r.docs_url))}" target="_blank" rel="noopener" onclick="event.stopPropagation()">docs ↗</a>` : ''}
          </div>
        </div>
      `;
      // Bouton édition (recettes locales uniquement) — ouvre l'éditeur GUI
      const editBtn = card.querySelector('.recipe-edit-btn');
      if (editBtn) {
        editBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          doClose();
          modalEditRecipe(r);
        });
      }
      // Bouton suppression rapide (recettes locales) — confirm direct
      const delBtn = card.querySelector('.recipe-delete-btn');
      if (delBtn) {
        delBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          confirmDialog(`Supprimer la recette « ${r.name || r.id} » ?`, async () => {
            try {
              await API.del(`/api/mcps/recipes/local/${r.id}`);
              toastOk(`Recette '${r.id}' supprimée`);
              doClose();
              modalMcpRecipes();
            } catch (err) { toastErr(err.message); }
          }, { danger: true });
        });
      }
      // Click sur la carte → install (toujours actif, même si déjà installé une fois)
      // L'install modal proposera un id auto-suffixé (ex: opnsense-2) pour 2e instance
      card.style.cursor = 'pointer';
      card.addEventListener('click', () => {
        doClose();
        modalInstallRecipe(r);
      });
      grid.appendChild(card);
    }
    body.appendChild(grid);
  };

  renderSection('Recettes Nebula (catalogue public)', publicRecipes);
  renderSection('Recettes locales (perso, non partagées)', localRecipes);
}

function modalInstallRecipe(recipe) {
  const body = el('div');
  const params = recipe.params || [];

  // Substitue ${KEY} dans une string par values[KEY] ; supporte plusieurs occurences
  const substitute = (s, values) =>
    String(s).replace(/\$\{([A-Z0-9_]+)\}/g, (_, k) => values[k] !== undefined ? values[k] : `\${${k}}`);

  // Calcule un id pré-suggéré : auto-suffix si la base est déjà prise.
  // Permet d'installer la même recette N fois (ex: 2 firewalls OPNsense).
  const existingIds = new Set((STATE.mcps || []).map(m => m.id));
  const instances = [...existingIds].filter(id => id === recipe.id || id.startsWith(recipe.id + '-')).length;
  let suggestedId = recipe.id;
  if (existingIds.has(suggestedId)) {
    let n = 2;
    while (existingIds.has(`${recipe.id}-${n}`)) n++;
    suggestedId = `${recipe.id}-${n}`;
  }

  body.innerHTML = `
    <div style="display:flex;align-items:center;gap:var(--sp-3);margin-bottom:var(--sp-3)">
      <div style="font-size:32px">${escapeHtml(recipe.emoji || '🔌')}</div>
      <div>
        <div style="font-size:15px;font-weight:600">${escapeHtml(recipe.name)}</div>
        <div class="dim" style="font-size:12px">${escapeHtml(recipe.description || '')}</div>
        ${instances > 0 ? `<div style="font-size:11px;color:var(--info);margin-top:4px">ℹ ${instances} instance(s) déjà installée(s) — un nouvel ID est suggéré ci-dessous</div>` : ''}
      </div>
    </div>
    <div class="field">
      <label class="field-label">ID dans Nebula</label>
      <input class="input mono" name="mcp_id" value="${escapeHtml(suggestedId)}" autocomplete="off">
      <div class="dim" style="font-size:11px;margin-top:4px">Tu peux personnaliser pour distinguer (ex: <code class="mono">opnsense-prod</code>, <code class="mono">opnsense-dev</code>). Auto-suffix si l'ID est déjà pris.</div>
    </div>
  `;

  // Champs des params
  for (const p of params) {
    const field = el('div', 'field');
    field.innerHTML = `
      <label class="field-label">${escapeHtml(p.label)}${p.required ? ' <span style="color:var(--err)">*</span>' : ''}</label>
      <input class="input ${p.secret ? '' : 'mono'}"
             name="param_${escapeHtml(p.key)}"
             type="${p.secret ? 'password' : 'text'}"
             placeholder="${escapeHtml(p.placeholder || '')}"
             autocomplete="off">
      ${p.help ? `<div class="dim" style="font-size:11px;margin-top:4px">${escapeHtml(p.help)}</div>` : ''}
    `;
    body.appendChild(field);
  }

  // Aperçu de la commande finale (réactif)
  const previewBox = el('div', 'recipe-preview');
  previewBox.innerHTML = `<div class="dim" style="font-size:11px;margin-bottom:4px">Commande générée :</div><code class="mono"></code>`;
  body.appendChild(previewBox);

  const updatePreview = () => {
    // Pour la preview, on masque les valeurs des params marqués `secret: true`
    // (le token finit dans le registre en clair, mais ne pas le montrer à l'écran
    //  évite les fuites par capture d'écran ou démo en partage écran).
    const displayValues = {};
    for (const p of params) {
      const v = body.querySelector(`[name=param_${p.key}]`).value;
      if (!v) {
        displayValues[p.key] = `\${${p.key}}`;
      } else if (p.secret) {
        displayValues[p.key] = '••••••••';
      } else {
        displayValues[p.key] = v;
      }
    }
    const cmd = recipe.command + (recipe.args && recipe.args.length ? ' ' + recipe.args.map(a => substitute(a, displayValues)).join(' ') : '');
    const envSummary = Object.entries(recipe.env || {})
      .map(([k, v]) => `${k}=${substitute(v, displayValues)}`)
      .join(' ');
    previewBox.querySelector('code').textContent = cmd + (envSummary ? `\n\n# env\n${envSummary}` : '');
  };
  body.querySelectorAll('input').forEach(i => i.addEventListener('input', updatePreview));
  updatePreview();

  const cancel = btn('Annuler', 'btn-ghost');
  const install = btn('Installer', 'btn-primary', I.plus);
  const { close } = openModal({
    title: `Installer « ${recipe.name} »`, body, footer: [cancel, install],
  });
  cancel.addEventListener('click', close);
  install.addEventListener('click', async () => {
    // Validation params requis
    const values = {};
    for (const p of params) {
      const v = body.querySelector(`[name=param_${p.key}]`).value.trim();
      if (p.required && !v) { toastErr(`Champ requis : ${p.label}`); return; }
      values[p.key] = v;
    }
    const mcpId = body.querySelector('[name=mcp_id]').value.trim() || recipe.id;
    // Auto-suffix si l'id existe déjà
    let finalId = mcpId;
    let suffix = 2;
    const existing = new Set((STATE.mcps || []).map(m => m.id));
    while (existing.has(finalId)) { finalId = `${mcpId}-${suffix++}`; }

    // Construction de la payload avec substitution
    const env = {};
    for (const [k, v] of Object.entries(recipe.env || {})) env[k] = substitute(v, values);

    const payload = {
      id: finalId,
      name: recipe.name,
      description: recipe.description || '',
      transport: recipe.transport || 'stdio',
      command: substitute(recipe.command || '', values),
      args: (recipe.args || []).map(a => substitute(a, values)),
      env,
      cwd: '',
      url: '',
      headers: {},
      workspaces: [],
      status: 'disponible',
    };
    install.disabled = true;
    try {
      await API.post('/api/mcps', payload);
      toastOk(`MCP « ${finalId} » installé depuis la recette`);
      close();
      STATE.loading = true;
      route();
    } catch (e) {
      toastErr(e.message);
      install.disabled = false;
    }
  });
}

// Convertit un MCP du registre en template de recette locale.
// Heuristique : chaque env var devient un param ${KEY}, secret=true si le nom
// suggère un secret (token/key/secret/password/auth/credential).
function mcpToRecipeTemplate(mcp) {
  const SECRET_RX = /token|key|secret|password|auth|credential|api_?key|bearer/i;
  const params = [];
  const env = {};
  for (const [k, v] of Object.entries(mcp.env || {})) {
    params.push({
      key: k,
      label: k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
      placeholder: '',
      required: true,
      secret: SECRET_RX.test(k),
    });
    env[k] = `\${${k}}`;
  }
  return {
    id: mcp.id,
    name: mcp.name || mcp.id,
    emoji: mcp.emoji || '🔌',
    description: mcp.description || '',
    transport: mcp.transport || 'stdio',
    command: mcp.command || '',
    args: mcp.args || [],
    url: mcp.url || '',
    env,
    params,
    docs_url: '',
  };
}

function modalSaveAsRecipe(mcp) {
  const template = mcpToRecipeTemplate(mcp);
  // Ouvre l'éditeur en mode "création depuis MCP" : id éditable, pas de delete
  modalEditRecipe(template, { fromMcp: true, sourceMcpId: mcp.id });
}

// ── Éditeur GUI de recette locale ────────────────────────────────────────────
function modalEditRecipe(existing, opts = {}) {
  const fromMcp = !!opts.fromMcp;
  // En mode fromMcp, on est techniquement en CRÉATION (pas d'édition d'une
  // recette qui existerait déjà). Donc on déverrouille l'id.
  const isEdit = !!existing && !fromMcp;
  const r = existing ? JSON.parse(JSON.stringify(existing)) : {
    id: '', name: '', emoji: '🔌', description: '',
    transport: 'stdio', command: '', args: [], env: {}, url: '',
    params: [], docs_url: '',
  };

  const body = el('div');
  body.innerHTML = `
    ${fromMcp ? `
      <div class="callout callout-info" style="margin-bottom:var(--sp-3)">
        <div>
          <strong>📋 Conversion MCP → recette</strong>
          <p style="margin:4px 0 0;font-size:12px">
            Chaque variable d'env de ton MCP a été convertie en paramètre <code class="mono">\${KEY}</code>.
            Les noms suggérant un secret (token, key, password…) sont marqués <code class="mono">secret: true</code>.
            <strong>Vérifie/ajuste</strong> les params ci-dessous avant de sauver.
            ${r.id ? `Si tu gardes l'id <code class="mono">${escapeHtml(r.id)}</code>, ça écrasera une recette locale homonyme existante (sinon utilise un id différent).` : ''}
          </p>
        </div>
      </div>
    ` : ''}
    <div class="field-row">
      <div class="field" style="max-width:80px"><label class="field-label">Emoji</label><input class="input" name="emoji" value="${escapeHtml(r.emoji || '🔌')}" maxlength="4"></div>
      <div class="field" style="flex:1"><label class="field-label">ID *</label><input class="input mono" name="id" value="${escapeHtml(r.id)}" placeholder="mon-mcp" autocomplete="off" ${isEdit ? 'disabled' : ''}></div>
      <div class="field" style="flex:2"><label class="field-label">Nom</label><input class="input" name="name" value="${escapeHtml(r.name || '')}" placeholder="Mon MCP"></div>
    </div>
    <div class="field"><label class="field-label">Description</label><textarea class="textarea" name="description" rows="2" placeholder="À quoi sert ce MCP">${escapeHtml(r.description || '')}</textarea></div>
    <div class="field-row">
      <div class="field"><label class="field-label">Transport</label>
        <select class="select" name="transport">
          <option value="stdio" ${r.transport === 'stdio' ? 'selected' : ''}>stdio</option>
          <option value="http" ${r.transport === 'http' ? 'selected' : ''}>http</option>
          <option value="sse" ${r.transport === 'sse' ? 'selected' : ''}>sse</option>
        </select>
      </div>
      <div class="field" style="flex:2"><label class="field-label">Documentation (URL)</label><input class="input" name="docs_url" value="${escapeHtml(r.docs_url || '')}" placeholder="https://github.com/..."></div>
    </div>
    <div data-stdio>
      <div class="field"><label class="field-label">Command *</label><input class="input mono" name="command" value="${escapeHtml(r.command || '')}" placeholder="npx ou uvx"></div>
      <div class="field"><label class="field-label">Args (un par ligne) <span class="dim">— supporte <code class="mono">\${KEY}</code></span></label><textarea class="textarea mono" name="args" rows="3" placeholder="-y&#10;@scope/mcp-server&#10;\${PATH}">${escapeHtml((r.args || []).join('\n'))}</textarea></div>
    </div>
    <div data-http hidden>
      <div class="field"><label class="field-label">URL *</label><input class="input mono" name="url" value="${escapeHtml(r.url || '')}" placeholder="https://api.example.com/mcp"></div>
    </div>
    <div class="field"><label class="field-label">Env <span class="dim">— KEY=VALUE par ligne, supporte <code class="mono">\${KEY}</code></span></label><textarea class="textarea mono" name="env" rows="3" placeholder="API_KEY=\${TOKEN}&#10;DEBUG=1">${escapeHtml(Object.entries(r.env || {}).map(([k,v]) => `${k}=${v}`).join('\n'))}</textarea></div>

    <div class="section-label" style="margin-top:var(--sp-3);margin-bottom:var(--sp-2)"><span class="num">⚙</span> Paramètres demandés à l'install</div>
    <p class="dim" style="font-size:11.5px;margin:0 0 var(--sp-2) 0">Pour chaque <code class="mono">\${KEY}</code> utilisé dans command/args/env, déclare ici un param. L'utilisateur saisira sa valeur lors de l'install.</p>
    <div class="recipe-params-list" data-params></div>
    <button type="button" class="btn btn-sm btn-ghost" data-add-param style="margin-top:var(--sp-2)">+ Ajouter un paramètre</button>
  `;

  // Toggle stdio/http/sse
  const updateTransport = () => {
    const t = body.querySelector('[name=transport]').value;
    body.querySelectorAll('[data-stdio]').forEach(e => e.hidden = t !== 'stdio');
    body.querySelectorAll('[data-http]').forEach(e => e.hidden = t === 'stdio');
  };
  body.querySelector('[name=transport]').addEventListener('change', updateTransport);
  updateTransport();

  // Liste dynamique de params
  const paramsHost = body.querySelector('[data-params]');
  const renderParam = (p = { key: '', label: '', placeholder: '', required: false, secret: false, help: '' }) => {
    const row = el('div', 'recipe-param-row');
    row.innerHTML = `
      <input class="input mono" data-pk="key"         placeholder="KEY"            value="${escapeHtml(p.key || '')}">
      <input class="input"      data-pk="label"       placeholder="Label affiché"  value="${escapeHtml(p.label || '')}">
      <input class="input"      data-pk="placeholder" placeholder="Exemple"        value="${escapeHtml(p.placeholder || '')}">
      <label class="ws-check" style="padding:4px 8px;margin:0"><input type="checkbox" data-pk="required" ${p.required ? 'checked' : ''}> <span>requis</span></label>
      <label class="ws-check" style="padding:4px 8px;margin:0"><input type="checkbox" data-pk="secret" ${p.secret ? 'checked' : ''}> <span>secret</span></label>
      <button type="button" class="btn btn-sm btn-ghost btn-icon-only btn-danger" data-remove-param title="Retirer">✗</button>
    `;
    row.querySelector('[data-remove-param]').addEventListener('click', () => row.remove());
    paramsHost.appendChild(row);
  };
  for (const p of (r.params || [])) renderParam(p);
  body.querySelector('[data-add-param]').addEventListener('click', () => renderParam());

  // Footer : Save + Delete (si edit) + Cancel
  const cancel = btn('Annuler', 'btn-ghost');
  const save = btn(isEdit ? 'Enregistrer' : 'Créer la recette', 'btn-primary', I.check || I.plus);
  const footer = [cancel];
  if (isEdit) {
    const del = btn('Supprimer', 'btn-ghost btn-danger', I.trash);
    del.title = 'Supprimer cette recette locale';
    del.addEventListener('click', () => {
      confirmDialog(`Supprimer la recette « ${r.name || r.id} » ?`, async () => {
        try {
          await API.del(`/api/mcps/recipes/local/${r.id}`);
          toastOk(`Recette '${r.id}' supprimée`);
          close();
          // Reload + ré-ouvre le catalog
          STATE.loading = true;
          await route();
          modalMcpRecipes();
        } catch (e) { toastErr(e.message); }
      }, { danger: true });
    });
    footer.push(del);
  }
  footer.push(save);

  const { close } = openModal({
    title: isEdit
      ? `Modifier la recette « ${r.name || r.id} »`
      : (fromMcp ? `Sauver « ${opts.sourceMcpId} » comme recette` : 'Nouvelle recette locale'),
    body, footer, wide: true,
  });
  cancel.addEventListener('click', close);

  save.addEventListener('click', async () => {
    const get = (n) => body.querySelector(`[name=${n}]`).value.trim();
    const id = get('id') || r.id;
    if (!/^[a-zA-Z0-9_-]{1,40}$/.test(id)) {
      toastErr('ID invalide (alphanumérique + - _ uniquement, max 40)'); return;
    }
    const transport = get('transport');
    // Parse env KEY=VALUE
    const env = {};
    for (const line of get('env').split('\n').map(s => s.trim()).filter(Boolean)) {
      const idx = line.indexOf('=');
      if (idx > 0) env[line.slice(0, idx).trim()] = line.slice(idx + 1).trim();
    }
    // Parse params (lit chaque row)
    const params = [];
    for (const row of paramsHost.querySelectorAll('.recipe-param-row')) {
      const pk = (k) => row.querySelector(`[data-pk=${k}]`).value;
      const k = pk('key').trim();
      const lbl = pk('label').trim();
      if (!k || !lbl) continue;  // skip ligne incomplète
      params.push({
        key: k,
        label: lbl,
        placeholder: pk('placeholder').trim(),
        required: row.querySelector('[data-pk=required]').checked,
        secret: row.querySelector('[data-pk=secret]').checked,
      });
    }

    const payload = {
      id,
      name: get('name') || id,
      emoji: get('emoji') || '🔌',
      description: get('description'),
      transport,
      command: transport === 'stdio' ? get('command') : '',
      args: transport === 'stdio' ? get('args').split('\n').map(s => s.trim()).filter(Boolean) : [],
      url: transport !== 'stdio' ? get('url') : '',
      env,
      params,
      docs_url: get('docs_url'),
    };

    save.disabled = true;
    try {
      const resp = await API.post('/api/mcps/recipes/local', payload);
      toastOk(resp.action === 'created' ? `Recette '${id}' créée` : `Recette '${id}' mise à jour`);
      close();
      // Re-fetch + re-ouvre la modal de catalogue
      modalMcpRecipes();
    } catch (e) {
      toastErr(e.message);
      save.disabled = false;
    }
  });
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
      <div class="field">
        <label class="field-label">Workspaces ciblés <span class="dim" style="font-weight:400">— où ce MCP doit être disponible</span></label>
        <div class="ws-checklist" data-name="workspaces"></div>
      </div>
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

  // Construit la liste de checkboxes pour les workspaces ciblés
  const wsHost = body.querySelector('[data-name=workspaces]');
  const currentWs = new Set(m.workspaces || []);
  const allWs = STATE.workspaces || [];
  const allChecked = currentWs.has('*');

  const wsAllLabel = el('label', 'ws-check ws-check-all');
  wsAllLabel.innerHTML = `<input type="checkbox" data-ws-all ${allChecked ? 'checked' : ''}>
    <span><strong>★ Tous les workspaces</strong> <span class="dim">(${allWs.length})</span></span>`;
  wsHost.appendChild(wsAllLabel);

  if (!allWs.length) {
    wsHost.appendChild(el('div', 'dim', '<small>Aucun workspace défini — crée-en un d\'abord.</small>'));
  }

  for (const w of allWs) {
    const lbl = el('label', 'ws-check');
    const checked = allChecked || currentWs.has(w.id);
    lbl.innerHTML = `<input type="checkbox" data-ws="${escapeHtml(w.id)}" ${checked ? 'checked' : ''} ${allChecked ? 'disabled' : ''}>
      <span>${w.emoji ? escapeHtml(w.emoji) + ' ' : ''}<strong>${escapeHtml(w.id)}</strong>${w.label && w.label !== w.id ? ` <span class="dim">— ${escapeHtml(w.label)}</span>` : ''}</span>`;
    wsHost.appendChild(lbl);
  }

  // Logique : "Tous" coché → désactive les autres ; un autre coché → décoche "Tous"
  const wsAllInput = wsHost.querySelector('[data-ws-all]');
  wsAllInput.addEventListener('change', () => {
    const isAll = wsAllInput.checked;
    wsHost.querySelectorAll('[data-ws]').forEach(cb => {
      cb.disabled = isAll;
      if (isAll) cb.checked = true;
    });
  });
  wsHost.querySelectorAll('[data-ws]').forEach(cb => {
    cb.addEventListener('change', () => {
      if (cb.checked && wsAllInput.checked) {
        // Si on décoche un workspace pendant que "Tous" est actif, désactive "Tous"
      }
      // Si tous les ws individuels sont cochés ET pas de "Tous", on laisse l'utilisateur décider
    });
  });
  for (const tab of body.querySelectorAll('.tab')) {
    tab.addEventListener('click', () => {
      body.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      body.querySelectorAll('[data-tab-body]').forEach(b => b.hidden = b.dataset.tabBody !== tab.dataset.tab);
    });
  }

  const cancel = btn('Annuler', 'btn-ghost');
  const save = btn(isEdit ? 'Mettre à jour' : 'Créer', 'btn-primary');
  const footer = [cancel];
  // En mode édition d'un MCP existant : bouton "Sauver comme recette"
  // permet de transformer une config qui marche en template réutilisable.
  if (isEdit) {
    const saveAsRecipe = btn('Sauver comme recette', 'btn-ghost', I.sparkle);
    saveAsRecipe.title = 'Crée une recette locale (template) à partir de ce MCP — réutilisable pour installer d\'autres instances avec d\'autres credentials';
    saveAsRecipe.addEventListener('click', () => {
      close();
      modalSaveAsRecipe(m);
    });
    footer.push(saveAsRecipe);
  }
  footer.push(save);
  const { close } = openModal({ title: isEdit ? `Modifier ${m.id}` : 'Nouveau MCP', body, footer, wide: true });
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
      // Lit les workspaces depuis les checkboxes : ["*"] si "Tous", sinon liste des ids cochés
      const wsHost = body.querySelector('[data-name=workspaces]');
      const wsAllChecked = wsHost.querySelector('[data-ws-all]')?.checked;
      const wsRaw = wsAllChecked
        ? ['*']
        : Array.from(wsHost.querySelectorAll('[data-ws]:checked')).map(cb => cb.dataset.ws);
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
      const resp = await API.post('/api/mcps', payload);
      // Affiche les workspaces synchronisés automatiquement (auto-sync backend)
      const synced = resp.synced || [];
      const verb = isEdit ? 'mis à jour' : 'créé';
      if (synced.length === 0) {
        toastOk(`MCP ${verb}`);
      } else {
        toastOk(`MCP ${verb} et synchronisé vers ${synced.length} workspace(s) : ${synced.slice(0, 3).join(', ')}${synced.length > 3 ? '…' : ''}`);
      }
      close(); STATE.loading = true; route();
    } catch (e) { toastErr(e.message); }
  });
}

/* ================================================================
   FIRST-RUN WIZARD — assistant de premier lancement
   ================================================================ */
function markOnboarded() {
  if (STATE.uiState) STATE.uiState.onboarded = true;
  API.post('/api/ui-state', { onboarded: true }).catch(() => {});
}
function resetOnboarded() {
  if (STATE.uiState) STATE.uiState.onboarded = false;
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
        <span class="brand-name">nebula</span>
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
      const done = btn('Commencer à utiliser Nebula', 'btn-primary', I.sparkle);
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
        <h1>Bienvenue dans Nebula</h1>
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
              ? ' Ce qui était dans ta config Claude est déjà connu d\'Nebula.'
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
          <p>Pointe Nebula vers un projet déjà sur ton disque, sans le déplacer.</p>
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
const UPDATE_CHECK_KEY = 'nebula-last-update-check';
const UPDATE_SESSION_FLAG = 'nebula-update-checked-this-session';
const UPDATE_CHECK_INTERVAL_MS = 60 * 60 * 1000;  // 1h

async function checkForUpdates({ force = false } = {}) {
  // 1ère ouverture de session (sessionStorage vide) → toujours forcer un fetch.
  // Ainsi un fermer/rouvrir d'onglet déclenche un check frais sans attendre l'intervalle.
  let firstOfSession = false;
  try {
    if (!sessionStorage.getItem(UPDATE_SESSION_FLAG)) {
      firstOfSession = true;
      sessionStorage.setItem(UPDATE_SESSION_FLAG, '1');
    }
  } catch { /* sessionStorage indispo */ }

  // Anti-spam : ne check le distant qu'une fois par UPDATE_CHECK_INTERVAL_MS
  let shouldCheckRemote = force || firstOfSession;
  if (!shouldCheckRemote) {
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
  // Nettoie les anciennes versions du badge (sidebar + topbar)
  const existingNav = $('#nav-update-badge');
  if (existingNav) existingNav.remove();
  const slot = $('#topbar-update-slot');
  if (slot) slot.innerHTML = '';

  if (!info || !info.is_git || !info.behind || info.behind <= 0) return;

  // Badge prominent dans le topbar (visible quelle que soit la page)
  if (slot) {
    const badge = el('button', 'topbar-update-badge');
    badge.type = 'button';
    badge.title = `Cliquer pour appliquer les ${info.behind} mise(s) à jour`;
    badge.innerHTML = `
      <span class="topbar-update-dot"></span>
      <span class="topbar-update-text">${info.behind} MAJ</span>
    `;
    badge.addEventListener('click', () => modalSystemUpdate());
    slot.appendChild(badge);
  }

  // Badge secondaire dans la sidebar footer (descriptif)
  const footer = $('.sidebar-footer');
  if (footer) {
    const navBadge = el('button', 'update-badge');
    navBadge.id = 'nav-update-badge';
    navBadge.type = 'button';
    navBadge.innerHTML = `
      <span class="update-badge-dot"></span>
      <span class="update-badge-text">${info.behind} mise${info.behind > 1 ? 's' : ''} à jour disponible${info.behind > 1 ? 's' : ''}</span>
      <span class="update-badge-icon">${I.right}</span>
    `;
    navBadge.addEventListener('click', () => modalSystemUpdate());
    footer.insertBefore(navBadge, footer.firstChild);
  }
}

async function modalSystemUpdate() {
  const body = el('div');
  body.innerHTML = `<div class="page-loader"><div class="spinner"></div><span>Vérification…</span></div>`;
  const closeBtn = btn('Fermer', 'btn-ghost');
  const { close } = openModal({ title: 'Mises à jour Nebula', body, footer: closeBtn, wide: true });
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
          <p style="margin:var(--sp-2) 0 0">Pour activer l'auto-update, ton install doit être un clone du repo officiel d'Nebula (le chemin importe peu — bureau, disque secondaire, etc.).</p>
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

  // Modifs locales : INFO seulement (auto-stash gère le pull). Plus jamais bloquant.
  if (info.dirty) {
    body.appendChild(el('div', 'callout callout-info', `
      <div>
        <strong>ℹ ${info.dirty_files.length}+ modification(s) locale(s)</strong> détectée(s).
        Nebula va automatiquement les <code class="mono">stash</code> avant le pull et les <code class="mono">pop</code> après — pas besoin de commit/stash manuel.
        <ul class="help-list" style="margin-top:6px">${info.dirty_files.slice(0, 6).map(f => `<li class="mono" style="font-size:11px">${escapeHtml(f)}</li>`).join('')}</ul>
      </div>
    `));
  }

  // Action button
  body.appendChild(el('div', 'callout callout-info', `
    <div>
      Nebula va exécuter <code class="mono">git pull --ff-only</code> (avec auto-stash si nécessaire). Tes données personnelles (registre, workspaces, .env.local) sont préservées via <code class="mono">.gitignore</code>.
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

      // Affiche un panneau d'erreur enrichi : hint + bouton reset si pertinent
      const errPanel = el('div', 'callout callout-warn');
      errPanel.style.marginTop = 'var(--sp-3)';
      errPanel.innerHTML = `
        <div>
          <strong>${escapeHtml(r.error || 'Échec')}</strong>
          ${r.hint ? `<p style="margin:var(--sp-2) 0 0">${escapeHtml(r.hint)}</p>` : ''}
          ${r.stash_applied ? '<p class="dim" style="margin:var(--sp-2) 0 0;font-size:11.5px">ℹ Tes modifs locales ont été stashées (préservées dans `git stash list`).</p>' : ''}
          ${r.stash_pop_warning ? `<p class="text-warn" style="margin:var(--sp-2) 0 0;font-size:11.5px">⚠ ${escapeHtml(r.stash_pop_warning)}</p>` : ''}
          ${(r.sensitive_in_stash || []).length ? `<p class="text-warn" style="margin:var(--sp-2) 0 0;font-size:11.5px">⚠ Fichiers sensibles dans le stash : ${r.sensitive_in_stash.map(escapeHtml).join(', ')} — vérifie avec <code class="mono">git stash list</code> si la restauration semble incomplète.</p>` : ''}
          ${r.stderr ? `<details style="margin-top:var(--sp-2)"><summary style="cursor:pointer;font-size:11px;color:var(--text-muted)">Détail technique</summary><pre class="mono" style="font-size:10.5px;background:var(--bg);padding:var(--sp-2);border-radius:4px;margin-top:6px;white-space:pre-wrap;max-height:160px;overflow:auto">${escapeHtml(r.stderr)}</pre></details>` : ''}
        </div>
      `;
      body.appendChild(errPanel);

      if (r.can_reset_to_upstream) {
        const resetBox = el('div');
        resetBox.style.cssText = 'margin-top:var(--sp-3);padding:var(--sp-3);background:var(--surface-2);border:1px dashed var(--border);border-radius:8px';
        resetBox.innerHTML = `
          <div style="font-size:12px;font-weight:500;margin-bottom:4px">🔄 Escape hatch : forcer l'alignement</div>
          <div class="dim" style="font-size:11.5px;margin-bottom:var(--sp-2)">
            Réinitialise ton dépôt local sur la version distante (<code class="mono">git reset --hard origin/main</code>).
            <strong>Tes modifs locales seront stashées</strong> (récupérables via <code class="mono">git stash pop</code>).
            Données utilisateur (registry, workspaces, .env.local) préservées via .gitignore.
          </div>
        `;
        const resetBtn = btn('Réinitialiser à la version distante', 'btn-sm btn-danger', I.refresh);
        resetBtn.addEventListener('click', () => {
          confirmDialog(
            'Forcer l\'alignement sur la version distante ? Tes modifs locales seront stashées (récupérables via `git stash pop` plus tard).',
            async () => {
              resetBtn.disabled = true;
              resetBtn.innerHTML = `<div class="spinner" style="width:12px;height:12px"></div><span>Reset en cours…</span>`;
              try {
                const rr = await API.post('/api/system/reset', {});
                if (!rr.ok) { toastErr(rr.error || 'Échec'); return; }
                toastOk(rr.message || 'Reset OK');
                // Reload page après reset (cas .py changé) ou refresh badge
                setTimeout(() => location.reload(), 1500);
              } catch (e) { toastErr(e.message); }
            },
            { danger: true }
          );
        });
        resetBox.appendChild(resetBtn);
        body.appendChild(resetBox);
      }
      return;
    }
    // Succès
    body.innerHTML = `
      <div class="callout" style="background:var(--ok-soft);border-color:rgba(52,211,153,0.3);border-left-color:var(--ok)">
        <div>
          ${I.check} <strong>Mise à jour appliquée</strong> · <span class="mono">${escapeHtml(r.from)}</span> → <span class="mono">${escapeHtml(r.to)}</span>
          <p style="margin:var(--sp-2) 0 0">${escapeHtml(r.message)}</p>
          ${r.stash_applied ? '<p class="dim" style="margin:var(--sp-2) 0 0;font-size:11.5px">ℹ Tes modifs locales ont été stashées puis re-appliquées automatiquement.</p>' : ''}
          ${r.stash_pop_warning ? `<p class="text-warn" style="margin:var(--sp-2) 0 0;font-size:11.5px">⚠ ${escapeHtml(r.stash_pop_warning)}</p>` : ''}
          ${(r.sensitive_in_stash || []).length ? `<p class="text-warn" style="margin:var(--sp-2) 0 0;font-size:11.5px">⚠ Fichiers sensibles dans le stash : ${r.sensitive_in_stash.map(escapeHtml).join(', ')} — vérifie avec <code class="mono">git stash list</code> si la restauration semble incomplète.</p>` : ''}
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
        Les MCPs déclarés dans <code class="mono">~/.claude.json</code> ou <code class="mono">~/.claude/settings.json</code> sont actifs <strong>globalement</strong>, partout. Si Nebula en sync un avec le même nom dans un workspace, Claude Code voit la définition deux fois (project &gt; user). Ça marche, mais tu peux te retrouver avec une vieille version qui traîne.
      </div>
    `));

    // ─── Section CONFLITS (même ID dans les deux) ───
    const conflicts = data.conflicts || [];
    body.appendChild(el('div', 'section-label', `<span class="num">A.</span> Doublons (${conflicts.length})`));

    if (!conflicts.length) {
      body.appendChild(el('div', 'callout', `<div>${I.check} Aucun doublon : ton registre Nebula et ta config Claude globale sont disjoints.</div>`));
    } else {
      body.appendChild(el('p', 'muted', `<small>Ces MCPs sont présents dans Nebula <strong>et</strong> dans la config Claude globale. Tu peux les retirer de la config globale (Nebula reste la source de vérité) — un backup <code class="mono">.bak</code> est créé automatiquement.</small>`));
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
              Nebula : statut <strong>${escapeHtml(c.registry_status)}</strong>${c.registry_workspaces.length ? ` · scope <span class="mono">${c.registry_workspaces.map(escapeHtml).join(', ')}</span>` : ' · <span class="text-warn">aucun workspace ciblé</span>'}
            </div>
          </div>
        `;
        const removeBtn = btn('Retirer du global', 'btn-sm btn-danger', I.trash);
        removeBtn.title = `Retire ${c.id} de ${c.source_label}`;
        removeBtn.addEventListener('click', () => confirmDialog(
          `Retirer "${c.id}" de ${c.source_label} ? La définition reste dans le registre Nebula (un backup .bak est créé).`,
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

    // ─── Section ORPHELINS (dans Claude global mais pas dans Nebula) ───
    const orphans = data.orphans || [];
    body.appendChild(el('div', 'section-label', `<span class="num">B.</span> Orphelins (${orphans.length})`));

    if (!orphans.length) {
      body.appendChild(el('div', 'callout', `<div>${I.check} Aucun MCP global non géré par Nebula.</div>`));
    } else {
      body.appendChild(el('p', 'muted', `<small>Ces MCPs sont présents dans la config Claude globale mais Nebula ne les connaît pas. Tu peux les <strong>migrer</strong> vers Nebula (import + retrait de la source) ou simplement les <strong>retirer</strong> s'ils sont obsolètes.</small>`));
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
        migrate.title = 'Importer dans le registre Nebula puis retirer de la source';
        migrate.addEventListener('click', () => confirmDialog(
          `Migrer "${o.id}" vers Nebula ? Il sera importé dans le registre (sans workspace ciblé) et retiré de ${o.source_label}.`,
          async () => {
            try {
              await API.post('/api/mcps/conflicts/migrate', { id: o.id, source: o.source });
              toastOk(`${o.id} migré vers Nebula`);
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
    <p style="margin:0 0 var(--sp-2);font-size:13px">Le scan a trouvé <strong>${mcps.length}</strong> MCP(s) et <strong>${projects.length}</strong> projet(s) Claude Code. Coche ceux que tu veux importer dans Nebula.</p>
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
// ── Aide : contenu des sections (réutilisé par les sous-pages) ─────────────
function _helpSections() {
  return {
'overview': `
      <h2>${I.home}<span>Vue d'ensemble du dashboard</span></h2>
      <p>Nebula est un <strong>tableau de bord local</strong> qui pilote ton écosystème Claude Code : workspaces (projets), MCPs (serveurs Model Context Protocol), skills, plugins, templates et hooks. Tout est servi par un petit serveur Python sur <code class="mono">127.0.0.1:4777</code> — aucune donnée ne sort de ta machine.</p>
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

`,
'onboarding': `
      <h2>${I.download}<span>Premier lancement & import depuis Claude</span></h2>
      <p>Si tu utilises déjà Claude Code, Nebula peut <strong>récupérer ta config existante</strong> en un clic. Trois portes d'entrée :</p>
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
          <p>Pour pointer Nebula vers un projet déjà sur disque (sans le déplacer), utilise <em>Enregistrer un dossier</em>. Tu donnes l'ID, le label et le chemin absolu — aucun fichier n'est touché, juste un enregistrement dans <code class="mono">data/workspaces.json</code>.</p>
        </div>
      </div>
      <div class="help-step">
        <div class="help-step-num">3</div>
        <div>
          <h4>Coller du JSON MCP</h4>
          <p>Si tu as un bloc <code class="mono">{"mcpServers": {...}}</code> ou un objet MCP brut, colle-le via <strong>MCPs → Importer</strong>. Nebula détecte automatiquement le format.</p>
        </div>
      </div>
      <div class="callout callout-info">
        <strong>Bon à savoir :</strong> l'import ne touche jamais à <code class="mono">~/.claude/settings.json</code>. Nebula maintient son propre registre dans <code class="mono">mcp/registry.json</code> et distribue ensuite vers les <code class="mono">.mcp.json</code> de chaque workspace via <em>Sync</em>.
      </div>

`,
'workspaces': `
      <h2>${I.box}<span>Workspaces</span></h2>
      <h3>Créer un nouveau workspace</h3>
      <p>Bouton <em>Nouveau workspace</em> sur la Home (ou raccourci <kbd>n</kbd>). Tu fournis :</p>
      <ul class="help-list">
        <li><strong>ID</strong> — identifiant technique (a-z, 0-9, _, -). Sert de nom de dossier et de clé interne.</li>
        <li><strong>Label</strong> — libellé lisible affiché dans l'UI.</li>
        <li><strong>Emoji</strong> — pictogramme pour repérer visuellement le projet.</li>
        <li><strong>Description</strong> et <strong>Outils / contexte</strong> — utilisés comme placeholders dans le template.</li>
        <li><strong>Template</strong> — sélectionne un modèle parmi ceux de la page Templates.</li>
      </ul>
      <p>Nebula crée le dossier <code class="mono">workspaces/&lt;id&gt;/</code>, copie le template en remplaçant les placeholders, génère un <code class="mono">launch-&lt;id&gt;.bat</code> dans <code class="mono">scripts/</code>, et enregistre l'entrée.</p>

      <h3>Importer un dossier existant</h3>
      <p>Si ton projet est déjà ailleurs sur le disque (ex. <code class="mono">D:\\projets\\monapp</code>), utilise <em>+ Dossier</em> sur la Home. Aucun fichier n'est créé ni copié, juste un enregistrement.</p>

      <h3>Lancer Claude Code dans un workspace</h3>
      <p>Bouton <strong>Lancer</strong> ouvre une nouvelle console et exécute <code class="mono">claude</code> dans le dossier. <strong>Reprendre</strong> fait <code class="mono">claude -c</code> pour continuer la dernière session.</p>

      <h3>Page détail d'un workspace</h3>
      <p>Clique sur une carte workspace pour voir : statistiques (sessions, tokens consommés), MCPs scopés, skills locaux, plugins overridés, agents/commandes, et accès rapide aux fichiers de config (<code class="mono">CLAUDE.md</code>, <code class="mono">settings.json</code>, permissions, hooks).</p>

      <div class="callout callout-warn">
        <strong>Suppression :</strong> par défaut, supprimer un workspace ne retire que l'enregistrement (le dossier reste sur disque). Coche <em>Supprimer aussi le dossier</em> pour purger physiquement — irréversible.
      </div>

`,
'mcps': `
      <h2>${I.cpu}<span>MCPs (Model Context Protocol)</span></h2>
      <p>Les MCPs sont des serveurs externes que Claude peut interroger pour accéder à des données ou fonctionnalités. Nebula centralise leur config dans un registre, puis les distribue aux workspaces.</p>

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

      <h3>Statut calculé automatiquement</h3>
      <p>Le statut affiché sur la card est dérivé de l'état réel à chaque rafraîchissement (toutes les 30s sur la page MCPs) :</p>
      <ul class="help-list">
        <li><strong>désactivé</strong> — choix manuel (case "Désactiver" dans Modifier).</li>
        <li><strong>à configurer</strong> — config incomplète (pas de command pour stdio, pas d'url pour http/sse).</li>
        <li><strong>disponible</strong> — config OK, prêt à fonctionner.</li>
      </ul>
      <p class="dim" style="font-size:12px">Le statut "connecté" demanderait un test live à chaque check (lourd). Utilise <em>Tester</em> ou <em>Diag</em> pour vérifier en réel.</p>

      <h3>Sauver une config MCP comme recette</h3>
      <p>Tu as configuré un MCP qui marche (HomeAssistant avec ton token, OPNsense avec creds firewall…) ? Tu peux le transformer en <strong>recette locale réutilisable</strong> :</p>
      <ol class="help-list">
        <li>Card MCP → <em>Modifier</em></li>
        <li>Footer du modal → bouton <strong>✨ Sauver comme recette</strong></li>
        <li>Conversion intelligente : chaque var d'env devient un param <code class="mono">\${KEY}</code>. Les noms suggérant un secret (TOKEN, KEY, SECRET, PASSWORD…) sont marqués <code class="mono">secret: true</code> automatiquement.</li>
        <li>Tu ajustes labels/placeholders → <em>Créer la recette</em></li>
      </ol>
      <p>Tu peux ensuite installer cette recette plusieurs fois avec d'autres credentials (cf section <a href="#h-recipes">Recettes</a>).</p>

      <h3>Vue JSON brut</h3>
      <p>L'onglet <em>JSON brut</em> de la modale te permet d'éditer toute la config en un coup, utile pour copier-coller depuis un README de MCP.</p>

      <h3>Workspaces ciblés (checkboxes)</h3>
      <p>Dans le formulaire MCP, le champ <em>Workspaces ciblés</em> liste tes workspaces existants en cases à cocher. Coche ceux qui doivent recevoir ce MCP. Case "★ Tous les workspaces" pour activer partout. <strong>Auto-sync</strong> : le <code class="mono">.mcp.json</code> de chaque workspace ciblé est régénéré immédiatement après le save (toast "MCP créé et synchronisé vers N workspace(s)").</p>

      <div class="callout callout-info">
        <strong>Le registre vs Claude :</strong> le fichier <code class="mono">mcp/registry.json</code> est la source de vérité d'Nebula. À chaque modif, Nebula régénère automatiquement les <code class="mono">.mcp.json</code> dans les workspaces concernés en interpolant les <code class="mono">\${VAR}</code>. Le bouton <em>Sync MCPs</em> sur un workspace n'est plus nécessaire dans le flow normal — utile uniquement pour forcer un re-sync (ex: après changement de <code class="mono">.env.local</code>).
      </div>

`,
'recipes': `
      <h2>${I.sparkle}<span>Recettes MCP — installation 1-clic</span></h2>
      <p>Les <strong>recettes</strong> sont des templates pré-configurés pour les MCPs courants. Plus besoin de chercher la commande, les args, la doc — tu cliques, tu remplis 2 champs, c'est installé.</p>

      <h3>Accès</h3>
      <p>Page <strong>MCPs → Recettes</strong> (bouton dans le topbar). Modale avec deux sections :</p>
      <ul class="help-list">
        <li><strong>📦 Recettes Nebula (catalogue public)</strong> — 8 recettes embarquées : Filesystem, GitHub, Brave Search, Fetch HTTP, Memory, Puppeteer, PostgreSQL, Slack. Mises à jour via auto-update du dashboard.</li>
        <li><strong>🔒 Recettes locales (perso, non partagées)</strong> — Tes recettes propres, stockées dans <code class="mono">dashboard/data/mcp_recipes.local.json</code> (gitignored). Parfait pour les MCPs privés ou propriétaires (OPNsense interne, BDD perso, etc.).</li>
      </ul>

      <h3>Installer une recette</h3>
      <p>Clic sur une carte → modale d'install avec :</p>
      <ul class="help-list">
        <li>ID auto-suggéré (auto-suffixé si déjà pris : <code class="mono">opnsense-2</code>, <code class="mono">opnsense-prod</code>…)</li>
        <li>Champs typés pour chaque param (text ou password selon <code class="mono">secret</code>)</li>
        <li><strong>Aperçu live</strong> de la commande générée — les secrets sont masqués <code class="mono">••••••••</code> à l'écran (sécurité capture)</li>
        <li>Aide contextuelle sous chaque champ + lien doc ↗</li>
      </ul>

      <h3>Recettes = templates réutilisables</h3>
      <p>Une recette n'est pas "à usage unique" — tu peux l'<strong>installer N fois</strong> avec des configs différentes. Ex : 2 firewalls OPNsense, 2 instances GitHub avec des tokens différents (perso/pro), 3 BDD PostgreSQL pour staging/prod/local. La carte affiche un badge <em>"Nx installées"</em>.</p>

      <h3>Créer une recette locale</h3>
      <p>Modale Recettes → bouton <strong>+ Nouvelle recette</strong> → éditeur GUI complet :</p>
      <ul class="help-list">
        <li>Métadonnées : id, nom, emoji, description, URL doc</li>
        <li>Transport (stdio/http/sse) avec champs adaptés</li>
        <li><strong>Liste dynamique de paramètres</strong> : chaque <code class="mono">\${KEY}</code> dans command/args/env doit avoir un param. Bouton <em>+ Ajouter un paramètre</em>, ✗ pour retirer. Cases <code class="mono">secret</code> et <code class="mono">required</code>.</li>
      </ul>

      <h3>Modifier / supprimer une recette locale</h3>
      <p>Sur la carte d'une recette locale → ✎ en haut à droite → ouvre l'éditeur. Bouton 🗑 dans le footer pour supprimer.</p>

      <h3>Workflow MCP existant → recette</h3>
      <p>Tu as déjà un MCP configuré qui marche ? Convertis-le en recette en 1 clic : <em>Modifier</em> sur la card MCP → bouton <strong>✨ Sauver comme recette</strong>. Conversion auto avec détection des secrets. Cf <a href="#h-mcps">section MCPs</a>.</p>

      <div class="callout callout-info">
        <strong>Avantage du modèle recette :</strong> tes recettes locales survivent aux <code class="mono">git pull</code> du dashboard (gitignored) et restent strictement sur ta machine. Le catalogue public, lui, est versionné et reçoit les updates Anthropic / nouveaux MCPs populaires automatiquement via auto-update.
      </div>

`,
'skills': `
      <h2>${I.sparkle}<span>Skills — modèle "magasin"</span></h2>
      <p>Un skill = un dossier contenant <code class="mono">SKILL.md</code> (frontmatter + instructions Markdown). Optionnellement des fichiers de référence (<code class="mono">references/</code>, <code class="mono">examples/</code>).</p>

      <h3>Bibliothèque centralisée (le magasin)</h3>
      <p>Nebula maintient une <strong>bibliothèque</strong> dans <code class="mono">dashboard/data/skills-library/</code> : c'est ta source de vérité, le magasin où tu pioches. La page Skills affiche cette bibliothèque, pas <code class="mono">~/.claude/skills/</code> directement.</p>
      <p>Pourquoi cette indirection : tu peux installer le même skill dans plusieurs workspaces (ex. <code class="mono">n8n-prod</code> + <code class="mono">n8n-dev</code>) avec une seule édition, sans copier-coller manuel.</p>

      <h3>Créer un skill</h3>
      <p>Bouton <strong>Nouveau skill</strong> en haut de la page Skills. Le skill est créé dans la bibliothèque uniquement — non distribué tant que tu n'utilises pas <em>Distribuer</em>.</p>

      <h3>Distribuer un skill</h3>
      <p>Bouton <strong>📤 Distribuer</strong> sur une carte → modal avec checkboxes :</p>
      <ul class="help-list">
        <li><strong>Global</strong> (<code class="mono">~/.claude/skills/&lt;name&gt;/</code>) — actif dans tous les projets</li>
        <li>Une ligne par <strong>workspace</strong> (<code class="mono">&lt;workspace&gt;/.claude/skills/&lt;name&gt;/</code>) — actif uniquement dans ce projet</li>
      </ul>
      <p>Coche pour installer/écraser, décoche pour retirer. C'est un <em>set complet</em> : tu modélises l'état désiré, Nebula ajoute/met à jour/retire en conséquence.</p>

      <h3>Importer depuis GitHub</h3>
      <p>Bouton <strong>📥 Importer GitHub</strong> → colle <code class="mono">user/repo</code> ou une URL complète, choisis la branche (optionnel) → Analyser. Nebula clone en shallow, détecte tous les <code class="mono">SKILL.md</code> du repo, et te laisse choisir lesquels importer dans la bibliothèque + les distribuer immédiatement (Global / workspaces) si tu veux.</p>
      <p>Chaque skill importé reçoit un <code class="mono">.nebula-origin.json</code> qui trace <code class="mono">repo</code>, <code class="mono">branch</code>, <code class="mono">commit</code>, <code class="mono">imported_at</code> — utile pour de futurs checks de mise à jour.</p>

      <h3>Édition centralisée + désync</h3>
      <p>Le bouton <em>Éditer</em> ouvre la version <strong>bibliothèque</strong> du skill. Les copies déjà distribuées <strong>ne sont pas écrasées en silence</strong> — un badge <em>« N désync. »</em> apparaît sur la carte si certaines copies ont divergé. Pour propager les changements : re-clique <em>Distribuer</em>.</p>

      <h3>Ajouter depuis le magasin sur un workspace</h3>
      <p>Sur la page d'un workspace, section <strong>Skills</strong> → bouton <strong>+ Ajouter depuis le magasin</strong>. Modale qui liste les skills de la bibliothèque non encore présents dans ce workspace, avec checkboxes multi-sélection.</p>

      <h3>Migration depuis l'existant</h3>
      <p>Si ta bibliothèque est vide mais qu'Nebula détecte des skills dans <code class="mono">~/.claude/skills/</code> ou dans des workspaces, un bandeau te propose <strong>Importer dans la bibliothèque</strong> en 1 clic. Migration purement additive, aucune copie écrasée.</p>

      <div class="callout callout-info">
        <strong>Activation par Claude :</strong> les skills sont auto-découverts par Claude Code au démarrage de la session — tu n'as rien à enregistrer manuellement. Vérifie qu'ils apparaissent avec <code class="mono">/help</code> ou via le menu skills de Claude.
      </div>

`,
'plugins': `
      <h2>${I.plug}<span>Plugins</span></h2>
      <p>Les plugins Claude Code sont gérés par la CLI <code class="mono">claude plugin</code>. Nebula propose un browser et la gestion du scope par workspace.</p>

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

`,
'templates': `
      <h2>${I.layers}<span>Templates</span></h2>
      <p>Un template = un dossier dans <code class="mono">templates/&lt;id&gt;/</code> qui sera copié à chaque création de workspace, en remplaçant les placeholders par les valeurs saisies dans le formulaire "Nouveau workspace".</p>

      <h3>Créer un template — bouton "+ Nouveau template"</h3>
      <p>Choix d'un <strong>starter</strong> pré-rempli :</p>
      <ul class="help-list">
        <li>⭐ <strong>Standard</strong> (recommandé) — CLAUDE.md + .gitignore + README.md déjà câblés avec tous les placeholders.</li>
        <li>📭 <strong>Vide</strong> — juste le <code class="mono">.template.json</code>, à toi de tout construire.</li>
        <li>🐍 <strong>Python</strong>, 🟢 <strong>Node.js</strong>, 🐳 <strong>Docker</strong> — starters spécialisés stack.</li>
      </ul>
      <p>Après création, l'éditeur s'ouvre directement sur le nouveau template — tu peux modifier le contenu, ajouter des fichiers, etc.</p>

      <h3>Les 6 placeholders</h3>
      <ul class="help-list">
        <li><code class="mono">{{name}}</code> → champ <strong>ID</strong> du workspace</li>
        <li><code class="mono">{{label}}</code> → champ <strong>Label</strong></li>
        <li><code class="mono">{{description}}</code> → champ <strong>Description</strong></li>
        <li><code class="mono">{{tools}}</code> → champ <strong>Outils / contexte</strong></li>
        <li><code class="mono">{{emoji}}</code> → champ <strong>Emoji</strong></li>
        <li><code class="mono">{{date}}</code> → date du jour à la création (ISO)</li>
      </ul>

      <h3>Panneau "Conseils & qualité"</h3>
      <p>L'éditeur scanne automatiquement le template et propose des suggestions :</p>
      <ul class="help-list">
        <li>⚠️ Pas de <code class="mono">CLAUDE.md</code> — Claude n'aura pas de contexte projet</li>
        <li>⚠️ Pas de <code class="mono">.gitignore</code> — risque de committer des secrets</li>
        <li>❌ Dossiers interdits détectés (<code class="mono">.git</code>, <code class="mono">node_modules</code>, <code class="mono">__pycache__</code>…)</li>
        <li>ℹ️ Placeholders critiques (<code class="mono">{{name}}</code>, <code class="mono">{{label}}</code>) jamais utilisés</li>
      </ul>
      <p>Score de qualité affiché en badge sur chaque card de la grid Templates.</p>

      <h3>Bouton "👁 Aperçu"</h3>
      <p>Dans l'éditeur, sur la barre d'un fichier ouvert, le bouton <strong>👁 Aperçu</strong> ouvre un modal en lecture seule qui montre le contenu après substitution avec des valeurs de test (<code class="mono">name=mon-projet</code>, <code class="mono">label=Mon Projet</code>, etc.). Pratique pour vérifier que les placeholders sont bien câblés.</p>

      <h3>Édition complète depuis le GUI</h3>
      <p>Bouton <em>Éditer</em> sur une carte template ouvre la modale avec arborescence + éditeur. Ctrl+S pour sauvegarder le fichier ouvert. Le panneau qualité se rafraîchit automatiquement après chaque enregistrement.</p>

      <div class="callout callout-warn">
        <strong>Pièges à éviter :</strong> ne jamais inclure <code class="mono">.git/</code>, <code class="mono">node_modules/</code>, <code class="mono">__pycache__/</code>, ni de fichiers binaires &gt; 512 Kio (non éditables ensuite). Pas de secrets en dur — utilise <code class="mono">\${VAR}</code> + <code class="mono">.env.local</code>.
      </div>

`,
'env': `
      <h2>${I.key}<span>Variables d'environnement (.env.local)</span></h2>
      <p>Tes tokens, clés d'API et mots de passe ne doivent jamais se retrouver écrits en dur dans tes fichiers de config. Nebula te propose un emplacement unique pour les stocker : le fichier <code class="mono">.env.local</code>, qui reste local à ta machine et n'est jamais partagé.</p>

      <h3>À quoi ça sert</h3>
      <p>Tu mets une fois tes secrets dans Nebula, et tu les réutilises dans n'importe quel MCP en écrivant <code class="mono">\${NOM_DE_LA_CLE}</code>. Au moment où Nebula configure le MCP pour ton workspace, il remplace automatiquement par la vraie valeur. Avantages :</p>
      <ul class="help-list">
        <li>Tu peux partager ou versionner tes configs MCP sans risque de fuite</li>
        <li>Quand un token expire, tu le mets à jour une fois et tous tes MCPs sont à jour</li>
        <li>Plus de copier-coller à l'aveugle dans des champs de saisie</li>
      </ul>

      <h3>Gérer tes variables</h3>
      <p>Rendez-vous dans <strong>Outils → Variables d'environnement</strong>. Tu y trouves :</p>
      <ul class="help-list">
        <li>Un formulaire pour ajouter une nouvelle clé et sa valeur</li>
        <li>La liste de tes variables, regroupées par préfixe (toutes les <code class="mono">GITHUB_*</code> ensemble, etc.)</li>
        <li>Un champ de recherche pour filtrer rapidement</li>
        <li>Pour chaque variable : un bouton œil pour révéler la valeur, un crayon pour la modifier, une corbeille pour la supprimer</li>
      </ul>

      <h3>Sécuriser le fichier (Windows)</h3>
      <p>Par défaut, <code class="mono">.env.local</code> est un simple fichier texte sur ton disque. Sur Windows, Nebula peut le chiffrer automatiquement pour qu'il devienne illisible en dehors de ta session.</p>
      <p>Sur la page <strong>Outils → Variables d'environnement</strong>, clique sur <em>Activer le chiffrement</em>. C'est tout — l'édition continue de marcher exactement comme avant, mais le fichier sur disque devient illisible si quelqu'un essaie de l'ouvrir sans passer par Nebula.</p>

      <div class="callout callout-info">
        <strong>Ce que le chiffrement protège</strong>
        <ul class="help-list" style="margin-top:6px">
          <li>Une copie du fichier sur clé USB, disque externe ou sauvegarde cloud reste illisible</li>
          <li>Un autre compte utilisateur sur la même machine n'y a pas accès</li>
          <li>Un coup d'œil par-dessus l'épaule ou un partage d'écran ne révèle rien</li>
        </ul>
      </div>

      <div class="callout callout-warn">
        <strong>À garder en tête avant de chiffrer</strong>
        <ul class="help-list" style="margin-top:6px">
          <li>Le chiffrement est lié à ton compte Windows actuel. Si tu changes de machine, réinstalles Windows, ou utilises un autre compte, tu ne pourras plus déchiffrer le fichier.</li>
          <li>Avant un changement de poste ou une réinstallation, pense à utiliser le bouton <em>Désactiver / Exporter clair</em> pour récupérer tes valeurs et les sauvegarder ailleurs (gestionnaire de mots de passe par exemple).</li>
          <li>Le chiffrement ne protège pas contre un logiciel malveillant qui tournerait déjà sur ta session. La meilleure défense reste un antivirus à jour et la prudence avec les exécutables téléchargés.</li>
        </ul>
      </div>

      <h3>Désactiver le chiffrement</h3>
      <p>Le bouton <em>Désactiver / Exporter clair</em> remet le fichier en clair sur ton disque. Pratique pour faire un backup hors-poste, ou pour migrer vers un autre ordinateur. Tu peux réactiver le chiffrement quand tu veux ensuite.</p>

`,
'scope': `
      <h2>${I.activity}<span>Lier MCPs / skills / plugins à un workspace</span></h2>
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

`,
'tools': `
      <h2>${I.tools}<span>Outils & maintenance</span></h2>
      <ul class="help-list">
        <li><strong>Apparence</strong> — choix du thème (Nebula sombre/clair, Marine, Forêt, Brique). Persisté côté serveur (<code class="mono">data/ui_state.json</code>) avec cache localStorage pour éviter le flash au chargement.</li>
        <li><strong>Onboarding</strong> — checklist de découverte + bouton <em>Conflits Claude global</em> (détecte les MCPs en doublon entre Nebula et <code class="mono">~/.claude.json</code> ou <code class="mono">settings.json</code>, avec backup auto avant nettoyage).</li>
        <li><strong>Accès rapide</strong> — boutons pour ouvrir directement les fichiers de config dans l'explorateur ou le bloc-notes.</li>
        <li><strong>Hooks globaux</strong> — édition des hooks Claude Code de <code class="mono">~/.claude/settings.json</code>.</li>
        <li><strong>Sauvegardes</strong> — copie horodatée de <code class="mono">~/.claude.json</code> et <code class="mono">~/.claude/settings.json</code> dans <code class="mono">backups/</code>.</li>
        <li><strong>Variables d'environnement</strong> — éditeur GUI pour <code class="mono">.env.local</code> (cf section 9).</li>
        <li><strong>Maintenance</strong> — nettoyage des <code class="mono">.bat</code> orphelins (workspaces supprimés mais script de lancement encore présent).</li>
      </ul>
      <div class="callout callout-info">
        <strong>Note :</strong> l'import de MCPs depuis du JSON brut se fait directement sur la page MCPs (bouton <em>Importer</em>) — pas de doublon dans Outils.
      </div>

`,
'reflexive': `
      <h2>${I.brain}<span>Reflexive — boucle d'amélioration</span></h2>
      <p>Reflexive observe les sessions Claude Code et mesure leur qualité sur 4 dimensions, pour faire émerger des propositions d'amélioration concrètes. <strong>Optionnel</strong> et <strong>opt-in par workspace</strong> : aucun workspace n'est observé tant que tu n'as pas activé le toggle.</p>
      <h3>À quoi ça sert</h3>
      <p>Au fil des sessions, le score moyen et les <em>flags</em> récurrents (ex. <code class="mono">missing-claude-md-read</code>, <code class="mono">redundant-grep</code>) révèlent des patterns que tu peux corriger via un skill, une convention dans <code class="mono">CLAUDE.md</code> ou un hook. Chaque correctif vient avec un <em>plan de mesure</em> qui vérifie si l'amélioration tient sur N interactions suivantes.</p>
      <h3>Activer Reflexive sur un workspace</h3>
      <ol class="help-list">
        <li>Page <strong>Accueil</strong> → menu d'une card workspace → <em>Modifier</em>.</li>
        <li>Active le switch <strong>Observer cet espace</strong>.</li>
        <li>Les hooks (<code class="mono">SessionStart</code>, <code class="mono">PostToolUse</code>, <code class="mono">Stop</code>) sont ajoutés au <code class="mono">.claude/settings.json</code> du workspace (avec backup <code class="mono">.bak</code>, sans toucher aux hooks tiers).</li>
      </ol>
      <h3>Lire les stats</h3>
      <ul class="help-list">
        <li><strong>Vue d'ensemble</strong> (<kbd>g</kbd> <kbd>r</kbd>) : score moyen + tendance, courbe 30 jours, barres par dimension (la plus basse est le meilleur axe d'attaque).</li>
        <li><strong>Interactions</strong> : table cliquable → modale avec full transcript / tools / files / éval.</li>
        <li><strong>Propositions</strong> : cards Apply / Reject. Le rejet capture une raison pour ajuster le diagnostician.</li>
        <li><strong>Mesures en cours</strong> : les plans déclenchés par les propositions appliquées.</li>
      </ul>
      <h3>Dépannage</h3>
      <ul class="help-list">
        <li><strong>Un hook plante</strong> : l'erreur est loggée dans <code class="mono">dashboard/data/reflexive_hook_errors.log</code>. Les hooks Reflexive ne font <em>jamais</em> échouer une session Claude Code (toute exception est ravalée).</li>
        <li><strong>Désactiver proprement</strong> : repasser le toggle en off retire les hooks Reflexive du <code class="mono">settings.json</code> sans toucher aux autres entrées.</li>
        <li><strong>Réinitialiser la DB</strong> : arrêter le dashboard puis supprimer <code class="mono">dashboard/data/reflexive.db*</code>. La DB sera recréée vide au prochain démarrage.</li>
      </ul>
      <div class="callout callout-info">
        <strong>Sobriété :</strong> Reflexive ne signale rien tant qu'un pattern n'a pas été observé sur ≥5 interactions cohérentes. Mieux vaut zéro proposition qu'une proposition faible.
      </div>

`,
'shortcuts': `
      <h2>${I.zap}<span>Raccourcis clavier</span></h2>
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

`,
'update': `
      <h2>${I.refresh}<span>Auto-update bulletproof</span></h2>
      <p>Le dashboard se met à jour <strong>via git</strong>. Tant que ton install est un clone du repo public, tu reçois les nouvelles fonctionnalités automatiquement.</p>

      <h3>Vérification automatique</h3>
      <ul class="help-list">
        <li><strong>1ʳᵉ vérif de session</strong> — un fermer/rouvrir d'onglet (ou un nouveau navigateur) déclenche systématiquement un <code class="mono">git fetch</code> frais, peu importe quand le dernier check a eu lieu. Garantit qu'un refresh montre toujours les MAJ disponibles.</li>
        <li><strong>Anti-spam</strong> — au sein d'une même session, l'intervalle entre 2 fetchs distants est de <strong>1h</strong> (pour ne pas marteler le remote).</li>
        <li><strong>Re-check périodique</strong> — toutes les 30 min en arrière-plan tant que l'onglet reste ouvert.</li>
        <li>Si des commits sont en attente : <strong>badge gradient pulsant "X MAJ"</strong> apparaît dans le topbar à droite (visible sur toutes les pages), plus un badge descriptif dans la sidebar footer.</li>
      </ul>

      <h3>Appliquer une mise à jour</h3>
      <p>Clic sur le badge → modale avec : version locale (sha), tracking branch, liste des commits à venir (sha + message + auteur + date relative).</p>
      <p>Bouton <em>Appliquer</em> → exécute <code class="mono">git pull --ff-only</code>. Détection auto :</p>
      <ul class="help-list">
        <li>Si seuls JS/CSS/HTML ont changé → bouton <em>Recharger la page</em> (F5 suffit).</li>
        <li>Si du Python a changé → bandeau <em>Redémarrage requis</em>, ferme la console et relance <code class="mono">start-dashboard.bat</code>.</li>
      </ul>

      <h3>Zéro blocage : auto-stash systématique</h3>
      <p>Si tu as des modifs locales (fichiers édités, supprimés, ou untracked) au moment de l'update, Nebula fait un <code class="mono">git stash --include-untracked</code> automatique avec un label horodaté <strong>avant</strong> le pull, puis <code class="mono">git stash pop</code> pour restaurer après. Aucune intervention manuelle requise.</p>
      <p>Si le pop échoue (vraie collision avec les changements distants), tes modifs sont <strong>préservées dans la pile stash</strong> (visibles via <code class="mono">git stash list</code>) — aucune perte de données possible. Un warning explicite te donne le label de stash pour récupération CLI.</p>

      <h3>Escape hatch : Réinitialiser à la version distante</h3>
      <p>Si le pull échoue malgré l'auto-stash (cas exceptionnel : branche divergée, état corrompu…), un panneau <strong>"Forcer l'alignement"</strong> apparaît avec un bouton <em>Réinitialiser à la version distante</em> :</p>
      <ul class="help-list">
        <li>Pré-stash systématique avant le reset</li>
        <li>Exécute <code class="mono">git fetch + git reset --hard origin/main</code></li>
        <li>Tes données utilisateur (registry, workspaces.json, .env.local, mémoire perso) sont préservées via <code class="mono">.gitignore</code> et <code class="mono">--skip-worktree</code></li>
      </ul>

      <h3>Modes de panne couverts</h3>
      <ul class="help-list">
        <li>Modifs locales sur fichiers trackés → auto-stash</li>
        <li>Fichiers supprimés localement (<code class="mono">D ...</code>) → auto-stash</li>
        <li>Fichiers untracked qui collisionnent → auto-stash</li>
        <li>Lock orphelin <code class="mono">.git/index.lock</code> > 60s → retiré automatiquement</li>
        <li>Branches divergées → hint + bouton reset</li>
        <li>Réseau / auth / disque plein → hint humain explicite</li>
      </ul>

      <div class="callout callout-info">
        <strong>Aucun mode de panne n'est silencieux.</strong> Chaque erreur git remonte avec un hint humain et le stderr brut accessible (collapsable) pour debug.
      </div>

`,
'troubleshoot': `
      <h2>${I.alert}<span>Dépannage</span></h2>

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

      <h3>MCPs en doublon entre Nebula et la config Claude globale</h3>
      <p>Si tu avais des MCPs dans <code class="mono">~/.claude.json</code> ou <code class="mono">~/.claude/settings.json</code> avant d'utiliser Nebula, ils peuvent maintenant exister à deux endroits. Ouvre <strong>Outils → Onboarding → Conflits Claude global</strong> pour les détecter et les nettoyer (avec backup automatique). Une bannière jaune apparaît aussi sur la page MCPs si des conflits sont présents.</p>

      <h3>Réinitialiser un workspace cassé</h3>
      <p>Supprime via le GUI <strong>sans</strong> cocher la purge — ça retire seulement l'entrée du registre, le dossier reste intact. Tu peux ensuite réimporter avec <em>+ Dossier</em>.</p>

      <h3>Backup avant manipulation risquée</h3>
      <p><strong>Outils → Sauvegardes → Sauvegarder maintenant</strong> copie <code class="mono">~/.claude.json</code> et <code class="mono">~/.claude/settings.json</code> dans <code class="mono">backups/</code> avec timestamp. À faire avant tout import massif ou bidouille manuelle.</p>
`,
  };
}

// ── Aide : topics (groupements de sections) ────────────────────────────────
const HELP_TOPICS = [
  { id: 'premiers-pas',   emoji: '🚀', title: 'Premiers pas',         summary: 'Découvre Nebula et importe ta config Claude existante.',          sections: ['overview', 'onboarding'] },
  { id: 'workspaces',     emoji: '🗂️', title: 'Workspaces',            summary: 'Créer, importer, lancer et gérer tes projets Claude Code.',       sections: ['workspaces', 'scope'] },
  { id: 'mcps',           emoji: '🔌', title: 'MCPs',                  summary: 'Configurer les serveurs Model Context Protocol et leurs recettes.', sections: ['mcps', 'recipes'] },
  { id: 'skills-plugins', emoji: '✨', title: 'Skills & Plugins',      summary: 'Bibliothèque de compétences et extensions Claude Code.',          sections: ['skills', 'plugins'] },
  { id: 'templates',      emoji: '📋', title: 'Templates',             summary: 'Modèles réutilisables pour démarrer un workspace rapidement.',    sections: ['templates'] },
  { id: 'secrets',        emoji: '🔐', title: 'Secrets & sécurité',    summary: 'Stockage centralisé de tes tokens et clés d\'API, chiffrement.',  sections: ['env'] },
  { id: 'outils',         emoji: '🛠️', title: 'Outils & maintenance',  summary: 'Hooks, sauvegardes, mises à jour automatiques.',                  sections: ['tools', 'update'] },
  { id: 'reflexive',      emoji: '🧠', title: 'Reflexive',              summary: 'Boucle d\'observation et d\'amélioration mesurable de Claude.',    sections: ['reflexive'] },
  { id: 'reference',      emoji: '⌨️', title: 'Référence & dépannage', summary: 'Raccourcis clavier et solutions aux problèmes courants.',         sections: ['shortcuts', 'troubleshoot'] },
];

async function renderHelp() {
  setBreadcrumbs([{ label: 'Aide' }]);
  const tourBtn = btn('🎯 Visite guidée', 'btn-primary', null);
  tourBtn.title = 'Lance un tour interactif en 8 étapes (~2 min)';
  tourBtn.addEventListener('click', () => startTour('main'));
  setTopbarActions([tourBtn]);

  const hash = location.hash;
  const m = hash.match(/^#\/aide\/([a-z0-9-]+)$/);
  if (m) {
    const topic = HELP_TOPICS.find(t => t.id === m[1]);
    if (topic) return renderHelpTopic(topic);
  }
  return renderHelpHub();
}

function renderHelpHub() {
  const c = $('#content');
  c.innerHTML = '';
  const page = el('div', 'page');
  page.appendChild(el('div', 'page-header', `
    <div class="page-header-text">
      <div class="page-eyebrow"><span class="index">05.</span><span>Documentation</span></div>
      <h1 class="page-title">Aide & guide d'utilisation</h1>
      <p class="page-subtitle">Choisis un sujet pour en savoir plus. Chaque page est courte et autonome.</p>
    </div>
  `));

  // Promo visite guidée si jamais lancée
  let tourCompleted = false;
  try { tourCompleted = localStorage.getItem('nebula-tour-completed') === '1'; } catch {}
  if (!tourCompleted) {
    const promo = el('div', 'callout callout-info');
    promo.style.marginBottom = 'var(--sp-4)';
    promo.innerHTML = `
      <div>
        <strong>🎯 Première fois ici ?</strong>
        <p style="margin:4px 0 0;font-size:12.5px">Lance la <strong>visite guidée interactive</strong> (~2 min) — elle te montre les fonctions essentielles avec spotlight sur l'UI réelle.</p>
      </div>
    `;
    const launchBtn = btn('Démarrer la visite', 'btn-primary', null);
    launchBtn.style.marginTop = '8px';
    launchBtn.addEventListener('click', () => startTour('main'));
    promo.querySelector('div').appendChild(launchBtn);
    page.appendChild(promo);
  }

  // Grille de cartes
  const grid = el('div', 'help-hub-grid');
  for (const t of HELP_TOPICS) {
    const card = el('a', 'help-hub-card');
    card.href = `#/aide/${t.id}`;
    card.innerHTML = `
      <div class="help-hub-emoji">${t.emoji}</div>
      <div class="help-hub-title">${escapeHtml(t.title)}</div>
      <div class="help-hub-summary">${escapeHtml(t.summary)}</div>
    `;
    grid.appendChild(card);
  }
  page.appendChild(grid);

  c.appendChild(page);
}

function renderHelpTopic(topic) {
  setBreadcrumbs([
    { label: 'Aide', href: '#/aide' },
    { label: topic.title },
  ]);
  const c = $('#content');
  c.innerHTML = '';
  const page = el('div', 'page');

  // Header avec bouton retour
  const header = el('div', 'page-header');
  header.innerHTML = `
    <div class="page-header-text">
      <div class="page-eyebrow"><a href="#/aide" style="color:inherit;text-decoration:none">← Toutes les aides</a></div>
      <h1 class="page-title">${topic.emoji} ${escapeHtml(topic.title)}</h1>
      <p class="page-subtitle">${escapeHtml(topic.summary)}</p>
    </div>
  `;
  page.appendChild(header);

  // Contenu : concatène les sections de ce topic
  const sections = _helpSections();
  const content = el('div', 'help-content help-content-single');
  let html = '';
  for (const secId of topic.sections) {
    html += `<section>${sections[secId] || ''}</section>`;
  }
  content.innerHTML = html;
  page.appendChild(content);

  // Navigation entre topics (précédent / suivant)
  const idx = HELP_TOPICS.findIndex(t => t.id === topic.id);
  const prev = idx > 0 ? HELP_TOPICS[idx - 1] : null;
  const next = idx < HELP_TOPICS.length - 1 ? HELP_TOPICS[idx + 1] : null;
  const nav = el('div', 'help-topic-nav');
  nav.innerHTML = `
    ${prev ? `<a href="#/aide/${prev.id}" class="help-nav-link"><span class="dim">← Précédent</span><strong>${prev.emoji} ${escapeHtml(prev.title)}</strong></a>` : '<span></span>'}
    ${next ? `<a href="#/aide/${next.id}" class="help-nav-link" style="text-align:right"><span class="dim">Suivant →</span><strong>${next.emoji} ${escapeHtml(next.title)}</strong></a>` : '<span></span>'}
  `;
  page.appendChild(nav);

  c.appendChild(page);
  window.scrollTo({ top: 0, behavior: 'instant' });
}

/* ================================================================
   PAGE: SKILLS
   ================================================================ */
async function renderSkills() {
  setBreadcrumbs([{ label: 'Skills' }]);
  const newBtn = btn('Nouveau skill', 'btn-primary', I.plus);
  newBtn.addEventListener('click', () => modalNewSkill());
  const importBtn = btn('Importer GitHub', 'btn-ghost', '📥');
  importBtn.title = 'Importer un skill depuis un repo GitHub (méthode manuelle automatisée)';
  importBtn.addEventListener('click', () => modalImportSkillsFromGitHub());
  setTopbarActions([importBtn, newBtn]);

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
          <h4>📚 La bibliothèque = ton magasin</h4>
          <p>La page Skills affiche ta <strong>bibliothèque centralisée</strong> (<code class="mono">dashboard/data/skills-library/</code>). Chaque carte représente un skill que tu peux distribuer vers Global et/ou des workspaces — comme un magasin où tu piochais ce que tu veux où tu veux.</p>
        </div>
        <div>
          <h4>📤 Distribuer un skill</h4>
          <p>Bouton <strong>Distribuer</strong> sur chaque carte → coche les cibles (Global + workspaces). Coche pour installer/écraser, décoche pour retirer. Une seule action peut installer le même skill dans plusieurs workspaces simultanément.</p>
        </div>
        <div>
          <h4>📥 Importer depuis GitHub</h4>
          <p>Bouton <strong>Importer GitHub</strong> en haut → colle <code class="mono">user/repo</code> (ex. <code class="mono">czlonkowski/n8n-skills</code>) → Analyser. Nebula détecte tous les <code class="mono">SKILL.md</code> et tu choisis ceux à importer dans ta bibliothèque, avec option de distribution immédiate.</p>
        </div>
        <div>
          <h4>✏️ Édition centralisée</h4>
          <p>Le bouton <strong>Éditer</strong> ouvre la version <em>bibliothèque</em>. Les copies déjà distribuées ne sont <strong>pas écrasées en silence</strong> — un badge « désync. » apparaît si elles divergent. Pour propager, re-clique <em>Distribuer</em>.</p>
        </div>
        <div>
          <h4>🌍 Global vs workspace</h4>
          <p><strong>Global</strong> : <code class="mono">~/.claude/skills/&lt;name&gt;/</code> — actif dans tous les projets.<br><strong>Workspace</strong> : <code class="mono">&lt;workspace&gt;/.claude/skills/&lt;name&gt;/</code> — actif uniquement dans ce projet. La bibliothèque te permet de gérer les deux d'un seul endroit.</p>
        </div>
        <div>
          <h4>⚡ Activation par Claude</h4>
          <p>Les skills sont <strong>auto-découverts</strong> par Claude Code au démarrage de la session — pas besoin de les enregistrer manuellement. Vérifie qu'ils apparaissent avec <code class="mono">/help</code> ou via le menu skills de Claude.</p>
        </div>
      </div>
      <div class="callout callout-info" style="margin-top:var(--sp-3)">
        <div>
          <strong>💡 Tu as déjà des skills dans <code class="mono">~/.claude/skills/</code> ou des workspaces ?</strong>
          Si ta bibliothèque est vide mais qu'Nebula détecte des skills existants, un bandeau te proposera de les importer en 1 clic. Aucune copie n'est écrasée — la migration est purement additive.
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

  // Banner migration : bibliothèque vide mais des skills existent ailleurs
  const library = STATE.skillsLibrary || [];
  if (!library.length && (STATE.skills || []).length) {
    const banner = el('div', 'callout callout-info');
    banner.innerHTML = `
      <div>
        <strong>📚 Importer mes skills existants dans la bibliothèque ?</strong>
        <p style="margin:4px 0 0;font-size:12px">
          Nebula a détecté ${STATE.skills.length} skill(s) dans <code class="mono">~/.claude/skills/</code>.
          Importe-les dans la bibliothèque pour les gérer comme un magasin (édition centralisée + distribution multi-workspaces).
        </p>
      </div>
    `;
    const migrateBtn = btn('Importer dans la bibliothèque', 'btn-primary', '📥');
    migrateBtn.style.marginTop = '8px';
    migrateBtn.addEventListener('click', async () => {
      try {
        const r = await API.post('/api/skills-library/migrate', {});
        toastOk(`${(r.imported || []).length} skill(s) importé(s) dans la bibliothèque`);
        STATE.loading = true; route();
      } catch (e) { toastErr(e.message); }
    });
    banner.querySelector('div').appendChild(migrateBtn);
    page.appendChild(banner);
  }

  const grid = el('div', 'skill-grid');
  page.appendChild(grid);

  const skills = library.slice().sort((a, b) => (a.name || a.id).localeCompare(b.name || b.id));

  const renderList = () => {
    const filter = (toolbar.querySelector('[name=filter]').value || '').trim().toLowerCase();
    const filtered = filter
      ? skills.filter(s => (`${s.id} ${s.name || ''} ${s.description || ''}`).toLowerCase().includes(filter))
      : skills;
    toolbar.querySelector('[data-count]').textContent = `${filtered.length} / ${skills.length}`;
    grid.innerHTML = '';
    if (!filtered.length) {
      const empty = el('div', 'empty');
      if (filter) {
        empty.innerHTML = `<div class="empty-title">Aucun skill ne correspond</div><p class="muted">Modifie ton filtre.</p>`;
      } else {
        empty.innerHTML = `<div class="empty-title">Bibliothèque vide</div><p class="muted">Crée un skill, ou importe-en depuis GitHub avec le bouton « Importer GitHub ».</p>`;
      }
      grid.appendChild(empty);
      return;
    }
    for (const s of filtered) grid.appendChild(librarySkillCard(s));
  };
  toolbar.querySelector('[name=filter]').addEventListener('input', debounce(renderList, 100));
  renderList();

  c.appendChild(page);
}

function librarySkillCard(s) {
  const card = el('div', 'skill-card');
  const distributed = s.distributed_to || [];
  const outdated = s.outdated_count || 0;
  const distLabel = (t) => {
    if (t === 'global') return 'Global';
    if (t.startsWith('workspace:')) {
      const id = t.split(':', 2)[1];
      const w = (STATE.workspaces || []).find(x => x.id === id);
      return `WS: ${w?.label || w?.name || id}`;
    }
    return t;
  };
  let badge;
  if (!distributed.length) {
    badge = '<span class="badge">non distribué</span>';
  } else if (outdated > 0) {
    badge = `<span class="badge badge-warn" title="${outdated} copie(s) avec contenu différent de la bibliothèque">${distributed.length} distribué(s) · ${outdated} désync.</span>`;
  } else {
    badge = `<span class="badge badge-ok">${distributed.length} distribué(s)</span>`;
  }

  card.innerHTML = `
    <div class="skill-card-header">
      <div class="skill-icon">${I.sparkle}</div>
      <div style="flex:1;min-width:0">
        <h3 class="skill-name">${escapeHtml(s.name || s.id)}</h3>
        <div class="dim mono" style="font-size:11px;margin-top:2px">${escapeHtml(s.id)}</div>
      </div>
      ${badge}
    </div>
    <p class="skill-desc">${escapeHtml(s.description || 'Pas de description')}</p>
    ${distributed.length ? `<div class="skill-ws-list">${distributed.map(t => `<span class="chip">${escapeHtml(distLabel(t))}</span>`).join('')}</div>` : ''}
  `;
  const actions = el('div', 'skill-actions');
  const dist = btn('Distribuer', 'btn-sm btn-primary', '📤');
  dist.addEventListener('click', () => modalDistributeSkill(s));
  const ed = btn('Éditer', 'btn-sm btn-ghost', I.edit);
  ed.addEventListener('click', () => modalEditLibrarySkill(s));
  const rm = btn('', 'btn-sm btn-ghost btn-icon-only btn-danger', I.trash);
  rm.title = 'Supprimer de la bibliothèque';
  rm.addEventListener('click', () => modalDeleteLibrarySkill(s));
  actions.append(dist, ed, rm);
  card.appendChild(actions);
  return card;
}

function modalDistributeSkill(s) {
  const body = el('div');
  const distributed = new Set(s.distributed_to || []);
  const wsList = (STATE.workspaces || []);
  body.innerHTML = `
    <p class="muted" style="margin-top:0">
      Coche les emplacements où <strong class="mono">${escapeHtml(s.id)}</strong> doit être présent.
      Décoche pour retirer. La bibliothèque reste source de vérité.
    </p>
    <label class="ws-check" style="display:flex;gap:8px;align-items:center;padding:8px 10px;border:1px solid var(--border);border-radius:6px;margin-bottom:6px">
      <input type="checkbox" data-target="global" ${distributed.has('global') ? 'checked' : ''}>
      <span><strong>Global</strong> <span class="dim mono" style="font-size:11px">~/.claude/skills/</span><br><span class="dim" style="font-size:11.5px">Actif dans tous les projets</span></span>
    </label>
    <div class="dim" style="font-size:11px;margin:8px 0 4px">Workspaces :</div>
    <div data-ws-list></div>
  `;
  const wsHost = body.querySelector('[data-ws-list]');
  if (!wsList.length) {
    wsHost.innerHTML = '<p class="muted">Aucun workspace.</p>';
  } else {
    for (const w of wsList) {
      const t = `workspace:${w.id}`;
      const lbl = el('label', 'ws-check');
      lbl.style.cssText = 'display:flex;gap:8px;align-items:center;padding:6px 10px;border:1px solid var(--border);border-radius:6px;margin-bottom:4px';
      lbl.innerHTML = `
        <input type="checkbox" data-target="${escapeHtml(t)}" ${distributed.has(t) ? 'checked' : ''}>
        <span>${escapeHtml(w.emoji || '📁')} ${escapeHtml(w.label || w.name || w.id)} <span class="dim mono" style="font-size:11px">${escapeHtml(w.id)}</span></span>
      `;
      wsHost.appendChild(lbl);
    }
  }
  const cancel = btn('Annuler', 'btn-ghost');
  const ok = btn('Appliquer', 'btn-primary', '📤');
  const { close } = openModal({ title: `Distribuer ${s.id}`, body, footer: [cancel, ok], wide: true });
  cancel.addEventListener('click', close);
  ok.addEventListener('click', async () => {
    const targets = Array.from(body.querySelectorAll('input[type=checkbox]:checked')).map(cb => cb.dataset.target);
    const willRemove = [...distributed].filter(t => !targets.includes(t));
    const apply = async () => {
      ok.disabled = true;
      try {
        const r = await API.post(`/api/skills-library/${s.id}/distribute`, { targets });
        const parts = [];
        if (r.added?.length) parts.push(`${r.added.length} ajout(s)`);
        if (r.updated?.length) parts.push(`${r.updated.length} mise(s) à jour`);
        if (r.removed?.length) parts.push(`${r.removed.length} retrait(s)`);
        toastOk(parts.join(' · ') || 'Aucun changement');
        close();
        STATE.loading = true; route();
      } catch (e) {
        toastErr(e.message); ok.disabled = false;
      }
    };
    if (willRemove.length) {
      confirmDialog(`Retirer ce skill de ${willRemove.length} emplacement(s) ?`, apply, { danger: true });
    } else {
      apply();
    }
  });
}

function modalAddSkillFromLibrary(wsId) {
  const target = `workspace:${wsId}`;
  const library = (STATE.skillsLibrary || []);
  const candidates = library.filter(s => !(s.distributed_to || []).includes(target));
  const body = el('div');
  if (!library.length) {
    body.innerHTML = `<p class="muted" style="margin-top:0">Ta bibliothèque est vide. Crée un skill depuis l'onglet <strong>Skills</strong> ou importe-en depuis GitHub.</p>`;
    const c = btn('Fermer', 'btn-ghost');
    const { close } = openModal({ title: 'Ajouter depuis le magasin', body, footer: c });
    c.addEventListener('click', close);
    return;
  }
  body.innerHTML = `
    <p class="muted" style="margin-top:0">Coche les skills à installer dans ce workspace.</p>
    <div class="recipes-grid" data-list></div>
  `;
  const list = body.querySelector('[data-list]');
  if (!candidates.length) {
    list.innerHTML = '<p class="muted">Tous les skills de la bibliothèque sont déjà installés ici.</p>';
  }
  for (const s of candidates) {
    const card = el('label', 'recipe-card');
    card.style.cursor = 'pointer';
    card.innerHTML = `
      <input type="checkbox" data-id="${escapeHtml(s.id)}" style="margin-right:8px">
      <div class="recipe-emoji">🧠</div>
      <div class="recipe-body">
        <div class="recipe-name">${escapeHtml(s.name || s.id)}</div>
        <div class="recipe-desc">${escapeHtml(s.description || '')}</div>
        <div class="recipe-meta"><span class="badge mono">${escapeHtml(s.id)}</span></div>
      </div>
    `;
    list.appendChild(card);
  }
  const cancel = btn('Annuler', 'btn-ghost');
  const ok = btn('Installer', 'btn-primary', I.plus);
  const { close } = openModal({ title: 'Ajouter depuis le magasin', body, footer: [cancel, ok], wide: true });
  cancel.addEventListener('click', close);
  ok.addEventListener('click', async () => {
    const ids = Array.from(body.querySelectorAll('input[type=checkbox]:checked')).map(cb => cb.dataset.id);
    if (!ids.length) { toastErr('Aucun skill sélectionné'); return; }
    ok.disabled = true;
    let okCount = 0;
    for (const id of ids) {
      const s = library.find(x => x.id === id);
      const targets = new Set(s?.distributed_to || []);
      targets.add(target);
      try {
        await API.post(`/api/skills-library/${id}/distribute`, { targets: [...targets] });
        okCount++;
      } catch (e) { toastErr(`${id}: ${e.message}`); }
    }
    if (okCount) toastOk(`${okCount} skill(s) installé(s)`);
    close(); STATE.loading = true; route();
  });
}

function modalEditLibrarySkill(s) {
  (async () => {
    let data;
    try { data = await API.get(`/api/skills-library/${s.id}/content`); }
    catch (e) { toastErr(e.message); return; }
    const body = el('div');
    body.innerHTML = `
      <p class="muted" style="margin-top:0">Édition de la version <strong>bibliothèque</strong>.
      Les copies déjà distribuées ne seront <strong>pas écrasées</strong> automatiquement —
      utilise « Distribuer » pour propager les changements.</p>
      <textarea class="textarea mono" rows="22" style="width:100%;font-size:12.5px"></textarea>
    `;
    const ta = body.querySelector('textarea');
    ta.value = data.content || '';
    const cancel = btn('Annuler', 'btn-ghost');
    const save = btn('Enregistrer', 'btn-primary', I.check);
    const { close } = openModal({ title: `Éditer ${s.id} (bibliothèque)`, body, footer: [cancel, save], wide: true });
    cancel.addEventListener('click', close);
    save.addEventListener('click', async () => {
      try {
        await API.post(`/api/skills-library/${s.id}/content`, { content: ta.value });
        toastOk('Enregistré dans la bibliothèque');
        close(); STATE.loading = true; route();
      } catch (e) { toastErr(e.message); }
    });
  })();
}

function modalDeleteLibrarySkill(s) {
  const distributed = (s.distributed_to || []).length;
  const body = el('div');
  body.innerHTML = `
    <p style="margin-top:0">Supprimer <strong class="mono">${escapeHtml(s.id)}</strong> de la bibliothèque ?</p>
    ${distributed > 0 ? `
      <label class="ws-check" style="display:flex;gap:8px;align-items:center;padding:8px;border:1px solid var(--border);border-radius:6px">
        <input type="checkbox" data-also>
        <span>Supprimer aussi des <strong>${distributed} emplacement(s)</strong> où il est distribué</span>
      </label>
      <p class="dim" style="font-size:12px;margin-top:8px">Sinon les copies distribuées restent en place mais perdent leur lien avec la bibliothèque.</p>
    ` : '<p class="dim" style="font-size:12px">Ce skill n\'est distribué nulle part.</p>'}
  `;
  const cancel = btn('Annuler', 'btn-ghost');
  const ok = btn('Supprimer', 'btn-danger', I.trash);
  const { close } = openModal({ title: `Supprimer ${s.id}`, body, footer: [cancel, ok] });
  cancel.addEventListener('click', close);
  ok.addEventListener('click', async () => {
    const also = body.querySelector('[data-also]')?.checked ? 1 : 0;
    try {
      await API.del(`/api/skills-library/${s.id}?also_remove_distributed=${also}`);
      toastOk('Supprimé');
      close(); STATE.loading = true; route();
    } catch (e) { toastErr(e.message); }
  });
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
  const newBtn = btn('Nouveau template', 'btn-primary', I.plus);
  newBtn.addEventListener('click', () => modalNewTemplate());
  setTopbarActions([newBtn]);

  const c = $('#content');
  c.innerHTML = '';
  const page = el('div', 'page');
  page.appendChild(el('div', 'page-header', `
    <div class="page-header-text">
      <div class="page-eyebrow"><span class="index">03.</span><span>Bibliothèque</span></div>
      <h1 class="page-title">Templates</h1>
      <p class="page-subtitle">Modèles réutilisables pour créer de nouveaux workspaces — clique <strong>+ Nouveau template</strong> pour démarrer.</p>
    </div>
  `));

  // Note "Comment utiliser" (collapsible) — refondu
  const help = el('details', 'help-card');
  help.open = !STATE.templates.length;  // ouvert par défaut si aucun template
  help.innerHTML = `
    <summary>
      <span class="help-icon">${I.info}</span>
      <span class="help-title">Comment ça marche ?</span>
      <span class="help-toggle">${I.down}</span>
    </summary>
    <div class="help-body">
      <div class="help-grid">
        <div>
          <h4>📦 Qu'est-ce qu'un template ?</h4>
          <p>Un <strong>dossier modèle</strong> dans <code class="mono">templates/&lt;id&gt;/</code>. À chaque "Nouveau workspace" qui le sélectionne, Nebula copie tout le contenu et remplace les <code class="mono">{{placeholders}}</code> par les valeurs saisies dans le formulaire.</p>
        </div>
        <div>
          <h4>✨ Exemple concret avant/après</h4>
          <p style="margin-bottom:6px">Dans <code class="mono">CLAUDE.md</code> du template :</p>
          <pre class="help-code"># {{label}}

Projet : {{name}}
Créé : {{date}}</pre>
          <p style="margin:6px 0">Devient à la création (ID=<code class="mono">audit</code>, Label=<code class="mono">Audit Prod</code>) :</p>
          <pre class="help-code"># Audit Prod

Projet : audit
Créé : 2026-04-27</pre>
        </div>
        <div>
          <h4>🔤 Les 6 placeholders</h4>
          <table style="font-size:12px;width:100%;border-collapse:collapse">
            <tr><td><code class="mono">{{name}}</code></td><td>ID technique du workspace</td></tr>
            <tr><td><code class="mono">{{label}}</code></td><td>Libellé lisible</td></tr>
            <tr><td><code class="mono">{{emoji}}</code></td><td>Emoji choisi</td></tr>
            <tr><td><code class="mono">{{description}}</code></td><td>Description courte</td></tr>
            <tr><td><code class="mono">{{tools}}</code></td><td>Outils / contexte</td></tr>
            <tr><td><code class="mono">{{date}}</code></td><td>Date du jour ISO</td></tr>
          </table>
        </div>
        <div>
          <h4>✅ Anatomie d'un bon template</h4>
          <ul class="help-list">
            <li><strong>CLAUDE.md</strong> — contexte projet (Claude le lit à chaque session)</li>
            <li><strong>.gitignore</strong> — adapté au stack (Python, Node, etc.)</li>
            <li><strong>README.md</strong> — pour humains</li>
            <li>Structure plate, &lt; 50 fichiers</li>
          </ul>
        </div>
        <div>
          <h4>⚠️ Pièges classiques</h4>
          <ul class="help-list">
            <li>Ne jamais inclure <code class="mono">.git/</code>, <code class="mono">node_modules/</code>, <code class="mono">__pycache__/</code></li>
            <li>Pas de fichiers binaires &gt; 512 Kio (non éditables ensuite)</li>
            <li>Pas de secrets en dur — utilise <code class="mono">\${VAR}</code> et <code class="mono">.env.local</code></li>
            <li>Toujours utiliser <code class="mono">{{name}}</code> et <code class="mono">{{label}}</code> au moins 1 fois</li>
          </ul>
        </div>
        <div>
          <h4>🚀 Démarrage rapide</h4>
          <p>Clique <strong>+ Nouveau template</strong> → choisis un starter (Standard recommandé pour les novices) → édite le contenu → c'est prêt à être utilisé pour créer des workspaces.</p>
        </div>
      </div>
    </div>
  `;
  page.appendChild(help);

  const tpls = STATE.templates;
  if (!tpls.length) {
    const empty = el('div', 'empty');
    empty.innerHTML = `
      <div class="empty-title">Aucun template</div>
      <p class="muted">Clique <strong>+ Nouveau template</strong> en haut à droite pour démarrer avec un starter pré-rempli.</p>
    `;
    const newCta = btn('+ Nouveau template', 'btn-primary', I.plus);
    newCta.style.marginTop = '12px';
    newCta.addEventListener('click', () => modalNewTemplate());
    empty.appendChild(newCta);
    page.appendChild(empty);
  } else {
    const grid = el('div', 'template-grid');
    for (const t of tpls) {
      grid.appendChild(templateCard(t));
    }
    page.appendChild(grid);
  }
  c.appendChild(page);
}

function templateCard(t) {
  const card = el('div', 'template-card');
  // Le starter "Standard" est mis en avant si présent
  const isRecommended = t.id === 'standard';
  card.innerHTML = `
    ${isRecommended ? '<div class="template-recommended">⭐ Recommandé</div>' : ''}
    <div class="template-emoji">${escapeHtml(t.emoji || '📦')}</div>
    <h3 class="template-name">${escapeHtml(t.label || t.id)}</h3>
    <p class="template-desc">${escapeHtml(t.description || '—')}</p>
    <div class="template-meta">${t.file_count} fichier${t.file_count > 1 ? 's' : ''} · <span class="mono">${escapeHtml(t.id)}</span></div>
    <div class="template-quality" data-quality>
      <span class="dim" style="font-size:11px">⏳ qualité…</span>
    </div>
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

  // Fetch qualité en async (non-bloquant)
  const qualHost = card.querySelector('[data-quality]');
  API.get(`/api/templates/${t.id}/quality`).then(q => {
    const sugs = q.suggestions || [];
    const hasErr = sugs.some(s => s.level === 'error');
    const hasWarn = sugs.some(s => s.level === 'warn');
    const hasInfo = sugs.some(s => s.level === 'info');
    let cls, icon, summary;
    if (hasErr) { cls = 'badge-err'; icon = '❌'; summary = `${sugs.length} problème${sugs.length > 1 ? 's' : ''}`; }
    else if (hasWarn) { cls = 'badge-warn'; icon = '⚠️'; summary = `${sugs.length} suggestion${sugs.length > 1 ? 's' : ''}`; }
    else if (hasInfo) { cls = 'badge'; icon = 'ℹ️'; summary = `${sugs.length} info${sugs.length > 1 ? 's' : ''}`; }
    else { cls = 'badge-ok'; icon = '✅'; summary = 'Qualité OK'; }
    qualHost.innerHTML = `<span class="badge ${cls}" title="${escapeHtml(sugs.map(s => '• ' + s.msg).join('\n') || 'Aucune suggestion')}">${icon} ${summary}</span>`;
  }).catch(() => {
    qualHost.innerHTML = '';
  });

  return card;
}

function modalNewTemplate() {
  const body = el('div');
  const STARTERS = [
    { id: 'standard', emoji: '⭐', name: 'Standard', recommended: true,
      desc: 'CLAUDE.md + .gitignore + README.md pré-remplis avec tous les placeholders. Idéal pour démarrer.' },
    { id: 'empty',    emoji: '📭', name: 'Vide',
      desc: 'Juste le .template.json. Tu construis tout à la main.' },
    { id: 'python',   emoji: '🐍', name: 'Python',
      desc: 'CLAUDE.md + requirements.txt + .gitignore Python + README.md.' },
    { id: 'node',     emoji: '🟢', name: 'Node.js',
      desc: 'CLAUDE.md + package.json + .gitignore Node + README.md.' },
    { id: 'docker',   emoji: '🐳', name: 'Docker',
      desc: 'CLAUDE.md + Dockerfile + docker-compose.yml + .dockerignore.' },
  ];

  body.innerHTML = `
    <div class="callout callout-info" style="margin-bottom:var(--sp-3)">
      <div>
        <strong>2 étapes :</strong> 1) choisis un starter ; 2) renseigne les méta. Tu pourras tout éditer ensuite.
      </div>
    </div>
    <div class="section-label" style="margin-bottom:var(--sp-2)"><span class="num">1</span> Choisis un starter</div>
    <div class="recipes-grid" data-starters></div>
    <div class="section-label" style="margin-top:var(--sp-3);margin-bottom:var(--sp-2)"><span class="num">2</span> Méta du template</div>
    <div class="field-row">
      <div class="field" style="flex:0 0 80px"><label class="field-label">Emoji</label><input class="input" name="emoji" value="📦" maxlength="4"></div>
      <div class="field" style="flex:1"><label class="field-label">ID *</label><input class="input mono" name="id" placeholder="mon-template" autocomplete="off"></div>
      <div class="field" style="flex:2"><label class="field-label">Label *</label><input class="input" name="label" placeholder="Mon Template"></div>
    </div>
    <div class="field"><label class="field-label">Description</label><input class="input" name="description" placeholder="À quoi sert ce template (1 phrase)"></div>
  `;

  const startersHost = body.querySelector('[data-starters]');
  let selectedStarter = 'standard';
  for (const s of STARTERS) {
    const card = el('label', 'recipe-card');
    card.style.cursor = 'pointer';
    card.innerHTML = `
      <input type="radio" name="starter" value="${s.id}" ${s.id === 'standard' ? 'checked' : ''} style="margin-right:8px">
      <div class="recipe-emoji">${escapeHtml(s.emoji || '🧠')}</div>
      <div class="recipe-body">
        <div class="recipe-name">${escapeHtml(s.name)}${s.recommended ? ' <span class="badge badge-ok" style="margin-left:6px">recommandé novices</span>' : ''}</div>
        <div class="recipe-desc">${escapeHtml(s.desc)}</div>
      </div>
    `;
    card.querySelector('input').addEventListener('change', (e) => {
      if (e.target.checked) selectedStarter = s.id;
    });
    startersHost.appendChild(card);
  }

  const cancel = btn('Annuler', 'btn-ghost');
  const ok = btn('Créer le template', 'btn-primary', I.plus);
  const { close } = openModal({ title: 'Nouveau template', body, footer: [cancel, ok], wide: true });
  cancel.addEventListener('click', close);
  ok.addEventListener('click', async () => {
    const get = (n) => body.querySelector(`[name=${n}]`).value.trim();
    const payload = {
      id: get('id'),
      label: get('label') || get('id'),
      emoji: get('emoji') || '📦',
      description: get('description'),
      starter: selectedStarter,
    };
    if (!/^[a-zA-Z0-9_-]{1,40}$/.test(payload.id)) { toastErr('ID invalide (a-z, 0-9, _, -, max 40)'); return; }
    ok.disabled = true;
    try {
      await API.post('/api/templates', payload);
      toastOk(`Template '${payload.id}' créé (starter: ${selectedStarter})`);
      close();
      STATE.loading = true;
      // Ouvre directement l'éditeur sur le nouveau
      await route();
      modalEditTemplate(payload.id);
    } catch (e) {
      toastErr(e.message);
      ok.disabled = false;
    }
  });
}

function modalPreviewTemplateFile(path, data) {
  const body = el('div');
  if (data.binary || data.error) {
    body.innerHTML = `<div class="error-box">${escapeHtml(data.error || 'Fichier binaire')}</div>`;
  } else {
    const vars = data.test_vars || {};
    const varList = Object.entries(vars).map(([k, v]) => `<code class="mono">{{${k}}}</code> → <code class="mono">${escapeHtml(v)}</code>`).join(' · ');
    body.innerHTML = `
      <div class="callout callout-info" style="margin-bottom:var(--sp-3)">
        <div>
          <strong>Aperçu avec valeurs de test</strong>
          <div class="dim" style="font-size:11.5px;margin-top:4px">${varList}</div>
        </div>
      </div>
      <pre class="help-code" style="max-height:60vh;overflow:auto">${escapeHtml(data.preview || '')}</pre>
    `;
  }
  const close = btn('Fermer', 'btn-ghost');
  const { close: doClose } = openModal({ title: `Aperçu · ${path}`, body, footer: close, wide: true });
  close.addEventListener('click', doClose);
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
    <div data-quality-panel></div>
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

  // Panneau "Conseils & qualité" (async, refresh-able)
  const qualHost = body.querySelector('[data-quality-panel]');
  const refreshQuality = async () => {
    try {
      const q = await API.get(`/api/templates/${tplId}/quality`);
      const sugs = q.suggestions || [];
      const hasErr = sugs.some(s => s.level === 'error');
      const hasWarn = sugs.some(s => s.level === 'warn');
      const hasInfo = sugs.some(s => s.level === 'info');
      let cls, icon, summary;
      if (hasErr) { cls = 'callout-error'; icon = '❌'; summary = `${sugs.length} problème${sugs.length > 1 ? 's' : ''}`; }
      else if (hasWarn) { cls = 'callout-warn'; icon = '⚠️'; summary = `${sugs.length} suggestion${sugs.length > 1 ? 's' : ''}`; }
      else if (hasInfo) { cls = 'callout-info'; icon = 'ℹ️'; summary = `${sugs.length} info${sugs.length > 1 ? 's' : ''}`; }
      else { cls = 'callout-success'; icon = '✅'; summary = 'rien à signaler'; }

      const lines = sugs.map(s => {
        const li = s.level === 'error' ? '❌' : s.level === 'warn' ? '⚠️' : 'ℹ️';
        return `<li>${li} ${escapeHtml(s.msg)}</li>`;
      }).join('');
      const placeholders = (q.placeholders_used || []).length
        ? `<div class="dim" style="font-size:11px;margin-top:6px">Placeholders détectés : ${q.placeholders_used.map(p => `<code class="mono">{{${p}}}</code>`).join(' ')}</div>`
        : `<div class="dim" style="font-size:11px;margin-top:6px">Aucun placeholder utilisé — le template ne s'adapte pas au workspace créé.</div>`;
      // Ouvert par défaut si erreur ou warn ; fermé pour info-only et OK
      const openByDefault = hasErr || hasWarn;
      qualHost.innerHTML = `
        <details class="callout ${cls}" style="margin-bottom:var(--sp-3)" ${openByDefault ? 'open' : ''}>
          <summary style="cursor:pointer;font-weight:600">${icon} Conseils & qualité — ${summary}</summary>
          ${lines ? `<ul class="help-list" style="margin:8px 0 0">${lines}</ul>` : ''}
          ${placeholders}
        </details>
      `;
    } catch { qualHost.innerHTML = ''; }
  };
  refreshQuality();

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
        <button class="btn btn-sm btn-ghost" data-preview-file title="Aperçu avec valeurs de test">👁 Aperçu</button>
        <button class="btn btn-sm btn-primary" data-save-file>Enregistrer</button>
      </div>
      <textarea class="textarea textarea-code tpl-editor-textarea" spellcheck="false"></textarea>
      <div class="dim" style="font-size:11px;margin-top:6px">💡 Astuce : Ctrl+S enregistre. Bouton 👁 pour voir le rendu après substitution des <code class="mono">{{placeholders}}</code>.</div>
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
        refreshQuality();
        toastOk('Enregistré');
      } catch (e) { toastErr(e.message); }
    });
    pane.querySelector('[data-preview-file]').addEventListener('click', async () => {
      try {
        const r = await API.get(`/api/templates/${tplId}/preview?path=${encodeURIComponent(path)}`);
        modalPreviewTemplateFile(path, r);
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
// Construit la card "Démarrage" : checklist d'onboarding + actions d'import.
// Toujours accessible depuis Outils → A. Démarrage, pas seulement au premier lancement.
function buildOnboardingChecklist() {
  const card = el('div', 'card onboarding-checklist');
  card.innerHTML = `<p class="muted" style="margin:0 0 var(--sp-3) 0;font-size:13px">Récap des étapes de mise en route. Coche-les en cliquant sur l'action correspondante — toujours accessible ici.</p>`;

  // Détection de l'état de chaque étape — non-bloquant si une donnée manque
  const onboardedDone = !!(STATE.uiState && STATE.uiState.onboarded);
  const themePicked = (function() {
    try { return !!localStorage.getItem('nebula-theme'); } catch { return false; }
  })();
  const hasMcps = (STATE.mcps || []).length > 0;
  const hasWorkspaces = (STATE.workspaces || []).length > 0;
  // Coché si AU MOINS un MCP a une intention de scope (registry.workspaces) OU est déjà sync
  const hasScopedMcps =
    (STATE.mcps || []).some(m => (m.workspaces || []).length > 0) ||
    Object.values(STATE.wsMcps || {}).some(x => (x.active || []).length > 0);
  const hasPlugins = (STATE.plugins && STATE.plugins.count > 0) || false;

  const steps = [
    { done: onboardedDone, label: 'Wizard d\'introduction',
      desc: 'Présentation des fonctions clés (thème, import…).',
      action: { label: 'Rejouer', fn: () => { resetOnboarded(); startFirstRunWizard(); } } },
    { done: themePicked, label: 'Thème choisi',
      desc: 'Personnalise l\'ambiance visuelle.',
      action: { label: 'Choisir', fn: () => { document.querySelector('.theme-grid')?.scrollIntoView({ behavior: 'smooth', block: 'center' }); } } },
    { done: hasMcps, label: 'Au moins 1 MCP au registre',
      desc: 'Scanne ta config Claude Code existante OU ajoute manuellement.',
      action: { label: 'Scanner ~/.claude/', fn: () => modalSetupWizard() } },
    { done: hasWorkspaces, label: 'Au moins 1 workspace',
      desc: 'Crée-en un nouveau ou enregistre un dossier existant.',
      action: { label: 'Enregistrer un dossier', fn: () => modalRegisterExisting() } },
    { done: hasScopedMcps, label: 'MCPs scopés à un workspace',
      desc: 'Assigne tes MCPs aux workspaces concernés (page MCP).',
      action: { label: 'Aller aux MCPs', fn: () => { location.hash = '#/mcps'; } } },
    { done: hasPlugins, label: 'Au moins 1 plugin actif',
      desc: 'Active des plugins (code-review, frontend-design…) selon tes besoins.',
      action: { label: 'Voir plugins', fn: () => { location.hash = '#/plugins'; } } },
  ];

  const list = el('div', 'checklist');
  for (const s of steps) {
    const row = el('div', 'checklist-row' + (s.done ? ' is-done' : ''));
    row.innerHTML = `
      <div class="checklist-marker">${s.done ? I.check : '<span class="checklist-circle"></span>'}</div>
      <div class="checklist-body">
        <div class="checklist-label">${escapeHtml(s.label)}</div>
        <div class="checklist-desc">${escapeHtml(s.desc)}</div>
      </div>
    `;
    if (s.action && !s.done) {
      const b = btn(s.action.label, 'btn-sm');
      b.addEventListener('click', s.action.fn);
      row.appendChild(b);
    } else if (s.action && s.done) {
      const b = btn(s.action.label, 'btn-sm btn-ghost');
      b.addEventListener('click', s.action.fn);
      row.appendChild(b);
    }
    list.appendChild(row);
  }
  card.appendChild(list);

  // Compteur de progression
  const doneCount = steps.filter(s => s.done).length;
  const progress = el('div', 'checklist-progress');
  progress.innerHTML = `
    <div class="checklist-progress-bar"><div class="checklist-progress-fill" style="width:${(doneCount / steps.length) * 100}%"></div></div>
    <div class="checklist-progress-text">${doneCount} / ${steps.length} étape${steps.length > 1 ? 's' : ''} ${doneCount === steps.length ? '✓ tout est prêt' : 'complétée' + (doneCount > 1 ? 's' : '')}</div>
  `;
  card.appendChild(progress);

  // Action complémentaire (conflits — l'import JSON est déjà sur la page MCPs)
  const extra = el('div', 'row');
  extra.style.cssText = 'margin-top:var(--sp-3);padding-top:var(--sp-3);border-top:1px solid var(--border)';
  const onbConflicts = btn('Conflits Claude global', 'btn-sm btn-ghost', I.alert);
  onbConflicts.title = 'Détecter et nettoyer les MCPs en doublon avec ~/.claude/';
  onbConflicts.addEventListener('click', () => modalGlobalConflicts());
  extra.append(onbConflicts);
  card.appendChild(extra);

  return card;
}

/* ================================================================
   PAGE: REFLEXIVE — boucle observation / scoring / propositions
   ================================================================ */
const REFX_TABS = [
  ['overview',     "Vue d'ensemble"],
  ['interactions', 'Interactions'],
  ['proposals',    'Propositions'],
  ['measurements', 'Mesures en cours'],
];

function refxScore(v, denom = 12) {
  if (v == null) return '—';
  return Number(v).toFixed(1) + ' / ' + denom;
}

function refxTrend(curr, prev) {
  if (curr == null || prev == null) return '';
  const d = curr - prev;
  const span = document.createElement('span');
  if (Math.abs(d) < 0.05) {
    span.className = 'refx-trend refx-trend-flat';
    span.textContent = '±0';
  } else if (d > 0) {
    span.className = 'refx-trend refx-trend-up';
    span.textContent = '↑ +' + d.toFixed(1);
  } else {
    span.className = 'refx-trend refx-trend-down';
    span.textContent = '↓ ' + d.toFixed(1);
  }
  return span.outerHTML;
}

function refxSparkline(series) {
  if (!series || series.length === 0) return '';
  const W = 600, H = 120, PAD = 8;
  const vals = series.map(p => p.avg_total).filter(v => v != null);
  if (vals.length === 0) return '';
  const max = Math.max(...vals, 12);
  const min = Math.min(...vals, 0);
  const range = (max - min) || 1;
  const stepX = (W - 2 * PAD) / Math.max(1, series.length - 1);
  let d = '';
  series.forEach((p, i) => {
    if (p.avg_total == null) return;
    const x = PAD + i * stepX;
    const y = H - PAD - ((p.avg_total - min) / range) * (H - 2 * PAD);
    d += (d ? ' L' : 'M') + x.toFixed(1) + ',' + y.toFixed(1);
  });
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('class', 'refx-spark');
  svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
  svg.setAttribute('preserveAspectRatio', 'none');
  svg.setAttribute('role', 'img');
  svg.setAttribute('aria-label', 'Courbe de progression du score');
  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('d', d);
  path.setAttribute('fill', 'none');
  path.setAttribute('stroke', 'var(--accent)');
  path.setAttribute('stroke-width', '2');
  path.setAttribute('stroke-linejoin', 'round');
  path.setAttribute('stroke-linecap', 'round');
  svg.appendChild(path);
  return svg.outerHTML;
}

async function renderReflexive() {
  const hash = location.hash || '#/reflexive';
  const sub = hash.replace(/^#\/reflexive\/?/, '') || 'overview';
  const tab = REFX_TABS.some(t => t[0] === sub) ? sub : 'overview';

  setBreadcrumbs([{ label: 'Reflexive' }]);

  const runBtn = btn('Lancer diagnostic', 'btn-primary', I.sparkle);
  runBtn.addEventListener('click', async () => {
    try {
      await API.post('/api/reflexive/diagnostician/run', {});
      toastOk('Diagnostic lancé');
    } catch (e) { toastErr(e.message); }
  });
  setTopbarActions([runBtn]);

  const c = $('#content');
  c.innerHTML = '';

  const page = el('div', 'page');
  const header = el('div', 'page-header');
  const headerText = el('div', 'page-header-text');
  const eyebrow = el('div', 'page-eyebrow');
  const idx = el('span', 'index'); idx.textContent = '06.';
  const lbl = el('span'); lbl.textContent = 'Réflexion';
  eyebrow.appendChild(idx); eyebrow.appendChild(lbl);
  const h1 = el('h1', 'page-title'); h1.textContent = 'Reflexive';
  const sub2 = el('p', 'page-subtitle');
  sub2.textContent = "Observe, score et améliore Claude au fil des sessions. Active la boucle par workspace.";
  headerText.appendChild(eyebrow); headerText.appendChild(h1); headerText.appendChild(sub2);
  header.appendChild(headerText);
  page.appendChild(header);

  const tabs = el('nav', 'tabs');
  tabs.setAttribute('aria-label', 'Sections Reflexive');
  for (const [id, label] of REFX_TABS) {
    const a = document.createElement('a');
    a.href = id === 'overview' ? '#/reflexive' : '#/reflexive/' + id;
    a.className = 'tab' + (id === tab ? ' active' : '');
    a.textContent = label;
    tabs.appendChild(a);
  }
  page.appendChild(tabs);

  const body = el('div', 'refx-body');
  page.appendChild(body);
  c.appendChild(page);

  if (tab === 'overview')          await renderReflexiveOverview(body);
  else if (tab === 'interactions') await renderReflexiveInteractions(body);
  else if (tab === 'proposals')    await renderReflexiveProposals(body);
  else if (tab === 'measurements') await renderReflexiveMeasurements(body);
}

function refxDimBar(label, value, max = 10) {
  const v = value == null ? 0 : Math.max(0, Math.min(max, value));
  const pct = (v / max) * 100;
  const display = value == null ? '—' : value.toFixed(1) + '/' + max;
  const wrap = el('div', 'refx-dim');
  const lab = el('span', 'refx-dim-label'); lab.textContent = label;
  const track = el('span', 'refx-dim-track');
  const fill = el('span', 'refx-dim-fill');
  fill.style.width = pct.toFixed(1) + '%';
  track.appendChild(fill);
  const val = el('span', 'refx-dim-val mono'); val.textContent = display;
  wrap.appendChild(lab); wrap.appendChild(track); wrap.appendChild(val);
  return wrap;
}

function refxLoader(host) {
  host.innerHTML = '';
  const loader = el('div', 'page-loader');
  loader.appendChild(el('div', 'spinner'));
  const span = el('span'); span.textContent = 'Chargement…';
  loader.appendChild(span);
  host.appendChild(loader);
}

function refxEmpty(host, title, hint) {
  host.innerHTML = '';
  const card = el('div', 'card empty');
  const p1 = el('p', 'muted'); p1.textContent = title;
  card.appendChild(p1);
  if (hint) {
    const p2 = el('p', 'muted');
    p2.style.fontSize = '12px';
    p2.textContent = hint;
    card.appendChild(p2);
  }
  host.appendChild(card);
}

function refxKpi(label, value, sub) {
  const card = el('div', 'card refx-kpi');
  const l = el('div', 'refx-kpi-label'); l.textContent = label;
  const v = el('div', 'refx-kpi-value mono'); v.textContent = value;
  card.appendChild(l); card.appendChild(v);
  if (sub) {
    const s = el('div', 'refx-kpi-sub');
    if (sub instanceof Node) s.appendChild(sub);
    else s.textContent = sub;
    card.appendChild(s);
  }
  return card;
}

async function renderReflexiveOverview(host) {
  refxLoader(host);
  const stats = await safe('/api/reflexive/stats?days=30', null);
  host.innerHTML = '';
  if (!stats) {
    refxEmpty(host, 'Stats indisponibles — vérifie que le backend est joignable.');
    return;
  }

  const kpiRow = el('div', 'refx-kpi-row');
  // Score moyen + trend
  const trendSub = el('span');
  if (stats.avg_total != null && stats.avg_total_prev != null) {
    const d = stats.avg_total - stats.avg_total_prev;
    let cls = 'refx-trend-flat', txt = '±0';
    if (Math.abs(d) >= 0.05) {
      cls = d > 0 ? 'refx-trend-up' : 'refx-trend-down';
      txt = (d > 0 ? '↑ +' : '↓ ') + d.toFixed(1);
    }
    trendSub.className = 'refx-trend ' + cls;
    trendSub.textContent = txt;
  } else {
    trendSub.className = 'muted';
    trendSub.textContent = 'pas encore de tendance';
  }
  kpiRow.appendChild(refxKpi('Score moyen (30j)', refxScore(stats.avg_total), trendSub));

  const interSub = el('span', 'muted'); interSub.textContent = 'sur 30 derniers jours';
  kpiRow.appendChild(refxKpi('Interactions', fmtNum(stats.interactions), interSub));

  const propSub = document.createElement('a');
  propSub.className = 'link';
  propSub.href = '#/reflexive/proposals';
  propSub.textContent = 'Voir →';
  kpiRow.appendChild(refxKpi('Propositions en attente', fmtNum(stats.proposals_pending), propSub));

  host.appendChild(kpiRow);

  // Sparkline
  const sparkCard = el('div', 'card');
  const eb = el('div', 'card-eyebrow'); eb.textContent = 'Progression du score · 30 derniers jours';
  sparkCard.appendChild(eb);
  if (!stats.series || !stats.series.some(p => p.avg_total != null)) {
    const empty = el('div', 'refx-spark-empty');
    empty.textContent = 'Aucune donnée encore — active Reflexive sur un workspace pour commencer.';
    sparkCard.appendChild(empty);
  } else {
    const wrap = el('div'); wrap.innerHTML = refxSparkline(stats.series);
    sparkCard.appendChild(wrap);
  }
  host.appendChild(sparkCard);

  // Dimensions
  const dims = stats.dimensions || {};
  const dimCard = el('div', 'card');
  const eb2 = el('div', 'card-eyebrow'); eb2.textContent = 'Score par dimension';
  dimCard.appendChild(eb2);
  const dimWrap = el('div', 'refx-dims');
  dimWrap.appendChild(refxDimBar('Correctness', dims.correctness));
  dimWrap.appendChild(refxDimBar('Efficiency',  dims.efficiency));
  dimWrap.appendChild(refxDimBar('Alignment',   dims.alignment));
  dimWrap.appendChild(refxDimBar('Learning',    dims.learning));
  dimCard.appendChild(dimWrap);
  host.appendChild(dimCard);

  // Workspaces
  const wsCard = el('div', 'card refx-ws-card');
  const wsLeft = el('div');
  const eb3 = el('div', 'card-eyebrow'); eb3.textContent = 'Workspaces observés';
  const count = el('div', 'refx-ws-count mono');
  count.textContent = stats.workspaces_enabled + ' / ' + stats.workspaces_total;
  const hint = el('p', 'muted');
  hint.style.cssText = 'margin:6px 0 0;font-size:12px';
  hint.textContent = "Active Reflexive sur un workspace depuis sa fiche pour qu'il soit observé.";
  wsLeft.appendChild(eb3); wsLeft.appendChild(count); wsLeft.appendChild(hint);
  wsCard.appendChild(wsLeft);
  const goBtn = btn('Gérer les workspaces', 'btn-sm', I.right);
  goBtn.addEventListener('click', () => location.hash = '#/');
  wsCard.appendChild(goBtn);
  host.appendChild(wsCard);
}

async function renderReflexiveInteractions(host) {
  refxLoader(host);
  const data = await safe('/api/reflexive/interactions?limit=100', { items: [], total: 0 });
  host.innerHTML = '';
  if (!data.items.length) {
    refxEmpty(host,
      "Aucune interaction enregistrée pour l'instant.",
      "Active Reflexive sur un workspace et lance une session Claude pour commencer.");
    return;
  }
  const table = el('table', 'data-table');
  const thead = el('thead');
  const trh = el('tr');
  for (const h of ['Démarré', 'Workspace', 'Tâche', 'Outcome', 'Score', 'Flags']) {
    const th = el('th'); th.textContent = h; trh.appendChild(th);
  }
  thead.appendChild(trh); table.appendChild(thead);
  const tbody = el('tbody');
  for (const it of data.items) {
    const tr = el('tr', 'refx-row');
    tr.tabIndex = 0;
    const td1 = el('td', 'mono dim'); td1.textContent = fmtDate(it.started_at);
    const td2 = el('td'); td2.textContent = it.workspace_id || '—';
    const td3 = el('td', 'refx-summary'); td3.textContent = it.task_summary || '(non résumée)';
    const td4 = el('td');
    const oc = it.outcome || 'unknown';
    const ocSpan = el('span', 'refx-outcome refx-outcome-' + oc); ocSpan.textContent = oc;
    td4.appendChild(ocSpan);
    const td5 = el('td', 'mono');
    td5.textContent = it.eval_total != null ? (it.eval_total + '/40') : '—';
    const td6 = el('td');
    const flags = Array.isArray(it.eval_flags) ? it.eval_flags : [];
    for (const f of flags) {
      const chip = el('span', 'chip'); chip.textContent = f; td6.appendChild(chip);
      td6.appendChild(document.createTextNode(' '));
    }
    tr.appendChild(td1); tr.appendChild(td2); tr.appendChild(td3);
    tr.appendChild(td4); tr.appendChild(td5); tr.appendChild(td6);
    const openDetail = () => modalReflexiveInteraction(it.id);
    tr.addEventListener('click', openDetail);
    tr.addEventListener('keydown', (e) => { if (e.key === 'Enter') openDetail(); });
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  host.appendChild(table);
  const meta = el('div', 'muted refx-meta');
  meta.textContent = data.items.length + ' / ' + data.total + ' interactions';
  host.appendChild(meta);
}

async function modalReflexiveInteraction(id) {
  let d;
  try { d = await API.get('/api/reflexive/interactions/' + id); }
  catch (e) { toastErr(e.message); return; }
  const i = d.interaction || {};
  const ev = d.eval || null;
  const tools = Array.isArray(i.tools_used) ? i.tools_used : [];
  const files = Array.isArray(i.files_touched) ? i.files_touched : [];
  const body = el('div');

  const grid = el('div', 'refx-detail-grid');
  const addCell = (label, value, mono = false) => {
    const cell = el('div');
    const lab = el('span', 'dim'); lab.textContent = label;
    const val = el('div', mono ? 'mono' : null); val.textContent = value || '—';
    cell.appendChild(lab); cell.appendChild(val);
    grid.appendChild(cell);
  };
  addCell('Workspace', i.workspace_id, true);
  addCell('Session', i.session_id, true);
  addCell('Début', i.started_at, true);
  addCell('Fin', i.ended_at, true);
  addCell('Outcome', i.outcome || 'unknown');
  addCell('Self-confidence', i.self_confidence != null ? i.self_confidence.toFixed(2) : null, true);
  body.appendChild(grid);

  const h1 = el('h4', 'refx-section-h'); h1.textContent = 'Résumé';
  body.appendChild(h1);
  const p1 = el('p'); p1.textContent = i.task_summary || '(non résumée)';
  body.appendChild(p1);

  const h2 = el('h4', 'refx-section-h'); h2.textContent = 'Outils utilisés (' + tools.length + ')';
  body.appendChild(h2);
  const chips = el('div', 'refx-chips');
  if (tools.length) {
    for (const t of tools) {
      const c = el('span', 'chip mono'); c.textContent = t; chips.appendChild(c);
      chips.appendChild(document.createTextNode(' '));
    }
  } else {
    const m = el('span', 'muted'); m.textContent = '—'; chips.appendChild(m);
  }
  body.appendChild(chips);

  const h3 = el('h4', 'refx-section-h'); h3.textContent = 'Fichiers touchés (' + files.length + ')';
  body.appendChild(h3);
  const filesEl = el('div', 'refx-files mono');
  if (files.length) {
    for (const f of files) { const d = el('div'); d.textContent = f; filesEl.appendChild(d); }
  } else {
    const m = el('span', 'muted'); m.textContent = '—'; filesEl.appendChild(m);
  }
  body.appendChild(filesEl);

  if (ev) {
    const hE = el('h4', 'refx-section-h');
    hE.textContent = 'Évaluation · ' + (ev.evaluated_at || '');
    body.appendChild(hE);
    const wrap = el('div', 'refx-dims');
    wrap.appendChild(refxDimBar('Correctness', ev.correctness));
    wrap.appendChild(refxDimBar('Efficiency',  ev.efficiency));
    wrap.appendChild(refxDimBar('Alignment',   ev.alignment));
    wrap.appendChild(refxDimBar('Learning',    ev.learning));
    body.appendChild(wrap);
    const p = el('p', 'muted');
    p.style.marginTop = 'var(--sp-3)';
    const strong = el('strong'); strong.textContent = 'Total : ';
    p.appendChild(strong);
    p.appendChild(document.createTextNode(ev.total + '/40 — ' + (ev.justification || '')));
    body.appendChild(p);
  } else {
    const m = el('p', 'muted'); m.textContent = "Pas encore d'évaluation pour cette interaction.";
    body.appendChild(m);
  }

  const close = btn('Fermer', 'btn-ghost btn-sm');
  const { close: doClose } = openModal({ title: 'Interaction #' + id, body, footer: close, wide: true });
  close.addEventListener('click', doClose);
}

async function renderReflexiveProposals(host) {
  refxLoader(host);
  const data = await safe('/api/reflexive/proposals?status=pending', { items: [] });
  host.innerHTML = '';
  if (!data.items.length) {
    refxEmpty(host,
      'Aucune proposition en attente.',
      'Le diagnosticien génère des propositions à partir des évaluations accumulées.');
    return;
  }
  for (const p of data.items) {
    const card = el('div', 'card refx-proposal');
    const head = el('div', 'refx-proposal-head');
    const left = el('div');
    const eb = el('div', 'card-eyebrow');
    eb.textContent = (p.target || 'global') + ' · ' + (p.evidence_count || 0) + ' preuves';
    const h = el('h3', 'refx-proposal-title'); h.textContent = p.title || '(sans titre)';
    const path = el('div', 'mono dim');
    path.style.fontSize = '12px';
    path.textContent = p.path || '';
    left.appendChild(eb); left.appendChild(h); left.appendChild(path);
    const actions = el('div', 'refx-proposal-actions');
    head.appendChild(left); head.appendChild(actions);
    card.appendChild(head);

    const applyBtn = btn('Apply', 'btn-primary btn-sm', I.check);
    const rejectBtn = btn('Reject', 'btn-ghost btn-sm', I.x);
    applyBtn.addEventListener('click', async () => {
      try {
        await API.post('/api/reflexive/proposals/' + p.id + '/apply');
        snackbar('Proposition « ' + (p.title || p.id) + ' » appliquée', {
          actionLabel: 'Voir',
          onAction: () => location.hash = '#/reflexive/proposals',
        });
        route();
      } catch (e) { toastErr(e.message); }
    });
    rejectBtn.addEventListener('click', () => modalRejectProposal(p));
    actions.appendChild(applyBtn);
    actions.appendChild(rejectBtn);
    host.appendChild(card);
  }
}

function modalRejectProposal(p) {
  const body = el('div');
  const intro = el('p', 'muted');
  intro.style.marginTop = '0';
  intro.textContent = 'Pourquoi rejeter cette proposition ? La raison sera utilisée pour ajuster le diagnostician.';
  body.appendChild(intro);
  const ta = document.createElement('textarea');
  ta.className = 'textarea';
  ta.rows = 4;
  ta.placeholder = 'Ex. : trop spécifique, pas applicable globalement, contredit une convention…';
  body.appendChild(ta);
  const cancel = btn('Annuler', 'btn-ghost btn-sm');
  const ok = btn('Rejeter', 'btn-danger btn-sm');
  const { close } = openModal({
    title: 'Rejeter « ' + (p.title || ('#' + p.id)) + ' »',
    body, footer: [cancel, ok],
  });
  cancel.addEventListener('click', close);
  ok.addEventListener('click', async () => {
    const reason = ta.value.trim();
    if (!reason) { toastErr('Raison requise'); return; }
    try {
      await API.post('/api/reflexive/proposals/' + p.id + '/reject', { reason });
      toastOk('Proposition rejetée');
      close();
      route();
    } catch (e) { toastErr(e.message); }
  });
}

async function renderReflexiveMeasurements(host) {
  refxLoader(host);
  const data = await safe('/api/reflexive/measurement-plans?status=active', { items: [] });
  host.innerHTML = '';
  if (!data.items.length) {
    refxEmpty(host,
      'Aucun plan de mesure actif.',
      "Chaque proposition appliquée déclenche un plan de mesure pour vérifier qu'elle aide réellement.");
    return;
  }
  for (const m of data.items) {
    const card = el('div', 'card refx-plan');
    const eb = el('div', 'card-eyebrow');
    eb.textContent = m.threshold_dimension + ' ≥ ' + m.threshold_value + ' · ' + m.sample_size + ' interactions';
    const h = el('h3', 'refx-proposal-title'); h.textContent = m.criteria;
    const meta = el('div', 'muted mono');
    meta.style.fontSize = '12px';
    meta.textContent = 'créé le ' + fmtDate(m.created_at) + ' · proposition #' + m.proposal_id;
    card.appendChild(eb); card.appendChild(h); card.appendChild(meta);
    host.appendChild(card);
  }
}

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

  // Démarrage — checklist progressive (toujours visible, accessible à tout moment)
  stack.appendChild(el('div', 'section-label', '<span class="num">A.</span> Démarrage'));
  stack.appendChild(buildOnboardingChecklist());

  // Apparence — sélecteur de thème
  stack.appendChild(el('div', 'section-label', '<span class="num">B.</span> Apparence & assistance'));
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
      <div class="dim" style="font-size:11.5px">Synchronisation avec le dépôt git officiel d'Nebula</div>
    </div>
  `;
  const updateBtn = btn('Vérifier maintenant', 'btn-sm', I.refresh);
  updateBtn.addEventListener('click', () => modalSystemUpdate());
  updateRow.appendChild(updateBtn);
  themeCard.appendChild(updateRow);

  stack.appendChild(themeCard);

  // (la section Onboarding originale a été fusionnée dans "A. Démarrage" ci-dessus)

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
    const fileExists = !!r.exists;
    const encrypted = !!r.encrypted;
    const decErr = r.decryption_error || null;
    const wrap = el('div', 'card');
    const encBadge = encrypted
      ? '<span class="badge badge-ok" style="margin-left:6px" title="Chiffré via DPAPI Windows (compte utilisateur)">🔒 Chiffré (DPAPI)</span>'
      : (fileExists ? '<span class="badge badge-warn" style="margin-left:6px" title="Fichier en clair sur disque">⚠ Clair</span>' : '');
    const missBadge = (!fileExists && !encrypted) ? ' <span class="badge badge-warn" style="margin-left:6px">.env.local absent</span>' : '';
    wrap.innerHTML = `<div class="card-header" style="display:flex;align-items:center;justify-content:space-between;gap:var(--sp-2);flex-wrap:wrap"><h3 class="card-title">${allKeys.length} variable${allKeys.length > 1 ? 's' : ''}${encBadge}${missBadge}</h3><div data-enc-actions style="display:flex;gap:6px"></div></div>`;

    // Actions chiffrement
    const encActions = wrap.querySelector('[data-enc-actions]');
    if (!encrypted) {
      const enableBtn = btn('Activer le chiffrement', 'btn-sm', I.key);
      enableBtn.title = 'Chiffre .env.local avec DPAPI (clé liée à ton compte Windows)';
      enableBtn.addEventListener('click', () => {
        confirmDialog(
          'Activer le chiffrement DPAPI ?\n\nLe fichier sera lié à ton compte Windows. Si tu réinstalles ou changes de poste, les secrets seront illisibles — pense à exporter en clair pour backup avant.\n\nUn fichier .env.local.bak.<date> sera conservé.',
          async () => {
            try { const res = await API.post('/api/env/encrypt', {}); toastOk(`Chiffré (${res.keys} clé${res.keys > 1 ? 's' : ''})`); loadEnvVars(host); }
            catch (e) { toastErr(e.message); }
          }
        );
      });
      encActions.appendChild(enableBtn);
    } else {
      const disableBtn = btn('Désactiver / Exporter clair', 'btn-sm btn-ghost', I.unlock || I.key);
      disableBtn.title = 'Déchiffre et écrit .env.local en clair, supprime le fichier chiffré';
      disableBtn.addEventListener('click', () => {
        confirmDialog(
          'Désactiver le chiffrement ?\n\nLe fichier .env.local sera réécrit en clair sur disque. Pratique pour un backup hors-poste ou pour migrer. Pense à le supprimer ou à réactiver le chiffrement après.',
          async () => {
            try { const res = await API.post('/api/env/decrypt', {}); toastOk(`Déchiffré (${res.keys} clé${res.keys > 1 ? 's' : ''})`); loadEnvVars(host); }
            catch (e) { toastErr(e.message); }
          },
          { danger: true }
        );
      });
      encActions.appendChild(disableBtn);
    }

    if (decErr) {
      const errBox = el('div', 'callout callout-warn');
      errBox.style.marginBottom = 'var(--sp-3)';
      errBox.innerHTML = `
        <div>
          <strong>⚠ Déchiffrement impossible</strong>
          <p style="margin:4px 0 0;font-size:12.5px">Le fichier <code class="mono">.env.local.enc</code> est présent mais ne peut pas être déchiffré sur ce poste / compte utilisateur. Détail : <code class="mono">${escapeHtml(decErr)}</code>.</p>
          <p style="margin:4px 0 0;font-size:12.5px" class="dim">Probable changement de compte Windows, machine, ou profil corrompu. Si tu as un backup clair, restaure-le et réactive le chiffrement.</p>
        </div>
      `;
      wrap.appendChild(errBox);
    }

    // Bloc pédagogique si vraiment vide (pas de fichier OU aucune variable)
    if (!allKeys.length) {
      const intro = el('div', 'callout callout-info');
      intro.style.marginBottom = 'var(--sp-3)';
      intro.innerHTML = `
        <div>
          <strong>🔐 Stockage centralisé pour tes secrets</strong>
          <p style="margin:4px 0 6px;font-size:12.5px">
            <code class="mono">.env.local</code> est un fichier à la racine de Nebula où tu mets tes tokens, API keys, mots de passe.
            Tu y fais référence dans n'importe quel champ MCP avec <code class="mono">\${KEY}</code> — Nebula substitue à la sync vers les workspaces.
            Le fichier reste local, jamais commité.
          </p>
          <pre class="help-code" style="margin:4px 0 6px;font-size:11.5px">GITHUB_TOKEN=ghp_xxxxxxxxxxxx
OPENAI_API_KEY=sk-xxxxxxxxxxxx
DB_PASSWORD=mon_mot_de_passe</pre>
          <p style="margin:0;font-size:11.5px" class="dim">
            ${fileExists
              ? `Le fichier existe (<code class="mono">${escapeHtml(r.file || '.env.local')}</code>) mais est vide. Ajoute ta première variable ci-dessous.`
              : `Le fichier sera <strong>créé automatiquement</strong> à ton premier ajout (chemin : <code class="mono">${escapeHtml(r.file || '.env.local')}</code>).`}
          </p>
        </div>
      `;
      wrap.appendChild(intro);
    }

    // Toolbar : ajout + filtre
    const toolbar = el('div');
    toolbar.style.cssText = 'display:flex;gap:var(--sp-2);margin-bottom:var(--sp-3);flex-wrap:wrap';
    toolbar.innerHTML = `<input class="input input-search" name="filter" placeholder="Filtrer…" style="flex:1;min-width:200px">`;
    wrap.appendChild(toolbar);

    const addRow = el('form');
    addRow.style.cssText = 'display:flex;gap:8px;margin-bottom:var(--sp-3)';
    addRow.innerHTML = `<input class="input mono" name="k" placeholder="KEY (ex. OPENAI_API_KEY)" style="max-width:260px"><input class="input" name="v" placeholder="value" style="flex:1">`;
    const addBtn = btn('Ajouter', 'btn-primary btn-sm', I.plus);
    addBtn.type = 'submit';
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
            <td class="mono" data-cell-val style="font-size:12.5px;color:var(--text-muted);max-width:520px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"><span data-revealed="0" data-real="${escapeHtml(vals[k])}">••••••••</span></td>
            <td style="text-align:right;width:120px;white-space:nowrap"></td>
          `;
          const valCell = tr.querySelector('[data-cell-val]');
          const valSpan = tr.querySelector('[data-real]');
          const eyeBtn = el('button', 'icon-btn btn-icon-only', I.eye);
          eyeBtn.title = 'Afficher / masquer';
          eyeBtn.addEventListener('click', () => {
            const shown = valSpan.dataset.revealed === '1';
            valSpan.textContent = shown ? '••••••••' : valSpan.dataset.real;
            valSpan.dataset.revealed = shown ? '0' : '1';
            eyeBtn.innerHTML = shown ? I.eye : I.eyeoff;
          });
          const editBtn = el('button', 'icon-btn btn-icon-only', I.edit);
          editBtn.title = 'Modifier';
          editBtn.addEventListener('click', () => {
            const current = valSpan.dataset.real;
            const input = document.createElement('input');
            input.className = 'input mono';
            input.type = 'text';
            input.value = current;
            input.style.cssText = 'width:100%;font-size:12.5px;padding:4px 8px';
            valCell.replaceChildren(input);
            input.focus();
            input.select();
            let done = false;
            const save = async () => {
              if (done) return; done = true;
              const newVal = input.value;
              if (newVal === current) { loadEnvVars(host); return; }
              try { await API.post('/api/env', { key: k, value: newVal }); toastOk('Modifié'); loadEnvVars(host); }
              catch (e) { toastErr(e.message); loadEnvVars(host); }
            };
            const cancel = () => { if (done) return; done = true; loadEnvVars(host); };
            input.addEventListener('keydown', (ev) => {
              if (ev.key === 'Enter') { ev.preventDefault(); save(); }
              else if (ev.key === 'Escape') { ev.preventDefault(); cancel(); }
            });
            input.addEventListener('blur', save);
          });
          const rm = el('button', 'icon-btn btn-icon-only btn-danger', I.trash);
          rm.title = 'Supprimer';
          rm.addEventListener('click', () => confirmDialog(`Supprimer ${k} ?`, async () => {
            try { await API.del('/api/env/' + encodeURIComponent(k)); toastOk('Supprimé'); loadEnvVars(host); }
            catch (e) { toastErr(e.message); }
          }, { danger: true }));
          tr.children[2].append(eyeBtn, editBtn, rm);
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

  // Toggle Reflexive observation — appel API immédiat, indépendant du Save
  const refxRow = el('div', 'field');
  refxRow.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:var(--sp-3);margin-top:var(--sp-2);padding-top:var(--sp-3);border-top:1px solid var(--border)';
  const refxLeft = el('div');
  const refxLabel = el('div'); refxLabel.style.cssText = 'font-size:13px;font-weight:500';
  refxLabel.textContent = 'Reflexive — observer cet espace';
  const refxHint = el('div', 'dim'); refxHint.style.cssText = 'font-size:11.5px;margin-top:2px';
  refxHint.textContent = "Installe les hooks d'observation dans .claude/settings.json (avec backup .bak). Désactiver les retire proprement.";
  refxLeft.appendChild(refxLabel); refxLeft.appendChild(refxHint);
  const sw = el('label', 'switch');
  const cb = document.createElement('input');
  cb.type = 'checkbox';
  cb.checked = !!w.reflexive_enabled;
  const slider = el('span', 'switch-slider');
  sw.appendChild(cb); sw.appendChild(slider);
  refxRow.appendChild(refxLeft); refxRow.appendChild(sw);
  body.appendChild(refxRow);

  cb.addEventListener('change', async () => {
    const wanted = cb.checked;
    cb.disabled = true;
    try {
      const endpoint = wanted ? 'enable' : 'disable';
      await API.post(`/api/reflexive/workspace/${w.id}/${endpoint}`);
      w.reflexive_enabled = wanted;
      toastOk(wanted ? 'Reflexive activé — hooks installés' : 'Reflexive désactivé — hooks retirés');
    } catch (e) {
      cb.checked = !wanted;
      toastErr(e.message);
    } finally {
      cb.disabled = false;
    }
  });

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
    <p style="margin-top:0;color:var(--text-muted);font-size:13px">
      <strong>Soft delete</strong> retire le workspace du registre — annulable 10s. Le dossier sur disque est préservé.<br>
      <strong>Purge</strong> supprime aussi le dossier sur disque — irréversible, demande de taper l'ID.
    </p>
    <label class="row" style="cursor:pointer;font-size:13px;margin-top:var(--sp-2)"><input type="checkbox" name="purge"> <span>Purger : supprimer aussi le dossier sur disque</span></label>
    <div class="field" style="display:none;margin-top:var(--sp-3)" data-purge-confirm>
      <label class="field-label">Tape <code class="mono">${escapeHtml(w.id)}</code> pour confirmer la purge</label>
      <input class="input mono" name="confirm" autocomplete="off">
    </div>
  `;
  const purgeCb = body.querySelector('[name=purge]');
  const purgeRow = body.querySelector('[data-purge-confirm]');
  const del = btn('Supprimer', 'btn-danger', I.trash);
  purgeCb.addEventListener('change', () => {
    purgeRow.style.display = purgeCb.checked ? '' : 'none';
    del.textContent = purgeCb.checked ? 'Purger (irréversible)' : 'Supprimer (annulable)';
  });
  const cancel = btn('Annuler', 'btn-ghost');
  const { close } = openModal({ title: 'Supprimer le workspace', body, footer: [cancel, del] });
  cancel.addEventListener('click', close);
  del.addEventListener('click', async () => {
    const purge = purgeCb.checked;
    if (purge && body.querySelector('[name=confirm]').value !== w.id) {
      toastErr('ID incorrect — saisis l\'ID exact pour purger');
      return;
    }
    // Snapshot des metadata pour permettre l'undo (soft delete uniquement)
    const snapshot = {
      id: w.id, path: w.path, label: w.label || w.id,
      emoji: w.emoji || '', description: w.description || '',
    };
    try {
      await API.del(`/api/workspaces/${w.id}${purge ? '?purge=true' : ''}`);
      close();
      STATE.loading = true;
      location.hash = '#/';
      if (purge) {
        toastOk(`Workspace '${w.id}' purgé (dossier supprimé)`);
      } else {
        snackbar(`Workspace '${w.id}' supprimé du registre`, {
          actionLabel: 'ANNULER',
          duration: 10000,
          onAction: async () => {
            try {
              await API.post('/api/setup/import', { mcps: [], projects: [snapshot] });
              toastOk(`Workspace '${w.id}' restauré`);
              STATE.loading = true;
              location.hash = `#/workspace/${w.id}`;
            } catch (e) { toastErr(`Restauration KO : ${e.message}`); }
          },
        });
      }
    } catch (e) { toastErr(e.message); }
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

function modalImportSkillsFromGitHub() {
  const body = el('div');
  const wsRows = (STATE.workspaces || []).map(w => `
    <label class="ws-check" style="display:flex;gap:8px;align-items:center;padding:5px 8px;border:1px solid var(--border);border-radius:6px;margin:3px 0">
      <input type="checkbox" data-target="workspace:${escapeHtml(w.id)}">
      <span>${escapeHtml(w.emoji || '📁')} ${escapeHtml(w.label || w.name || w.id)}</span>
    </label>
  `).join('');
  body.innerHTML = `
    <div class="callout callout-info" style="margin-bottom:var(--sp-3)">
      <div>
        <strong>📥 Import depuis GitHub vers la bibliothèque</strong>
        <p style="margin:4px 0 0;font-size:12px">
          Clone un repo public, détecte les skills (dossiers contenant <code class="mono">SKILL.md</code>),
          les ajoute à ta <strong>bibliothèque</strong> (le magasin), et — optionnel — les distribue
          immédiatement vers Global et/ou des workspaces.
        </p>
      </div>
    </div>
    <div class="field-row">
      <div class="field" style="flex:3">
        <label class="field-label">Repo GitHub *</label>
        <input class="input mono" name="url" placeholder="czlonkowski/n8n-skills ou https://github.com/.../..." autocomplete="off">
      </div>
      <div class="field" style="flex:1">
        <label class="field-label">Branche</label>
        <input class="input mono" name="branch" placeholder="main" autocomplete="off">
      </div>
    </div>
    <div class="field-row" style="align-items:flex-end">
      <button type="button" class="btn btn-primary" data-analyze>🔍 Analyser le repo</button>
      <label class="ws-check" style="margin:0;padding:6px 10px"><input type="checkbox" name="overwrite"> <span>Écraser dans la bibliothèque si existe déjà</span></label>
    </div>
    <div data-result style="margin-top:var(--sp-3)"></div>
    <div data-distribute hidden style="margin-top:var(--sp-3);padding-top:var(--sp-3);border-top:1px solid var(--border)">
      <div class="section-label" style="margin-bottom:var(--sp-2)"><span class="num">📤</span> Distribuer immédiatement (optionnel)</div>
      <p class="dim" style="font-size:11.5px;margin:0 0 var(--sp-2) 0">Si tu coches des cibles ici, les skills importés y seront copiés. Sinon ils restent uniquement dans la bibliothèque.</p>
      <label class="ws-check" style="display:flex;gap:8px;align-items:center;padding:5px 8px;border:1px solid var(--border);border-radius:6px;margin:3px 0">
        <input type="checkbox" data-target="global">
        <span><strong>Global</strong> <span class="dim mono" style="font-size:11px">~/.claude/skills/</span></span>
      </label>
      ${wsRows}
    </div>
  `;

  const cancel = btn('Fermer', 'btn-ghost');
  const importBtn = btn('Importer la sélection', 'btn-primary', '📦');
  importBtn.disabled = true;
  const { close } = openModal({ title: 'Importer des skills depuis GitHub', body, footer: [cancel, importBtn], wide: true });
  cancel.addEventListener('click', close);

  const resultHost = body.querySelector('[data-result]');
  const get = (n) => body.querySelector(`[name=${n}]`).value.trim();
  let lastPreview = null;

  body.querySelector('[data-analyze]').addEventListener('click', async () => {
    const url = get('url');
    if (!url) { toastErr('URL requise'); return; }
    resultHost.innerHTML = '<div class="dim" style="padding:var(--sp-2)">⏳ Clone en cours…</div>';
    importBtn.disabled = true;
    try {
      const r = await API.post('/api/skills/import/preview', { url, branch: get('branch') });
      lastPreview = r;
      if (!r.skills || !r.skills.length) {
        resultHost.innerHTML = '<div class="callout callout-warn">Aucun SKILL.md détecté.</div>';
        return;
      }
      resultHost.innerHTML = `
        <div class="section-label" style="margin-bottom:var(--sp-2)">
          <span class="num">📦</span> ${r.skills.length} skill${r.skills.length > 1 ? 's' : ''} détecté${r.skills.length > 1 ? 's' : ''}
          <span class="right dim" style="font-weight:400">
            ${escapeHtml(r.owner)}/${escapeHtml(r.repo)} · ${escapeHtml(r.branch)} · <code class="mono">${escapeHtml((r.commit || '').slice(0, 7))}</code>
          </span>
        </div>
        <div class="recipes-grid" data-skill-list></div>
      `;
      const list = resultHost.querySelector('[data-skill-list]');
      for (const s of r.skills) {
        const card = el('label', 'recipe-card');
        card.style.cursor = 'pointer';
        card.innerHTML = `
          <input type="checkbox" data-rel="${escapeHtml(s.rel_path)}" checked style="margin-right:8px">
          <div class="recipe-emoji">🧠</div>
          <div class="recipe-body">
            <div class="recipe-name">${escapeHtml(s.name)}</div>
            <div class="recipe-desc">${escapeHtml(s.description || '(pas de description)')}</div>
            <div class="recipe-meta">
              <span class="badge mono">${escapeHtml(s.rel_path)}</span>
            </div>
          </div>
        `;
        list.appendChild(card);
      }
      importBtn.disabled = false;
      body.querySelector('[data-distribute]').hidden = false;
    } catch (e) {
      resultHost.innerHTML = `<div class="callout callout-warn">${escapeHtml(e.message || 'Échec analyse')}</div>`;
    }
  });

  importBtn.addEventListener('click', async () => {
    if (!lastPreview) return;
    const selected = Array.from(resultHost.querySelectorAll('input[type=checkbox][data-rel]:checked'))
      .map(cb => cb.dataset.rel);
    if (!selected.length) { toastErr('Aucun skill sélectionné'); return; }
    const distributeTo = Array.from(body.querySelectorAll('[data-distribute] input[type=checkbox]:checked'))
      .map(cb => cb.dataset.target);
    const payload = {
      url: get('url'),
      branch: get('branch'),
      skills: selected,
      overwrite: body.querySelector('[name=overwrite]').checked,
      distribute_to: distributeTo,
    };
    importBtn.disabled = true;
    try {
      const r = await API.post('/api/skills/import', payload);
      const parts = [];
      if (r.imported?.length) parts.push(`${r.imported.length} importé(s)`);
      if (r.skipped?.length) parts.push(`${r.skipped.length} ignoré(s) (existe déjà)`);
      if (r.errors?.length) parts.push(`${r.errors.length} erreur(s)`);
      toastOk(parts.join(' · ') || 'Terminé');
      close();
      STATE.loading = true;
      route();
    } catch (e) {
      toastErr(e.message);
      importBtn.disabled = false;
    }
  });
}

function modalNewSkill() {
  const body = el('div');
  body.innerHTML = `
    <p class="muted" style="margin-top:0">Créé dans la <strong>bibliothèque</strong> (le magasin). Tu pourras ensuite le distribuer vers Global et/ou des workspaces avec le bouton « Distribuer ».</p>
    <div class="field"><label class="field-label">Nom * (a-z, 0-9, _, -)</label><input class="input mono" name="name" placeholder="mon-skill"></div>
    <div class="field"><label class="field-label">Description * (1 phrase)</label><input class="input" name="description" placeholder="Ce skill aide à…"></div>
    <div class="field"><label class="field-label">Instructions (corps du SKILL.md, optionnel)</label><textarea class="textarea textarea-code" name="body" rows="10" placeholder="Décris ici comment Claude doit utiliser ce skill : étapes, règles, exemples…"></textarea></div>
  `;
  const cancel = btn('Annuler', 'btn-ghost');
  const ok = btn('Créer', 'btn-primary', I.plus);
  const { close } = openModal({ title: 'Nouveau skill (bibliothèque)', body, footer: [cancel, ok], wide: true });
  cancel.addEventListener('click', close);
  ok.addEventListener('click', async () => {
    const get = n => body.querySelector(`[name=${n}]`).value;
    const payload = { name: get('name').trim(), description: get('description').trim(), body: get('body') };
    if (!payload.name) { toastErr('Nom requis'); return; }
    if (!payload.description) { toastErr('Description requise'); return; }
    try {
      await API.post('/api/skills-library', payload);
      toastOk('Skill ajouté à la bibliothèque'); close();
      STATE.loading = true;
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
    const map = { h: '#/', m: '#/mcps', p: '#/plugins', k: '#/skills', t: '#/templates', r: '#/reflexive', o: '#/tools', a: '#/aide' };
    if (map[e.key]) { location.hash = map[e.key]; lastKey = null; e.preventDefault(); return; }
    lastKey = null;
  }
});

/* ================================================================
   TOUR GUIDÉ — overlay + spotlight + bubble par étape
   ================================================================ */
const TOURS = {
  main: [
    {
      title: '👋 Bienvenue dans Nebula',
      body: `<p>Nebula pilote ton écosystème <strong>Claude Code</strong> en local. En 8 étapes (~2 min), je te montre l'essentiel.</p>
        <p class="dim" style="font-size:12px">Tu peux <kbd>Échap</kbd> à tout moment, ou cliquer "Passer". Tu pourras relancer cette visite quand tu veux.</p>`,
      target: null, navigate: '#/',
    },
    {
      title: '📁 Workspaces — tes projets Claude',
      body: `<p>Chaque workspace = un projet Claude Code (un dossier avec son <code class="mono">CLAUDE.md</code>, ses MCPs scopés, ses skills).</p>
        <p>D'ici, tu lances <em>claude</em> directement dans le bon dossier d'un clic.</p>`,
      target: '.workspace-grid, .empty', navigate: '#/',
    },
    {
      title: '➕ Créer un workspace',
      body: `<p>Le bouton <strong>Nouveau workspace</strong> en haut à droite te lance la création depuis un template (Standard, Python, Node…). On copie l'arborescence et on remplace les <code class="mono">{{placeholders}}</code>.</p>`,
      target: '#topbar-actions', navigate: '#/',
    },
    {
      title: '🔌 MCPs — super-pouvoirs de Claude',
      body: `<p>Les <strong>MCPs</strong> (Model Context Protocol) donnent à Claude accès à des outils externes : filesystem, GitHub, n8n, ta base de données…</p>
        <p>Pas besoin d'écrire du JSON : utilise les <strong>recettes</strong> (catalogue 1-clic) ou le formulaire visuel. Nebula sync automatiquement vers les workspaces ciblés.</p>`,
      target: '.page', navigate: '#/mcps',
    },
    {
      title: '🔐 Secrets — <code class="mono">.env.local</code>',
      body: `<p>Tokens, API keys, mots de passe : <strong>jamais en dur</strong> dans tes configs MCP ou templates. Tu les stockes ici une fois et tu les réutilises avec <code class="mono">\${MA_VAR}</code> dans n'importe quel champ MCP.</p>
        <p>Sur Windows, tu peux <strong>chiffrer le fichier en un clic</strong> avec le bouton <em>Activer le chiffrement</em> — illisible si copié ailleurs ou ouvert par un autre compte, transparent à l'usage.</p>`,
      target: '.page', navigate: '#/tools',
    },
    {
      title: '🧠 Skills — bibliothèque centrale',
      body: `<p>Les <strong>skills</strong> sont des compétences réutilisables (prompts longs structurés) que Claude active dynamiquement.</p>
        <p>Le modèle "magasin" : tu maintiens une bibliothèque, et tu <strong>distribues</strong> chaque skill vers Global et/ou des workspaces spécifiques. Une seule édition, plusieurs cibles.</p>`,
      target: '.page', navigate: '#/skills',
    },
    {
      title: '🧪 Reflexive — Claude qui s\'améliore',
      body: `<p>Optionnel : <strong>Reflexive</strong> observe les sessions Claude d'un workspace, les score sur 4 dimensions et fait émerger des propositions concrètes. Activable par workspace (<kbd>g</kbd> <kbd>r</kbd> pour voir la page).</p>
        <p class="dim" style="font-size:12px">Tu peux ignorer ça pour l'instant et y revenir quand tu auras accumulé quelques sessions.</p>`,
      target: '.page', navigate: '#/reflexive',
    },
    {
      title: '📦 Templates — moules de workspaces',
      body: `<p>Un template, c'est l'arborescence de fichiers copiée à chaque <em>Nouveau workspace</em>. Le bouton <strong>+ Nouveau template</strong> propose des starters (Standard, Python, Node, Docker).</p>
        <p>Chaque template a un panneau <em>Conseils & qualité</em> qui scanne les bonnes pratiques.</p>`,
      target: '.page', navigate: '#/templates',
    },
    {
      title: '🛡️ Sanity check + Journal sur la home',
      body: `<p>De retour à l'accueil. La colonne droite contient :</p>
        <ul style="margin:6px 0;padding-left:18px;font-size:13px">
          <li><strong>Sanity check</strong> : signale les configs MCP cassées ou desync.</li>
          <li><strong>Journal</strong> : tes notes rapides projet par projet.</li>
        </ul>`,
      target: '.home-grid > div:nth-child(2)', navigate: '#/',
    },
    {
      title: '🎯 Tu sais l\'essentiel',
      body: `<p>Pour aller plus loin : la page <strong>Aide</strong> détaille tout (raccourcis, dépannage, modèles avancés). Tu peux <strong>relancer cette visite</strong> à tout moment depuis Aide → bouton "Visite guidée".</p>
        <p style="margin-top:8px">Bon code !</p>`,
      target: null,
    },
  ],
};

function _ensureTourOverlay() {
  let overlay = document.getElementById('tour-overlay');
  if (overlay) return overlay;
  overlay = document.createElement('div');
  overlay.id = 'tour-overlay';
  overlay.innerHTML = `
    <div class="tour-mask"></div>
    <div class="tour-bubble" role="dialog" aria-live="polite">
      <div class="tour-bubble-step"></div>
      <h3 class="tour-bubble-title"></h3>
      <div class="tour-bubble-body"></div>
      <div class="tour-bubble-actions">
        <button type="button" class="btn btn-ghost btn-sm" data-tour-skip>Passer</button>
        <div style="flex:1"></div>
        <button type="button" class="btn btn-ghost btn-sm" data-tour-prev>← Précédent</button>
        <button type="button" class="btn btn-primary btn-sm" data-tour-next>Suivant →</button>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);
  overlay.querySelector('[data-tour-skip]').addEventListener('click', endTour);
  overlay.querySelector('[data-tour-next]').addEventListener('click', () => tourGoto(STATE.tour.step + 1));
  overlay.querySelector('[data-tour-prev]').addEventListener('click', () => tourGoto(STATE.tour.step - 1));
  return overlay;
}

function _positionTourBubble(targetEl) {
  const overlay = document.getElementById('tour-overlay');
  const bubble = overlay.querySelector('.tour-bubble');
  const mask = overlay.querySelector('.tour-mask');
  if (!targetEl) {
    // Centre la bulle sans spotlight
    mask.style.clipPath = 'none';
    bubble.style.top = '50%';
    bubble.style.left = '50%';
    bubble.style.transform = 'translate(-50%, -50%)';
    return;
  }
  const r = targetEl.getBoundingClientRect();
  const pad = 8;
  // Spotlight via clip-path : un trou rectangulaire dans le mask
  const x1 = Math.max(0, r.left - pad);
  const y1 = Math.max(0, r.top - pad);
  const x2 = Math.min(window.innerWidth, r.right + pad);
  const y2 = Math.min(window.innerHeight, r.bottom + pad);
  mask.style.clipPath = `polygon(
    0 0, 100% 0, 100% 100%, 0 100%, 0 0,
    ${x1}px ${y1}px, ${x1}px ${y2}px, ${x2}px ${y2}px, ${x2}px ${y1}px, ${x1}px ${y1}px
  )`;
  // Position de la bulle : sous l'élément si possible, sinon au-dessus
  const bw = 380, bh = 240;
  let top = y2 + 12;
  let left = Math.max(12, Math.min(window.innerWidth - bw - 12, r.left));
  if (top + bh > window.innerHeight) {
    top = Math.max(12, y1 - bh - 12);
  }
  bubble.style.transform = 'none';
  bubble.style.top = `${top}px`;
  bubble.style.left = `${left}px`;
  // Scroll si l'élément n'est pas visible
  if (r.top < 0 || r.bottom > window.innerHeight) {
    targetEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

async function tourGoto(idx) {
  if (!STATE.tour) return;
  const def = STATE.tour.definition;
  if (idx < 0) return;
  if (idx >= def.length) { endTour(); return; }
  STATE.tour.step = idx;
  const step = def[idx];

  // Navigation hash si demandée
  if (step.navigate && location.hash !== step.navigate) {
    location.hash = step.navigate;
    // Attendre que la page render
    await new Promise(r => setTimeout(r, 200));
  }
  // Petit délai pour les animations CSS
  await new Promise(r => setTimeout(r, 80));

  const overlay = _ensureTourOverlay();
  overlay.classList.add('is-active');
  overlay.querySelector('.tour-bubble-step').textContent = `${idx + 1} / ${def.length}`;
  overlay.querySelector('.tour-bubble-title').textContent = step.title;
  overlay.querySelector('.tour-bubble-body').innerHTML = step.body;
  overlay.querySelector('[data-tour-prev]').disabled = idx === 0;
  overlay.querySelector('[data-tour-next]').textContent = idx === def.length - 1 ? 'Terminer ✓' : 'Suivant →';

  const targetEl = step.target ? document.querySelector(step.target) : null;
  _positionTourBubble(targetEl);
  try { sessionStorage.setItem('nebula-tour-progress', JSON.stringify({ name: STATE.tour.name, step: idx })); } catch {}
}

function startTour(name = 'main', startStep = 0) {
  const def = TOURS[name];
  if (!def) return;
  STATE.tour = { name, step: startStep, definition: def };
  tourGoto(startStep);
  // Échap pour quitter
  window.addEventListener('keydown', _tourKeyHandler);
  // Reposition sur resize
  window.addEventListener('resize', _tourResizeHandler);
}

function endTour() {
  const overlay = document.getElementById('tour-overlay');
  if (overlay) overlay.classList.remove('is-active');
  STATE.tour = null;
  window.removeEventListener('keydown', _tourKeyHandler);
  window.removeEventListener('resize', _tourResizeHandler);
  try { sessionStorage.removeItem('nebula-tour-progress'); } catch {}
  try { localStorage.setItem('nebula-tour-completed', '1'); } catch {}
}

function _tourKeyHandler(e) {
  if (!STATE.tour) return;
  if (e.key === 'Escape') { endTour(); }
  else if (e.key === 'ArrowRight') { tourGoto(STATE.tour.step + 1); }
  else if (e.key === 'ArrowLeft') { tourGoto(STATE.tour.step - 1); }
}
function _tourResizeHandler() {
  if (!STATE.tour) return;
  const step = STATE.tour.definition[STATE.tour.step];
  const targetEl = step.target ? document.querySelector(step.target) : null;
  _positionTourBubble(targetEl);
}

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
    // STATE.uiState est déjà chargé par loadAll() (lancé dans route()).
    // On lit la source de vérité et on synchronise thème + wizard.
    const uiState = STATE.uiState;

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

    // Re-check périodique (toutes les 30 min) sans force, donc respecte
    // l'anti-spam UPDATE_CHECK_INTERVAL_MS pour le fetch distant.
    // Ce poller global n'est PAS géré par clearPagePollers (volontaire).
    setInterval(() => {
      checkForUpdates().then(renderUpdateBadge).catch(() => {});
    }, 30 * 60 * 1000);
  });
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
else init();
