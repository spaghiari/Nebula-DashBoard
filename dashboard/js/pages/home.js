/* ================================================================
   Nebula - Page Home (Accueil)
   ----------------------------------------------------------------
   renderHome : KPI row + bandeau quickstart + grid (workspaces, sanity, journal).
   buildHomeQuickstart : bandeau d'onboarding affiche tant que la
   checklist 6/6 n'est pas complete.
   workspaceCard : card d'un workspace (chip Reflexive, dot live, actions Lancer/Stop/Detail).
   loadSanity : panneau de sanity check (registre vs .mcp.json par workspace).
   loadJournal : 8 dernieres entrees du journal.

   Dependances : STATE, API, safe, escapeHtml, fmtDate, el, btn, I.*,
   setBreadcrumbs, setTopbarActions, toastOk, toastErr, confirmDialog, route.
   Forward-refs (resolus au runtime via global scope) : modalNewWorkspace,
   modalSetupWizard, modalRegisterExisting, resetOnboarded, startFirstRunWizard.

   Ref : CM-2 batch 5, refactor 2026-05-13.
   ================================================================ */
'use strict';

// Collecte les ids de workspaces dont le .mcp.json avait été édité à la main
// (drapeau `hand_edited` posé par sync_workspace_mcps). `results` = map
// {ws_id: {hand_edited?, ...}} renvoyée par /api/sync-all.
function collectHandEdited(results) {
  return Object.entries(results || {})
    .filter(([, r]) => r && r.hand_edited)
    .map(([ws]) => ws);
}

// Avertit (non bloquant) que des .mcp.json ont été modifiés hors Nebula et
// viennent d'être remplacés par la régénération depuis le registre. Le registre
// est la source de vérité : il faut éditer le registre, pas le fichier.
function warnHandEdited(wsIds) {
  if (!wsIds || !wsIds.length) return;
  const list = wsIds.join(', ');
  toast(
    `.mcp.json modifié hors Nebula (${list}) -- édite le registre, pas le fichier ; ta modif manuelle a été remplacée.`,
    'info', 8000
  );
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
    try {
      const r = await API.post('/api/sync-all', {});
      toastOk('Sync terminé pour ' + Object.keys(r.results || {}).length + ' workspace(s)');
      warnHandEdited(collectHandEdited(r.results));
    }
    catch (e) { toastErr(e.message); }
    finally { syncAllBtn.disabled = false; }
  });
  setTopbarActions([registerBtn, importBtn, syncAllBtn, newWsBtn]);

  const c = $('#content');
  c['innerHTML'] = '';
  const page = el('div', 'page');

  page.appendChild(el('div', 'page-header', `
    <div class="page-header-text">
      <div class="page-eyebrow"><span class="index">00.</span><span>Accueil</span></div>
      <h1 class="page-title">Nebula</h1>
      <p class="page-subtitle">Pilotage des workspaces, MCPs, plugins et skills Claude Code.</p>
    </div>
  `));
  mountHelpLink(page, 'premiers-pas', 'vue d\'ensemble de Nebula');

  const quickstart = buildHomeQuickstart();
  if (quickstart) page.appendChild(quickstart);

  // Stats + sanity en parallèle : la sanity alimente les badges « désync »
  // des workspace cards (lot E item 1a). On stocke l'ensemble des ids désync
  // dans STATE pour que workspaceCard() le lise sans refaire d'appel réseau.
  const [stats, sanity] = await Promise.all([
    safe('/api/stats', {}),
    safe('/api/sanity-check', { findings: [] }),
  ]);
  STATE.stats = stats;
  STATE.sanityDesync = new Set((sanity.findings || []).map(f => f.workspace));
  const wsCount = STATE.workspaces.length;
  const mcpCount = STATE.mcps.filter(m => m.status !== 'désactivé').length;
  const pluginCount = STATE.plugins.count || Object.keys(STATE.plugins.enabled || {}).length;
  const totalSessions = Object.values(stats).reduce((s, x) => s + (x.sessions || 0), 0);

  const kpis = el('div', 'kpi-row');
  kpis['innerHTML'] = `
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

  const grid = el('div', 'home-grid');
  const left = el('div');
  const right = el('div', 'stack');

  left.appendChild(el('div', 'section-label', '<span class="num">A.</span> Workspaces <span class="right">' + wsCount + ' total</span>'));
  if (wsCount === 0) {
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
  } else {
    const wsGrid = el('div', 'workspace-grid');
    for (const w of STATE.workspaces) wsGrid.appendChild(workspaceCard(w));
    left.appendChild(wsGrid);
  }

  right.appendChild(el('div', 'section-label', '<span class="num">B.</span> Sanity check'));
  const sanityCard = el('div', 'card sanity-card');
  sanityCard['innerHTML'] = `<div class="card-header"><h3 class="card-title">${I.shield} Sanity check</h3><button class="icon-btn" data-refresh aria-label="Rafraîchir">${I.refresh}</button></div>`;
  const sanityBody = el('div');
  sanityCard.appendChild(sanityBody);
  right.appendChild(sanityCard);
  loadSanity(sanityBody);
  sanityCard.querySelector('[data-refresh]').addEventListener('click', () => loadSanity(sanityBody));

  right.appendChild(el('div', 'section-label', '<span class="num">C.</span> Journal'));
  const journalCard = el('div', 'card');
  journalCard['innerHTML'] = `<div class="card-header"><h3 class="card-title">${I.book} Journal</h3><button class="icon-btn btn-danger" data-clear aria-label="Tout effacer">${I.trash}</button></div>`;
  const jForm = el('form', 'journal-form');
  jForm['innerHTML'] = `<textarea class="textarea" placeholder="Note rapide… (Ctrl+Entrée pour valider)" rows="2"></textarea>`;
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
  card.setAttribute('role', 'button');
  card.setAttribute('aria-label', `Ouvrir le workspace ${w.label || w.id}`);
  const stats = STATE.stats[w.id] || {};
  const mcpsInfo = STATE.wsMcps[w.id] || { active: [] };
  const last = stats.last ? fmtDate(stats.last) : 'jamais';

  // Lot E item 1 : badges d'état conditionnels surfacés depuis des données
  // déjà chargées (sanity-check, path_exists du registre). Cliquables vers la
  // vue/action concernée -- ils LIENT, ne réimplémentent rien.
  //   1a désync MCP  : workspace présent dans les findings de sanity-check.
  //   1b chemin KO   : w.path_exists === false (champ ajouté à /api/workspaces).
  const stateBadges = [];
  // Chemin KO en premier : c'est le plus bloquant (le dossier n'existe pas).
  if (w.path_exists === false) {
    stateBadges.push(`<span class="badge badge-err ws-badge-pathko" role="button" tabindex="0" title="Le dossier de ce workspace est introuvable sur le disque : ${escapeHtml(w.path || '(chemin inconnu)')}. Clique pour ouvrir le détail.">⛔ chemin KO</span>`);
  }
  if ((STATE.sanityDesync instanceof Set) && STATE.sanityDesync.has(w.id)) {
    stateBadges.push(`<span class="badge badge-warn ws-badge-desync" role="button" tabindex="0" title="Le registre MCP et le .mcp.json de ce workspace divergent. Clique pour ouvrir le détail et synchroniser.">⚠ désync</span>`);
  }
  const stateBadgesRow = stateBadges.length
    ? `<div class="workspace-state-badges">${stateBadges.join('')}</div>`
    : '';

  card['innerHTML'] = `
    <div class="workspace-card-header">
      <span class="workspace-emoji">${escapeHtml(w.emoji || '📁')}</span>
      <div style="flex:1;min-width:0">
        <h3 class="workspace-name">${escapeHtml(w.label || w.id)}</h3>
        <div class="workspace-id mono">${escapeHtml(w.id)}</div>
      </div>
    </div>
    ${stateBadgesRow}
    <p class="workspace-desc">${escapeHtml(w.description || '—')}</p>
    <div class="workspace-meta">
      <span class="workspace-meta-item">${I.cpu}<span>${mcpsInfo.active.length} MCP${mcpsInfo.active.length > 1 ? 's' : ''}</span></span>
      <span class="workspace-meta-item">${I.message}<span>${stats.sessions || 0} session${(stats.sessions || 0) > 1 ? 's' : ''}</span></span>
      <span class="workspace-meta-item">${I.history}<span>${last}</span></span>
    </div>
  `;

  // Badges d'état : navigation clavier vers le détail (le click souris remonte
  // déjà au handler de la card via propagation). On garde le même flux que le
  // clic sur la card -- le détail expose le panneau de sync / le chemin.
  for (const b of card.querySelectorAll('.workspace-state-badges [role=button]')) {
    b.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault(); e.stopPropagation();
        location.hash = `#/workspace/${w.id}`;
      }
    });
  }

  // Chip Reflexive en coin haut-droit, click toggle direct.
  const refxChip = document.createElement('button');
  refxChip.type = 'button';
  refxChip.className = 'workspace-refx-chip' + (w.reflexive_enabled ? ' is-on' : '');
  refxChip.title = w.reflexive_enabled
    ? 'Reflexive observe ce workspace. Clic pour désactiver.'
    : "Reflexive inactif. Clic pour activer l'observation (installe les hooks).";
  const refxLabel = el('span'); refxLabel.textContent = w.reflexive_enabled ? 'on' : 'off';
  refxChip['innerHTML'] = I.brain;
  refxChip.appendChild(refxLabel);
  refxChip.addEventListener('click', async (e) => {
    e.stopPropagation();
    const wanted = !w.reflexive_enabled;
    refxChip.disabled = true;
    try {
      const ep = wanted ? 'enable' : 'disable';
      await API.post('/api/reflexive/workspace/' + w.id + '/' + ep);
      w.reflexive_enabled = wanted;
      refxChip.classList.toggle('is-on', wanted);
      refxLabel.textContent = wanted ? 'on' : 'off';
      refxChip.title = wanted
        ? 'Reflexive observe ce workspace. Clic pour désactiver.'
        : "Reflexive inactif. Clic pour activer l'observation (installe les hooks).";
      toastOk(wanted
        ? "Reflexive activé -- hooks installés (relance la session Claude pour qu'ils prennent)"
        : 'Reflexive désactivé -- hooks retirés');
    } catch (err) { toastErr(err.message); }
    refxChip.disabled = false;
  });
  card.appendChild(refxChip);

  const isActive = !!(STATE.activeSessions || {})[w.id];
  if (isActive) {
    const liveDot = el('span', 'workspace-live-dot');
    liveDot.title = 'Session Claude Code active';
    card.appendChild(liveDot);
  }

  const actions = el('div', 'workspace-actions');
  if (isActive) {
    const stopBtn = btn('Stop', 'btn-sm btn-danger-outline', I.x);
    stopBtn.title = 'Arrêter la session Claude Code en cours';
    stopBtn.addEventListener('click', async (e) => {
      e.stopPropagation();
      confirmDialog(`Arrêter la session Claude Code de « ${w.label || w.id} » ?`, async () => {
        try {
          const r = await API.post(`/api/workspaces/${w.id}/stop`, {});
          if (r.ok) {
            toastOk(r.message || 'Session arrêtée');
            // RM-1 v2 : mutation locale + silent route
            if (STATE.activeSessions) delete STATE.activeSessions[w.id];
            route({ silent: true });
          }
          else { toastErr(r.message || 'Échec'); }
        } catch (err) { toastErr(err.message); }
      }, { danger: true });
    });
    actions.appendChild(stopBtn);
  } else {
    const launch = btn('Lancer', 'btn-primary btn-sm', I.play);
    launch.addEventListener('click', (e) => {
      e.stopPropagation();
      withBusy(launch, async () => {
        try { const r = await API.post(`/api/launch/${w.id}`, {}); toastOk(r.message || 'Lancé'); STATE.loading = true; setTimeout(route, 400); }
        catch (err) { toastErr(err.message); }
      }, { keepBusyOnSuccess: true });
    });
    actions.appendChild(launch);
  }
  const detail = btn('Détail', 'btn-sm', I.right);
  detail.addEventListener('click', (e) => { e.stopPropagation(); location.hash = `#/workspace/${w.id}`; });
  actions.appendChild(detail);
  card.appendChild(actions);
  card.addEventListener('click', () => { location.hash = `#/workspace/${w.id}`; });
  card.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); location.hash = `#/workspace/${w.id}`; }
  });
  return card;
}

async function loadSanity(host) {
  host['innerHTML'] = '<div style="padding:var(--sp-3);color:var(--text-dim);font-size:12px">Vérification…</div>';
  try {
    const r = await API.get('/api/sanity-check');
    if (!r.findings.length && Object.keys(r.missing_env || {}).length === 0) {
      host['innerHTML'] = `<div class="sanity-empty">${I.success}<div>Tout est en ordre.</div></div>`;
      return;
    }
    const list = el('div', 'sanity-list');

    // « Tout synchroniser » si plusieurs workspaces désync (réutilise
    // /api/sync-all). Placé en tête de liste pour rester découvrable.
    if (r.findings.length > 1) {
      const allRow = el('div', 'sanity-item');
      allRow.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:var(--sp-2)';
      const lbl = el('div', 'dim');
      lbl.style.fontSize = '12px';
      lbl['innerHTML'] = `<strong>${r.findings.length} workspaces désync</strong> registre ↔ <code class="mono">.mcp.json</code>`;
      const syncAllBtn = btn('Tout synchroniser', 'btn-sm btn-primary', I.refresh);
      syncAllBtn.addEventListener('click', () => withBusy(syncAllBtn, async () => {
        try {
          const res = await API.post('/api/sync-all', {});
          toastOk('Sync terminé pour ' + Object.keys(res.results || {}).length + ' workspace(s)');
          warnHandEdited(collectHandEdited(res.results));
          loadSanity(host);
        } catch (e) { toastErr(e.message); }
      }));
      allRow.append(lbl, syncAllBtn);
      list.appendChild(allRow);
    }

    for (const f of r.findings) {
      const item = el('div', 'sanity-item');
      item['innerHTML'] = `
        <div class="row" style="justify-content:space-between">
          <strong class="mono" style="font-size:12px">${escapeHtml(f.workspace)}</strong>
          <span class="badge badge-warn">désync</span>
        </div>
        ${f.missing_sync.length ? `<div class="dim">à sync : <span class="mono">${f.missing_sync.map(escapeHtml).join(', ')}</span></div>` : ''}
        ${f.stale.length ? `<div class="dim">obsolètes : <span class="mono">${f.stale.map(escapeHtml).join(', ')}</span></div>` : ''}
      `;
      // Bouton de réparation 1-clic : sync ce workspace précis
      // (POST /api/workspaces/<id>/sync-mcps), puis rafraîchit le panneau.
      const actionRow = el('div');
      actionRow.style.cssText = 'display:flex;justify-content:flex-end;margin-top:var(--sp-2)';
      const syncBtn = btn('Sync ce workspace', 'btn-sm', I.refresh);
      syncBtn.title = "Synchronise le registre MCP vers le .mcp.json de ce workspace";
      syncBtn.addEventListener('click', () => withBusy(syncBtn, async () => {
        try {
          const res = await API.post(`/api/workspaces/${f.workspace}/sync-mcps`, {});
          toastOk('« ' + f.workspace + ' » synchronisé');
          // Avertit si le .mcp.json avait été édité à la main : le registre est
          // la source de vérité, la modif manuelle vient d'être remplacée.
          if (res && res.hand_edited) warnHandEdited([f.workspace]);
          loadSanity(host);
        } catch (e) { toastErr(e.message); }
      }));
      actionRow.appendChild(syncBtn);
      item.appendChild(actionRow);
      list.appendChild(item);
    }
    for (const [mcpId, vars] of Object.entries(r.missing_env || {})) {
      const item = el('div', 'sanity-item err');
      item['innerHTML'] = `
        <div class="row" style="justify-content:space-between">
          <strong class="mono" style="font-size:12px">${escapeHtml(mcpId)}</strong>
          <span class="badge badge-err">env manquant</span>
        </div>
        <div class="dim">${vars.map(escapeHtml).join(', ')}</div>
      `;
      list.appendChild(item);
    }
    host['innerHTML'] = '';
    host.appendChild(list);
  } catch (e) {
    host['innerHTML'] = `<div class="error-box">${escapeHtml(e.message)}</div>`;
  }
}

async function loadJournal(host) {
  host['innerHTML'] = '<div class="dim" style="font-size:12px">Chargement…</div>';
  try {
    const r = await API.get('/api/journal');
    const entries = (r.entries || []).slice().reverse().slice(0, 8);
    if (!entries.length) {
      host['innerHTML'] = '<div class="dim" style="font-size:12px;padding:var(--sp-2)">Aucune entrée pour le moment.</div>';
      return;
    }
    host['innerHTML'] = '';
    for (const e of entries) {
      const item = el('div', 'journal-entry');
      item['innerHTML'] = `<div class="journal-ts">${escapeHtml(e.ts)}</div><div class="journal-text">${escapeHtml(e.text)}</div>`;
      host.appendChild(item);
    }
  } catch (e) {
    host['innerHTML'] = `<div class="error-box">${escapeHtml(e.message)}</div>`;
  }
}
