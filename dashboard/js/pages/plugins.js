/* ================================================================
   Nebula - Page Plugins (marketplace + installes)
   ----------------------------------------------------------------
   renderPlugins : en-tete, cartes « Installes » (filtres), orphelins,
   scope par workspace. Mise en page de la refonte 2026-10 (langage de
   la page MCPs : .pg-filters, .xcard, css/redesign.css section 10).
   loadInstalledPlugins / pluginCard : cartes avec interrupteur global
   et desinstallation ; pluginState : actif / desactive / casse / absent.
   pluginUpdatesInfo / pluginUpdateBadge : mises a jour d'apres le clone
   local du marketplace (GET /api/plugins/outdated), bouton « Rafraichir
   les marketplaces » (POST /api/plugins/marketplaces/refresh).
   renderPluginScope : override par workspace (Actif / Inactif / Heriter).
   modalInstallPlugin : modal d'installation depuis marketplace.
   modalPluginReadme : visualisation du README d'un plugin.

   Dependances foundations : STATE, API, escapeHtml, el, btn, fmtDate,
   I.*, setBreadcrumbs, setTopbarActions, openModal, toastOk, toastErr,
   confirmDialog, route.

   Ref : CM-2 batch 10, refactor 2026-05-13.
   ================================================================ */
'use strict';

async function renderPlugins() {
  setBreadcrumbs([{ label: 'Plugins' }]);
  const installBtn = btn('Installer', 'btn-primary', I.plus);
  installBtn.addEventListener('click', () => modalInstallPlugin());
  setTopbarActions([installBtn]);

  const c = $('#content');
  c['innerHTML'] = '';
  const page = el('div', 'page');
  const enabledMap = (STATE.plugins && STATE.plugins.enabled) || {};
  const nKnown = Object.keys(enabledMap).length;
  const nOn = Object.values(enabledMap).filter(Boolean).length;
  const header = el('div', 'page-header rise', `
    <div class="page-header-text">
      <h1 class="page-title">Plugins</h1>
      <p class="page-subtitle" data-plugins-sub>${nKnown} plugin${nKnown > 1 ? 's' : ''} Claude Code déclaré${nKnown > 1 ? 's' : ''}, ${nOn} actif${nOn > 1 ? 's' : ''} globalement. Le scope se règle ensuite workspace par workspace.</p>
    </div>
  `);
  page.appendChild(header);
  mountHelpLink(page, 'skills-plugins', 'les plugins');

  // Installés
  const instHead = el('div', 'lbl rise', 'Installés <small data-inst-count></small>');
  instHead.style.setProperty('--i', 1);
  page.appendChild(instHead);
  const installedHost = el('div', 'rise');
  installedHost.style.setProperty('--i', 2);
  page.appendChild(installedHost);
  loadInstalledPlugins(installedHost, { countEl: instHead.querySelector('[data-inst-count]'), subEl: header.querySelector('[data-plugins-sub]') });

  // Scope par plugin et par workspace
  const scopeHead = el('div', 'lbl rise', 'Scope par workspace <small>override local d\'un plugin, ou héritage du global</small>');
  scopeHead.style.setProperty('--i', 3);
  page.appendChild(scopeHead);
  const scopeHost = el('div', 'rise');
  scopeHost.style.setProperty('--i', 4);
  page.appendChild(scopeHost);
  renderPluginScope(scopeHost);

  c.appendChild(page);
}

// Etat affiche d'un plugin installe (Lot E item 4 : 3 etats degrades).
//   cassé    : activé (enabled) mais absent du disque -> rouge, switch
//              désactivé (l'activer n'a aucun effet réel).
//   absent   : présent dans settings.json mais plus sur disque, pas activé
//              -> neutre (warn), simple constat.
//   actif/désactivé : sur disque, géré normalement par le switch.
function pluginState(p) {
  if (p.enabled && !p.on_disk) return { key: 'broken', pill: '<span class="pill err" title="Plugin activé mais introuvable sur le disque -- il ne fait rien. Réinstalle-le ou désinstalle l\'entrée.">cassé</span>' };
  if (!p.on_disk) return { key: 'missing', pill: '<span class="pill warn" title="Absent du disque">absent</span>' };
  return p.enabled
    ? { key: 'on', pill: '<span class="pill ok">actif</span>' }
    : { key: 'off', pill: '<span class="pill mute">désactivé</span>' };
}

// ── Mises a jour (GET /api/plugins/outdated, dashcore/plugin_updates.py) ──
// Comparaison installe vs CLONE LOCAL du marketplace, sans reseau : le
// libelle dit toujours d'ou vient l'information et de quand elle date.
// Partage par le KPI plugins de l'Accueil (js/pages/home.js).
function fmtDayMonth(iso) {
  const d = new Date(iso);
  return isNaN(d) ? '' : d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' });
}

function pluginUpdatesInfo(upd) {
  if (!upd || !upd.counts) {
    return { short: 'mises à jour : état inconnu', cls: '', when: '', byId: {},
      groups: [{ title: 'Mises à jour', text: true, items: ['Marketplace local illisible : état des mises à jour inconnu.'] }] };
  }
  const c = upd.counts, total = upd.total || 0;
  const day = upd.checked_at ? fmtDayMonth(upd.checked_at) : '';
  const src = day ? ` · marketplace du ${day}` : '';
  let short, cls = '';
  if (!total) short = 'aucun plugin installé';
  else if (c.outdated) { short = `${c.outdated} mise${c.outdated > 1 ? 's' : ''} à jour dispo`; cls = 'warn'; }
  else if (c.unknown === total) short = 'mises à jour : état inconnu';
  else if (c.unknown) short = `${c.up_to_date}/${total} à jour${src}`;
  else { short = `à jour${src}`; cls = 'ok'; }
  const when = upd.checked_at
    ? `rafraîchi le ${fmtDateTime(upd.checked_at)} (${fmtAgo(upd.checked_at)})`
    : 'date de rafraîchissement inconnue';
  const names = (st) => Object.entries(upd.plugins || {}).filter(([, r]) => r.state === st).map(([id]) => id.split('@')[0]);
  const groups = [
    { title: 'Mise à jour disponible', items: names('outdated') },
    { title: 'Non vérifiables', items: names('unknown') },
    { title: 'Source', text: true, items: [
      `D'après le clone local du marketplace, ${when}.`,
      'Claude Code ne le rafraîchit qu\'à son démarrage ou via « Rafraîchir les marketplaces » (page Plugins).',
    ] },
  ];
  return { short, cls, when, groups, byId: upd.plugins || {} };
}

// Pastille / mention de mise a jour d'une carte de plugin.
function pluginUpdateBadge(id, r) {
  if (!r || r.state === 'up_to_date') return '';
  const lines = [];
  if (r.installed) lines.push(`Installé : ${r.installed}`);
  if (r.available) lines.push(`Marketplace : ${r.available}`);
  if (r.reason) lines.push(r.reason);
  if (r.state === 'outdated') {
    lines.push(`Pour l'appliquer : claude plugin update ${id} (puis redémarrer Claude Code).`);
    const hc = hcAttrs([{ title: 'Mise à jour disponible', items: lines, text: true }]);
    return `<span class="pill upd"${hc} aria-label="${escapeHtml('Mise à jour disponible. ' + lines.join(' '))}">mise à jour dispo</span>`;
  }
  const hc = hcAttrs([{ title: 'Mise à jour non vérifiable', items: lines, text: true }]);
  return `<span class="xupd-unk"${hc}>mise à jour non vérifiable</span>`;
}

async function loadInstalledPlugins(host, opts = {}) {
  host['innerHTML'] = '<div class="page-loader"><div class="spinner"></div></div>';
  try {
    const [data, updRaw] = await Promise.all([API.get('/api/plugins/installed'), safe('/api/plugins/outdated', null)]);
    const upd = pluginUpdatesInfo(updRaw);
    const updOf = (p) => upd.byId[p.id] || null;
    // API renvoie {cross, on_disk, marketplaces, orphans_on_disk}
    const installed = data.cross || [];
    const orphans = data.orphans_on_disk || [];
    // Stash les marketplaces pour le bouton Installer
    STATE.marketplaces = data.marketplaces || [];

    const refreshHeader = () => {
      const on = installed.filter(p => p.enabled && p.on_disk).length;
      const bad = installed.filter(p => !p.on_disk).length;
      if (opts.countEl) opts.countEl.textContent = installed.length ? String(installed.length) : '';
      if (opts.subEl) {
        opts.subEl['innerHTML'] = `${installed.length} plugin${installed.length > 1 ? 's' : ''} Claude Code installé${installed.length > 1 ? 's' : ''}, ${on} actif${on > 1 ? 's' : ''}`
          + (bad ? `, ${bad} à réparer` : '') + '. Le scope se règle ensuite workspace par workspace.';
      }
    };
    refreshHeader();

    if (!installed.length && !orphans.length) {
      host['innerHTML'] = '<div class="empty"><div class="empty-title">Aucun plugin installé</div><p class="muted">Clique sur <strong>Installer</strong> pour parcourir les marketplaces.</p></div>';
      return;
    }
    host['innerHTML'] = '';

    if (installed.length) {
      // Barre de filtres : recherche + puces (actifs / désactivés / à réparer).
      const toolbar = el('div', 'pg-filters');
      toolbar['innerHTML'] = `<span class="search-field">${I.search}<input class="input" type="search" placeholder="Nom, marketplace, description…" aria-label="Filtrer les plugins"></span>`;
      const searchInput = toolbar.querySelector('input');
      const chipGroup = el('span', 'pg-chipgroup');
      chipGroup.setAttribute('role', 'group');
      chipGroup.setAttribute('aria-label', 'Filtrer par état');
      toolbar.appendChild(chipGroup);
      host.appendChild(toolbar);

      // Etat des mises a jour + rafraichissement du clone a la demande
      // (`claude plugin marketplace update`, reseau, jusqu'a 3 min).
      const updBar = el('div', 'pg-upd');
      updBar['innerHTML'] = `<p><span class="pg-upd-k">Mises à jour</span> <span class="k-t ${upd.cls}">${escapeHtml(upd.short)}</span>`
        + `<span class="pg-upd-src"${hcAttrs(upd.groups)}>${upd.when ? `d'après le marketplace local, ${escapeHtml(upd.when)}` : 'marketplace local illisible'}</span></p>`;
      const refreshBtn = btn('Rafraîchir les marketplaces', 'btn-sm', I.refresh);
      refreshBtn.title = 'Télécharge la dernière version des marketplaces (claude plugin marketplace update), puis recompare';
      refreshBtn.addEventListener('click', () => withBusy(refreshBtn, async () => {
        try {
          const r = await API.post('/api/plugins/marketplaces/refresh', {});
          const n = ((r.updates || {}).counts || {}).outdated || 0;
          toastOk(n ? `Marketplaces rafraîchis : ${n} mise${n > 1 ? 's' : ''} à jour disponible${n > 1 ? 's' : ''}` : 'Marketplaces rafraîchis : rien de nouveau');
          loadInstalledPlugins(host, opts);
        } catch (e) { toastErr(e.message); }
      }));
      updBar.appendChild(refreshBtn);
      host.appendChild(updBar);
      const FILTERS = [['', 'Tous', () => true], ['on', 'Actifs', p => pluginState(p).key === 'on'],
        ['off', 'Désactivés', p => pluginState(p).key === 'off'], ['bad', 'À réparer', p => !p.on_disk],
        ['upd', 'Mise à jour dispo', p => (updOf(p) || {}).state === 'outdated']];
      let stateF = '';
      const drawChips = () => {
        chipGroup['innerHTML'] = FILTERS
          .map(([v, l, fn]) => [v, l, installed.filter(fn).length])
          .filter(([v, , n]) => !v || n > 0 || v === stateF)
          .map(([v, l, n]) => `<button class="fchip" type="button" data-f="${v}" aria-pressed="${stateF === v}">${escapeHtml(l)} <b>${n}</b></button>`).join('');
      };

      const grid = el('div', 'xgrid');
      host.appendChild(grid);
      const cards = installed.map(p => {
        const card = pluginCard(p, () => { drawChips(); refreshHeader(); applyFilter(); }, updOf(p));
        grid.appendChild(card);
        return [p, card];
      });
      const emptyEl = el('div', 'empty');
      emptyEl.hidden = true;
      emptyEl['innerHTML'] = '<div class="empty-title">Aucun plugin ne correspond</div><p class="muted">Modifie ta recherche ou tes filtres.</p> <button class="btn btn-sm" type="button" data-reset-filters>Tout afficher</button>';
      emptyEl.querySelector('[data-reset-filters]').addEventListener('click', () => { searchInput.value = ''; stateF = ''; drawChips(); applyFilter(); });
      grid.appendChild(emptyEl);

      function applyFilter() {
        const q = (searchInput.value || '').trim().toLowerCase();
        const fn = (FILTERS.find(f => f[0] === stateF) || FILTERS[0])[2];
        let n = 0;
        for (const [p, card] of cards) {
          card.hidden = !(fn(p) && (!q || `${p.id} ${p.description || ''}`.toLowerCase().includes(q)));
          if (!card.hidden) n++;
        }
        emptyEl.hidden = n > 0;
      }
      chipGroup.addEventListener('click', (e) => {
        const b = e.target.closest('[data-f]');
        if (!b) return;
        stateF = b.dataset.f;
        drawChips(); applyFilter();
      });
      searchInput.addEventListener('input', debounce(applyFilter, 100));
      drawChips();
    }

    if (orphans.length) {
      const box = el('div', 'card flush xorph');
      box['innerHTML'] = `
        <div class="card-h"><h3>${I.folder}Dossiers orphelins</h3><span class="pill mute">${orphans.length}</span></div>
        <p class="xorph-note">${orphans.length} dossier(s) orphelin(s) sur disque (présents mais non listés dans settings.json)</p>
        <div class="xrows"></div>
      `;
      const rows = box.querySelector('.xrows');
      for (const o of orphans) {
        const r = el('div', 'xrow');
        r['innerHTML'] = `<span class="mono xrow-n">${escapeHtml(o.dir_name)}</span><span class="dim mono xrow-p" title="${escapeHtml(o.rel_path)}">${escapeHtml(o.rel_path)}</span>`;
        rows.appendChild(r);
      }
      host.appendChild(box);
    }
  } catch (e) { host['innerHTML'] = `<div class="error-box">${escapeHtml(e.message)}</div>`; }
}

// Carte d'un plugin installe : etat, interrupteur global, desinstallation.
// onChange : rappel apres bascule reussie (compteurs / filtres de la page).
function pluginCard(p, onChange, upd = null) {
  const card = el('article', 'xcard plugin-card');
  const [shortId, mkt] = p.id.includes('@') ? p.id.split('@') : [p.id, null];
  const meta = [];
  const updBadge = pluginUpdateBadge(p.id, upd);
  const updOutdated = upd && upd.state === 'outdated';
  if (updBadge && !updOutdated) meta.push(updBadge);
  if (p.scope) meta.push(`<span>scope ${escapeHtml(p.scope)}</span>`);
  if (p.size_kb) meta.push(`<span>${fmtBytes(p.size_kb * 1024)}</span>`);
  if (p.installed_at) meta.push(`<span title="${escapeHtml(fmtDateTime(p.installed_at))}">installé ${escapeHtml(fmtAgo(p.installed_at))}</span>`);
  card['innerHTML'] = `
    <div class="top">
      <span class="xi" aria-hidden="true">${I.plug}</span>
      <div class="xt">
        <h3>${escapeHtml(shortId)}</h3>
        <div class="msub">${mkt ? `<small>${escapeHtml(mkt)}</small>` : ''}${p.version ? `<span class="chip">${escapeHtml(p.version)}</span>` : ''}</div>
      </div>
      <div class="xstate"><span data-state>${pluginState(p).pill}</span>${updOutdated ? updBadge : ''}</div>
    </div>
    <p class="xdesc ${p.description ? '' : 'none'}" title="${escapeHtml(p.description || '')}">${escapeHtml(p.description || 'Pas de description.')}</p>
    ${meta.length ? `<div class="xmeta">${meta.join('')}</div>` : ''}
  `;
  const foot = el('div', 'xfoot');
  const swWrap = el('label', 'xswitch');
  swWrap['innerHTML'] = `<span class="switch"><input type="checkbox" aria-label="Activer ${escapeHtml(shortId)}" ${p.enabled ? 'checked' : ''}${!p.on_disk ? ' disabled' : ''}><span class="switch-slider"></span></span><span class="xswitch-l">Activé globalement</span>`;
  // Switch désactivé si le plugin est absent du disque : (dés)activer un
  // plugin introuvable n'a aucun effet -> on évite le faux levier.
  if (!p.on_disk) {
    swWrap.title = "Plugin absent du disque -- impossible de l'activer tant qu'il n'est pas réinstallé.";
  }
  swWrap.querySelector('input').addEventListener('change', async (ev) => {
    const url = ev.target.checked ? '/api/plugins/enable' : '/api/plugins/disable';
    ev.target.disabled = true;
    try {
      await API.post(url, { plugin_id: p.id });
      toastOk('Mis à jour');
      p.enabled = ev.target.checked;
      if (STATE.plugins && STATE.plugins.enabled && p.id in STATE.plugins.enabled) STATE.plugins.enabled[p.id] = p.enabled;
      card.querySelector('[data-state]')['innerHTML'] = pluginState(p).pill;
      if (onChange) onChange();
    }
    catch (e) { toastErr(e.message); ev.target.checked = !ev.target.checked; }
    finally { ev.target.disabled = false; }
  });
  const rm = btn('', 'btn-sm btn-ghost btn-icon-only btn-danger', I.trash);
  rm.title = 'Désinstaller';
  rm.setAttribute('aria-label', `Désinstaller ${shortId}`);
  rm.addEventListener('click', () => confirmDialog(`Désinstaller ${p.id} ?`, async () => {
    try {
      await API.post('/api/plugins/uninstall-soft', { plugin_id: p.id, remove_files: false });
      toastOk('Désinstallé'); STATE.loading = true; route();
    } catch (e) { toastErr(e.message); }
  }, { danger: true, confirmLabel: 'Désinstaller' }));
  foot.append(swWrap, rm);
  card.appendChild(foot);
  return card;
}

async function renderPluginScope(host) {
  host['innerHTML'] = '<div class="page-loader"><div class="spinner"></div></div>';

  const pluginIds = Object.keys(STATE.plugins.enabled || {});
  if (!pluginIds.length) {
    host['innerHTML'] = '<div class="card xempty">Aucun plugin installé pour configurer le scope.</div>';
    return;
  }
  if (!STATE.workspaces.length) {
    host['innerHTML'] = '<div class="card xempty">Aucun workspace.</div>';
    return;
  }

  // UI : sélecteur plugin + filtre workspace + actions de masse + liste
  host['innerHTML'] = `
    <div class="card flush scope-card">
      <div class="scope-toolbar">
        <label class="scope-field">
          <span class="field-label">Plugin</span>
          <select class="select" name="plugin">
            ${pluginIds.map(id => `<option value="${escapeHtml(id)}">${escapeHtml(id.split('@')[0])}${id.includes('@') ? ` · ${escapeHtml(id.split('@')[1])}` : ''}</option>`).join('')}
          </select>
        </label>
        <label class="scope-field scope-field-q">
          <span class="field-label">Filtrer les workspaces</span>
          <span class="search-field">${I.search}<input class="input" type="search" name="filter" placeholder="Nom ou id…"></span>
        </label>
        <div class="scope-bulk" role="group" aria-label="Actions de masse sur les workspaces filtrés">
          <span class="scope-bulk-l">En masse</span>
          <button class="btn btn-sm" type="button" data-bulk="on">Activer tout</button>
          <button class="btn btn-sm" type="button" data-bulk="off">Désactiver tout</button>
          <button class="btn btn-sm btn-ghost" type="button" data-bulk="reset">Réinitialiser</button>
        </div>
      </div>
      <div class="scope-summary"></div>
      <div class="scope-list"></div>
    </div>
  `;

  const sel = host.querySelector('[name=plugin]');
  const filterInput = host.querySelector('[name=filter]');
  const summaryEl = host.querySelector('.scope-summary');
  const listEl = host.querySelector('.scope-list');

  let cache = {};  // ws_id -> {global, effective, overridden}
  let currentPid = sel.value;

  const fetchData = async (pid) => {
    cache = {};
    const r = await Promise.all(STATE.workspaces.map(async w => {
      try { const data = await API.get(`/api/workspaces/${w.id}/plugins`); return [w.id, (data.plugins || {})[pid]]; }
      catch { return [w.id, null]; }
    }));
    cache = Object.fromEntries(r);
  };

  const stateOf = (info) => {
    if (!info) return 'inherit';
    if (info.overridden) return info.effective ? 'on' : 'off';
    return info.effective ? 'inherit-on' : 'inherit-off';
  };
  const STATE_PILL = {
    'on': '<span class="pill ok" title="Override local : forcé actif">actif ici</span>',
    'off': '<span class="pill err" title="Override local : forcé inactif">inactif ici</span>',
    'inherit-on': '<span class="pill mute" title="Pas d\'override : suit le global">hérité · actif</span>',
    'inherit-off': '<span class="pill mute" title="Pas d\'override : suit le global">hérité · inactif</span>',
    'inherit': '<span class="pill mute" title="État inconnu : suit le global">hérité</span>',
  };

  const render = () => {
    const filter = (filterInput.value || '').trim().toLowerCase();
    const filtered = STATE.workspaces.filter(w => !filter || (`${w.id} ${w.label || ''}`).toLowerCase().includes(filter));

    // Stats résumé
    let active = 0, disabled = 0, inheritOn = 0, inheritOff = 0;
    for (const w of STATE.workspaces) {
      const s = stateOf(cache[w.id]);
      if (s === 'on') active++;
      else if (s === 'off') disabled++;
      else if (s === 'inherit-on') inheritOn++;
      else inheritOff++;
    }
    summaryEl['innerHTML'] = `
      <span><b class="text-ok tabular">${active}</b> override actif</span>
      <span><b class="text-err tabular">${disabled}</b> override désactivé</span>
      <span><b class="tabular">${inheritOn + inheritOff}</b> hérités du global (${inheritOn} actifs)</span>
    `;

    if (!filtered.length) {
      listEl['innerHTML'] = '<div class="xempty">Aucun workspace ne correspond.</div>';
      return;
    }

    listEl['innerHTML'] = '';
    for (const w of filtered) {
      const info = cache[w.id];
      const state = stateOf(info);
      const row = el('div', 'scope-row');
      row['innerHTML'] = `
        ${wsGem(w)}
        <div class="scope-row-main">
          <div class="scope-row-name">${escapeHtml(w.label || w.id)}</div>
          <small>${escapeHtml(w.id)}</small>
        </div>
        <div class="scope-row-state">${STATE_PILL[state] || STATE_PILL.inherit}</div>
        <div class="seg-control" role="group" aria-label="Plugin pour ${escapeHtml(w.label || w.id)}">
          <button type="button" data-set="on" class="${state === 'on' ? 'is-active' : ''}" aria-pressed="${state === 'on'}" title="Activé pour ce workspace">Actif</button>
          <button type="button" data-set="off" class="${state === 'off' ? 'is-active' : ''}" aria-pressed="${state === 'off'}" title="Désactivé pour ce workspace">Inactif</button>
          <button type="button" data-set="reset" class="${state.startsWith('inherit') ? 'is-active' : ''}" aria-pressed="${state.startsWith('inherit')}" title="Hériter du global (${info && info.global ? 'actif' : 'inactif'} actuellement)">Hériter</button>
        </div>
      `;
      const segBtns = Array.from(row.querySelectorAll('button[data-set]'));
      segBtns.forEach(b => {
        b.addEventListener('click', async () => {
          const next = { 'on': true, 'off': false, 'reset': null }[b.dataset.set];
          segBtns.forEach(x => { x.disabled = true; });
          try {
            await API.post(`/api/workspaces/${w.id}/plugins`, { plugin_id: currentPid, enabled: next });
            // Update cache locally pour réactivité
            const newInfo = next === null
              ? { global: info?.global, effective: info?.global, overridden: false }
              : { global: info?.global, effective: next, overridden: true };
            cache[w.id] = newInfo;
            render(); // recree la row (boutons remplaces, plus besoin de reactiver)
          } catch (e) {
            toastErr(e.message);
            segBtns.forEach(x => { x.disabled = false; });
          }
        });
      });
      listEl.appendChild(row);
    }
  };

  const reload = async () => {
    // Pas d'effacement de listEl pour préserver scroll/hauteur ; juste un voile
    listEl.classList.add('is-loading');
    await fetchData(currentPid);
    listEl.classList.remove('is-loading');
    render();
  };

  // Bulk actions
  for (const b of host.querySelectorAll('[data-bulk]')) {
    b.addEventListener('click', async () => {
      const action = b.dataset.bulk;
      const filter = (filterInput.value || '').trim().toLowerCase();
      const targets = STATE.workspaces.filter(w => !filter || (`${w.id} ${w.label || ''}`).toLowerCase().includes(filter));
      if (!targets.length) return;
      const verb = { on: 'activer', off: 'désactiver', reset: 'réinitialiser' }[action];
      confirmDialog(`${verb[0].toUpperCase()}${verb.slice(1)} le plugin pour ${targets.length} workspace(s) ?`, async () => {
        const value = action === 'on' ? true : action === 'off' ? false : null;
        const errs = [];
        for (const w of targets) {
          try { await API.post(`/api/workspaces/${w.id}/plugins`, { plugin_id: currentPid, enabled: value }); }
          catch (e) { errs.push(`${w.id}: ${e.message}`); }
        }
        if (errs.length) toastErr(errs.length + ' échec(s)'); else toastOk('Action de masse terminée');
        await reload();
      }, { confirmLabel: `${verb[0].toUpperCase()}${verb.slice(1)} (${targets.length})` });
    });
  }

  sel.addEventListener('change', async () => {
    currentPid = sel.value;
    await reload();
  });
  filterInput.addEventListener('input', debounce(render, 100));

  await reload();
}

async function modalInstallPlugin() {
  const body = el('div');
  body['innerHTML'] = `<div class="page-loader"><div class="spinner"></div><span>Chargement des marketplaces…</span></div>`;
  const cancel = btn('Fermer', 'btn-ghost');
  const { close } = openModal({ title: 'Installer un plugin', body, footer: cancel, wide: true });
  cancel.addEventListener('click', close);

  // Récupère les marketplaces disponibles
  let marketplaces = STATE.marketplaces;
  if (!marketplaces || !marketplaces.length) {
    try { const data = await API.get('/api/plugins/installed'); marketplaces = data.marketplaces || []; STATE.marketplaces = marketplaces; }
    catch (e) { body['innerHTML'] = `<div class="error-box">${escapeHtml(e.message)}</div>`; return; }
  }

  // Fallback : marketplace officielle Claude Code
  if (!marketplaces.length) {
    marketplaces = [{ id: 'claude-plugins-official' }];
  }

  // Statut "déjà installé"
  const installed = STATE.plugins?.enabled || {};
  const isInstalled = (mktId, plugId) => `${plugId}@${mktId}` in installed || plugId in installed;

  body['innerHTML'] = `
    <div class="row" style="gap:var(--sp-3);margin-bottom:var(--sp-4)">
      <div class="field" style="flex:1;margin:0">
        <label class="field-label">Marketplace</label>
        <select class="select" name="mkt">
          ${marketplaces.map(m => `<option value="${escapeHtml(m.id)}">${escapeHtml(m.id)}</option>`).join('')}
        </select>
      </div>
      <div class="field" style="flex:2;margin:0">
        <label class="field-label">Filtrer</label>
        <input class="input input-search" name="filter" placeholder="Rechercher…">
      </div>
    </div>
    <div class="tabs">
      <div class="tab active" data-tab="all">Tous</div>
      <div class="tab" data-tab="first_party">Officiels</div>
      <div class="tab" data-tab="external">Externes</div>
      <div class="tab" data-tab="manual">Spec manuel</div>
    </div>
    <div data-pane="all" class="plugin-browser"></div>
    <div data-pane="first_party" class="plugin-browser" hidden></div>
    <div data-pane="external" class="plugin-browser" hidden></div>
    <div data-pane="manual" hidden>
      <p class="muted" style="margin-top:0">Spec : <code class="mono">marketplace@plugin</code> ou URL git.</p>
      <div class="field"><label class="field-label">Spec</label><input class="input mono" name="spec" placeholder="claude-plugins-official@code-review"></div>
      <button class="btn btn-primary" data-install-spec>Installer</button>
    </div>
  `;

  // Tabs
  for (const tab of body.querySelectorAll('.tab')) {
    tab.addEventListener('click', () => {
      body.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      body.querySelectorAll('[data-pane]').forEach(p => p.hidden = p.dataset.pane !== tab.dataset.tab);
    });
  }

  // Manual install
  body.querySelector('[data-install-spec]').addEventListener('click', async () => {
    const spec = body.querySelector('[name=spec]').value.trim();
    if (!spec) { toastErr('Spec requis'); return; }
    await doInstall(spec, body);
  });

  const renderPlugin = (p, mktId, kind) => {
    const installed = isInstalled(mktId, p.id);
    const item = el('div', 'plugin-item' + (installed ? ' is-installed' : ''));
    const components = p.components || {};
    const compStr = Object.entries(components).filter(([_, n]) => n > 0).map(([k, n]) => `${n} ${k}`).join(' · ');
    item['innerHTML'] = `
      <div class="plugin-item-main">
        <div class="row" style="gap:var(--sp-2);align-items:flex-start">
          <strong style="font-size:13px">${escapeHtml(p.name || p.id)}</strong>
          ${p.version ? `<span class="badge mono">${escapeHtml(p.version)}</span>` : ''}
          ${kind === 'external' ? '<span class="badge badge-warn">externe</span>' : '<span class="badge badge-accent">officiel</span>'}
          ${installed ? '<span class="badge badge-ok">installé</span>' : ''}
        </div>
        <div class="muted" style="font-size:12px;margin-top:4px">${escapeHtml(p.description || '—')}</div>
        <div class="dim mono" style="font-size:11px;margin-top:4px">${escapeHtml(p.id)}${p.author ? ' · ' + escapeHtml(p.author) : ''}${compStr ? ' · ' + escapeHtml(compStr) : ''}</div>
      </div>
      <div class="plugin-item-actions"></div>
    `;
    const actions = item.querySelector('.plugin-item-actions');
    if (p.has_readme) {
      const readme = btn('README', 'btn-sm btn-ghost', I.book);
      readme.addEventListener('click', () => modalPluginReadme(mktId, kind, p.id, p.name));
      actions.appendChild(readme);
    }
    if (!installed) {
      const inst = btn('Installer', 'btn-sm btn-primary', I.download);
      inst.addEventListener('click', async () => {
        inst.disabled = true;
        await doInstall(`${p.id}@${mktId}`, body);
      });
      actions.appendChild(inst);
    }
    return item;
  };

  const renderMarketplace = async (mktId) => {
    const panes = {
      all: body.querySelector('[data-pane=all]'),
      first_party: body.querySelector('[data-pane=first_party]'),
      external: body.querySelector('[data-pane=external]'),
    };
    Object.values(panes).forEach(p => p['innerHTML'] = '<div class="page-loader"><div class="spinner"></div></div>');
    let data;
    try { data = await API.get(`/api/plugins/marketplace/${mktId}`); }
    catch (e) { Object.values(panes).forEach(p => p['innerHTML'] = `<div class="error-box">${escapeHtml(e.message)}</div>`); return; }
    if (data.error) {
      Object.values(panes).forEach(p => p['innerHTML'] = `<div class="error-box">${escapeHtml(data.error)}</div>`);
      return;
    }

    const filter = (body.querySelector('[name=filter]').value || '').trim().toLowerCase();
    const filterFn = (p) => !filter || (`${p.id} ${p.name || ''} ${p.description || ''}`).toLowerCase().includes(filter);

    const renderList = (host, items, kind) => {
      host['innerHTML'] = '';
      const filtered = items.filter(filterFn);
      if (!filtered.length) { host['innerHTML'] = '<div class="dim" style="padding:var(--sp-3);font-size:12.5px">Aucun plugin.</div>'; return; }
      for (const p of filtered) host.appendChild(renderPlugin(p, mktId, kind));
    };

    renderList(panes.all, [...(data.first_party || []).map(p => ({ ...p, _kind: 'first_party' })), ...(data.external || []).map(p => ({ ...p, _kind: 'external' }))].sort((a, b) => (a.name || a.id).localeCompare(b.name || b.id)), null);
    // Hack: re-render all with proper kind
    panes.all['innerHTML'] = '';
    const merged = [...(data.first_party || []).map(p => [p, 'first_party']), ...(data.external || []).map(p => [p, 'external'])];
    merged.sort(([a], [b]) => (a.name || a.id).localeCompare(b.name || b.id));
    const filteredAll = merged.filter(([p]) => filterFn(p));
    if (!filteredAll.length) panes.all['innerHTML'] = '<div class="dim" style="padding:var(--sp-3);font-size:12.5px">Aucun plugin.</div>';
    else for (const [p, kind] of filteredAll) panes.all.appendChild(renderPlugin(p, mktId, kind));

    renderList(panes.first_party, data.first_party || [], 'first_party');
    renderList(panes.external, data.external || [], 'external');
  };

  const select = body.querySelector('[name=mkt]');
  const filterInput = body.querySelector('[name=filter]');
  select.addEventListener('change', () => renderMarketplace(select.value));
  filterInput.addEventListener('input', debounce(() => renderMarketplace(select.value), 150));
  await renderMarketplace(select.value);

  async function doInstall(spec, container) {
    const toastId = toast(`Installation de ${spec}…`, 'info', 60000);
    try {
      const r = await API.post('/api/plugins/install', { spec });
      if (r.ok) {
        toastOk(`Plugin installé : ${spec}`);
        // Refresh marketplaces + plugins state
        STATE.loading = true;
        // Refresh just the modal view
        await renderMarketplace(select.value);
        // And refresh the underlying plugins page list
        if (location.hash === '#/plugins') route();
      } else {
        toastErr(r.stderr || r.error || 'Échec');
      }
    } catch (e) { toastErr(e.message); }
  }
}

async function modalPluginReadme(mktId, kind, pluginId, name) {
  let data;
  try { data = await API.get(`/api/plugins/marketplace/${mktId}/${kind}/${pluginId}/readme`); }
  catch (e) { toastErr(e.message); return; }
  const body = el('div');
  body.style.fontSize = '13px';
  body['innerHTML'] = `<pre style="background:var(--surface-2);padding:var(--sp-4);border-radius:var(--r-sm);max-height:60vh;overflow:auto;white-space:pre-wrap;font-family:var(--font-mono);font-size:12px;line-height:1.6">${escapeHtml(data.content || '')}</pre>`;
  const closeBtn = btn('Fermer', 'btn-ghost');
  const { close } = openModal({ title: `README · ${name || pluginId}`, body, footer: closeBtn, wide: true });
  closeBtn.addEventListener('click', close);
}
