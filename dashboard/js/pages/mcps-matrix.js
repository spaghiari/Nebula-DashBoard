/* ================================================================
   Nebula - Vue Matrice (page MCPs) : MCP x workspace
   ----------------------------------------------------------------
   Lignes = MCPs, colonnes = workspaces, une case = « ce MCP est actif dans
   ce workspace ». Source de verite : le champ `workspaces` de chaque MCP du
   registre (/api/mcps). Un MCP dont `workspaces` contient "*" (ou "all") est
   actif PARTOUT (meme semantique que mcp_applies_to cote serveur).

   Edition en deux temps :
   - un clic bascule la case LOCALEMENT (anneau pointille = en attente),
     aucune ecriture reseau ;
   - le bandeau « N modifications en attente » propose Appliquer / Annuler.
   Appliquer reproduit le flux de la modale d'edition : POST /api/mcps avec
   le MCP complet et sa nouvelle liste `workspaces` ; le serveur synchronise
   lui-meme les .mcp.json des workspaces touches (add_or_update_mcp ->
   _auto_sync) et renvoie la liste `synced`. Un POST par MCP modifie, en
   sequence (verrou de mutation cote serveur) : l'echec d'un MCP n'empeche
   pas les autres, et ses cases sont rétablies visuellement.

   Performance : le DOM est construit une fois par rendu (innerHTML d'une
   chaine), puis un clic ne met a jour QUE la case concernee, les compteurs
   de sa ligne et de sa colonne. Delegation d'evenements sur la table.

   Les modifications en attente vivent dans _mxPending (module) : elles
   survivent a un re-rendu de la page (poller, route silencieux) et sont
   reconciliees avec l'etat serveur a chaque rendu.

   Styles : css/editor-matrix.css. Charge APRES mcps.js.
   ================================================================ */
'use strict';

const MX_VIEW_KEY = 'nebula-mcps-view';
const MX_SORT_KEY = 'nebula-mcps-matrix-sort';

// "mcpId|wsId" -> booleen VOULU (differe toujours de l'etat serveur).
const _mxPending = new Map();
let _mxPhase = 'idle';          // 'idle' | 'applying'
let _mxProgress = { done: 0, total: 0 };
let _mxResult = null;           // { ok: [ids], failed: [{id, msg}] } apres Appliquer
let _mxFailKeys = new Set();    // cases a signaler en echec (retablies)
let _mxBarListener = null;      // callback de rafraichissement du bandeau (instance courante)

function mcpViewMode() {
  try { return localStorage.getItem(MX_VIEW_KEY) === 'matrix' ? 'matrix' : 'cards'; } catch { return 'cards'; }
}
function setMcpViewMode(mode) {
  try { localStorage.setItem(MX_VIEW_KEY, mode === 'matrix' ? 'matrix' : 'cards'); } catch { /* quota / mode prive */ }
}
function mcpMatrixSort() {
  try { return localStorage.getItem(MX_SORT_KEY) === 'count' ? 'count' : 'name'; } catch { return 'name'; }
}
function setMcpMatrixSort(v) {
  try { localStorage.setItem(MX_SORT_KEY, v === 'count' ? 'count' : 'name'); } catch { /* noop */ }
}

const _mxKey = (mcpId, wsId) => `${mcpId}|${wsId}`;
const _mxIsWild = (m) => { const w = m.workspaces || []; return w.includes('*') || w.includes('all'); };
const _mxServerActive = (m, wsId) => _mxIsWild(m) || (m.workspaces || []).includes(wsId);

// Helpers partagés avec la page workspace (app.js : Détacher / modale
// Attacher) -- même sémantique joker que la matrice.
function mcpIsWildcard(m) { return _mxIsWild(m); }
function mcpActiveOn(m, wsId) { return _mxServerActive(m, wsId); }
// Liste `workspaces` d'un MCP après retrait de `wsId`. Joker "*"/"all" ->
// liste explicite de tous les workspaces connus sauf `wsId` (les workspaces
// créés plus tard ne l'auront plus automatiquement).
function mcpWorkspacesWithout(m, wsId, wsList) {
  if (_mxIsWild(m)) return (wsList || []).map(w => w.id).filter(id => id !== wsId);
  return (m.workspaces || []).filter(x => x !== wsId);
}
const _mxWanted = (m, wsId) => {
  const k = _mxKey(m.id, wsId);
  return _mxPending.has(k) ? _mxPending.get(k) : _mxServerActive(m, wsId);
};

// Nouvelle liste `workspaces` d'un MCP apres application des cases en attente.
// Garde les ids inconnus de la liste des workspaces (orphelins) ; si le MCP
// etait en "*", la liste devient explicite (les cases decochees sortent).
function _mxWorkspacesAfter(m, wsList) {
  const ids = wsList.map(w => w.id);
  const known = new Set(ids);
  const orig = m.workspaces || [];
  const keep = _mxIsWild(m) ? [] : orig.filter(x => !known.has(x));
  return [...ids.filter(id => _mxWanted(m, id)), ...keep];
}

// Retire les cases en attente devenues sans objet (egales a l'etat serveur,
// MCP ou workspace disparu).
function _mxReconcile(allMcps, wsList) {
  const byId = new Map(allMcps.map(m => [m.id, m]));
  const wsIds = new Set(wsList.map(w => w.id));
  for (const [k, want] of Array.from(_mxPending)) {
    const [mid, wid] = k.split('|');
    const m = byId.get(mid);
    if (!m || !wsIds.has(wid) || _mxServerActive(m, wid) === want) _mxPending.delete(k);
  }
}

// Le bandeau est fixe (hors de la page) : on le retire quand on quitte la page
// MCPs. Les modifications en attente restent en memoire (_mxPending) et le
// bandeau reapparait au retour sur la vue Matrice.
window.addEventListener('hashchange', () => {
  if (!/^#\/mcps(\/|$|\?)/.test(location.hash)) {
    const bar = document.getElementById('mx-bar');
    if (bar) bar.remove();
  }
});

// Avertit avant de quitter / recharger l'onglet avec des modifications non appliquees.
window.addEventListener('beforeunload', (e) => {
  if (_mxPending.size) { e.preventDefault(); e.returnValue = ''; }
});

// ---- Bandeau flottant ---------------------------------------------------
function _mxEnsureBar() {
  let bar = document.getElementById('mx-bar');
  if (!bar) {
    bar = document.createElement('div');
    bar.id = 'mx-bar';
    bar.className = 'mx-bar';
    bar.setAttribute('role', 'region');
    bar.setAttribute('aria-label', 'Modifications de la matrice MCP');
    document.body.appendChild(bar);
  }
  return bar;
}
function _mxRemoveBar() {
  const bar = document.getElementById('mx-bar');
  if (bar) bar.remove();
}

function createMcpMatrix({ onEdit = null } = {}) {
  const root = el('div', 'mx-wrap');
  let mcps = [];
  let wss = [];
  let rows = [];          // { m, tr, cells: [button], cnt, countEl }
  let colTh = [];         // th d'en-tete par colonne
  let colTd = [];         // tableaux de td par colonne
  let colCnt = [];
  let footEls = [];
  let hot = { r: -1, c: -1 };
  let cur = null;         // case portant tabindex=0 (roving)
  let table = null;
  let scroller = null;
  let destroyed = false;

  const cellOf = (r, c) => (rows[r] ? rows[r].cells[c] : null);

  // ---- Peinture d'une case + compteurs (aucune reconstruction) --------
  const paintCell = (r, c) => {
    const row = rows[r];
    const btnEl = row.cells[c];
    const m = row.m;
    const w = wss[c];
    const k = _mxKey(m.id, w.id);
    const want = _mxWanted(m, w.id);
    btnEl.setAttribute('aria-pressed', want ? 'true' : 'false');
    btnEl.classList.toggle('is-pending', _mxPending.has(k));
    btnEl.classList.toggle('is-fail', _mxFailKeys.has(k));
    const via = _mxIsWild(m) && !_mxPending.has(k) && want ? ' (actif via « tous les workspaces »)' : '';
    btnEl.title = _mxPending.has(k)
      ? `${m.name || m.id} dans ${w.id} : ${want ? 'sera activé' : 'sera retiré'} (en attente)`
      : `${m.name || m.id} dans ${w.id} : ${want ? 'actif' : 'inactif'}${via}`;
  };
  const setCount = (r, c, delta) => {
    rows[r].cnt += delta; colCnt[c] += delta;
    rows[r].countEl.textContent = String(rows[r].cnt);
    footEls[c].textContent = String(colCnt[c]);
  };

  // ---- Bandeau ----------------------------------------------------------
  const refreshBar = () => {
    if (destroyed) return;
    const n = _mxPending.size;
    if (_mxPhase === 'applying') {
      const bar = _mxEnsureBar();
      bar.dataset.state = 'applying';
      bar['innerHTML'] = `<span class="spinner" aria-hidden="true"></span><div class="mx-bar-msg" role="status"><strong>Application en cours…</strong><small>${_mxProgress.done}/${_mxProgress.total} MCP</small></div>`;
      return;
    }
    if (n > 0) {
      const bar = _mxEnsureBar();
      bar.dataset.state = 'pending';
      const nM = new Set(Array.from(_mxPending.keys()).map(k => k.split('|')[0])).size;
      bar['innerHTML'] = `
        <div class="mx-bar-msg" role="status"><strong>${n} modification${n > 1 ? 's' : ''} en attente sur ${nM} MCP${nM > 1 ? 's' : ''}</strong><small>Rien n'est écrit tant que tu n'as pas appliqué.</small></div>
      `;
      const cancel = btn('Annuler', 'btn-sm btn-ghost');
      const apply = btn('Appliquer et synchroniser', 'btn-sm btn-primary', I.check);
      cancel.addEventListener('click', discard);
      apply.addEventListener('click', applyAll);
      bar.append(cancel, apply);
      return;
    }
    if (_mxResult && _mxResult.failed.length) {
      const bar = _mxEnsureBar();
      bar.dataset.state = 'error';
      const f = _mxResult.failed;
      bar['innerHTML'] = `
        <div class="mx-bar-msg" role="status"><strong>${f.length} MCP en échec</strong>${_mxResult.ok.length ? `, ${_mxResult.ok.length} appliqué${_mxResult.ok.length > 1 ? 's' : ''}` : ''}
          <small>${f.map(x => `${escapeHtml(x.id)} : ${escapeHtml(x.msg)}`).join(' · ')} -- cases rétablies.</small></div>
      `;
      const close = btn('Fermer', 'btn-sm');
      close.addEventListener('click', () => { _mxResult = null; clearFailMarks(); refreshBar(); });
      bar.append(close);
      return;
    }
    _mxRemoveBar();
  };
  _mxBarListener = refreshBar;

  const clearFailMarks = () => {
    const keys = Array.from(_mxFailKeys);
    _mxFailKeys = new Set();
    for (const k of keys) repaintKey(k);
  };

  // Repeint une case designee par sa cle (si elle est affichee).
  const repaintKey = (k) => {
    const [mid, wid] = k.split('|');
    const r = rows.findIndex(x => x.m.id === mid);
    const c = wss.findIndex(w => w.id === wid);
    if (r < 0 || c < 0) return;
    const before = rows[r].cells[c].getAttribute('aria-pressed') === 'true';
    paintCell(r, c);
    const after = rows[r].cells[c].getAttribute('aria-pressed') === 'true';
    if (before !== after) setCount(r, c, after ? 1 : -1);
  };

  // ---- Actions ------------------------------------------------------------
  const toggle = (r, c) => {
    if (_mxPhase === 'applying') return;
    if (_mxResult) { _mxResult = null; clearFailMarks(); }
    const m = rows[r].m;
    const w = wss[c];
    const k = _mxKey(m.id, w.id);
    const next = !_mxWanted(m, w.id);
    if (next === _mxServerActive(m, w.id)) _mxPending.delete(k); else _mxPending.set(k, next);
    paintCell(r, c);
    setCount(r, c, next ? 1 : -1);
    refreshBar();
  };

  const discard = () => {
    if (_mxPhase === 'applying') return;
    const keys = Array.from(_mxPending.keys());
    _mxPending.clear();
    for (const k of keys) repaintKey(k);
    refreshBar();
  };

  const applyAll = async () => {
    if (_mxPhase === 'applying' || !_mxPending.size) return;
    // Regroupe les cases en attente par MCP.
    const byMcp = new Map();
    for (const [k] of _mxPending) {
      const [mid, wid] = k.split('|');
      if (!byMcp.has(mid)) byMcp.set(mid, new Set());
      byMcp.get(mid).add(wid);
    }
    const snapshotKeys = Array.from(_mxPending.keys());
    _mxPhase = 'applying';
    _mxProgress = { done: 0, total: byMcp.size };
    _mxResult = null;
    _mxFailKeys = new Set();
    root.classList.add('is-applying');
    root.querySelectorAll('.mx-cell').forEach(b => { b.disabled = true; });
    refreshBar();

    const ok = [];
    const failed = [];
    const touchedWs = new Set();
    for (const [mid, wsSet] of byMcp) {
      const m = (STATE.mcps || []).find(x => x.id === mid);
      if (!m) {
        failed.push({ id: mid, msg: 'MCP introuvable dans le registre' });
        for (const wid of wsSet) { _mxPending.delete(_mxKey(mid, wid)); _mxFailKeys.add(_mxKey(mid, wid)); }
      } else {
        const newList = _mxWorkspacesAfter(m, STATE.workspaces || []);
        try {
          const resp = await API.post('/api/mcps', { ...m, workspaces: newList });
          m.workspaces = newList;
          // STATE.mcps a pu etre remplace par le poller pendant le POST.
          const live = (STATE.mcps || []).find(x => x.id === mid);
          if (live) live.workspaces = newList;
          (resp.synced || []).forEach(x => touchedWs.add(x));
          wsSet.forEach(x => touchedWs.add(x));
          ok.push(mid);
          for (const wid of wsSet) _mxPending.delete(_mxKey(mid, wid));
        } catch (e) {
          failed.push({ id: mid, msg: e.message || 'erreur inconnue' });
          // Rollback visuel : on abandonne les cases de ce MCP (retour a l'etat serveur).
          for (const wid of wsSet) { _mxPending.delete(_mxKey(mid, wid)); _mxFailKeys.add(_mxKey(mid, wid)); }
        }
      }
      _mxProgress.done++;
      refreshBar();
    }

    // Rafraichit l'etat partage pour les autres pages (STATE.wsMcps) sans
    // recharger toute l'application.
    try {
      await Promise.all(Array.from(touchedWs).filter(id => (STATE.workspaces || []).some(w => w.id === id)).map(async (id) => {
        const r = await safe(`/api/workspaces/${id}/mcps`, null);
        if (r) STATE.wsMcps = { ...(STATE.wsMcps || {}), [id]: r };
      }));
    } catch (e) { console.warn('[matrice] rafraîchissement wsMcps échoué :', e.message); }

    // Le poller (30 s) a pu remplacer STATE.mcps pendant l'application : on
    // relit le registre puis on rattache chaque ligne a l'objet a jour, sinon
    // repaintKey repeindrait avec un `workspaces` perime.
    try {
      const fresh = await safe('/api/mcps', null);
      if (fresh && Array.isArray(fresh.mcps)) STATE.mcps = fresh.mcps;
    } catch (e) { console.warn('[matrice] relecture du registre échouée :', e.message); }
    for (const row of rows) {
      const cur2 = (STATE.mcps || []).find(x => x.id === row.m.id);
      if (cur2) row.m = cur2;
    }

    _mxPhase = 'idle';
    root.classList.remove('is-applying');
    root.querySelectorAll('.mx-cell').forEach(b => { b.disabled = false; });
    _mxResult = { ok, failed };
    for (const k of snapshotKeys) repaintKey(k);
    if (failed.length) {
      toastErr(`${failed.length} MCP en échec : ${failed.map(f => f.id).join(', ')}`);
    }
    if (ok.length) {
      toastOk(`${ok.length} MCP mis à jour -- ${touchedWs.size} workspace${touchedWs.size > 1 ? 's' : ''} synchronisé${touchedWs.size > 1 ? 's' : ''}`);
    }
    if (!failed.length) _mxResult = null;
    refreshBar();
  };

  // ---- Survol en croix ----------------------------------------------------
  const setHot = (r, c) => {
    if (hot.r === r && hot.c === c) return;
    if (hot.r !== r) {
      if (hot.r >= 0 && rows[hot.r]) rows[hot.r].tr.classList.remove('is-hot');
      if (r >= 0 && rows[r]) rows[r].tr.classList.add('is-hot');
    }
    if (hot.c !== c) {
      if (hot.c >= 0 && colTh[hot.c]) { colTh[hot.c].classList.remove('is-hotc'); colTd[hot.c].forEach(td => td.classList.remove('is-hotc')); }
      if (c >= 0 && colTh[c]) { colTh[c].classList.add('is-hotc'); colTd[c].forEach(td => td.classList.add('is-hotc')); }
    }
    hot = { r, c };
  };

  // ---- Navigation clavier (tabindex itinerant) -----------------------------
  const setCurrent = (b) => {
    if (cur === b) return;
    if (cur) cur.tabIndex = -1;
    cur = b;
    if (cur) cur.tabIndex = 0;
  };
  const focusCell = (r, c) => {
    r = Math.max(0, Math.min(rows.length - 1, r));
    c = Math.max(0, Math.min(wss.length - 1, c));
    const b = cellOf(r, c);
    if (b) { setCurrent(b); b.focus(); }
  };

  const onKeyDown = (e) => {
    const b = e.target.closest && e.target.closest('.mx-cell');
    if (!b || e.altKey || e.metaKey) return;
    const r = +b.dataset.r;
    const c = +b.dataset.c;
    let nr = r, nc = c;
    switch (e.key) {
      case 'ArrowRight': nc = c + 1; break;
      case 'ArrowLeft': nc = c - 1; break;
      case 'ArrowDown': nr = r + 1; break;
      case 'ArrowUp': nr = r - 1; break;
      case 'PageDown': nr = r + 10; break;
      case 'PageUp': nr = r - 10; break;
      case 'Home': nc = 0; if (e.ctrlKey) nr = 0; break;
      case 'End': nc = wss.length - 1; if (e.ctrlKey) nr = rows.length - 1; break;
      default: return;
    }
    e.preventDefault();
    focusCell(nr, nc);
  };

  const onClick = (e) => {
    const b = e.target.closest('.mx-cell');
    if (b && !b.disabled) { toggle(+b.dataset.r, +b.dataset.c); return; }
    const ed = e.target.closest('.mx-edit');
    if (ed && onEdit) { onEdit(rows[+ed.dataset.r].m); }
  };
  const onDblClick = (e) => {
    const h = e.target.closest('.mx-rowhead');
    if (h && !e.target.closest('.mx-edit') && onEdit) onEdit(rows[+h.parentElement.dataset.r].m);
  };
  const onOver = (e) => {
    const cell = e.target.closest('td.mx-c, th.mx-rowhead, th.mx-colhead');
    if (!cell) return;
    const tr = cell.parentElement;
    const r = tr.dataset.r !== undefined ? +tr.dataset.r : -1;
    const c = cell.dataset.c !== undefined ? +cell.dataset.c : -1;
    setHot(r, c);
  };
  const onFocusIn = (e) => {
    const b = e.target.closest && e.target.closest('.mx-cell');
    if (!b) return;
    setCurrent(b);
    setHot(+b.dataset.r, +b.dataset.c);
  };

  // ---- Rendu complet ---------------------------------------------------
  const render = (list, workspaces, { sort = 'name', all = null } = {}) => {
    if (destroyed || _mxPhase === 'applying') return;
    // Memorise defilement + case focalisee pour les re-rendus (poller, filtre).
    const prevScroll = scroller ? { t: scroller.scrollTop, l: scroller.scrollLeft } : null;
    const focused = (cur && document.activeElement === cur) ? { mid: rows[+cur.dataset.r]?.m.id, wid: wss[+cur.dataset.c]?.id } : null;

    mcps = list;
    wss = workspaces;
    _mxReconcile(all || list, wss);

    root.innerHTML = '';
    rows = []; colTh = []; colTd = []; colCnt = []; footEls = []; cur = null; hot = { r: -1, c: -1 };

    if (!wss.length) {
      root.appendChild(el('div', 'mx-empty', '<strong>Aucun workspace</strong><p>Crée un workspace pour pouvoir y activer des MCPs.</p>'));
      refreshBar();
      return;
    }
    if (!list.length) {
      root.appendChild(el('div', 'mx-empty', '<strong>Aucun MCP ne correspond</strong><p>Modifie ta recherche ou tes filtres.</p>'));
      refreshBar();
      return;
    }

    // Groupes : utilises (au moins un workspace, en tenant compte des cases
    // en attente) puis sans workspace. Le regroupement ne change qu'a un
    // rendu complet, jamais a un clic (sinon les lignes sauteraient).
    const countOf = (m) => wss.reduce((n, w) => n + (_mxWanted(m, w.id) ? 1 : 0), 0);
    const decorated = list.map(m => ({ m, n: countOf(m) }));
    const byName = (a, b) => (a.m.name || a.m.id).localeCompare(b.m.name || b.m.id, 'fr', { sensitivity: 'base' });
    const cmp = sort === 'count' ? (a, b) => (b.n - a.n) || byName(a, b) : byName;
    const used = decorated.filter(x => x.n > 0).sort(cmp);
    const unused = decorated.filter(x => x.n === 0).sort(byName);
    const ordered = [...used, ...unused];

    const nCols = wss.length;
    const parts = [];
    parts.push(`<table class="mx" aria-label="Matrice des MCPs par workspace"><caption class="mx-sr">Une case cochée signifie que le MCP est actif dans le workspace. Utilise les flèches pour naviguer et Espace pour basculer.</caption>`);
    parts.push(`<thead><tr><th class="mx-corner" scope="col"><strong>${list.length} MCP${list.length > 1 ? 's' : ''}</strong> × ${nCols} workspace${nCols > 1 ? 's' : ''}</th>`);
    wss.forEach((w, c) => {
      parts.push(`<th class="mx-colhead" scope="col" data-c="${c}" title="${escapeHtml(w.label && w.label !== w.id ? `${w.id} -- ${w.label}` : w.id)}"><span>${escapeHtml(w.id)}</span></th>`);
    });
    parts.push('</tr></thead><tbody>');

    const colTotals = new Array(nCols).fill(0);
    let r = 0;
    const emitGroup = (items, label) => {
      if (!items.length) return;
      if (label) parts.push(`<tr class="mx-group"><th colspan="${nCols + 1}" scope="colgroup"><span>${escapeHtml(label)} · ${items.length}</span></th></tr>`);
      for (const { m, n } of items) {
        const status = m.status === 'désactivé' ? 'off' : (m.status === 'disponible' ? 'ok' : 'warn');
        const nm = m.name || m.id;
        parts.push(`<tr data-r="${r}"${status === 'off' ? ' class="is-off"' : ''}><th class="mx-rowhead" scope="row"><div class="mx-rh">`
          + `<span class="mx-status" data-s="${status}" title="${escapeHtml(m.status || 'à configurer')}"></span>`
          + `<span class="mx-name" title="${escapeHtml(nm)}${nm !== m.id ? ` (${escapeHtml(m.id)})` : ''}">${escapeHtml(nm)}</span>`
          + `<span class="badge">${escapeHtml(m.transport || 'stdio')}</span>`
          + (_mxIsWild(m) ? `<span class="badge badge-accent" title="Ce MCP est actif dans TOUS les workspaces (&quot;*&quot;)">★ tous</span>` : '')
          + `<span class="mx-rcount" title="Workspaces où ce MCP est actif">${n}</span>`
          + `<button type="button" class="icon-btn mx-edit" data-r="${r}" aria-label="Modifier le MCP ${escapeHtml(nm)}" title="Modifier ${escapeHtml(nm)} (ou double-clic sur la ligne)">${I.edit}</button>`
          + `</div></th>`);
        wss.forEach((w, c) => {
          const want = _mxWanted(m, w.id);
          const k = _mxKey(m.id, w.id);
          if (want) colTotals[c]++;
          const pend = _mxPending.has(k);
          parts.push(`<td class="mx-c" data-c="${c}"><button type="button" class="mx-cell${pend ? ' is-pending' : ''}${_mxFailKeys.has(k) ? ' is-fail' : ''}" data-r="${r}" data-c="${c}" tabindex="-1" aria-pressed="${want ? 'true' : 'false'}" aria-label="${escapeHtml(nm)} dans ${escapeHtml(w.id)}"></button></td>`);
        });
        parts.push('</tr>');
        r++;
      }
    };
    emitGroup(used, unused.length ? 'Utilisés dans au moins un workspace' : null);
    emitGroup(unused, used.length || unused.length ? 'Sans workspace' : null);
    parts.push('</tbody><tfoot><tr><th scope="row">Total actifs</th>');
    for (let c = 0; c < nCols; c++) parts.push(`<td data-foot="${c}">${colTotals[c]}</td>`);
    parts.push('</tr></tfoot></table>');

    const legend = el('div', 'mx-legend');
    legend['innerHTML'] = `
      <span><span class="mx-cell" aria-pressed="true" aria-hidden="true"></span> Actif</span>
      <span><span class="mx-cell" aria-pressed="false" aria-hidden="true"></span> Non utilisé</span>
      <span><span class="mx-cell is-pending" aria-pressed="true" aria-hidden="true"></span> Modification en attente</span>
      <span class="dim">Flèches : naviguer · Espace : basculer · Double-clic sur un MCP : l'éditer</span>`;
    scroller = el('div', 'mx-scroll');
    scroller['innerHTML'] = parts.join('');
    root.append(legend, scroller);
    table = scroller.querySelector('table');

    // Index des elements (une seule passe).
    for (let c = 0; c < nCols; c++) colTd.push([]);
    colTh = Array.from(table.querySelectorAll('thead th.mx-colhead'));
    footEls = Array.from(table.querySelectorAll('tfoot td'));
    colCnt = colTotals.slice();
    table.querySelectorAll('tbody tr[data-r]').forEach((tr) => {
      const idx = +tr.dataset.r;
      const cells = Array.from(tr.querySelectorAll('button.mx-cell'));
      const tds = tr.querySelectorAll('td.mx-c');
      tds.forEach((td, c) => colTd[c].push(td));
      const item = ordered[idx];
      rows[idx] = { m: item.m, tr, cells, cnt: item.n, countEl: tr.querySelector('.mx-rcount') };
    });

    table.addEventListener('click', onClick);
    table.addEventListener('dblclick', onDblClick);
    table.addEventListener('mouseover', onOver);
    table.addEventListener('mouseleave', () => setHot(-1, -1));
    table.addEventListener('focusin', onFocusIn);
    table.addEventListener('focusout', (e) => { if (!table.contains(e.relatedTarget)) setHot(-1, -1); });
    table.addEventListener('keydown', onKeyDown);

    // Tabindex itinerant : une seule case dans l'ordre de tabulation.
    let start = cellOf(0, 0);
    if (focused && focused.mid) {
      const rr = rows.findIndex(x => x.m.id === focused.mid);
      const cc = wss.findIndex(w => w.id === focused.wid);
      if (rr >= 0 && cc >= 0) start = cellOf(rr, cc);
    }
    if (start) setCurrent(start);
    if (prevScroll) { scroller.scrollTop = prevScroll.t; scroller.scrollLeft = prevScroll.l; }
    if (focused && start && focused.mid) { try { start.focus({ preventScroll: true }); } catch { /* noop */ } }
    refreshBar();
  };

  return {
    el: root,
    render,
    pendingCount: () => _mxPending.size,
    refreshBar,
    destroy: () => { destroyed = true; if (_mxBarListener === refreshBar) _mxBarListener = null; },
    // Exposes pour les tests / l'inspection.
    _toggleByIds: (mid, wid) => {
      const r = rows.findIndex(x => x.m.id === mid);
      const c = wss.findIndex(w => w.id === wid);
      if (r >= 0 && c >= 0) toggle(r, c);
    },
    applyAll,
    discard,
  };
}

window.createMcpMatrix = createMcpMatrix;
window.mcpViewMode = mcpViewMode;
window.setMcpViewMode = setMcpViewMode;
window.mcpMatrixSort = mcpMatrixSort;
window.setMcpMatrixSort = setMcpMatrixSort;
