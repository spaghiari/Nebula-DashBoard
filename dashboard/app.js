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
  // Les onglets optionnels portent un 3e element = overlay requis
  // (STATE.overlaysActive) ; aucun pour l'instant.
];
// Onglets a afficher pour un workspace (les optionnels selon les modules actifs).
function wsTabsFor(wsId) {
  return WS_TABS.filter(t => !t[2] || wsHasOverlay(wsId, t[2]));
}
// Page workspace courante : { wsId, root, tab, keys, panels: {key: {el,
// mounted, isDirty}} }. null hors page workspace.
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
  const tabsDef = wsTabsFor(wsId);
  const tabKeys = tabsDef.map(t => t[0]);
  const current = tabKeys.includes(tab) ? tab : (prev && tabKeys.includes(prev.tab) && prev.tab) || 'memoire';
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
      <div class="ws-tabs" role="tablist" aria-label="Sections du workspace">${tabsDef.map(([k, l]) => wsTabButtonHtml(k, l, k === current, counts[k])).join('')}</div>
      <span class="ws-tab-ind" aria-hidden="true"></span>
      <div class="ws-maint"></div>
    </div>
    ${tabsDef.map(([k]) => wsTabPanelHtml(k)).join('')}
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
    const keys = WS_PAGE.keys;
    let i = keys.indexOf(WS_PAGE.tab);
    i = e.key === 'Home' ? 0 : e.key === 'End' ? keys.length - 1
      : (i + (e.key === 'ArrowRight' ? 1 : -1) + keys.length) % keys.length;
    wsSelectTab(keys[i], true);
    page.querySelector(`#ws-tab-${keys[i]}`).focus();
  });

  const panels = {};
  for (const k of tabKeys) {
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
  WS_PAGE = { wsId, w, root: page, tab: current, keys: tabKeys, panels };
  wsRefreshSiBadge();
  wsSelectTab(current, false);
  if (animate) countUp(page);
  wsUpdateDirtyDots();
  if (current !== 'extensions' && !prev) wsPrefetchExtCounts(wsId);
}

function wsTabButtonHtml(k, l, on, count) {
  return `<button class="ws-tab" type="button" role="tab" id="ws-tab-${k}" aria-controls="ws-panel-${k}" aria-selected="${on}" tabindex="${on ? 0 : -1}" data-tab="${k}">${l}${count != null ? `<span class="ct">${count}</span>` : ''}<span class="dirty" hidden title="Modifications non sauvegardées"></span></button>`;
}
function wsTabPanelHtml(k) {
  return `<section class="ws-tabpanel" id="ws-panel-${k}" role="tabpanel" aria-labelledby="ws-tab-${k}" tabindex="0" data-panel="${k}" hidden></section>`;
}

function wsSetTabCount(wsId, key, n) {
  if (!WS_PAGE || WS_PAGE.wsId !== wsId || !WS_PAGE.root.isConnected) return;
  const tab = WS_PAGE.root.querySelector(`#ws-tab-${key}`);
  if (!tab) return;
  let ct = tab.querySelector('.ct');
  if (!ct) { ct = el('span', 'ct'); tab.insertBefore(ct, tab.querySelector('.dirty')); }
  ct.textContent = String(n);
  requestAnimationFrame(placeWsTabInd);
}

// Ajoute / retire les onglets optionnels apres un changement de modules
// (activation de claude-team depuis l'onglet Configuration) sans re-rendre
// la page : les panneaux montes sont conserves.
function wsSyncOptionalTabs() {
  if (!WS_PAGE || !WS_PAGE.root.isConnected) return;
  const want = wsTabsFor(WS_PAGE.wsId);
  const wantKeys = want.map(t => t[0]);
  if (wantKeys.join() === WS_PAGE.keys.join()) return;
  const bar = WS_PAGE.root.querySelector('.ws-tabs');
  const lastPanel = () => [...WS_PAGE.root.querySelectorAll('.ws-tabpanel')].pop();
  for (const [k, l] of want) {
    if (WS_PAGE.panels[k]) continue;
    bar.insertAdjacentHTML('beforeend', wsTabButtonHtml(k, l, false));
    lastPanel().insertAdjacentHTML('afterend', wsTabPanelHtml(k));
    WS_PAGE.panels[k] = { el: WS_PAGE.root.querySelector(`#ws-panel-${k}`), mounted: false, isDirty: () => false };
  }
  for (const k of Object.keys(WS_PAGE.panels)) {
    if (wantKeys.includes(k)) continue;
    const b = WS_PAGE.root.querySelector(`#ws-tab-${k}`);
    if (b) b.remove();
    WS_PAGE.panels[k].el.remove();
    delete WS_PAGE.panels[k];
    if (WS_PAGE.tab === k) wsSelectTab('config', false);
  }
  WS_PAGE.keys = wantKeys;
  requestAnimationFrame(placeWsTabInd);
}

// Bascule d'onglet depuis le hash (lien, palette, historique) sans re-rendu.
function wsSwitchTabFromHash(hash) {
  const m = hash.match(/^#\/workspace\/([a-zA-Z0-9_-]+)(?:\/([a-z]+))?$/);
  if (!m || !WS_PAGE || WS_PAGE.wsId !== m[1] || !WS_PAGE.root.isConnected) return false;
  wsSelectTab(WS_PAGE.keys.includes(m[2]) ? m[2] : 'memoire', false);
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
  if (!WS_PAGE.keys.includes(key)) key = 'memoire';
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

// Badges de modules de l'en-tete (etat /api/overview) : « Auto-amelioration »
// renvoie vers le module dans l'onglet Configuration, « Equipe d'agents »
// (claude-team) vers l'onglet Amelioration.
function wsRefreshSiBadge() {
  if (!WS_PAGE) return;
  const slot = WS_PAGE.root.querySelector('[data-ws-si]');
  if (!slot) return;
  slot.replaceChildren();
  if (wsHasOverlay(WS_PAGE.wsId)) {
    const b = el('button', 'pill info', `${I.selfImprove}Auto-amélioration`);
    b.type = 'button';
    b.title = "Auto-amélioration de Claude active : voir le module dans l'onglet Configuration";
    b.addEventListener('click', () => {
      wsSelectTab('config', true);
      const mod = WS_PAGE.root.querySelector('#ws-panel-config .mods');
      if (mod) mod.scrollIntoView({ behavior: motionOK() ? 'smooth' : 'auto', block: 'nearest' });
    });
    slot.appendChild(b);
  }
  if (wsHasOverlay(WS_PAGE.wsId, CLAUDE_TEAM_ID)) {
    const b = el('button', 'pill accent', `${I.cpu}Équipe d'agents`);
    b.type = 'button';
    b.title = "Équipe d'agents active : routage, relecture, modèle et effort sur la ligne du module (onglet Configuration)";
    b.addEventListener('click', () => {
      wsSelectTab('config', true);
      const mod = WS_PAGE.root.querySelector('#ws-panel-config .mods');
      if (mod) mod.scrollIntoView({ behavior: motionOK() ? 'smooth' : 'auto', block: 'nearest' });
    });
    slot.appendChild(b);
  }
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
   Tout overlay disponible, rendu depuis son marker (.nebula-overlay.json :
   features, after_apply, requires, generators -- rien de code en dur par
   overlay) : etat actif / inactif, ce que le module installe, Activer
   (modale) ou Re-appliquer (ne copie que les fichiers manquants).
   Idempotent cote backend. Un overlay dont le prerequis (`requires`) est
   inactif ne peut pas etre active : lien vers la modale du prerequis.
   ================================================================ */
// Icone d'une feature de marker (cle de I.*), repli sur une etincelle.
function overlayFeatureIcon(name) {
  return (name && /^[a-zA-Z]+$/.test(name) && I[name]) ? I[name] : I.sparkle;
}
// Liste des features + phrase post-activation (HTML). `text` du marker est
// du HTML de confiance (fichier livre par Nebula) limite a <code> : tout
// autre balisage est echappe.
function overlayFeaturesHtml(ov) {
  const feats = (ov.features || []).filter(f => f && f.title);
  if (!feats.length) return '';
  const safeText = (t) => escapeHtml(String(t || '')).replace(/&lt;(\/?)code&gt;/g, '<$1code>');
  return `<ul class="mod-feat">${feats.map(f => `<li><span class="fi">${overlayFeatureIcon(f.icon)}</span><span><b>${escapeHtml(f.title)}</b>${safeText(f.text)}</span></li>`).join('')}</ul>`
    + (ov.after_apply ? `<div class="mod-foot">${I.sparkle}<span>${escapeHtml(ov.after_apply)}</span></div>` : '');
}
// Tri des modules : sans prerequis d'abord, puis par libelle.
function sortOverlays(list) {
  return list.slice().sort((a, b) => ((a.requires || []).length - (b.requires || []).length)
    || String(a.label || a.id).localeCompare(String(b.label || b.id), 'fr'));
}

// Routage always-on du module claude-team (routing = GET
// /api/workspaces/<id>/overlays -> entree du module : {declared, mode, modes,
// review_gate, review_gate_values}). Pill d'etat visible sur la ligne du
// module ; selecteurs segmentes (aria-pressed, clavier) qui appellent
// POST /api/workspaces/<id>/team/routing et mettent la pill a jour en place.
const TEAM_ROUTING_MODES = [['manuel', 'Manuel', 'Délègue seulement sur /team ou demande explicite'], ['assiste', 'Assisté', 'Le hook suggère un routage, le fil principal le suit sauf raison explicite'], ['auto', 'Auto', 'Le fil principal applique la table de routage sans qu\'on le lui demande']];
const TEAM_REVIEW_GATES = [['always', 'toujours', 'Tout code livré est relu à froid par le reviewer'], ['from_3_files', 'dès 3 fichiers', 'Relecture à partir de 3 fichiers touchés'], ['never', 'jamais', 'Relecture seulement sur demande']];
const TEAM_ROUTING_PILL = { auto: ['accent', 'Routage auto'], assiste: ['info', 'Routage assisté'], manuel: ['mute', 'Routage manuel'] };

function teamRoutingPillHtml(routing) {
  if (!routing.declared) return '<span class="pill warn" data-routing-pill title="Section routing absente de .claude/team.json : activer le routage ci-dessous">Routage non déclaré</span>';
  const [cls, label] = TEAM_ROUTING_PILL[routing.mode] || TEAM_ROUTING_PILL.manuel;
  return `<span class="pill ${cls}" data-routing-pill title="routing.mode = ${escapeHtml(routing.mode)} (.claude/team.json)">${escapeHtml(label)}</span>`;
}

function teamRoutingSegHtml(name, label, options, allowed, current) {
  const opts = options.filter(([v]) => (allowed || []).includes(v));
  if (!opts.length) return '';
  return `<span class="seg" role="group" aria-label="${escapeHtml(label)}" data-seg="${escapeHtml(name)}"><span class="thumb"></span>${opts.map(([v, l, t]) => `<button type="button" data-v="${escapeHtml(v)}" aria-pressed="${v === current}" title="${escapeHtml(t)}">${escapeHtml(l)}</button>`).join('')}</span>`;
}

function teamRoutingBlockHtml(routing) {
  if (!routing.declared) {
    return `<div class="mod-routing" data-routing>
      <div class="mod-routing-row"><span class="mod-routing-l">Routage</span><span class="muted">Module activé avant le routage automatique : la section <code>routing</code> manque dans <code>.claude/team.json</code>.</span><button type="button" class="btn btn-sm" data-routing-enable>${I.zap}Activer le routage</button></div>
    </div>`;
  }
  return `<div class="mod-routing" data-routing>
    <div class="mod-routing-row"><span class="mod-routing-l">Routage</span>${teamRoutingSegHtml('mode', 'Mode de routage', TEAM_ROUTING_MODES, routing.modes, routing.mode)}<span class="muted mod-routing-h" data-routing-help>${escapeHtml((TEAM_ROUTING_MODES.find(([v]) => v === routing.mode) || ['', '', ''])[2])}</span></div>
    <div class="mod-routing-row"><span class="mod-routing-l">Relecture du code</span>${teamRoutingSegHtml('review_gate', 'Relecture du code livré', TEAM_REVIEW_GATES, routing.review_gate_values, routing.review_gate)}<span class="muted mod-routing-h">par <code>reviewer</code> avant de présenter</span></div>
  </div>`;
}

function bindTeamRouting(wsId, row, routing) {
  const post = (payload) => API.post(`/api/workspaces/${wsId}/team/routing`, payload);
  const applyState = (r) => {
    const pill = row.querySelector('[data-routing-pill]');
    if (pill) pill.outerHTML = teamRoutingPillHtml(r);
    const help = row.querySelector('[data-routing-help]');
    if (help) help.textContent = (TEAM_ROUTING_MODES.find(([v]) => v === r.mode) || ['', '', ''])[2];
    if (STATE.teamRouting) STATE.teamRouting[wsId] = r.mode;
  };
  const enable = row.querySelector('[data-routing-enable]');
  if (enable) {
    enable.addEventListener('click', () => withBusy(enable, async () => {
      try {
        const r = await post({ mode: 'auto' });
        toastOk('Routage activé (mode auto) : section routing écrite dans .claude/team.json');
        applyState(r.routing);
        const block = row.querySelector('[data-routing]');
        if (block) { block.outerHTML = teamRoutingBlockHtml(r.routing); bindTeamRouting(wsId, row, r.routing); }
      } catch (e) { toastErr(e.message); }
    }));
    return;
  }
  for (const seg of row.querySelectorAll('[data-routing] .seg')) {
    const key = seg.dataset.seg;
    bindSeg(seg, async (v) => {
      const prev = key === 'mode' ? routing.mode : routing.review_gate;
      seg.querySelectorAll('button').forEach(b => { b.disabled = true; });
      try {
        const r = await post({ [key]: v });
        routing = r.routing;
        applyState(r.routing);
        const label = ((key === 'mode' ? TEAM_ROUTING_MODES : TEAM_REVIEW_GATES).find(([x]) => x === v) || ['', v])[1];
        toastOk(key === 'mode' ? `Routage : ${label}` : `Relecture du code : ${label}`);
      } catch (e) {
        toastErr(e.message);
        // Retour a l'etat serveur (le clic a deja bascule aria-pressed).
        seg.querySelectorAll('button[data-v]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.v === prev)));
        placeSegThumb(seg);
      } finally {
        seg.querySelectorAll('button').forEach(b => { b.disabled = false; });
      }
    });
  }
}

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
  overlays = sortOverlays(overlays);
  // Etat local (badge en-tete + indicateur accueil + onglets optionnels)
  // aligne sur la reponse.
  const act = overlays.filter(o => o.active).map(o => o.id);
  if (act.length) STATE.overlaysActive[wsId] = act; else delete STATE.overlaysActive[wsId];
  if (WS_PAGE && WS_PAGE.wsId === wsId) { wsRefreshSiBadge(); wsSyncOptionalTabs(); }
  const byId = new Map(overlays.map(o => [o.id, o]));

  const box = el('section', 'card mods');
  box.setAttribute('aria-label', 'Modules optionnels');
  for (const ov of overlays) {
    const n = ov.file_count || 0;
    const missing = (ov.requires || []).filter(r => !(byId.get(r) || {}).active);
    const row = el('div', 'mod' + (ov.active ? ' on' : ''));
    row.dataset.mod = ov.id;
    const reqPills = (ov.requires || []).map(r => {
      const req = byId.get(r);
      const ok = req && req.active;
      return `<span class="pill ${ok ? 'mute' : 'warn'}" title="${ok ? 'Prérequis actif' : 'Prérequis inactif'}">requiert ${escapeHtml(req ? req.label : r)}</span>`;
    }).join('');
    // Routage always-on (claude-team actif) : pill d'etat dans l'en-tete de
    // la ligne + selecteurs sur la ligne (jamais enterres dans une modale).
    const routing = ov.active && ov.routing ? ov.routing : null;
    row['innerHTML'] = `
      <span class="mod-ic" aria-hidden="true">${escapeHtml(ov.emoji || '🧩')}</span>
      <div style="min-width:0">
        <div class="mod-h"><h3>${escapeHtml(ov.label || ov.id)}</h3>${ov.active ? '<span class="pill ok"><span class="sdot"></span>Actif</span>' : '<span class="pill mute">Inactif</span>'}${routing ? teamRoutingPillHtml(routing) : ''}${reqPills}</div>
        <p>${escapeHtml(ov.description || '')}</p>
        ${routing ? teamRoutingBlockHtml(routing) : ''}
        ${ov.active && ov.id === CLAUDE_TEAM_ID ? '<div class="mod-routing mod-teamcfg" data-teamcfg></div>' : ''}
        ${ov.active && (ov.features || []).length ? '<button type="button" class="mod-more" aria-expanded="false">Ce que le module installe ' + I.right + '</button>' : ''}
        ${overlayFeaturesHtml(ov)}
        ${missing.length && !ov.active ? `<div class="mod-req">${I.alert}<span>Requiert ${missing.map(r => `<b>${escapeHtml((byId.get(r) || {}).label || r)}</b>`).join(', ')} : <button type="button" class="linklike" data-req="${escapeHtml(missing[0])}">activer d'abord ce module</button>.</span></div>` : ''}
      </div>
      <div class="mod-act"><small>${n} fichier${n > 1 ? 's' : ''}${ov.active ? '' : ', idempotent'}</small></div>`;
    if (routing) bindTeamRouting(wsId, row, routing);
    const tcSlot = row.querySelector('[data-teamcfg]');
    if (tcSlot) mountTeamConfigRow(wsId, tcSlot);  // js/pages/team-config.js
    const actions = row.querySelector('.mod-act');
    const applyBtn = ov.active ? btn('Ré-appliquer', 'btn-sm', I.refresh) : btn('Activer', 'btn-primary', I.plus);
    applyBtn.title = ov.active
      ? ((ov.managed || []).length
        ? "Ré-applique le module : copie les fichiers absents et met à jour les fichiers gérés par le module (ancienne version sauvegardée en .bak) ; ton contenu n'est jamais touché."
        : "Ré-applique le module : ne copie que les fichiers absents, n'écrase rien.")
      : `Copie ${n} fichier(s) dans ce workspace (idempotent, n'écrase rien).`;
    if (!ov.active) applyBtn.setAttribute('aria-label', `Activer ${ov.label || ov.id}`);
    if (missing.length && !ov.active) {
      applyBtn.disabled = true;
      applyBtn.title = `Requiert ${missing.map(r => (byId.get(r) || {}).label || r).join(', ')}`;
      applyBtn.textContent = `Requiert ${(byId.get(missing[0]) || {}).label || missing[0]}`;
    }
    // Le clic ouvre une modale qui collecte les options (mode / langue /
    // auteur / profondeur si l'overlay les exploite, modeles par role si
    // generateur team_agents) AVANT d'appliquer.
    applyBtn.addEventListener('click', () => modalApplyOverlay(wsId, ov, host));
    actions.prepend(applyBtn);
    if (ov.active) {
      // Retrait : aperçu d'abord (rien n'est supprimé, tout est archivé).
      const removeBtn = btn('Retirer', 'btn-sm btn-danger-outline', I.archive);
      removeBtn.title = "Retire le module de ce projet après un aperçu : rien n'est supprimé, tout est mis de côté dans une archive du projet.";
      removeBtn.setAttribute('aria-label', `Retirer ${ov.label || ov.id}`);
      removeBtn.addEventListener('click', () => modalRemoveOverlay(wsId, ov, host, { byId }));
      applyBtn.after(removeBtn);
    }
    const reqLink = row.querySelector('[data-req]');
    if (reqLink) reqLink.addEventListener('click', () => {
      const req = byId.get(reqLink.dataset.req);
      if (req) modalApplyOverlay(wsId, req, host, { then: ov });
    });
    const more = row.querySelector('.mod-more');
    if (more) more.addEventListener('click', () => {
      row.classList.toggle('open');
      more.setAttribute('aria-expanded', String(row.classList.contains('open')));
    });
    box.appendChild(row);
  }
  host.replaceChildren(box);
}

// Modale d'activation d'un overlay. Champs selon le marker : mode projet,
// langue, convention auteur (si equipe), profondeur d'install quand
// l'overlay exploite ces options (bootstrap_options) ; « Modeles par
// role » + « Regenerer » quand il genere des agents (team_agents).
// opts.then : overlay a proposer juste apres (activation d'un prerequis
// depuis la modale d'un module dependant) ; opts.onDone : rappel apres
// application reussie (page Templates).
// Alias de modèle et niveaux d'effort proposés à l'activation (valeurs =
// dashcore/config.py TEAM_MODEL_ALIASES / TEAM_EFFORT_LEVELS ; GET /team les
// renvoie dans `model_aliases` / `effort_levels`, qui priment s'ils sont là).
const TEAM_MODEL_CHOICES = [['sonnet', 'sonnet (rapide)'], ['opus', 'opus (profond)'], ['haiku', 'haiku (léger)'], ['fable', 'fable'], ['inherit', 'inherit : modèle de la session']];
const TEAM_EFFORT_CHOICES = [['', 'effort : défaut de la session'], ['low', 'effort faible'], ['medium', 'effort moyen'], ['high', 'effort élevé'], ['xhigh', 'effort très élevé'], ['max', 'effort max']];

// Avertissements de consommation selon l'abonnement (GET
// /api/claude/subscription : `rules` recalculées en direct à chaque changement
// de sélecteur). Effort vide = medium ; `auto` toujours faux dans la modale.
const TEAM_EFFORT_ORDER = ['low', 'medium', 'high', 'xhigh', 'max'];
function teamSubWarnings(sub, picks) {
  if (!sub || !Array.isArray(sub.rules)) return [];
  const rank = e => Math.max(0, TEAM_EFFORT_ORDER.indexOf(e || 'medium'));
  const out = [];
  for (const r of sub.rules) {
    const w = r.when || {};
    if (w.plan && w.plan !== sub.plan) continue;
    if (w.auto) continue;
    if (w.conflict && !sub.conflict) continue;
    if (w.model === undefined && w.effort_min === undefined) {
      out.push({ code: r.code, level: r.level, message: r.message, agents: [] });
      continue;
    }
    const hit = picks.filter(p => (w.model === undefined || String(p.model || '').toLowerCase().includes(String(w.model).toLowerCase()))
      && (w.effort_min === undefined || rank(p.effort) >= rank(w.effort_min))).map(p => p.id);
    if (hit.length) out.push({ code: r.code, level: r.level, message: r.message, agents: hit });
  }
  return out;
}

function teamSubWarnHtml(list) {
  return list.map(w => `<div class="callout ${w.level === 'alert' ? 'callout-warn' : 'callout-info'}" style="margin-top:var(--sp-2)"><div>${escapeHtml(w.message)}${w.agents.length ? ` (${w.agents.map(a => escapeHtml(a)).join(', ')})` : ''}</div></div>`).join('');
}

function modalApplyOverlay(wsId, ov, host, opts = {}) {
  const hasTeam = (ov.generators || []).includes('team_agents');
  // Module équipe déjà actif : modèles et efforts pré-remplis depuis le
  // .claude/team.json du workspace (GET /team), pas depuis le modèle livré,
  // sinon « Ré-appliquer » remettrait les modèles du template.
  if (hasTeam && ov.active && !opts._team) {
    API.get(`/api/workspaces/${wsId}/team`).catch(() => null)
      .then(t => modalApplyOverlay(wsId, ov, host, { ...opts, _team: t || {} }));
    return;
  }
  const body = el('div');
  const hasBoot = ov.bootstrap_options !== false;
  const wsTeam = opts._team || {};
  const wsAgents = new Map(((wsTeam.active && wsTeam.agents) || []).map(a => [a.id, a]));
  const agents = hasTeam ? (ov.agents || []).map(a => {
    const w = wsAgents.get(a.id);
    return w ? { ...a, model: w.model || a.model, effort: w.effort || null } : a;
  }) : [];
  const aliases = Array.isArray(wsTeam.model_aliases) && wsTeam.model_aliases.length ? wsTeam.model_aliases : TEAM_MODEL_CHOICES.map(m => m[0]);
  const MODELS = aliases.map(v => TEAM_MODEL_CHOICES.find(m => m[0] === v) || [v, v]);
  const levels = Array.isArray(wsTeam.effort_levels) && wsTeam.effort_levels.length ? wsTeam.effort_levels : TEAM_EFFORT_CHOICES.slice(1).map(e => e[0]);
  const EFFORTS = [TEAM_EFFORT_CHOICES[0], ...levels.map(v => TEAM_EFFORT_CHOICES.find(e => e[0] === v) || [v, v])];
  const optList = (list, cur) => list.map(([v, l]) => `<option value="${escapeHtml(v)}"${v === (cur || '') ? ' selected' : ''}>${escapeHtml(l)}</option>`).join('');
  // Itération /improve en attente de verdict (GET /team) : modèles et
  // efforts verrouillés comme dans la ligne « Modèle et effort » du module, et
  // jamais envoyés (le candidat serait mesuré sur une autre configuration).
  const pend = hasTeam && ov.active ? (wsTeam.pending || null) : null;
  body.innerHTML = `
    <div class="muted" style="font-size:12px;margin-bottom:10px">
      ${escapeHtml(ov.emoji || '🧩')} <strong>${escapeHtml(ov.label || ov.id)}</strong> :
      ${escapeHtml(ov.description || '')}
    </div>
    ${opts.then ? `<div class="callout callout-info" style="margin-bottom:var(--sp-3)"><div>Prérequis de <strong>${escapeHtml(opts.then.label || opts.then.id)}</strong> : après activation, la modale de ce module s'ouvrira.</div></div>` : ''}
    ${ov.active && (ov.managed || []).length ? `<div class="callout callout-info" style="margin-bottom:var(--sp-3)"><div>Ré-appliquer <strong>met à jour</strong> les fichiers gérés par le module (${(ov.managed || []).map(g => `<code>${escapeHtml(g)}</code>`).join(', ')})${ov.refresh_claude_md ? ' et son bloc du <code>CLAUDE.md</code>' : ''} ; l'ancienne version est sauvegardée en <code>.bak</code>. Tout le reste (registres, mémoire, manifeste${ov.refresh_claude_md ? ', texte hors du bloc' : ', bloc du <code>CLAUDE.md</code> complété pour ton projet'}) n'est jamais touché.</div></div>` : ''}
    ${hasBoot ? `
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
    </div>` : ''}
    ${hasTeam ? `
    <div class="field">
      <label class="field-label">Préfixe des agents</label>
      <input class="input mono" name="prefix" maxlength="40" pattern="[a-zA-Z0-9_-]{1,40}" value="${escapeHtml(ov.prefix || wsId)}" placeholder="${escapeHtml(wsId)}">
      <div class="muted" style="font-size:11px;margin-top:4px">
        ex. <code>dash</code> pour obtenir <code>dash-orchestrator</code> à côté de <code>dash-expert</code>. Lettres, chiffres, <code>-</code> et <code>_</code> (40 max) ; mémorisé dans <code>.claude/team.json</code> (<code>team.prefix</code>).
      </div>
    </div>` : ''}
    ${agents.length ? `
    <div class="field">
      <label class="field-label">Modèle et effort par rôle</label>
      <div class="muted" style="font-size:11px;margin-bottom:6px">Pré-rempli depuis ${ov.active ? 'le <code>.claude/team.json</code> du projet' : 'le manifeste'}. Effort vide = réglage par défaut de la session. Un agent déjà généré n'est pas réécrit sans « Régénérer » (sauf si son effort change).</div>
      ${pend ? `<p class="impr-team-msg warn" style="margin:0 0 8px">${I.alert}<span>Itération ${escapeHtml(String(pend.iteration))} de <code class="mono">/improve</code> en attente de verdict : trancher d'abord (nouvelle session puis <code class="mono">/improve</code>), sinon le candidat serait mesuré sur une autre configuration.</span></p>` : ''}
      <div class="team-models with-effort">${agents.map(a => `
        <div class="team-model-row"><span><b>${escapeHtml(a.id)}</b>${a.role ? `<small>${escapeHtml(a.role)}</small>` : ''}</span>
          <select class="select" name="model-${escapeHtml(a.id)}" data-agent="${escapeHtml(a.id)}" aria-label="Modèle de ${escapeHtml(a.id)}"${pend ? ' disabled' : ''}>${optList(MODELS, a.model)}</select>
          <select class="select" name="effort-${escapeHtml(a.id)}" data-effort="${escapeHtml(a.id)}" data-initial="${escapeHtml(a.effort || '')}" aria-label="Effort de ${escapeHtml(a.id)}"${pend ? ' disabled' : ''}>${optList(EFFORTS, a.effort)}</select>
        </div>`).join('')}</div>
      <div data-sub-warn aria-live="polite"></div>
    </div>
    ${ov.active ? `<label class="xswitch" style="padding:0"><input type="checkbox" name="regenerate"> Régénérer les agents générés par Nebula (ceux qui portent encore le marqueur généré)</label>` : ''}` : ''}
  `;
  const modeSel = body.querySelector('[name=mode]');
  const depthSel = body.querySelector('[name=depth]');
  const authorField = body.querySelector('[data-author-field]');
  if (modeSel) {
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
  }

  // Avertissements d'abonnement en direct ; route en échec = rien d'affiché.
  const warnBox = body.querySelector('[data-sub-warn]');
  if (warnBox) {
    let sub = null;
    const refreshWarn = () => {
      const mSel = new Map([...body.querySelectorAll('select[data-agent]')].map(x => [x.dataset.agent, x]));
      const eSel = new Map([...body.querySelectorAll('select[data-effort]')].map(x => [x.dataset.effort, x]));
      const picks = agents.map(a => {
        const m = mSel.get(a.id);
        const e = eSel.get(a.id);
        return { id: a.id, model: m ? m.value : a.model, effort: e ? e.value || null : null };
      });
      warnBox.innerHTML = teamSubWarnHtml(teamSubWarnings(sub, picks));
    };
    body.addEventListener('change', ev => { if (ev.target.matches && ev.target.matches('select[data-agent], select[data-effort]')) refreshWarn(); });
    API.get(`/api/claude/subscription?ws=${encodeURIComponent(wsId)}`).then(r => { sub = r; refreshWarn(); }).catch(() => {});
  }

  const cancel = btn('Annuler', 'btn-ghost');
  const apply = btn(ov.active ? 'Ré-appliquer' : 'Activer', 'btn-primary', ov.active ? I.refresh : I.plus);
  const { close } = openModal({ title: `Module : ${ov.label || ov.id}`, body, footer: [cancel, apply] });
  cancel.addEventListener('click', close);
  apply.addEventListener('click', () => withBusy(apply, async () => {
    const payload = {};
    if (modeSel) {
      payload.mode = modeSel.value;
      payload.language = body.querySelector('[name=language]').value;
      payload.depth = depthSel.value;
      payload.author = body.querySelector('[name=author]').value.trim();
    }
    if (agents.length) {
      // Itération en attente : aucun modèle envoyé (le serveur refuserait).
      if (!pend) {
        payload.models = {};
        for (const sel of body.querySelectorAll('select[data-agent]')) payload.models[sel.dataset.agent] = sel.value;
      }
      const regen = body.querySelector('[name=regenerate]');
      payload.regenerate = !!(regen && regen.checked);
    }
    const prefixInput = body.querySelector('[name=prefix]');
    if (prefixInput) {
      // Meme regle que safe_id cote serveur ; vide = id du workspace.
      const prefix = prefixInput.value.trim();
      if (prefix && !/^[a-zA-Z0-9_-]{1,40}$/.test(prefix)) {
        prefixInput.focus();
        toastErr('Préfixe invalide : lettres, chiffres, « - » et « _ » seulement (40 caractères max).');
        return;
      }
      if (prefix) payload.prefix = prefix;
    }
    // Efforts modifiés (l'activation ne les porte pas) : écrits juste après
    // par POST /team/agents-config, qui régénère les agents générés.
    const efforts = {};
    for (const sel of pend ? [] : body.querySelectorAll('select[data-effort]')) {
      if (sel.value !== sel.dataset.initial) efforts[sel.dataset.effort] = { effort: sel.value || null };
    }
    try {
      const r = await API.post(`/api/workspaces/${wsId}/overlays/${ov.id}`, payload);
      if (Object.keys(efforts).length) {
        try {
          const rc = await API.post(`/api/workspaces/${wsId}/team/agents-config`, { agents: efforts });
          const ne = Object.keys(efforts).length;
          if (rc.written) toast(`Effort enregistré pour ${ne} agent${ne > 1 ? 's' : ''}${(rc.generated || []).length ? ` (${rc.generated.length} régénéré${rc.generated.length > 1 ? 's' : ''})` : ''}${rc.baseline_stale ? ' ; la mesure de référence ne correspond plus : relance /eval dans une nouvelle session' : ''}.`, 'success', 7000);
        } catch (e) { toastErr(`Module appliqué, mais effort non enregistré : ${e.message}`); }
      }
      const nc = (r.copied || []).length;
      const na = (r.appended || []).length;
      const nseed = (r.seeded || []).length;
      const ng = (r.generated || []).length;
      const np = (r.settings_patched || []).length;
      const ns = (r.skipped || []).length;
      const nu = (r.updated || []).length;
      const nb = (r.backups || []).length;
      const parts = [];
      if (nc) parts.push(`${nc} ajouté(s)`);
      if (na) parts.push(`${na} fragment(s) CLAUDE.md`);
      if (nseed) parts.push(`${nseed} exemple(s)`);
      if (ng) parts.push(`${ng} agent(s) généré(s)${r.prefix ? ` (${r.prefix}-*)` : ''}`);
      if (np) parts.push('settings.json complété');
      if (ns) parts.push(`${ns} ignoré(s)`);
      if (nu) {
        // Fichiers gérés remplacés : Claude Code ne les recharge qu'au
        // démarrage d'une session (agents, hooks, CLAUDE.md).
        const head = `Module mis à jour : ${nu} fichier${nu > 1 ? 's' : ''}${nb ? ` (${nb} sauvegardé${nb > 1 ? 's' : ''} en .bak)` : ''}`;
        toast(`${head}${parts.length ? ' · ' + parts.join(', ') : ''}. Relance Claude Code pour charger les changements.`, 'success', 8000);
      } else if (!nc && !na && !nseed && !ng && !np) {
        toastOk(`Module déjà à jour (${ns} fichier(s) déjà présent(s))`);
      } else {
        toastOk(`Module appliqué · ${parts.join(', ')}`);
      }
      close();
      if (opts.onDone) opts.onDone(r);
      if (host) renderWsOverlays(wsId, host);  // refresh badges + etat (en-tete, accueil, onglets)
      // Prerequis active depuis la modale d'un module dependant : enchainer.
      if (opts.then) modalApplyOverlay(wsId, { ...opts.then, active: false }, host, { onDone: opts.onDone });
      // Le module a pu creer / completer CLAUDE.md : l'onglet Memoire est
      // remonte s'il n'est pas en cours d'edition, sinon on previent (un
      // enregistrement ecraserait le fragment ajoute).
      // `updated` porte « CLAUDE.md (bloc <module>) » quand le bloc est remplacé.
      const touchedMd = [...(r.copied || []), ...(r.appended || []), ...(r.updated || [])].some(f => /(^|[\\/])CLAUDE\.md(\s|$)/i.test(String(f)));
      if (touchedMd && WS_PAGE && WS_PAGE.wsId === wsId) {
        const mem = WS_PAGE.panels.memoire;
        if (mem && mem.mounted && mem.isDirty()) toast("CLAUDE.md a été complété par le module : enregistre ou annule tes modifications de l'onglet Mémoire, puis recharge la page pour voir l'ajout.", 'info', 9000);
        else wsRefreshPanels(['memoire']);
      }
    } catch (e) { toastErr(e.message); }
  }));
}

/* ---- Retrait d'un module -------------------------------------------
   POST /api/workspaces/<id>/overlays/<ov>/remove en deux temps : aperçu
   (dry_run, aucune écriture, rend plan_id) puis exécution avec ce plan_id.
   Rien n'est supprimé : tout part dans .claude/.nebula-removed/<module>-<date>/
   (+ removal.json). 409 gérés dans la modale : dependents (bouton qui
   enchaîne sur le module dépendant), active_session (option « Forcer »),
   plan_id périmé (aperçu frais renvoyé, réaffiché), settings.json corrompu.
   Cf. dashcore/api_overlays.py remove_overlay. */
// [raison renvoyée par le serveur, titre du groupe, précision]
const OV_REMOVAL_GROUPS = [
  ['identique au rendu', 'Fichiers du module, jamais modifiés', ''],
  ['modifié', 'Fichiers du module que tu as modifiés', 'ta version est gardée telle quelle dans l\'archive'],
  ['contenu vivant', 'Ton contenu : mémoire, registres, journal, évals', 'coche la case plus bas pour le laisser en place'],
  ['agent généré', 'Agents générés par Nebula', ''],
  ['signature du module', 'Marqueur d\'activation du module', 'sans lui, le module apparaît comme inactif'],
];

// Raison « laissé en place » du serveur -> phrase lisible.
function ovKeepReasonText(reason) {
  const r = String(reason || '');
  if (r.startsWith('contenu vivant conservé')) return 'ton contenu, gardé à ta demande';
  if (r.startsWith('agent édité à la main')) return 'agent modifié à la main : Nebula n\'y touche pas';
  if (r === 'modifié : conservé') return 'modifié par toi : conservé';
  if (r.startsWith('lien ou jonction')) return 'raccourci (lien) vers un autre dossier : laissé tel quel';
  return r;
}

function ovPathListHtml(items, fmt) {
  return `<ul class="rm-list">${items.map(x => `<li>${fmt(x)}</li>`).join('')}</ul>`;
}

// Mise à jour de l'interface après un retrait (même partiel) : état local
// des modules, badges de l'en-tête, onglets optionnels (l'onglet
// Amélioration disparaît sans rechargement), routage de l'accueil, puis
// onglets Mémoire / Configuration / Extensions remontés s'ils ne sont pas en
// cours d'édition (CLAUDE.md, settings.json et agents ont changé).
async function afterOverlayRemoval(wsId, ovId, host, { removed = true } = {}) {
  // Retrait partiel : le module peut rester actif (signature laissée), seul
  // le serveur tranche (renderWsOverlays), pas de mise à jour anticipée.
  if (removed) {
    const act = (STATE.overlaysActive[wsId] || []).filter(x => x !== ovId);
    if (act.length) STATE.overlaysActive[wsId] = act; else delete STATE.overlaysActive[wsId];
    if (ovId === CLAUDE_TEAM_ID && STATE.teamRouting) delete STATE.teamRouting[wsId];
  }
  const onPage = WS_PAGE && WS_PAGE.wsId === wsId && WS_PAGE.root.isConnected;
  if (onPage) { wsRefreshSiBadge(); wsSyncOptionalTabs(); }
  // L'onglet Configuration courant et non modifié est remonté en entier
  // (modules compris) ; sinon on ne rafraîchit que la liste des modules,
  // qui recale aussi l'état sur la réponse du serveur.
  const cfg = onPage ? WS_PAGE.panels.config : null;
  const remountCfg = cfg && cfg.mounted && !cfg.isDirty() && WS_PAGE.tab === 'config';
  // `host` a pu être remplacé par un remontage (retraits enchaînés) : on
  // reprend alors le conteneur des modules de la page courante.
  const mods = onPage ? WS_PAGE.root.querySelector('#ws-panel-config .mods') : null;
  const liveHost = host && host.isConnected ? host : (mods ? mods.parentElement : null);
  if (!remountCfg && liveHost) await renderWsOverlays(wsId, liveHost);
  if (onPage) wsRefreshPanels(['memoire', 'config', 'extensions']);
}

// opts.byId : Map des modules du workspace (libellés) ; opts.then : module à
// proposer de retirer juste après (retrait demandé d'un prérequis).
function modalRemoveOverlay(wsId, ov, host, opts = {}) {
  const label = ov.label || ov.id;
  const url = `/api/workspaces/${wsId}/overlays/${ov.id}/remove`;
  const st = { keepLiving: false, force: false, plan: null };
  const body = el('div', 'rm-ov');
  const cancel = btn('Annuler', 'btn-ghost');
  const go = btn('Retirer le module', 'btn-danger', I.archive);
  go.disabled = true;
  const { close } = openModal({ title: `Retirer le module : ${label}`, body, footer: [cancel, go], wide: true });
  cancel.addEventListener('click', close);

  const loading = (txt) => {
    go.disabled = true;
    body['innerHTML'] = `<div class="page-loader"><div class="spinner"></div><span>${escapeHtml(txt)}</span></div>`;
  };

  const preview = async (notice) => {
    loading('Préparation de l\'aperçu…');
    let res;
    try {
      res = await API.postStatus(url, { dry_run: true, keep_living: st.keepLiving, force: st.force });
    } catch (e) { renderError(e.message); return; }
    handle(res, notice);
  };

  const handle = (res, notice) => {
    const d = res.data || {};
    if (res.ok) { if (d.dry_run) renderPreview(d, notice); else renderDone(d); return; }
    if (res.status === 409 && Array.isArray(d.dependents) && d.dependents.length) { renderDependents(d); return; }
    if (res.status === 409 && d.active_session) { renderSession(); return; }
    if (res.status === 409 && d.plan_id) { renderPreview(d, 'stale'); return; }
    if (res.status === 409) { renderError(d.error, { settings: true, file: d.file }); return; }
    renderError(d.error, d.dry_run === false ? d : null);
  };

  const renderPreview = (d, notice) => {
    st.plan = d;
    const s = d.settings || {};
    const c = d.claude_md || {};
    // settings.json et CLAUDE.md archivés entiers sont déplacés aussi : ils
    // comptent dans l'archive affichée (le serveur les traite à part).
    const archive = [...(d.archive || [])];
    if (s.archived) archive.push({ path: '.claude/settings.json', reason: 'identique au rendu' });
    if (c.block_removed && c.whole_file) archive.push({ path: 'CLAUDE.md', reason: 'identique au rendu' });
    const keep = d.keep || [];
    const notFound = d.not_found || [];
    const known = OV_REMOVAL_GROUPS.map(g => g[0]);
    const groups = OV_REMOVAL_GROUPS.map(([r, t, h]) => [t, h, archive.filter(a => a.reason === r)]);
    const other = archive.filter(a => !known.includes(a.reason));
    if (other.length) groups.push(['Autres fichiers du module', '', other]);
    const openAll = archive.length <= 12;
    const hasLiving = archive.some(a => a.reason === 'contenu vivant');
    const code = (p) => `<code>${escapeHtml(p)}</code>`;

    let settingsHtml;
    if (!s.present) settingsHtml = '<p>Pas de <code>settings.json</code> dans ce projet : rien à faire.</p>';
    else if (s.archived) settingsHtml = '<p>Identique à celui livré par le module : il part entier dans l\'archive.</p>';
    else if ((s.entries_removed || []).length || s.statusline_removed) {
      settingsHtml = `<p>Seuls les hooks du module sont retirés (une copie de sauvegarde <code>.bak</code> est faite avant). Tes permissions et tes autres réglages ne bougent pas.</p>
        ${(s.entries_removed || []).length ? ovPathListHtml(s.entries_removed, h => `<b>${escapeHtml(h.event)}</b>${h.matcher ? ` <span class="dim">(${escapeHtml(h.matcher)})</span>` : ''} : ${code(h.command)}`) : ''}
        ${s.statusline_removed ? '<p>La barre d\'état (<code>statusLine</code>) du module est retirée aussi.</p>' : ''}`;
    } else settingsHtml = '<p>Aucun hook du module à retirer : le fichier n\'est pas touché.</p>';
    if (s.note) settingsHtml += `<p class="dim">${escapeHtml(s.note)}</p>`;
    // settings.local.json : jamais archivé, seuls les hooks du module partent.
    const sl = d.settings_local || {};
    const localHtml = ((sl.entries_removed || []).length || sl.statusline_removed)
      ? `<div class="rm-sec"><h4><code>settings.local.json</code></h4><p>Tes réglages locaux référencent aussi des scripts du module : ces hooks sont retirés (sauvegarde <code>settings.local.json.bak</code> avant, rangée dans l'archive du retrait et non à côté du fichier), le reste du fichier ne bouge pas.</p>
        ${(sl.entries_removed || []).length ? ovPathListHtml(sl.entries_removed, h => `<b>${escapeHtml(h.event)}</b>${h.matcher ? ` <span class="dim">(${escapeHtml(h.matcher)})</span>` : ''} : ${code(h.command)}`) : ''}
        ${sl.statusline_removed ? '<p>La barre d\'état (<code>statusLine</code>) du module est retirée aussi.</p>' : ''}
        ${sl.note ? `<p class="dim">${escapeHtml(sl.note)}</p>` : ''}</div>`
      : (sl.note ? `<div class="rm-sec"><h4><code>settings.local.json</code></h4><p class="dim">${escapeHtml(sl.note)}</p></div>` : '');

    let mdHtml;
    if (c.block_removed && c.whole_file) mdHtml = '<p>Le fichier ne contient que le bloc du module : il part entier dans l\'archive.</p>';
    else if (c.block_removed) mdHtml = '<p>Seul le bloc du module est retiré (copié dans l\'archive, plus une sauvegarde <code>.bak</code>). Le reste du fichier ne bouge pas.</p>';
    else mdHtml = `<p>${c.note ? escapeHtml(c.note.charAt(0).toUpperCase() + c.note.slice(1)) : 'Aucun bloc du module dans <code>CLAUDE.md</code>.'}</p>`;

    const nArch = archive.length;
    body['innerHTML'] = `
      ${notice === 'stale' ? `<div class="callout callout-warn"><div>Un fichier a changé depuis l'aperçu : voici l'aperçu à jour. Relis-le avant de confirmer.</div></div>` : ''}
      ${st.force ? `<div class="callout callout-warn"><div>Retrait forcé alors qu'une session Claude tourne : relance-la ensuite, elle garde l'ancien état du module en mémoire.</div></div>` : ''}
      ${d.inactive ? `<div class="callout callout-info"><div>Ce module n'est pas actif ici (son marqueur d'activation est absent) : seules les traces sûres d'un retrait interrompu sont traitées (hooks vers un script du module disparu, bloc du module dans <code>CLAUDE.md</code>, agents générés par Nebula). Les fichiers de même nom sont considérés comme ceux du projet et ne sont pas touchés.</div></div>` : ''}
      ${d.nothing_to_do
        ? `<div class="callout callout-info"><div>Rien à retirer : ce module n'a plus rien dans ce projet.</div></div>`
        : `<p class="rm-intro"><b>Rien n'est supprimé.</b> Chaque fichier est déplacé dans une archive du projet, avec un fichier <code>removal.json</code> qui explique comment tout remettre en place.</p>`}
      <div class="rm-sec">
        <h4>Mis de côté dans l'archive <span class="ct">${nArch}</span></h4>
        ${nArch ? groups.filter(g => g[2].length).map(([t, h, items]) => `
          <details class="rm-grp"${openAll ? ' open' : ''}><summary>${escapeHtml(t)} <span class="ct">${items.length}</span>${h ? `<small>${escapeHtml(h)}</small>` : ''}</summary>
            ${ovPathListHtml(items, a => code(a.path))}</details>`).join('') : '<p class="dim">Aucun fichier.</p>'}
      </div>
      ${keep.length ? `<div class="rm-sec">
        <h4>Laissé en place <span class="ct">${keep.length}</span></h4>
        ${ovPathListHtml(keep, k => `${code(k.path)} <span class="dim">${escapeHtml(ovKeepReasonText(k.reason))}</span>`)}
      </div>` : ''}
      <div class="rm-sec"><h4><code>settings.json</code></h4>${settingsHtml}</div>
      ${localHtml}
      <div class="rm-sec"><h4><code>CLAUDE.md</code></h4>${mdHtml}</div>
      ${notFound.length ? `<details class="rm-grp rm-sec"><summary>Déjà absents du projet <span class="ct">${notFound.length}</span><small>rien à faire pour eux</small></summary>${ovPathListHtml(notFound, code)}</details>` : ''}
      <div class="rm-sec"><h4>Archive</h4><p>${code(`.claude/.nebula-removed/${ov.id}-<date>-<heure>/`)}, dans ce projet.</p></div>
      ${hasLiving || st.keepLiving ? `<label class="xswitch rm-keep"><input type="checkbox" data-keep-living${st.keepLiving ? ' checked' : ''}> Garder ma mémoire et mes registres en place</label>
        <p class="dim rm-keep-h">Ton contenu reste là où il est ; seuls les fichiers techniques du module partent dans l'archive. Exception : le fichier marqueur du module (${ov.signature_file ? code(ov.signature_file) : '<code>improvements.md</code> pour l\'auto-amélioration, <code>team.json</code> pour l\'équipe'}) part quand même dans l'archive, sinon le module resterait actif.</p>` : ''}
      ${d.nothing_to_do ? '' : '<p class="dim rm-foot">Ferme aussi toute session Claude ouverte à la main dans ce dossier (Nebula ne voit que les sessions qu\'il a lancées), puis relance Claude Code dans ce projet après le retrait.</p>'}`;
    const keepBox = body.querySelector('[data-keep-living]');
    if (keepBox) keepBox.addEventListener('change', () => { st.keepLiving = keepBox.checked; preview(); });
    go.disabled = !!d.nothing_to_do;
    go.hidden = false;
  };

  const renderDependents = (d) => {
    st.plan = null;
    go.disabled = true;
    const deps = d.dependents;
    const names = deps.map(x => `<b>${escapeHtml(x.label || x.id)}</b>`).join(', ');
    body['innerHTML'] = `<div class="callout callout-warn"><div>${names} s'appuie sur « ${escapeHtml(label)} » : retire-le d'abord, puis reviens retirer celui-ci. Rien n'a été modifié.</div></div><div class="rm-acts"></div>`;
    const acts = body.querySelector('.rm-acts');
    for (const dep of deps) {
      const b = btn(dep.id === CLAUDE_TEAM_ID ? 'Retirer d\'abord l\'équipe' : `Retirer d'abord « ${dep.label || dep.id} »`, 'btn-primary', I.right);
      b.addEventListener('click', () => {
        close();
        const full = (opts.byId && opts.byId.get(dep.id)) || dep;
        modalRemoveOverlay(wsId, full, host, { byId: opts.byId, then: ov });
      });
      acts.appendChild(b);
    }
  };

  const renderSession = () => {
    st.plan = null;
    go.disabled = true;
    body['innerHTML'] = `<div class="callout callout-warn"><div><b>Ferme d'abord la session Claude de ce projet.</b> Elle garde les hooks et les agents du module chargés, et ses fichiers seraient déplacés pendant qu'elle tourne. Ferme aussi toute session Claude ouverte à la main dans ce dossier : Nebula ne voit que celles qu'il a lancées. Rien n'a été modifié.</div></div><div class="rm-acts"></div>`;
    const acts = body.querySelector('.rm-acts');
    const retry = btn('Réessayer', 'btn-sm', I.refresh);
    retry.addEventListener('click', () => preview());
    const force = btn('Forcer quand même', 'btn-sm btn-danger-outline', I.alert);
    force.title = 'Retirer le module malgré la session ouverte (à relancer ensuite)';
    force.addEventListener('click', () => { st.force = true; preview(); });
    acts.append(retry, force);
  };

  const renderError = (msg, ctx) => {
    st.plan = null;
    go.disabled = true;
    const partial = ctx && ctx.dry_run === false;
    let html;
    if (ctx && ctx.settings) {
      const f = String(ctx.file || '.claude/settings.json').split('/').pop();
      html = `<div class="callout callout-err"><div><b><code>${escapeHtml(f)}</code> de ce projet est illisible</b> (JSON invalide) : corrige-le${f === 'settings.json' ? ' dans l\'onglet Configuration' : ''}, puis réessaie. Rien n'a été modifié.<br><span class="dim">${escapeHtml(msg || '')}</span></div></div>`;
    } else if (partial) {
      const errs = ctx.errors || [];
      html = `<div class="callout callout-err"><div><b>Le retrait s'est arrêté en cours de route.</b> ${escapeHtml(msg || '')}</div></div>
        ${errs.length ? ovPathListHtml(errs, x => `<code>${escapeHtml(x.path)}</code> <span class="dim">${escapeHtml(x.error)}</span>`) : ''}
        ${ctx.archive_dir ? `<p>Ce qui a déjà été déplacé est dans <code>${escapeHtml(ctx.archive_dir)}</code>.</p>` : ''}
        <p>Relance l'aperçu pour terminer le retrait.</p>`;
    } else {
      html = `<div class="callout callout-err"><div>${escapeHtml(msg || 'Erreur inconnue')}</div></div>`;
    }
    body['innerHTML'] = html + '<div class="rm-acts"></div>';
    const again = btn('Relancer l\'aperçu', 'btn-sm', I.refresh);
    again.addEventListener('click', () => preview());
    body.querySelector('.rm-acts').appendChild(again);
    if (partial) {
      toastErr(`Retrait partiel de « ${label} » : ${msg || 'erreur'}`);
      afterOverlayRemoval(wsId, ov.id, host, { removed: false });
    }
  };

  const renderDone = (d) => {
    st.plan = null;
    go.hidden = true;
    cancel.querySelector('span').textContent = 'Fermer';
    if (d.nothing_to_do) {
      body['innerHTML'] = '<div class="callout callout-info"><div>Rien à retirer : ce module n\'a plus rien dans ce projet.</div></div>';
      toast(`« ${label} » : rien à retirer`, 'info');
      afterOverlayRemoval(wsId, ov.id, host);
      return;
    }
    const n = (d.moved || []).length;
    const s = d.settings || {};
    const c = d.claude_md || {};
    body['innerHTML'] = `
      <div class="callout callout-info"><div><b>Module retiré.</b> ${n} fichier${n > 1 ? 's' : ''} mis de côté dans <code>${escapeHtml(d.archive_dir || '')}</code>.</div></div>
      <p><b>Relance Claude Code dans ce projet</b> pour qu'il oublie les hooks et les agents du module.</p>
      ${s.backup ? `<p class="dim">settings.json : sauvegarde <code>${escapeHtml(s.backup)}</code>.</p>` : ''}
      ${(d.settings_local || {}).backup ? `<p class="dim">settings.local.json : sauvegarde <code>${escapeHtml(d.settings_local.backup)}</code>.</p>` : ''}
      ${c.backup ? `<p class="dim">CLAUDE.md : sauvegarde <code>${escapeHtml(c.backup)}</code>.</p>` : ''}
      <p class="dim">Pour revenir en arrière : le fichier <code>removal.json</code> de l'archive explique comment tout remettre en place.</p>
      <div class="rm-acts"></div>`;
    const acts = body.querySelector('.rm-acts');
    const openArch = btn('Ouvrir le dossier des archives', 'btn-sm', I.folder);
    openArch.addEventListener('click', () => withBusy(openArch, async () => {
      try { const r = await API.post('/api/open', { target: `workspace-removed:${wsId}` }); toastOk(r.message || 'Ouvert'); }
      catch (e) { toastErr(e.message); }
    }));
    acts.appendChild(openArch);
    if (opts.then) {
      const next = btn(`Retirer maintenant « ${opts.then.label || opts.then.id} »`, 'btn-sm btn-danger-outline', I.right);
      next.addEventListener('click', () => { close(); modalRemoveOverlay(wsId, opts.then, host, { byId: opts.byId }); });
      acts.appendChild(next);
    }
    toast(`Module « ${label} » retiré : ${n} fichier${n > 1 ? 's' : ''} dans ${d.archive_dir}. Relance Claude Code dans ce projet.`, 'success', 9000);
    afterOverlayRemoval(wsId, ov.id, host);
  };

  go.addEventListener('click', async () => {
    if (!st.plan || go.disabled) return;
    const prevHtml = go['innerHTML'];
    go.disabled = true;
    go.setAttribute('aria-busy', 'true');
    go['innerHTML'] = '<span class="btn-spinner" aria-hidden="true"></span><span>Retrait…</span>';
    let res = null;
    try {
      res = await API.postStatus(url, { plan_id: st.plan.plan_id, keep_living: st.keepLiving, force: st.force });
    } catch (e) {
      toastErr(e.message);
      go.disabled = false;
    } finally {
      go['innerHTML'] = prevHtml;
      go.removeAttribute('aria-busy');
    }
    if (res) handle(res);
  });

  preview();
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
    // Projets dont le dossier n'existe plus : affichés grisés avec leur raison
    // (comme dans la modale d'import), jamais masqués en silence.
    const missingProjects = (scanResult.projects || []).filter(p => !p.already_registered && !p.path_exists);
    const projName = p => (p.path || '').split(/[\\/]/).filter(Boolean).pop() || p.encoded || 'workspace';
    const missingBlock = missingProjects.length ? `
      <div class="firstrun-import-block" style="opacity:0.6;margin-top:var(--sp-3)">
        <h4>${I.box} Introuvables (${missingProjects.length})</h4>
        <ul>${missingProjects.slice(0, 6).map(p => `<li>
          <span class="mono">${escapeHtml(projName(p))}</span>
          <span class="badge badge-err" style="font-size:10.5px">dossier introuvable</span>
          <div class="dim mono" style="font-size:11px;word-break:break-all">${escapeHtml(p.path || '(chemin inconnu)')}</div>
        </li>`).join('')}${missingProjects.length > 6 ? `<li class="dim">…et ${missingProjects.length - 6} autre(s)</li>` : ''}</ul>
        <p class="dim" style="font-size:11.5px;margin:6px 0 0">Ces projets ont un historique Claude Code mais leur dossier n'existe plus à cet emplacement (déplacé, renommé ou supprimé) : ils ne sont pas importés. S'il a été déplacé, adopte-le à son nouvel emplacement (étape suivante).</p>
      </div>` : '';

    if (newMcps.length === 0 && newProjects.length === 0) {
      scanHost.innerHTML = `
        <div class="callout callout-info" style="margin:0">
          <div>
            <strong>Rien à importer.</strong>
            ${scanResult.mcps.length || scanResult.projects.length
              ? (missingProjects.length
                ? ' Le reste de ta config Claude est déjà connu de Nebula ou introuvable sur le disque (détail ci-dessous).'
                : ' Ce qui était dans ta config Claude est déjà connu d\'Nebula.')
              : ' Aucun MCP ni projet trouvé dans <code class="mono">~/.claude/</code> — c\'est un démarrage propre, c\'est parfait.'}
          </div>
        </div>
        ${missingBlock}
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
          const sess = p.sessions_expired
            ? '<span class="badge" style="font-size:10.5px" title="Claude Code a purgé les anciens transcripts (cleanupPeriodDays, 30 jours par défaut) ; le dossier existe toujours.">sessions expirées</span>'
            : `<span class="dim" style="font-size:11px">${p.sessions} session${p.sessions > 1 ? 's' : ''}</span>`;
          return `<li><span class="mono">${escapeHtml(guessId)}</span> ${sess}</li>`;
        }).join('')}${newProjects.length > 6 ? `<li class="dim">…et ${newProjects.length - 6} autre(s)</li>` : ''}</ul></div>` : ''}
      </div>
      ${missingBlock}
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
// Quand vérifier le dépôt distant (git fetch via ?check=1) :
// - à CHAQUE chargement de la page, sauf F5 en rafale (anti-rebond 2 min,
//   partagé entre onglets via localStorage) ;
// - au retour sur l'onglet si la dernière vérification date de plus de 10 min ;
// - toutes les 30 min (setInterval dans init()).
// Le serveur sérialise et dédoublonne les fetch concurrents (_fetch_remote).
const UPDATE_CHECK_KEY = 'nebula-last-update-check';
const UPDATE_DEBOUNCE_MS = 2 * 60 * 1000;
const UPDATE_VISIBLE_STALE_MS = 10 * 60 * 1000;
const UPDATE_PERIOD_MS = 30 * 60 * 1000;
let _updateCheckInflight = null;  // { remote, promise } : une requête à la fois

function lastUpdateCheckAt() {
  try { return parseInt(localStorage.getItem(UPDATE_CHECK_KEY) || '0', 10) || 0; }
  catch { return 0; }
}

async function checkForUpdates({ force = false, minAgeMs = UPDATE_DEBOUNCE_MS } = {}) {
  const wantRemote = force || (Date.now() - lastUpdateCheckAt()) > minAgeMs;
  // Requête déjà en vol : on la partage si elle répond au besoin.
  if (_updateCheckInflight && (_updateCheckInflight.remote || !wantRemote)) {
    return _updateCheckInflight.promise;
  }
  // Horodaté AVANT la requête : un échec compte aussi (pas de martelage du
  // serveur git quand le réseau ou l'authentification est en panne).
  if (wantRemote) { try { localStorage.setItem(UPDATE_CHECK_KEY, String(Date.now())); } catch {} }

  const promise = (async () => {
    let info;
    try { info = await API.get(`/api/system/version?check=${wantRemote ? '1' : '0'}`); }
    catch (e) {
      // Jamais de toast ici (vérification d'arrière-plan) : l'erreur est
      // affichée dans l'écran des mises à jour.
      STATE.updateCheckError = e.message || 'serveur injoignable';
      refreshUpdatePanels();
      return null;
    }
    STATE.updateCheckError = null;
    STATE.systemVersion = info;
    // Source unique de la version : injectée dans la sidebar (cf. brand-version
    // de index.html, initialement "v…" placeholder).
    if (info.version) {
      const tag = document.getElementById('brand-version');
      if (tag) tag.textContent = 'v' + info.version;
    }
    refreshUpdatePanels();
    return info;
  })();
  _updateCheckInflight = { remote: wantRemote, promise };
  try { return await promise; }
  finally { if (_updateCheckInflight && _updateCheckInflight.promise === promise) _updateCheckInflight = null; }
}

// Vérification d'arrière-plan + badge, sans jamais lever.
function runUpdateCheck(minAgeMs, why) {
  return checkForUpdates({ minAgeMs })
    .then(renderUpdateBadge)
    .catch(e => console.warn(`[updates] vérification (${why}) échouée :`, e.message));
}

/* ---------- Écran des mises à jour : briques partagées section / modale ---------- */

// Types de commit (convention `type(scope): message`) -> badge lisible.
const COMMIT_TYPES = {
  feature: ['Nouveauté', 'accent'], feat: ['Nouveauté', 'accent'],
  fix: ['Correctif', 'ok'],
  update: ['Amélioration', 'info'], refactor: ['Amélioration', 'info'],
  perf: ['Amélioration', 'info'], style: ['Amélioration', 'info'], chore: ['Amélioration', 'info'],
  doc: ['Doc', 'mute'], docs: ['Doc', 'mute'],
  push: ['Version', 'mute'],
};

// « feature(ui): nouvel écran » -> { text: 'Nouvel écran', label: 'Nouveauté', tone: 'accent' }.
// Type inconnu : sujet affiché tel quel, sans badge.
function parseCommitSubject(subject) {
  const s = String(subject || '').trim();
  const m = /^([A-Za-z]+)(?:\(([^)]*)\))?!?:\s*(.+)$/.exec(s);
  const t = m && COMMIT_TYPES[m[1].toLowerCase()];
  if (!t) return { text: s, label: '', tone: '' };
  return { text: m[3].charAt(0).toUpperCase() + m[3].slice(1), label: t[0], tone: t[1] };
}

// Le serveur ne renvoie que du http(s) ; double garde avant tout href.
function safeWebUrl(u) {
  return /^https?:\/\/[^\s"'<>]+$/i.test(String(u || '')) ? String(u) : '';
}

function extLink(url, label, icon, cls = 'btn btn-sm btn-ghost') {
  const u = safeWebUrl(url);
  if (!u) return '';
  return `<a class="${cls}" href="${escapeHtml(u)}" target="_blank" rel="noopener noreferrer">${icon || ''}<span>${escapeHtml(label)}</span></a>`;
}

// État résumé : { tone: ok|accent|warn|err|mute, title, sub }.
function updateStatus(info, err) {
  if (!info) return { tone: 'err', title: 'Impossible de vérifier', sub: err || 'Le serveur Nebula ne répond pas.' };
  if (!info.is_git) return { tone: 'mute', title: 'Mises à jour automatiques indisponibles', sub: info.reason || "Cette installation n'est pas un clone git." };
  const n = info.behind || 0;
  const failed = info.check_error ? (info.check_hint || info.check_error) : '';
  if (info.diverged) {
    return { tone: 'warn', title: 'Versions divergentes',
      sub: `${info.ahead} modification(s) locale(s) absentes du dépôt, ${n} nouveauté(s) côté dépôt. Voir les options avancées.` };
  }
  if (n > 0) {
    return { tone: 'accent', title: `${n} mise${n > 1 ? 's' : ''} à jour disponible${n > 1 ? 's' : ''}`,
      sub: failed ? `Impossible de vérifier : ${failed} Liste issue de la dernière vérification réussie.` :'Tes données (workspaces, MCPs, secrets) ne sont pas touchées.' };
  }
  if (failed) return { tone: 'err', title: 'Impossible de vérifier', sub: failed };
  if (!info.upstream) return { tone: 'mute', title: 'Aucune branche distante suivie', sub: info.reason || 'Impossible de comparer avec le dépôt.' };
  return { tone: 'ok', title: 'À jour', sub: 'Tu as la dernière version publiée.' };
}

const UPDATE_TONE_ICON = { ok: 'check', accent: 'download', warn: 'alert', err: 'alert', mute: 'info' };

// En-tête commun : état + version + date de vérification + détail d'erreur.
function updateSummaryHtml(info, err) {
  const st = updateStatus(info, err);
  const checked = info && info.checked_at ? `Vérifié ${fmtAgo(info.checked_at)}`
    : (info && info.check_error ? 'Échec' : (info && info.is_git ? 'Jamais vérifié' : ''));
  const version = info ? `${info.version ? 'v' + escapeHtml(info.version) : ''}${info.head ? ` <code class="mono">${escapeHtml(info.head)}</code>` : ''}` : '';
  const rawErr = info ? info.check_error : err;
  return `
    <div class="upd-head upd-${st.tone}">
      <span class="upd-ic">${I[UPDATE_TONE_ICON[st.tone]] || ''}</span>
      <div class="upd-head-main">
        <div class="upd-title">${escapeHtml(st.title)}</div>
        <div class="upd-sub">${escapeHtml(st.sub)}</div>
        ${rawErr && info ? `<details class="upd-tech"><summary>Détail technique</summary><pre class="mono">${escapeHtml(rawErr)}</pre></details>` : ''}
      </div>
      <dl class="upd-facts">
        ${version ? `<div><dt>Version installée</dt><dd>${version}</dd></div>` : ''}
        ${checked ? `<div><dt>Dernière vérification</dt><dd>${escapeHtml(checked)}</dd></div>` : ''}
      </dl>
    </div>`;
}

// Liste lisible des changements à venir.
function updateCommitsHtml(info) {
  const commits = (info && info.commits) || [];
  if (!commits.length) return '';
  const base = safeWebUrl(info.repo_commit_url);
  const rows = commits.map(c => {
    const p = parseCommitSubject(c.subject);
    const when = c.date ? fmtAgo(c.date) : (c.relative || '');
    const sha = /^[0-9a-f]{7,40}$/i.test(c.sha_full || '') ? c.sha_full : (/^[0-9a-f]{4,40}$/i.test(c.sha || '') ? c.sha : '');
    const link = base && sha ? extLink(base + sha, 'voir le détail', I.ext, 'upd-link') : '';
    return `<li class="upd-item">
        ${p.label ? `<span class="pill ${p.tone}">${escapeHtml(p.label)}</span>` : '<span class="pill mute">Changement</span>'}
        <div class="upd-item-main">
          <div class="upd-item-msg">${escapeHtml(p.text)}</div>
          <div class="upd-item-meta">${escapeHtml(when)}${c.author ? ` · ${escapeHtml(c.author)}` : ''}${link ? ` · ${link}` : ''}</div>
        </div>
      </li>`;
  }).join('');
  const more = (info.behind || 0) - commits.length;
  return `<div class="upd-list-h">Ce qui arrive</div>
    <ol class="upd-list">${rows}</ol>
    ${more > 0 ? `<div class="upd-more dim">…et ${more} changement(s) plus ancien(s)</div>` : ''}`;
}

// Liens vers le projet (masqués si le remote n'est pas une URL web).
function updateRepoLinksHtml(info) {
  if (!info || !safeWebUrl(info.repo_web_url)) return '';
  const host = info.repo_host_label || "l'hébergeur";
  return `<div class="upd-links">
      ${extLink(info.repo_web_url, `Voir le projet sur ${host}`, I.ext)}
      ${extLink(info.repo_web_url, 'Lire le README', I.book)}
      ${extLink(info.repo_issues_url, 'Signaler un problème', I.message)}
    </div>`;
}

// Re-rend toutes les sections « Mises à jour » montées (page Outils).
function refreshUpdatePanels() {
  document.querySelectorAll('[data-update-panel]').forEach(h => renderUpdatesCard(h));
}

// Confirmation + `git reset --hard <upstream>` (pré-stash serveur), puis rechargement.
function confirmResetToUpstream(resetBtn, info) {
  const target = (info && info.upstream) || 'origin/main';
  confirmDialog(
    `Réinitialiser ton installation sur ${target} ? Tes modifications locales du code sont sauvegardées automatiquement (git stash) et restent récupérables ici. Tes données (workspaces, MCPs, secrets) ne sont pas touchées.`,
    () => withBusy(resetBtn, async () => {
      let rr;
      try { rr = await API.post('/api/system/reset', {}); }
      catch (e) { toastErr(e.message); return; }
      if (!rr.ok) { toastErr(rr.error || 'Échec de la réinitialisation'); return; }
      toastOk(rr.message || 'Installation alignée sur la version distante');
      setTimeout(() => location.reload(), 1200);
    }, { keepBusyOnSuccess: true }),
    { danger: true, confirmLabel: 'Réinitialiser' }
  );
}

// Zone repliable « Options avancées » : réinitialisation, sauvegardes (stash),
// divergence. Les encarts stash ne sont chargés qu'à l'ouverture.
function updateAdvancedBox(info, { open = false, onToggle } = {}) {
  const box = el('details', 'upd-adv');
  box.open = open;
  const dirty = (info && info.dirty_files) || [];
  box.innerHTML = `
    <summary>${I.sliders}<span>Options avancées</span><span class="dim">réinitialisation, sauvegardes locales, état git</span></summary>
    <div class="upd-adv-body">
      <dl class="upd-git">
        <div><dt>Branche</dt><dd class="mono">${escapeHtml((info && info.branch) || '?')}</dd></div>
        <div><dt>Suit</dt><dd class="mono">${escapeHtml((info && info.upstream) || 'aucune')}</dd></div>
        <div><dt>En avance / en retard</dt><dd class="mono">${(info && info.ahead) || 0} / ${(info && info.behind) || 0}</dd></div>
        ${info && info.head_message ? `<div><dt>Dernier changement installé</dt><dd>${escapeHtml(parseCommitSubject(info.head_message).text)}</dd></div>` : ''}
      </dl>
      ${dirty.length ? `<p class="upd-adv-note">${dirty.length}+ fichier(s) du code modifié(s) localement : ils sont mis de côté puis réappliqués automatiquement pendant la mise à jour.</p>
        <ul class="help-list">${dirty.slice(0, 6).map(f => `<li class="mono" style="font-size:11px">${escapeHtml(f)}</li>`).join('')}</ul>` : ''}
      <div class="upd-adv-reset">
        <div>
          <div class="upd-adv-t">Réinitialiser à la version distante</div>
          <div class="dim">Si la mise à jour échoue ou si les versions ont divergé : aligne le code sur <code class="mono">${escapeHtml((info && info.upstream) || 'origin/main')}</code>. Modifications locales sauvegardées avant.</div>
        </div>
        <div data-reset-slot></div>
      </div>
      <div data-stash-slot></div>
    </div>`;
  if (info && info.is_git && info.upstream) {
    const resetBtn = btn('Réinitialiser', 'btn-sm btn-danger-outline', I.refresh);
    resetBtn.addEventListener('click', () => confirmResetToUpstream(resetBtn, info));
    box.querySelector('[data-reset-slot]').appendChild(resetBtn);
  } else {
    box.querySelector('.upd-adv-reset').remove();
  }
  let stashMounted = false;
  const mountStashes = () => {
    if (stashMounted || !box.open) return;
    stashMounted = true;
    const slot = box.querySelector('[data-stash-slot]');
    mountStashRecover(slot);
    mountStashManager(slot);
  };
  box.addEventListener('toggle', () => { mountStashes(); if (onToggle) onToggle(box.open); });
  mountStashes();
  return box;
}

// Section « Mises à jour » de la page Outils. Rendue depuis STATE.systemVersion,
// re-rendue après chaque vérification (refreshUpdatePanels).
function renderUpdatesCard(host) {
  if (!host || !host.isConnected) return;
  host.dataset.updatePanel = '1';
  const info = STATE.systemVersion || null;
  const err = STATE.updateCheckError || null;
  host.innerHTML = '';
  const card = el('div', 'card upd-card');
  if (!info && !err) {
    card.innerHTML = `<div class="page-loader"><div class="spinner"></div><span>Vérification des mises à jour…</span></div>`;
    host.appendChild(card);
    return;
  }
  card.innerHTML = updateSummaryHtml(info, err);
  const actions = el('div', 'upd-actions');
  if (info && info.is_git && info.behind > 0 && !info.diverged) {
    const go = btn('Mettre à jour', 'btn-primary', I.download);
    go.addEventListener('click', () => modalSystemUpdate({ autoApply: true }));
    const see = btn('Voir le détail', 'btn-ghost', I.list);
    see.addEventListener('click', () => modalSystemUpdate());
    actions.append(go, see);
  } else if (info && info.diverged) {
    const fix = btn('Résoudre', 'btn-primary', I.alert);
    fix.addEventListener('click', () => modalSystemUpdate());
    actions.appendChild(fix);
  }
  const check = btn('Vérifier maintenant', 'btn', I.refresh);
  check.addEventListener('click', () => withBusy(check, async () => {
    const r = await checkForUpdates({ force: true });
    renderUpdateBadge(r);
  }));
  actions.appendChild(check);
  card.appendChild(actions);

  const list = updateCommitsHtml(info);
  if (list) card.appendChild(el('div', 'upd-body', list));
  const links = updateRepoLinksHtml(info);
  if (links) card.appendChild(el('div', 'upd-foot', links));
  if (info && info.is_git) {
    card.appendChild(updateAdvancedBox(info, { open: !!host._advOpen, onToggle: (o) => { host._advOpen = o; } }));
  }
  host.appendChild(card);
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

async function modalSystemUpdate({ autoApply = false } = {}) {
  const body = el('div', 'upd-modal');
  body.innerHTML = `<div class="page-loader"><div class="spinner"></div><span>Vérification…</span></div>`;
  const closeBtn = btn('Fermer', 'btn-ghost');
  const { close } = openModal({ title: 'Mises à jour Nebula', body, footer: closeBtn, wide: true });
  closeBtn.addEventListener('click', close);

  // Force un fetch frais à l'ouverture
  const info = await checkForUpdates({ force: true });
  renderUpdateBadge(info);
  // Même en-tête que la section de la page Outils (état, version, vérification).
  body.innerHTML = updateSummaryHtml(info, STATE.updateCheckError);
  if (!info) return;

  if (!info.is_git) {
    body.appendChild(el('div', 'callout callout-info', `
      <div>
        Pour activer les mises à jour automatiques, ton installation doit être un clone git du dépôt officiel de Nebula (le dossier importe peu : bureau, disque secondaire, etc.).
      </div>
    `));
    return;
  }

  const links = updateRepoLinksHtml(info);

  // ───── Cas DIVERGENT : pas de pull possible (workflow dev→export typique).
  //       Proposer directement le reset proactif, sans laisser l'utilisateur
  //       cliquer "Appliquer" pour découvrir le 500.
  if (info.diverged) {
    body.appendChild(el('div', 'callout callout-warn', `
      <div>
        <strong>Branches divergées</strong>
        <p style="margin:var(--sp-2) 0 0;font-size:13px">
          Ton dépôt local a <strong>${info.ahead} commit${info.ahead > 1 ? 's' : ''}</strong>
          que le remote n'a pas, ET le remote a <strong>${info.behind} commit${info.behind > 1 ? 's' : ''}</strong>
          que ton local n'a pas. <code class="mono">git pull --ff-only</code> est impossible dans ce cas.
        </p>
        <p style="margin:var(--sp-2) 0 0;font-size:13px">
          <strong>Cas le plus courant</strong> : workflow dev→export où tes commits locaux
          granulaires ont leurs équivalents bundlés sur le remote (même contenu, hash
          différents). La solution propre est de <strong>réinitialiser ton local sur le remote</strong>
          (tes modifs locales seront stashées par sécurité).
        </p>
      </div>
    `));

    const resetBox = el('div', 'upd-adv-reset upd-reset-strong');
    resetBox.innerHTML = `
      <div>
        <div class="upd-adv-t">Réinitialiser sur ${escapeHtml(info.upstream || 'origin/main')}</div>
        <div class="dim">
          Exécute <code class="mono">git reset --hard ${escapeHtml(info.upstream || 'origin/main')}</code> précédé
          d'une sauvegarde automatique (<code class="mono">git stash</code>) de tes modifs locales du code. Les fichiers
          utilisateurs (registre, workspaces.json, .env.local) sont préservés.
        </div>
      </div>
    `;
    const resetBtn = btn('Réinitialiser sur origin', 'btn-primary', I.refresh);
    resetBtn.addEventListener('click', () => confirmResetToUpstream(resetBtn, info));
    resetBox.appendChild(resetBtn);
    body.appendChild(resetBox);
    body.appendChild(el('div', 'upd-body', updateCommitsHtml(info)));
    if (links) body.appendChild(el('div', 'upd-foot', links));
    // Gestionnaire de sauvegardes : les pre-reset s'accumulent surtout ici.
    mountStashManager(body);
    return;
  }

  // ───── Déjà à jour (ou vérification impossible sans retard connu) ─────
  if (!info.behind) {
    if (links) body.appendChild(el('div', 'upd-foot', links));
    // Filet de sécurité : stash résiduel d'un pull précédent récupérable et
    // sauvegardes visibles, dans les options avancées.
    body.appendChild(updateAdvancedBox(info));
    return;
  }

  // ───── Mises à jour disponibles ─────
  body.appendChild(el('div', 'upd-body', updateCommitsHtml(info)));

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
      updateRow.after(errPanel);
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
        errPanel.after(resetBox);
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
  if (links) body.appendChild(el('div', 'upd-foot', links));
  body.appendChild(updateAdvancedBox(info));
  // Bouton « Mettre à jour » de la page Outils : lance directement l'application.
  if (autoApply) applyBtn.click();
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
    <p class="dim" style="margin:0;font-size:12px">Les éléments déjà enregistrés ou introuvables sont grisés. « Sessions expirées » : Claude Code a purgé les anciens transcripts, mais le dossier du projet existe toujours.</p>
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
      if (p.sessions_expired) tags.push('<span class="badge" title="Claude Code a purgé les anciens transcripts (cleanupPeriodDays, 30 jours par défaut) ; le dossier existe toujours.">sessions expirées</span>');
      else tags.push(`<span class="badge">${p.sessions} session${p.sessions > 1 ? 's' : ''}</span>`);
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
function modalRegisterExisting(opts = {}) {
  const body = el('div');

  // Bascule de mode : un dossier (flux historique) ou plusieurs projets
  // trouvés dans un dossier parent (adoption groupée).
  let mode = opts.mode === 'parent' ? 'parent' : 'single';
  const modeBar = el('div', 'seg-control');
  modeBar.setAttribute('role', 'group');
  modeBar.setAttribute('aria-label', 'Mode d\'adoption');
  modeBar.style.marginBottom = 'var(--sp-3)';
  modeBar.innerHTML = `
    <button type="button" data-mode="single">Un dossier</button>
    <button type="button" data-mode="parent">Plusieurs projets d'un dossier</button>
  `;
  body.appendChild(modeBar);
  const singlePane = el('div', 'adopt-pane adopt-pane-single');
  const parentPane = el('div', 'adopt-pane adopt-pane-parent');
  body.append(singlePane, parentPane);

  // Etape 1 : champ chemin + bouton Inspecter + zone resultats.
  const step1 = el('div', 'adopt-step adopt-step-1');
  step1.innerHTML = `
    <p class="muted" style="margin-top:0">Adopte un dossier existant comme workspace Nebula. Aucun fichier du dossier n'est créé ni modifié.</p>
    <div class="field">
      <label class="field-label" for="adopt-single-path">Chemin absolu du dossier *</label>
      <div class="row" style="gap:var(--sp-2);align-items:center">
        <input class="input mono" id="adopt-single-path" name="path" placeholder="C:\\dev\\mon-projet" autocomplete="off" style="flex:1;min-width:0">
        <button type="button" class="btn" data-browse style="display:none">${I.folder}<span>Parcourir…</span></button>
      </div>
    </div>
    <div class="row" style="gap:var(--sp-2);align-items:center">
      <button type="button" class="btn btn-primary" data-inspect>Inspecter</button>
      <span class="muted" style="font-size:12px">Lecture seule -- aucun fichier modifié.</span>
    </div>
    <div class="adopt-inspect-result" data-inspect-result style="margin-top:var(--sp-3);display:none"></div>
  `;
  singlePane.appendChild(step1);

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
  singlePane.appendChild(step2);

  const cancel = btn('Annuler', 'btn-ghost');
  const adopt = btn('Adopter', 'btn-primary', I.plus);
  adopt.disabled = true;
  // Adoption groupée partiellement réussie : la liste des workspaces est
  // rafraîchie à la fermeture (la modale reste ouverte pour lire les échecs).
  let refreshOnClose = false;
  const { close } = openModal({
    title: 'Adopter un workspace existant', body, footer: [cancel, adopt], wide: true,
    onClose: () => { if (refreshOnClose) { STATE.loading = true; route(); } },
  });
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

  // ── Mode « Plusieurs projets d'un dossier » ──────────────────────────────
  // Inspection lecture seule du dossier parent (POST /api/workspaces/inspect-parent)
  // puis adoption groupée (POST /api/workspaces/adopt-bulk), réponse par item.
  parentPane.innerHTML = `
    <p class="muted" style="margin-top:0">Indique le dossier qui contient tes projets (ex. <code class="mono">C:\\dev</code>) : Nebula liste les sous-dossiers qui ressemblent à des projets (CLAUDE.md, .claude, .git, package.json, pyproject.toml…). Aucun fichier n'est créé ni modifié.</p>
    <div class="field">
      <label class="field-label" for="adopt-parent-path">Dossier parent *</label>
      <div class="row" style="gap:var(--sp-2);align-items:center">
        <input class="input mono" id="adopt-parent-path" name="parent_path" placeholder="C:\\dev" autocomplete="off" style="flex:1;min-width:0">
        <button type="button" class="btn" data-browse style="display:none">${I.folder}<span>Parcourir…</span></button>
      </div>
    </div>
    <div class="row" style="gap:var(--sp-3);align-items:center;flex-wrap:wrap">
      <button type="button" class="btn btn-primary" data-inspect-parent>Chercher les projets</button>
      <label class="row" style="gap:6px;align-items:center;font-size:13px;cursor:pointer">
        <input type="checkbox" name="depth2"> Descendre d'un niveau de plus
      </label>
    </div>
    <div data-parent-result style="margin-top:var(--sp-3)"></div>
  `;
  const parentInput = parentPane.querySelector('[name=parent_path]');
  const parentResult = parentPane.querySelector('[data-parent-result]');
  const inspectParentBtn = parentPane.querySelector('[data-inspect-parent]');
  let parentScan = null;

  const updateAdoptLabel = () => {
    const span = adopt.querySelector('span');
    if (mode !== 'parent') {
      if (span) span.textContent = 'Adopter';
      adopt.disabled = !(lastInspect && lastInspect.exists && !lastInspect.already_adopted);
      return;
    }
    const n = parentResult.querySelectorAll('input[data-cand]:checked:not(:disabled)').length;
    if (span) span.textContent = n ? `Adopter la sélection (${n})` : 'Adopter la sélection';
    adopt.disabled = n === 0;
  };

  const SIGNAL_LABELS = { '.git': 'git', '.claude': '.claude/', 'CLAUDE.md': 'CLAUDE.md', '.mcp.json': '.mcp.json' };
  const renderParentResult = (r) => {
    parentResult.innerHTML = '';
    const cands = r.candidates || [];
    if (!cands.length) {
      const empty = el('div', 'callout callout-info');
      empty.style.margin = '0';
      empty.textContent = 'Aucun sous-dossier ne ressemble à un projet ici.'
        + (r.depth < 2 ? ' Essaie « Descendre d\'un niveau de plus ».' : '');
      parentResult.appendChild(empty);
      updateAdoptLabel();
      return;
    }
    const fresh = cands.filter(c => !c.already_adopted).length;
    const head = el('div', 'row');
    head.style.cssText = 'gap:var(--sp-2);align-items:center;justify-content:space-between;flex-wrap:wrap;margin-bottom:var(--sp-2)';
    const summary = el('div', 'muted');
    summary.style.fontSize = '12.5px';
    summary.textContent = `${cands.length} projet(s) trouvé(s), dont ${fresh} à adopter.`
      + (r.truncated ? ` Liste tronquée à ${r.max} : affine le dossier parent.` : '');
    const tools = el('div', 'row');
    tools.style.gap = 'var(--sp-1)';
    const selAll = btn('Tout cocher', 'btn-sm btn-ghost');
    const selNone = btn('Tout décocher', 'btn-sm btn-ghost');
    selAll.addEventListener('click', () => { parentResult.querySelectorAll('input[data-cand]:not(:disabled)').forEach(cb => cb.checked = true); updateAdoptLabel(); });
    selNone.addEventListener('click', () => { parentResult.querySelectorAll('input[data-cand]:not(:disabled)').forEach(cb => cb.checked = false); updateAdoptLabel(); });
    tools.append(selAll, selNone);
    head.append(summary, tools);
    parentResult.appendChild(head);
    if (r.truncated) {
      const warn = el('div', 'badge badge-warn');
      warn.style.cssText = 'font-size:12px;margin-bottom:var(--sp-2)';
      warn.textContent = `⚠ Plus de ${r.max} projets : seuls les ${r.max} premiers sont listés.`;
      parentResult.appendChild(warn);
    }

    const list = el('div', 'wizard-list');
    for (const c of cands) {
      const item = el('label', 'wizard-item' + (c.already_adopted ? ' is-registered' : ''));
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.dataset.cand = '1';
      cb.checked = !c.already_adopted;
      cb.disabled = !!c.already_adopted;
      cb.addEventListener('change', updateAdoptLabel);
      const main = el('div', 'wizard-item-main');
      const name = el('div', 'wizard-item-name');
      const nm = el('span', 'mono');
      nm.textContent = c.relative || c.name;
      const pth = el('span', 'dim');
      pth.style.cssText = 'font-size:11px;margin-left:6px';
      pth.textContent = c.path;
      name.append(nm, pth);
      const meta = el('div', 'wizard-item-meta');
      const tag = (cls, text) => { const s = el('span', 'badge' + (cls ? ' ' + cls : '')); s.textContent = text; meta.appendChild(s); return s; };
      if (c.already_adopted) tag('badge-warn', `déjà adopté (${c.adopted_id})`);
      else tag('badge-ok', 'nouveau');
      if (c.claude) tag('badge-info', 'Claude');
      for (const s of (c.signals || [])) tag('', SIGNAL_LABELS[s] || s);
      const status = el('span', 'badge badge-err');
      status.dataset.status = '1';
      status.style.display = 'none';
      meta.appendChild(status);
      main.append(name, meta);
      const idInput = document.createElement('input');
      idInput.type = 'text';
      idInput.className = 'input mono wizard-id-input';
      idInput.value = c.suggested_id || '';
      idInput.disabled = !!c.already_adopted;
      idInput.style.cssText = 'max-width:160px;font-size:12px';
      idInput.setAttribute('aria-label', 'ID du workspace pour ' + (c.relative || c.name));
      item.append(cb, main, idInput);
      item._cand = c;
      list.appendChild(item);
    }
    parentResult.appendChild(list);

    if (cands.some(c => !c.already_adopted && (c.signals || []).includes('.mcp.json'))) {
      const row = el('label', 'row');
      row.style.cssText = 'cursor:pointer;font-size:13px;margin-top:var(--sp-2);gap:var(--sp-2);align-items:center';
      row.innerHTML = `<input type="checkbox" name="bulk_import_mcps" checked><span>Importer aussi les MCPs des <code class="mono">.mcp.json</code> trouvés (les MCPs déjà présents dans le registre ne sont pas écrasés).</span>`;
      parentResult.appendChild(row);
    }
    updateAdoptLabel();
  };

  const runParentInspect = () => withBusy(inspectParentBtn, async () => {
    const path = parentInput.value.trim();
    if (!path) { toastErr('Dossier parent requis'); return; }
    const depth = parentPane.querySelector('[name=depth2]').checked ? 2 : 1;
    try {
      parentScan = await API.post('/api/workspaces/inspect-parent', { path, depth });
      renderParentResult(parentScan);
    } catch (e) {
      parentScan = null;
      parentResult.innerHTML = '';
      const errBox = el('div', 'error-box');
      errBox.textContent = e.message;
      parentResult.appendChild(errBox);
      updateAdoptLabel();
    }
  });
  inspectParentBtn.addEventListener('click', () => runParentInspect().catch(() => {}));
  parentInput.addEventListener('keydown', ev => { if (ev.key === 'Enter') { ev.preventDefault(); inspectParentBtn.click(); } });

  const adoptBulk = async () => {
    const items = [];
    const rows = [];
    const importMcps = !!parentResult.querySelector('[name=bulk_import_mcps]:checked');
    for (const item of parentResult.querySelectorAll('.wizard-item')) {
      const cb = item.querySelector('input[data-cand]');
      if (!cb || !cb.checked || cb.disabled) continue;
      const id = (item.querySelector('.wizard-id-input').value || '').trim();
      if (!id) { toastErr('ID requis pour ' + (item._cand.relative || item._cand.name)); return; }
      const c = item._cand;
      items.push({ path: c.path, id, label: id, emoji: '📁', description: '', import_mcps: importMcps && (c.signals || []).includes('.mcp.json') });
      rows.push(item);
    }
    if (!items.length) { toastErr('Aucun projet sélectionné'); return; }
    let r;
    try { r = await API.post('/api/workspaces/adopt-bulk', { items }); }
    catch (e) { toastErr(e.message); return; }
    const results = r.results || [];
    results.forEach((res, i) => {
      const item = rows[i];
      if (!item) return;
      const cb = item.querySelector('input[data-cand]');
      const status = item.querySelector('[data-status]');
      if (res.ok) {
        cb.checked = false; cb.disabled = true;
        item.querySelector('.wizard-id-input').disabled = true;
        item.classList.add('is-registered');
        status.className = 'badge badge-ok';
        status.textContent = 'adopté';
      } else {
        status.className = 'badge badge-err';
        status.textContent = res.error || 'échec';
      }
      status.style.display = '';
    });
    const failed = r.failed || 0;
    refreshOnClose = true;
    if (failed) {
      // Toast d'erreur (pas de succès) : la modale reste ouverte, chaque
      // ligne en échec porte sa raison ; rafraîchissement à la fermeture.
      toastErr(`${r.adopted} projet(s) adopté(s), ${failed} en échec : détail dans la liste`);
    } else {
      toastOk(`${r.adopted} projet(s) adopté(s)`);
      close();
    }
  };

  // ── Bouton « Parcourir… » : sélecteur de dossier natif côté serveur ──────
  // Capacité lue une fois (GET, sans effet de bord) : bouton masqué si le
  // poste n'a pas de sélecteur (501 côté POST, message clair).
  const wireBrowse = (pane, input, onPicked) => {
    const b = pane.querySelector('[data-browse]');
    folderPickerSupported().then(ok => { if (ok) b.style.display = ''; });
    b.addEventListener('click', () => withBusy(b, async () => {
      const r = await API.post('/api/system/pick-folder', { initial: input.value.trim(), title: 'Choisis le dossier à adopter' });
      return r;
    }).then(r => {
      if (r && r.ok && r.path) { input.value = r.path; onPicked(); }
    }).catch(e => {
      // 501 (aucun sélecteur sur ce poste) : on retire le bouton, saisie manuelle.
      if (/indisponible/i.test(e.message)) { _folderPickerSupported = false; b.style.display = 'none'; }
      toastErr(e.message);
    }));
  };
  wireBrowse(step1, step1.querySelector('[name=path]'), () => inspectBtn.click());
  wireBrowse(parentPane, parentInput, () => inspectParentBtn.click());

  const setMode = (m) => {
    mode = m;
    modeBar.querySelectorAll('button').forEach(b => {
      const on = b.dataset.mode === m;
      b.classList.toggle('is-active', on);
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    singlePane.style.display = m === 'single' ? '' : 'none';
    parentPane.style.display = m === 'parent' ? '' : 'none';
    updateAdoptLabel();
  };
  modeBar.querySelectorAll('button').forEach(b => b.addEventListener('click', () => setMode(b.dataset.mode)));
  setMode(mode);

  // Bouton Adopter (etape 2, ou sélection groupée en mode dossier parent).
  adopt.addEventListener('click', () => withBusy(adopt, async () => {
    if (mode === 'parent') { await adoptBulk(); return; }
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
  }).then(() => { if (mode === 'parent') updateAdoptLabel(); }));
}

// Capacité du sélecteur de dossier natif (bouton « Parcourir… »), lue une
// fois par session : GET sans effet de bord, false si la route échoue.
let _folderPickerSupported = null;
async function folderPickerSupported() {
  if (_folderPickerSupported === null) {
    try {
      const r = await API.get('/api/system/pick-folder');
      _folderPickerSupported = !!(r && r.supported);
    } catch { _folderPickerSupported = false; }
  }
  return _folderPickerSupported;
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
  // Tri : modules sans prerequis d'abord (sortOverlays). Cocher un module
  // coche et verrouille ses prerequis ; l'ordre d'application est resolu
  // cote backend (order_by_requires).
  const overlays = sortOverlays(STATE.overlays || []);
  const ovById = new Map(overlays.map(o => [o.id, o]));
  const overlaysSection = overlays.length ? `
    <div class="field">
      <label class="field-label" id="ov-pick-label">Modules optionnels</label>
      <div class="muted" style="font-size:12px;margin-bottom:6px">
        Appliqués par-dessus le template choisi. N'écrasent jamais un fichier déjà présent ; activables aussi plus tard depuis l'onglet Configuration du workspace.
      </div>
      <div class="ov-pick" role="group" aria-labelledby="ov-pick-label" data-overlays-host>
        ${overlays.map(o => {
          const si = o.id === SELF_IMPROVING_ID;
          const reqs = (o.requires || []).map(r => (ovById.get(r) || {}).label || r);
          return `
          <label class="ov-opt${si ? ' featured' : ''}">
            <input type="checkbox" name="overlay" value="${escapeHtml(o.id)}" data-requires="${escapeHtml((o.requires || []).join(' '))}">
            <span class="ov-e" aria-hidden="true">${escapeHtml(o.emoji || '🧩')}</span>
            <span style="min-width:0">
              <b>${escapeHtml(o.label || o.id)}${si ? '<span class="pill accent ov-tag">Recommandé</span>' : ''}${reqs.length ? `<span class="pill mute ov-tag">requiert ${escapeHtml(reqs.join(', '))}</span>` : ''}</b>
              <span class="ov-d" style="display:block">${escapeHtml(o.description || '')}</span>
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
  // Dependances entre modules : cocher un module coche et verrouille ses
  // prerequis ; decocher un prerequis decoche les modules qui le requierent.
  const ovInputs = Array.from(body.querySelectorAll('input[name="overlay"]'));
  const syncOverlayDeps = () => {
    const checked = new Set(ovInputs.filter(i => i.checked).map(i => i.value));
    for (const i of ovInputs) {
      const neededBy = ovInputs.filter(o => o.checked && (o.dataset.requires || '').split(' ').includes(i.value));
      i.disabled = neededBy.length > 0;
      i.closest('.ov-opt').title = neededBy.length ? `Requis par ${neededBy.map(o => (ovById.get(o.value) || {}).label || o.value).join(', ')}` : '';
      if (neededBy.length) i.checked = true;
    }
    for (const i of ovInputs) {
      const reqs = (i.dataset.requires || '').split(' ').filter(Boolean);
      if (i.checked && reqs.some(r => !checked.has(r) && ovById.has(r))) {
        for (const r of reqs) { const ri = ovInputs.find(o => o.value === r); if (ri) { ri.checked = true; ri.disabled = true; } }
      }
    }
  };
  for (const i of ovInputs) i.addEventListener('change', syncOverlayDeps);

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
    { g: 'Actions', t: 'Adopter plusieurs projets d\'un dossier', d: 'Lister les projets d\'un dossier parent et les adopter en une fois', ic: I.folder, hidden: true, run: () => modalRegisterExisting({ mode: 'parent' }) },
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
      body: `<p>Nebula pilote ton écosystème <strong>Claude Code</strong> en local : projets, outils, mais aussi <strong>modules</strong> (auto-amélioration, équipe d'agents) et mises à jour. En 13 étapes (~3 min), je te montre l'essentiel.</p>
        <p class="dim" style="font-size:12px">Tu peux <kbd>Échap</kbd> à tout moment, ou cliquer "Passer". Tu pourras relancer cette visite quand tu veux.</p>`,
      target: null, navigate: '#/',
    },
    {
      title: '📁 Workspaces : tes projets Claude',
      body: `<p>Chaque workspace = un projet Claude Code (un dossier avec son <code class="mono">CLAUDE.md</code>, ses MCPs scopés, ses skills).</p>
        <p>D'ici, tu lances <em>claude</em> directement dans le bon dossier d'un clic.</p>`,
      target: '#ws-host, .empty', navigate: '#/',
    },
    {
      title: '➕ Créer ou retrouver tes projets',
      body: `<p><strong>Nouveau workspace</strong> crée un projet depuis un template. <strong>Adopter</strong> enregistre un dossier qui existe déjà : bouton <em>Parcourir…</em> pour le choisir, ou l'onglet <em>Plusieurs projets d'un dossier</em> pour en adopter plusieurs d'un coup.</p>
        <p>Adopter ne copie rien et ne modifie rien dans ton dossier.</p>`,
      target: '#topbar-actions', navigate: '#/',
    },
    {
      title: '🔌 MCPs : super-pouvoirs de Claude',
      body: `<p>Les <strong>MCPs</strong> (Model Context Protocol) donnent à Claude accès à des outils externes : filesystem, GitHub, n8n, ta base de données…</p>
        <p>Pas besoin d'écrire du JSON : utilise les <strong>recettes</strong> (catalogue 1-clic) ou le formulaire visuel. Nebula sync automatiquement vers les workspaces ciblés.</p>`,
      target: '.page', navigate: '#/mcps',
    },
    {
      title: '🔐 Secrets : <code class="mono">.env.local</code>',
      body: `<p>Tokens, API keys, mots de passe : <strong>jamais en dur</strong> dans tes configs MCP ou templates. Tu les stockes ici une fois et tu les réutilises avec <code class="mono">\${MA_VAR}</code> dans n'importe quel champ MCP.</p>
        <p>Sur Windows, tu peux <strong>chiffrer le fichier en un clic</strong> avec le bouton <em>Activer le chiffrement</em> : illisible si copié ailleurs ou ouvert par un autre compte, transparent à l'usage.</p>`,
      target: '.page', navigate: '#/tools',
    },
    {
      title: '🧠 Skills : bibliothèque centrale',
      body: `<p>Les <strong>skills</strong> sont des compétences réutilisables (prompts longs structurés) que Claude active dynamiquement.</p>
        <p>Le modèle "magasin" : tu maintiens une bibliothèque, et tu <strong>distribues</strong> chaque skill vers Global et/ou des workspaces spécifiques. Une seule édition, plusieurs cibles.</p>`,
      target: '.page', navigate: '#/skills',
    },
    {
      title: '🧩 Modules : des super-pouvoirs à poser sur un projet',
      body: `<p>La page <strong>Templates</strong> contient les moules de workspaces, et surtout la section <strong>Modules</strong> : des ajouts qui se posent <em>par-dessus</em> un projet, sans écraser un seul de ses fichiers.</p>
        <p>Pour en activer un : <em>Activer sur un workspace…</em>. Ensuite, dans le workspace, onglet <strong>Configuration</strong> : <em>Ré-appliquer</em> met le module à jour, <em>Retirer</em> montre d'abord un aperçu et ne supprime rien (tout part dans une archive).</p>`,
      target: '.mods-sec, .page', navigate: '#/templates',
    },
    {
      title: '🔁 Auto-amélioration de Claude',
      body: `<p>Ce module donne une <strong>mémoire</strong> à ton projet : conventions, pièges rencontrés, idées et actions à faire sont notés dans des registres versionnés.</p>
        <p>Résultat : Claude apprend de ton projet au fil des sessions et ne repart plus de zéro. Active-le depuis sa carte.</p>`,
      target: '.module-card[data-overlay="claude-self-improving"], .mods-sec, .page', navigate: '#/templates',
    },
    {
      title: '👥 Équipe d\'agents',
      body: `<p>Ce module ajoute <strong>7 agents</strong> : orchestrateur, chercheur, architecte, exécutant, relecteur, évaluateur et critique. Tape <code class="mono">/team &lt;objectif&gt;</code> dans Claude et le travail est découpé et réparti entre eux.</p>
        <p>Le routage est automatique, et tu peux régler le <strong>modèle</strong> et l'<strong>effort</strong> de chaque agent. Attention au coût : un agent sur <em>opus</em> consomme davantage, surtout avec un abonnement Pro.</p>`,
      target: '.module-card[data-overlay="claude-team"], .mods-sec, .page', navigate: '#/templates',
    },
    {
      title: '🧭 Équipe réglée sur la ligne du module',
      body: `<p>Dans l'onglet <strong>Configuration</strong> du workspace, la ligne du module claude-team porte le <strong>routage</strong> (Manuel, Assisté, Auto), la <strong>relecture du code</strong> (toujours, dès 3 fichiers, jamais) et <strong>Modèle et effort</strong> (bouton « Régler », propositions expliquées).</p>
        <p>L'amélioration se fait au fil des conversations : Claude note les frictions de l'équipe dans <code class="mono">improvements.md</code> et propose le correctif, tu valides.</p>`,
      target: '#h-modules, .page', navigate: '#/aide/modules',
    },
    {
      title: '🔄 Mises à jour de Nebula',
      body: `<p>Dans <strong>Outils</strong>, la section <em>Mises à jour</em> vérifie à chaque ouverture si une nouvelle version existe. Un badge <strong>MAJ</strong> apparaît alors dans l'interface.</p>
        <p>Tu y trouves aussi les liens vers le projet et les notes de version.</p>`,
      targetLabel: 'Mises à jour', target: '.tools-stack, .page', navigate: '#/tools',
    },
    {
      title: '🛡️ Santé + Journal sur la home',
      body: `<p>De retour à l'accueil. La colonne Activité contient :</p>
        <ul style="margin:6px 0;padding-left:18px;font-size:13px">
          <li><strong>Santé</strong> : signale les configs MCP cassées, désynchronisées ou inutilisées.</li>
          <li><strong>Journal</strong> : tes notes rapides projet par projet.</li>
        </ul>`,
      target: '.rail, .page', navigate: '#/',
    },
    {
      title: '🎯 Tu sais l\'essentiel',
      body: `<p>Pour aller plus loin : la page <strong>Aide</strong> détaille tout (modules, raccourcis, dépannage). Tu peux <strong>relancer cette visite</strong> à tout moment depuis Aide → bouton "Visite guidée".</p>
        <p style="margin-top:8px">Bon code !</p>`,
      target: null,
    },
  ],
};

// Cible d'une étape : liste de sélecteurs (repli dans l'ordre) ; `targetLabel` vise d'abord
// le titre de section (.section-label) contenant ce texte, avec repli sur `target`.
function _tourResolveTarget(step) {
  if (step.targetLabel) {
    const lab = [...document.querySelectorAll('.section-label')]
      .find(n => n.textContent.includes(step.targetLabel));
    if (lab) return lab;
  }
  if (!step.target) return null;
  // Priorité à l'ordre de la liste (querySelector prendrait le premier dans le DOM).
  for (const sel of step.target.split(',')) {
    const n = document.querySelector(sel.trim());
    if (n) return n;
  }
  return null;
}

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
  // Page rendue en asynchrone (cartes de modules...) : on laisse jusqu'a 3 s
  // au premier sélecteur de la cible pour apparaitre, sinon repli sur la suite.
  if (step.target) {
    const first = step.target.split(',')[0].trim();
    for (let k = 0; k < 60 && !document.querySelector(first) && STATE.tour && STATE.tour.step === idx; k++) {
      await new Promise(r => setTimeout(r, 50));
    }
  }
  if (!STATE.tour || STATE.tour.step !== idx) return;

  const overlay = _ensureTourOverlay();
  overlay.classList.add('is-active');
  overlay.querySelector('.tour-bubble-step').textContent = `${idx + 1} / ${def.length}`;
  overlay.querySelector('.tour-bubble-title').textContent = step.title;
  overlay.querySelector('.tour-bubble-body').innerHTML = step.body;
  overlay.querySelector('[data-tour-prev]').disabled = idx === 0;
  overlay.querySelector('[data-tour-next]').textContent = idx === def.length - 1 ? 'Terminer ✓' : 'Suivant →';

  const targetEl = _tourResolveTarget(step);
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
  const targetEl = _tourResolveTarget(step);
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

    // Vérification de mise à jour à chaque chargement de la page (non
    // bloquante) ; seul l'anti-rebond UPDATE_DEBOUNCE_MS évite les F5 en rafale.
    setTimeout(() => runUpdateCheck(UPDATE_DEBOUNCE_MS, 'chargement'), 1500);

    // Retour sur l'onglet : nouvelle vérification si la dernière est ancienne.
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') runUpdateCheck(UPDATE_VISIBLE_STALE_MS, 'retour sur l\'onglet');
    });

    // Re-check périodique (toutes les 30 min). Ce poller global n'est PAS
    // géré par clearPagePollers (volontaire).
    setInterval(() => runUpdateCheck(UPDATE_DEBOUNCE_MS, 'périodique'), UPDATE_PERIOD_MS);
  });
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
else init();
