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

async function loadAll() {
  const [ws, mcps, env, tpls, plugins, skills, uiState, library, sessions] = await Promise.all([
    safe('/api/workspaces', { workspaces: [] }),
    safe('/api/mcps',       { mcps: [] }),
    safe('/api/env',        { keys: [], file: null, exists: false }),
    safe('/api/templates',  { templates: [] }),
    safe('/api/plugins',    { enabled: {}, count: 0 }),
    safe('/api/skills',     { global: [] }),
    safe('/api/ui-state',   { theme: 'nebula', onboarded: false }),
    safe('/api/skills-library', { skills: [] }),
    safe('/api/sessions/active', { sessions: {} }),
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
  STATE.activeSessions = sessions.sessions || {};

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

// Track la route precedente pour distinguer "navigation entre pages"
// (montrer un loader) de "refresh same-page post-action" (silencieux).
let _lastRoutedHash = null;

async function route(opts) {
  const silent = !!(opts && opts.silent);
  clearPagePollers();
  updateActiveNav();
  const hash = location.hash || '#/';
  // Ancres intra-page (ex. #h-env depuis le TOC d'Aide) : on laisse le
  // navigateur scroller, on ne re-render rien -- sinon on perd la page courante.
  if (hash && !hash.startsWith('#/')) return;
  if (STATE.loading) await loadAll();
  const content = $('#content');
  // RM-1 v1 : "silent route" pour les refresh same-page post-action.
  // Si on reste sur la meme page (refresh post-CRUD), pas de page-loader
  // qui flash. La nouvelle DOM remplace l'ancienne d'un coup, sans etat
  // intermediaire vide. Sur vraie navigation (hash change), loader normal.
  const samePage = (hash === _lastRoutedHash);
  if (!silent && !samePage) {
    content['innerHTML'] = '<div class="page-loader"><div class="spinner"></div><span>Chargement…</span></div>';
  }
  _lastRoutedHash = hash;
  try {
    if (hash === '#/') return await renderHome();
    if (hash === '#/mcps') return await renderMCPs();
    if (hash === '#/plugins') return await renderPlugins();
    if (hash === '#/skills') return await renderSkills();
    if (hash === '#/templates') return await renderTemplates();
    if (hash === '#/tools') return await renderTools();
    if (hash === '#/aide' || hash.startsWith('#/aide/')) return await renderHelp();
    const m = hash.match(/^#\/workspace\/([a-zA-Z0-9_-]+)$/);
    if (m) return await renderWorkspace(m[1]);
    location.hash = '#/';
  } catch (e) {
    content['innerHTML'] = `<div class="error-box">Erreur : ${escapeHtml(e.message)}</div>`;
  }
}

window.addEventListener('hashchange', route);
