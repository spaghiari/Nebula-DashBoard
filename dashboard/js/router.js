/* ================================================================
   Nebula - Router + data loading
   ----------------------------------------------------------------
   loadAll : charge en parallele toutes les ressources globales en
   STATE (workspaces, mcps, env, templates, plugins, skills, ui-state,
   library, active sessions, per-ws MCPs).
   route : dispatcher hash-based vers renderHome / renderMCPs /
   renderPlugins / renderSkills / renderTemplates / renderTools /
   renderHelp / renderWorkspace.

   RM-1 v1 "silent route" : sur refresh same-page post-action, pas de
   page-loader qui flash. La nouvelle DOM remplace l'ancienne d'un
   coup. Sur vraie navigation (hash change), loader normal.

   Charge APRES nav.js (updateActiveNav), state.js (STATE,
   clearPagePollers), api.js (API, safe), utils.js ($, escapeHtml).
   Les renderXxx restent dans app.js et sont resolus au call-time
   via le global record (script-scope partage).

   Ref : CM-2 split app.js, refactor 2026-05-13.
   ================================================================ */
'use strict';

// sanity : true quand la page cible est l'accueil. Le sanity-check part
// alors EN PARALLELE des ressources globales (sans rallonger loadAll : il
// n'est pas dans le Promise.all) et renderHome reprend sa promesse ainsi que
// les stats deja chargees ici, au lieu de les redemander apres coup.
async function loadAll({ sanity = false } = {}) {
  const sanityPromise = sanity ? safe('/api/sanity-check', null) : null;
  // Historique quotidien des totaux (sparklines des KPIs) : meme principe.
  const historyPromise = sanity ? safe('/api/stats/history', null) : null;
  // Erreurs de chargement par ressource : distingue « le serveur a echoue »
  // d'un etat vide legitime (avant, safe() renvoyait le fallback vide et la
  // page affichait « aucun element » sur une erreur). Lu par route() via
  // loadErrorsFor() pour afficher une boite d'erreur + Reessayer.
  const errors = {};
  const track = (key, url, fallback) => API.get(url).catch(e => {
    errors[key] = (e && e.message) || 'erreur inconnue';
    return fallback;
  });
  // /api/overview = workspaces (avec path_exists) + statut MCP de chaque
  // workspace en UNE requete (avant : 1 GET /api/workspaces + 1 GET
  // /api/workspaces/<id>/mcps par workspace).
  // /api/stats (cache serveur par fichier) : les chiffres des workspaces sont
  // utiles a toutes les pages (sidebar « recents », en-tete workspace), plus
  // seulement a l'accueil.
  const [overview, mcps, env, tpls, overlays, plugins, skills, uiState, library, sessions, stats] = await Promise.all([
    track('workspaces', '/api/overview', { workspaces: [], ws_mcps: {} }),
    track('mcps', '/api/mcps',       { mcps: [] }),
    track('env', '/api/env',        { keys: [], file: null, exists: false }),
    track('templates', '/api/templates',  { templates: [] }),
    track('overlays', '/api/overlays',   { overlays: [] }),
    track('plugins', '/api/plugins',    { enabled: {}, count: 0 }),
    track('skills', '/api/skills',     { global: [] }),
    safe('/api/ui-state',   { theme: 'nebula', onboarded: false }),
    track('skillsLibrary', '/api/skills-library', { skills: [] }),
    safe('/api/sessions/active', { sessions: {} }),
    API.get('/api/stats').catch(() => null),
  ]);
  STATE.workspaces = overview.workspaces || [];
  STATE.wsMcps = overview.ws_mcps || {};
  STATE.overlaysActive = overview.overlays_active || {};
  if (stats) STATE.stats = stats;
  STATE.statsFailed = !stats;
  STATE.homePrefetch = sanityPromise ? { at: Date.now(), stats, sanity: sanityPromise, history: historyPromise } : null;
  STATE.mcps = mcps.mcps || [];
  STATE.envKeys = env.keys || [];
  STATE.envFile = env.file;
  STATE.envExists = env.exists;
  STATE.templates = tpls.templates || [];
  STATE.overlays = overlays.overlays || [];
  STATE.plugins = plugins;
  STATE.skills = skills.global || [];
  STATE.skillsLibrary = library.skills || [];
  STATE.uiState = uiState;
  STATE.activeSessions = sessions.sessions || {};
  STATE.loadErrors = errors;
  startSessionsPolling();
  updateNavCounts();
  renderRecentWorkspaces();

  STATE.loading = false;
  // Detecteur hors-ligne : deduit des requetes ci-dessus (API._req leve
  // « Serveur injoignable » sur erreur reseau), sans requete supplementaire.
  const offline = Object.values(errors).some(m => m === 'Serveur injoignable');
  $('#offline-banner').hidden = !offline;
}

// Ressources STATE dont chaque page a besoin. Si l'une a echoue au
// chargement, route() affiche une erreur + « Reessayer » au lieu de rendre
// la page avec des listes vides trompeuses.
const ROUTE_RESOURCES = [
  [/^#\/$/, ['workspaces']],
  [/^#\/mcps$/, ['mcps', 'workspaces']],
  [/^#\/plugins$/, ['plugins']],
  [/^#\/skills$/, ['skills', 'skillsLibrary']],
  [/^#\/templates$/, ['templates']],
  [/^#\/workspace\//, ['workspaces']],
];

const RESOURCE_LABELS = {
  workspaces: 'workspaces', mcps: 'registre MCP', plugins: 'plugins',
  skills: 'skills', skillsLibrary: 'bibliotheque de skills', templates: 'templates',
};

function loadErrorsFor(hash) {
  const errs = STATE.loadErrors || {};
  const entry = ROUTE_RESOURCES.find(([re]) => re.test(hash));
  if (!entry) return [];
  return entry[1].filter(k => errs[k]).map(k => ({ key: k, message: errs[k] }));
}

function renderLoadError(content, failures) {
  const box = el('div', 'page');
  const err = el('div', 'error-box load-error');
  err.setAttribute('role', 'alert');
  const lines = failures.map(f =>
    `<li><strong>${escapeHtml(RESOURCE_LABELS[f.key] || f.key)}</strong> : ${escapeHtml(f.message)}</li>`).join('');
  err['innerHTML'] = `<p>Impossible de charger les données de cette page (erreur réseau ou serveur, pas une liste vide).</p><ul>${lines}</ul>`;
  const retry = btn('Réessayer', 'btn-primary', I.refresh);
  retry.addEventListener('click', () => { STATE.loading = true; route(); });
  err.appendChild(retry);
  box.appendChild(err);
  content.replaceChildren(box);
  retry.focus();
}

// Track la route precedente pour distinguer "navigation entre pages"
// (montrer un loader) de "refresh same-page post-action" (silencieux).
let _lastRoutedHash = null;

// Bug #14 : jeton de rendu monotone contre les renders perimes.
// Chaque route() qui va declencher un rendu incremente le jeton ; tout
// travail async (loadAll ici, awaits dans les renderXxx) capture le
// jeton a l'entree et verifie routeIsStale() avant d'ecrire dans
// #content. Meme esprit que le garde row.isConnected
// d'attachSessionPreview (app.js). Sans ca, une navigation rapide
// A -> B laisse le rendu lent de A ecraser la page B apres coup
// (y compris des boutons topbar lies au mauvais id via closures).
let _routeToken = 0;

function routeIsStale(token) { return token !== _routeToken; }

// Cle de page : l'onglet d'un workspace (#/workspace/<id>/<onglet>) ne change
// pas de page (bascule sans re-rendu, cf. renderWorkspace).
function pageKey(hash) {
  const m = hash.match(/^#\/workspace\/([a-zA-Z0-9_-]+)(?:\/[a-z]+)?$/);
  return m ? `#/workspace/${m[1]}` : hash;
}

/* ================================================================
   Actions de page « dockees » (refonte 2026-10)
   ----------------------------------------------------------------
   Les pages continuent d'appeler setTopbarActions() ; le conteneur
   #page-actions (recherche + mise a jour + actions) est ensuite deplace
   dans l'en-tete de la page rendue ([data-page-actions] ou .page-header).
   Avant chaque rendu il revient dans la topbar : les pages vident #content
   et le detruiraient sinon. Rendu silencieux : un clone inerte garde la
   place le temps du rendu (pas de clignotement des boutons).
   ================================================================ */
function undockPageActions(keepGhost) {
  const pa = $('#page-actions');
  const bar = $('.topbar');
  if (!pa || !bar || pa.parentElement === bar) return;
  if (keepGhost) {
    const ghost = pa.cloneNode(true);
    ghost.removeAttribute('id');
    ghost.querySelectorAll('[id]').forEach(n => n.removeAttribute('id'));
    ghost.inert = true;
    ghost.setAttribute('aria-hidden', 'true');
    pa.replaceWith(ghost);
  }
  bar.appendChild(pa);
  bar.classList.remove('is-docked');
}

function dockPageActions() {
  const pa = $('#page-actions');
  const bar = $('.topbar');
  if (!pa || !bar) return;
  const page = $('#content > .page');
  const slot = page && (page.querySelector('[data-page-actions]') || page.querySelector('.page-header'));
  if (!slot) { bar.classList.remove('is-docked'); return; }
  if (pa.parentElement !== slot) slot.appendChild(pa);
  bar.classList.add('is-docked');
  requestAnimationFrame(() => document.querySelectorAll('.seg').forEach(placeSegThumb));
}

/* ================================================================
   Garde de navigation interne (onglet workspace modifie)
   ----------------------------------------------------------------
   beforeunload (app.js) ne couvre que la fermeture / le rechargement de
   l'onglet du navigateur. Quitter la page workspace par la sidebar, un
   lien, Ctrl+K, un raccourci « g x » ou l'historique passe par
   hashchange -> route() : on demande confirmation si un onglet du
   workspace a une edition non enregistree (meme etat que la pastille
   « modifie », panels[k].isDirty()).
   Rester = le hash precedent est restaure par replaceState (aucun
   hashchange, aucun re-rendu : editeurs intacts). Une bascule d'onglet
   dans le meme workspace (meme pageKey) n'est jamais concernee.
   Navigation programmee apres une mutation explicite (creation,
   duplication, suppression : STATE.loading deja a true) : pas de garde.
   Limite : « Rester » apres un Precedent du navigateur reecrit l'entree
   d'historique precedente avec la page workspace (pas de go(+1) fiable).
   ================================================================ */
let _navGuardPending = false;

// Libelles des onglets du workspace affiche qui ont une edition en cours.
function wsPendingEditTabs() {
  if (typeof WS_PAGE === 'undefined' || !WS_PAGE || !WS_PAGE.root || !WS_PAGE.root.isConnected) return [];
  const tabs = (typeof WS_TABS !== 'undefined') ? WS_TABS : [];
  return tabs.filter(([k]) => {
    const p = WS_PAGE.panels[k];
    return p && p.mounted && typeof p.isDirty === 'function' && p.isDirty();
  }).map(t => t[1]);
}

// true = navigation bloquee (l'appelant ne doit rien rendre).
async function navGuardBlocks(hash) {
  // Une confirmation est deja ouverte : elle tranchera sur le hash final.
  if (_navGuardPending) return true;
  if ((STATE.loading && !STATE.panelsReloading) || !_lastRoutedHash || !hash.startsWith('#/')) return false;
  if (pageKey(hash) === pageKey(_lastRoutedHash)) return false;
  const tabs = wsPendingEditTabs();
  if (!tabs.length) return false;
  const from = _lastRoutedHash;
  _navGuardPending = true;
  let leave = false;
  try {
    const plural = tabs.length > 1;
    const msg = `Modifications non enregistrées dans ${plural ? 'les onglets' : "l'onglet"} ${tabs.join(', ')}.\n`
      + 'Quitter cette page les abandonne. Reste sur la page pour les enregistrer (Ctrl+S) ou les annuler.';
    leave = await new Promise((resolve) => {
      let yes = false;
      confirmDialog(msg, () => { yes = true; }, {
        danger: true, confirmLabel: 'Quitter sans enregistrer', cancelLabel: 'Rester sur la page',
        onClose: () => resolve(yes),
      });
    });
  } finally {
    _navGuardPending = false;
  }
  if (leave) return false;
  if (location.hash !== from) history.replaceState(null, '', from);
  updateActiveNav();
  return true;
}

async function route(opts) {
  const silent = !!(opts && opts.silent);
  if (!silent && await navGuardBlocks(location.hash || '#/')) return;
  clearPagePollers();
  updateActiveNav();
  const hash = location.hash || '#/';
  // Ancres intra-page (ex. #h-env depuis le TOC d'Aide) : on laisse le
  // navigateur scroller, on ne re-render rien -- sinon on perd la page courante.
  if (hash && !hash.startsWith('#/')) return;
  // Bug #14 : ce route() va rendre une page -> il invalide tout rendu
  // encore en vol (silent inclus : un silent re-route re-rend la page
  // entiere, il doit donc lui aussi superseder les rendus precedents).
  // Meme workspace deja affiche, seul l'onglet change (lien, palette,
  // historique) : bascule en place, editeurs et explorateur preserves.
  if (!silent && !STATE.loading && pageKey(hash) === pageKey(_lastRoutedHash || '')
      && hash !== _lastRoutedHash && typeof wsSwitchTabFromHash === 'function' && wsSwitchTabFromHash(hash)) {
    _lastRoutedHash = hash;
    return;
  }
  const myToken = ++_routeToken;
  if (STATE.loading) await loadAll({ sanity: hash === '#/' });
  // Bug #14 : une navigation plus recente a pris la main pendant
  // loadAll -- on abandonne AVANT de toucher au DOM ou de dispatcher.
  if (routeIsStale(myToken)) return;
  const content = $('#content');
  // RM-1 v1 : "silent route" pour les refresh same-page post-action.
  // Si on reste sur la meme page (refresh post-CRUD), pas de page-loader
  // qui flash. La nouvelle DOM remplace l'ancienne d'un coup, sans etat
  // intermediaire vide. Sur vraie navigation (hash change), loader normal.
  const samePage = (pageKey(hash) === pageKey(_lastRoutedHash || ''));
  undockPageActions(silent || samePage);
  if (!silent && !samePage) {
    content['innerHTML'] = '<div class="page-loader"><div class="spinner"></div><span>Chargement…</span></div>';
  }
  _lastRoutedHash = hash;
  const failures = loadErrorsFor(hash);
  if (failures.length) { renderLoadError(content, failures); return; }
  try {
    const m = hash.match(/^#\/workspace\/([a-zA-Z0-9_-]+)(?:\/([a-z]+))?$/);
    if (hash === '#/') await renderHome();
    else if (hash === '#/mcps') await renderMCPs();
    else if (hash === '#/plugins') await renderPlugins();
    else if (hash === '#/skills') await renderSkills();
    else if (hash === '#/templates') await renderTemplates();
    else if (hash === '#/tools') await renderTools();
    else if (hash === '#/aide' || hash.startsWith('#/aide/')) await renderHelp();
    else if (m) await renderWorkspace(m[1], m[2]);
    else { location.hash = '#/'; return; }
    if (!routeIsStale(myToken)) dockPageActions();
  } catch (e) {
    // Bug #14 : ne pas ecraser la page d'une navigation plus recente
    // avec la boite d'erreur d'un rendu perime.
    if (routeIsStale(myToken)) return;
    content['innerHTML'] = `<div class="error-box">Erreur : ${escapeHtml(e.message)}</div>`;
  }
}

/* ================================================================
   Sessions actives : marqueurs running / idle + polling leger
   ----------------------------------------------------------------
   /api/sessions/active renvoie { ws_id: {pid, launched_at, label,
   state} } avec state = "running" (Claude tourne dans le cmd) ou
   "idle" (fenetre cmd encore ouverte, Claude ferme). Les sessions
   mortes / a PID recycle sont prunees cote serveur.

   Polling toutes les 5 s UNIQUEMENT si l'onglet est visible, + refresh
   immediat au retour de visibilite. Aucun re-render de page : seuls
   les noeuds marques sont mis a jour, et seulement si l'etat change :
   - [data-ws-state=<id>]           : marqueur d'etat (cellule, pastille, en-tete)
   - [data-ws-card=<id>]            : card / rangee / featured (presence)
   - [data-ws-session-actions=<id>] : boutons Stop vs Lancer (detail)
   ================================================================ */
function sessionState(id) {
  const s = (STATE.activeSessions || {})[id];
  if (!s) return null;
  return s.state === 'idle' ? 'idle' : 'running';
}

// Date de lancement de la session (chronometre « depuis »), ISO ou ''.
// Le backend stocke launched_at en epoch SECONDES (active_sessions.py) :
// normalise en ISO ; une chaine ISO deja fournie est conservee.
function sessionSince(id) {
  const s = (STATE.activeSessions || {})[id];
  const v = s && s.launched_at;
  if (typeof v === 'number' && Number.isFinite(v)) return new Date(v * 1000).toISOString();
  if (typeof v === 'string' && /^\d+(\.\d+)?$/.test(v)) return new Date(Number(v) * 1000).toISOString();
  return v || '';
}

// Etat de session de la refonte : `kind` = 'cell' (colonne Etat du tableau),
// 'header' (en-tete workspace, avec chronometre) ou 'pill' (fil d'activite).
function wsStateInner(id, kind) {
  const st = sessionState(id);
  if (kind === 'cell') {
    if (st === 'running') return '<span class="state-cell st-run"><span class="sdot live"></span>En direct</span>';
    if (st === 'idle') return '<span class="state-cell st-idle" title="La fenêtre cmd est ouverte, Claude Code ne tourne plus"><span class="sdot"></span>Terminal ouvert</span>';
    return '<span class="state-cell off">Inactif</span>';
  }
  if (kind === 'pill') {
    if (st === 'running') return '<span class="pill ok"><span class="sdot live"></span>en cours</span>';
    if (st === 'idle') return '<span class="pill warn">terminal ouvert</span>';
    return '';
  }
  // header
  const since = sessionSince(id);
  if (st === 'running') {
    return `<span class="hstate"><span class="pill ok"><span class="sdot live"></span>En direct</span>`
      + (since ? `<span class="since">depuis <span class="timer" data-since="${escapeHtml(since)}">${escapeHtml(fmtElapsed(Date.now() - Date.parse(since)))}</span></span>` : '')
      + '</span>';
  }
  if (st === 'idle') {
    return `<span class="hstate"><span class="pill warn" title="La fenêtre cmd est ouverte, Claude Code ne tourne plus. Stop la ferme."><span class="sdot"></span>Terminal ouvert</span>`
      + `<span class="since">Claude Code arrêté, fenêtre cmd encore ouverte</span></span>`;
  }
  return '';
}
function wsStateMarker(id, kind) {
  return `<span class="ws-live-wrap" data-ws-state="${escapeHtml(id)}" data-state-kind="${escapeHtml(kind)}">${wsStateInner(id, kind)}</span>`;
}

// Chronometres « depuis » : un seul intervalle global, 1 maj/s, uniquement
// le texte des [data-since] visibles (aucun re-rendu).
let _sinceTick = null;
function startSinceTimers() {
  if (_sinceTick) return;
  _sinceTick = setInterval(() => {
    if (document.visibilityState !== 'visible') return;
    for (const node of document.querySelectorAll('[data-since]')) {
      const t = Date.parse(node.dataset.since);
      if (!isNaN(t)) node.textContent = fmtElapsed(Date.now() - t);
    }
  }, 1000);
}

let _sessPollId = null;
let _sessInflight = false;

function startSessionsPolling() {
  startSinceTimers();
  if (_sessPollId) return;
  _sessPollId = setInterval(() => {
    if (document.visibilityState === 'visible') refreshActiveSessions();
  }, 5000);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') refreshActiveSessions();
  });
}

async function refreshActiveSessions() {
  if (_sessInflight || STATE.loading) return;
  _sessInflight = true;
  try {
    const r = await API.get('/api/sessions/active');
    if (!STATE.loading) applyActiveSessions((r && r.sessions) || {});
  } catch { /* silencieux : le banner offline est gere par loadAll */ }
  finally { _sessInflight = false; }
}

function applyActiveSessions(next) {
  const prev = STATE.activeSessions || {};
  const ids = new Set([...Object.keys(prev), ...Object.keys(next)]);
  const changed = [];
  for (const id of ids) {
    const a = prev[id];
    const b = next[id];
    if (!!a !== !!b) changed.push(id);
    else if (a && b && ((a.state || 'running') !== (b.state || 'running') || a.launched_at !== b.launched_at)) changed.push(id);
  }
  if (!changed.length) return;
  STATE.activeSessions = next;
  for (const id of changed) {
    const sel = CSS.escape(id);
    for (const wrap of document.querySelectorAll(`[data-ws-state="${sel}"]`)) {
      wrap['innerHTML'] = wsStateInner(id, wrap.dataset.stateKind || 'cell');
    }
    refreshSessionNodes(id);
  }
  renderRecentWorkspaces();
}

// Re-rendu cible des noeuds d'un workspace dont la session a change (aucun
// re-rendu de page : explorateur / editeurs preserves).
function refreshSessionNodes(id) {
  const w = STATE.workspaces.find(x => x.id === id);
  if (!w) return;
  const active = !!(STATE.activeSessions || {})[id];
  const sel = CSS.escape(id);
  let liveFound = false;
  for (const node of document.querySelectorAll(`[data-ws-card="${sel}"]`)) {
    const kind = node.dataset.wsKind;
    if (kind === 'featured') {
      liveFound = true;
      if (!active) { node.remove(); continue; }
      // Etat change (running <-> idle) : la carte change de forme.
      const fresh = typeof liveCard === 'function' ? liveCard(w, node.classList.contains('alt')) : null;
      if (fresh) node.replaceWith(fresh);
      continue;
    }
    const fresh = kind === 'row' ? workspaceRow(w) : kind === 'card' ? workspaceCard(w) : null;
    if (fresh) node.replaceWith(fresh);
  }
  // Session apparue hors navigation : ajoutee a « En cours » si la section existe.
  if (active && !liveFound && typeof liveCard === 'function') {
    const grid = document.querySelector('.live-grid');
    if (grid) grid.appendChild(liveCard(w, grid.querySelectorAll('.live-card').length % 2 === 1));
  }
  // Section « En cours » devenue vide -> retirer grille + son label.
  for (const grid of document.querySelectorAll('.live-grid, .featured-grid')) {
    if (grid.children.length) continue;
    const label = grid.previousElementSibling;
    if (label && (label.classList.contains('section-label') || label.classList.contains('lbl'))) label.remove();
    grid.remove();
  }
  for (const box of document.querySelectorAll(`[data-ws-session-actions="${sel}"]`)) {
    box.replaceChildren(...wsSessionActions(w));
  }
}

window.addEventListener('hashchange', route);
