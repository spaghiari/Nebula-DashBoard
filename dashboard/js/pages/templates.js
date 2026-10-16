/* ================================================================
   Nebula - Page Templates (catalogue + edition + duplication)
   ----------------------------------------------------------------
   renderTemplates : cartes .xcard + filtres (recherche, qualite), aide
   repliable (refonte 2026-10, css/redesign.css section 10).
   templateCard : card par template avec qualite async.
   modalNewTemplate : 2 etapes (starter + meta).
   modalPreviewTemplateFile : apercu avec valeurs de test.
   modalEditTemplate : editeur tree + textarea + qualite refresh.
   modalDuplicateTemplate : duplication par source -> nouveau id.

   Dependances foundations : STATE, API, escapeHtml, el, btn, fmtBytes,
   I.*, setBreadcrumbs, setTopbarActions, openModal, toastOk, toastErr,
   confirmDialog, route.

   Ref : CM-2 batch 7, refactor 2026-05-13.
   ================================================================ */
'use strict';

async function renderTemplates() {
  setBreadcrumbs([{ label: 'Templates' }]);
  const newBtn = btn('Nouveau template', 'btn-primary', I.plus);
  newBtn.addEventListener('click', () => modalNewTemplate());
  setTopbarActions([newBtn]);

  const c = $('#content');
  c['innerHTML'] = '';
  const page = el('div', 'page');
  const tpls = STATE.templates || [];
  const nFiles = tpls.reduce((n, t) => n + (Number(t.file_count) || 0), 0);
  page.appendChild(el('div', 'page-header rise', `
    <div class="page-header-text">
      <h1 class="page-title">Templates</h1>
      <p class="page-subtitle">${tpls.length} modèle${tpls.length > 1 ? 's' : ''} (${nFiles} fichier${nFiles > 1 ? 's' : ''}) copié${tpls.length > 1 ? 's' : ''} à chaque nouveau workspace, <code class="mono">{{placeholders}}</code> remplacés. Clique <strong>Nouveau template</strong> pour démarrer.</p>
    </div>
  `));
  mountHelpLink(page, 'templates', 'les templates');

  // Note "Comment utiliser" (repliable)
  const help = el('details', 'help-card rise');
  help.style.setProperty('--i', 1);
  help.open = !tpls.length;  // ouvert par défaut si aucun template
  help['innerHTML'] = `
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
          <table class="help-ph">
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

  if (!tpls.length) {
    const empty = el('div', 'empty rise');
    empty.style.setProperty('--i', 2);
    empty['innerHTML'] = `
      <div class="empty-title">Aucun template</div>
      <p class="muted">Clique <strong>Nouveau template</strong> pour démarrer avec un starter pré-rempli.</p>
    `;
    const newCta = btn('Nouveau template', 'btn-primary', I.plus);
    newCta.style.marginTop = '12px';
    newCta.addEventListener('click', () => modalNewTemplate());
    empty.appendChild(newCta);
    page.appendChild(empty);
    c.appendChild(page);
    return;
  }

  // Barre de filtres : recherche + puces de qualite (alimentees au fil des
  // reponses /quality, une requete par carte comme avant).
  const toolbar = el('div', 'pg-filters rise');
  toolbar.style.setProperty('--i', 2);
  toolbar['innerHTML'] = `<span class="search-field">${I.search}<input class="input" type="search" placeholder="Nom, id, description…" aria-label="Filtrer les templates"></span>`;
  const searchInput = toolbar.querySelector('input');
  const chipGroup = el('span', 'pg-chipgroup');
  chipGroup.setAttribute('role', 'group');
  chipGroup.setAttribute('aria-label', 'Filtrer par qualité');
  const countEl = el('span', 'pg-count tab-num');
  countEl.setAttribute('aria-live', 'polite');
  toolbar.append(chipGroup, el('span', 'sp'), countEl);
  page.appendChild(toolbar);

  const quality = new Map();  // id -> 'ok' | 'info' | 'warn' | 'err'
  const QF = [['', 'Tous', () => true], ['ok', 'Qualité OK', l => l === 'ok' || l === 'info'], ['todo', 'À revoir', l => l === 'warn' || l === 'err']];
  let qualF = '';
  const drawChips = () => {
    chipGroup['innerHTML'] = QF
      .map(([v, l, fn]) => [v, l, v ? tpls.filter(t => quality.has(t.id) && fn(quality.get(t.id))).length : tpls.length])
      .filter(([v, , n]) => !v || n > 0 || v === qualF)
      .map(([v, l, n]) => `<button class="fchip" type="button" data-f="${v}" aria-pressed="${qualF === v}">${escapeHtml(l)} <b>${n}</b></button>`).join('');
  };
  chipGroup.addEventListener('click', (e) => {
    const b = e.target.closest('[data-f]');
    if (!b) return;
    qualF = b.dataset.f;
    drawChips(); applyFilter();
  });

  const grid = el('div', 'xgrid rise');
  grid.style.setProperty('--i', 3);
  const cards = tpls.map(t => {
    const card = templateCard(t, (level) => { quality.set(t.id, level); drawChips(); applyFilter(); });
    grid.appendChild(card);
    return [t, card];
  });
  const emptyEl = el('div', 'empty');
  emptyEl.hidden = true;
  emptyEl['innerHTML'] = `<div class="empty-title">Aucun template ne correspond</div><p class="muted">Modifie ta recherche ou tes filtres.</p> <button class="btn btn-sm" type="button" data-reset-filters>Tout afficher</button>`;
  emptyEl.querySelector('[data-reset-filters]').addEventListener('click', () => { searchInput.value = ''; qualF = ''; drawChips(); applyFilter(); });
  grid.appendChild(emptyEl);
  page.appendChild(grid);

  // Filtre en place (pas de reconstruction : la qualite deja chargee reste).
  function applyFilter() {
    const q = (searchInput.value || '').trim().toLowerCase();
    const fn = (QF.find(f => f[0] === qualF) || QF[0])[2];
    let n = 0;
    for (const [t, card] of cards) {
      const okQ = !qualF || (quality.has(t.id) && fn(quality.get(t.id)));
      const okS = !q || (`${t.id} ${t.label || ''} ${t.description || ''}`).toLowerCase().includes(q);
      card.hidden = !(okQ && okS);
      if (!card.hidden) n++;
    }
    emptyEl.hidden = n > 0;
    countEl.textContent = `${n} / ${tpls.length}`;
  }
  searchInput.addEventListener('input', debounce(applyFilter, 100));
  drawChips();
  applyFilter();
  renderModulesSection(page, 4);
  c.appendChild(page);
}

/* ---- Section « Modules » (overlays) -----------------------------------
   Une carte .xcard par overlay : emoji, libelle, description, usage (actif
   sur N / M workspaces, hovercard), prerequis, features du marker, Dossier,
   « Activer sur un workspace... » (selecteur puis modale d'activation de
   app.js). Usage : GET /api/overlays -> usage {overlay_id: [ws_id]}. */
function renderModulesSection(page, i) {
  const overlays = sortOverlays(STATE.overlays || []);
  if (!overlays.length) return;
  const sec = el('section', 'mods-sec rise');
  sec.style.setProperty('--i', i);
  sec['innerHTML'] = `
    <div class="page-header-text" style="margin-bottom:var(--gap)">
      <h2 class="mods-title">Modules</h2>
      <p class="page-subtitle">${overlays.length} module${overlays.length > 1 ? 's' : ''}. Un module se pose <strong>par-dessus</strong> un template (à la création du workspace ou plus tard, onglet Configuration) : il n'écrase aucun fichier déjà présent et se ré-applique sans risque.</p>
    </div>`;
  const grid = el('div', 'xgrid');
  const byId = new Map(overlays.map(o => [o.id, o]));
  const cards = new Map();
  const usage = {};  // overlay_id -> [ws_id], rempli par refreshUsage
  for (const ov of overlays) {
    const card = moduleCard(ov, byId, () => usage[ov.id] || [], () => refreshUsage());
    cards.set(ov.id, card);
    grid.appendChild(card);
  }
  sec.appendChild(grid);
  page.appendChild(sec);

  // Usage par module (une requete, mise a jour en place).
  const refreshUsage = async () => {
    try {
      const r = await API.get('/api/overlays');
      STATE.overlays = r.overlays || STATE.overlays;
      Object.assign(usage, r.usage || {});
      for (const [id, card] of cards) {
        const slot = card.querySelector('[data-usage]');
        if (slot) slot.replaceChildren(moduleUsagePill(usage[id] || []));
      }
    } catch (e) {
      for (const card of cards.values()) {
        const slot = card.querySelector('[data-usage]');
        if (slot) slot['innerHTML'] = `<span class="pill warn" title="${escapeHtml(e.message)}">usage inconnu</span>`;
      }
    }
  };
  refreshUsage();
}

// Pill « actif sur N / M workspaces » + hovercard listant les workspaces
// (meme donnee que hcAttrs, posee directement en data-hc).
function moduleUsagePill(wsIds) {
  const total = (STATE.workspaces || []).length;
  const n = wsIds.length;
  const pill = el('span', 'pill ' + (n ? 'ok' : 'mute'), `actif sur ${n} / ${total} workspace${total > 1 ? 's' : ''}`);
  if (n) { pill.dataset.hc = JSON.stringify([{ title: 'Actif sur', ws: wsIds }]); pill.tabIndex = 0; }
  return pill;
}

function moduleCard(ov, byId, getUsage, onChange) {
  const card = el('article', 'xcard module-card');
  card.dataset.overlay = ov.id;
  const reqs = (ov.requires || []).map(r => (byId.get(r) || {}).label || r);
  const feats = (ov.features || []).filter(f => f && f.title);
  card['innerHTML'] = `
    <div class="top">
      <span class="gem" style="--h:${nameHue(ov.label || ov.id)}" aria-hidden="true">${escapeHtml(ov.emoji || '🧩')}</span>
      <div class="xt">
        <h3>${escapeHtml(ov.label || ov.id)}</h3>
        <div class="msub"><small>${escapeHtml(ov.id)}</small><span class="chip">${ov.file_count || 0} fichier${(ov.file_count || 0) > 1 ? 's' : ''}</span>${(ov.generators || []).includes('team_agents') ? `<span class="chip">${(ov.agents || []).length} agents</span>` : ''}</div>
      </div>
      <div class="xstate"><span data-usage><span class="pill mute">usage…</span></span></div>
    </div>
    ${reqs.length ? `<div class="xmeta"><span>${I.alert} Requiert <b>${escapeHtml(reqs.join(', '))}</b> (activé d'abord, automatiquement à la création)</span></div>` : ''}
    <p class="xdesc ${ov.description ? '' : 'none'}">${escapeHtml(ov.description || 'Pas de description.')}</p>
    ${feats.length ? `<ul class="mod-feat compact">${feats.map(f => `<li><span class="fi">${overlayFeatureIcon(f.icon)}</span><span><b>${escapeHtml(f.title)}</b></span></li>`).join('')}</ul>` : ''}
  `;
  const actions = el('div', 'xfoot');
  const open = btn('Dossier', 'btn-sm btn-ghost', I.folder);
  open.title = "Ouvrir le dossier du module dans l'explorateur";
  open.addEventListener('click', async () => {
    try { const r = await API.post('/api/open', { target: `template:${ov.dir_id || ov.id}` }); toastOk(r.message || 'Ouvert'); }
    catch (e) { toastErr(e.message); }
  });
  const act = btn('Activer sur un workspace…', 'btn-sm btn-primary', I.plus);
  act.addEventListener('click', () => modalActivateModuleOn(ov, getUsage(), onChange));
  actions.append(open, act);
  card.appendChild(actions);
  return card;
}

// Selecteur de workspace (parmi ceux ou le module n'est pas actif), puis
// modale d'activation existante (modalApplyOverlay, app.js). Le prerequis
// inactif est signale et propose en premier.
function modalActivateModuleOn(ov, activeOn, onChange) {
  const candidates = (STATE.workspaces || []).filter(w => !activeOn.includes(w.id) && w.path_exists !== false);
  const body = el('div');
  if (!candidates.length) {
    body['innerHTML'] = `<p class="muted">Ce module est déjà actif sur tous les workspaces${(STATE.workspaces || []).length ? '' : ' (aucun workspace)'}.</p>`;
    const close1 = btn('Fermer', 'btn-ghost');
    const { close } = openModal({ title: `Activer ${ov.label || ov.id}`, body, footer: close1 });
    close1.addEventListener('click', close);
    return;
  }
  body['innerHTML'] = `
    <div class="muted" style="font-size:12px;margin-bottom:10px">${escapeHtml(ov.emoji || '🧩')} <strong>${escapeHtml(ov.label || ov.id)}</strong> : ${escapeHtml(ov.description || '')}</div>
    <div class="field">
      <label class="field-label">Workspace</label>
      <select class="select" name="ws">${candidates.map(w => `<option value="${escapeHtml(w.id)}">${escapeHtml(w.emoji || '📁')} ${escapeHtml(w.label || w.id)} (${escapeHtml(w.id)})</option>`).join('')}</select>
      <div class="muted" style="font-size:11px;margin-top:4px" data-req-note></div>
    </div>`;
  const sel = body.querySelector('[name=ws]');
  const note = body.querySelector('[data-req-note]');
  const reqs = ov.requires || [];
  const missingFor = (wsId) => reqs.filter(r => !wsHasOverlay(wsId, r));
  const syncNote = () => {
    const miss = missingFor(sel.value);
    note.textContent = miss.length
      ? `Prérequis inactif sur ce workspace : ${miss.map(r => ((STATE.overlays || []).find(o => o.id === r) || {}).label || r).join(', ')}. Il sera proposé en premier.`
      : (reqs.length ? 'Prérequis actif sur ce workspace.' : '');
  };
  sel.addEventListener('change', syncNote);
  syncNote();
  const cancel = btn('Annuler', 'btn-ghost');
  const next = btn('Continuer', 'btn-primary', I.right);
  const { close } = openModal({ title: `Activer ${ov.label || ov.id}`, body, footer: [cancel, next] });
  cancel.addEventListener('click', close);
  next.addEventListener('click', () => {
    const wsId = sel.value;
    close();
    const miss = missingFor(wsId);
    const onDone = () => {
      // Etat global des overlays actifs (badges, onglets) + usage des cartes.
      API.get(`/api/workspaces/${wsId}/overlays`).then(r => {
        const act = (r.overlays || []).filter(o => o.active).map(o => o.id);
        if (act.length) STATE.overlaysActive[wsId] = act; else delete STATE.overlaysActive[wsId];
      }).catch(() => {}).finally(() => { if (onChange) onChange(); });
    };
    if (miss.length) {
      const req = (STATE.overlays || []).find(o => o.id === miss[0]);
      if (req) { modalApplyOverlay(wsId, { ...req, active: false }, null, { then: ov, onDone }); return; }
    }
    modalApplyOverlay(wsId, { ...ov, active: false }, null, { onDone });
  });
}

function templateCard(t, onQuality) {
  const card = el('article', 'xcard template-card');
  // Le starter "Standard" est mis en avant si présent
  const isRecommended = t.id === 'standard';
  const n = Number(t.file_count) || 0;
  card['innerHTML'] = `
    <div class="top">
      <span class="gem" style="--h:${nameHue(t.label || t.id)}" aria-hidden="true">${escapeHtml(t.emoji || '📦')}</span>
      <div class="xt">
        <h3 class="template-name">${escapeHtml(t.label || t.id)}</h3>
        <div class="msub"><small>${escapeHtml(t.id)}</small><span class="chip">${n} fichier${n > 1 ? 's' : ''}</span></div>
      </div>
      <div class="xstate">
        ${isRecommended ? '<span class="pill accent">Recommandé</span>' : ''}
        <span data-quality><span class="pill mute">qualité…</span></span>
      </div>
    </div>
    <p class="xdesc ${t.description ? '' : 'none'}">${escapeHtml(t.description || 'Pas de description.')}</p>
  `;
  const actions = el('div', 'xfoot');
  const ed = btn('Éditer', 'btn-sm btn-ghost xfoot-main', I.edit);
  ed.addEventListener('click', () => modalEditTemplate(t.id));
  const open = btn('Dossier', 'btn-sm btn-ghost', I.folder);
  open.title = 'Ouvrir dans l\'explorateur';
  open.addEventListener('click', async () => {
    try { const r = await API.post('/api/open', { target: `template:${t.id}` }); toastOk(r.message || 'Ouvert'); }
    catch (e) { toastErr(e.message); }
  });
  const dup = btn('Dupliquer', 'btn-sm btn-ghost', I.copy);
  dup.addEventListener('click', () => modalDuplicateTemplate(t));
  const rm = btn('', 'btn-sm btn-ghost btn-icon-only btn-danger', I.trash);
  rm.title = 'Supprimer';
  rm.setAttribute('aria-label', `Supprimer le template ${t.label || t.id}`);
  rm.addEventListener('click', () => confirmDialog(`Supprimer le template ${t.id} ?`, async () => {
    try {
      await API.del(`/api/templates/${t.id}`);
      toastOk('Supprimé');
      STATE.templates = STATE.templates.filter(x => x.id !== t.id);
      route({ silent: true });
    }
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
    let cls, level, summary;
    if (hasErr) { cls = 'err'; level = 'err'; summary = `${sugs.length} problème${sugs.length > 1 ? 's' : ''}`; }
    else if (hasWarn) { cls = 'warn'; level = 'warn'; summary = `${sugs.length} suggestion${sugs.length > 1 ? 's' : ''}`; }
    else if (hasInfo) { cls = 'mute'; level = 'info'; summary = `${sugs.length} info${sugs.length > 1 ? 's' : ''}`; }
    else { cls = 'ok'; level = 'ok'; summary = 'Qualité OK'; }
    qualHost['innerHTML'] = `<span class="pill ${cls}" title="${escapeHtml(sugs.map(s => '• ' + s.msg).join('\n') || 'Aucune suggestion')}">${summary}</span>`;
    if (onQuality) onQuality(level);
  }).catch(() => {
    qualHost['innerHTML'] = '';
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

  body['innerHTML'] = `
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
    card['innerHTML'] = `
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
    body['innerHTML'] = `<div class="error-box">${escapeHtml(data.error || 'Fichier binaire')}</div>`;
  } else {
    const vars = data.test_vars || {};
    const varList = Object.entries(vars).map(([k, v]) => `<code class="mono">{{${k}}}</code> → <code class="mono">${escapeHtml(v)}</code>`).join(' · ');
    body['innerHTML'] = `
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
  body['innerHTML'] = `<div class="page-loader"><div class="spinner"></div><span>Chargement du template…</span></div>`;
  const closeBtn = btn('Fermer', 'btn-ghost');
  // Garde anti-perte a la fermeture (croix, Echap, Fermer) : fichier courant
  // modifie non enregistre OU meta (emoji/label/description) non enregistree.
  // Etats `dirty` / `metaDirty` declares plus bas, lus au moment de fermer.
  let dirty = false;
  let metaDirty = false;
  const guard = makeDirtyGuard('Modifications non enregistrées dans ce template. Fermer sans enregistrer ?',
    { isDirty: () => dirty || metaDirty });
  const { close, requestClose } = openModal({
    title: `Template · ${tplId}`, body, footer: closeBtn, wide: true, confirmClose: guard.confirmClose,
  });
  guard.bind(close);
  closeBtn.addEventListener('click', requestClose);

  let detail;
  try { detail = await API.get(`/api/templates/${tplId}`); }
  catch (e) { body['innerHTML'] = `<div class="error-box">${escapeHtml(e.message)}</div>`; return; }

  body['innerHTML'] = `
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
  for (const n of ['emoji', 'label', 'description']) {
    body.querySelector(`[name=${n}]`).addEventListener('input', () => { metaDirty = true; });
  }
  body.querySelector('[data-save-meta]').addEventListener('click', async () => {
    const get = n => body.querySelector(`[name=${n}]`).value.trim();
    try {
      await API.post(`/api/templates/${tplId}/meta`, { label: get('label'), description: get('description'), emoji: get('emoji') });
      metaDirty = false;
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
      qualHost['innerHTML'] = `
        <details class="callout ${cls}" style="margin-bottom:var(--sp-3)" ${openByDefault ? 'open' : ''}>
          <summary style="cursor:pointer;font-weight:600">${icon} Conseils & qualité — ${summary}</summary>
          ${lines ? `<ul class="help-list" style="margin:8px 0 0">${lines}</ul>` : ''}
          ${placeholders}
        </details>
      `;
    } catch { qualHost['innerHTML'] = ''; }
  };
  refreshQuality();

  const treeList = body.querySelector('.tpl-tree-list');
  const pane = body.querySelector('.tpl-pane');
  let files = detail.files.slice();
  let currentPath = null;
  // Garde anti-perte de saisie (`dirty`, declare en tete de fonction) : passe
  // a true quand l'editeur est modifie, remis a false au chargement d'un
  // fichier et apres sauvegarde reussie.
  let curEditor = null;   // editeur du fichier courant (mountFileEditor)

  const renderTree = () => {
    treeList['innerHTML'] = '';
    if (!files.length) {
      treeList['innerHTML'] = '<div class="dim" style="padding:var(--sp-3);font-size:12px">Aucun fichier</div>';
      return;
    }
    files.sort((a, b) => a.path.localeCompare(b.path));
    for (const f of files) {
      const item = el('div', 'tpl-tree-item' + (f.path === currentPath ? ' is-active' : ''));
      item['innerHTML'] = `
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
            if (currentPath === f.path) { currentPath = null; dirty = false; pane['innerHTML'] = '<div class="tpl-pane-empty">Sélectionne un fichier.</div>'; }
            renderTree(); toastOk('Supprimé');
          } catch (err) { toastErr(err.message); }
        }, { danger: true });
      });
      item.appendChild(rm);
      treeList.appendChild(item);
    }
  };

  const openFile = async (path) => {
    // Confirmation si on quitte un fichier modifie non sauvegarde.
    if (dirty && path !== currentPath) {
      const ok = await new Promise((resolve) => {
        confirmDialog('Modifications non sauvegardées sur le fichier courant. Changer de fichier sans enregistrer ?',
          () => resolve(true), { danger: true, confirmLabel: 'Changer de fichier' });
      });
      if (!ok) return;
    }
    dirty = false;
    currentPath = path;
    renderTree();
    pane['innerHTML'] = `<div class="page-loader"><div class="spinner"></div></div>`;
    let data;
    try { data = await API.get(`/api/templates/${tplId}/file?path=${encodeURIComponent(path)}`); }
    catch (e) { pane['innerHTML'] = `<div class="error-box">${escapeHtml(e.message)}</div>`; return; }
    if (data.binary || data.error) {
      pane['innerHTML'] = `<div class="error-box">${escapeHtml(data.error || 'Fichier binaire non éditable')}</div>`;
      return;
    }
    pane['innerHTML'] = `
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
    const saveBtn = pane.querySelector('[data-save-file]');
    // .json -> editeur JSON non bloquant (placeholders {{...}}) ; Ctrl+S.
    if (curEditor) curEditor.destroy();
    const editor = mountFileEditor(ta, path, {
      onChange: () => { dirty = true; },
      onSave: () => saveBtn.click(),
    });
    curEditor = editor;
    editor.focus();
    saveBtn.addEventListener('click', () => withBusy(saveBtn, async () => {
      try {
        const r = await API.post(`/api/templates/${tplId}/file`, { path, content: editor.getValue() });
        const f = files.find(x => x.path === path);
        if (f) f.size = r.size;
        dirty = false;
        renderTree();
        refreshQuality();
        toastOk('Enregistré');
        // JSON accepté malgré des placeholders hors guillemets : le serveur
        // prévient que la copie dans un workspace sera invalide si non remplacé.
        if (r.warning) toast(r.warning, 'info', 12000);
      } catch (e) { toastErr(e.message); }
    }));
    pane.querySelector('[data-preview-file]').addEventListener('click', async () => {
      try {
        const r = await API.get(`/api/templates/${tplId}/preview?path=${encodeURIComponent(path)}`);
        modalPreviewTemplateFile(path, r);
      } catch (e) { toastErr(e.message); }
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
    fbody['innerHTML'] = `
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
  body['innerHTML'] = `
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
