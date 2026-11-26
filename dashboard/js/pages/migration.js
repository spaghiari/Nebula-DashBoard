/* ================================================================
   Nebula - Page Migration (export / import de tout l'environnement)
   ----------------------------------------------------------------
   renderMigration : deux blocs cote a cote.
   - Exporter : taille estimee par categorie (job `estimate`), choix des
     workspaces, phrase de passe + confirmation, progression, bilan.
   - Importer : choix de l'archive, phrase de passe, APERCU en lecture seule
     (job `preview`) avec remappage des chemins et decision explicite sur
     chaque conflit, puis execution (job `import`, plan_id frais).
   Toutes les operations sont des jobs asynchrones (dashcore/api_migration.py) :
   POST /api/migration/jobs puis GET /api/migration/jobs/<id>.

   La phrase de passe ne vit que dans les champs de saisie de la page : jamais
   en STATE, localStorage, URL ni journal ; les champs sont vides apres succes.

   Dependances foundations : API, escapeHtml, el, btn, withBusy, fmtNum,
   fmtDateTime, wsGem, I.*, setBreadcrumbs, setTopbarActions, toastOk, toastErr,
   confirmDialog, registerPagePoller.
   Forward-refs (app.js) : folderPickerSupported.
   ================================================================ */
'use strict';

const MIG_PHASE_LABELS = {
  start: 'Démarrage', inventory: 'Inventaire des fichiers', write: 'Chiffrement et écriture',
  verify: "Vérification de l'archive", plan: "Construction de l'aperçu",
  extract: 'Préparation des fichiers', apply: 'Application',
};
const MIG_COLORS = ['var(--seg-1)', 'var(--seg-3)', 'var(--seg-4)', 'var(--info)', 'var(--text-dim)'];
const MIG_ORIGIN_LABELS = {
  rule: 'chemin remappé', same: 'même chemin', fallback: 'dossier de repli',
  user: 'chemin choisi', workspaces: 'dossier workspaces',
};

function migBytes(n) {
  n = Number(n) || 0;
  const f = (v, d) => v.toLocaleString('fr-FR', { maximumFractionDigits: d });
  if (n < 1024) return `${n} o`;
  if (n < 1048576) return `${f(n / 1024, 1)} Kio`;
  if (n < 1073741824) return `${f(n / 1048576, 1)} Mio`;
  return `${f(n / 1073741824, 2)} Gio`;
}

const migSleep = (ms) => new Promise((r) => setTimeout(r, ms));

function migPlural(n, one, many) { return `${fmtNum(n)} ${n > 1 ? many : one}`; }

// Lance un job puis l'interroge jusqu'a sa fin. Rend le dernier etat, ou null
// si la page a ete quittee (le job continue cote serveur).
async function migRunJob(body, { onProgress, alive, holder }) {
  const st = await API.postStatus('/api/migration/jobs', body);
  if (!st.ok) {
    const e = new Error(st.data.error || `HTTP ${st.status}`);
    e.code = st.data.error_code;
    throw e;
  }
  const id = st.data.job_id;
  if (holder) holder.id = id;
  for (;;) {
    await migSleep(350);
    if (alive && !alive()) return null;
    const snap = await API.get(`/api/migration/jobs/${id}`);
    if (onProgress) onProgress(snap);
    if (snap.status !== 'running') {
      if (holder) holder.id = null;
      return snap;
    }
  }
}

function migJobError(snap) {
  const e = new Error(snap.error || 'Opération échouée');
  e.code = snap.error_code;
  e.snap = snap;
  return e;
}

// Bloc de progression : phase, pourcentage, libelle courant, annulation.
function migProgressBox(holder) {
  const box = el('div', 'mig-run', `
    <div class="mig-run-top"><span data-phase>Démarrage…</span><span data-pct class="mono"></span></div>
    <div class="mig-progress" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-label="Progression"><div class="mig-fill" data-fill></div></div>
    <div class="mig-run-label mono" data-label></div>
    <div class="mig-run-actions"></div>`);
  const cancel = btn('Annuler', 'btn', I.stop);
  cancel.addEventListener('click', () => {
    if (holder.id) API.post(`/api/migration/jobs/${holder.id}/cancel`).catch(() => {});
    cancel.disabled = true;
  });
  box.querySelector('.mig-run-actions').appendChild(cancel);
  const bar = box.querySelector('.mig-progress');
  const fill = box.querySelector('[data-fill]');
  const update = (snap) => {
    box.querySelector('[data-phase]').textContent = MIG_PHASE_LABELS[snap.phase] || snap.phase;
    box.querySelector('[data-label]').textContent = snap.label || '';
    const pct = snap.total > 0 ? Math.min(100, Math.floor((100 * snap.done) / snap.total)) : null;
    bar.classList.toggle('is-indet', pct === null);
    box.querySelector('[data-pct]').textContent = pct === null ? `${Math.round(snap.elapsed)} s` : `${pct} %`;
    if (pct !== null) { fill.style.width = `${pct}%`; bar.setAttribute('aria-valuenow', String(pct)); }
    else { bar.removeAttribute('aria-valuenow'); }
  };
  return { box, cancel, update };
}

function migCallout(kind, html) {
  const icon = kind === 'err' ? I.alert : kind === 'warn' ? I.alert : I.info;
  const cls = kind === 'err' ? 'callout callout-err' : kind === 'warn' ? 'callout callout-warn' : 'callout callout-info';
  return el('div', cls, `${icon}<div>${html}</div>`);
}

function migList(items) {
  return `<ul class="mig-ul">${items.map((x) => `<li>${escapeHtml(x)}</li>`).join('')}</ul>`;
}

async function renderMigration() {
  setBreadcrumbs([{ label: 'Migration' }]);
  setTopbarActions([]);
  const c = $('#content');
  c['innerHTML'] = '';
  const page = el('div', 'page');
  page.appendChild(el('div', 'page-header rise', `
    <div class="page-header-text">
      <h1 class="page-title">Migration</h1>
      <p class="page-subtitle">Emporte tout ton environnement Nebula dans une archive chiffrée par une phrase de passe, puis retrouve-le sur une autre machine ou après une réinstallation.</p>
    </div>
  `));
  c.appendChild(page);
  let info;
  try { info = await API.get('/api/migration/info'); }
  catch (e) {
    page.appendChild(el('div', 'error-box', escapeHtml(e.message)));
    return;
  }
  const grid = el('div', 'mig-grid rise');
  grid.style.setProperty('--i', 1);
  const S = { info, alive: () => document.body.contains(grid) };
  grid.appendChild(migBuildExport(S));
  grid.appendChild(migBuildImport(S));
  page.appendChild(grid);
}

/* ---------------------------------------------------------------
   Exporter
   --------------------------------------------------------------- */
function migBuildExport(S) {
  const info = S.info;
  const sec = el('section', 'mig-card');
  sec.setAttribute('aria-labelledby', 'mig-exp-h');
  sec['innerHTML'] = `
    <header class="mig-head">
      <span class="xi">${I.upload}</span>
      <div><h2 id="mig-exp-h">Exporter</h2>
      <p>Une seule archive : workspaces, sessions Claude Code, MCPs, secrets et configuration. Chiffrée en entier.</p></div>
    </header>
    <div class="mig-size" data-size aria-live="polite"><span class="dim">Calcul de la taille…</span></div>
    <details class="mig-ws" data-ws-box>
      <summary><span data-ws-sum>Workspaces</span></summary>
      <div class="mig-ws-tools"><button type="button" class="btn btn-ghost btn-sm" data-all>Tout cocher</button>
        <button type="button" class="btn btn-ghost btn-sm" data-none>Tout décocher</button></div>
      <div class="mig-ws-list" data-ws-list></div>
    </details>
    <div data-notes></div>
    <form class="mig-form" data-form autocomplete="off">
      <div class="field"><label class="field-label" for="mig-dest">Dossier de destination</label>
        <div class="mig-inline"><input id="mig-dest" class="input mono" data-dest spellcheck="false">
        <button type="button" class="btn" data-browse style="display:none">${I.folder}<span>Parcourir…</span></button></div></div>
      <div class="field"><label class="field-label" for="mig-pass">Phrase de passe</label>
        <div class="mig-inline"><input id="mig-pass" class="input" type="password" data-pass autocomplete="new-password" spellcheck="false">
        <button type="button" class="btn btn-ghost" data-eye aria-label="Afficher la phrase de passe" aria-pressed="false">${I.eye}</button></div></div>
      <div class="field"><label class="field-label" for="mig-pass2">Confirmer la phrase de passe</label>
        <input id="mig-pass2" class="input" type="password" data-pass2 autocomplete="new-password" spellcheck="false"></div>
      <p class="mig-hint" data-hint aria-live="polite"></p>
    </form>
    <div data-run></div>
    <div data-result></div>`;

  const q = (s) => sec.querySelector(s);
  const E = { selected: new Set(), sizes: {}, token: 0, est: null };
  const dest = q('[data-dest]');
  dest.value = info.default_dest || '';
  const pass = q('[data-pass]');
  const pass2 = q('[data-pass2]');
  const hint = q('[data-hint]');
  const form = q('[data-form]');

  // Liste des workspaces
  const list = q('[data-ws-list]');
  for (const w of info.workspaces) {
    const row = el('label', 'mig-row' + (w.exists ? '' : ' is-off'));
    row['innerHTML'] = `<input type="checkbox" data-ws="${escapeHtml(w.id)}" ${w.exists ? 'checked' : 'disabled'}>
      ${wsGem(w)}<span class="mig-row-main"><b>${escapeHtml(w.label)}</b>
      <small class="mono">${escapeHtml(w.path)}</small></span>
      <span class="mig-row-size mono" data-size-of="${escapeHtml(w.id)}">${w.exists ? '' : 'introuvable'}</span>`;
    list.appendChild(row);
    if (w.exists) E.selected.add(w.id);
  }
  if (!info.workspaces.length) list['innerHTML'] = '<p class="xempty">Aucun workspace enregistré.</p>';

  const updateWsSummary = () => {
    const total = info.workspaces.filter((w) => w.exists).length;
    q('[data-ws-sum]').textContent = `Workspaces à exporter : ${E.selected.size} sur ${total}`;
  };
  updateWsSummary();

  // Estimation (annule la precedente cote serveur)
  const sizeBox = q('[data-size]');
  const notes = q('[data-notes]');
  const refreshEstimate = async () => {
    const token = ++E.token;
    sizeBox['innerHTML'] = '<span class="dim">Calcul de la taille…</span>';
    let snap;
    try {
      snap = await migRunJob({ kind: 'estimate', workspaces: [...E.selected] }, { alive: S.alive, holder: {} });
    } catch (e) {
      if (token === E.token) sizeBox['innerHTML'] = `<span class="mig-err">${escapeHtml(e.message)}</span>`;
      return;
    }
    if (!snap || token !== E.token || snap.status === 'cancelled') return;
    if (snap.status !== 'done') {
      sizeBox['innerHTML'] = `<span class="mig-err">${escapeHtml(snap.error || 'Estimation impossible')}</span>`;
      return;
    }
    E.est = snap.result;
    renderEstimate();
  };
  const refreshSoon = debounce(refreshEstimate, 450);

  const renderEstimate = () => {
    const est = E.est;
    if (!est) return;
    for (const w of est.workspaces) {
      if (w.selected) E.sizes[w.id] = w.bytes;
      const span = list.querySelector(`[data-size-of="${CSS.escape(w.id)}"]`);
      if (span && w.exists) span.textContent = E.sizes[w.id] != null ? migBytes(E.sizes[w.id]) : '';
    }
    const groups = est.groups.filter((g) => g.bytes > 0 || g.files > 0);
    const total = Math.max(est.total_bytes, 1);
    const segs = groups.map((g, i) => `<span class="mig-seg" style="flex:${Math.max(g.bytes, total * 0.015)};background:${MIG_COLORS[i % MIG_COLORS.length]}" title="${escapeHtml(g.label)}"></span>`).join('');
    const legend = groups.map((g, i) => `<li><span class="mig-dot" style="background:${MIG_COLORS[i % MIG_COLORS.length]}"></span>
      <span class="mig-leg-name">${escapeHtml(g.label)}</span>
      <span class="mig-leg-n mono">${migBytes(g.bytes)}</span>
      <span class="mig-leg-f dim">${migPlural(g.files, 'fichier', 'fichiers')}</span></li>`).join('');
    sizeBox['innerHTML'] = `
      <div class="mig-total"><b>${migBytes(est.total_bytes)}</b>
        <span>avant compression · ${migPlural(est.total_files, 'fichier', 'fichiers')}</span></div>
      <div class="mig-bar" role="img" aria-label="Répartition par catégorie">${segs}</div>
      <ul class="mig-legend">${legend}</ul>`;
    const parts = [];
    if (est.env_error) {
      parts.push(migCallout('err', `<strong>Coffre d'environnement illisible</strong> : ${escapeHtml(est.env_error)}. L'export est refusé tant que le coffre n'est pas lisible (sinon l'archive serait sans secrets sans te le dire).`));
    } else {
      parts.push(migCallout('info', `<strong>${migPlural(est.env_keys, 'variable', 'variables')} d'environnement</strong> (secrets) seront incluses. L'archive est chiffrée en entier : transcripts de sessions compris, qui peuvent contenir des secrets.`));
    }
    if (est.recreate && est.recreate.length) {
      parts.push(migCallout('info', `<strong>${migPlural(est.recreate.length, 'environnement', 'environnements')} non exporté${est.recreate.length > 1 ? 's' : ''}</strong> (.venv, node_modules) : à recréer sur la nouvelle machine.
        <details class="mig-more"><summary>Voir la liste</summary>${migList(est.recreate)}</details>`));
    }
    if (est.warnings && est.warnings.length) parts.push(migCallout('warn', migList(est.warnings)));
    notes['innerHTML'] = '';
    parts.forEach((p) => notes.appendChild(p));
  };

  list.addEventListener('change', (ev) => {
    const cb = ev.target.closest('[data-ws]');
    if (!cb) return;
    if (cb.checked) E.selected.add(cb.dataset.ws); else E.selected.delete(cb.dataset.ws);
    updateWsSummary();
    refreshSoon();
  });
  q('[data-all]').addEventListener('click', () => {
    list.querySelectorAll('[data-ws]:not(:disabled)').forEach((cb) => { cb.checked = true; E.selected.add(cb.dataset.ws); });
    updateWsSummary(); refreshSoon();
  });
  q('[data-none]').addEventListener('click', () => {
    list.querySelectorAll('[data-ws]').forEach((cb) => { cb.checked = false; });
    E.selected.clear(); updateWsSummary(); refreshSoon();
  });

  // Dossier de destination : selecteur natif du serveur si disponible
  const browse = q('[data-browse]');
  if (typeof folderPickerSupported === 'function') {
    folderPickerSupported().then((ok) => { if (ok) browse.style.display = ''; });
  }
  browse.addEventListener('click', () => withBusy(browse, async () => {
    const r = await API.post('/api/system/pick-folder', { initial: dest.value.trim(), title: "Dossier de l'archive" });
    if (r && r.ok && r.path) dest.value = r.path;
  }).catch((e) => toastErr(e.message)));

  const eye = q('[data-eye]');
  eye.addEventListener('click', () => {
    const show = pass.type === 'password';
    pass.type = show ? 'text' : 'password';
    pass2.type = pass.type;
    eye.setAttribute('aria-pressed', show ? 'true' : 'false');
    eye.setAttribute('aria-label', show ? 'Masquer la phrase de passe' : 'Afficher la phrase de passe');
    eye['innerHTML'] = show ? I.eyeoff : I.eye;
  });

  const exportBtn = btn('Exporter', 'btn-primary', I.upload);
  exportBtn.disabled = true;
  const actions = el('div', 'mig-actions');
  actions.appendChild(exportBtn);
  form.after(actions);

  const validate = () => {
    const min = info.min_passphrase;
    let msg = '', ok = false;
    if (pass.value.length < min) msg = `${pass.value.length} / ${min} caractères minimum.`;
    else if (pass.value !== pass2.value) msg = 'Les deux phrases ne correspondent pas.';
    else { msg = 'Phrase valide.'; ok = true; }
    hint.textContent = msg;
    hint.classList.toggle('is-ok', ok);
    exportBtn.disabled = !ok || !dest.value.trim();
  };
  [pass, pass2, dest].forEach((i) => i.addEventListener('input', validate));
  validate();
  form.addEventListener('submit', (e) => e.preventDefault());

  const runHost = q('[data-run]');
  const resultHost = q('[data-result]');
  exportBtn.addEventListener('click', async () => {
    resultHost['innerHTML'] = '';
    const holder = {};
    const prog = migProgressBox(holder);
    runHost.appendChild(prog.box);
    form.disabled = true;
    exportBtn.disabled = true;
    form.querySelectorAll('input,button').forEach((i) => { i.disabled = true; });
    let snap;
    try {
      snap = await migRunJob({
        kind: 'export', passphrase: pass.value, passphrase_confirm: pass2.value,
        dest_dir: dest.value.trim(), workspaces: [...E.selected],
      }, { onProgress: prog.update, alive: S.alive, holder });
    } catch (e) {
      snap = { status: 'error', error: e.message };
    }
    runHost['innerHTML'] = '';
    form.querySelectorAll('input,button').forEach((i) => { i.disabled = false; });
    validate();
    if (!snap) return;
    if (snap.status === 'done') {
      pass.value = ''; pass2.value = '';
      validate();
      migRenderExportResult(resultHost, snap.result);
    } else if (snap.status === 'cancelled') {
      resultHost.appendChild(migCallout('info', 'Export annulé : aucun fichier laissé.'));
    } else {
      resultHost.appendChild(migCallout('err', `<strong>Export impossible.</strong> ${escapeHtml(snap.error || '')}`));
    }
  });

  refreshEstimate();
  return sec;
}

function migRenderExportResult(host, r) {
  const box = el('div', 'mig-done');
  box['innerHTML'] = `
    <div class="mig-done-h"><span class="pill ok">Archive vérifiée</span>
      <b>${migBytes(r.size)}</b>
      <span class="dim">${migPlural(r.files, 'fichier', 'fichiers')} · ${migPlural(r.workspaces, 'workspace', 'workspaces')} · ${migPlural(r.env_keys, 'variable', 'variables')} · ${escapeHtml(String(r.seconds))} s</span></div>
    <div class="mig-path mono" data-path>${escapeHtml(r.path)}</div>
    <div class="mig-actions"></div>
    <p class="mig-hint">Copie ce fichier sur l'autre machine, puis importe-le depuis cette même page. Garde la phrase de passe <strong>séparément</strong> : sans elle, l'archive est irrécupérable.</p>`;
  const copy = btn('Copier le chemin', 'btn', I.copy);
  copy.addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(r.path); toastOk('Chemin copié'); }
    catch { toastErr('Copie impossible : sélectionne le chemin à la main'); }
  });
  box.querySelector('.mig-actions').appendChild(copy);
  if (r.warnings && r.warnings.length) box.appendChild(migCallout('warn', migList(r.warnings)));
  host.appendChild(box);
}

/* ---------------------------------------------------------------
   Importer
   --------------------------------------------------------------- */
function migBuildImport(S) {
  const info = S.info;
  const sec = el('section', 'mig-card');
  sec.setAttribute('aria-labelledby', 'mig-imp-h');
  sec['innerHTML'] = `
    <header class="mig-head">
      <span class="xi">${I.download}</span>
      <div><h2 id="mig-imp-h">Importer</h2>
      <p>Aperçu en lecture seule d'abord : rien n'est écrit tant que tu n'as pas validé. Rien n'est jamais écrasé sans sauvegarde.</p></div>
    </header>
    <form class="mig-form" data-form autocomplete="off">
      <div class="field"><label class="field-label" for="mig-arch">Archive (.nebmig)</label>
        <div class="mig-inline"><input id="mig-arch" class="input mono" data-arch spellcheck="false" placeholder="Chemin complet du fichier d'archive">
        <button type="button" class="btn" data-browse style="display:none">${I.folder}<span>Chercher dans un dossier…</span></button></div></div>
      <div class="mig-found" data-found></div>
      <p class="mig-hint" data-arch-info aria-live="polite"></p>
      <div class="field"><label class="field-label" for="mig-ipass">Phrase de passe</label>
        <div class="mig-inline"><input id="mig-ipass" class="input" type="password" data-pass autocomplete="off" spellcheck="false">
        <button type="button" class="btn btn-ghost" data-eye aria-label="Afficher la phrase de passe" aria-pressed="false">${I.eye}</button></div></div>
    </form>
    <div class="mig-actions" data-analyze-row></div>
    <div data-run></div>
    <div data-plan></div>
    <div data-result></div>`;

  const q = (s) => sec.querySelector(s);
  const M = {
    archive: null, options: { rules: [], workspaces: {}, mcp: {}, env: {}, items: {}, claude_json: 'keep' },
    planId: null, plan: null, dirty: false, busy: false,
  };
  const arch = q('[data-arch]');
  const pass = q('[data-pass]');
  const archInfo = q('[data-arch-info]');
  const found = q('[data-found]');
  const runHost = q('[data-run]');
  const planHost = q('[data-plan]');
  const resultHost = q('[data-result]');

  const analyze = btn("Analyser l'archive", 'btn-primary', I.search);
  analyze.disabled = true;
  q('[data-analyze-row]').appendChild(analyze);
  const updateAnalyze = () => { analyze.disabled = M.busy || !M.archive || !pass.value; };

  q('[data-eye]').addEventListener('click', (ev) => {
    const eye = ev.currentTarget;
    const show = pass.type === 'password';
    pass.type = show ? 'text' : 'password';
    eye.setAttribute('aria-pressed', show ? 'true' : 'false');
    eye.setAttribute('aria-label', show ? 'Masquer la phrase de passe' : 'Afficher la phrase de passe');
    eye['innerHTML'] = show ? I.eyeoff : I.eye;
  });
  q('[data-form]').addEventListener('submit', (e) => e.preventDefault());
  pass.addEventListener('input', updateAnalyze);

  const resetPlan = () => {
    M.plan = null; M.planId = null; M.dirty = false;
    M.options = { rules: [], workspaces: {}, mcp: {}, env: {}, items: {}, claude_json: 'keep' };
    planHost['innerHTML'] = '';
    resultHost['innerHTML'] = '';
  };

  const inspect = async () => {
    const path = arch.value.trim();
    M.archive = null;
    updateAnalyze();
    resetPlan();
    if (!path) { archInfo.textContent = ''; return; }
    const r = await API.postStatus('/api/migration/inspect-archive', { path });
    if (arch.value.trim() !== path) return;
    if (!r.ok) {
      archInfo['innerHTML'] = `<span class="pill err">${escapeHtml(r.data.error || 'Archive refusée')}</span>`;
      return;
    }
    M.archive = r.data;
    archInfo['innerHTML'] = `<span class="pill ok">Archive Nebula</span> format ${escapeHtml(String(r.data.format_version))} · ${migBytes(r.data.size)} · modifiée ${escapeHtml(fmtDateTime(r.data.mtime))}`;
    updateAnalyze();
  };
  arch.addEventListener('change', inspect);
  arch.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); inspect(); } });

  const showFound = (archives, folder) => {
    found['innerHTML'] = '';
    if (!archives.length) {
      found['innerHTML'] = `<p class="mig-hint">Aucune archive .nebmig dans ${escapeHtml(folder)}.</p>`;
      return;
    }
    const wrap = el('div', 'mig-archs');
    wrap.setAttribute('role', 'list');
    for (const a of archives) {
      const b = el('button', 'mig-arch', `${I.archive}<span class="mig-row-main"><b>${escapeHtml(a.name)}</b>
        <small class="mono">${migBytes(a.size)} · ${escapeHtml(fmtDateTime(a.mtime))}</small></span>`);
      b.type = 'button';
      b.setAttribute('role', 'listitem');
      b.addEventListener('click', () => { arch.value = a.path; inspect(); });
      wrap.appendChild(b);
    }
    found.appendChild(wrap);
  };
  const scan = async (folder) => {
    const r = await API.postStatus('/api/migration/find-archives', { folder });
    if (r.ok) showFound(r.data.archives, folder);
  };
  const browse = q('[data-browse]');
  if (typeof folderPickerSupported === 'function') {
    folderPickerSupported().then((ok) => { if (ok) browse.style.display = ''; });
  }
  browse.addEventListener('click', () => withBusy(browse, async () => {
    const r = await API.post('/api/system/pick-folder', { initial: info.default_dest, title: "Dossier contenant l'archive" });
    if (r && r.ok && r.path) await scan(r.path);
  }).catch((e) => toastErr(e.message)));
  scan(info.default_dest);       // archives deja presentes dans le dossier de sauvegarde

  const setBusy = (b) => { M.busy = b; updateAnalyze(); arch.disabled = b; pass.disabled = b; };

  // -- Apercu (job `preview`) ------------------------------------------------
  const runPreview = async () => {
    if (M.busy) return;
    collectRules();
    resultHost['innerHTML'] = '';
    setBusy(true);
    const holder = {};
    const prog = migProgressBox(holder);
    runHost.appendChild(prog.box);
    let snap;
    try {
      snap = await migRunJob({
        kind: 'preview', archive_path: M.archive.path, passphrase: pass.value, options: M.options,
      }, { onProgress: prog.update, alive: S.alive, holder });
    } catch (e) { snap = { status: 'error', error: e.message }; }
    runHost['innerHTML'] = '';
    setBusy(false);
    if (!snap) return;
    if (snap.status !== 'done') {
      planHost['innerHTML'] = '';
      if (snap.status === 'cancelled') { planHost.appendChild(migCallout('info', 'Analyse annulée.')); return; }
      planHost.appendChild(migCallout('err', `<strong>Analyse impossible.</strong> ${escapeHtml(snap.error || '')}`));
      return;
    }
    M.plan = snap.result.plan;
    M.planId = snap.result.plan_id;
    M.dirty = false;
    renderPlan();
  };
  analyze.addEventListener('click', () => { resetPlan(); runPreview(); });

  const collectRules = () => {
    const rows = planHost.querySelectorAll('[data-rule]');
    if (!M.plan) return;
    M.options.rules = [...rows].map((r) => ({
      from: r.querySelector('[data-from]').value.trim(), to: r.querySelector('[data-to]').value.trim(),
    })).filter((r) => r.from && r.to);
  };

  // -- Rendu du plan -----------------------------------------------------------
  const markDirty = () => {
    if (M.dirty) return;
    M.dirty = true;
    const bar = planHost.querySelector('[data-dirty]');
    if (bar) bar.hidden = false;
    const go = planHost.querySelector('[data-go]');
    if (go) go.disabled = true;
  };

  const sel = (name, value, opts) => {
    const s = el('select', 'select mig-sel');
    s.setAttribute('aria-label', name);
    for (const [v, label] of opts) {
      const o = document.createElement('option');
      o.value = v; o.textContent = label;
      if (v === value) o.selected = true;
      s.appendChild(o);
    }
    return s;
  };

  const section = (title, sub) => {
    const s = el('section', 'mig-sec');
    s['innerHTML'] = `<h3 class="mig-sec-h">${escapeHtml(title)}${sub ? ` <small>${escapeHtml(sub)}</small>` : ''}</h3>`;
    return s;
  };

  const renderPlan = () => {
    const plan = M.plan;
    planHost['innerHTML'] = '';
    const top = el('div', 'mig-sum');
    const c = plan.counts;
    const kpi = (n, label) => `<div class="mig-kpi"><b>${escapeHtml(fmtNum(n))}</b><span>${escapeHtml(label)}</span></div>`;
    const status = plan.blocked ? `<span class="pill err">Bloqué : ${migPlural(c.workspaces_blocked, 'workspace', 'workspaces')}</span>`
      : !plan.disk.ok ? '<span class="pill err">Espace disque insuffisant</span>'
        : '<span class="pill ok">Prêt à importer</span>';
    const sessBytes = plan.sessions.reduce((a, s) => a + s.bytes, 0);
    top['innerHTML'] = `
      <div class="mig-sum-h">${status}<span class="dim">Archive de ${escapeHtml(plan.archive.source_host || '?')} (${escapeHtml(plan.archive.source_os)}), Nebula ${escapeHtml(plan.archive.nebula_version)}, créée ${escapeHtml(fmtDateTime(plan.archive.created))}</span></div>
      <div class="mig-kpis">
        ${kpi(c.workspaces_import, 'workspaces à importer')}
        ${kpi(c.conflicts, 'conflits à trancher')}
        ${kpi(plan.sessions.length, 'dossiers de sessions')}
        <div class="mig-kpi"><b>${migBytes(plan.disk.needed)}</b><span>à préparer · ${migBytes(plan.disk.free)} libres</span></div>
      </div>`;
    planHost.appendChild(top);
    const dirty = migCallout('warn', 'Tes choix ont changé : recalcule l\'aperçu avant d\'importer.');
    dirty.setAttribute('data-dirty', '');
    dirty.hidden = true;
    planHost.appendChild(dirty);
    if (plan.warnings.length) planHost.appendChild(migCallout('warn', migList(plan.warnings)));

    planHost.appendChild(renderRules(plan));
    planHost.appendChild(renderWorkspaces(plan));
    planHost.appendChild(renderMcp(plan));
    planHost.appendChild(renderEnv(plan));
    planHost.appendChild(renderItems(plan));
    planHost.appendChild(renderSessions(plan));
    if (plan.notes.length || plan.recreate.length || plan.plugins_installed.length) planHost.appendChild(renderNotes(plan));

    const bar = el('div', 'mig-actions mig-sticky');
    const recompute = btn("Recalculer l'aperçu", 'btn', I.refresh);
    recompute.addEventListener('click', runPreview);
    const go = btn('Importer', 'btn-primary', I.download);
    go.setAttribute('data-go', '');
    go.disabled = !plan.ok;
    go.addEventListener('click', () => confirmImport());
    bar.append(recompute, go);
    planHost.appendChild(bar);
  };

  function renderRules(plan) {
    const s = section('Chemins sur cette machine', 'remappage des chemins absolus');
    const body = el('div', 'mig-rules');
    body['innerHTML'] = `<p class="mig-hint">Les chemins de l'archive (<span class="mono">${escapeHtml(plan.archive.source_os)}</span>) sont convertis pour <span class="mono">${escapeHtml(plan.target.os)}</span> dans les workspaces, ~/.claude.json, le registre MCP, les variables et les dossiers de sessions. La règle la plus précise gagne.</p>`;
    for (const r of plan.rules.auto) {
      body.appendChild(el('div', 'mig-rule is-auto', `<span class="mono">${escapeHtml(r.from)}</span><span class="mig-arrow" aria-hidden="true">${I.right}</span><span class="mono">${escapeHtml(r.to)}</span><span class="pill mute">automatique</span>`));
    }
    const userHost = el('div');
    const addRule = (from = '', to = '') => {
      const row = el('div', 'mig-rule');
      row.setAttribute('data-rule', '');
      row['innerHTML'] = `<input class="input mono" data-from placeholder="Ancien préfixe (ex. D:\\Projets)" aria-label="Ancien préfixe">
        <span class="mig-arrow" aria-hidden="true">${I.right}</span>
        <input class="input mono" data-to placeholder="Nouveau préfixe" aria-label="Nouveau préfixe">`;
      row.querySelector('[data-from]').value = from;
      row.querySelector('[data-to]').value = to;
      const rm = btn('', 'btn-ghost btn-icon', I.x);
      rm.setAttribute('aria-label', 'Retirer la règle');
      rm.addEventListener('click', () => { row.remove(); markDirty(); });
      row.appendChild(rm);
      row.addEventListener('input', markDirty);
      userHost.appendChild(row);
      return row;
    };
    for (const r of plan.rules.user) addRule(r.from, r.to);
    body.appendChild(userHost);
    const add = btn('Ajouter une règle', 'btn btn-ghost', I.plus);
    add.addEventListener('click', () => { addRule().querySelector('[data-from]').focus(); });
    body.appendChild(add);
    s.appendChild(body);
    return s;
  }

  function renderWorkspaces(plan) {
    const s = section('Workspaces', migPlural(plan.workspaces.length, 'dans l\'archive', 'dans l\'archive'));
    if (!plan.workspaces.length) { s.appendChild(el('p', 'xempty', 'Aucun workspace dans cette archive.')); return s; }
    const list = el('div', 'mig-wslist');
    for (const w of plan.workspaces) {
      const row = el('div', 'mig-ws-item');
      const pills = [];
      if (w.blocked) pills.push(`<span class="pill err">bloqué</span>`);
      else if (w.status === 'new') pills.push('<span class="pill ok">nouveau</span>');
      else {
        if (w.conflicts.includes('id')) pills.push('<span class="pill warn">id déjà pris</span>');
        if (w.conflicts.includes('path')) pills.push('<span class="pill warn">chemin occupé</span>');
      }
      pills.push(`<span class="pill mute">${escapeHtml(MIG_ORIGIN_LABELS[w.path_origin] || w.path_origin)}</span>`);
      if (w.action !== 'skip' && !w.parent_exists && !w.blocked) pills.push('<span class="pill mute">dossier parent créé</span>');
      row['innerHTML'] = `<div class="mig-ws-top">${wsGem(w)}<span class="mig-row-main"><b>${escapeHtml(w.label)}</b>
        <small class="mono">${escapeHtml(w.id)}${w.eff_id !== w.id ? ` → ${escapeHtml(w.eff_id)}` : ''} · ${migBytes(w.bytes)} · ${migPlural(w.files, 'fichier', 'fichiers')}</small></span>
        <span class="mig-pills">${pills.join('')}</span></div>
        <div class="mig-paths mono"><span>${escapeHtml(w.source_path)}</span><span class="mig-arrow" aria-hidden="true">${I.right}</span><span data-target>${escapeHtml(w.target_path)}</span></div>
        ${w.blocked ? `<p class="mig-blocked">${escapeHtml(w.blocked)}</p>` : ''}`;
      const ctl = el('div', 'mig-ctl');
      const opts = w.status === 'new' ? [['import', 'Importer'], ['skip', 'Ignorer']]
        : [['skip', 'Ignorer'], ['replace', 'Remplacer (ancien rangé en sauvegarde)'], ['rename', 'Importer sous un autre id']];
      const value = (w.status === 'new' && w.action === 'rename') ? 'import' : w.action;
      const act = sel(`Action pour ${w.label}`, opts.some((o) => o[0] === value) ? value : opts[0][0], opts);
      const idIn = el('input', 'input mono mig-newid');
      idIn.setAttribute('aria-label', 'Nouvel id');
      idIn.value = (M.options.workspaces[w.id] && M.options.workspaces[w.id].new_id) || w.suggested_id;
      idIn.hidden = act.value !== 'rename';
      act.addEventListener('change', () => {
        const o = M.options.workspaces[w.id] = M.options.workspaces[w.id] || {};
        o.action = act.value;
        if (act.value === 'rename') o.new_id = idIn.value.trim();
        idIn.hidden = act.value !== 'rename';
        markDirty();
      });
      idIn.addEventListener('input', () => {
        const o = M.options.workspaces[w.id] = M.options.workspaces[w.id] || {};
        o.action = 'rename'; o.new_id = idIn.value.trim();
        markDirty();
      });
      ctl.append(act, idIn);
      const det = el('details', 'mig-more');
      det['innerHTML'] = '<summary>Changer le chemin cible</summary>';
      const pathIn = el('input', 'input mono');
      pathIn.setAttribute('aria-label', 'Chemin cible');
      pathIn.value = (M.options.workspaces[w.id] && M.options.workspaces[w.id].target_path) || w.target_path;
      pathIn.addEventListener('input', () => {
        const o = M.options.workspaces[w.id] = M.options.workspaces[w.id] || {};
        o.target_path = pathIn.value.trim();
        if (!o.action) o.action = w.action;
        markDirty();
      });
      det.appendChild(pathIn);
      if (w.blocked) det.open = true;
      row.append(ctl, det);
      list.appendChild(row);
    }
    s.appendChild(list);
    return s;
  }

  function renderMcp(plan) {
    const s = section('Registre MCP', migPlural(plan.mcp.length, 'serveur', 'serveurs'));
    const n = (st) => plan.mcp.filter((m) => m.status === st).length;
    s.appendChild(el('p', 'mig-hint', `${migPlural(n('new'), 'nouveau', 'nouveaux')} · ${migPlural(n('same'), 'identique', 'identiques')} · ${migPlural(n('conflict'), 'en conflit', 'en conflit')}. Les fichiers .mcp.json des workspaces importés viennent de l'archive ; « Synchroniser tout » les régénère ensuite.`));
    for (const m of plan.mcp.filter((x) => x.status === 'conflict')) {
      const row = el('div', 'mig-line', `<span class="mig-row-main"><b>${escapeHtml(m.name)}</b><small class="mono">${escapeHtml(m.id)}</small></span><span class="pill warn">config différente</span>`);
      const s2 = sel(`MCP ${m.name}`, m.action, [['skip', 'Garder le local'], ['replace', 'Remplacer (registre sauvegardé)']]);
      s2.addEventListener('change', () => { M.options.mcp[m.id] = s2.value; markDirty(); });
      row.appendChild(s2);
      s.appendChild(row);
    }
    return s;
  }

  function renderEnv(plan) {
    const items = plan.env.items;
    const s = section('Variables d\'environnement', migPlural(items.length, 'clé', 'clés'));
    if (plan.env.error) { s.appendChild(migCallout('err', `${escapeHtml(plan.env.error)}`)); return s; }
    const n = (st) => items.filter((m) => m.status === st).length;
    s.appendChild(el('p', 'mig-hint', `${migPlural(n('new'), 'nouvelle', 'nouvelles')} · ${migPlural(n('same'), 'identique', 'identiques')} · ${migPlural(n('conflict'), 'en conflit', 'en conflit')}. Seuls les noms sont affichés, jamais les valeurs.`));
    for (const e of items.filter((x) => x.status === 'conflict')) {
      const row = el('div', 'mig-line', `<span class="mig-row-main"><b class="mono">${escapeHtml(e.key)}</b></span><span class="pill warn">valeur différente</span>`);
      const s2 = sel(`Variable ${e.key}`, e.action, [['keep', 'Garder la valeur locale'], ['replace', 'Remplacer (coffre sauvegardé)']]);
      s2.addEventListener('change', () => { M.options.env[e.key] = s2.value; markDirty(); });
      row.appendChild(s2);
      s.appendChild(row);
    }
    return s;
  }

  function renderItems(plan) {
    const s = section('Configuration et fichiers', migPlural(plan.items.length, 'élément', 'éléments'));
    const exists = plan.items.filter((i) => i.status === 'exists');
    const fresh = plan.items.filter((i) => i.status === 'new');
    s.appendChild(el('p', 'mig-hint', `${migPlural(fresh.length, 'élément sera ajouté', 'éléments seront ajoutés')} (settings, skills, agents, commandes, templates, configs MCP, code des serveurs MCP locaux…). ${migPlural(exists.length, 'existe déjà ici', 'existent déjà ici')} : ignoré par défaut.`));
    for (const i of exists) {
      const row = el('div', 'mig-line', `<span class="mig-row-main"><b>${escapeHtml(i.label)}</b><small class="mono">${escapeHtml(i.dest)}</small></span><span class="pill warn">déjà présent</span>`);
      const s2 = sel(`Élément ${i.label}`, i.action, [['skip', 'Garder le local'], ['replace', 'Remplacer (ancien rangé en sauvegarde)']]);
      s2.addEventListener('change', () => { M.options.items[i.key] = s2.value; markDirty(); });
      row.appendChild(s2);
      s.appendChild(row);
    }
    if (fresh.length) {
      const d = el('details', 'mig-more');
      d['innerHTML'] = `<summary>Voir les éléments ajoutés</summary>${migList(fresh.map((i) => i.label))}`;
      s.appendChild(d);
    }
    return s;
  }

  function renderSessions(plan) {
    const total = plan.sessions.reduce((a, x) => a + x.bytes, 0);
    const files = plan.sessions.reduce((a, x) => a + x.files, 0);
    const s = section('Historique des sessions', `${migPlural(plan.sessions.length, 'dossier', 'dossiers')} · ${migPlural(files, 'fichier', 'fichiers')} · ${migBytes(total)}`);
    const renamed = plan.sessions.filter((x) => x.renamed);
    const merge = plan.sessions.filter((x) => x.status === 'merge');
    s.appendChild(el('p', 'mig-hint', `Toujours inclus pour que /resume fonctionne. Fusion fichier par fichier : un fichier déjà présent n'est jamais écrasé. ${migPlural(renamed.length, 'dossier est renommé', 'dossiers sont renommés')} pour les nouveaux chemins ; ${migPlural(merge.length, 'existe déjà (fusion)', 'existent déjà (fusion)')}.`));
    if (renamed.length) {
      const d = el('details', 'mig-more');
      d['innerHTML'] = `<summary>Voir les dossiers renommés</summary><ul class="mig-ul mono">${renamed.map((x) => `<li>${escapeHtml(x.name)} → ${escapeHtml(x.target_name)}</li>`).join('')}</ul>`;
      s.appendChild(d);
    }
    return s;
  }

  function renderNotes(plan) {
    const s = section('À faire ensuite');
    const box = el('div');
    for (const n of plan.notes) box.appendChild(migCallout('info', `${escapeHtml(n)}`));
    if (plan.recreate.length) {
      const d = el('details', 'mig-more');
      d['innerHTML'] = `<summary>Environnements à recréer (${plan.recreate.length})</summary>${migList(plan.recreate)}`;
      box.appendChild(d);
    }
    if (plan.plugins_installed.length) {
      const d = el('details', 'mig-more');
      d['innerHTML'] = `<summary>Plugins à réinstaller (${plan.plugins_installed.length})</summary>${migList(plan.plugins_installed)}`;
      box.appendChild(d);
    }
    s.appendChild(box);
    return s;
  }

  // -- Execution (job `import`) -------------------------------------------------
  function confirmImport() {
    if (!M.plan || M.dirty || !M.planId) return;
    const c = M.plan.counts;
    const msg = `Importer ${c.workspaces_import} workspace(s) et le reste de l'archive ?\n\n`
      + 'Tout ce qui est remplacé est d\'abord rangé dans backups/migration-<date>/. '
      + 'Ferme Claude Code avant de continuer : il réécrit ~/.claude.json.';
    confirmDialog(msg, () => { runImport(); }, { confirmLabel: 'Importer' });
  }

  const runImport = async () => {
    setBusy(true);
    resultHost['innerHTML'] = '';
    const holder = {};
    const prog = migProgressBox(holder);
    runHost.appendChild(prog.box);
    planHost.querySelectorAll('button,input,select').forEach((n) => { n.disabled = true; });
    let snap;
    try {
      snap = await migRunJob({ kind: 'import', plan_id: M.planId, passphrase: pass.value },
        { onProgress: prog.update, alive: S.alive, holder });
    } catch (e) { snap = { status: 'error', error: e.message }; }
    runHost['innerHTML'] = '';
    setBusy(false);
    if (!snap) return;
    if (snap.status === 'done') {
      pass.value = '';
      updateAnalyze();
      planHost['innerHTML'] = '';
      M.plan = null; M.planId = null;
      migRenderImportResult(resultHost, snap.result);
      toastOk('Import terminé');
      return;
    }
    if (snap.error_code === 'plan_stale' && snap.result && snap.result.plan) {
      M.plan = snap.result.plan; M.planId = snap.result.plan_id; M.dirty = false;
      renderPlan();
      resultHost.appendChild(migCallout('warn', `<strong>L'état de cette machine a changé</strong> depuis l'aperçu : relis le nouvel aperçu ci-dessus avant d'importer.`));
      return;
    }
    planHost.querySelectorAll('button,input,select').forEach((n) => { n.disabled = false; });
    if (snap.status === 'cancelled') resultHost.appendChild(migCallout('info', 'Import annulé : rien n\'a été appliqué.'));
    else {
      if (snap.error_code === 'plan_expired') { M.plan = null; M.planId = null; }
      resultHost.appendChild(migCallout('err', `<strong>Import impossible.</strong> ${escapeHtml(snap.error || '')}`));
    }
  };

  return sec;
}

function migRenderImportResult(host, r) {
  const box = el('div', 'mig-done');
  const w = r.workspaces, e = r.env, m = r.mcp, it = r.items, se = r.sessions;
  box['innerHTML'] = `
    <div class="mig-done-h"><span class="pill ok">Import terminé</span><span class="dim">${escapeHtml(String(r.seconds))} s</span></div>
    <ul class="mig-ul">
      <li>${migPlural(w.imported, 'workspace importé', 'workspaces importés')}${w.replaced ? `, dont ${escapeHtml(String(w.replaced))} remplacé(s)` : ''}${w.errors ? `, ${escapeHtml(String(w.errors))} en erreur` : ''}</li>
      <li>MCP : ${escapeHtml(String(m.added))} ajouté(s), ${escapeHtml(String(m.replaced))} remplacé(s)</li>
      <li>Variables : ${escapeHtml(String(e.added))} ajoutée(s), ${escapeHtml(String(e.replaced))} remplacée(s)${e.errors ? `, ${escapeHtml(String(e.errors))} en erreur` : ''}</li>
      <li>Éléments de configuration : ${escapeHtml(String(it.imported))} ajouté(s), ${escapeHtml(String(it.replaced))} remplacé(s)</li>
      <li>Sessions : ${escapeHtml(fmtNum(se.files_added))} fichier(s) ajouté(s), ${escapeHtml(fmtNum(se.identical))} identique(s), ${escapeHtml(fmtNum(se.kept_local))} conservé(s) en local</li>
    </ul>
    ${r.backup_dir ? `<p class="mig-hint">Anciens états rangés dans <span class="mono">${escapeHtml(r.backup_dir)}</span></p>` : ''}`;
  if (r.errors && r.errors.length) {
    box.appendChild(migCallout('err', `<strong>${migPlural(r.errors.length, 'erreur', 'erreurs')}</strong>${migList(r.errors.map((x) => `${x.area} ${x.id} : ${x.error}`))}`));
  }
  if (r.extract_errors && r.extract_errors.length) {
    box.appendChild(migCallout('warn', `<strong>${migPlural(r.extract_errors.length, 'fichier non extrait', 'fichiers non extraits')}</strong>${migList(r.extract_errors.slice(0, 20).map((x) => `${x.path} : ${x.error}`))}`));
  }
  box.appendChild(migCallout('info', `<strong>À faire ensuite</strong>${migList(r.next_steps || [])}`));
  host.appendChild(box);
}
