/* ================================================================
   Nebula - Page Plugins (marketplace + installes)
   ----------------------------------------------------------------
   renderPlugins : page Plugins avec 2 onglets (installes, explorer).
   loadInstalledPlugins : liste des plugins installes localement avec
   actions enable/disable/uninstall.
   renderPluginScope : onglet Explorer (marketplace + filtres).
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
  page.appendChild(el('div', 'page-header', `
    <div class="page-header-text">
      <div class="page-eyebrow"><span class="index">02.</span><span>Extensions</span></div>
      <h1 class="page-title">Plugins</h1>
      <p class="page-subtitle">Plugins Claude Code installés et leur scope par workspace.</p>
    </div>
  `));
  mountHelpLink(page, 'skills-plugins', 'les plugins');

  // Installed
  page.appendChild(el('div', 'section-label', '<span class="num">A.</span> Installés'));
  const installedHost = el('div');
  page.appendChild(installedHost);
  loadInstalledPlugins(installedHost);

  // Per-plugin scope manager
  page.appendChild(el('div', 'section-label', '<span class="num">B.</span> Scope par workspace'));
  const scopeHost = el('div');
  page.appendChild(scopeHost);
  renderPluginScope(scopeHost);

  c.appendChild(page);
}

async function loadInstalledPlugins(host) {
  host['innerHTML'] = '<div class="page-loader"><div class="spinner"></div></div>';
  try {
    const data = await API.get('/api/plugins/installed');
    // API renvoie {cross, on_disk, marketplaces, orphans_on_disk}
    const installed = data.cross || [];
    const orphans = data.orphans_on_disk || [];
    // Stash les marketplaces pour le bouton Installer
    STATE.marketplaces = data.marketplaces || [];

    if (!installed.length && !orphans.length) {
      host['innerHTML'] = '<div class="empty"><div class="empty-title">Aucun plugin installé</div><p class="muted">Clique sur <strong>Installer</strong> pour parcourir les marketplaces.</p></div>';
      return;
    }
    host['innerHTML'] = '';

    if (installed.length) {
      const wrap = el('div', 'table-frame');
      wrap['innerHTML'] = `
        <table class="table">
          <thead><tr><th>Plugin</th><th>Description</th><th>État</th><th></th></tr></thead>
          <tbody></tbody>
        </table>
      `;
      const tb = wrap.querySelector('tbody');
      for (const p of installed) {
        const tr = el('tr');
        const [shortId, mkt] = p.id.includes('@') ? p.id.split('@') : [p.id, null];
        // Lot E item 4 : distinguer 3 états dégradés.
        //   cassé    : activé (enabled) mais absent du disque -> rouge, switch
        //              désactivé (l'activer n'a aucun effet réel).
        //   absent   : présent dans settings.json mais plus sur disque, pas activé
        //              -> neutre (warn), simple constat.
        //   actif/désactivé : sur disque, géré normalement par le switch.
        const broken = p.enabled && !p.on_disk;
        let stateBadge = '';
        if (broken) {
          stateBadge = '<span class="badge badge-err" title="Plugin activé mais introuvable sur le disque -- il ne fait rien. Réinstalle-le ou désinstalle l\'entrée." style="margin-left:6px">cassé</span>';
        } else if (!p.on_disk) {
          stateBadge = '<span class="badge badge-warn" title="Absent du disque" style="margin-left:6px">absent</span>';
        }
        tr['innerHTML'] = `
          <td>
            <div><strong style="font-size:13px">${escapeHtml(shortId)}</strong>${stateBadge}</div>
            ${mkt ? `<div class="dim mono" style="font-size:10.5px">${escapeHtml(mkt)}</div>` : ''}
          </td>
          <td><div class="muted" style="font-size:12.5px;max-width:520px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${escapeHtml(p.description || '')}">${escapeHtml(p.description || '—')}</div></td>
          <td></td>
          <td style="text-align:right"></td>
        `;
        const sw = el('label', 'switch', `<input type="checkbox" aria-label="Activer ${escapeHtml(shortId)}" ${p.enabled ? 'checked' : ''}${!p.on_disk ? ' disabled' : ''}><span class="switch-slider"></span>`);
        // Switch désactivé si le plugin est absent du disque : (dés)activer un
        // plugin introuvable n'a aucun effet -> on évite le faux levier.
        if (!p.on_disk) {
          sw.title = "Plugin absent du disque -- impossible de l'activer tant qu'il n'est pas réinstallé.";
        }
        sw.querySelector('input').addEventListener('change', async (ev) => {
          const url = ev.target.checked ? '/api/plugins/enable' : '/api/plugins/disable';
          ev.target.disabled = true;
          try { await API.post(url, { plugin_id: p.id }); toastOk('Mis à jour'); }
          catch (e) { toastErr(e.message); ev.target.checked = !ev.target.checked; }
          finally { ev.target.disabled = false; }
        });
        tr.children[2].appendChild(sw);

        const actions = tr.children[3];
        const rm = btn('', 'btn-sm btn-ghost btn-icon-only btn-danger', I.trash);
        rm.title = 'Désinstaller';
        rm.addEventListener('click', () => confirmDialog(`Désinstaller ${p.id} ?`, async () => {
          try {
            await API.post('/api/plugins/uninstall-soft', { plugin_id: p.id, remove_files: false });
            toastOk('Désinstallé'); STATE.loading = true; route();
          } catch (e) { toastErr(e.message); }
        }, { danger: true }));
        actions.appendChild(rm);
        tb.appendChild(tr);
      }
      host.appendChild(wrap);
    }

    if (orphans.length) {
      const orphHeader = el('div', 'dim');
      orphHeader.style.cssText = 'font-size:12px;margin:var(--sp-3) 0 var(--sp-2)';
      orphHeader.textContent = `${orphans.length} dossier(s) orphelin(s) sur disque (présents mais non listés dans settings.json)`;
      host.appendChild(orphHeader);
      const wrap = el('div', 'table-frame');
      wrap['innerHTML'] = `<table class="table"><thead><tr><th>Dossier</th><th>Chemin</th></tr></thead><tbody></tbody></table>`;
      const tb = wrap.querySelector('tbody');
      for (const o of orphans) {
        const tr = el('tr');
        tr['innerHTML'] = `<td><span class="mono">${escapeHtml(o.dir_name)}</span></td><td><span class="dim mono" style="font-size:11.5px">${escapeHtml(o.rel_path)}</span></td>`;
        tb.appendChild(tr);
      }
      host.appendChild(wrap);
    }
  } catch (e) { host['innerHTML'] = `<div class="error-box">${escapeHtml(e.message)}</div>`; }
}

async function renderPluginScope(host) {
  host['innerHTML'] = '<div class="page-loader"><div class="spinner"></div></div>';

  const pluginIds = Object.keys(STATE.plugins.enabled || {});
  if (!pluginIds.length) {
    host['innerHTML'] = '<div class="dim" style="font-size:12.5px;padding:var(--sp-3)">Aucun plugin installé pour configurer le scope.</div>';
    return;
  }
  if (!STATE.workspaces.length) {
    host['innerHTML'] = '<div class="dim" style="font-size:12.5px;padding:var(--sp-3)">Aucun workspace.</div>';
    return;
  }

  // UI : sélecteur plugin + filtre workspace + actions de masse + liste
  host['innerHTML'] = `
    <div class="scope-toolbar">
      <div class="field" style="flex:2;margin:0;min-width:240px">
        <label class="field-label">Plugin</label>
        <select class="select" name="plugin">
          ${pluginIds.map(id => `<option value="${escapeHtml(id)}">${escapeHtml(id.split('@')[0])}${id.includes('@') ? ` <span>· ${escapeHtml(id.split('@')[1])}</span>` : ''}</option>`).join('')}
        </select>
      </div>
      <div class="field" style="flex:1;margin:0;min-width:200px">
        <label class="field-label">Filtrer workspaces</label>
        <input class="input input-search" name="filter" placeholder="Recherche…">
      </div>
      <div class="scope-bulk">
        <span class="dim" style="font-size:11px;text-transform:uppercase;letter-spacing:0.1em">Masse :</span>
        <button class="btn btn-sm" data-bulk="on">Activer tout</button>
        <button class="btn btn-sm" data-bulk="off">Désactiver tout</button>
        <button class="btn btn-sm btn-ghost" data-bulk="reset">Réinitialiser</button>
      </div>
    </div>
    <div class="scope-summary"></div>
    <div class="scope-list"></div>
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
      <div class="row" style="gap:var(--sp-3);font-size:12px;margin:var(--sp-3) 0;color:var(--text-muted)">
        <span><strong class="text-ok tabular">${active}</strong> override actif</span>
        <span><strong class="text-err tabular">${disabled}</strong> override désactivé</span>
        <span class="dim"><strong class="tabular">${inheritOn + inheritOff}</strong> hérités du global (${inheritOn} actifs)</span>
      </div>
    `;

    if (!filtered.length) {
      listEl['innerHTML'] = '<div class="dim" style="padding:var(--sp-3);font-size:12.5px">Aucun workspace ne correspond.</div>';
      return;
    }

    listEl['innerHTML'] = '';
    for (const w of filtered) {
      const info = cache[w.id];
      const state = stateOf(info);
      const row = el('div', 'scope-row');
      row['innerHTML'] = `
        <span class="workspace-emoji" style="font-size:20px">${escapeHtml(w.emoji || '📁')}</span>
        <div class="scope-row-main">
          <div class="scope-row-name">${escapeHtml(w.label || w.id)}</div>
          <div class="dim mono" style="font-size:10.5px">${escapeHtml(w.id)}</div>
        </div>
        <div class="scope-state-badge state-${state}"></div>
        <div class="seg-control">
          <button data-set="on" class="${state === 'on' ? 'is-active' : ''}" title="Activé pour ce workspace">Actif</button>
          <button data-set="off" class="${state === 'off' ? 'is-active' : ''}" title="Désactivé pour ce workspace">Inactif</button>
          <button data-set="reset" class="${state.startsWith('inherit') ? 'is-active' : ''}" title="Hériter du global (${info && info.global ? 'actif' : 'inactif'} actuellement)">Hériter</button>
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
      });
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
