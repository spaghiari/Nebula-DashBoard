/* ================================================================
   Nebula - Page Skills (catalogue + library + edition)
   ----------------------------------------------------------------
   renderSkills : page Skills avec 2 onglets (library + global).
   librarySkillCard / skillCard : cards des deux sections.
   modalDistributeSkill : copier un skill library vers N workspaces.
   modalAddSkillFromLibrary : ajouter au workspace courant.
   modalEditSkillFiles : navigateur de fichiers partagé (global/workspace/library).
   modalDeleteLibrarySkill : suppression library.
   modalCopySkillToWorkspace : copier global -> workspace.
   modalEditSkillFiles : editeur tree + textarea du dossier skill.

   Dependances foundations : STATE, API, escapeHtml, el, btn, fmtBytes,
   I.*, setBreadcrumbs, setTopbarActions, openModal, toastOk, toastErr,
   confirmDialog, route.
   Forward-refs (app.js) : modalNewSkill, modalEditSkill,
   modalImportSkillsFromGitHub, renderGlobalSkills.

   Ref : CM-2 batch 8, refactor 2026-05-13.
   ================================================================ */
'use strict';

async function renderSkills() {
  setBreadcrumbs([{ label: 'Skills' }]);
  const newBtn = btn('Nouveau skill', 'btn-primary', I.plus);
  newBtn.addEventListener('click', () => modalNewSkill());
  const importBtn = btn('Importer GitHub', 'btn-ghost', '📥');
  importBtn.title = 'Importer un skill depuis un repo GitHub (méthode manuelle automatisée)';
  importBtn.addEventListener('click', () => modalImportSkillsFromGitHub());
  setTopbarActions([importBtn, newBtn]);

  const c = $('#content');
  c['innerHTML'] = '';
  const page = el('div', 'page');

  page.appendChild(el('div', 'page-header', `
    <div class="page-header-text">
      <div class="page-eyebrow"><span class="index">04.</span><span>Capacités</span></div>
      <h1 class="page-title">Skills</h1>
      <p class="page-subtitle">Modules de compétences activables par Claude — globaux ou scopés à un workspace.</p>
    </div>
  `));
  mountHelpLink(page, 'skills-plugins', 'les skills');

  // Help collapsible
  const help = el('details', 'help-card');
  help['innerHTML'] = `
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
  toolbar['innerHTML'] = `
    <input class="input input-search" name="filter" placeholder="Rechercher un skill…" style="flex:1;min-width:240px;max-width:480px">
    <span class="dim mono" style="font-size:11px;letter-spacing:0.1em" data-count></span>
  `;
  page.appendChild(toolbar);

  // Banner migration : bibliothèque vide mais des skills existent ailleurs
  const library = STATE.skillsLibrary || [];
  if (!library.length && (STATE.skills || []).length) {
    const banner = el('div', 'callout callout-info');
    banner['innerHTML'] = `
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
    grid['innerHTML'] = '';
    if (!filtered.length) {
      const empty = el('div', 'empty');
      if (filter) {
        empty['innerHTML'] = `<div class="empty-title">Aucun skill ne correspond</div><p class="muted">Modifie ton filtre.</p>`;
      } else {
        empty['innerHTML'] = `<div class="empty-title">Bibliothèque vide</div><p class="muted">Crée un skill, ou importe-en depuis GitHub avec le bouton « Importer GitHub ».</p>`;
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

  // Lot E item 5 : chip d'origine GitHub pour les skills importés.
  // s.origin = {repo:"owner/repo", commit:"<sha>", source_path, branch}.
  // Exposé par list_library (lit .nebula-origin.json). Le sha est tronqué à 7.
  let originChip = '';
  if (s.origin && s.origin.repo) {
    const repo = s.origin.repo;
    const sha = s.origin.commit ? String(s.origin.commit).slice(0, 7) : '';
    const label = sha ? `GitHub: ${repo}@${sha}` : `GitHub: ${repo}`;
    const titleParts = [`Importé depuis ${repo}`];
    if (s.origin.branch && s.origin.branch !== 'default') titleParts.push(`branche ${s.origin.branch}`);
    if (s.origin.source_path) titleParts.push(`chemin ${s.origin.source_path}`);
    if (s.origin.imported_at) titleParts.push(`le ${s.origin.imported_at}`);
    originChip = `<span class="chip chip-origin" title="${escapeHtml(titleParts.join(' · '))}">${escapeHtml(label)}</span>`;
  }

  card['innerHTML'] = `
    <div class="skill-card-header">
      <div class="skill-icon">${I.sparkle}</div>
      <div style="flex:1;min-width:0">
        <h3 class="skill-name">${escapeHtml(s.name || s.id)}</h3>
        <div class="dim mono" style="font-size:11px;margin-top:2px">${escapeHtml(s.id)}</div>
      </div>
      ${badge}
    </div>
    <p class="skill-desc">${escapeHtml(s.description || 'Pas de description')}</p>
    ${originChip ? `<div class="skill-origin">${originChip}</div>` : ''}
    ${distributed.length ? `<div class="skill-ws-list">${distributed.map(t => `<span class="chip">${escapeHtml(distLabel(t))}</span>`).join('')}</div>` : ''}
  `;
  const actions = el('div', 'skill-actions');
  const dist = btn('Distribuer', 'btn-sm btn-primary', '📤');
  dist.addEventListener('click', () => modalDistributeSkill(s));
  const ed = btn('Éditer', 'btn-sm btn-ghost', I.edit);
  // Ouvre le navigateur de fichiers complet (SKILL.md + annexes), même UI que
  // les skills global/workspace. Remplace l'ancien textarea SKILL.md-seul.
  ed.addEventListener('click', () => modalEditSkillFiles('library', s.id));
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
  body['innerHTML'] = `
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
    wsHost['innerHTML'] = '<p class="muted">Aucun workspace.</p>';
  } else {
    for (const w of wsList) {
      const t = `workspace:${w.id}`;
      const lbl = el('label', 'ws-check');
      lbl.style.cssText = 'display:flex;gap:8px;align-items:center;padding:6px 10px;border:1px solid var(--border);border-radius:6px;margin-bottom:4px';
      lbl['innerHTML'] = `
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
      confirmDialog(`Retirer ce skill de ${willRemove.length} emplacement(s) ?`, apply, { danger: true, confirmLabel: 'Retirer' });
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
    body['innerHTML'] = `<p class="muted" style="margin-top:0">Ta bibliothèque est vide. Crée un skill depuis l'onglet <strong>Skills</strong> ou importe-en depuis GitHub.</p>`;
    const c = btn('Fermer', 'btn-ghost');
    const { close } = openModal({ title: 'Ajouter depuis le magasin', body, footer: c });
    c.addEventListener('click', close);
    return;
  }
  body['innerHTML'] = `
    <p class="muted" style="margin-top:0">Coche les skills à installer dans ce workspace.</p>
    <div class="recipes-grid" data-list></div>
  `;
  const list = body.querySelector('[data-list]');
  if (!candidates.length) {
    list['innerHTML'] = '<p class="muted">Tous les skills de la bibliothèque sont déjà installés ici.</p>';
  }
  for (const s of candidates) {
    const card = el('label', 'recipe-card');
    card.style.cursor = 'pointer';
    card['innerHTML'] = `
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

function modalDeleteLibrarySkill(s) {
  const distributed = (s.distributed_to || []).length;
  const body = el('div');
  body['innerHTML'] = `
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
  card['innerHTML'] = `
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
    body['innerHTML'] = '<p class="muted">Aucun workspace disponible.</p>';
    const close = btn('Fermer', 'btn-ghost');
    const { close: doClose } = openModal({ title: 'Copier dans un workspace', body, footer: close });
    close.addEventListener('click', doClose);
    return;
  }
  body['innerHTML'] = `
    <p class="muted" style="margin-top:0">Choisis le ou les workspaces où copier <strong class="mono">${escapeHtml(skill.id)}</strong> :</p>
    <div class="ws-pick-list"></div>
  `;
  const list = body.querySelector('.ws-pick-list');
  for (const w of STATE.workspaces) {
    const item = el('label', 'wizard-item');
    item['innerHTML'] = `
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

// Navigateur de fichiers d'un skill, partagé par les scopes global / workspace
// ET bibliothèque ('library'). Seules les URLs diffèrent : la bibliothèque a son
// propre préfixe `/api/skills-library/<name>/…`, les autres `/api/skills/<scope>/<name>/…`.
function skillFileUrls(scope, name) {
  if (scope === 'library') {
    const base = `/api/skills-library/${name}`;
    return {
      detail: `${base}/detail`,
      file: (p) => `${base}/file?path=${encodeURIComponent(p)}`,
      filePost: `${base}/file`,
    };
  }
  const base = `/api/skills/${scope}/${name}`;
  return {
    detail: base,
    file: (p) => `${base}/file?path=${encodeURIComponent(p)}`,
    filePost: `${base}/file`,
  };
}

async function modalEditSkillFiles(scope, name) {
  const U = skillFileUrls(scope, name);
  const body = el('div');
  body['innerHTML'] = `<div class="page-loader"><div class="spinner"></div><span>Chargement du skill…</span></div>`;
  const closeBtn = btn('Fermer', 'btn-ghost');
  const titleSuffix = scope === 'library' ? ' (bibliothèque)' : '';
  // Garde anti-perte : fichier courant modifie et non enregistre -> la
  // fermeture (croix, Echap, Fermer) demande confirmation.
  let dirty = false;
  const guard = makeDirtyGuard('Modifications non enregistrées dans ce skill. Fermer sans enregistrer ?',
    { isDirty: () => dirty });
  const { close, requestClose } = openModal({
    title: `Skill · ${name}${titleSuffix}`, body, footer: closeBtn, wide: true, confirmClose: guard.confirmClose,
  });
  guard.bind(close);
  closeBtn.addEventListener('click', requestClose);

  let detail;
  try { detail = await API.get(U.detail); }
  catch (e) { body['innerHTML'] = `<div class="error-box">${escapeHtml(e.message)}</div>`; return; }

  body['innerHTML'] = `
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
  let curEditor = null;          // editeur du fichier courant (mountFileEditor)

  const renderTree = () => {
    treeList['innerHTML'] = '';
    if (!files.length) {
      treeList['innerHTML'] = '<div class="dim" style="padding:var(--sp-3);font-size:12px">Aucun fichier</div>';
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
      item['innerHTML'] = `
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
              await API.del(U.file(f.path));
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
    // Changer de fichier avec des modifications non enregistrees : confirmer.
    if (dirty && path !== currentPath) {
      const ok = await new Promise((resolve) => {
        confirmDialog('Modifications non sauvegardées sur le fichier courant. Changer de fichier sans enregistrer ?',
          () => resolve(true), { danger: true, confirmLabel: 'Changer de fichier', onClose: () => resolve(false) });
      });
      if (!ok) return;
    }
    dirty = false;
    currentPath = path;
    renderTree();
    pane['innerHTML'] = `<div class="page-loader"><div class="spinner"></div></div>`;
    let data;
    try { data = await API.get(U.file(path)); }
    catch (e) { pane['innerHTML'] = `<div class="error-box">${escapeHtml(e.message)}</div>`; return; }
    if (data.binary || data.error) {
      pane['innerHTML'] = `<div class="error-box">${escapeHtml(data.error || 'Fichier binaire non éditable')}</div>`;
      return;
    }
    pane['innerHTML'] = `
      <div class="tpl-pane-header">
        <span class="mono" style="font-size:13px;flex:1">${escapeHtml(path)}</span>
        <span class="dim mono" style="font-size:11px">${fmtBytes(data.size)}</span>
        <button class="btn btn-sm btn-primary" data-save-file>Enregistrer</button>
      </div>
      <textarea class="textarea textarea-code tpl-editor-textarea" spellcheck="false"></textarea>
    `;
    const ta = pane.querySelector('textarea');
    ta.value = data.content;
    const saveBtn = pane.querySelector('[data-save-file]');
    // .json -> editeur JSON non bloquant (placeholders {{...}}) ; Ctrl+S.
    if (curEditor) curEditor.destroy();
    const editor = mountFileEditor(ta, path, {
      onChange: () => { dirty = true; },
      onSave: () => saveBtn.click(),
    });
    curEditor = editor;
    editor.focus();
    saveBtn.addEventListener('click', async () => {
      try {
        const r = await API.post(U.filePost, { path, content: editor.getValue() });
        const f = files.find(x => x.path === path);
        if (f) f.size = r.size;
        if (currentPath === path) dirty = false;
        renderTree(); toastOk('Enregistré');
      } catch (e) { toastErr(e.message); }
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
    fbody['innerHTML'] = `
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
        const r = await API.post(U.filePost, { path, content });
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
