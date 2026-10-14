/* ================================================================
   Nebula - Page MCPs
   ----------------------------------------------------------------
   renderMCPs : liste les serveurs MCP enregistres (avec filtres),
   permet de creer/editer (modalNewMCP), importer (recettes), gerer
   les recettes locales (modalMcpRecipes / modalInstallRecipe /
   modalSaveAsRecipe / modalEditRecipe).

   Forward-refs : modal*, render*, fonctions utilitaires (STATE, API,
   safe, toast, $, escapeHtml, btn, el, I) viennent du script-scope
   partage (foundations + app.js).

   Ref : CM-2 split app.js, refactor 2026-05-13.
   ================================================================ */
'use strict';

/* ================================================================
   PAGE: MCPs
   ================================================================ */
/* ================================================================
   PAGE MCPS (liste + cards + modals new/edit/recipes)
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
  c['innerHTML'] = '';
  const page = el('div', 'page');

  const nWs = (STATE.workspaces || []).length;
  page.appendChild(el('div', 'page-header rise', `
    <div class="page-header-text">
      <h1 class="page-title">MCPs</h1>
      <p class="page-subtitle">${STATE.mcps.length} serveur${STATE.mcps.length > 1 ? 's' : ''} dans le registre, synchronisé${STATE.mcps.length > 1 ? 's' : ''} vers les <span class="mono">.mcp.json</span> de ${nWs} workspace${nWs > 1 ? 's' : ''}.</p>
    </div>
  `));
  mountHelpLink(page, 'mcps', 'les MCPs');

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
    envBanner['innerHTML'] = `
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
      banner['innerHTML'] = `
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
    } catch (e) { console.warn('[conflicts] banner fetch échoué :', e.message); }
  })();

  // Barre de filtres : recherche + puces a compteurs (type / usage, statut)
  // + bascule Cartes | Matrice (memorisee en localStorage ; Cartes par defaut).
  const toolbar = el('div', 'mcp-filters rise');
  toolbar.style.setProperty('--i', 1);
  toolbar['innerHTML'] = `<span class="search-field">${I.search}<input class="input" type="search" placeholder="Nom, commande, workspace…" aria-label="Filtrer les MCPs"></span>`;
  const searchInput = toolbar.querySelector('input');
  // Pre-remplissage depuis la palette (Ctrl+K > un MCP).
  if (STATE.filter && STATE.filter.mcp) { searchInput.value = STATE.filter.mcp; STATE.filter.mcp = ''; }
  let typeF = '';   // '' | stdio | http | sse | orphan
  let statusF = ''; // '' | à configurer | désactivé
  const typeGroup = el('span', 'mcp-chipgroup');
  typeGroup.setAttribute('role', 'group');
  typeGroup.setAttribute('aria-label', 'Filtrer par type');
  const statusGroup = el('span', 'mcp-chipgroup');
  statusGroup.setAttribute('role', 'group');
  statusGroup.setAttribute('aria-label', 'Filtrer par statut');
  const drawChips = () => {
    const all = STATE.mcps || [];
    const tr = (m) => m.transport || 'stdio';
    const types = [['', 'Tous', all.length], ['stdio', 'stdio', all.filter(m => tr(m) === 'stdio').length],
      ['http', 'http', all.filter(m => tr(m) === 'http').length], ['sse', 'sse', all.filter(m => tr(m) === 'sse').length],
      ['orphan', 'Sans workspace', all.filter(m => !(m.workspaces || []).length).length]]
      .filter(([v, , n]) => !v || v === 'orphan' || n > 0 || v === typeF);
    typeGroup['innerHTML'] = types.map(([v, l, n]) => `<button class="fchip" type="button" data-type="${v}" aria-pressed="${typeF === v}">${escapeHtml(l)} <b>${n}</b></button>`).join('');
    const sts = [['disponible', 'Disponibles'], ['à configurer', 'À configurer'], ['désactivé', 'Désactivés']]
      .map(([v, l]) => [v, l, all.filter(m => m.status === v).length]).filter(([v, , n]) => n > 0 || v === statusF);
    statusGroup['innerHTML'] = sts.length ? '<span class="fchip-sep" aria-hidden="true"></span>' + sts.map(([v, l, n]) => `<button class="fchip" type="button" data-status="${escapeHtml(v)}" aria-pressed="${statusF === v}" title="Cliquer à nouveau pour retirer le filtre">${escapeHtml(l)} <b>${n}</b></button>`).join('') : '';
  };
  typeGroup.addEventListener('click', (e) => { const b = e.target.closest('[data-type]'); if (!b) return; typeF = b.dataset.type; drawChips(); renderList(); });
  statusGroup.addEventListener('click', (e) => { const b = e.target.closest('[data-status]'); if (!b) return; statusF = statusF === b.dataset.status ? '' : b.dataset.status; drawChips(); renderList(); });
  toolbar.append(typeGroup, statusGroup, el('span', 'sp'));

  let viewMode = mcpViewMode();
  const sortSel = el('select', 'select mx-sort');
  sortSel['innerHTML'] = `<option value="name">Tri : nom (A-Z)</option><option value="count">Tri : plus utilisés</option>`;
  sortSel.value = mcpMatrixSort();
  sortSel.setAttribute('aria-label', 'Tri de la matrice');
  toolbar.appendChild(sortSel);
  const viewToggle = el('span', 'seg mx-view');
  viewToggle.setAttribute('role', 'group');
  viewToggle.setAttribute('aria-label', "Mode d'affichage des MCPs");
  viewToggle['innerHTML'] = `<span class="thumb"></span><button type="button" data-view="cards" aria-pressed="false">${I.grid}Cartes</button><button type="button" data-view="matrix" aria-pressed="false">${I.list}Matrice</button>`;
  toolbar.appendChild(viewToggle);
  page.appendChild(toolbar);
  drawChips();

  const grid = el('div', 'mcp-grid rise');
  grid.style.setProperty('--i', 2);
  page.appendChild(grid);
  const matrixHost = el('div', 'mx-host');
  page.appendChild(matrixHost);
  let matrix = null;

  const renderList = () => {
    const q = searchInput.value.trim().toLowerCase();
    const sf = statusF;
    const tf = typeF;
    const list = STATE.mcps.filter(m => {
      if (sf && m.status !== sf) return false;
      if (tf === 'orphan') { if ((m.workspaces || []).length) return false; }
      else if (tf && (m.transport || 'stdio') !== tf) return false;
      if (q) {
        const cmd = `${m.command || ''} ${(m.args || []).join(' ')} ${m.url || ''}`;
        const hay = `${m.id} ${m.name || ''} ${m.description || ''} ${(m.workspaces || []).join(' ')} ${m.transport || ''} ${cmd}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
    if (viewMode === 'matrix') {
      grid.style.display = 'none';
      matrixHost.style.display = '';
      if (!matrix) {
        matrix = createMcpMatrix({ onEdit: (m) => modalNewMCP(m) });
        matrixHost.appendChild(matrix.el);
      }
      matrix.render(list, STATE.workspaces || [], { sort: sortSel.value, all: STATE.mcps });
      return;
    }
    grid.style.display = '';
    matrixHost.style.display = 'none';
    grid['innerHTML'] = '';
    if (!list.length) {
      const empty = el('div', 'empty');
      const filterActive = !!(q || sf || tf);
      if (filterActive) {
        empty['innerHTML'] = `<div class="empty-title">Aucun MCP ne correspond</div><p class="muted">Modifie ta recherche ou tes filtres.</p>`;
      } else {
        empty['innerHTML'] = `<div class="empty-title">Aucun MCP</div><p class="muted">Crée ton premier MCP ou importe depuis Claude Code.</p>`;
      }
      grid.appendChild(empty);
      return;
    }
    for (const m of list) grid.appendChild(mcpCard(m));
  };
  searchInput.addEventListener('input', debounce(renderList, 100));
  sortSel.addEventListener('change', () => { setMcpMatrixSort(sortSel.value); renderList(); });

  const syncViewUi = () => {
    viewToggle.querySelectorAll('button').forEach(b => {
      const on = b.dataset.view === viewMode;
      b.classList.toggle('is-active', on);
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
    sortSel.style.display = viewMode === 'matrix' ? '' : 'none';
    requestAnimationFrame(() => placeSegThumb(viewToggle));
  };
  const switchView = (mode) => {
    if (mode === viewMode) return;
    const go = () => {
      viewMode = mode;
      setMcpViewMode(mode);
      // Le bandeau (ex. echec d'application) n'a pas de sens en vue Cartes.
      if (mode === 'cards') { const bar = document.getElementById('mx-bar'); if (bar) bar.remove(); }
      syncViewUi();
      renderList();
    };
    // Passer en Cartes avec des modifications non appliquees : on previent
    // plutot que de les abandonner en silence (pas de bandeau en vue Cartes).
    const pending = matrix ? matrix.pendingCount() : 0;
    if (mode === 'cards' && pending > 0) {
      confirmDialog(`${pending} modification(s) de la matrice n'ont pas été appliquées.\nPasser en vue Cartes les abandonne.`, () => { matrix.discard(); go(); },
        { danger: true, confirmLabel: 'Abandonner et passer en Cartes', cancelLabel: 'Rester sur la matrice' });
      return;
    }
    go();
  };
  viewToggle.addEventListener('click', (e) => {
    const b = e.target.closest('button[data-view]');
    if (b) switchView(b.dataset.view);
  });
  syncViewUi();
  renderList();
  if (viewMode !== 'matrix') { const bar = document.getElementById('mx-bar'); if (bar) bar.remove(); }

  // Auto-refresh des MCPs toutes les 30s tant que la page est active.
  // Le poller est nettoyé automatiquement via clearPagePollers() au changement de page.
  const liveDot = el('span', 'live-dot');
  liveDot.title = 'Auto-refresh actif (toutes les 30s)';
  liveDot.style.cssText = 'display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--ok);margin-left:8px;vertical-align:middle;animation:pulse 2s ease-in-out infinite';
  const titleEl = page.querySelector('.page-title');
  if (titleEl) titleEl.appendChild(liveDot);

  const pollerId = setInterval(async () => {
    try {
      const r = await API.get('/api/mcps');
      const next = r.mcps || [];
      // Re-render seulement si le contenu a changé (évite reflow inutile)
      if (JSON.stringify(next) !== JSON.stringify(STATE.mcps)) {
        STATE.mcps = next;
        drawChips();
        renderList();
      }
    } catch { /* silencieux : un blip réseau ne doit pas spammer */ }
  }, 30000);
  registerPagePoller(pollerId);

  c.appendChild(page);
}

// Pastille d'etat d'un MCP : statut calcule (disponible / a configurer /
// desactive) enrichi du dernier verdict de « Diagnostiquer » (m.last_probe,
// dashcore/mcp_probe.py). Seul un MCP « disponible » est concerne. Etats :
//   ok      -> « vérifié » (vert) : test OK, recent, config inchangee ;
//   err     -> « en échec » (rouge) ; warn -> « à revérifier » (orange) ;
//   expired / changed -> « disponible » (bleu), le verdict reste lisible
//   dans l'infobulle mais n'affirme plus rien.
// Age et validite dans une infobulle hcAttrs (pas de `title` natif).
function mcpStatePill(m) {
  const status = m.status || 'à configurer';
  const base = status === 'disponible' ? 'info' : status === 'désactivé' ? 'mute' : 'warn';
  const p = m.last_probe;
  if (status !== 'disponible' || !p || !p.at) return `<span class="pill ${base}">${escapeHtml(status)}</span>`;
  const iso = new Date(p.at * 1000).toISOString();
  const when = `${fmtAgo(iso)} (${fmtDateTime(iso)})`;
  const VERDICT = { ok: 'OK', warn: 'avec avertissements', err: 'en échec' };
  const LOOK = {
    ok: ['ok probe', 'vérifié'],
    warn: ['warn probe', 'à revérifier'],
    err: ['err probe', 'en échec'],
    // Verdict perime : reste « disponible », point creux = « un ancien test existe ».
    expired: ['info probe-old', status],
    changed: ['info probe-old', status],
  };
  const [cls, label] = LOOK[p.state] || [base, status];
  const lines = [`Résultat : ${VERDICT[p.verdict] || p.verdict}, ${when}.`];
  if (p.state === 'changed') lines.push('Le MCP a été modifié depuis : ce verdict ne vaut plus.');
  else if (p.state === 'expired') lines.push(`Plus vieux que ${p.fresh_days} jours : il ne vaut plus comme preuve.`);
  else lines.push(`Valable ${p.fresh_days} jours, ou jusqu'à la prochaine modification du MCP.`);
  lines.push('« Diagnostiquer » relance le test.');
  const hc = hcAttrs([{ title: 'Dernier diagnostic', items: lines, text: true }]);
  return `<span class="pill ${cls}"${hc} aria-label="${escapeHtml(`${label}. ${lines[0]}`)}">${escapeHtml(label)}</span>`;
}

function mcpCard(m) {
  const card = el('article', 'mcp-card');
  card.dataset.mcpId = m.id;
  // Statut réel calculé par compute_mcp_status (back) : disponible /
  // à configurer / désactivé. « connecté » n'est jamais retourné (aucune
  // sonde automatique) : pas de vert sans test explicite.
  // Lot E item 2 : « désactivé » est un choix VOLONTAIRE -> neutre (gris),
  // pas rouge. Le rouge est réservé aux états réellement cassés (env
  // manquant ci-dessous), pour ne pas mélanger « off » et « KO ».
  // Le vert (« vérifié ») vient du dernier verdict de « Diagnostiquer »
  // mémorisé côté serveur (last_probe), cf. mcpStatePill.
  const transport = m.transport || 'stdio';
  const isHttp = transport === 'http' || transport === 'sse';
  const cmd = isHttp ? (m.url || '—') : (m.command || '—') + (m.args && m.args.length ? ' ' + m.args.join(' ') : '');
  const headerCount = Object.keys(m.headers || {}).length;
  const envCount = Object.keys(m.env || {}).length;
  const chips = [`<span class="chip">${escapeHtml(transport)}</span>`];
  if (envCount) chips.push(`<span class="chip" title="${envCount} variable(s) d'env">${envCount} env</span>`);
  if (headerCount) chips.push(`<span class="chip" title="${headerCount} header(s)">${headerCount} hdr</span>`);
  if (m.cwd) chips.push(`<span class="chip" title="cwd : ${escapeHtml(m.cwd)}">cwd</span>`);

  // Lot E item 2 : sous-badge « env manquant » dérivé du même lint que le
  // diagnostic (lintInterpolation, js/lint.js). On compare les ${VAR}
  // référencées aux clés de .env.local déjà chargées (STATE.envKeys) -- aucun
  // appel réseau. Distingue un MCP réellement cassé (rouge) du statut neutre.
  const lint = lintInterpolation(mcpInterpolableStrings(m), STATE.envKeys);
  const missingEnv = lint.missing;
  // On ne montre le badge par card QUE si .env.local existe mais qu'une var
  // precise manque. Si le fichier n'existe pas du tout, le bandeau global en
  // tete de page le signale deja -- inutile de rougir chaque card (bruit).
  const missingBadge = (STATE.envExists && missingEnv.length)
    ? `<button type="button" class="pill err mcp-missing-env" title="Variable(s) référencée(s) mais absente(s) de .env.local : ${escapeHtml(missingEnv.join(', '))}. Clique pour diagnostiquer.">env manquant : ${escapeHtml(missingEnv.join(', '))}</button>`
    : '';

  // Workspaces : pastilles des workspaces connus, compte des inconnus.
  const wsList = m.workspaces || [];
  const wild = wsList.includes('*') || wsList.includes('all');
  const byId = new Map((STATE.workspaces || []).map(w => [w.id, w]));
  const known = wsList.filter(x => byId.has(x));
  const unknown = wsList.filter(x => x !== '*' && x !== 'all' && !byId.has(x));
  let used;
  if (wild) used = `<span class="pill accent" title="Actif dans TOUS les workspaces (joker « * »)">★ tous les workspaces</span>`;
  else if (!wsList.length) used = '<span class="pill warn">Aucun workspace</span>';
  else {
    const hc = hcAttrs([{ title: 'Dans Nebula', ws: known }, { title: 'Hors Nebula', ws: unknown }]);
    used = (known.length ? `<span class="gem-stack"${hc}>${known.slice(0, 5).map(x => wsGem(byId.get(x))).join('')}</span>` : '')
      + `<span>${known.length} workspace${known.length > 1 ? 's' : ''}${known.length > 5 ? ` (${escapeHtml(known.slice(0, 5).map(x => byId.get(x).label || x).join(', '))}…)` : ''}</span>`
      + (unknown.length ? `<span class="ghost"${hc}>+${unknown.length} hors Nebula</span>` : '');
  }

  card['innerHTML'] = `
    <div class="top">
      <span class="mi ${isHttp ? 'http' : ''}" aria-hidden="true">${isHttp ? I.ext : I.terminal}</span>
      <div style="min-width:0">
        <h3 class="mcp-name">${escapeHtml(m.name || m.id)}</h3>
        <div class="msub"><small>${escapeHtml(m.id)}</small>${chips.join('')}</div>
      </div>
      <div class="mstate">${mcpStatePill(m)}${missingBadge}</div>
    </div>
    <p class="mcp-desc ${m.description ? '' : 'none'}">${m.description ? escapeHtml(m.description) : 'Pas de description.'}</p>
    <div class="used">${used}</div>
    <div class="mcp-cmd" title="${escapeHtml(cmd)}">${escapeHtml(cmd)}</div>
    ${m.cwd ? `<div class="dim mono" style="font-size:11px" title="working directory">cd : ${escapeHtml(m.cwd)}</div>` : ''}
  `;
  // Sous-badge « env manquant » cliquable -> ouvre le diagnostic (lot C).
  const missingEl = card.querySelector('.mcp-missing-env');
  if (missingEl) missingEl.addEventListener('click', () => modalDiagnoseMCP(m));

  const footer = el('div', 'mcp-card-footer');
  const diag = btn('Diagnostiquer', 'btn-sm btn-ghost', I.activity || I.search);
  diag.title = 'Vérifier pourquoi ce MCP ne marche pas (variables, commande, sonde HTTP, sync)';
  diag.addEventListener('click', () => modalDiagnoseMCP(m));
  const ed = btn('Modifier', 'btn-sm btn-ghost', I.edit);
  ed.addEventListener('click', () => modalNewMCP(m));
  const rm = btn('', 'btn-sm btn-ghost btn-icon-only btn-danger', I.trash);
  rm.title = 'Supprimer';
  rm.setAttribute('aria-label', `Supprimer ${m.name || m.id}`);
  rm.addEventListener('click', () => confirmDialog(`Supprimer ${m.id} ?`, async () => {
    try {
      await API.del(`/api/mcps/${m.id}`);
      toastOk('Supprimé');
      // RM-1 v2 : mutation locale + silent route = pas de flash + pas
      // de fetch storm (les 15 requetes de loadAll evitees).
      STATE.mcps = STATE.mcps.filter(x => x.id !== m.id);
      Object.keys(STATE.wsMcps || {}).forEach(wsId => {
        const w = STATE.wsMcps[wsId];
        if (w && Array.isArray(w.active)) w.active = w.active.filter(x => x !== m.id);
      });
      route({ silent: true });
    }
    catch (e) { toastErr(e.message); }
  }, { danger: true, confirmLabel: 'Supprimer' }));
  footer.append(diag, ed, rm);
  card.appendChild(footer);
  return card;
}

// ── Diagnostic actionnable d'un MCP (Lot C audit UX 2026-05-25) ───────────────
// Modale qui appelle GET /api/mcps/<id>/diagnose : verdict global + liste de
// checks (label + statut coloré + detail + fix). Le lint statique front
// (lintInterpolation de js/lint.js) s'affiche INSTANTANÉMENT — les ${VAR}
// manquants et le char parasite sont connus côté client sans aller-retour
// réseau — pendant que la sonde HTTP (potentiellement lente) tourne au fond.
function modalDiagnoseMCP(m) {
  // Map statut -> classe de pastille / pictogramme (réutilise les badges projet).
  const STAT = {
    ok: { cls: 'badge-ok', dot: 'var(--ok)', icon: '✓', label: 'OK' },
    warn: { cls: 'badge-warn', dot: 'var(--warn)', icon: '!', label: 'Attention' },
    err: { cls: 'badge-err', dot: 'var(--err)', icon: '✗', label: 'Erreur' },
  };

  const body = el('div');

  // En-tête : verdict global (rempli plus bas, "en cours" au départ).
  const verdictBox = el('div', 'diag-verdict');
  verdictBox.style.cssText = 'display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:8px;margin-bottom:var(--sp-3);border:1px solid var(--border)';
  verdictBox['innerHTML'] = `
    <span class="diag-verdict-dot" style="width:12px;height:12px;border-radius:50%;background:var(--text-muted);flex:none"></span>
    <div style="flex:1;min-width:0">
      <strong class="diag-verdict-label">Diagnostic en cours…</strong>
      <div class="dim diag-verdict-sub" style="font-size:12px">Analyse de la config de <code class="mono">${escapeHtml(m.id)}</code>.</div>
    </div>
  `;
  body.appendChild(verdictBox);

  // Hôte de la liste des checks.
  const list = el('div', 'diag-checks');
  body.appendChild(list);

  // Rend un check {label, status, detail, fix} en bloc.
  const renderCheck = (c) => {
    const s = STAT[c.status] || STAT.warn;
    const row = el('div', 'diag-check');
    row.style.cssText = 'display:flex;gap:10px;padding:10px 0;border-top:1px solid var(--border)';
    row['innerHTML'] = `
      <span class="diag-check-icon" title="${escapeHtml(s.label)}" style="width:20px;height:20px;border-radius:50%;flex:none;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;color:#fff;background:${s.dot}">${s.icon}</span>
      <div style="flex:1;min-width:0">
        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
          <strong style="font-size:13px">${escapeHtml(c.label)}</strong>
          <span class="badge ${s.cls}">${escapeHtml(s.label)}</span>
        </div>
        ${c.detail ? `<p style="margin:4px 0 0;font-size:12.5px;color:var(--text-muted)">${escapeHtml(c.detail)}</p>` : ''}
        ${c.fix ? `<p style="margin:4px 0 0;font-size:12.5px"><strong>Correctif :</strong> ${escapeHtml(c.fix)}</p>` : ''}
      </div>
    `;
    return row;
  };

  // Met à jour l'en-tête de verdict global.
  const setVerdict = (verdict, sub) => {
    const s = STAT[verdict] || STAT.warn;
    verdictBox.querySelector('.diag-verdict-dot').style.background = s.dot;
    const LABELS = { ok: 'Tout est bon', warn: 'Points à vérifier', err: 'Problème(s) bloquant(s)' };
    verdictBox.querySelector('.diag-verdict-label').textContent = LABELS[verdict] || 'Diagnostic';
    if (sub) verdictBox.querySelector('.diag-verdict-sub').textContent = sub;
    verdictBox.style.borderColor = s.dot;
  };

  // Pré-affichage INSTANTANÉ du lint statique front (avant la réponse réseau).
  // On reconstruit le payload interpolable depuis le MCP courant.
  const preStrings = [
    m.command || '', m.url || '', m.cwd || '',
    ...(m.args || []).map(String),
    ...Object.values(m.env || {}).map(String),
    ...Object.values(m.headers || {}).map(String),
  ];
  const pre = lintInterpolation(preStrings, STATE.envKeys);
  if (pre.missing.length) {
    list.appendChild(renderCheck({
      label: 'Variables ${VAR} (pré-vérif locale)',
      status: 'err',
      detail: `Référencée(s) mais absente(s) de .env.local : ${pre.missing.join(', ')}.`,
      fix: `Définis ${pre.missing.join(', ')} dans .env.local (Outils -> Variables d'environnement).`,
    }));
  }
  if (pre.stuck.length) {
    const d = pre.stuck.map(h => `« ${h.char} » accolé à \${${h.varName}}`).join(', ');
    list.appendChild(renderCheck({
      label: 'Lint statique (pré-vérif locale)',
      status: 'warn',
      detail: `Caractère parasite : ${d}. Probable typo.`,
      fix: 'Retire le caractère accolé juste après le } de la variable.',
    }));
  }
  const loadingRow = el('div', 'diag-loading');
  loadingRow.style.cssText = 'display:flex;align-items:center;gap:8px;padding:12px 0;color:var(--text-muted);font-size:12.5px';
  loadingRow['innerHTML'] = `<span class="spinner"></span><span>Sonde réseau et vérifications serveur en cours…</span>`;
  list.appendChild(loadingRow);

  const close = btn('Fermer', 'btn-ghost');
  const { close: doClose } = openModal({
    title: `Diagnostic — ${m.name || m.id}`, body, footer: close, wide: true,
  });
  close.addEventListener('click', doClose);

  // Appel réseau : remplace la pré-vérif par le diagnostic serveur complet.
  (async () => {
    try {
      const r = await API.get(`/api/mcps/${m.id}/diagnose`);
      list['innerHTML'] = '';
      for (const c of (r.checks || [])) list.appendChild(renderCheck(c));
      const nb = (r.checks || []).length;
      setVerdict(r.verdict, `${nb} vérification(s) effectuée(s) sur ${m.id}.`);
      // Verdict memorise cote serveur : la pastille de la carte suit tout de suite.
      if (r.last_probe) {
        const cur = (STATE.mcps || []).find(x => x.id === m.id);
        for (const x of new Set([m, cur].filter(Boolean))) x.last_probe = r.last_probe;
        const old = document.querySelector(`.mcp-card[data-mcp-id="${CSS.escape(m.id)}"]`);
        if (old) old.replaceWith(mcpCard(cur || m));
      }
    } catch (e) {
      loadingRow.remove();
      setVerdict('err', 'Le diagnostic a échoué (voir ci-dessous).');
      list.appendChild(renderCheck({
        label: 'Diagnostic',
        status: 'err',
        detail: e.message || 'Erreur réseau pendant le diagnostic.',
        fix: 'Vérifie que le serveur Nebula tourne, puis relance le diagnostic.',
      }));
    }
  })();
}

// ── Recettes MCP : catalogue 1-clic ──────────────────────────────────────────
async function modalMcpRecipes() {
  const body = el('div');
  body['innerHTML'] = `<div class="page-loader"><div class="spinner"></div><span>Chargement…</span></div>`;
  const close = btn('Fermer', 'btn-ghost');
  const { close: doClose } = openModal({
    title: 'Recettes MCP — installation 1-clic', body, footer: close, wide: true,
  });
  close.addEventListener('click', doClose);

  let data;
  try { data = await API.get('/api/mcps/recipes'); }
  catch (e) {
    body['innerHTML'] = `<div class="error-box">${escapeHtml(e.message)}</div>`;
    return;
  }
  const recipes = data.recipes || [];
  const publicRecipes = recipes.filter(r => r.source !== 'local');
  const localRecipes = recipes.filter(r => r.source === 'local');
  const existingIds = new Set((STATE.mcps || []).map(m => m.id));

  body['innerHTML'] = '';

  // Bandeau d'aide
  const intro = el('div');
  intro.style.cssText = 'margin:0 0 var(--sp-3) 0;font-size:13px;color:var(--text-muted)';
  intro['innerHTML'] = `
    Sélection de MCPs pré-configurés. Clique pour installer en remplissant les paramètres requis (token, chemin…).<br>
    <span style="font-size:12px">Tu peux ajouter tes propres recettes locales (gitignored) via le bouton ci-dessous.</span>
  `;
  body.appendChild(intro);

  // Bandeau "Recettes locales" (toujours visible avec bouton)
  const localBar = el('div', 'recipes-local-bar');
  localBar['innerHTML'] = `
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
    label['innerHTML'] = `<span class="num">${isLocal ? '🔒' : '📦'}</span> ${title} <span class="right" style="color:var(--text-muted);font-weight:400">${list.length} recette${list.length > 1 ? 's' : ''}</span>`;
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
      card['innerHTML'] = `
        ${isLocal ? '<button class="recipe-edit-btn" type="button" title="Éditer la définition de cette recette">✎</button><button class="recipe-delete-btn" type="button" title="Supprimer cette recette locale">🗑</button>' : ''}
        <div class="recipe-emoji">${escapeHtml(r.emoji || '🔌')}</div>
        <div class="recipe-body">
          <div class="recipe-name">${escapeHtml(r.name)}${instances > 0 ? ` <span class="badge badge-info" style="margin-left:6px" title="Tu as déjà ${instances} instance(s) de cette recette installée(s)">${instances}× installée${instances > 1 ? 's' : ''}</span>` : ''}</div>
          <div class="recipe-desc">${escapeHtml(r.description || '')}</div>
          <div class="recipe-meta">
            <span class="badge">${escapeHtml(r.transport || 'stdio')}</span>
            ${paramCount > 0 ? `<span class="badge badge-info">${paramCount} param${paramCount > 1 ? 's' : ''} requis</span>` : '<span class="badge badge-ok">prêt à l\'emploi</span>'}
            ${safeUrl(r.docs_url) ? `<a class="badge recipe-docs-link" href="${escapeHtml(safeUrl(r.docs_url))}" target="_blank" rel="noopener">docs ↗</a>` : ''}
          </div>
        </div>
      `;
      // Lien docs : ne pas propager au clic de la card (sinon ouvre la modale)
      const docsLink = card.querySelector('.recipe-docs-link');
      if (docsLink) docsLink.addEventListener('click', (e) => e.stopPropagation());
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

  body['innerHTML'] = `
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
    field['innerHTML'] = `
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
  previewBox['innerHTML'] = `<div class="dim" style="font-size:11px;margin-bottom:4px">Commande générée :</div><code class="mono"></code>`;
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
  // Ouvre l'éditeur en mode "création depuis MCP" : id éditable, pas de delete.
  // Empilé au-dessus de la modale MCP (restée ouverte) : après enregistrement
  // on y revient, au lieu d'ouvrir le catalogue de recettes.
  modalEditRecipe(template, { fromMcp: true, sourceMcpId: mcp.id, onSaved: () => {} });
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
  body['innerHTML'] = `
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
    row['innerHTML'] = `
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
      // Re-fetch + re-ouvre la modal de catalogue (sauf appelant qui gère
      // la suite lui-même, ex. « Sauver comme recette » depuis la modale MCP).
      if (typeof opts.onSaved === 'function') opts.onSaved(resp);
      else modalMcpRecipes();
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
  body['innerHTML'] = `
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
        <div class="field"><label class="field-label">Statut</label><select class="select" name="status">${['à configurer','disponible','désactivé'].map(t => `<option ${m.status===t?'selected':''}>${t}</option>`).join('')}</select></div>
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
      <div class="field"><label class="field-label" for="mcp-raw-json-ta">JSON complet du MCP</label><div data-editor-host></div></div>
    </div>
  `;
  const updateTransportFields = () => {
    const t = body.querySelector('[name=transport]').value;
    body.querySelectorAll('[data-stdio]').forEach(e => e.style.display = t === 'stdio' ? '' : 'none');
    body.querySelectorAll('[data-http]').forEach(e => e.style.display = t !== 'stdio' ? '' : 'none');
  };
  body.querySelector('[name=transport]').addEventListener('change', updateTransportFields);
  updateTransportFields();
  // Editeur JSON maison (js/json-editor.js). `jsonTouched` : tant que
  // l'utilisateur n'y a rien saisi, l'onglet JSON est regenere depuis le
  // formulaire a chaque ouverture (sinon il affichait un etat perime).
  const cancel = btn('Annuler', 'btn-ghost');
  const save = btn(isEdit ? 'Mettre à jour' : 'Créer', 'btn-primary');
  let jsonTouched = false;
  let jsonValid = true;
  const updateSaveState = () => {
    const onJson = body.querySelector('.tab.active').dataset.tab === 'json';
    const bad = onJson && !jsonValid;
    save.disabled = bad;
    save.title = bad ? 'Corrige le JSON pour pouvoir enregistrer' : '';
  };
  // Garde anti-perte : toute saisie (formulaire, cases, JSON brut) rend la
  // modale « dirty » ; Échap / croix / clic sur le voile / Annuler ouvrent
  // alors une confirmation empilée (« Revenir à l'édition » la referme seule,
  // saisie intacte).
  const guard = makeDirtyGuard('Modifications non enregistrées sur ce MCP. Fermer sans enregistrer ?');
  body.addEventListener('input', guard.markDirty);
  body.addEventListener('change', guard.markDirty);
  const jsonEditor = createJsonEditor({
    value: JSON.stringify(m, null, 2), rows: 18, id: 'mcp-raw-json', ariaLabel: 'JSON complet du MCP',
    onChange: () => { jsonTouched = true; guard.markDirty(); },
    onSave: () => { if (!save.disabled) save.click(); },
    onValidChange: (ok) => { jsonValid = ok; updateSaveState(); },
  });
  body.querySelector('[data-editor-host]').appendChild(jsonEditor.el);

  // Construit la liste de checkboxes pour les workspaces ciblés
  const wsHost = body.querySelector('[data-name=workspaces]');
  const currentWs = new Set(m.workspaces || []);
  const allWs = STATE.workspaces || [];
  const allChecked = currentWs.has('*') || currentWs.has('all');

  const wsAllLabel = el('label', 'ws-check ws-check-all');
  wsAllLabel['innerHTML'] = `<input type="checkbox" data-ws-all ${allChecked ? 'checked' : ''}>
    <span><strong>★ Tous les workspaces</strong> <span class="dim">(${allWs.length})</span></span>`;
  wsHost.appendChild(wsAllLabel);

  if (!allWs.length) {
    wsHost.appendChild(el('div', 'dim', '<small>Aucun workspace défini — crée-en un d\'abord.</small>'));
  }

  for (const w of allWs) {
    const lbl = el('label', 'ws-check');
    const checked = allChecked || currentWs.has(w.id);
    lbl['innerHTML'] = `<input type="checkbox" data-ws="${escapeHtml(w.id)}" ${checked ? 'checked' : ''} ${allChecked ? 'disabled' : ''}>
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
      if (tab.dataset.tab === 'json') {
        if (!jsonTouched) jsonEditor.setValue(JSON.stringify(readFormPayload(), null, 2));
        else jsonEditor.refresh();
      }
      updateSaveState();
    });
  }

  const footer = [cancel];
  // En mode édition d'un MCP existant : bouton "Sauver comme recette"
  // permet de transformer une config qui marche en template réutilisable.
  if (isEdit) {
    const saveAsRecipe = btn('Sauver comme recette', 'btn-ghost', I.sparkle);
    saveAsRecipe.title = 'Crée une recette locale (template) à partir de ce MCP — réutilisable pour installer d\'autres instances avec d\'autres credentials';
    // Part de la SAISIE EN COURS (formulaire ou JSON brut), pas du MCP tel
    // qu'il était à l'ouverture. La modale MCP reste ouverte (l'éditeur de
    // recette s'empile dessus) : rien n'est perdu, la garde anti-perte
    // reste en place pour la fermeture.
    saveAsRecipe.addEventListener('click', () => {
      let current;
      if (body.querySelector('.tab.active').dataset.tab === 'json') {
        const check = jsonEditor.validate();
        if (!check.ok) { toastErr(`JSON invalide, ligne ${check.line} : ${check.msg}`); return; }
        current = check.value;
        if (!current || typeof current !== 'object' || Array.isArray(current)) {
          toastErr('Le JSON doit décrire un objet MCP'); return;
        }
      } else {
        current = readFormPayload();
      }
      modalSaveAsRecipe({ ...m, ...current, id: current.id || m.id });
    });
    footer.push(saveAsRecipe);
  }
  footer.push(save);
  const { close, requestClose } = openModal({
    title: isEdit ? `Modifier ${m.id}` : 'Nouveau MCP', body, footer, wide: true,
    closeOnBackdrop: true, confirmClose: guard.confirmClose,
  });
  guard.bind(close);
  cancel.addEventListener('click', requestClose);

  const parseKV = (text) => {
    const out = {};
    for (const line of text.split('\n').map(s => s.trim()).filter(Boolean)) {
      const [k, ...rest] = line.split('=');
      if (k) out[k.trim()] = rest.join('=').trim();
    }
    return out;
  };

  // Lit le formulaire (onglet « Formulaire ») et construit le payload MCP.
  const readFormPayload = () => {
    const get = (n) => body.querySelector(`[name=${n}]`).value;
    const argsRaw = get('args').split('\n').map(s => s.trim()).filter(Boolean);
    // Lit les workspaces depuis les checkboxes : ["*"] si "Tous", sinon liste des ids cochés
    const wsHost = body.querySelector('[data-name=workspaces]');
    const wsAllChecked = wsHost.querySelector('[data-ws-all]')?.checked;
    const wsRaw = wsAllChecked
      ? ['*']
      : Array.from(wsHost.querySelectorAll('[data-ws]:checked')).map(cb => cb.dataset.ws);
    return {
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
  };

  save.addEventListener('click', async () => {
    let payload;
    const activeTab = body.querySelector('.tab.active').dataset.tab;
    if (activeTab === 'json') {
      const check = jsonEditor.validate();
      if (!check.ok) { toastErr(`JSON invalide, ligne ${check.line} : ${check.msg}`); return; }
      payload = check.value;
    } else {
      payload = readFormPayload();
    }
    // Envoi effectif (factorisé : appelé directement ou après confirmation du lint).
    const doSave = async () => {
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
        guard.markSaved(); close(); STATE.loading = true; route();
      } catch (e) { toastErr(e.message); }
    };

    // Lint préventif (Lot B item 1) : char parasite après ${VAR} (1a) +
    // ${VAR} absent de .env.local (1b). WARN non-bloquant -> confirmation.
    const lintResult = lintInterpolation(mcpInterpolableStrings(payload), STATE.envKeys);
    if (lintResult.stuck.length || lintResult.missing.length) {
      confirmMcpLint(lintResult, doSave);
      return;
    }
    await doSave();
  });
}

// Modal de confirmation des warnings de lint MCP (item 1a/1b).
// Non-bloquant : laisse continuer après affichage des problèmes détectés.
// Toutes les valeurs dynamiques passent par escapeHtml (convention du fichier).
function confirmMcpLint(lintResult, onContinue) {
  const stuck = lintResult.stuck;
  const missing = lintResult.missing;
  const body = el('div');
  const parts = [];
  if (stuck.length) {
    const items = stuck.map(h =>
      `<li>caractère « <strong>${escapeHtml(h.char)}</strong> » accolé à <code class="mono">\${${escapeHtml(h.varName)}}</code> - probable typo</li>`
    ).join('');
    parts.push(`<p style="margin:0 0 6px"><strong>Caractère parasite après une variable</strong></p><ul style="margin:0 0 var(--sp-3);padding-left:18px;font-size:13px">${items}</ul>`);
  }
  if (missing.length) {
    const vars = missing.map(v => `<code class="mono">\${${escapeHtml(v)}}</code>`).join(', ');
    parts.push(`<p style="margin:0 0 6px"><strong>Variable(s) absente(s) de <code class="mono">.env.local</code></strong></p>
             <p style="margin:0 0 6px;font-size:13px">${vars} - ne seront pas substituées tant qu'elles ne sont pas définies (le MCP plantera à la sync si elles restent vides).</p>`);
  }
  parts.push(`<p style="margin:var(--sp-2) 0 0;font-size:12.5px;color:var(--text-muted)">Continuer l'enregistrement quand même ?</p>`);
  body.innerHTML = parts.join('');

  const cancel = btn('Annuler', 'btn-ghost');
  const cont = btn('Continuer', 'btn-primary');
  const footer = [cancel];
  if (missing.length) {
    const goEnv = btn('Configurer .env.local', 'btn-ghost', I.key);
    goEnv.addEventListener('click', () => { close(); location.hash = '#/tools'; });
    footer.push(goEnv);
  }
  footer.push(cont);
  const { close } = openModal({ title: 'Vérification avant enregistrement', body, footer });
  cancel.addEventListener('click', close);
  cont.addEventListener('click', async () => {
    close();
    await onContinue();
  });
}
