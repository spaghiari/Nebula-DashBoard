/* ================================================================
   Nebula - Page Home (Accueil) -- refonte 2026-10
   ----------------------------------------------------------------
   renderHome : en-tete (phrase de synthese) + KPI + « En cours » (cartes
   running / « Terminal ouvert ») + tableau ou grille des workspaces
   (colonne Etat, tris, bascule memorisee) + colonne Activite (dernieres
   sessions, Sante, Journal).
   buildHomeQuickstart : bandeau d'onboarding affiche tant que la
   checklist 6/6 n'est pas complete.
   liveCard / workspaceRow / workspaceCard : re-rendus cibles par le
   polling des sessions (router.js refreshSessionNodes, [data-ws-card]).
   loadSanity : bloc Sante (sanity-check serveur + controles calcules
   cote client depuis STATE : workspaces inconnus, MCPs inutilises).
   loadJournal : dernieres entrees du journal.

   Dependances : STATE, API, safe, escapeHtml, fmt*, el, btn, I.*, wsGem,
   setBreadcrumbs, setTopbarActions, toastOk, toastErr, confirmDialog, route,
   wsStateMarker, sessionState, sessionSince (router.js).
   Forward-refs (resolus au runtime via global scope) : modalNewWorkspace,
   modalSetupWizard, modalRegisterExisting, resetOnboarded, startFirstRunWizard.

   Ref : CM-2 batch 5, refactor 2026-05-13 ; refonte graphique 2026-10.
   ================================================================ */
'use strict';

// Collecte les workspaces dont le .mcp.json avait été édité à la main
// (drapeau `hand_edited`) ou contient des serveurs hors registre conservés
// (`preserved`), tels que renvoyés par sync_workspace_mcps. `results` = map
// {ws_id: {hand_edited?, preserved?, ...}} renvoyée par /api/sync-all.
// Retourne [{ws, handEdited, preserved: [...]}].
function collectHandEdited(results) {
  return Object.entries(results || {})
    .map(([ws, r]) => syncNotice(ws, r))
    .filter(Boolean);
}

// Normalise la réponse d'une sync unitaire (POST /sync-mcps) ; null si rien
// à signaler.
function syncNotice(ws, r) {
  if (!r) return null;
  const preserved = Array.isArray(r.preserved) ? r.preserved : [];
  if (!r.hand_edited && !preserved.length) return null;
  return { ws, handEdited: !!r.hand_edited, preserved };
}

// Avertit (non bloquant) après une sync. La sync est NON destructive : les
// serveurs ajoutés à la main (hors registre) sont conservés tels quels ; seuls
// les serveurs gérés par Nebula sont régénérés depuis le registre (source de
// vérité). `notices` = sortie de collectHandEdited / [syncNotice(...)].
function warnHandEdited(notices) {
  const list = (notices || []).filter(Boolean);
  if (!list.length) return;
  const parts = list.map(n => {
    const kept = n.preserved.length
      ? `serveurs hors registre conservés : ${n.preserved.join(', ')}`
      : 'aucun serveur hors registre';
    return n.handEdited
      ? `${n.ws} (modifié hors Nebula ; serveurs Nebula régénérés depuis le registre, ${kept})`
      : `${n.ws} (${kept})`;
  });
  const anyEdited = list.some(n => n.handEdited);
  const tail = anyEdited
    ? ' -- pour changer un serveur Nebula, édite le registre, pas le fichier.'
    : '';
  toast(`.mcp.json : ${parts.join(' ; ')}${tail}`, 'info', 10000);
}

// Bandeau "Mise en route" sur Home -- affiche tant que la checklist n'est pas complete.
// Retourne null si tout est OK (6/6 etapes faites) -> la home reste epuree pour les users avances.
function buildHomeQuickstart() {
  // Memes 6 criteres que dans buildOnboardingChecklist (Outils -> A. Demarrage)
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
  if (doneCount >= steps.length) return null;

  const nextStep = steps.find(s => !s.done);
  const card = el('div', 'home-quickstart');
  card['innerHTML'] = `
    <div class="home-quickstart-head">
      <div>
        <div class="home-quickstart-title">🚀 Mise en route : ${doneCount} / ${steps.length}</div>
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

// --- Etat de session (rang de tri) -------------------------------------
const _homeStateRank = (id) => {
  const st = sessionState(id);
  return st === 'running' ? 0 : st === 'idle' ? 1 : 2;
};
const _wsStats = (id) => (STATE.stats || {})[id] || {};
const _wsMcpIds = (id) => ((STATE.wsMcps || {})[id] || { active: [] }).active || [];
const _isWild = (m) => { const w = m.workspaces || []; return w.includes('*') || w.includes('all'); };

// Phrase de synthese de l'en-tete (texte, valeurs echappees).
function homeSentence() {
  const ids = Object.keys(STATE.activeSessions || {}).filter(id => STATE.workspaces.some(w => w.id === id));
  const running = ids.filter(id => sessionState(id) === 'running').length;
  const idle = ids.length - running;
  const nW = STATE.workspaces.length;
  const nM = STATE.mcps.length;
  return `${nW} workspace${nW > 1 ? 's' : ''}, ${nM} MCP${nM > 1 ? 's' : ''}. `
    + (running ? `<b>${running === 1 ? 'Une session tourne' : running + ' sessions tournent'}</b>` : 'Aucune session ne tourne')
    + (idle ? `, ${idle === 1 ? 'un terminal est resté ouvert' : idle + ' terminaux sont restés ouverts'}.` : '.');
}

/* ---- Series temporelles des KPIs (GET /api/stats/history) -------------
   Un point par jour enregistre cote serveur a chaque /api/stats
   (workspace_io.record_stats_history). Serie = historique (hors jour
   courant) + point du jour calcule en direct depuis les stats deja
   chargees. Moins de 2 jours connus : repli sur le texte d'origine, sans
   sparkline. */
function _isoLocalDate(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function kpiSeries(history, key, todayVal) {
  const today = _isoLocalDate(new Date());
  const pts = ((history && history.points) || [])
    .filter(p => p && typeof p.date === 'string' && p.date < today && Number.isFinite(p[key]))
    .map(p => ({ d: p.date, v: p[key] }));
  if (Number.isFinite(todayVal)) pts.push({ d: today, v: todayVal });
  return pts.slice(-31);
}

// Ecart sur ~7 jours (ou depuis le plus ancien point si l'historique est
// plus court) : { delta, days } ou null.
function kpiTrend(series) {
  if (series.length < 2) return null;
  const last = series[series.length - 1];
  const lim = new Date(Date.parse(last.d + 'T00:00:00') - 7 * 86400000);
  const limIso = _isoLocalDate(lim);
  let ref = series[0];
  for (const p of series) { if (p.d <= limIso) ref = p; }
  const days = Math.round((Date.parse(last.d + 'T00:00:00') - Date.parse(ref.d + 'T00:00:00')) / 86400000);
  return days > 0 ? { delta: last.v - ref.v, days } : null;
}

// Sparkline de l'activite quotidienne (increments jour a jour, >= 0).
// Decorative (aria-hidden) : l'information est portee par le texte de tendance.
function kpiSpark(series) {
  if (series.length < 3) return '';
  const inc = [];
  for (let i = 1; i < series.length; i++) inc.push(Math.max(0, series[i].v - series[i - 1].v));
  const max = Math.max(...inc, 1);
  const W = 84, H = 28;
  const pts = inc.map((v, i) => `${(inc.length === 1 ? W : (i / (inc.length - 1)) * W).toFixed(1)},${(H - 2 - (v / max) * (H - 4)).toFixed(1)}`).join(' ');
  return `<svg class="k-spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true" focusable="false"`
    + ` style="flex:0 1 ${W}px;min-width:40px;height:${H}px;margin-left:auto;align-self:flex-end;color:var(--accent);opacity:.7;overflow:visible">`
    + `<polyline points="${pts}" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/></svg>`;
}

function kpiTrendText(tr, unit) {
  const n = Math.max(0, tr.delta);
  return `+${fmtNum(n)} ${unit}${n > 1 ? 's' : ''} sur ${tr.days} j`;
}

async function renderHome() {
  // Bug #14 : capture du jeton de rendu (voir _routeToken, js/router.js).
  // renderHome await des fetchs (stats + sanity) avant d'attacher la page
  // a #content -- si une navigation plus recente arrive entretemps, on
  // doit abandonner au lieu d'ecraser la nouvelle page.
  const myToken = _routeToken;
  setBreadcrumbs([{ label: 'Accueil' }]);
  const newWsBtn = btn('Nouveau workspace', 'btn-primary', I.plus);
  newWsBtn.addEventListener('click', () => modalNewWorkspace());
  const importBtn = btn('Importer', 'btn', I.download);
  importBtn.title = 'Importer MCPs et workspaces depuis ~/.claude/';
  importBtn.addEventListener('click', () => modalSetupWizard());
  const registerBtn = btn('Adopter', 'btn', I.folder);
  registerBtn.title = 'Adopter un dossier Claude Code existant -- inspection puis enregistrement, sans toucher au contenu';
  registerBtn.setAttribute('aria-label', 'Adopter un workspace existant');
  registerBtn.addEventListener('click', () => modalRegisterExisting());
  const syncAllBtn = btn('Sync tous', 'btn', I.refresh);
  syncAllBtn.title = 'Synchronise le registre MCP vers le .mcp.json de chaque workspace';
  syncAllBtn.addEventListener('click', () => withBusy(syncAllBtn, async () => {
    try {
      const r = await API.post('/api/sync-all', {});
      toastOk('Sync terminé pour ' + Object.keys(r.results || {}).length + ' workspace(s)');
      warnHandEdited(collectHandEdited(r.results));
    }
    catch (e) { toastErr(e.message); }
  }));
  setTopbarActions([syncAllBtn, importBtn, registerBtn, newWsBtn]);

  const c = $('#content');
  const page = el('div', 'page');

  const head = el('div', 'page-header rise');
  head['innerHTML'] = `
    <div class="page-header-text">
      <h1 class="page-title">Accueil</h1>
      <p class="page-subtitle" data-home-sentence>${homeSentence()}</p>
    </div>`;
  page.appendChild(head);
  mountHelpLink(page, 'premiers-pas', 'vue d\'ensemble de Nebula');

  const quickstart = buildHomeQuickstart();
  if (quickstart) page.appendChild(quickstart);

  // Stats + sanity en parallèle : la sanity alimente les badges « désync »
  // (lot E item 1a) et le bloc Santé. stats === null = echec de /api/stats
  // (distinct de « 0 session ») : le KPI l'affiche au lieu d'un 0 trompeur.
  // Juste apres un loadAll (cf. js/router.js), les deux sont deja en vol ou
  // charges : on les reprend (usage unique, 10 s max) au lieu de refetcher.
  const pre = STATE.homePrefetch;
  STATE.homePrefetch = null;
  const [statsRaw, sanity, history] = pre && Date.now() - pre.at < 10000
    ? [pre.stats, await pre.sanity, await pre.history]
    : await Promise.all([
      API.get('/api/stats').catch(() => null),
      safe('/api/sanity-check', null),
      safe('/api/stats/history', null),
    ]);
  if (statsRaw) STATE.stats = statsRaw;
  const stats = STATE.stats || {};
  STATE.sanityDesync = new Set(((sanity && sanity.findings) || []).map(f => f.workspace));
  const wsCount = STATE.workspaces.length;
  const pluginCount = STATE.plugins.count || Object.keys(STATE.plugins.enabled || {}).length;
  const totalSessions = Object.values(stats).reduce((s, x) => s + (x.sessions || 0), 0);
  const totalMsgs = Object.values(stats).reduce((s, x) => s + (x.messages || 0), 0);
  const activeWs = STATE.workspaces.filter(w => (_wsStats(w.id).messages || 0) > 0).length;
  const orphans = STATE.mcps.filter(m => !(m.workspaces || []).length);
  const disabled = STATE.mcps.filter(m => m.status === 'désactivé').length;
  const nSkills = (STATE.skills || []).length;

  // Tendances reelles (historique) : sessions et messages. Repli : textes d'origine.
  const sessSeries = statsRaw ? kpiSeries(history, 'sessions', totalSessions) : [];
  const msgSeries = statsRaw ? kpiSeries(history, 'messages', totalMsgs) : [];
  const sessTr = kpiTrend(sessSeries);
  const msgTr = kpiTrend(msgSeries);
  const kpi = (i, icon, n, label, trend, cls, count = true, spark = '', tip = '') => `
    <div class="card kpi rise" style="--i:${i}"${tip ? ` title="${escapeHtml(tip)}"` : ''}><span class="ic">${icon}</span>
      <div style="min-width:0"><div class="k-n"><b class="tab-num" ${count ? `data-count="${n}"` : ''}>${count ? fmtNum(n) : escapeHtml(String(n))}</b><span class="k-l">${escapeHtml(label)}</span></div>
      <span class="k-t ${cls}">${escapeHtml(trend)}</span></div>${spark}</div>`;
  const sessText = `${totalSessions} session${totalSessions > 1 ? 's' : ''} cumulée${totalSessions > 1 ? 's' : ''}`;
  const actText = `${activeWs} workspace${activeWs > 1 ? 's' : ''} actif${activeWs > 1 ? 's' : ''}`;
  const kpis = el('section', 'kpis');
  kpis.setAttribute('aria-label', 'Indicateurs');
  kpis['innerHTML'] =
    kpi(1, I.folder, wsCount, 'workspaces', statsRaw ? (sessTr ? kpiTrendText(sessTr, 'session') : sessText) : 'Statistiques indisponibles', statsRaw ? (sessTr && sessTr.delta > 0 ? 'ok' : '') : 'err',
      true, kpiSpark(sessSeries), sessTr ? sessText : '')
    + kpi(2, I.box, STATE.mcps.length, 'MCPs', orphans.length ? `${orphans.length} sans workspace` : (disabled ? `${disabled} désactivé${disabled > 1 ? 's' : ''}` : 'tous utilisés'), orphans.length ? 'warn' : (disabled ? '' : 'ok'))
    + kpi(3, I.plug, pluginCount, pluginCount > 1 ? 'plugins' : 'plugin', `${nSkills} skill${nSkills > 1 ? 's' : ''} global${nSkills > 1 ? 'aux' : ''}`, '')
    + kpi(4, I.message, statsRaw ? totalMsgs : '-', 'messages', statsRaw ? (msgTr ? kpiTrendText(msgTr, 'message') : actText) : 'Statistiques indisponibles', statsRaw ? (msgTr && msgTr.delta > 0 ? 'ok' : '') : 'err',
      !!statsRaw, kpiSpark(msgSeries), msgTr ? actText : '');
  page.appendChild(kpis);

  // --- Section « En cours » : running (cartes vives) puis idle (Terminal ouvert).
  const liveWs = STATE.workspaces.filter(w => sessionState(w.id))
    .sort((a, b) => (_homeStateRank(a.id) - _homeStateRank(b.id)) || (sessionSince(a.id) > sessionSince(b.id) ? 1 : -1));
  if (liveWs.length) {
    const running = liveWs.filter(w => sessionState(w.id) === 'running').length;
    const idle = liveWs.length - running;
    const lbl = el('h2', 'lbl rise');
    lbl.style.setProperty('--i', 3);
    lbl['innerHTML'] = `En cours <small>${running} en direct${idle ? `, ${idle} terminal${idle > 1 ? 'aux' : ''} ouvert${idle > 1 ? 's' : ''}` : ''}</small>`;
    page.appendChild(lbl);
    const grid = el('section', 'live-grid');
    grid.setAttribute('aria-label', 'Sessions en cours');
    let alt = 0;
    liveWs.forEach((w, i) => {
      const isRun = sessionState(w.id) === 'running';
      const card = liveCard(w, isRun && (alt++ % 2 === 1));
      card.classList.add('rise');
      card.style.setProperty('--i', 4 + i);
      grid.appendChild(card);
    });
    page.appendChild(grid);
  }

  // --- Colonnes : workspaces | activite
  const cols = el('div', 'home-cols');
  if (wsCount === 0) {
    const left = el('section');
    left.appendChild(el('h2', 'lbl', 'Workspaces'));
    const empty = el('div', 'empty');
    empty['innerHTML'] = `
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
    cols.appendChild(left);
  } else {
    cols.appendChild(buildWorkspacesBrowser());
  }
  cols.appendChild(buildHomeRail(sanity));
  page.appendChild(cols);

  // Bug #14 : rendu perime (navigation pendant les awaits stats/sanity
  // ci-dessus) -> on n'attache pas la page, #content appartient deja a
  // la route plus recente. Tout ce qui precede n'a touche que des noeuds
  // detaches, donc abandonner ici est sans effet de bord.
  if (routeIsStale(myToken)) return;
  c.replaceChildren(page);
  countUp(page);
  renderRecentWorkspaces();
}

// ================================================================
// « En cours » : carte d'un workspace avec session active.
// running = carte vive (tokens, chrono « depuis » base sur launched_at,
// Reprendre / Arreter) ; idle = carte neutre « Terminal ouvert » avec
// Fermer le terminal. Metriques REELLES uniquement (stats + wsMcps).
// ================================================================
function liveCard(w, alt) {
  const st = sessionState(w.id) || 'running';
  const s = _wsStats(w.id);
  const nMcp = _wsMcpIds(w.id).length;
  const label = w.label || w.id;
  const card = el('article', st === 'idle' ? 'idle-card' : 'live-card' + (alt ? ' alt' : ''));
  card.dataset.wsCard = w.id; card.dataset.wsKind = 'featured';
  card.tabIndex = 0;
  card.setAttribute('role', 'link');
  card.setAttribute('aria-label', `${label}, ${st === 'idle' ? 'terminal ouvert' : 'session en cours'} : ouvrir le workspace`);
  const badges = stateBadgesHtml(w);
  const plural = (n, a, b) => `${n > 1 ? b : a}`;
  if (st === 'idle') {
    const since = sessionSince(w.id);
    card['innerHTML'] = `
      <div class="t">${wsGem(w)}<div class="nm">${escapeHtml(label)}<small>${escapeHtml(w.id)}</small></div>
        <span class="pill warn"><span class="sdot"></span>Terminal ouvert</span></div>
      <p>Claude Code s'est arrêté mais la fenêtre cmd est encore ouverte${since ? ` depuis <span class="tab-num">${escapeHtml(fmtAgo(since).replace('il y a ', ''))}</span>` : ''}.</p>
      ${badges ? `<div class="live-badges">${badges}</div>` : ''}
      <div class="m"><span><b>${fmtNum(s.messages || 0)}</b> messages</span><span><b>${s.sessions || 0}</b> ${plural(s.sessions || 0, 'session', 'sessions')}</span><span><b>${nMcp}</b> ${plural(nMcp, 'MCP', 'MCPs')}</span></div>
      <div class="row"></div>`;
  } else {
    const since = sessionSince(w.id);
    const segs = [
      ['cache lu', s.cache_read_tokens || 0, 'var(--seg-1)'],
      ['cache écrit', s.cache_creation_tokens || 0, 'var(--seg-2)'],
      ['sortie', s.output_tokens || 0, 'var(--seg-3)'],
    ];
    const tot = segs.reduce((a, x) => a + x[1], 0) + (s.input_tokens || 0);
    card['innerHTML'] = `
      <div class="t">${wsGem(w)}<div class="nm">${escapeHtml(label)}<small>${escapeHtml(w.id)}</small></div>
        <span class="lpill"><span class="sdot live"></span>En direct</span></div>
      ${badges ? `<div class="live-badges">${badges}</div>` : ''}
      <div class="m"><span><b data-count="${s.messages || 0}">${fmtNum(s.messages || 0)}</b> messages</span><span><b>${s.sessions || 0}</b> ${plural(s.sessions || 0, 'session', 'sessions')}</span><span><b>${nMcp}</b> ${plural(nMcp, 'MCP', 'MCPs')}</span>${since ? `<span>depuis <b class="timer" data-since="${escapeHtml(since)}">${escapeHtml(fmtElapsed(Date.now() - Date.parse(since)))}</b></span>` : ''}</div>
      ${tot ? `<div class="tok" role="img" aria-label="Répartition des tokens : ${segs.map(x => `${x[0]} ${fmtCompact(x[1])}`).join(', ')}">${segs.map((x, k) => `<i style="--i:${k};width:${Math.max(1.5, x[1] / tot * 100)}%;background:${x[2]}"></i>`).join('')}</div>
      <div class="tok-l">${segs.map(x => `<span><i style="background:${x[2]}"></i>${x[0]} <b>${escapeHtml(fmtCompact(x[1]))}</b></span>`).join('')}</div>` : ''}
      <div class="row"></div>`;
  }
  const row = card.querySelector('.row');
  const resume = btn('Reprendre', 'btn-primary btn-sm', st === 'idle' ? I.play : I.terminal);
  resume.title = 'Reprendre la dernière session Claude Code de ce workspace';
  resume.addEventListener('click', (e) => { e.stopPropagation(); doResume(w, resume); });
  const stop = st === 'idle'
    ? btn('Fermer le terminal', 'btn-sm', I.x)
    : btn('Arrêter', 'btn-sm btn-ghost-live', I.stop);
  stop.title = st === 'idle' ? 'Fermer la fenêtre cmd restée ouverte' : 'Arrêter la session Claude Code en cours';
  stop.addEventListener('click', (e) => { e.stopPropagation(); doStop(w); });
  row.append(resume, stop);
  if (st !== 'idle') {
    const open = document.createElement('a');
    open.className = 'hint';
    open.href = `#/workspace/${encodeURIComponent(w.id)}`;
    open['innerHTML'] = `Ouvrir ${I.right}`;
    open.addEventListener('click', (e) => e.stopPropagation());
    row.appendChild(open);
  }
  bindOpenWorkspace(card, w);
  bindStateBadges(card, w);
  return card;
}

// Navigation vers le detail : clic n'importe ou (hors boutons / liens) +
// Entree / Espace quand l'element lui-meme a le focus.
function bindOpenWorkspace(node, w) {
  node.addEventListener('click', (e) => {
    if (e.target.closest('button, a, input, label, select, textarea')) return;
    location.hash = `#/workspace/${w.id}`;
  });
  node.addEventListener('keydown', (e) => {
    if (e.target !== node) return;
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); location.hash = `#/workspace/${w.id}`; }
  });
}

// Lot E item 1 : badges d'etat conditionnels surfaces depuis des donnees
// deja chargees (sanity-check, path_exists). Ils LIENT vers le detail.
function stateBadgesHtml(w) {
  const out = [];
  if (w.path_exists === false) {
    out.push(`<span class="badge badge-err ws-badge-pathko" role="button" tabindex="0" title="Le dossier de ce workspace est introuvable sur le disque : ${escapeHtml(w.path || '(chemin inconnu)')}. Clique pour ouvrir le détail.">⛔ chemin KO</span>`);
  }
  if ((STATE.sanityDesync instanceof Set) && STATE.sanityDesync.has(w.id)) {
    out.push(`<span class="badge badge-warn ws-badge-desync" role="button" tabindex="0" title="Le registre MCP et le .mcp.json de ce workspace divergent. Clique pour ouvrir le détail et synchroniser.">⚠ désync</span>`);
  }
  return out.join('');
}
function bindStateBadges(node, w) {
  for (const b of node.querySelectorAll('.ws-badge-pathko, .ws-badge-desync')) {
    const go = (e) => { e.preventDefault(); e.stopPropagation(); location.hash = `#/workspace/${w.id}`; };
    b.addEventListener('click', go);
    b.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') go(e); });
  }
}

// --- Actions de session partagees (cartes, lignes, grille) ---------------
function doResume(w, button) {
  return withBusy(button, async () => {
    try { const r = await API.post(`/api/launch-resume/${w.id}`, {}); toastOk(r.message || 'Reprise…'); STATE.loading = true; setTimeout(route, 400); }
    catch (err) { toastErr(err.message); }
  }, { keepBusyOnSuccess: true });
}
function doLaunch(w, button) {
  return withBusy(button, async () => {
    try { const r = await API.post(`/api/launch/${w.id}`, {}); toastOk(r.message || 'Lancé'); STATE.loading = true; setTimeout(route, 400); }
    catch (err) { toastErr(err.message); }
  }, { keepBusyOnSuccess: true });
}
function doStop(w) {
  const idle = sessionState(w.id) === 'idle';
  const label = w.label || w.id;
  confirmDialog(idle
    ? `Fermer la fenêtre cmd restée ouverte pour « ${label} » ? Claude Code n'y tourne plus.`
    : `Arrêter la session Claude Code de « ${label} » ?`, async () => {
    try {
      const r = await API.post(`/api/workspaces/${w.id}/stop`, {});
      if (r.ok) {
        toastOk(r.message || (idle ? 'Terminal fermé' : 'Session arrêtée'));
        // RM-1 v2 : mutation locale + silent route
        if (STATE.activeSessions) delete STATE.activeSessions[w.id];
        route({ silent: true });
      } else { toastErr(r.message || 'Échec'); }
    } catch (err) { toastErr(err.message); }
  }, { danger: true, confirmLabel: idle ? 'Fermer le terminal' : 'Arrêter' });
}

// Boutons d'action d'une ligne / carte selon l'etat de session.
function wsRowActions(w) {
  const st = sessionState(w.id);
  const label = w.label || w.id;
  const out = [];
  if (st) {
    const resume = btn('Reprendre', 'btn-sm', st === 'idle' ? I.play : I.terminal);
    resume.addEventListener('click', (e) => { e.stopPropagation(); doResume(w, resume); });
    const stop = btn('', 'btn-sm btn-icon-only btn-danger-outline', st === 'idle' ? I.x : I.stop);
    stop.title = st === 'idle' ? 'Fermer la fenêtre cmd' : 'Arrêter la session';
    stop.setAttribute('aria-label', st === 'idle' ? `Fermer le terminal de ${label}` : `Arrêter la session de ${label}`);
    stop.addEventListener('click', (e) => { e.stopPropagation(); doStop(w); });
    out.push(resume, stop);
  } else {
    if ((_wsStats(w.id).sessions || 0) > 0) {
      const resume = btn('', 'btn-sm btn-icon-only btn-ghost', I.ret);
      resume.title = 'Reprendre la dernière session';
      resume.setAttribute('aria-label', `Reprendre la dernière session de ${label}`);
      resume.addEventListener('click', (e) => { e.stopPropagation(); doResume(w, resume); });
      out.push(resume);
    }
    const launch = btn('Lancer', 'btn-sm launch', I.play);
    launch.setAttribute('aria-label', `Lancer Claude Code dans ${label}`);
    launch.addEventListener('click', (e) => { e.stopPropagation(); doLaunch(w, launch); });
    out.push(launch);
  }
  return out;
}

function _mcpChips(id) {
  const ids = _wsMcpIds(id);
  if (!ids.length) return '<span class="dim">aucun</span>';
  return `<span class="chip">${escapeHtml(ids[0])}</span>${ids.length > 1 ? `<span class="chip more"${hcAttrs([{ title: 'Autres MCPs', items: ids.slice(1) }])}>+${ids.length - 1}</span>` : ''}`;
}

// ================================================================
// Navigateur « Tous les workspaces » : recherche + tri (segmented et
// en-tetes de colonnes) + bascule liste <-> grille memorisee
// (localStorage nebula-ws-view / nebula-ws-sort).
// ================================================================
function buildWorkspacesBrowser() {
  const wrap = el('section', 'ws-browser');
  wrap.setAttribute('aria-labelledby', 'h-all-ws');
  let view = 'list';
  let sort = 'recent';
  try { const v = localStorage.getItem('nebula-ws-view'); if (v === 'list' || v === 'grid') view = v; } catch {}
  try { const v = localStorage.getItem('nebula-ws-sort'); if (['recent', 'name', 'sessions'].includes(v)) sort = v; } catch {}

  const head = el('h2', 'lbl rise');
  head.id = 'h-all-ws';
  head.style.setProperty('--i', 7);
  head['innerHTML'] = `Tous les workspaces <small data-ws-count>${STATE.workspaces.length}</small>
    <span class="r home-tools">
      <span class="search-field">${I.search}<input class="input" type="search" placeholder="Filtrer…" aria-label="Filtrer les workspaces"></span>
      <span class="seg" role="group" aria-label="Tri" data-seg="sort"><span class="thumb"></span>
        <button type="button" data-v="recent" aria-pressed="${sort === 'recent'}">Récents</button><button type="button" data-v="name" aria-pressed="${sort === 'name'}">Nom</button><button type="button" data-v="sessions" aria-pressed="${sort === 'sessions'}">Sessions</button></span>
      <span class="seg" role="group" aria-label="Affichage" data-seg="view"><span class="thumb"></span>
        <button type="button" data-v="list" aria-pressed="${view === 'list'}" aria-label="Liste" title="Liste">${I.list}</button><button type="button" data-v="grid" aria-pressed="${view === 'grid'}" aria-label="Grille" title="Grille">${I.grid}</button></span>
    </span>`;
  const host = el('div', 'rise');
  host.id = 'ws-host';
  host.style.setProperty('--i', 8);
  wrap.append(head, host);
  const search = head.querySelector('input');
  const sortSeg = head.querySelector('[data-seg="sort"]');
  const viewSeg = head.querySelector('[data-seg="view"]');

  const setSort = (v) => {
    sort = v;
    try { localStorage.setItem('nebula-ws-sort', v); } catch {}
    sortSeg.querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.v === v)));
    placeSegThumb(sortSeg);
    draw();
  };

  const draw = (animate) => {
    const q = search.value.trim().toLowerCase();
    let list = STATE.workspaces.slice();
    if (q) list = list.filter(w => (`${w.label || ''} ${w.id} ${w.description || ''}`).toLowerCase().includes(q));
    const last = (id) => _wsStats(id).last || '';
    list.sort((a, b) => {
      if (sort === 'name') return (a.label || a.id).localeCompare(b.label || b.id, 'fr');
      if (sort === 'sessions') return (_wsStats(b.id).sessions || 0) - (_wsStats(a.id).sessions || 0);
      // recent : sessions en cours d'abord, puis derniere activite (jamais = en bas)
      return (_homeStateRank(a.id) - _homeStateRank(b.id))
        || (last(b.id) > last(a.id) ? 1 : last(b.id) < last(a.id) ? -1 : (a.label || a.id).localeCompare(b.label || b.id, 'fr'));
    });
    head.querySelector('[data-ws-count]').textContent = q ? `${list.length} sur ${STATE.workspaces.length}` : String(STATE.workspaces.length);
    if (!list.length) {
      host['innerHTML'] = `<div class="card home-empty">Aucun workspace ne correspond à « ${escapeHtml(search.value.trim())} ». </div>`;
      const clr = btn('Effacer le filtre', 'btn-sm');
      clr.addEventListener('click', () => { search.value = ''; draw(); search.focus(); });
      host.firstElementChild.appendChild(clr);
      return;
    }
    if (view === 'grid') {
      const grid = el('div', 'ws-grid');
      for (const w of list) grid.appendChild(workspaceCard(w));
      host.replaceChildren(grid);
    } else {
      const tbl = el('div', 'card tbl');
      tbl.setAttribute('role', 'table');
      tbl.setAttribute('aria-label', 'Workspaces');
      const hdr = el('div', 'tr h');
      hdr.setAttribute('role', 'row');
      const sortBtn = (v, txt) => `<button type="button" data-sort="${v}" ${sort === v ? `aria-sort="${v === 'name' ? 'ascending' : 'descending'}"` : ''} title="Trier par ${txt.toLowerCase()}">${txt}${sort === v ? I.down : ''}</button>`;
      hdr['innerHTML'] = `<span role="columnheader">${sortBtn('name', 'Workspace')}</span><span role="columnheader">État</span><span role="columnheader">MCPs</span><span class="num" role="columnheader">${sortBtn('sessions', 'Sessions')}</span><span role="columnheader">${sortBtn('recent', 'Activité')}</span><span role="columnheader"><span class="sr-only">Actions</span></span>`;
      hdr.querySelectorAll('svg').forEach(s => { s.style.width = '12px'; s.style.height = '12px'; });
      hdr.addEventListener('click', (e) => { const b = e.target.closest('[data-sort]'); if (b && b.dataset.sort !== sort) setSort(b.dataset.sort); });
      tbl.appendChild(hdr);
      for (const w of list) tbl.appendChild(workspaceRow(w));
      host.replaceChildren(tbl);
    }
    if (animate && motionOK()) { host.classList.remove('fade-in'); void host.offsetWidth; host.classList.add('fade-in'); }
  };

  search.addEventListener('input', debounce(() => draw(), 120));
  bindSeg(sortSeg, setSort);
  bindSeg(viewSeg, (v) => { view = v; try { localStorage.setItem('nebula-ws-view', v); } catch {} draw(true); });
  draw();
  return wrap;
}

// Ligne du tableau (vue liste). Cible du re-rendu cible par le polling
// des sessions (router.js) : [data-ws-card][data-ws-kind=row].
function workspaceRow(w) {
  const s = _wsStats(w.id);
  const row = el('div', 'tr');
  row.dataset.wsCard = w.id; row.dataset.wsKind = 'row';
  row.setAttribute('role', 'row');
  row.tabIndex = 0;
  row.setAttribute('aria-label', `Ouvrir le workspace ${w.label || w.id}`);
  const badges = stateBadgesHtml(w);
  row['innerHTML'] = `
    <div class="wn" role="cell">${wsGem(w)}<div><b><span class="lbt">${escapeHtml(w.label || w.id)}</span>${selfImprovingMark(w.id)}${badges ? `<span class="row-badges">${badges}</span>` : ''}</b><small>${escapeHtml(w.id)}</small></div></div>
    <span role="cell">${wsStateMarker(w.id, 'cell')}</span>
    <div class="chips" role="cell">${_mcpChips(w.id)}</div>
    <span class="num" role="cell">${s.sessions || 0}</span>
    <span class="muted" role="cell" title="${escapeHtml(s.last ? fmtDateTime(s.last) : 'Aucune session')}">${escapeHtml(fmtAgo(s.last))}</span>
    <div class="ra" role="cell"></div>`;
  row.querySelector('.ra').append(...wsRowActions(w));
  bindOpenWorkspace(row, w);
  bindStateBadges(row, w);
  return row;
}

// Carte de la vue grille : [data-ws-card][data-ws-kind=card].
function workspaceCard(w) {
  const s = _wsStats(w.id);
  const nMcp = _wsMcpIds(w.id).length;
  const card = el('article', 'card wcard');
  card.dataset.wsCard = w.id; card.dataset.wsKind = 'card';
  card.tabIndex = 0;
  card.setAttribute('role', 'link');
  card.setAttribute('aria-label', `Ouvrir le workspace ${w.label || w.id}`);
  const badges = stateBadgesHtml(w);
  card['innerHTML'] = `
    <div class="top">${wsGem(w)}<div class="wn"><div><b><span class="lbt">${escapeHtml(w.label || w.id)}</span>${selfImprovingMark(w.id)}</b><small>${escapeHtml(w.id)}</small></div></div></div>
    ${badges ? `<div class="workspace-state-badges">${badges}</div>` : ''}
    <p>${w.description ? escapeHtml(w.description) : '<span class="dim">Pas de description</span>'}</p>
    <div class="meta"><span>${wsStateMarker(w.id, 'cell')}</span><span>${nMcp} MCP${nMcp > 1 ? 's' : ''}</span><span>${s.sessions || 0} sess.</span><span>${escapeHtml(fmtAgo(s.last))}</span></div>
    <div class="ra"></div>`;
  card.querySelector('.ra').append(...wsRowActions(w));
  bindOpenWorkspace(card, w);
  bindStateBadges(card, w);
  return card;
}

// ================================================================
// Colonne Activite : dernieres sessions, Sante, Journal.
// ================================================================
function buildHomeRail(sanity) {
  const rail = el('aside', 'rail');
  rail.setAttribute('aria-label', 'Activité et santé');
  const h = el('h2', 'lbl rise', 'Activité');
  h.style.setProperty('--i', 9);
  rail.appendChild(h);

  // Dernieres sessions (stats.last)
  const feedCard = el('section', 'card flush rise');
  feedCard.style.setProperty('--i', 9);
  const recent = STATE.workspaces.filter(w => _wsStats(w.id).last)
    .sort((a, b) => (_wsStats(b.id).last > _wsStats(a.id).last ? 1 : -1)).slice(0, 6);
  feedCard['innerHTML'] = `<div class="card-h"><h3>Dernières sessions</h3></div><div class="card-b">${recent.length
    ? `<ul class="feed">${recent.map(w => {
        const s = _wsStats(w.id);
        return `<li><a href="#/workspace/${encodeURIComponent(w.id)}">${wsGem(w)}<div style="min-width:0"><b>${escapeHtml(w.label || w.id)}</b><small>${fmtNum(s.messages || 0)} messages</small></div><time datetime="${escapeHtml(s.last)}" title="${escapeHtml(fmtDateTime(s.last))}">${sessionState(w.id) ? wsStateMarker(w.id, 'pill') : escapeHtml(fmtAgo(s.last))}</time></a></li>`;
      }).join('')}</ul>`
    : '<p class="dim" style="margin:0;font-size:13px">Aucune session pour le moment.</p>'}</div>`;
  rail.appendChild(feedCard);

  // Sante
  const healthCard = el('section', 'card flush rise sanity-card');
  healthCard.style.setProperty('--i', 10);
  healthCard['innerHTML'] = `<div class="card-h"><h3>Santé</h3><span class="r"></span></div>`;
  const refresh = btn('', 'btn-sm btn-ghost btn-icon-only', I.refresh);
  refresh.title = 'Relancer la vérification';
  refresh.setAttribute('aria-label', 'Relancer la vérification');
  healthCard.querySelector('.r').appendChild(refresh);
  const healthBody = el('div', 'card-b health');
  healthCard.appendChild(healthBody);
  rail.appendChild(healthCard);
  renderHealth(healthBody, sanity);
  refresh.addEventListener('click', () => loadSanity(healthBody));

  // Journal
  const journalCard = el('section', 'card flush journal rise');
  journalCard.style.setProperty('--i', 11);
  journalCard['innerHTML'] = `<div class="card-h"><h3>Journal</h3><span class="r"></span></div>`;
  const clear = btn('', 'btn-sm btn-ghost btn-icon-only btn-danger', I.trash);
  clear.title = 'Tout effacer';
  clear.setAttribute('aria-label', 'Effacer tout le journal');
  journalCard.querySelector('.r').appendChild(clear);
  const jBody = el('div', 'card-b');
  const jForm = el('form', 'journal-form');
  jForm['innerHTML'] = `<label class="sr-only" for="journal-note">Nouvelle note</label><textarea id="journal-note" rows="2" placeholder="Note rapide sur ce que tu fais…"></textarea>
    <div class="jf"><span><kbd class="k">Ctrl</kbd> <kbd class="k">Entrée</kbd> pour ajouter</span></div>`;
  const jSubmit = btn('Ajouter', 'btn-sm');
  jSubmit.type = 'submit';
  jForm.querySelector('.jf').appendChild(jSubmit);
  const jList = el('ul', 'jlist');
  jBody.append(jForm, jList);
  journalCard.appendChild(jBody);
  rail.appendChild(journalCard);
  jForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const ta = jForm.querySelector('textarea');
    const t = ta.value.trim();
    if (!t) { ta.focus(); return; }
    await withBusy(jSubmit, async () => {
      try {
        await API.post('/api/journal', { text: t });
        ta.value = ''; toastOk('Note enregistrée'); loadJournal(jList);
      } catch (err) { toastErr(err.message); }
    });
  });
  jForm.querySelector('textarea').addEventListener('keydown', (e) => {
    if (e.ctrlKey && !e.altKey && e.key === 'Enter') { e.preventDefault(); jSubmit.click(); }
  });
  clear.addEventListener('click', () => {
    confirmDialog('Effacer toutes les entrées du journal ?', async () => {
      try { await API.del('/api/journal'); loadJournal(jList); toastOk('Journal effacé'); }
      catch (e) { toastErr(e.message); }
    }, { danger: true, confirmLabel: 'Tout effacer' });
  });
  loadJournal(jList);
  return rail;
}

async function loadSanity(host) {
  host['innerHTML'] = '<div class="dim" style="font-size:12.5px">Vérification…</div>';
  try {
    const r = await API.get('/api/sanity-check');
    STATE.sanityDesync = new Set((r.findings || []).map(f => f.workspace));
    renderHealth(host, r);
  } catch (e) {
    host['innerHTML'] = `<div class="error-box">${escapeHtml(e.message)}</div>`;
  }
}

// Bloc Sante : sanity-check serveur (desync registre <-> .mcp.json, env
// manquant, reparation 1 clic) + controles calcules cote client depuis
// STATE (workspaces references par des MCPs mais inconnus de Nebula, MCPs
// sans workspace). `r` null = echec du sanity-check.
function renderHealth(host, r) {
  host['innerHTML'] = '';
  const line = (cls, icon, title, desc) => {
    const d = el('div', 'hl');
    d['innerHTML'] = `<span class="hi ${cls}">${icon}</span><div><b>${title}</b>${desc ? `<span class="d">${desc}</span>` : ''}</div>`;
    host.appendChild(d);
    return d.querySelector('div');
  };
  if (!r) {
    line('err', I.alert, 'Vérification indisponible', 'Le sanity-check n\'a pas répondu. Relance avec le bouton ci-dessus.');
  } else {
    const findings = r.findings || [];
    const missingEnv = Object.entries(r.missing_env || {});
    if (!findings.length && !missingEnv.length) {
      line('ok', I.check, 'Registre et .mcp.json alignés', `${STATE.workspaces.length} workspace${STATE.workspaces.length > 1 ? 's' : ''} vérifié${STATE.workspaces.length > 1 ? 's' : ''}, aucune variable d'environnement manquante.`);
    }
    if (findings.length) {
      const box = line('warn', I.refresh, `${findings.length} workspace${findings.length > 1 ? 's' : ''} désynchronisé${findings.length > 1 ? 's' : ''}`, 'Le registre MCP et le .mcp.json divergent.');
      if (findings.length > 1) {
        const all = btn('Tout synchroniser', 'btn-sm btn-primary', I.refresh);
        all.addEventListener('click', () => withBusy(all, async () => {
          try {
            const res = await API.post('/api/sync-all', {});
            toastOk('Sync terminé pour ' + Object.keys(res.results || {}).length + ' workspace(s)');
            warnHandEdited(collectHandEdited(res.results));
            loadSanity(host);
          } catch (e) { toastErr(e.message); }
        }));
        box.appendChild(all);
      }
      const list = el('div', 'health-list');
      for (const f of findings.slice(0, 6)) {
        const it = el('div', 'health-item');
        const detail = [
          f.missing_sync && f.missing_sync.length ? `à sync : ${f.missing_sync.join(', ')}` : '',
          f.stale && f.stale.length ? `obsolètes : ${f.stale.join(', ')}` : '',
        ].filter(Boolean).join(' · ');
        it['innerHTML'] = `<div><b class="mono">${escapeHtml(f.workspace)}</b><div class="dim" style="font-size:11.5px">${escapeHtml(detail)}</div></div>`;
        const sync = btn('', 'btn-sm btn-ghost btn-icon-only', I.refresh);
        sync.title = 'Synchronise le registre MCP vers le .mcp.json de ce workspace';
        sync.setAttribute('aria-label', `Synchroniser ${f.workspace}`);
        sync.addEventListener('click', () => withBusy(sync, async () => {
          try {
            const res = await API.post(`/api/workspaces/${f.workspace}/sync-mcps`, {});
            toastOk('« ' + f.workspace + ' » synchronisé');
            warnHandEdited([syncNotice(f.workspace, res)]);
            loadSanity(host);
          } catch (e) { toastErr(e.message); }
        }));
        it.appendChild(sync);
        list.appendChild(it);
      }
      if (findings.length > 6) list.appendChild(el('div', 'dim', `<span style="font-size:12px">+${findings.length - 6} autre(s)</span>`));
      box.appendChild(list);
    }
    for (const [mcpId, vars] of missingEnv) {
      line('err', I.key, `${escapeHtml(mcpId)} : variable d'env manquante`, `${vars.map(escapeHtml).join(', ')} absente(s) de .env.local.`);
    }
  }
  // Controles cote client (aucune requete).
  const known = new Set(STATE.workspaces.map(w => w.id));
  const unknown = new Set();
  for (const m of STATE.mcps) {
    if (_isWild(m)) continue;
    for (const x of (m.workspaces || [])) if (!known.has(x)) unknown.add(x);
  }
  if (unknown.size) {
    const u = [...unknown].sort();
    const box = line('warn', I.alert, `${u.length} workspace${u.length > 1 ? 's' : ''} inconnu${u.length > 1 ? 's' : ''} référencé${u.length > 1 ? 's' : ''}`, 'Des MCPs ciblent des workspaces absents de Nebula.');
    const chips = el('div', 'chips');
    chips['innerHTML'] = u.slice(0, 5).map(x => `<span class="chip">${escapeHtml(x)}</span>`).join('') + (u.length > 5 ? `<span class="chip more"${hcAttrs([{ title: 'Autres workspaces inconnus', items: u.slice(5) }])}>+${u.length - 5}</span>` : '');
    box.appendChild(chips);
  }
  const unused = STATE.mcps.filter(m => !(m.workspaces || []).length);
  if (unused.length) {
    const names = unused.map(m => escapeHtml(m.name || m.id));
    const box = line('warn', I.box, unused.length === 1 ? `${names[0]} n'est utilisé nulle part` : `${unused.length} MCPs ne sont utilisés nulle part`,
      unused.length === 1 ? '' : names.join(', '));
    const a = document.createElement('a');
    a.href = '#/mcps';
    a.className = 'btn btn-sm btn-ghost';
    a['innerHTML'] = `${I.grid}<span>Activer depuis la matrice</span>`;
    a.addEventListener('click', () => { try { setMcpViewMode('matrix'); } catch { /* noop */ } });
    box.appendChild(a);
  }
}

async function loadJournal(host) {
  host['innerHTML'] = '<li class="dim" style="border:0">Chargement…</li>';
  try {
    const r = await API.get('/api/journal');
    const entries = (r.entries || []).slice().reverse().slice(0, 8);
    if (!entries.length) {
      host['innerHTML'] = '<li class="dim" style="border:0;font-size:12.5px">Aucune entrée pour le moment.</li>';
      return;
    }
    host['innerHTML'] = entries.map(e => `<li><time>${escapeHtml(e.ts)}</time>${escapeHtml(e.text)}</li>`).join('');
  } catch (e) {
    host['innerHTML'] = `<li class="error-box">${escapeHtml(e.message)}</li>`;
  }
}
