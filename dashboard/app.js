/* ================================================================
   Nebula — Claude Workspace Dashboard
   Vanilla JS SPA — no dependencies, no CDN
   ================================================================ */
'use strict';

/* Foundations extraites en modules charges avant ce fichier dans
   index.html : js/icons.js, js/utils.js, js/state.js, js/api.js,
   js/theme.js. Ref CM-2 split, refactor 2026-05-13. */

/* Toast / Snackbar et Modal / confirmDialog extraits en js/toast.js
   et js/modal.js. Factories btn et el deplacees vers js/utils.js. */

/* Navigation (sidebar, breadcrumbs, topbar actions) extraite en js/nav.js. */

/* Router (loadAll, route, _lastRoutedHash, hashchange) extrait en js/router.js. */

/* Page Home (renderHome, buildHomeQuickstart, workspaceCard, loadSanity,
   loadJournal) extraite en js/pages/home.js. */


/* ================================================================
   PAGE WORKSPACE (refonte 2026-10) : en-tete + chiffres + 5 onglets
   ----------------------------------------------------------------
   Onglets Memoire / Configuration / Extensions / Sessions / Fichiers,
   memorises dans l'URL (#/workspace/<id>/<onglet>, replaceState : pas
   d'entree d'historique). Chaque onglet est monte au PREMIER affichage
   (lazy) puis conserve : basculer d'onglet ne detruit rien.
   Re-rendu de la meme page (silent route apres une action, lancement...) :
   les panneaux en cours d'edition (CLAUDE.md, settings.json, fichier
   ouvert dans l'explorateur) sont TRANSPLANTES tels quels dans la
   nouvelle page, jamais recrees. Les conteneurs [data-ws-session-actions]
   et [data-ws-state] restent les cibles du polling des sessions.
   ================================================================ */
const WS_TABS = [
  ['memoire', 'Mémoire'],
  ['config', 'Configuration'],
  ['extensions', 'Extensions'],
  ['sessions', 'Sessions'],
  ['fichiers', 'Fichiers'],
];
const WS_TAB_KEYS = WS_TABS.map(t => t[0]);
// Page workspace courante : { wsId, root, tab, panels: {key: {el, mounted,
// isDirty}} }. null hors page workspace.
let WS_PAGE = null;

// Actions de session (en-tete du detail). Reconstruites en place par le
// polling (router.js refreshSessionNodes) : running -> Stop + Reprendre ;
// idle (« Terminal ouvert ») -> Fermer le terminal + Reprendre ;
// sinon -> Reprendre (si sessions) + Lancer.
function wsSessionActions(w) {
  const st = sessionState(w.id);
  const out = [];
  if (st) {
    const stop = btn(st === 'idle' ? 'Fermer le terminal' : 'Stop', 'btn-danger-outline', st === 'idle' ? I.x : I.stop);
    stop.title = st === 'idle' ? 'Fermer la fenêtre cmd restée ouverte' : 'Arrêter la session Claude Code en cours pour ce workspace';
    stop.addEventListener('click', () => doStop(w));
    const resume = btn('Reprendre', 'btn-primary', st === 'idle' ? I.play : I.terminal);
    resume.title = 'Reprendre la dernière session Claude Code';
    resume.addEventListener('click', () => doResume(w, resume));
    out.push(stop, resume);
  } else {
    if (((STATE.stats || {})[w.id] || {}).sessions) {
      const resume = btn('Reprendre', 'btn', I.ret);
      resume.title = 'Reprendre la dernière session Claude Code';
      resume.addEventListener('click', () => doResume(w, resume));
      out.push(resume);
    }
    const launch = btn('Lancer', 'btn-primary', I.play);
    launch.addEventListener('click', () => doLaunch(w, launch));
    out.push(launch);
  }
  return out;
}

// Compteur de l'onglet Extensions = MCPs actifs + skills locaux + plugins
// actifs (comme le prototype). Skills et plugins ne sont pas dans STATE :
// memorises ici a chaque chargement de l'onglet (loadWsSkills /
// loadWsPlugins) ou par wsPrefetchExtCounts a l'ouverture de la page.
const WS_EXT_COUNTS = {};   // ws_id -> { skills, plugins }

function wsTabCounts(w) {
  const s = (STATE.stats || {})[w.id] || {};
  const x = WS_EXT_COUNTS[w.id] || {};
  return {
    extensions: ((STATE.wsMcps || {})[w.id] || { active: [] }).active.length + (x.skills || 0) + (x.plugins || 0),
    sessions: s.sessions || 0,
  };
}

// Met a jour un compte (skills | plugins) puis le chiffre de l'onglet.
function wsSetExtCount(wsId, key, n) {
  (WS_EXT_COUNTS[wsId] = WS_EXT_COUNTS[wsId] || {})[key] = n;
  if (!WS_PAGE || WS_PAGE.wsId !== wsId || !WS_PAGE.root.isConnected) return;
  const ct = WS_PAGE.root.querySelector('#ws-tab-extensions .ct');
  if (ct) ct.textContent = String(wsTabCounts(WS_PAGE.w).extensions);
  requestAnimationFrame(placeWsTabInd);
}

// Deux GET legers (listing de dossiers) en arriere-plan, uniquement si
// l'onglet Extensions n'est pas celui qu'on monte (il les charge lui-meme).
function wsPrefetchExtCounts(wsId) {
  API.get(`/api/workspaces/${wsId}/skills`)
    .then(r => wsSetExtCount(wsId, 'skills', (r.local || []).length)).catch(() => {});
  API.get(`/api/workspaces/${wsId}/plugins`)
    .then(r => wsSetExtCount(wsId, 'plugins', Object.values(r.plugins || {}).filter(p => p && p.effective).length)).catch(() => {});
}

async function renderWorkspace(wsId, tab) {
  const w = STATE.workspaces.find(x => x.id === wsId);
  if (!w) {
    $('#content').innerHTML = `<div class="page"><div class="error-box">Workspace introuvable : <span class="mono">${escapeHtml(wsId)}</span>. <a class="btn btn-sm" href="#/">Retour à l'accueil</a></div></div>`;
    WS_PAGE = null;
    return;
  }
  setBreadcrumbs([
    { label: 'Workspaces', href: '#/' },
    { label: w.label || w.id },
  ]);

  // Boutons de session dans un conteneur cible : le polling des sessions
  // les remplace en place (explorer / editeurs preserves).
  const sessionBox = el('span', 'ws-session-actions');
  sessionBox.dataset.wsSessionActions = w.id;
  sessionBox.append(...wsSessionActions(w));
  const sync = btn('Sync MCPs', 'btn', I.refresh);
  sync.title = 'Synchronise le registre MCP vers le .mcp.json de ce workspace';
  sync.addEventListener('click', () => withBusy(sync, async () => {
    try {
      const r = await API.post(`/api/workspaces/${w.id}/sync-mcps`, {});
      toastOk('Sync : ' + (r.applied || []).length + ' MCP(s) appliqués');
      warnHandEdited([syncNotice(w.id, r)]);
    } catch (e) { toastErr(e.message); }
  }));
  // Ordre : actions secondaires a gauche, action primaire a droite.
  setTopbarActions([sync, sessionBox]);

  // Panneaux en cours d'edition de la page precedente (meme workspace) :
  // transplantes dans la nouvelle page au lieu d'etre recrees.
  const prev = (WS_PAGE && WS_PAGE.wsId === wsId && WS_PAGE.root && WS_PAGE.root.isConnected) ? WS_PAGE : null;
  const keep = {};
  if (prev) {
    for (const [k, p] of Object.entries(prev.panels)) {
      if (p.mounted && p.isDirty && p.isDirty()) keep[k] = p;
    }
  }

  const stats = (STATE.stats || {})[w.id] || {};
  const counts = wsTabCounts(w);
  const current = WS_TAB_KEYS.includes(tab) ? tab : (prev && prev.tab) || 'memoire';
  const animate = !prev;
  const r = (i) => animate ? ` rise" style="--i:${i}` : '';

  const page = el('div', 'page ws-page');
  page.innerHTML = `
    <nav class="crumbs${r(0)}" aria-label="Fil d'Ariane"><a href="#/">Workspaces</a>${I.right}<span aria-current="page">${escapeHtml(w.label || w.id)}</span></nav>
    <header class="wsh${r(0)}">
      ${wsGem(w)}
      <div style="min-width:0">
        <h1>${escapeHtml(w.label || w.id)}${wsStateMarker(w.id, 'header')}<span data-ws-si></span></h1>
        <div class="ws-pathline"><span class="mono" title="${escapeHtml(w.path || '')}">${escapeHtml(w.path || '')}</span><button type="button" data-copy-path aria-label="Copier le chemin" title="Copier le chemin">${I.copy}</button></div>
        ${w.description ? `<p>${escapeHtml(w.description)}</p>` : ''}
        <div class="state-badges">${stateBadgesHtml(w)}</div>
      </div>
      <div data-page-actions></div>
    </header>
    <section class="card ws-stats${r(2)}" aria-label="Statistiques">
      <div class="ws-stat"><span>Sessions</span><b data-count="${stats.sessions || 0}">${fmtNum(stats.sessions || 0)}</b></div>
      <div class="ws-stat"><span>Messages</span><b data-count="${stats.messages || 0}">${fmtNum(stats.messages || 0)}</b></div>
      <div class="ws-stat"><span>Tokens entrée</span><b title="${fmtNum(stats.input_tokens || 0)}">${escapeHtml(fmtCompact(stats.input_tokens || 0))}</b></div>
      <div class="ws-stat"><span>Tokens sortie</span><b title="${fmtNum(stats.output_tokens || 0)}">${escapeHtml(fmtCompact(stats.output_tokens || 0))}</b></div>
      <div class="ws-stat"><span>Cache lu</span><b title="${fmtNum(stats.cache_read_tokens || 0)}">${escapeHtml(fmtCompact(stats.cache_read_tokens || 0))}</b></div>
      <div class="ws-stat"><span>Dernière activité</span><b class="s">${escapeHtml(stats.last ? fmtDateTime(stats.last) : 'jamais')}</b></div>
    </section>
    <div class="ws-tabbar${r(3)}">
      <div class="ws-tabs" role="tablist" aria-label="Sections du workspace">${WS_TABS.map(([k, l]) =>
        `<button class="ws-tab" type="button" role="tab" id="ws-tab-${k}" aria-controls="ws-panel-${k}" aria-selected="${k === current}" tabindex="${k === current ? 0 : -1}" data-tab="${k}">${l}${counts[k] != null ? `<span class="ct">${counts[k]}</span>` : ''}<span class="dirty" hidden title="Modifications non sauvegardées"></span></button>`).join('')}</div>
      <span class="ws-tab-ind" aria-hidden="true"></span>
      <div class="ws-maint"></div>
    </div>
    ${WS_TABS.map(([k]) => `<section class="ws-tabpanel" id="ws-panel-${k}" role="tabpanel" aria-labelledby="ws-tab-${k}" tabindex="0" data-panel="${k}" hidden></section>`).join('')}
  `;

  // Copier le chemin
  page.querySelector('[data-copy-path]').addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(w.path || ''); toastOk('Chemin copié'); }
    catch { toastErr('Copie impossible : sélectionne le chemin à la main'); }
  });
  bindStateBadges(page.querySelector('.wsh'), w);

  // Maintenance : Modifier / Dupliquer / Exporter / Dossier groupes,
  // Supprimer isole spatialement (bordure rouge permanente).
  const maint = page.querySelector('.ws-maint');
  const editBtn = btn('Modifier', 'btn-sm btn-ghost', I.edit);
  editBtn.title = "Modifier le nom, l'emoji, la description, le chemin";
  editBtn.addEventListener('click', () => modalEditWorkspace(w));
  const dupBtn = btn('Dupliquer', 'btn-sm btn-ghost', I.copy);
  dupBtn.title = 'Créer un nouveau workspace à partir de celui-ci';
  dupBtn.addEventListener('click', () => modalDuplicateWorkspace(w));
  const exportBtn = btn('Exporter', 'btn-sm btn-ghost', I.download);
  exportBtn.title = 'Télécharger un ZIP du workspace';
  // POST + X-Nebula-XHR (le zip contient des secrets) -> fetch + Blob,
  // jamais window.location (le header ne serait pas posé).
  exportBtn.addEventListener('click', () => withBusy(exportBtn, async () => {
    try {
      const name = await API.download('POST', `/api/workspaces/${w.id}/export`, `${w.id}.zip`, {});
      toastOk(`Export téléchargé : ${name}`);
    } catch (e) { toastErr(`Export impossible : ${e.message}`); }
  }));
  const openBtn = btn('Dossier', 'btn-sm btn-ghost', I.folder);
  openBtn.title = "Ouvrir le dossier du workspace dans l'explorateur";
  openBtn.addEventListener('click', async () => {
    try { const r2 = await API.post('/api/open', { target: `workspace-dir:${w.id}` }); toastOk(r2.message); }
    catch (e) { toastErr(e.message); }
  });
  const delBtn = btn('Supprimer', 'btn-sm btn-danger-outline', I.trash);
  delBtn.title = 'Supprimer ce workspace (action destructive, confirmation demandée)';
  delBtn.addEventListener('click', () => modalDeleteWorkspace(w));
  maint.append(editBtn, dupBtn, exportBtn, openBtn, delBtn);

  // Onglets : clic + fleches / Debut / Fin (motif ARIA tabs).
  const tabs = page.querySelector('.ws-tabs');
  tabs.addEventListener('click', (e) => { const b = e.target.closest('.ws-tab'); if (b) wsSelectTab(b.dataset.tab, true); });
  tabs.addEventListener('keydown', (e) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return;
    e.preventDefault();
    let i = WS_TAB_KEYS.indexOf(WS_PAGE.tab);
    i = e.key === 'Home' ? 0 : e.key === 'End' ? WS_TAB_KEYS.length - 1
      : (i + (e.key === 'ArrowRight' ? 1 : -1) + WS_TAB_KEYS.length) % WS_TAB_KEYS.length;
    wsSelectTab(WS_TAB_KEYS[i], true);
    page.querySelector(`#ws-tab-${WS_TAB_KEYS[i]}`).focus();
  });

  const panels = {};
  for (const [k] of WS_TABS) {
    const host = page.querySelector(`#ws-panel-${k}`);
    if (keep[k]) {
      host.replaceChildren(...keep[k].el.childNodes);
      panels[k] = { el: host, mounted: true, isDirty: keep[k].isDirty };
    } else {
      panels[k] = { el: host, mounted: false, isDirty: () => false };
    }
  }

  const c = $('#content');
  c.replaceChildren(page);
  WS_PAGE = { wsId, w, root: page, tab: current, panels };
  wsRefreshSiBadge();
  wsSelectTab(current, false);
  if (animate) countUp(page);
  wsUpdateDirtyDots();
  if (current !== 'extensions' && !prev) wsPrefetchExtCounts(wsId);
}

// Bascule d'onglet depuis le hash (lien, palette, historique) sans re-rendu.
function wsSwitchTabFromHash(hash) {
  const m = hash.match(/^#\/workspace\/([a-zA-Z0-9_-]+)(?:\/([a-z]+))?$/);
  if (!m || !WS_PAGE || WS_PAGE.wsId !== m[1] || !WS_PAGE.root.isConnected) return false;
  wsSelectTab(WS_TAB_KEYS.includes(m[2]) ? m[2] : 'memoire', false);
  return true;
}

function placeWsTabInd() {
  if (!WS_PAGE || !WS_PAGE.root.isConnected) return;
  const on = WS_PAGE.root.querySelector('.ws-tab[aria-selected="true"]');
  const ind = WS_PAGE.root.querySelector('.ws-tab-ind');
  if (!on || !ind) return;
  ind.style.transform = `translateX(${on.offsetLeft}px) scaleX(${on.offsetWidth / 100})`;
}
window.addEventListener('resize', debounce(placeWsTabInd, 80));

function wsSelectTab(key, user) {
  if (!WS_PAGE) return;
  if (!WS_TAB_KEYS.includes(key)) key = 'memoire';
  const { root, panels } = WS_PAGE;
  WS_PAGE.tab = key;
  root.querySelectorAll('.ws-tab').forEach(b => {
    const on = b.dataset.tab === key;
    b.setAttribute('aria-selected', String(on));
    b.tabIndex = on ? 0 : -1;
  });
  for (const [k, p] of Object.entries(panels)) p.el.hidden = (k !== key);
  const p = panels[key];
  if (!p.mounted) wsMountPanel(key);
  if (user && motionOK()) { p.el.classList.remove('fade-in'); void p.el.offsetWidth; p.el.classList.add('fade-in'); }
  requestAnimationFrame(placeWsTabInd);
  const h = `#/workspace/${WS_PAGE.wsId}/${key}`;
  if (location.hash !== h) {
    history.replaceState(null, '', h);
    _lastRoutedHash = h;
  }
}

// Monte (ou remonte) un onglet. Remonter n'arrive que si le panneau n'est
// pas en cours d'edition (cf. wsRefreshPanels).
function wsMountPanel(key) {
  if (!WS_PAGE) return;
  const w = WS_PAGE.w;
  const p = WS_PAGE.panels[key];
  p.el.replaceChildren();
  p.mounted = true;
  p.isDirty = () => false;
  if (key === 'memoire') mountWsMemoryTab(w, p);
  else if (key === 'config') mountWsConfigTab(w, p);
  else if (key === 'extensions') mountWsExtensionsTab(w, p);
  else if (key === 'sessions') mountWsSessionsTab(w, p);
  else if (key === 'fichiers') mountWsFilesTab(w, p);
}

// Rafraichit des onglets apres une action (au lieu d'un route() qui
// reconstruisait toute la page) : recharge eventuellement STATE, puis
// remonte chaque onglet DEJA monte et non modifie ; un onglet en cours
// d'edition est laisse intact. Met a jour les compteurs des onglets.
async function wsRefreshPanels(keys, { reload = false } = {}) {
  if (!WS_PAGE) return;
  const wsId = WS_PAGE.wsId;
  if (reload) {
    // panelsReloading : ce STATE.loading-ci n'est pas une navigation
    // post-mutation, la garde de navigation reste active (js/router.js).
    STATE.loading = true;
    STATE.panelsReloading = true;
    try { await loadAll(); } finally { STATE.loading = false; STATE.panelsReloading = false; }
  }
  if (!WS_PAGE || WS_PAGE.wsId !== wsId || !WS_PAGE.root.isConnected) return;
  const w = STATE.workspaces.find(x => x.id === wsId);
  if (w) WS_PAGE.w = w;
  for (const k of keys) {
    const p = WS_PAGE.panels[k];
    if (!p || !p.mounted) continue;
    if (p.isDirty()) {
      // Panneau en cours d'edition laisse intact : prevenir qu'il est perime
      // (l'enregistrer ecraserait ce qui vient d'etre ecrit ailleurs).
      const tab = (WS_TABS.find(t => t[0] === k) || [k, k])[1];
      toast(`Onglet ${tab} : le fichier a changé pendant ton édition. Annule tes modifications pour voir la nouvelle version, ou enregistre en connaissance de cause (cela écrase la modification).`, 'info', 10000);
      continue;
    }
    if (k === WS_PAGE.tab) wsMountPanel(k); else p.mounted = false;
  }
  const counts = wsTabCounts(WS_PAGE.w);
  for (const [k, n] of Object.entries(counts)) {
    const ct = WS_PAGE.root.querySelector(`#ws-tab-${k} .ct`);
    if (ct) ct.textContent = String(n);
  }
  requestAnimationFrame(placeWsTabInd);
}

// Quitter / recharger l'onglet du navigateur avec une edition non
// enregistree (CLAUDE.md, settings.json, fichier de l'explorateur).
window.addEventListener('beforeunload', (e) => {
  if (WS_PAGE && WS_PAGE.root && WS_PAGE.root.isConnected
      && Object.values(WS_PAGE.panels).some(p => p.mounted && p.isDirty())) {
    e.preventDefault(); e.returnValue = '';
  }
});

// Pastille « modifie » sur les onglets en cours d'edition.
function wsUpdateDirtyDots() {
  if (!WS_PAGE) return;
  for (const [k, p] of Object.entries(WS_PAGE.panels)) {
    const dot = WS_PAGE.root.querySelector(`#ws-tab-${k} .dirty`);
    if (dot) dot.hidden = !(p.mounted && p.isDirty());
  }
}

// Badge « Auto-amelioration » de l'en-tete (etat /api/overview) : renvoie
// vers le module dans l'onglet Configuration.
function wsRefreshSiBadge() {
  if (!WS_PAGE) return;
  const slot = WS_PAGE.root.querySelector('[data-ws-si]');
  if (!slot) return;
  if (!wsHasOverlay(WS_PAGE.wsId)) { slot.replaceChildren(); return; }
  slot['innerHTML'] = `<button type="button" class="pill info" title="Auto-amélioration de Claude active : voir le module dans l'onglet Configuration">${I.selfImprove}Auto-amélioration</button>`;
  slot.firstElementChild.addEventListener('click', () => {
    wsSelectTab('config', true);
    const mod = WS_PAGE.root.querySelector('#ws-panel-config .mods');
    if (mod) mod.scrollIntoView({ behavior: motionOK() ? 'smooth' : 'auto', block: 'nearest' });
  });
}

// Carte d'editeur : barre de fichier + corps + pied (etat, Annuler / Sauvegarder).
function edCard(name, icon) {
  const card = el('div', 'card ed');
  card['innerHTML'] = `
    <div class="ed-bar"><span class="fn">${icon || I.file}<span>${escapeHtml(name)}</span></span><span class="r"></span></div>
    <div class="ed-slot"></div>
    <div class="ed-foot"><span class="vstate" aria-live="polite"></span><span class="lc"></span><span class="r"><span class="dim" aria-hidden="true"><kbd class="k">Ctrl</kbd> <kbd class="k">S</kbd></span></span></div>`;
  return {
    card,
    bar: card.querySelector('.ed-bar .r'),
    slot: card.querySelector('.ed-slot'),
    vstate: card.querySelector('.vstate'),
    lc: card.querySelector('.lc'),
    foot: card.querySelector('.ed-foot .r'),
  };
}

/* ---- Editeur Markdown leger ---------------------------------------
   Meme principe que js/json-editor.js : textarea transparente sur un
   <pre> colore + goutiere, defilement commun (un seul conteneur). Tab
   n'est PAS intercepte (la page n'est pas une modale : Tab doit sortir). */
function _mdHighlight(src) {
  return escapeHtml(src).split('\n').map(l => {
    if (/^#{1,6}\s/.test(l)) return `<span class="mdh">${l}</span>`;
    return l.replace(/(\*\*[^*]+\*\*)/g, '<span class="mdb">$1</span>')
      .replace(/(`[^`]+`)/g, '<span class="mdc">$1</span>')
      .replace(/^(\s*[-*+]|\s*\d+\.)(\s)/, '<span class="mdl">$1</span>$2');
  }).join('\n');
}
function createMdEditor({ value = '', ariaLabel = 'Contenu', readOnly = false, onChange = null, onSave = null } = {}) {
  const root = el('div', 'md-body');
  root['innerHTML'] = `<div class="md-gut" aria-hidden="true"></div><div class="md-src"><pre aria-hidden="true"></pre><textarea spellcheck="false"></textarea></div>`;
  const gut = root.querySelector('.md-gut');
  const pre = root.querySelector('pre');
  const ta = root.querySelector('textarea');
  ta.setAttribute('aria-label', ariaLabel);
  ta.readOnly = readOnly;
  ta.value = String(value).replace(/^\uFEFF/, '').replace(/\r\n/g, '\n');
  let lines = 0;
  let raf = 0;
  const paint = () => {
    raf = 0;
    const v = ta.value;
    pre['innerHTML'] = _mdHighlight(v) + '\n';
    const n = v.split('\n').length;
    if (n !== lines) {
      lines = n;
      gut['innerHTML'] = Array.from({ length: n }, (_, i) => `<div>${i + 1}</div>`).join('');
    }
  };
  ta.addEventListener('input', () => {
    if (!raf) raf = requestAnimationFrame(paint);
    if (onChange) onChange();
  });
  ta.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && !e.altKey && e.key.toLowerCase() === 's') { e.preventDefault(); if (onSave) onSave(); }
  });
  paint();
  return {
    el: root,
    textarea: ta,
    getValue: () => ta.value,
    setValue: (v) => { ta.value = String(v); paint(); },
    lineCount: () => ta.value.split('\n').length,
  };
}

/* ---- Onglet Memoire : CLAUDE.md + raccourcis de configuration ------ */
function mountWsMemoryTab(w, panel) {
  const grid = el('div', 'two');
  const left = el('div');
  const right = el('div', 'card flush');
  right['innerHTML'] = `<div class="card-h"><h3>Fichiers de configuration</h3></div><div class="card-b qlist"></div>`;
  const q = right.querySelector('.qlist');
  const items = [
    [I.book, 'notes.md', 'Notes libres du workspace', () => openWsFile(w.id, 'notes.md')],
    [I.code, 'settings.json', 'Permissions, plugins, hooks', () => wsSelectTab('config', true)],
    [I.shield, 'Permissions', 'Règles allow / deny', () => modalPermissions(w.id, () => wsRefreshPanels(['config']))],
    [I.zap, 'Hooks', 'Commandes déclenchées par Claude Code', () => modalHooks(w.id, () => wsRefreshPanels(['config']))],
    [I.cpu, 'Agents et commandes', 'Onglet Extensions', () => wsSelectTab('extensions', true)],
  ];
  for (const [icon, t, d, fn] of items) {
    const b = el('button', 'qi', `<span class="qic">${icon}</span><span><b>${escapeHtml(t)}</b><small>${escapeHtml(d)}</small></span>${I.right}`);
    b.type = 'button';
    b.addEventListener('click', fn);
    q.appendChild(b);
  }
  grid.append(left, right);
  panel.el.appendChild(grid);
  renderWsClaudeMdInline(w.id, left, panel);
}

/* ---- Onglet Configuration : modules + settings.json + permissions/hooks */
function mountWsConfigTab(w, panel) {
  const modulesHost = el('div');
  panel.el.appendChild(modulesHost);
  if ((STATE.overlays || []).length) renderWsOverlays(w.id, modulesHost);
  const grid = el('div', 'two');
  const left = el('div');
  const right = el('div', 'col');
  grid.append(left, right);
  panel.el.appendChild(grid);
  left.innerHTML = '<div class="dim" style="padding:var(--sp-3)">Chargement de settings.json…</div>';

  (async () => {
    let data;
    try { data = await API.get(`/api/workspaces/${w.id}/settings`); }
    catch (e) { left.innerHTML = `<div class="error-box">${escapeHtml(e.message)}</div>`; return; }
    let saved = data.content || '{}';
    const ed = edCard('.claude/settings.json', I.code);
    let dirty = false;
    const save = btn('Sauvegarder', 'btn-sm btn-primary', I.check);
    save.title = 'Ctrl+S';
    const cancel = btn('Annuler', 'btn-sm btn-ghost');
    let editor = null;
    const refresh = () => {
      if (!editor) return;
      dirty = editor.getValue() !== saved;
      // Validite + nombre de lignes : barre de l'editeur JSON ; ici l'etat d'enregistrement.
      ed.vstate.className = 'vstate ' + (dirty ? 'dirty' : 'ok');
      ed.vstate['innerHTML'] = dirty ? `${I.edit}Modifié, non enregistré` : `${I.check}Enregistré`;
      save.disabled = !dirty || !editor.isValid();
      wsUpdateDirtyDots();
    };
    const doSave = () => withBusy(save, async () => {
      if (!editor.validate().ok) { toastErr("JSON invalide : corrige-le avant d'enregistrer"); return; }
      try {
        await API.post(`/api/workspaces/${w.id}/settings`, { content: editor.getValue() });
        saved = editor.getValue();
        toastOk('settings.json enregistré');
      } catch (e) { toastErr(e.message); }
    }).finally(refresh);
    editor = createJsonEditor({
      value: saved, ariaLabel: 'Contenu de .claude/settings.json',
      onChange: () => refresh(),
      onSave: () => { if (!save.disabled) doSave(); },
      onValidChange: () => refresh(),
    });
    saved = editor.getValue();
    save.addEventListener('click', doSave);
    cancel.addEventListener('click', () => { if (dirty) { editor.setValue(saved); refresh(); } });
    ed.foot.append(cancel, save);
    ed.slot.replaceWith(editor.el);
    left.replaceChildren(ed.card);
    panel.isDirty = () => dirty;
    refresh();

    // Cartes Permissions / Hooks : resume lu dans settings.json enregistre.
    let parsed = {};
    try { parsed = JSON.parse(saved) || {}; } catch { parsed = {}; }
    const perms = parsed.permissions || {};
    const allow = Array.isArray(perms.allow) ? perms.allow : [];
    const deny = Array.isArray(perms.deny) ? perms.deny : [];
    const tot = allow.length + deny.length;
    const pc = el('div', 'card flush');
    pc['innerHTML'] = `<div class="card-h"><h3>${I.shield} Permissions</h3><span class="r"></span></div><div class="card-b">
      <div class="muted" style="font-size:13px"><b style="color:var(--text)">${allow.length}</b> autorisée${allow.length > 1 ? 's' : ''}, <b style="color:var(--text)">${deny.length}</b> refusée${deny.length > 1 ? 's' : ''}</div>
      ${tot ? `<div class="meter" aria-hidden="true"><i style="width:${allow.length / tot * 100}%;background:var(--ok)"></i><i style="width:${deny.length / tot * 100}%;background:var(--err)"></i></div>` : ''}
      <div class="perm">${deny.slice(0, 8).map(x => `<span class="chip deny" title="Refusée">${escapeHtml(x.replace(/^Bash\((.*)\)$/, '$1'))}</span>`).join('')}${deny.length > 8 ? `<span class="chip more">+${deny.length - 8}</span>` : ''}</div></div>`;
    const pe = btn('Éditer', 'btn-sm btn-ghost');
    pe.addEventListener('click', () => modalPermissions(w.id, () => wsRefreshPanels(['config'])));
    pc.querySelector('.r').appendChild(pe);
    const hooks = parsed.hooks && typeof parsed.hooks === 'object' ? parsed.hooks : {};
    const hookRows = [];
    for (const [ev, arr] of Object.entries(hooks)) {
      for (const h of (Array.isArray(arr) ? arr : [])) {
        const cmds = (h.hooks || []).map(x => String(x.command || '').split(/[\\/]/).pop().replace(/["']/g, '')).filter(Boolean);
        hookRows.push(`<div class="hl"><span class="hi ok">${I.zap}</span><div><b>${escapeHtml(ev)}${h.matcher ? ` sur ${escapeHtml(h.matcher)}` : ''}</b><span class="d mono">${escapeHtml(cmds.join(', ') || '(commande vide)')}</span></div></div>`);
      }
    }
    const hc = el('div', 'card flush');
    hc['innerHTML'] = `<div class="card-h"><h3>${I.zap} Hooks</h3><span class="r"></span></div><div class="card-b health">${hookRows.join('') || '<p class="dim" style="margin:0;font-size:13px">Aucun hook dans ce workspace.</p>'}</div>`;
    const he = btn('Éditer', 'btn-sm btn-ghost');
    he.addEventListener('click', () => modalHooks(w.id, () => wsRefreshPanels(['config'])));
    hc.querySelector('.r').appendChild(he);
    right.replaceChildren(pc, hc);
  })();
}

/* ---- Onglet Extensions : MCPs / Skills + agents & commandes / Plugins */
function mountWsExtensionsTab(w, panel) {
  const grid = el('div', 'three');
  const mk = (icon, title) => {
    const card = el('div', 'card flush');
    card['innerHTML'] = `<div class="card-h"><h3>${icon} ${escapeHtml(title)}</h3><span class="r"></span></div><div class="card-b"><div class="xlist"></div></div>`;
    grid.appendChild(card);
    return { card, r: card.querySelector('.card-h .r'), list: card.querySelector('.xlist'), body: card.querySelector('.card-b') };
  };
  const mcps = mk(I.cpu, 'MCPs');
  const nAct = ((STATE.wsMcps || {})[w.id] || { active: [] }).active.length;
  mcps.r['innerHTML'] = `<span class="pill mute">${nAct} sur ${(STATE.mcps || []).length}</span>`;
  renderWsMCPs(w.id, mcps.list);
  const skills = mk(I.sparkle, 'Skills');
  loadWsSkills(w.id, skills.list);
  skills.body.appendChild(el('div', 'xsub', 'Agents et commandes'));
  const items = el('div', 'stack');
  skills.body.appendChild(items);
  loadFileItems(w.id, items);
  const plugins = mk(I.plug, 'Plugins');
  loadWsPlugins(w.id, plugins.list);
  panel.el.appendChild(grid);
}

/* ---- Onglet Sessions : tableau (date, 1er message, messages, tokens) */
function mountWsSessionsTab(w, panel) {
  const host = el('div');
  panel.el.appendChild(host);
  loadSessions(w.id, host);
}

/* ---- Onglet Fichiers : explorateur + editeur (etat local preserve) -- */
function mountWsFilesTab(w, panel) {
  renderWsFileExplorer(w.id, panel.el, panel);
}

/* ================================================================
   MODULES OPTIONNELS (overlays) -- onglet Configuration
   ================================================================
   Bloc « Auto-amelioration de Claude » (overlay claude-self-improving) et
   tout autre overlay disponible : etat actif / inactif, ce que le module
   installe, Activer (modale de bootstrap) ou Re-appliquer (ne copie que
   les fichiers manquants). Idempotent cote backend.
   ================================================================ */
const SELF_IMPROVING_FEATURES = [
  [I.book, 'Mémoire structurée', '<code>.claude/memory/</code> : hubs architecture, pitfalls, conventions…'],
  [I.activity, "Pipeline d'amélioration", '<code>ideas</code> → <code>backlog</code> → <code>improvements</code>, + roadmap'],
  [I.cpu, 'Agents et commandes', 'expert, validateur, auditeur ; <code>/pipeline</code>, <code>/brainstorm</code>, <code>/check-all</code>…'],
  [I.shield, 'Hooks Python pré-commit', 'em-dash, Co-Authored-By, fichiers protégés'],
];

async function renderWsOverlays(wsId, host) {
  // Re-fetch l'etat actif/inactif pour ce workspace specifiquement (les
  // STATE.overlays globaux ne portent pas l'info active=true|false).
  let overlays;
  try {
    const r = await API.get(`/api/workspaces/${wsId}/overlays`);
    overlays = r.overlays || [];
  } catch (e) {
    host.innerHTML = `<section class="card mods"><div class="mod-err">Impossible de charger les modules optionnels : ${escapeHtml(e.message)}</div></section>`;
    return;
  }
  if (!overlays.length) { host.innerHTML = ''; return; }
  // Auto-amelioration en tete (module mis en avant).
  overlays.sort((a, b) => (b.id === SELF_IMPROVING_ID) - (a.id === SELF_IMPROVING_ID));
  // Etat local (badge en-tete + indicateur accueil) aligne sur la reponse.
  const act = overlays.filter(o => o.active).map(o => o.id);
  if (act.length) STATE.overlaysActive[wsId] = act; else delete STATE.overlaysActive[wsId];
  if (WS_PAGE && WS_PAGE.wsId === wsId) wsRefreshSiBadge();

  const box = el('section', 'card mods');
  box.setAttribute('aria-label', 'Modules optionnels');
  for (const ov of overlays) {
    const si = ov.id === SELF_IMPROVING_ID;
    const n = ov.file_count || 0;
    const row = el('div', 'mod' + (ov.active ? ' on' : ''));
    row.dataset.mod = ov.id;
    row['innerHTML'] = `
      <span class="mod-ic" aria-hidden="true">${escapeHtml(ov.emoji || '🧩')}</span>
      <div style="min-width:0">
        <div class="mod-h"><h3>${escapeHtml(ov.label || ov.id)}</h3>${ov.active ? '<span class="pill ok"><span class="sdot"></span>Actif</span>' : '<span class="pill mute">Inactif</span>'}</div>
        <p>${si ? "Claude tient une mémoire de projet, trie ses propres idées d'amélioration et vérifie son travail avant chaque commit." : escapeHtml(ov.description || '')}</p>
        ${si && ov.active ? '<button type="button" class="mod-more" aria-expanded="false">Ce que le module installe ' + I.right + '</button>' : ''}
        ${si ? `<ul class="mod-feat">${SELF_IMPROVING_FEATURES.map(([ic, t, d]) => `<li><span class="fi">${ic}</span><span><b>${escapeHtml(t)}</b>${d}</span></li>`).join('')}</ul>
        <div class="mod-foot">${I.sparkle}<span>Après activation : lancer Claude et dire « bootstrap le projet ». N'écrase aucun fichier existant.</span></div>` : ''}
      </div>
      <div class="mod-act"><small>${n} fichier${n > 1 ? 's' : ''}${ov.active ? '' : ', idempotent'}</small></div>`;
    const actions = row.querySelector('.mod-act');
    const applyBtn = ov.active ? btn('Ré-appliquer', 'btn-sm', I.refresh) : btn('Activer', 'btn-primary', I.plus);
    applyBtn.title = ov.active
      ? "Ré-applique le module : ne copie que les fichiers absents, n'écrase rien."
      : `Copie ${n} fichier(s) dans ce workspace (idempotent, n'écrase rien).`;
    if (!ov.active) applyBtn.setAttribute('aria-label', `Activer ${ov.label || ov.id}`);
    // Le clic ouvre une modale de bootstrap qui collecte mode / langue /
    // auteur / profondeur AVANT d'appliquer (cf. P3).
    applyBtn.addEventListener('click', () => modalApplyOverlay(wsId, ov, host));
    actions.prepend(applyBtn);
    const more = row.querySelector('.mod-more');
    if (more) more.addEventListener('click', () => {
      row.classList.toggle('open');
      more.setAttribute('aria-expanded', String(row.classList.contains('open')));
    });
    box.appendChild(row);
  }
  host.replaceChildren(box);
}

// Modale de bootstrap d'un overlay : mode projet, langue, convention
// auteur (si equipe), profondeur d'install. Pre-remplit les defauts
// suggeres (solo -> minimale ; equipe -> complete) et applique au submit.
function modalApplyOverlay(wsId, ov, host) {
  const body = el('div');
  body.innerHTML = `
    <div class="muted" style="font-size:12px;margin-bottom:10px">
      ${escapeHtml(ov.emoji || '🧩')} <strong>${escapeHtml(ov.label || ov.id)}</strong> —
      ${escapeHtml(ov.description || '')}
    </div>
    <div class="field">
      <label class="field-label">Mode projet</label>
      <select class="select" name="mode">
        <option value="solo">Solo (un seul mainteneur)</option>
        <option value="equipe">Équipe (sans hiérarchie)</option>
        <option value="equipe-hierarchique">Équipe avec hiérarchie (digests actifs)</option>
      </select>
      <div class="muted" style="font-size:11px;margin-top:4px">
        Solo : pas d'attribution d'auteur obligatoire (validate_author=false).
        Équipe : auteur obligatoire sur les items de registres.
        Hiérarchique : ajoute digests/, /digest-week et l'agent digest-compiler.
      </div>
    </div>
    <div class="field-row">
      <div class="field">
        <label class="field-label">Langue</label>
        <select class="select" name="language">
          <option value="fr">Français</option>
          <option value="en">Anglais</option>
          <option value="autre">Autre</option>
        </select>
      </div>
      <div class="field">
        <label class="field-label">Profondeur d'install</label>
        <select class="select" name="depth">
          <option value="minimal">Minimale (overview + improvements)</option>
          <option value="complete">Complète (tout + exemples)</option>
        </select>
      </div>
    </div>
    <div class="field" data-author-field style="display:none">
      <label class="field-label">Convention auteur</label>
      <input class="input mono" name="author" placeholder="ex. antoine.b, ab, @slug">
      <div class="muted" style="font-size:11px;margin-top:4px">
        Identifiant utilisé dans les champs <code>par &lt;author&gt;</code> des registres.
      </div>
    </div>
  `;
  const modeSel = body.querySelector('[name=mode]');
  const depthSel = body.querySelector('[name=depth]');
  const authorField = body.querySelector('[data-author-field]');
  // Defauts suggeres + champ auteur conditionnel au mode equipe.
  const syncMode = () => {
    const m = modeSel.value;
    const team = (m === 'equipe' || m === 'equipe-hierarchique');
    authorField.style.display = team ? '' : 'none';
    // Defaut de profondeur suggere selon le mode (modifiable ensuite).
    depthSel.value = (m === 'solo') ? 'minimal' : 'complete';
  };
  modeSel.addEventListener('change', syncMode);
  syncMode();

  const cancel = btn('Annuler', 'btn-ghost');
  const apply = btn(ov.active ? 'Ré-appliquer' : 'Activer', 'btn-primary', ov.active ? I.refresh : I.plus);
  const { close } = openModal({ title: `Module : ${ov.label || ov.id}`, body, footer: [cancel, apply] });
  cancel.addEventListener('click', close);
  apply.addEventListener('click', () => withBusy(apply, async () => {
    const payload = {
      mode: modeSel.value,
      language: body.querySelector('[name=language]').value,
      depth: depthSel.value,
      author: body.querySelector('[name=author]').value.trim(),
    };
    try {
      const r = await API.post(`/api/workspaces/${wsId}/overlays/${ov.id}`, payload);
      const nc = (r.copied || []).length;
      const na = (r.appended || []).length;
      const nseed = (r.seeded || []).length;
      const ns = (r.skipped || []).length;
      const parts = [];
      if (nc) parts.push(`${nc} ajouté(s)`);
      if (na) parts.push(`${na} fragment(s) CLAUDE.md`);
      if (nseed) parts.push(`${nseed} exemple(s)`);
      if (ns) parts.push(`${ns} ignoré(s)`);
      if (!nc && !na && !nseed) {
        toastOk(`Module déjà complet (${ns} fichier(s) déjà présent(s))`);
      } else {
        toastOk(`Module appliqué · ${parts.join(', ')}`);
      }
      close();
      renderWsOverlays(wsId, host);  // refresh badges + etat (en-tete, accueil)
      // Le module a pu creer / completer CLAUDE.md : l'onglet Memoire est
      // remonte s'il n'est pas en cours d'edition, sinon on previent (un
      // enregistrement ecraserait le fragment ajoute).
      const touchedMd = [...(r.copied || []), ...(r.appended || [])].some(f => /(^|[\\/])CLAUDE\.md$/i.test(String(f)));
      if (touchedMd && WS_PAGE && WS_PAGE.wsId === wsId) {
        const mem = WS_PAGE.panels.memoire;
        if (mem && mem.mounted && mem.isDirty()) toast("CLAUDE.md a été complété par le module : enregistre ou annule tes modifications de l'onglet Mémoire, puis recharge la page pour voir l'ajout.", 'info', 9000);
        else wsRefreshPanels(['memoire']);
      }
    } catch (e) { toastErr(e.message); }
  }));
}

/* ================================================================
   WORKSPACE FILE EXPLORER (Section E sur la page workspace detail)
   ================================================================ */

// Point d'entrée : monte l'explorateur dans `host`. État local porté
// par l'objet `state` pour ne pas polluer STATE global. Tous les fetches
// passent par /api/workspaces/<id>/fs/* (cf. server.py).
async function renderWsFileExplorer(wsId, host, panel = null) {
  const section = el('div', 'ws-fs-section');

  // Header : titre + bouton Nouveau fichier
  const sectionLabel = el('div', 'section-label', 'Fichiers du workspace');
  const headerRow = el('div', 'ws-fs-header');
  const newBtn = btn('Nouveau fichier', 'btn-sm btn-ghost', I.plus);
  newBtn.title = 'Créer un fichier (les dossiers parents sont créés automatiquement)';
  newBtn.addEventListener('click', () => promptNewWsFile(wsId, state));
  headerRow.append(sectionLabel, newBtn);

  // Toolbar : recherche
  const toolbar = el('div', 'ws-fs-toolbar');
  const searchInput = document.createElement('input');
  searchInput.type = 'search';
  searchInput.className = 'input ws-fs-search-input';
  searchInput.placeholder = 'Rechercher dans le workspace…';
  searchInput.spellcheck = false;
  toolbar.appendChild(searchInput);

  // Split : tree à gauche, éditeur à droite
  const split = el('div', 'ws-fs-split');
  const treePane = el('div', 'ws-fs-tree');
  const editorPane = el('div', 'ws-fs-editor');
  split.append(treePane, editorPane);

  section.append(headerRow, toolbar, split);
  host.appendChild(section);

  // État local de cette instance d'explorer
  const state = {
    wsId,
    openFile: null,    // {path, content, mtime, encoding} ou null
    dirty: false,
    treePane,
    editorPane,
    textarea: null,
    dirtyDot: null,
    rootEntries: null, // cache pour restaurer après search
  };
  // Onglet Fichiers : un fichier modifie non sauvegarde protege l'onglet
  // (transplante tel quel si la page workspace est re-rendue).
  if (panel) panel.isDirty = () => !!state.dirty;

  // Rendu initial : éditeur vide + arbre racine
  renderWsFsEmpty(state);
  await loadWsFsSubtree(state, treePane, '');

  // Recherche avec debounce
  let searchTimer = null;
  searchInput.addEventListener('input', () => {
    clearTimeout(searchTimer);
    const q = searchInput.value.trim();
    if (q.length < 2) {
      treePane.innerHTML = '';
      loadWsFsSubtree(state, treePane, '');
      return;
    }
    searchTimer = setTimeout(() => doWsFsSearch(state, q), 300);
  });
}

async function loadWsFsSubtree(state, container, relPath) {
  container.innerHTML = '<div class="dim ws-fs-loading">Chargement…</div>';
  try {
    const r = await API.get(`/api/workspaces/${state.wsId}/fs/tree?path=${encodeURIComponent(relPath)}&depth=1`);
    container.innerHTML = '';
    if (!r.entries || r.entries.length === 0) {
      container.appendChild(el('div', 'dim ws-fs-empty-line', '(dossier vide)'));
      return;
    }
    for (const entry of r.entries) {
      const fullPath = relPath ? `${relPath}/${entry.name}` : entry.name;
      container.appendChild(renderWsFsRow(state, entry, fullPath));
    }
  } catch (e) {
    container.innerHTML = `<div class="error-box">${escapeHtml(e.message)}</div>`;
  }
}

function renderWsFsRow(state, entry, fullPath) {
  const isDir = entry.type === 'dir';
  const isExcluded = !!entry.excluded;
  const isBinary = !!entry.binary && !isDir;

  const row = el('div', 'ws-fs-tree-row' +
    (isDir ? ' ws-fs-tree-row-dir' : ' ws-fs-tree-row-file') +
    (isExcluded ? ' is-excluded' : '') +
    (isBinary ? ' is-binary' : ''));

  const icon = isExcluded ? '🚫' : (isDir ? '📁' : (isBinary ? '⛔' : '📄'));
  const childCount = (isDir && entry.children_count != null) ? ` (${entry.children_count})` : '';
  const sizeStr = (!isDir && entry.size != null) ? `<span class="ws-fs-tree-size dim">${fmtBytes(entry.size)}</span>` : '';

  row.innerHTML = `
    <span class="ws-fs-tree-icon">${icon}</span>
    <span class="ws-fs-tree-name">${escapeHtml(entry.name)}</span>
    <span class="ws-fs-tree-meta dim">${childCount}</span>
    ${sizeStr}
  `;

  if (isExcluded) {
    row.title = 'Dossier exclu (non explorable)';
    return row;
  }

  if (isDir) {
    const childContainer = el('div', 'ws-fs-tree-children');
    childContainer.style.display = 'none';
    let loaded = false;
    row.title = `Cliquer pour ${childCount ? 'voir le contenu' : 'explorer'}`;
    row.addEventListener('click', async () => {
      if (childContainer.style.display === 'none') {
        if (!loaded) { await loadWsFsSubtree(state, childContainer, fullPath); loaded = true; }
        childContainer.style.display = '';
        row.classList.add('is-expanded');
      } else {
        childContainer.style.display = 'none';
        row.classList.remove('is-expanded');
      }
    });
    const wrapper = el('div');
    wrapper.append(row, childContainer);
    return wrapper;
  }

  if (isBinary) {
    row.title = 'Fichier binaire (non éditable)';
    row.addEventListener('click', () => toast('Fichier binaire non éditable.', 'info'));
    return row;
  }

  row.title = `Cliquer pour ouvrir ${fullPath}`;
  row.addEventListener('click', () => openWsFsFileInEditor(state, fullPath, row));
  return row;
}

async function openWsFsFileInEditor(state, path, rowEl) {
  // Garde-fou : modifs non sauvegardées
  if (state.dirty) {
    toastErr('Modifications non-sauvegardées sur le fichier courant. Sauvegarde ou annule avant de changer.');
    return;
  }
  try {
    const r = await API.get(`/api/workspaces/${state.wsId}/fs/file?path=${encodeURIComponent(path)}`);
    if (r.binary) {
      toast(r.reason ? `Binaire (${r.reason})` : 'Fichier binaire non éditable', 'info');
      return;
    }
    // masked : fichier a secrets (.mcp.json, .env*) servi masque et en lecture
    // seule par le serveur (sauvegarder la version masquee ecraserait les secrets).
    state.openFile = { path, content: r.content || '', mtime: r.mtime, encoding: r.encoding, masked: !!r.masked };
    state.dirty = false;
    renderWsFsEditor(state);
    document.querySelectorAll('.ws-fs-tree-row.is-open').forEach(e => e.classList.remove('is-open'));
    if (rowEl) rowEl.classList.add('is-open');
  } catch (e) {
    toastErr(e.message);
  }
}

function renderWsFsEditor(state) {
  const pane = state.editorPane;
  pane.innerHTML = '';
  if (!state.openFile) { renderWsFsEmpty(state); return; }

  const header = el('div', 'ws-fs-editor-header');
  const titleSpan = el('div', 'ws-fs-editor-title mono');
  titleSpan.textContent = `📄 ${state.openFile.path}`;
  const dirtyDot = el('span', 'ws-fs-editor-dirty');
  dirtyDot.textContent = state.dirty ? '• modifié' : '';
  header.append(titleSpan, dirtyDot);

  // Fichier .json : editeur JSON (validation en direct, Tab = indentation).
  // Autres fichiers : zone de texte simple. `state.textarea` expose dans les
  // deux cas une propriete .value (lue par saveWsFsCurrentFile).
  const masked = !!state.openFile.masked;
  const isJson = !masked && /\.json$/i.test(state.openFile.path);
  let ta;
  let editor = null;
  let saveBtn = null;
  const refreshDirty = () => {
    state.dirty = (state.textarea.value !== state.openFile.content);
    dirtyDot.textContent = state.dirty ? '• modifié' : '';
    if (typeof wsUpdateDirtyDots === 'function') wsUpdateDirtyDots();
  };
  if (isJson) {
    editor = createJsonEditor({
      value: state.openFile.content, fill: true, ariaLabel: `Contenu de ${state.openFile.path}`,
      onChange: () => refreshDirty(),
      onSave: () => saveWsFsCurrentFile(state),
      onValidChange: (ok) => { if (saveBtn) { saveBtn.disabled = !ok; saveBtn.title = ok ? 'Ctrl+S' : 'Corrige le JSON pour pouvoir sauvegarder'; } },
    });
    ta = editor.el;
    state.textarea = { get value() { return editor.getValue(); }, set value(v) { editor.setValue(v); } };
    // Base de comparaison normalisee (BOM retire, fins de ligne LF) pour que
    // l'ouverture seule ne compte pas comme une modification.
    state.openFile.content = editor.getValue();
  } else if (/\.(md|markdown)$/i.test(state.openFile.path)) {
    // Markdown : editeur colore (goutiere + coloration), meme contrat .value.
    const md = createMdEditor({
      value: state.openFile.content, readOnly: masked, ariaLabel: `Contenu de ${state.openFile.path}`,
      onChange: () => refreshDirty(),
      onSave: () => saveWsFsCurrentFile(state),
    });
    ta = md.el;
    state.textarea = md.textarea;
    state.openFile.content = md.getValue();
  } else {
    ta = document.createElement('textarea');
    ta.className = 'ws-fs-editor-textarea mono';
    ta.value = state.openFile.content;
    ta.spellcheck = false;
    ta.readOnly = masked;
    ta.addEventListener('input', refreshDirty);
    ta.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); saveWsFsCurrentFile(state); }
    });
    state.textarea = ta;
  }
  state.editor = editor;
  state.dirtyDot = dirtyDot;

  const footer = el('div', 'ws-fs-editor-footer');
  // Supprimer à l'extrême gauche, isolé du couple Annuler/Sauvegarder
  // par le hint poussé à droite (Fitts' law : distance + style outline
  // rouge = clic accidentel improbable, cf. règle Session 3 RM-3).
  const deleteBtn = btn('Supprimer', 'btn-sm btn-danger-outline', I.trash);
  deleteBtn.title = 'Supprimer ce fichier (confirmation demandée)';
  deleteBtn.addEventListener('click', () => confirmDeleteWsFsFile(state));
  const hint = el('span', 'dim ws-fs-editor-hint');
  hint.textContent = 'Ctrl+S pour sauvegarder';
  const cancelBtn = btn('Annuler', 'btn-sm btn-ghost');
  cancelBtn.addEventListener('click', () => {
    if (!state.dirty) return;
    state.textarea.value = state.openFile.content;
    // Editeur JSON : state.textarea est un accesseur {value}, pas un EventTarget.
    if (typeof state.textarea.dispatchEvent === 'function') state.textarea.dispatchEvent(new Event('input'));
    state.dirty = false;
    dirtyDot.textContent = '';
    if (typeof wsUpdateDirtyDots === 'function') wsUpdateDirtyDots();
  });
  saveBtn = btn('Sauvegarder', 'btn-sm btn-primary', I.check);
  saveBtn.title = 'Ctrl+S';
  saveBtn.addEventListener('click', () => saveWsFsCurrentFile(state));
  footer.append(deleteBtn, hint, cancelBtn, saveBtn);
  if (editor) saveBtn.disabled = !editor.isValid();
  if (masked) {
    saveBtn.disabled = true;
    saveBtn.title = 'Lecture seule : secrets masqués';
    hint.textContent = 'Secrets masqués - lecture seule (modifie le registre MCP ou les variables d’environnement)';
  }

  pane.append(header, ta, footer);
}

function confirmDeleteWsFsFile(state) {
  if (!state.openFile) return;
  const path = state.openFile.path;
  const msg = state.dirty
    ? `Supprimer "${path}" ? Tes modifications non sauvegardées seront perdues.`
    : `Supprimer "${path}" ?`;
  confirmDialog(msg, async () => {
    try {
      await API.del(`/api/workspaces/${state.wsId}/fs/file?path=${encodeURIComponent(path)}`);
      toastOk(`Supprimé : ${path}`);
      state.openFile = null;
      state.dirty = false;
      // Rafraîchit l'arbre + repasse en empty state côté éditeur
      state.treePane.innerHTML = '';
      await loadWsFsSubtree(state, state.treePane, '');
      renderWsFsEmpty(state);
    } catch (e) {
      toastErr(e.message);
    }
  }, { danger: true });
}

function renderWsFsEmpty(state) {
  state.editorPane.innerHTML = '';
  const empty = el('div', 'ws-fs-empty');
  const title = el('div', 'ws-fs-empty-title');
  title.textContent = 'Aucun fichier sélectionné';
  const hint = el('div', 'ws-fs-empty-hint dim');
  hint.innerHTML = "▸ Clique sur un fichier dans l'arbre pour l'ouvrir<br>▸ Ou utilise la recherche ci-dessus";
  empty.append(title, hint);
  state.editorPane.appendChild(empty);
}

async function saveWsFsCurrentFile(state) {
  if (!state.openFile) return;
  if (!state.dirty) { toast('Rien à sauvegarder', 'info'); return; }
  if (state.editor && !state.editor.validate().ok) { toastErr("JSON invalide : corrige-le avant de sauvegarder"); return; }
  try {
    const r = await API.post(`/api/workspaces/${state.wsId}/fs/file`, {
      path: state.openFile.path,
      content: state.textarea.value,
    });
    state.openFile.content = state.textarea.value;
    state.openFile.mtime = r.mtime;
    state.dirty = false;
    if (state.dirtyDot) state.dirtyDot.textContent = '';
    if (typeof wsUpdateDirtyDots === 'function') wsUpdateDirtyDots();
    toastOk(`Sauvegardé : ${state.openFile.path}`);
  } catch (e) {
    toastErr(e.message);
  }
}

async function doWsFsSearch(state, query) {
  const container = state.treePane;
  container.innerHTML = '<div class="dim ws-fs-loading">Recherche…</div>';
  try {
    const r = await API.get(`/api/workspaces/${state.wsId}/fs/search?q=${encodeURIComponent(query)}&max=50`);
    container.innerHTML = '';
    if (!r.hits || r.hits.length === 0) {
      container.appendChild(el('div', 'dim ws-fs-empty-line', 'Aucun résultat.'));
      return;
    }
    const header = el('div', 'ws-fs-search-results-header dim');
    header.textContent = `${r.hits.length} résultat${r.hits.length > 1 ? 's' : ''}${r.truncated ? ' (tronqué)' : ''} · ${r.files_scanned} fichiers scannés`;
    container.appendChild(header);
    for (const hit of r.hits) {
      const row = el('div', 'ws-fs-search-hit');
      const pathEl = el('div', 'ws-fs-search-hit-path mono');
      pathEl.textContent = `${hit.path}:${hit.line}`;
      const snippetEl = el('div', 'ws-fs-search-hit-snippet dim');
      snippetEl.textContent = hit.snippet;
      row.append(pathEl, snippetEl);
      row.title = `Ouvrir ${hit.path}`;
      row.addEventListener('click', () => openWsFsFileInEditor(state, hit.path, null));
      container.appendChild(row);
    }
  } catch (e) {
    container.innerHTML = `<div class="error-box">${escapeHtml(e.message)}</div>`;
  }
}

function promptNewWsFile(wsId, fsState = null) {
  const body = el('div');
  const hint = el('p', 'muted');
  hint.style.cssText = 'margin-top:0;font-size:13px';
  hint.textContent = 'Le chemin doit être relatif à la racine du workspace. Les dossiers parents sont créés automatiquement.';
  const field = el('div', 'field');
  const label = el('label', 'field-label');
  label.textContent = 'Chemin (ex: agents/expert.md)';
  const input = document.createElement('input');
  input.className = 'input mono';
  input.name = 'path';
  input.placeholder = 'agents/expert.md';
  field.append(label, input);
  body.append(hint, field);

  const cancel = btn('Annuler', 'btn-ghost');
  const create = btn('Créer', 'btn-primary', I.plus);
  const { close } = openModal({ title: 'Nouveau fichier dans le workspace', body, footer: [cancel, create] });
  cancel.addEventListener('click', close);
  create.addEventListener('click', async () => {
    const path = input.value.trim();
    if (!path) { toastErr('Chemin requis'); return; }
    try {
      await API.post(`/api/workspaces/${wsId}/fs/file`, { path, content: '' });
      toastOk(`Créé : ${path}`);
      close();
      // Rafraîchit l'arbre en place (l'éditeur ouvert est préservé).
      if (fsState && fsState.treePane && fsState.treePane.isConnected) {
        fsState.treePane.innerHTML = '';
        await loadWsFsSubtree(fsState, fsState.treePane, '');
      } else { STATE.loading = true; route(); }
    } catch (e) { toastErr(e.message); }
  });
  setTimeout(() => input.focus(), 50);
}

async function loadSessions(wsId, host) {
  host.innerHTML = '<div class="dim" style="font-size:12px">Chargement…</div>';
  try {
    const r = await API.get(`/api/workspaces/${wsId}/sessions`);
    const all = r.sessions || [];
    const sessions = all.slice(0, 50);
    if (!sessions.length) {
      host.innerHTML = '<div class="card home-empty">Aucune session pour ce workspace. </div>';
      const w = STATE.workspaces.find(x => x.id === wsId);
      if (w) {
        const launch = btn('Lancer Claude Code', 'btn-sm btn-primary', I.play);
        launch.addEventListener('click', () => doLaunch(w, launch));
        host.firstElementChild.appendChild(launch);
      }
      return;
    }
    const running = sessionState(wsId) === 'running';
    const w = STATE.workspaces.find(x => x.id === wsId);
    const tbl = el('div', 'card tbl sess-list');
    tbl.setAttribute('role', 'table');
    tbl.setAttribute('aria-label', 'Sessions du workspace');
    tbl.innerHTML = `<div class="tr h" role="row"><span role="columnheader">Date</span><span role="columnheader">Premier message</span><span class="num" role="columnheader">Messages</span><span class="num" role="columnheader">Tokens sortie</span><span role="columnheader"><span class="sr-only">Actions</span></span></div>`;
    sessions.forEach((s, i) => {
      // La plus recente porte la session en cours (le detecteur ne dit pas
      // quel fichier .jsonl est ouvert : heuristique affichee comme telle).
      const cur = i === 0 && running;
      const row = el('div', 'tr' + (cur ? ' cur' : ''));
      row.setAttribute('role', 'row');
      row.tabIndex = 0;
      row.setAttribute('aria-label', `Ouvrir la session du ${fmtDateTime(s.mtime)}`);
      row.innerHTML = `
        <span class="tab-num" role="cell" title="${escapeHtml(s.mtime || '')}">${escapeHtml(fmtDateTime(s.mtime))}</span>
        <span class="sess-first" role="cell">${cur ? '<span class="pill ok" style="margin-right:8px"><span class="sdot live"></span>en cours</span>' : ''}${escapeHtml(s.first_message || '(vide)')}<small class="dim mono">${escapeHtml(s.file.slice(0, 8))}</small></span>
        <span class="num" role="cell">${fmtNum(s.messages || 0)}</span>
        <span class="num" role="cell" title="${fmtNum(s.output_tokens || 0)} (entrée : ${fmtNum(s.input_tokens || 0)})">${escapeHtml(fmtCompact(s.output_tokens || 0))}</span>
        <div class="ra" role="cell"></div>`;
      const ra = row.querySelector('.ra');
      const tail = btn('Suivre', 'btn-sm btn-ghost', I.activity);
      tail.title = 'Ouvrir la session en suivi live';
      tail.addEventListener('click', (e) => { e.stopPropagation(); modalSession(wsId, s.file); });
      ra.appendChild(tail);
      if (i === 0 && w) {
        const resume = btn('Reprendre', 'btn-sm', I.ret);
        resume.title = 'Reprendre la dernière session Claude Code';
        resume.addEventListener('click', (e) => { e.stopPropagation(); doResume(w, resume); });
        ra.appendChild(resume);
      }
      row.addEventListener('click', (e) => { if (!e.target.closest('button')) modalSession(wsId, s.file); });
      row.addEventListener('keydown', (e) => {
        if (e.target !== row) return;
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); modalSession(wsId, s.file); }
      });
      attachSessionPreview(row, wsId, s.file);
      tbl.appendChild(row);
    });
    host.replaceChildren(tbl);
    if (all.length > sessions.length) host.appendChild(el('p', 'dim', `<span style="font-size:12.5px">${sessions.length} sessions les plus récentes sur ${all.length}.</span>`));
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
  // Mode live : on charge d'abord le snapshot initial, puis on poll
  // /tail toutes les 2s pour append les nouveaux messages. Auto-scroll
  // vers le bas tant que l'utilisateur n'a pas scrollé manuellement
  // (sticky scroll détecté via scrollTop vs scrollHeight).
  const body = el('div');
  body.style.cssText = 'display:flex;flex-direction:column;gap:0;max-height:72vh';

  // Barre de contrôle : statut live + toggle
  const ctrl = el('div', 'session-ctrl');
  ctrl.style.cssText = 'display:flex;align-items:center;gap:var(--sp-3);padding:var(--sp-2) var(--sp-3);border-bottom:1px solid var(--border);background:var(--surface-1);flex-shrink:0';
  const liveDot = el('span', 'session-live-dot');
  const liveLabel = el('span', 'mono');
  liveLabel.style.cssText = 'font-size:11.5px;flex:1';
  const liveToggle = btn('Pause', 'btn-sm btn-ghost', I.pause || I.x);
  liveToggle.title = 'Mettre en pause le suivi live';
  ctrl.append(liveDot, liveLabel, liveToggle);

  // Zone de messages, scrollable
  const list = el('div', 'session-msgs');
  list.style.cssText = 'flex:1;overflow-y:auto;padding:var(--sp-3);min-height:0';

  body.append(ctrl, list);

  const close = btn('Fermer', 'btn-ghost');
  const { close: doClose, modal } = openModal({ title: filename, body, footer: close, wide: true });

  // État local de la session modal
  const session = {
    wsId,
    filename,
    offset: 0,
    polling: true,
    pollTimer: null,
    msgCount: 0,
    stickyScroll: true,  // auto-scroll bas tant que user n'a pas scrollé up
  };

  const appendMsg = (m) => {
    const item = el('div', 'session-msg-item');
    item.innerHTML = `
      <div class="session-msg-meta">
        <span class="badge ${m.role === 'user' ? 'badge-info' : 'badge-accent'}">${m.role}</span>
        <span class="dim mono" style="font-size:10.5px">${escapeHtml(m.timestamp || '')}</span>
      </div>
      <div class="session-msg-text">${escapeHtml(m.text)}</div>
    `;
    list.appendChild(item);
    session.msgCount += 1;
  };

  const refreshLabel = () => {
    if (session.polling) {
      liveDot.className = 'session-live-dot is-live';
      liveLabel.textContent = `● Live · ${session.msgCount} message${session.msgCount > 1 ? 's' : ''}`;
      liveToggle.querySelector('span').textContent = 'Pause';
    } else {
      liveDot.className = 'session-live-dot';
      liveLabel.textContent = `❚❚ Pause · ${session.msgCount} message${session.msgCount > 1 ? 's' : ''}`;
      liveToggle.querySelector('span').textContent = 'Reprendre';
    }
  };

  // Detection sticky scroll : si l'utilisateur scroll vers le haut,
  // on suspend l'auto-scroll. S'il revient en bas, on reprend.
  list.addEventListener('scroll', () => {
    const atBottom = list.scrollHeight - list.scrollTop - list.clientHeight < 40;
    session.stickyScroll = atBottom;
  });

  // Charge initial : tail avec offset=0 → tout le fichier en une fois
  try {
    const r = await API.get(`/api/workspaces/${wsId}/sessions/${filename}/tail?offset=0`);
    for (const m of r.messages || []) appendMsg(m);
    session.offset = r.new_offset || 0;
    if (session.stickyScroll) list.scrollTop = list.scrollHeight;
    if (!session.msgCount) {
      list.innerHTML = '<div class="dim" style="padding:var(--sp-3)">Session vide ou pas encore commencée.</div>';
    }
  } catch (e) {
    list.innerHTML = `<div class="error-box">${escapeHtml(e.message)}</div>`;
    session.polling = false;
  }
  refreshLabel();

  // Poll loop
  const tick = async () => {
    if (!session.polling) return;
    try {
      const r = await API.get(`/api/workspaces/${wsId}/sessions/${filename}/tail?offset=${session.offset}`);
      const newMsgs = r.messages || [];
      if (newMsgs.length) {
        // Si on avait un placeholder "session vide", on le retire
        const ph = list.querySelector('.dim');
        if (ph && session.msgCount === 0) list.innerHTML = '';
        for (const m of newMsgs) appendMsg(m);
        if (session.stickyScroll) list.scrollTop = list.scrollHeight;
        refreshLabel();
      }
      session.offset = r.new_offset || session.offset;
    } catch (e) {
      console.warn('[session-tail]', e.message);
    }
  };
  // 2s d'intervalle, registerPagePoller pour nettoyage propre à la navigation
  session.pollTimer = setInterval(() => { if (session.polling) tick(); }, 2000);
  registerPagePoller(session.pollTimer);

  liveToggle.addEventListener('click', () => {
    session.polling = !session.polling;
    refreshLabel();
    if (session.polling) tick();
  });

  close.addEventListener('click', () => {
    session.polling = false;
    clearInterval(session.pollTimer);
    doClose();
  });
}

function renderWsMCPs(wsId, host) {
  host.innerHTML = '';

  // Action bar : attacher un MCP. Direction Nebula admin totale -
  // l'utilisateur ne doit pas avoir a naviguer vers la page /mcps
  // pour modifier l'attachement d'un MCP a son workspace.
  const actionBar = el('div');
  actionBar.style.cssText = 'display:flex;justify-content:flex-end;margin-bottom:8px';
  const addBtn = btn('Attacher un MCP', 'btn-sm btn-primary', I.plus);
  addBtn.title = 'Attacher ou détacher des MCPs globaux à ce workspace';
  addBtn.addEventListener('click', () => modalAttachMcpToWorkspace(wsId));
  actionBar.appendChild(addBtn);
  host.appendChild(actionBar);

  const info = STATE.wsMcps[wsId] || { active: [] };
  if (!info.active.length) {
    host.appendChild(el('div', 'dim', '<span style="font-size:12.5px">Aucun MCP attaché. Clique « Attacher un MCP » pour en piocher dans le registre global.</span>'));
    return;
  }
  for (const mcpId of info.active) {
    const m = STATE.mcps.find(x => x.id === mcpId);
    const row = el('div', 'list-row');
    row.innerHTML = `
      <span class="dot ${m && m.status === 'désactivé' ? 'dot-err' : 'dot-info'}"></span>
      <div class="list-row-main">
        <div class="list-row-name mono">${escapeHtml(mcpId)}</div>
        ${m ? `<div class="list-row-desc">${escapeHtml(m.description || m.transport || '')}</div>` : ''}
      </div>
    `;
    // Détach 1-clic depuis la ligne (équivalent rapide du modal)
    const detachBtn = btn('', 'btn-sm btn-ghost btn-icon-only', I.x);
    detachBtn.title = 'Détacher de ce workspace';
    detachBtn.addEventListener('click', () => {
      const mcp0 = STATE.mcps.find(x => x.id === mcpId);
      // Joker "*"/"all" : retirer wsId d'une liste qui ne le contient pas ne
      // changerait rien. On convertit en liste explicite (tous les autres
      // workspaces), comme la matrice, après une confirmation qui le dit.
      const wild = !!(mcp0 && mcpIsWildcard(mcp0));
      const others = (STATE.workspaces || []).filter(x => x.id !== wsId).length;
      const msg = wild
        ? `« ${mcpId} » est attaché à TOUS les workspaces (joker « * »).\n\n`
          + `Le détacher de ce workspace remplace le joker par la liste explicite des ${others} autre(s) workspace(s). `
          + `Les workspaces créés plus tard ne l'auront plus automatiquement.`
        : `Détacher « ${mcpId} » de ce workspace ?`;
      confirmDialog(msg, async () => {
        const mcp = STATE.mcps.find(x => x.id === mcpId);
        if (!mcp) { toastErr('MCP introuvable dans le registre'); return; }
        const updated = { ...mcp, workspaces: mcpWorkspacesWithout(mcp, wsId, STATE.workspaces) };
        try {
          await API.post('/api/mcps', updated);
          toastOk(wild
            ? `Détaché : ${mcpId} (joker remplacé par ${updated.workspaces.length} workspace(s))`
            : `Détaché : ${mcpId}`);
          await wsRefreshPanels(['extensions'], { reload: true });
        } catch (e) { toastErr(e.message); throw e; }
      }, { confirmLabel: wild ? 'Remplacer le joker et détacher' : 'Détacher' });
    });
    row.appendChild(detachBtn);
    host.appendChild(row);
  }
}

// Modal de gestion des attachements MCP à un workspace donné. Réutilise
// la route POST /api/mcps (upsert via add_or_update_mcp) pour modifier
// la liste workspaces de chaque MCP impacté. Cf. principe Nebula admin
// totale : pas besoin de quitter la page workspace pour gérer les MCPs.
function modalAttachMcpToWorkspace(wsId) {
  const allMcps = STATE.mcps || [];
  if (!allMcps.length) {
    const body = el('div');
    body.innerHTML = `<p class="muted" style="margin-top:0">Aucun MCP dans le registre global. Crée-en un depuis l'onglet <strong>MCPs</strong> avant de pouvoir en attacher ici.</p>`;
    const c = btn('Fermer', 'btn-ghost');
    const { close } = openModal({ title: 'Attacher un MCP', body, footer: c });
    c.addEventListener('click', close);
    return;
  }
  const body = el('div');
  body.innerHTML = `<p class="muted" style="margin-top:0;font-size:13px">Coche les MCPs à attacher à ce workspace, décoche pour retirer l'attache. Les modifications sont appliquées à la validation.</p>`;
  const list = el('div', 'stack');
  list.style.cssText = 'max-height:50vh;overflow-y:auto';
  for (const m of allMcps) {
    // Joker "*"/"all" = actif ici aussi (même sémantique que la matrice).
    const initial = mcpActiveOn(m, wsId);
    const wild = mcpIsWildcard(m);
    const card = el('label', 'list-row');
    card.style.cursor = 'pointer';
    card.dataset.initial = initial ? '1' : '0';
    card.innerHTML = `
      <input type="checkbox" data-mcp-id="${escapeHtml(m.id)}" ${initial ? 'checked' : ''} style="margin-right:10px">
      <span class="dot ${m.status === 'désactivé' ? 'dot-err' : 'dot-info'}"></span>
      <div class="list-row-main">
        <div class="list-row-name mono">${escapeHtml(m.name || m.id)}${wild ? ' <span class="badge">tous les workspaces</span>' : ''}</div>
        <div class="list-row-desc">${escapeHtml(m.description || m.transport || '')}${wild ? ' -- décocher remplace le joker par la liste explicite des autres workspaces' : ''}</div>
      </div>
    `;
    list.appendChild(card);
  }
  body.appendChild(list);
  const cancel = btn('Annuler', 'btn-ghost');
  const ok = btn('Appliquer', 'btn-primary', I.check);
  const { close } = openModal({ title: 'Attacher des MCPs au workspace', body, footer: [cancel, ok], wide: true });
  cancel.addEventListener('click', close);
  ok.addEventListener('click', async () => {
    const rows = body.querySelectorAll('label.list-row');
    const changes = [];
    for (const row of rows) {
      const cb = row.querySelector('input[type=checkbox]');
      const initial = row.dataset.initial === '1';
      if (initial !== cb.checked) {
        changes.push({ mcpId: cb.dataset.mcpId, attach: cb.checked });
      }
    }
    if (!changes.length) { toast('Rien à modifier', 'info'); close(); return; }
    let errs = 0;
    for (const ch of changes) {
      const mcp = allMcps.find(m => m.id === ch.mcpId);
      if (!mcp) { errs++; continue; }
      let next;
      if (ch.attach) next = Array.from(new Set([...(mcp.workspaces || []), wsId]));
      else next = mcpWorkspacesWithout(mcp, wsId, STATE.workspaces);
      const updated = { ...mcp, workspaces: next };
      try { await API.post('/api/mcps', updated); }
      catch (e) { errs++; console.warn('[attach-mcp] update échoué pour', ch.mcpId, ':', e.message); }
    }
    if (errs) toastErr(`${errs} erreur(s) — voir console`);
    else toastOk(`${changes.length} MCP${changes.length > 1 ? 's' : ''} mis à jour`);
    close();
    await wsRefreshPanels(['extensions'], { reload: true });
  });
}

async function loadWsSkills(wsId, host) {
  host.innerHTML = '<div class="dim" style="font-size:12px">Chargement…</div>';
  try {
    const r = await API.get(`/api/workspaces/${wsId}/skills`);
    const local = r.local || [];
    const global = r.global_available || [];
    wsSetExtCount(wsId, 'skills', local.length);
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
          try { await API.del(`/api/skills/workspace:${wsId}/${s.id}`); toastOk('Skill retiré'); wsRefreshPanels(['extensions']); }
          catch (e) { toastErr(e.message); }
        }, { danger: true, confirmLabel: 'Retirer' });
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
          try { await API.post('/api/skills/copy', { name: s.id, workspace: wsId }); toastOk('Skill copié'); wsRefreshPanels(['extensions']); }
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
    wsSetExtCount(wsId, 'plugins', ids.filter(pid => plugins[pid] && plugins[pid].effective).length);
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
      const segBtns = Array.from(seg.querySelectorAll('button'));
      segBtns.forEach(b => {
        b.addEventListener('click', async () => {
          const next = { 'on': true, 'off': false, 'reset': null }[b.dataset.set];
          segBtns.forEach(x => { x.disabled = true; });
          try { await API.post(`/api/workspaces/${wsId}/plugins`, { plugin_id: pid, enabled: next }); loadWsPlugins(wsId, host); }
          catch (e) { toastErr(e.message); segBtns.forEach(x => { x.disabled = false; }); }
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
    const block = el('div', 'xblock');
    block.innerHTML = `<div class="xblock-h">${kind === 'agents' ? 'Agents' : 'Commandes'}</div>`;
    const list = el('div', 'xlist');
    block.appendChild(list);
    const add = btn(kind === 'agents' ? 'Nouvel agent' : 'Nouvelle commande', 'btn-sm btn-ghost', I.plus);
    add.addEventListener('click', () => modalEditFileItem(kind, `workspace:${wsId}`, null));
    block.appendChild(add);
    host.appendChild(block);
    try {
      const data = await API.get(`/api/${kind}/workspace/${wsId}`);
      // L'endpoint renvoie {global, local} : les agents/commands du workspace
      // sont dans `local`. (Bug : lisait data.workspace/data.items -> clés
      // inexistantes -> toujours "Aucun agent" meme quand le workspace en a.)
      const items = data.local || data.workspace || data.items || [];
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

// Éditeur inline de CLAUDE.md (onglet Mémoire). CLAUDE.md = pièce centrale
// de la mémoire projet, modifié quotidiennement -> place fixe, pas de modal.
// `panel` (onglet) : isDirty protege l'edition en cours contre les re-rendus.
async function renderWsClaudeMdInline(wsId, host, panel = null) {
  host.innerHTML = '<div class="dim ws-claudemd-loading" style="padding:var(--sp-3)">Chargement de CLAUDE.md…</div>';
  let initial = '';
  try {
    const data = await API.get(`/api/workspaces/${wsId}/config`);
    initial = (data.files || {})['CLAUDE.md'] || '';
  } catch (e) {
    host.innerHTML = `<div class="error-box">${escapeHtml(e.message)}</div>`;
    return;
  }

  const ed = edCard('CLAUDE.md', I.book);
  let dirty = false;
  const saveBtn = btn('Sauvegarder', 'btn-sm btn-primary', I.check);
  saveBtn.title = 'Ctrl+S';
  const cancelBtn = btn('Annuler', 'btn-sm btn-ghost');
  const refresh = () => {
    dirty = md.getValue() !== initial;
    ed.vstate.className = 'vstate' + (dirty ? ' dirty' : '');
    ed.vstate['innerHTML'] = dirty ? `${I.edit}Modifié` : 'Aucune modification';
    ed.lc.textContent = `${md.lineCount()} lignes`;
    saveBtn.disabled = !dirty;
    if (typeof wsUpdateDirtyDots === 'function') wsUpdateDirtyDots();
  };
  const saveCurrent = async () => {
    if (!dirty) { toast('Rien à sauvegarder', 'info'); return; }
    await withBusy(saveBtn, async () => {
      try {
        await API.post(`/api/workspaces/${wsId}/file`, { filename: 'CLAUDE.md', content: md.getValue() });
        initial = md.getValue();
        toastOk('CLAUDE.md sauvegardé');
      } catch (e) { toastErr(e.message); }
    });
    refresh();
  };
  const md = createMdEditor({ value: initial, ariaLabel: 'Contenu de CLAUDE.md', onChange: () => refresh(), onSave: saveCurrent });
  initial = md.getValue();
  saveBtn.addEventListener('click', saveCurrent);
  cancelBtn.addEventListener('click', () => { if (dirty) { md.setValue(initial); refresh(); } });
  const openBtn = btn('', 'btn-sm btn-ghost btn-icon-only', I.ext);
  openBtn.title = "Ouvrir CLAUDE.md dans l'éditeur externe";
  openBtn.setAttribute('aria-label', "Ouvrir CLAUDE.md dans l'éditeur externe");
  openBtn.addEventListener('click', async () => {
    try { const r = await API.post('/api/open', { target: `workspace-claude-md:${wsId}` }); toastOk(r.message || 'Ouvert'); }
    catch (e) { toastErr(e.message); }
  });
  ed.bar.appendChild(openBtn);
  ed.foot.append(cancelBtn, saveBtn);
  ed.slot.replaceWith(md.el);
  if (panel) panel.isDirty = () => dirty;
  host.replaceChildren(ed.card);
  refresh();
}

async function openWsFile(wsId, filename) {
  let data;
  try { data = await API.get(`/api/workspaces/${wsId}/config`); }
  catch (e) { toastErr(e.message); return; }
  const content = (data.files || {})[filename] || '';
  const body = el('div');
  body.innerHTML = `<div class="dim" style="font-size:11.5px;margin-bottom:6px">${escapeHtml(data.path || '')}/${escapeHtml(filename)}</div>`;
  const cancel = btn('Annuler', 'btn-ghost');
  const save = btn('Enregistrer', 'btn-primary');
  // Un fichier .json s'edite avec l'editeur JSON (validation en direct) ;
  // tout autre fichier (CLAUDE.md...) reste une zone de texte simple.
  const isJson = /\.json$/i.test(filename);
  let ta = null;
  let editor = null;
  if (isJson) {
    editor = createJsonEditor({
      value: content || '{}', rows: 18, ariaLabel: `Contenu de ${filename}`,
      onSave: () => { if (!save.disabled) save.click(); },
      onValidChange: (ok) => { save.disabled = !ok; save.title = ok ? '' : 'Corrige le JSON pour pouvoir enregistrer'; },
    });
    body.appendChild(editor.el);
  } else {
    ta = el('textarea', 'textarea textarea-code');
    ta.rows = 18; ta.value = content || '';
    body.appendChild(ta);
  }
  const { close } = openModal({ title: filename, body, footer: [cancel, save], wide: true });
  cancel.addEventListener('click', close);
  save.addEventListener('click', () => withBusy(save, async () => {
    if (editor && !editor.validate().ok) { toastErr("JSON invalide : corrige-le avant d'enregistrer"); return; }
    try { await API.post(`/api/workspaces/${wsId}/file`, { filename, content: editor ? editor.getValue() : ta.value }); toastOk('Enregistré'); close(); }
    catch (e) { toastErr(e.message); }
  }));
}

/* ================================================================
   PAGE MCPs -> deplacee dans js/pages/mcps.js (CM-2 batch 12)
   renderMCPs, mcpCard, modalMcpRecipes, modalInstallRecipe,
   mcpToRecipeTemplate, modalSaveAsRecipe, modalEditRecipe, modalNewMCP
   ================================================================ */


/* ================================================================
   FIRST-RUN WIZARD — assistant de premier lancement
   ================================================================ */
function markOnboarded() {
  if (STATE.uiState) STATE.uiState.onboarded = true;
  API.post('/api/ui-state', { onboarded: true }).catch(e => console.warn('[ui-state] markOnboarded échoué :', e.message));
}
function resetOnboarded() {
  if (STATE.uiState) STATE.uiState.onboarded = false;
  API.post('/api/ui-state', { onboarded: false }).catch(e => console.warn('[ui-state] resetOnboarded échoué :', e.message));
}

async function startFirstRunWizard() {
  let stepIdx = 0;
  let scanResult = null;
  let importedItems = { mcps: 0, workspaces: 0 };

  const root = $('#modal-root');
  const overlay = el('div', 'firstrun-overlay');
  const wiz = el('div', 'firstrun');
  wiz.setAttribute('role', 'dialog');
  wiz.setAttribute('aria-modal', 'true');
  wiz.setAttribute('aria-label', 'Assistant de premier lancement');
  wiz.tabIndex = -1;
  overlay.appendChild(wiz);
  // Focus lu AVANT l'insertion : pushModalLayer rend inerte une eventuelle
  // modale ouverte dessous, ce qui lui ferait perdre le focus.
  const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  root.appendChild(overlay);
  const releaseLayer = pushModalLayer(overlay, wiz);

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
    releaseLayer();
    setTimeout(() => overlay.remove(), 220);
    releaseTrap();
    if (previouslyFocused && document.body.contains(previouslyFocused)) {
      try { previouslyFocused.focus(); } catch { /* noop */ }
    }
  };
  // Focus trap partage (Tab cycle + Escape ferme sans marquer onboarded).
  const releaseTrap = createFocusTrap(wiz, { onEscape: () => close(false) });

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

    // Autofocus apres chaque etape : 1er champ du body sinon 1er focusable.
    setTimeout(() => {
      const focusables = getFocusables(wiz);
      const preferred = focusables.find(el => /^(INPUT|TEXTAREA|SELECT)$/i.test(el.tagName));
      const target = preferred || focusables[0] || wiz;
      try { target.focus(); } catch { /* noop */ }
    }, 30);
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
      // F3.2 : on transmet `source` (le serveur re-lit les valeurs réelles), pas
      // les valeurs sensibles qui ne transitent plus par le scan.
      const mcps = newMcps.map(m => ({
        id: m.id, name: m.id, source: m.source || '', status: 'disponible',
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
      } catch (e) { console.warn('[setup-wizard] fetch workspaces échoué :', e.message); }
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
  // Source unique de la version : injectée dans la sidebar (cf. brand-version
  // de index.html, initialement "v…" placeholder).
  if (info.version) {
    const tag = document.getElementById('brand-version');
    if (tag) tag.textContent = 'v' + info.version;
  }
  return info;
}

function renderUpdateBadge(info) {
  // Nettoie les anciennes versions du badge (sidebar + topbar)
  const existingNav = $('#nav-update-badge');
  if (existingNav) existingNav.remove();
  const slot = $('#topbar-update-slot');
  if (slot) slot.innerHTML = '';

  if (!info || !info.is_git) return;

  // Cas "divergent" : le dev local a ses propres commits ET le remote
  // a les siens (workflow dev→export typique). Pas une vraie "mise à
  // jour à appliquer" — pull --ff-only échouera. Afficher un badge
  // distinct (style warn) pour ne pas faire croire à un retard.
  if (info.diverged) {
    if (slot) {
      const badge = el('button', 'topbar-update-badge is-diverged');
      badge.type = 'button';
      badge.title = `Branches divergées : ${info.ahead} commit(s) local seulement, ${info.behind} remote seulement. Cliquer pour résoudre.`;
      badge.innerHTML = `
        <span class="topbar-update-dot"></span>
        <span class="topbar-update-text">Divergent</span>
      `;
      badge.addEventListener('click', () => modalSystemUpdate());
      slot.appendChild(badge);
    }
    const footer = $('.sidebar-footer');
    if (footer) {
      const navBadge = el('button', 'update-badge is-diverged');
      navBadge.id = 'nav-update-badge';
      navBadge.type = 'button';
      navBadge.innerHTML = `
        <span class="update-badge-dot"></span>
        <span class="update-badge-text">Branches divergées (${info.ahead} local / ${info.behind} remote)</span>
        <span class="update-badge-icon">${I.right}</span>
      `;
      navBadge.addEventListener('click', () => modalSystemUpdate());
      footer.insertBefore(navBadge, footer.firstChild);
    }
    return;
  }

  // Cas standard : remote en avance, fast-forward possible
  if (!info.behind || info.behind <= 0) return;

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

// Construit un encart « Récupérer mes modifs stashées » (lot D-4). Inséré
// dans la modale MAJ système quand un `git stash pop` a échoué après un pull.
// Appelle GET /api/system/stashes pour ne s'afficher que s'il reste des
// stash nebula-* à récupérer, puis POST /api/system/stash-recover.
async function mountStashRecover(host) {
  if (!host) return;
  let data;
  try { data = await API.get('/api/system/stashes'); }
  catch { return; }
  const stashes = (data && data.stashes) || [];
  if (!stashes.length) return;

  const box = el('div', 'callout callout-warn');
  box.style.cssText = 'margin-top:var(--sp-3)';
  box.innerHTML = `
    <div>
      <strong>↩ ${stashes.length} sauvegarde${stashes.length > 1 ? 's' : ''} de modifs locales</strong>
      <p style="margin:4px 0 0;font-size:11.5px">Tes modifs locales ont été stashées avant le pull mais n'ont pas pu être réappliquées automatiquement (conflit). Tu peux tenter la récupération ici, sans passer par la CLI.</p>
      <ul class="help-list" style="margin-top:6px">${stashes.slice(0, 5).map(s => `<li class="mono" style="font-size:11px">${escapeHtml(s.label || s.ref)}</li>`).join('')}</ul>
    </div>
  `;
  const recoverBtn = btn('Récupérer mes modifs stashées', 'btn-sm', I.refresh);
  recoverBtn.style.marginTop = 'var(--sp-2)';
  recoverBtn.addEventListener('click', () => withBusy(recoverBtn, async () => {
    let res;
    try { res = await API.post('/api/system/stash-recover', {}); }
    catch (e) {
      // API.post throw sur HTTP non-ok (conflit 409, etc.) en lisant `error`.
      toastErr(e.message);
      return;
    }
    toastOk(res.message || 'Modifs récupérées');
    // Recharge la page si des .py ont changé (le serveur a besoin d'un restart
    // de toute façon, mais un reload rafraîchit l'UI).
    if (res.needs_restart) {
      box.innerHTML = `<div><strong>Modifs récupérées.</strong> Des fichiers Python ont changé -- redémarre le dashboard pour les activer.</div>`;
    } else {
      box.innerHTML = `<div>${I.check} <strong>Modifs récupérées.</strong> ${escapeHtml(res.message || '')}</div>`;
    }
    // Le stash reste dans la pile par sécurité (apply, pas pop). Une fois les
    // modifs vérifiées, on peut l'oublier en 1-clic (git stash drop) sans CLI.
    if (res.applied_ref) {
      const dropBtn = btn('Oublier ce stash', 'btn-sm btn-ghost', I.trash);
      dropBtn.style.marginTop = 'var(--sp-2)';
      dropBtn.title = 'Supprime le stash de la pile (git stash drop) une fois tes modifs vérifiées';
      dropBtn.addEventListener('click', () => withBusy(dropBtn, async () => {
        try {
          const dr = await API.post('/api/system/stash-drop', { ref: res.applied_ref });
          toastOk(dr.message || 'Stash supprimé');
          dropBtn.remove();
        } catch (e) { toastErr(e.message); }
      }));
      box.querySelector('div').appendChild(dropBtn);
    }
  }));
  box.appendChild(recoverBtn);
  host.appendChild(box);
}

// Formate le timestamp epoch encodé dans un label nebula-*-<ts> en date
// lisible. Renvoie '' si le label n'a pas de timestamp exploitable.
function stashLabelDate(label) {
  const m = /-(\d{10})$/.exec(label || '');
  if (!m) return '';
  const d = new Date(parseInt(m[1], 10) * 1000);
  if (isNaN(d.getTime())) return '';
  return d.toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

// Construit l'encart « Sauvegardes locales (stash Nebula) » dans la modale
// MAJ. Conforme au feedback « UX découvrable » : le NOMBRE de sauvegardes est
// visible, et le nettoyage est accessible sans CLI. Ne liste QUE les stash
// nebula-* (l'endpoint /api/system/stashes ne remonte jamais un stash
// utilisateur), donc aucun risque de purger un « WIP » manuel.
async function mountStashManager(host) {
  if (!host) return;
  let data;
  try { data = await API.get('/api/system/stashes'); }
  catch { return; }
  const stashes = (data && data.stashes) || [];
  if (!stashes.length) return;

  const box = el('div');
  box.style.cssText = 'margin-top:var(--sp-4);padding:var(--sp-3);background:var(--surface-2);border:1px solid var(--border);border-radius:8px';

  const render = (list) => {
    box.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;gap:var(--sp-2);margin-bottom:var(--sp-2)">
        <div style="font-size:13px;font-weight:500">🧹 Sauvegardes locales · ${list.length}</div>
        <span class="dim" style="font-size:11px">stash Nebula auto-créés avant pull/reset</span>
      </div>
      <div class="dim" style="font-size:11.5px;margin-bottom:var(--sp-2);line-height:1.5">
        Ces sauvegardes (<code class="mono">git stash</code>) sont créées automatiquement avant chaque mise à jour ou réinitialisation. Une fois tes modifs vérifiées, tu peux les nettoyer ici. Seules les sauvegardes Nebula sont listées -- tes éventuels stash manuels ne sont jamais touchés.
      </div>
      <div class="stash-list">${list.map(s => {
        const date = stashLabelDate(s.label);
        const fc = (s.file_count === undefined || s.file_count < 0)
          ? '? fichier(s)'
          : `${s.file_count} fichier(s)`;
        const emptyTag = s.empty
          ? ' · <span class="text-warn" style="font-size:10.5px">vide</span>'
          : '';
        return `<div class="mono" style="font-size:11px;padding:3px 0;display:flex;gap:8px;align-items:baseline">
          <span style="color:var(--accent)">${escapeHtml(s.label || s.ref)}</span>
          <span class="dim" style="font-size:10.5px">${escapeHtml(date)} · ${fc}${emptyTag}</span>
        </div>`;
      }).join('')}</div>
    `;
    const cleanBtn = btn('Nettoyer les sauvegardes', 'btn-sm btn-ghost', I.trash);
    cleanBtn.style.marginTop = 'var(--sp-2)';
    cleanBtn.title = 'Supprime toutes les sauvegardes Nebula listées (git stash drop)';
    cleanBtn.addEventListener('click', () => {
      confirmDialog(
        `Supprimer ${list.length} sauvegarde(s) Nebula ? Cette action est définitive (git stash drop). Tes stash manuels éventuels ne sont pas touchés.`,
        () => withBusy(cleanBtn, async () => {
          let res;
          try { res = await API.post('/api/system/stash-prune', { refs: list.map(s => s.ref) }); }
          catch (e) { toastErr(e.message); return; }
          toastOk(res.message || 'Sauvegardes nettoyées');
          const remaining = res.remaining_stashes || [];
          if (!remaining.length) { box.remove(); }
          else { render(remaining); }
        }),
        { danger: true }
      );
    });
    box.appendChild(cleanBtn);
  };

  render(stashes);
  host.appendChild(box);
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

  // ───── Cas DIVERGENT : pas de pull possible (workflow dev→export typique).
  //       Proposer directement le reset proactif, sans laisser l'utilisateur
  //       cliquer "Appliquer" pour découvrir le 500.
  if (info.diverged) {
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

    body.appendChild(el('div', 'callout callout-warn', `
      <div>
        <strong>⚠ Branches divergées</strong>
        <p style="margin:var(--sp-2) 0 0;font-size:13px">
          Ton dépôt local a <strong>${info.ahead} commit${info.ahead > 1 ? 's' : ''}</strong>
          que le remote n'a pas, ET le remote a <strong>${info.behind} commit${info.behind > 1 ? 's' : ''}</strong>
          que ton local n'a pas. <code class="mono">git pull --ff-only</code> est mathématiquement
          impossible dans ce cas.
        </p>
        <p style="margin:var(--sp-2) 0 0;font-size:13px">
          <strong>Cas le plus courant</strong> : workflow dev→export où tes commits locaux
          granulaires ont leurs équivalents bundlés sur le remote (même contenu, hash
          différents). La solution propre est de <strong>réinitialiser ton local sur le remote</strong>
          — tes modifs locales seront stashées par sécurité.
        </p>
      </div>
    `));

    const resetBox = el('div');
    resetBox.style.cssText = 'margin-top:var(--sp-3);padding:var(--sp-4);background:var(--surface-2);border:1px solid var(--border);border-radius:8px';
    resetBox.innerHTML = `
      <div style="font-size:13px;font-weight:500;margin-bottom:6px">🔄 Réinitialiser sur ${escapeHtml(info.upstream || 'origin/main')}</div>
      <div class="dim" style="font-size:12px;margin-bottom:var(--sp-3);line-height:1.6">
        Exécute <code class="mono">git reset --hard ${escapeHtml(info.upstream || 'origin/main')}</code> précédé
        d'un <code class="mono">git stash --include-untracked</code> automatique pour préserver tes
        éventuelles modifs locales. Les fichiers utilisateurs (registre, workspaces.json,
        .env.local) sont préservés via <code class="mono">.gitignore</code> et skip-worktree.
      </div>
    `;
    const resetBtn = btn('Réinitialiser sur origin', 'btn-primary', I.refresh);
    resetBtn.addEventListener('click', () => {
      confirmDialog(
        `Réinitialiser ton local sur ${info.upstream || 'origin/main'} ? Tes ${info.ahead} commit(s) locaux seront perdus de l'historique (mais leur contenu est probablement déjà sur le remote sous forme bundlée). Modifs non-committées stashées par sécurité.`,
        async () => {
          resetBtn.disabled = true;
          resetBtn.innerHTML = `<div class="spinner" style="width:12px;height:12px"></div><span>Reset en cours…</span>`;
          try {
            const rr = await API.post('/api/system/reset', {});
            if (!rr.ok) { toastErr(rr.error || 'Échec du reset'); resetBtn.disabled = false; resetBtn.innerHTML = `${I.refresh}<span>Réessayer</span>`; return; }
            toastOk(rr.message || 'Local aligné sur le remote');
            setTimeout(() => location.reload(), 1200);
          } catch (e) { toastErr(e.message); resetBtn.disabled = false; resetBtn.innerHTML = `${I.refresh}<span>Réessayer</span>`; }
        },
        { danger: true, confirmLabel: 'Réinitialiser' }
      );
    });
    resetBox.appendChild(resetBtn);
    body.appendChild(resetBox);
    // Gestionnaire de sauvegardes : les pre-reset s'accumulent surtout ici.
    mountStashManager(body);
    return;
  }

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
    // Filet de sécurité : un stash résiduel d'un pull précédent doit rester
    // récupérable même quand il n'y a plus de mise à jour à appliquer.
    mountStashRecover(body);
    // Gestionnaire de sauvegardes : visibilité + nettoyage 1-clic (sans CLI).
    mountStashManager(body);
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
          <div data-stash-recover></div>
        </div>
      `;
      body.appendChild(errPanel);
      // Propose la récupération du stash si le pop a échoué.
      if (r.stash_pop_warning) mountStashRecover(errPanel.querySelector('[data-stash-recover]'));

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
            { danger: true, confirmLabel: "Forcer l'alignement" }
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
          <div data-stash-recover></div>
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
          <button class="btn btn-primary" data-reload-page>${I.refresh}<span>Recharger la page</span></button>
        </div>
      `}
    `;
    // Bouton recharger : addEventListener plutot qu'onclick inline (CSP +
    // coherence avec le reste du code).
    const reloadBtn = body.querySelector('[data-reload-page]');
    if (reloadBtn) reloadBtn.addEventListener('click', () => location.reload());
    // Si le stash pop a échoué pendant l'update, propose la récupération 1-clic.
    if (r.stash_pop_warning) mountStashRecover(body.querySelector('[data-stash-recover]'));
    // Gestionnaire de sauvegardes : visibilité + nettoyage 1-clic des stash
    // résiduels (la rétention auto a déjà purgé les anciens côté serveur).
    mountStashManager(body);
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
          { danger: true, confirmLabel: 'Retirer' }
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
          { danger: true, confirmLabel: 'Retirer' }
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
        // F3.2 : on n'envoie plus les valeurs sensibles (env/url) -- le scan ne
        // les expose pas. On transmet `source` : le serveur re-lit les valeurs
        // réelles depuis la config Claude d'origine (resolve_scanned_mcp).
        selectedMcps.push({
          id: m.id,
          name: m.id,
          source: m.source || '',
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

// ============================================================================
// modalRegisterExisting -- Adoption d'un workspace existant (flux 2 etapes).
// ----------------------------------------------------------------------------
// Etape 1 : inspection du chemin (POST /api/workspaces/inspect-path). Affiche
//           un recap des signaux Claude detectes (CLAUDE.md, .mcp.json, skills,
//           agents, commands, hooks) + warnings (sous ~/.claude/, deja adopte,
//           aucun signal). Garde-fous bloquants = erreur backend, warnings non
//           bloquants = check explicite.
// Etape 2 : adoption (POST /api/workspaces/adopt). Champs id (prerempli depuis
//           le basename slugifie, editable), label, emoji, description, et une
//           checkbox optionnelle d'import des MCPs declares dans le .mcp.json
//           (cochee par defaut SSI au moins 1 MCP detecte). Strategie d'import
//           = merge non destructif (skip si nom deja present dans le registre).
// ============================================================================
function modalRegisterExisting() {
  const body = el('div');

  // Etape 1 : champ chemin + bouton Inspecter + zone resultats.
  const step1 = el('div', 'adopt-step adopt-step-1');
  step1.innerHTML = `
    <p class="muted" style="margin-top:0">Adopte un dossier existant comme workspace Nebula. Aucun fichier du dossier n'est créé ni modifié.</p>
    <div class="field">
      <label class="field-label">Chemin absolu du dossier *</label>
      <input class="input mono" name="path" placeholder="C:\\dev\\mon-projet" autocomplete="off">
    </div>
    <div class="row" style="gap:var(--sp-2);align-items:center">
      <button type="button" class="btn btn-primary" data-inspect>Inspecter</button>
      <span class="muted" style="font-size:12px">Lecture seule -- aucun fichier modifié.</span>
    </div>
    <div class="adopt-inspect-result" data-inspect-result style="margin-top:var(--sp-3);display:none"></div>
  `;
  body.appendChild(step1);

  // Etape 2 : champs d'adoption (cachee tant que l'inspection n'a pas reussi).
  const step2 = el('div', 'adopt-step adopt-step-2');
  step2.style.display = 'none';
  step2.style.marginTop = 'var(--sp-3)';
  step2.style.paddingTop = 'var(--sp-3)';
  step2.style.borderTop = '1px solid var(--border)';
  step2.innerHTML = `
    <div class="field-row">
      <div class="field"><label class="field-label">ID *</label><input class="input mono" name="id" placeholder="mon-projet" autocomplete="off"></div>
      <div class="field"><label class="field-label">Emoji</label><input class="input" name="emoji" value="📁" autocomplete="off"></div>
    </div>
    <div class="field"><label class="field-label">Label</label><input class="input" name="label" autocomplete="off"></div>
    <div class="field"><label class="field-label">Description</label><input class="input" name="description" autocomplete="off"></div>
    <label class="row" data-import-mcps-row style="cursor:pointer;font-size:13px;margin-top:var(--sp-2);gap:var(--sp-2);align-items:flex-start;display:none">
      <input type="checkbox" name="import_mcps" style="margin-top:3px">
      <span>
        <strong>Importer les MCPs du <code class="mono">.mcp.json</code></strong> dans le registre Nebula.
        <div class="muted" style="font-size:12px">Les MCPs déjà présents dans le registre ne sont pas écrasés.</div>
      </span>
    </label>
    <div class="muted" data-no-signal-warning style="font-size:12px;margin-top:var(--sp-2);display:none">
      Aucun signal Claude détecté dans ce dossier. L'adoption reste possible -- le workspace apparaîtra dans la liste, mais sans skills/MCPs/hooks détectés.
    </div>
  `;
  body.appendChild(step2);

  const cancel = btn('Annuler', 'btn-ghost');
  const adopt = btn('Adopter', 'btn-primary', I.plus);
  adopt.disabled = true;
  const { close } = openModal({ title: 'Adopter un workspace existant', body, footer: [cancel, adopt], wide: true });
  cancel.addEventListener('click', close);

  // Etat partage entre etape 1 et etape 2.
  let lastInspect = null;

  // Slugifie le basename d'un chemin pour proposer un id par defaut.
  // Garde-fou de meme nature que SAFE_ID cote backend (a-z, 0-9, _, -).
  const slugify = (path) => {
    if (!path) return '';
    const parts = path.replace(/\\/g, '/').split('/').filter(Boolean);
    const base = parts[parts.length - 1] || '';
    return base.toLowerCase().replace(/[^a-z0-9_-]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 40);
  };

  // Rend le bloc de resultat d'inspection. Utilise textContent partout pour le
  // chemin (pas d'injection HTML). La structure statique reste innerHTML.
  const renderInspectResult = (r) => {
    const host = step1.querySelector('[data-inspect-result]');
    host.innerHTML = '';
    host.style.display = 'block';

    // Erreur backend (chemin invalide, sous ~/.claude/, etc.) : message brut.
    if (r.error) {
      const errBox = el('div', 'error-box');
      errBox.textContent = r.error;
      host.appendChild(errBox);
      return;
    }

    const pathLine = el('div', 'muted');
    pathLine.style.fontSize = '12px';
    pathLine.style.marginBottom = 'var(--sp-2)';
    const pathStrong = el('strong');
    pathStrong.textContent = r.path || '';
    pathLine.appendChild(document.createTextNode('Chemin inspecté : '));
    pathLine.appendChild(pathStrong);
    host.appendChild(pathLine);

    // Si chemin inexistant : warning explicite, pas de detail.
    if (!r.exists) {
      const w = el('div', 'badge badge-err');
      w.textContent = '⛔ Le dossier n\'existe pas sur disque';
      host.appendChild(w);
      return;
    }

    // Tableau visuel des signaux detectes.
    const grid = el('div', 'adopt-signals');
    grid.style.cssText = 'display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:var(--sp-2);margin:var(--sp-2) 0';
    const addSignal = (ok, label, detail) => {
      const cell = el('div');
      cell.style.cssText = 'display:flex;gap:6px;align-items:flex-start;padding:6px 8px;border:1px solid var(--border);border-radius:6px;background:var(--surface-2)';
      const icon = el('span');
      icon.textContent = ok ? '✓' : '–';
      icon.style.cssText = ok
        ? 'color:var(--ok);font-weight:600;flex-shrink:0'
        : 'color:var(--text-dim);font-weight:400;flex-shrink:0';
      const txt = el('div');
      txt.style.fontSize = '12.5px';
      const lbl = el('div');
      lbl.textContent = label;
      lbl.style.fontWeight = ok ? '500' : '400';
      lbl.style.color = ok ? 'var(--text)' : 'var(--text-dim)';
      txt.appendChild(lbl);
      if (detail) {
        const d = el('div', 'muted');
        d.textContent = detail;
        d.style.fontSize = '11.5px';
        txt.appendChild(d);
      }
      cell.append(icon, txt);
      grid.appendChild(cell);
    };
    addSignal(
      r.has_claude_md,
      r.has_claude_md ? 'CLAUDE.md' : 'Pas de CLAUDE.md',
      r.has_claude_md ? (r.claude_md_size + ' octets') : null
    );
    addSignal(
      r.has_mcp_json,
      r.has_mcp_json ? '.mcp.json' : 'Pas de .mcp.json',
      r.has_mcp_json ? (r.mcps.length + ' MCP' + (r.mcps.length > 1 ? 's' : '')) : null
    );
    addSignal(r.skills_count > 0, r.skills_count + ' skill' + (r.skills_count > 1 ? 's' : ''), null);
    addSignal(r.agents_count > 0, r.agents_count + ' agent' + (r.agents_count > 1 ? 's' : ''), null);
    addSignal(r.commands_count > 0, r.commands_count + ' command' + (r.commands_count > 1 ? 's' : ''), null);
    addSignal(
      !!r.hooks_settings,
      r.hooks_settings ? 'hooks dans settings.json' : 'Pas de hooks',
      r.hooks_settings ? (Object.keys(r.hooks_settings).length + ' événement(s)') : null
    );
    host.appendChild(grid);

    // Liste des MCPs detectes (jusqu'a 8 visibles, le reste compact).
    if (r.has_mcp_json && r.mcps.length) {
      const mcpHeader = el('div', 'muted');
      mcpHeader.style.cssText = 'font-size:12px;margin:var(--sp-2) 0 4px';
      mcpHeader.textContent = 'MCPs détectés :';
      host.appendChild(mcpHeader);
      const mcpList = el('div');
      mcpList.style.cssText = 'display:flex;flex-wrap:wrap;gap:4px';
      const shown = r.mcps.slice(0, 8);
      for (const mcp of shown) {
        const chip = el('span', 'badge');
        chip.style.cssText = 'font-family:var(--font-mono);font-size:11.5px';
        chip.textContent = mcp.name + ' (' + mcp.transport + ')';
        mcpList.appendChild(chip);
      }
      if (r.mcps.length > shown.length) {
        const more = el('span', 'muted');
        more.style.fontSize = '11.5px';
        more.textContent = '+ ' + (r.mcps.length - shown.length) + ' autre(s)';
        mcpList.appendChild(more);
      }
      host.appendChild(mcpList);
    }

    // Warnings (deja adopte, aucun signal). Distincts d'erreur, on adopte
    // quand meme apres confirmation visuelle.
    if (r.warnings && r.warnings.length) {
      const wHost = el('div');
      wHost.style.cssText = 'margin-top:var(--sp-2);display:flex;flex-direction:column;gap:4px';
      for (const w of r.warnings) {
        const wb = el('div', 'badge badge-warn');
        wb.style.fontSize = '12px';
        wb.textContent = '⚠ ' + w;
        wHost.appendChild(wb);
      }
      host.appendChild(wHost);
    }
  };

  // Handler du bouton Inspecter.
  const inspectBtn = step1.querySelector('[data-inspect]');
  inspectBtn.addEventListener('click', () => withBusy(inspectBtn, async () => {
    const path = step1.querySelector('[name=path]').value.trim();
    if (!path) { toastErr('Chemin requis'); return; }
    try {
      const r = await API.post('/api/workspaces/inspect-path', { path });
      lastInspect = r;
      renderInspectResult(r);

      // Affiche etape 2 si inspection OK (au moins exists=true ou exists=false
      // mais on autorise adoption d'un chemin inexistant via re-essai backend ?
      // Non -- on requiert le dossier existant cote adopt(). Donc on n'expose
      // step 2 que si exists=true ET pas deja adopte.
      if (r.exists && !r.already_adopted) {
        step2.style.display = 'block';
        adopt.disabled = false;

        // Pre-remplit id depuis le basename. Garde la valeur user si deja saisie.
        const idInput = step2.querySelector('[name=id]');
        if (!idInput.value) idInput.value = slugify(r.path);
        const labelInput = step2.querySelector('[name=label]');
        if (!labelInput.value) labelInput.value = slugify(r.path);

        // Checkbox import MCPs : visible et cochee par defaut si MCPs detectes.
        const mcpsRow = step2.querySelector('[data-import-mcps-row]');
        const mcpsCb = step2.querySelector('[name=import_mcps]');
        if (r.has_mcp_json && r.mcps.length > 0) {
          mcpsRow.style.display = 'flex';
          mcpsCb.checked = true;
        } else {
          mcpsRow.style.display = 'none';
          mcpsCb.checked = false;
        }

        // Bandeau "aucun signal" : visible si pas un seul signal Claude.
        const hasAnySignal = r.has_claude_md || r.has_mcp_json || r.has_claude_dir
          || r.skills_count || r.agents_count || r.commands_count;
        step2.querySelector('[data-no-signal-warning]').style.display = hasAnySignal ? 'none' : 'block';
      } else {
        step2.style.display = 'none';
        adopt.disabled = true;
      }
    } catch (e) {
      lastInspect = null;
      renderInspectResult({ error: e.message });
      step2.style.display = 'none';
      adopt.disabled = true;
    }
  }));

  // Bouton Adopter (etape 2).
  adopt.addEventListener('click', () => withBusy(adopt, async () => {
    if (!lastInspect || !lastInspect.exists) {
      toastErr('Inspecter le chemin d\'abord');
      return;
    }
    const get = n => step2.querySelector(`[name=${n}]`).value.trim();
    const importMcps = step2.querySelector('[name=import_mcps]').checked;
    const payload = {
      path: lastInspect.path,
      id: get('id'),
      label: get('label'),
      emoji: get('emoji'),
      description: get('description'),
      import_mcps: importMcps,
    };
    if (!payload.id) { toastErr('ID requis'); return; }
    try {
      const r = await API.post('/api/workspaces/adopt', payload);
      // Toast resume : skills/MCPs + ratio ajoutes/skipped si import demande.
      const det = r.detected || {};
      const imp = r.imported || {};
      const parts = [];
      if (det.skills) parts.push(det.skills + ' skill' + (det.skills > 1 ? 's' : ''));
      if (det.agents) parts.push(det.agents + ' agent' + (det.agents > 1 ? 's' : ''));
      if (det.commands) parts.push(det.commands + ' command' + (det.commands > 1 ? 's' : ''));
      if (importMcps && imp.mcps_added) {
        const added = imp.mcps_added.length;
        const skipped = (imp.mcps_skipped || []).length;
        parts.push(added + ' MCP ajouté' + (added > 1 ? 's' : '')
          + (skipped ? ' (' + skipped + ' déjà présent' + (skipped > 1 ? 's' : '') + ')' : ''));
      }
      const summary = parts.length ? ' -- ' + parts.join(', ') : '';
      toastOk('Workspace adopté' + summary);
      close();
      STATE.loading = true;
      location.hash = `#/workspace/${r.id}`;
    } catch (e) {
      toastErr(e.message);
    }
  }));
}

function modalImportMCPs() {
  const body = el('div');
  body.innerHTML = `
    <p class="muted" style="margin-top:0">Colle un objet MCP, un tableau, ou la section <code>mcpServers</code> d'un fichier Claude.</p>
    <div class="field"><label class="field-label" for="import-mcps-json-ta">JSON</label><div data-editor-host></div></div>
    <div class="field"><label class="field-label">Workspaces cibles (optionnel — surchage)</label><input class="input mono" name="ws" placeholder="dev,homeassistant ou *"></div>
    <div class="field" style="border-top:1px solid var(--border);padding-top:var(--sp-3)">
      <label class="field-label">Exporter le registre</label>
      <p class="muted" style="margin:0 0 var(--sp-2) 0;font-size:12px">Génère le JSON <code>mcpServers</code> de TOUS les MCPs actifs (les <code>\${VAR}</code> restent littéraux -- aucun secret) pour le coller sur un autre poste.</p>
      <div class="row" style="gap:var(--sp-2)">
        <button class="btn btn-sm" data-act="export-fill">Pré-remplir le champ ci-dessus</button>
        <button class="btn btn-sm" data-act="export-copy">Copier dans le presse-papier</button>
      </div>
    </div>
  `;
  const cancel = btn('Annuler', 'btn-ghost');
  const imp = btn('Importer', 'btn-primary', I.download);
  // Editeur JSON maison. Ici le champ peut etre vide tant qu'on n'a rien
  // colle : Importer n'est desactive que si le texte saisi est invalide.
  const editor = createJsonEditor({
    value: '', rows: 14, id: 'import-mcps-json', allowEmpty: true, ariaLabel: 'JSON des MCPs à importer',
    onSave: () => { if (!imp.disabled) imp.click(); },
    onValidChange: (ok) => { imp.disabled = !ok; imp.title = ok ? '' : 'Colle un JSON valide pour pouvoir importer'; },
  });
  body.querySelector('[data-editor-host]').appendChild(editor.el);
  const { close } = openModal({ title: 'Importer / exporter des MCPs', body, footer: [cancel, imp], wide: true });
  cancel.addEventListener('click', close);

  // Export à la demande depuis le registre (F5.1 : plus de fichier figé
  // import-mcps.json maintenu à la main).
  async function fetchExport() {
    const r = await API.get('/api/mcps/export');
    return JSON.stringify(r, null, 2);
  }
  body.querySelector('[data-act=export-fill]').addEventListener('click', async () => {
    try { editor.setValue(await fetchExport(), { silent: false }); toastOk('Registre exporté dans le champ'); }
    catch (e) { toastErr(e.message); }
  });
  body.querySelector('[data-act=export-copy]').addEventListener('click', async () => {
    try {
      const txt = await fetchExport();
      await navigator.clipboard.writeText(txt);
      toastOk('Export copié dans le presse-papier');
    } catch (e) { toastErr('Copie impossible : ' + e.message); }
  });
  imp.addEventListener('click', async () => {
    const check = editor.validate();
    if (!check.ok) { toastErr(`JSON invalide, ligne ${check.line} : ${check.msg}`); return; }
    const obj = check.value;
    const ws = body.querySelector('[name=ws]').value.split(',').map(s => s.trim()).filter(Boolean);
    if (ws.length) obj.workspaces = ws;
    try {
      const r = await API.post('/api/mcps/import', obj);
      const created = r.created || [];
      const overwritten = r.overwritten || [];
      const failed = (r.results || []).filter(x => !x.ok);
      // Récap explicite : un import écrasait un id existant en silence.
      // On distingue créés / écrasés (audit UX Lot G item 2).
      let msg = `${created.length} créé(s)`;
      if (overwritten.length) msg += `, ${overwritten.length} écrasé(s) : ${overwritten.join(', ')}`;
      if (failed.length) msg += ` -- ${failed.length} en échec`;
      // Un écrasement mérite un toast info plus long (l'utilisateur doit lire
      // quels ids existants ont été remplacés), un import 100% création = ok bref.
      if (overwritten.length) toast(msg, 'info', 7000);
      else toastOk(msg);
      close(); STATE.loading = true; route();
    } catch (e) { toastErr(e.message); }
  });
}

/* ================================================================
   PAGE: PLUGINS
   ================================================================ */
/* ================================================================
   PAGE PLUGINS (marketplace + installed + scope par workspace)
   ================================================================ */

/* ================================================================
   PAGE: AIDE
   ================================================================ */
// ── Aide : contenu des sections (réutilisé par les sous-pages) ─────────────

/* ================================================================
   PAGE: SKILLS
   ================================================================ */
/* ================================================================
   PAGE SKILLS (library + global + scope par workspace + import GitHub)
   ================================================================ */

/* ================================================================
   PAGE: TEMPLATES
   ================================================================ */
/* ================================================================
   PAGE TEMPLATES (catalogue + édition + duplication)
   ================================================================ */

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

/* Page Tools (renderTools, loadEnvVars, loadBackups) extraite en
   js/pages/tools.js. renderGlobalSkills appartient a la page Skills
   (extraction prochaine). */

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
        try {
          await API.del(`/api/skills/global/${s.id}`);
          toastOk('Supprimé');
          STATE.skills = (STATE.skills || []).filter(x => x.id !== s.id);
          route({ silent: true });
        }
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
  // Section "Modules optionnels" : checkboxes des overlays disponibles.
  // L'overlay est applique APRES le template de base (idempotent, ne
  // touche pas aux fichiers deja generes par le template).
  const overlays = (STATE.overlays || []).slice()
    .sort((a, b) => (b.id === SELF_IMPROVING_ID) - (a.id === SELF_IMPROVING_ID));
  const overlaysSection = overlays.length ? `
    <div class="field">
      <label class="field-label" id="ov-pick-label">Modules optionnels</label>
      <div class="muted" style="font-size:12px;margin-bottom:6px">
        Appliqués par-dessus le template choisi. N'écrasent jamais un fichier déjà présent ; activables aussi plus tard depuis l'onglet Configuration du workspace.
      </div>
      <div class="ov-pick" role="group" aria-labelledby="ov-pick-label" data-overlays-host>
        ${overlays.map(o => {
          const si = o.id === SELF_IMPROVING_ID;
          return `
          <label class="ov-opt${si ? ' featured' : ''}">
            <input type="checkbox" name="overlay" value="${escapeHtml(o.id)}">
            <span class="ov-e" aria-hidden="true">${escapeHtml(o.emoji || '🧩')}</span>
            <span style="min-width:0">
              <b>${escapeHtml(o.label || o.id)}${si ? '<span class="pill accent ov-tag">Recommandé</span>' : ''}</b>
              <span class="ov-d" style="display:block">${si
                ? "Mémoire structurée (.claude/memory), pipeline ideas → backlog → improvements, agents et commandes (/pipeline, /check-all…), hooks Python pré-commit. Après création : lancer Claude et dire « bootstrap le projet »."
                : escapeHtml(o.description || '')}</span>
            </span>
          </label>`;
        }).join('')}
      </div>
    </div>
  ` : '';
  body.innerHTML = `
    <div class="field-row">
      <div class="field"><label class="field-label">ID *</label><input class="input mono" name="id" placeholder="mon-projet"></div>
      <div class="field"><label class="field-label">Emoji</label><input class="input" name="emoji" value="📁"></div>
    </div>
    <div class="field"><label class="field-label">Label</label><input class="input" name="label" placeholder="Mon Projet"></div>
    <div class="field"><label class="field-label">Description</label><input class="input" name="description"></div>
    <div class="field"><label class="field-label">Outils / contexte</label><input class="input" name="tools" placeholder="Python, Docker, n8n..."></div>
    <div class="field"><label class="field-label">Template</label><select class="select" name="template">${STATE.templates.map(t => `<option value="${escapeHtml(t.id)}">${escapeHtml(t.emoji || '📦')} ${escapeHtml(t.label || t.id)}</option>`).join('') || '<option value="blank">Blank</option>'}</select></div>
    ${overlaysSection}
  `;
  const cancel = btn('Annuler', 'btn-ghost');
  const create = btn('Créer', 'btn-primary', I.plus);
  const { close } = openModal({ title: 'Nouveau workspace', body, footer: [cancel, create] });
  cancel.addEventListener('click', close);
  create.addEventListener('click', () => withBusy(create, async () => {
    const get = n => body.querySelector(`[name=${n}]`).value.trim();
    const selectedOverlays = Array.from(body.querySelectorAll('input[name="overlay"]:checked')).map(el => el.value);
    const payload = {
      id: get('id'), emoji: get('emoji'), label: get('label'),
      description: get('description'), tools: get('tools'),
      template: get('template') || 'blank',
      overlays: selectedOverlays,
    };
    if (!payload.id) { toastErr('ID requis'); return; }
    try {
      const r = await API.post('/api/workspaces', payload);
      // Resume des overlays appliques (s'il y en a) : on ne fait pas
      // d'echec bloquant si un overlay echoue, on remonte juste un toast
      // d'info pour ne pas masquer la creation reussie du workspace.
      const ovApplied = (r.overlays || []).filter(o => o.ok);
      const ovFailed = (r.overlays || []).filter(o => !o.ok);
      if (ovApplied.length) {
        const n = ovApplied.reduce((s, o) => s + (o.copied || []).length, 0);
        toastOk(`Workspace créé · ${ovApplied.length} module(s) appliqué(s), ${n} fichier(s) ajouté(s)`);
      } else {
        toastOk('Workspace créé');
      }
      for (const f of ovFailed) toastErr(`Overlay ${f.id} : ${f.error || 'échec'}`);
      close(); STATE.loading = true; location.hash = `#/workspace/${payload.id}`;
    }
    catch (e) { toastErr(e.message); }
  }));
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
  save.addEventListener('click', () => withBusy(save, async () => {
    const get = n => body.querySelector(`[name=${n}]`).value.trim();
    try { await API.post(`/api/workspaces/${w.id}/update`, { label: get('label'), emoji: get('emoji'), description: get('description'), path: get('path') }); toastOk('Mis à jour'); close(); STATE.loading = true; route(); }
    catch (e) { toastErr(e.message); }
  }));
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
  dup.addEventListener('click', () => withBusy(dup, async () => {
    const get = n => body.querySelector(`[name=${n}]`).value.trim();
    try { await API.post('/api/workspaces/duplicate', { source: w.id, id: get('id'), label: get('label'), description: get('description'), emoji: w.emoji }); toastOk('Dupliqué'); close(); STATE.loading = true; location.hash = `#/workspace/${get('id')}`; }
    catch (e) { toastErr(e.message); }
  }));
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

function modalPermissions(wsId, onSaved = null) {
  (async () => {
    let settings = {};
    try { settings = JSON.parse((await API.get(`/api/workspaces/${wsId}/settings`)).content) || {}; } catch (e) { console.warn(`[permissions] parse settings.json ws=${wsId} échoué :`, e.message); }
    const perms = settings.permissions || {};
    const allow = (perms.allow || []).join('\n');
    const deny = (perms.deny || []).join('\n');
    const body = el('div');
    body.innerHTML = `
      <p class="muted" style="margin-top:0">Une règle par ligne. Ex : <code class="mono">Bash(npm:*)</code>, <code class="mono">mcp__server__tool</code> (doubles underscores), <code class="mono">mcp__server__*</code></p>
      <div class="field"><label class="field-label text-ok">Allow</label><textarea class="textarea" name="allow" rows="6">${escapeHtml(allow)}</textarea><div class="perm-lint" data-lint="allow" style="font-size:11.5px;margin-top:4px"></div></div>
      <div class="field"><label class="field-label text-err">Deny</label><textarea class="textarea" name="deny" rows="6">${escapeHtml(deny)}</textarea><div class="perm-lint" data-lint="deny" style="font-size:11.5px;margin-top:4px"></div></div>
    `;
    // Validation live (item 2) : marque les lignes douteuses sous chaque
    // textarea. WARN non-bloquant (la liste des outils natifs n'est pas
    // exhaustive) ; le save propose une confirmation s'il en reste.
    const lintField = (which) => {
      const ta = body.querySelector(`[name=${which}]`);
      const host = body.querySelector(`[data-lint=${which}]`);
      const bad = ta.value.split('\n').map(s => s.trim()).filter(Boolean)
        .filter(line => !isValidPermissionLine(line));
      if (!bad.length) { host.innerHTML = ''; return []; }
      host.innerHTML = bad.map(line =>
        `<div class="text-err">⚠ ${escapeHtml(permissionHint(line))}</div>`
      ).join('');
      return bad;
    };
    body.querySelector('[name=allow]').addEventListener('input', () => lintField('allow'));
    body.querySelector('[name=deny]').addEventListener('input', () => lintField('deny'));
    lintField('allow'); lintField('deny');

    const cancel = btn('Annuler', 'btn-ghost');
    const save = btn('Enregistrer', 'btn-primary');
    const { close } = openModal({ title: 'Permissions', body, footer: [cancel, save], wide: true });
    cancel.addEventListener('click', close);
    const doSave = async () => {
      const a = body.querySelector('[name=allow]').value.split('\n').map(s => s.trim()).filter(Boolean);
      const d = body.querySelector('[name=deny]').value.split('\n').map(s => s.trim()).filter(Boolean);
      const value = (a.length || d.length) ? { allow: a, deny: d } : null;
      try { await API.post(`/api/workspaces/${wsId}/settings/permissions`, { value }); toastOk('Enregistré'); close(); if (onSaved) onSaved(); }
      catch (e) { toastErr(e.message); }
    };
    save.addEventListener('click', () => withBusy(save, async () => {
      const bad = [...lintField('allow'), ...lintField('deny')];
      if (bad.length) {
        confirmDialog(
          `${bad.length} règle(s) au format douteux (ex : « ${bad[0]} »). `
          + `Une permission mal formée est ignorée en silence par Claude Code. Enregistrer quand même ?`,
          () => withBusy(save, doSave)
        );
        return;
      }
      await doSave();
    }));
  })();
}

// Viewer minimaliste pour le log d'erreurs des hooks Claude Code (lit
// dashboard/data/hook_errors.log). Les hooks .sh n'ecrivent pas a disque
// par defaut -- ce viewer affiche surtout les erreurs des hooks qui
// redirigent explicitement vers ce log.
function modalHooksErrorsViewer() {
  const body = el('div');
  body.innerHTML = '<div class="page-loader"><div class="spinner"></div><span>Chargement…</span></div>';
  const refreshBtn = btn('Rafraîchir', 'btn-sm btn-ghost', I.refresh);
  const close = btn('Fermer', 'btn-ghost');
  const { close: doClose } = openModal({ title: "Erreurs hooks récentes", body, footer: [refreshBtn, close], wide: true });
  close.addEventListener('click', doClose);

  const reload = async () => {
    body.innerHTML = '<div class="page-loader"><div class="spinner"></div><span>Chargement…</span></div>';
    try {
      const r = await API.get('/api/hooks/errors?tail=200');
      body.innerHTML = '';
      const meta = el('div', 'dim');
      meta.style.cssText = 'font-size:11.5px;margin-bottom:var(--sp-2)';
      if (!r.exists) {
        meta.textContent = r.note || 'Aucun log.';
        body.appendChild(meta);
        return;
      }
      meta.textContent = `${r.path} · ${fmtBytes(r.size || 0)} · ${r.tail_lines || 0} lignes affichées`;
      body.appendChild(meta);
      if (!r.lines || r.lines.length === 0) {
        body.appendChild(el('div', 'dim', '<span style="font-size:12.5px">Log vide. Tant mieux : aucune erreur réflexive enregistrée.</span>'));
        return;
      }
      const pre = document.createElement('pre');
      pre.className = 'mono';
      pre.style.cssText = 'background:var(--bg);padding:var(--sp-3);border-radius:var(--r-sm);border:1px solid var(--border);font-size:11.5px;line-height:1.55;max-height:60vh;overflow:auto;white-space:pre-wrap;margin:0';
      pre.textContent = r.lines.join('\n');
      body.appendChild(pre);
    } catch (e) {
      body.innerHTML = `<div class="error-box">${escapeHtml(e.message)}</div>`;
    }
  };
  refreshBtn.addEventListener('click', reload);
  reload();
}

function modalHooks(wsId, onSaved = null) {
  (async () => {
    let current = {};
    if (wsId) {
      try { const s = JSON.parse((await API.get(`/api/workspaces/${wsId}/settings`)).content); current = s.hooks || {}; } catch (e) { console.warn(`[hooks] parse settings.json ws=${wsId} échoué :`, e.message); }
    } else {
      try { current = (await API.get('/api/hooks/global')).hooks || {}; } catch (e) { console.warn('[hooks] fetch hooks globaux échoué :', e.message); }
    }
    const body = el('div');
    body.innerHTML = `
      <p class="muted" style="margin-top:0">JSON des hooks Claude Code. ${wsId ? 'Spécifique au workspace.' : 'Configuration globale.'}</p>
      <div class="field" data-editor-host></div>
    `;
    // Zone de restauration depuis .bak (item D-2). Insérée sous l'éditeur,
    // peuplée async une fois la modale ouverte (n'affiche rien si pas de .bak).
    const restoreHost = el('div');
    restoreHost.style.marginTop = 'var(--sp-2)';
    body.appendChild(restoreHost);

    const cancel = btn('Annuler', 'btn-ghost');
    const save = btn('Enregistrer', 'btn-primary');
    // Garde anti-perte de saisie.
    const guard = makeDirtyGuard();
    // Editeur JSON maison : validation en direct, Enregistrer desactive si invalide.
    const editor = createJsonEditor({
      value: JSON.stringify(current, null, 2), rows: 16,
      ariaLabel: wsId ? `Hooks du workspace ${wsId} (JSON)` : 'Hooks globaux (JSON)',
      onChange: () => guard.markDirty(),
      onSave: () => { if (!save.disabled) save.click(); },
      onValidChange: (ok) => { save.disabled = !ok; save.title = ok ? '' : 'Corrige le JSON pour pouvoir enregistrer'; },
    });
    body.querySelector('[data-editor-host]').appendChild(editor.el);
    const { close, requestClose } = openModal({ title: wsId ? `Hooks · ${wsId}` : 'Hooks globaux', body, footer: [cancel, save], wide: true, confirmClose: guard.confirmClose });
    guard.bind(close);
    cancel.addEventListener('click', requestClose);

    // Charge l'existence d'une sauvegarde et propose la restauration.
    const backupUrl = wsId ? `/api/workspaces/${wsId}/hooks/backup` : '/api/hooks/backup';
    const restoreUrl = wsId ? `/api/workspaces/${wsId}/hooks/restore` : '/api/hooks/restore';
    (async () => {
      let bk;
      try { bk = await API.get(backupUrl); }
      catch (e) { console.warn('[hooks] lecture .bak échouée :', e.message); return; }
      if (!bk || !bk.exists) return;

      const box = el('div', 'callout callout-info');
      box.style.cssText = 'margin-top:var(--sp-2)';
      if (!bk.readable) {
        box.innerHTML = `<div><strong>Sauvegarde présente mais illisible</strong> <span class="dim">(.bak corrompu)</span></div>`;
        restoreHost.appendChild(box);
        return;
      }
      const bakHooks = bk.hooks || {};
      const when = bk.mtime ? fmtDate(bk.mtime) : 'date inconnue';
      box.innerHTML = `
        <div>
          <strong>↩ Version précédente disponible</strong>
          <span class="dim" style="font-size:11.5px">-- sauvegardée le ${escapeHtml(when)}</span>
          <p style="margin:4px 0 0;font-size:11.5px" class="dim">Restaure le <code class="mono">settings.json</code> à son état d'avant la dernière sauvegarde. La version actuelle est conservée comme nouvelle sauvegarde (action réversible).</p>
          <details style="margin-top:6px"><summary style="cursor:pointer;font-size:11.5px;color:var(--text-muted)">Aperçu des hooks de la sauvegarde</summary><pre class="mono" style="font-size:10.5px;background:var(--bg);padding:var(--sp-2);border-radius:4px;margin-top:6px;white-space:pre-wrap;max-height:160px;overflow:auto">${escapeHtml(JSON.stringify(bakHooks, null, 2))}</pre></details>
        </div>
      `;
      const restoreBtn = btn('Restaurer la version précédente', 'btn-sm', I.refresh);
      restoreBtn.style.marginTop = 'var(--sp-2)';
      restoreBtn.addEventListener('click', () => {
        confirmDialog(
          'Restaurer la version précédente des hooks ?\n\nLe settings.json actuel sera remplacé par la sauvegarde. La version actuelle est conservée comme nouvelle sauvegarde -- tu pourras revenir en arrière.',
          () => withBusy(restoreBtn, async () => {
            try {
              const resp = await API.post(restoreUrl, {});
              const restored = (resp && resp.hooks) || {};
              editor.setValue(JSON.stringify(restored, null, 2));
              guard.markSaved();
              toastOk('Version précédente restaurée');
              close();
            } catch (e) { toastErr(e.message); }
          }),
          { danger: true, confirmLabel: 'Restaurer' }
        );
      });
      box.appendChild(restoreBtn);
      restoreHost.appendChild(box);
    })();
    save.addEventListener('click', () => withBusy(save, async () => {
      const check = editor.validate();
      if (!check.ok) { toastErr(`JSON invalide, ligne ${check.line} : ${check.msg}`); return; }
      const hooks = check.value;
      // Miroir front du lint backend (item 3a) : chemin .sh relatif =
      // BLOQUANT (casserait toutes les sessions). Feedback immédiat sans
      // aller-retour réseau ; le backend refuse aussi par sécurité.
      const relSh = lintHooksRelativeSh(hooks);
      if (relSh.length) {
        const h = relSh[0];
        toastErr(`Chemin de hook relatif dans « ${h.event} » : « ${h.badPath} ». `
          + `Utilise \${CLAUDE_PROJECT_DIR}/.claude/hooks/${h.badPath.split(/[\\/]/).pop()} `
          + `(un chemin relatif casse dès que le shell dérive).`);
        return;
      }
      try {
        let resp;
        if (wsId) resp = await API.post(`/api/workspaces/${wsId}/settings/hooks`, { value: Object.keys(hooks).length ? hooks : null });
        else resp = await API.post('/api/hooks/global', { hooks });
        // Affiche les warnings non bloquants remontés par le backend
        // (3b fichier hook absent, 3c événement inconnu).
        const warns = (resp && resp.hook_warnings) || [];
        if (warns.length) {
          toastOk('Enregistré (avec avertissements)');
          for (const w of warns.slice(0, 3)) toastErr(w.msg);
        } else {
          toastOk('Enregistré');
        }
        guard.markSaved(); close();
        if (onSaved) onSaved();
      } catch (e) { toastErr(e.message); }
    }));
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
    const doSave = async () => {
      try { await API.post(`/api/skills/${scope}/${name}/content`, { content: ta.value }); toastOk('Enregistré'); close(); }
      catch (e) { toastErr(e.message); }
    };
    save.addEventListener('click', () => withBusy(save, async () => {
      // Validation frontmatter (item 5a) : un SKILL.md sans name+description
      // valides est invisible pour Claude (auto-découverte échoue). WARN fort
      // non-bloquant -> confirmation.
      const fm = validateSkillFrontmatter(ta.value);
      if (!fm.ok) {
        const what = fm.missing.length === 2
          ? 'aucun frontmatter `name`+`description` valide'
          : `pas de \`${fm.missing[0]}\` dans le frontmatter`;
        confirmDialog(
          `Ce SKILL.md n'a ${what}. Sans frontmatter \`name\`+\`description\` valide, `
          + `Claude ne verra pas ce skill (auto-découverte échouée). Enregistrer quand même ?`,
          () => withBusy(save, doSave)
        );
        return;
      }
      await doSave();
    }));
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
    save.addEventListener('click', () => withBusy(save, async () => {
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
    }));
  })();
}

/* ================================================================
   COMMAND PALETTE
   ================================================================ */
/* ================================================================
   PALETTE Ctrl+K (refonte 2026-10)
   ----------------------------------------------------------------
   Index local (aucune requete) : workspaces (etat de session), actions
   (lancer / reprendre, sync, creer, matrice...), pages, styles, MCPs,
   skills, templates, aide. Score : sous-chaine (bonus debut de mot) puis
   initiales (« ha » -> Home Assistant) ; surlignage <mark> ; groupes
   ordonnes par meilleur score. ARIA : dialog + combobox + listbox/option
   (aria-activedescendant), focus restaure a la fermeture.
   ================================================================ */
function paletteItems() {
  const items = [];
  const go = (h) => () => { location.hash = h; };
  for (const w of STATE.workspaces || []) {
    const st = sessionState(w.id);
    items.push({
      g: 'Workspaces', t: w.label || w.id, d: w.id + (w.description ? '  ' + w.description : ''), gem: w,
      r: st === 'running' ? '<span class="pill ok"><span class="sdot live"></span>En direct</span>'
        : st === 'idle' ? '<span class="pill warn">Terminal ouvert</span>' : '',
      run: go(`#/workspace/${w.id}`),
    });
  }
  for (const w of STATE.workspaces || []) {
    const st = sessionState(w.id);
    if (st) items.push({ g: 'Actions', t: 'Reprendre ' + (w.label || w.id), d: 'Reprendre la dernière session Claude Code', ic: I.terminal, hidden: true, run: () => doResume(w, null) });
    else items.push({ g: 'Actions', t: 'Lancer ' + (w.label || w.id), d: 'Ouvre Claude Code dans ce workspace', ic: I.play, hidden: true, run: () => doLaunch(w, null) });
  }
  items.push(
    { g: 'Actions', t: 'Synchroniser tous les workspaces', d: 'Registre MCP vers chaque .mcp.json', ic: I.refresh, run: async () => {
      try { const r = await API.post('/api/sync-all', {}); toastOk('Sync terminé pour ' + Object.keys(r.results || {}).length + ' workspace(s)'); warnHandEdited(collectHandEdited(r.results)); }
      catch (e) { toastErr(e.message); }
    } },
    { g: 'Actions', t: 'Nouveau workspace', d: 'Créer depuis un template', ic: I.plus, run: () => modalNewWorkspace() },
    { g: 'Actions', t: 'Nouveau MCP', d: 'Ajouter un serveur au registre', ic: I.plus, run: () => modalNewMCP() },
    { g: 'Actions', t: 'Ouvrir la matrice MCPs', d: 'MCP × workspace', ic: I.grid, run: () => { setMcpViewMode('matrix'); if (location.hash === '#/mcps') route(); else location.hash = '#/mcps'; } },
    { g: 'Actions', t: 'Adopter un workspace existant', d: 'Enregistrer un dossier déjà présent sur le disque', ic: I.folder, hidden: true, run: () => modalRegisterExisting() },
    { g: 'Actions', t: 'Importer la config Claude', d: 'MCPs et projets de ~/.claude/', ic: I.download, hidden: true, run: () => modalSetupWizard() },
  );
  for (const n of NAV_ITEMS) {
    if (n.section) continue;
    items.push({ g: 'Aller à', t: n.label, ic: n.icon, k: n.key ? 'g ' + n.key : '', run: go(n.route) });
  }
  for (const t of (typeof THEMES !== 'undefined' ? THEMES : [])) {
    items.push({ g: 'Style', t: 'Style : ' + t.label, d: t.desc, ic: I.palette, hidden: true, run: () => applyTheme(t.id) });
  }
  for (const m of STATE.mcps || []) {
    items.push({ g: 'MCPs', t: m.name || m.id, d: `${m.id}  ${m.transport || 'stdio'}`, ic: (m.transport === 'http' || m.transport === 'sse') ? I.ext : I.terminal, hidden: true,
      run: () => { STATE.filter.mcp = m.id; if (location.hash === '#/mcps') route(); else location.hash = '#/mcps'; } });
  }
  for (const s of STATE.skills || []) {
    items.push({ g: 'Skills', t: s.name || s.id, d: s.description || '', ic: I.sparkle, hidden: true, run: go('#/skills') });
  }
  for (const t of STATE.templates || []) {
    items.push({ g: 'Templates', t: t.label || t.id, d: t.description || t.id, ic: I.layers, hidden: true, run: go('#/templates') });
  }
  return items;
}

// Score d'un libelle : null si pas de correspondance, sinon {s, h} (html surligne).
function paletteScore(t, q) {
  if (!q) return { s: 1, h: escapeHtml(t) };
  const tl = t.toLowerCase();
  const i = tl.indexOf(q);
  if (i >= 0) {
    const start = i === 0 || /[\s\-_:./]/.test(tl[i - 1]);
    return { s: 100 - Math.min(i, 60) + (start ? 20 : 0), h: escapeHtml(t.slice(0, i)) + '<mark>' + escapeHtml(t.slice(i, i + q.length)) + '</mark>' + escapeHtml(t.slice(i + q.length)) };
  }
  // Initiales : « ha » trouve « Home Assistant ».
  const words = [...t.matchAll(/[^\s\-_]+/g)];
  if (q.length >= 2 && words.length >= q.length && words.slice(0, q.length).every((w, k) => w[0][0].toLowerCase() === q[k])) {
    let h = ''; let last = 0;
    words.slice(0, q.length).forEach(w => { h += escapeHtml(t.slice(last, w.index)) + '<mark>' + escapeHtml(w[0][0]) + '</mark>'; last = w.index + 1; });
    return { s: 120, h: h + escapeHtml(t.slice(last)) };
  }
  return null;
}

function openPalette() {
  const root = $('#palette-root');
  if (root.querySelector('.palette')) { root.querySelector('input').focus(); return; }
  root.innerHTML = '';
  const overlay = el('div', 'palette-overlay');
  const palette = el('div', 'palette');
  palette.setAttribute('role', 'dialog');
  palette.setAttribute('aria-modal', 'true');
  palette.setAttribute('aria-label', 'Recherche et actions rapides');
  palette.innerHTML = `
    <div class="pal-in">${I.search}<input class="palette-input" type="text" role="combobox" aria-expanded="true" aria-controls="pal-list" aria-autocomplete="list" aria-label="Rechercher un workspace, un MCP, une action, un style" placeholder="Workspace, MCP, action, style…" autocomplete="off" spellcheck="false"><kbd class="k">Échap</kbd></div>
    <div class="pal-list palette-list" id="pal-list" role="listbox" aria-label="Résultats"></div>
    <div class="pal-foot palette-hint"><span><kbd class="k">↑</kbd><kbd class="k">↓</kbd> naviguer</span><span><kbd class="k">Entrée</kbd> exécuter</span><span><kbd class="k">Échap</kbd> fermer</span><span style="margin-left:auto"><kbd class="k">g</kbd> puis <kbd class="k">h</kbd>/<kbd class="k">m</kbd>… pour naviguer partout</span></div>`;
  overlay.appendChild(palette);
  root.appendChild(overlay);
  const input = palette.querySelector('input');
  const list = palette.querySelector('.pal-list');
  const all = paletteItems();
  let res = [];
  let sel = 0;

  // Sauvegarde du focus precedent pour le restaurer a la fermeture.
  const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  const close = () => {
    root.innerHTML = '';
    document.removeEventListener('keydown', onKey, true);
    const restore = (previouslyFocused && document.body.contains(previouslyFocused))
      ? previouslyFocused : $('#topbar-search');
    if (restore) { try { restore.focus(); } catch { /* noop */ } }
  };
  const runItem = (it) => { close(); if (it) it.run(); };

  const draw = () => {
    const q = input.value.trim().toLowerCase();
    let scored = all.map(it => {
      if (!q && it.hidden) return null;
      const r = paletteScore(it.t, q) || (q.length >= 3 && (it.d || '').toLowerCase().includes(q) ? { s: 1, h: escapeHtml(it.t) } : null);
      return r ? { ...it, ...r } : null;
    }).filter(Boolean);
    if (q && typeof helpPaletteEntries === 'function') {
      for (const h of helpPaletteEntries(q)) scored.push({ g: 'Aide', t: h.label, h: escapeHtml(h.label), s: 2, ic: I.book, run: () => { location.hash = h.route; } });
    }
    const best = {};
    scored.forEach(r => { best[r.g] = Math.max(best[r.g] || 0, r.s); });
    const order = q ? Object.keys(best).sort((a, b) => best[b] - best[a]) : ['Workspaces', 'Actions', 'Aller à'];
    res = order.flatMap(g => scored.filter(r => r.g === g).sort((a, b) => b.s - a.s).slice(0, q ? 8 : 6));
    sel = Math.min(sel, Math.max(0, res.length - 1));
    if (!res.length) {
      list['innerHTML'] = `<div class="pal-empty" role="presentation">Rien ne correspond à « ${escapeHtml(input.value)} ».</div>`;
      input.removeAttribute('aria-activedescendant');
      return;
    }
    let g = null; let html = '';
    res.forEach((it, i) => {
      if (it.g !== g) { g = it.g; html += `<div class="pal-g" role="presentation">${escapeHtml(g)}</div>`; }
      html += `<div class="pi" role="option" id="pal-opt-${i}" data-i="${i}" aria-selected="${i === sel}">`
        + (it.gem ? wsGem(it.gem) : `<span class="pic">${it.ic || ''}</span>`)
        + `<b>${it.h}</b>${it.d ? `<span class="pd">${escapeHtml(it.d)}</span>` : ''}`
        + `<span class="pr">${it.r || ''}${it.k ? `<kbd class="k">${escapeHtml(it.k)}</kbd>` : ''}<span class="ret" aria-hidden="true">${I.ret}</span></span></div>`;
    });
    list['innerHTML'] = html;
    input.setAttribute('aria-activedescendant', 'pal-opt-' + sel);
  };
  const move = (d) => {
    if (!res.length) return;
    sel = (sel + d + res.length) % res.length;
    list.querySelectorAll('.pi').forEach(p => p.setAttribute('aria-selected', String(+p.dataset.i === sel)));
    const elSel = list.querySelector('#pal-opt-' + sel);
    if (elSel) elSel.scrollIntoView({ block: 'nearest' });
    input.setAttribute('aria-activedescendant', 'pal-opt-' + sel);
  };

  input.addEventListener('input', () => { sel = 0; draw(); });
  const onKey = (e) => {
    if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); close(); return; }
    if (e.key === 'ArrowDown') { e.preventDefault(); move(1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); move(-1); }
    else if (e.key === 'Enter') { e.preventDefault(); runItem(res[sel]); }
    else if (e.key === 'Tab') { e.preventDefault(); input.focus(); }
  };
  document.addEventListener('keydown', onKey, true);
  list.addEventListener('mousemove', (e) => {
    const p = e.target.closest('.pi');
    if (p && +p.dataset.i !== sel) { sel = +p.dataset.i; move(0); }
  });
  list.addEventListener('click', (e) => { const p = e.target.closest('.pi'); if (p) runItem(res[+p.dataset.i]); });
  overlay.addEventListener('mousedown', (e) => { if (e.target === overlay) close(); });
  draw();
  input.focus();
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
  if (e.key === '/' || (e.key === 'k' && (e.metaKey || e.ctrlKey) && !e.altKey)) {
    e.preventDefault(); openPalette(); return;
  }
  // Raccourcis simple-touche n/m/s retirés : ils se déclenchaient sur
  // n'importe quelle frappe hors input, ouvrant des modals par accident.
  // Les chords 'g <lettre>' ci-dessous couvrent la navigation. Pour
  // créer rapidement, passer par la palette ('/' ou Ctrl+K).
  // 'g' chord -> next key navigates
  if (e.key === 'g') { lastKey = 'g'; lastKeyAt = Date.now(); return; }
  if (lastKey === 'g' && Date.now() - lastKeyAt < 1000) {
    const map = { h: '#/', m: '#/mcps', p: '#/plugins', k: '#/skills', t: '#/templates', o: '#/tools', a: '#/aide' };
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
      target: '#ws-host, .empty', navigate: '#/',
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
      title: '📦 Templates — moules de workspaces',
      body: `<p>Un template, c'est l'arborescence de fichiers copiée à chaque <em>Nouveau workspace</em>. Le bouton <strong>+ Nouveau template</strong> propose des starters (Standard, Python, Node, Docker).</p>
        <p>Chaque template a un panneau <em>Conseils & qualité</em> qui scanne les bonnes pratiques.</p>`,
      target: '.page', navigate: '#/templates',
    },
    {
      title: '🛡️ Santé + Journal sur la home',
      body: `<p>De retour à l'accueil. La colonne Activité contient :</p>
        <ul style="margin:6px 0;padding-left:18px;font-size:13px">
          <li><strong>Santé</strong> : signale les configs MCP cassées, désynchronisées ou inutilisées.</li>
          <li><strong>Journal</strong> : tes notes rapides projet par projet.</li>
        </ul>`,
      target: '.rail', navigate: '#/',
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
  // Focus a restaurer a la sortie du tour.
  const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  STATE.tour = { name, step: startStep, definition: def, previouslyFocused, releaseTrap: null };
  tourGoto(startStep);
  // Piege le Tab dans la bulle (Escape/fleches restent geres par
  // _tourKeyHandler, donc pas de onEscape ici pour eviter le double-handler).
  const bubble = document.querySelector('#tour-overlay .tour-bubble');
  if (bubble) STATE.tour.releaseTrap = createFocusTrap(bubble);
  // Échap pour quitter
  window.addEventListener('keydown', _tourKeyHandler);
  // Reposition sur resize
  window.addEventListener('resize', _tourResizeHandler);
  // Autofocus sur le bouton « Suivant » a l'ouverture.
  setTimeout(() => {
    const next = document.querySelector('#tour-overlay [data-tour-next]');
    if (next) { try { next.focus(); } catch { /* noop */ } }
  }, 60);
}

function endTour() {
  const overlay = document.getElementById('tour-overlay');
  if (overlay) overlay.classList.remove('is-active');
  const prev = STATE.tour && STATE.tour.previouslyFocused;
  if (STATE.tour && STATE.tour.releaseTrap) STATE.tour.releaseTrap();
  STATE.tour = null;
  window.removeEventListener('keydown', _tourKeyHandler);
  window.removeEventListener('resize', _tourResizeHandler);
  try { sessionStorage.removeItem('nebula-tour-progress'); } catch {}
  try { localStorage.setItem('nebula-tour-completed', '1'); } catch {}
  if (prev && document.body.contains(prev)) { try { prev.focus(); } catch { /* noop */ } }
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
  // Declencheur ⌘K dans la topbar (cf. prototype command-center). Meme
  // palette que #open-palette / le raccourci clavier '/' et Ctrl+K.
  const topbarSearch = $('#topbar-search');
  if (topbarSearch) topbarSearch.addEventListener('click', openPalette);
  // Hote reel (carte profil sidebar) : source de verite = location.host.
  const hostEl = $('#sidebar-host');
  if (hostEl && location.host) hostEl.textContent = location.host;
  // Sous 900px la sidebar devient une barre horizontale (css/shell-mobile.css) :
  // plus de tiroir ni de bouton menu.
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
      checkForUpdates().then(renderUpdateBadge).catch(e => console.warn('[updates] check au boot échoué :', e.message));
    }, 1500);

    // Re-check périodique (toutes les 30 min) sans force, donc respecte
    // l'anti-spam UPDATE_CHECK_INTERVAL_MS pour le fetch distant.
    // Ce poller global n'est PAS géré par clearPagePollers (volontaire).
    setInterval(() => {
      checkForUpdates().then(renderUpdateBadge).catch(e => console.warn('[updates] check périodique échoué :', e.message));
    }, 30 * 60 * 1000);
  });
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
else init();
