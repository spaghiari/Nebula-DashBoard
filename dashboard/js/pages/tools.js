/* ================================================================
   Nebula - Page Tools (Outils)
   ----------------------------------------------------------------
   renderTools : page Outils avec sections Demarrage / Apparence /
   Acces rapide / Hooks globaux / Variables d'env / Sauvegardes.
   loadEnvVars : panneau .env.local avec DPAPI encrypt/decrypt + CRUD
   par cle, groupement par prefixe avant le premier underscore.
   loadBackups : liste des derniers backups + bouton "Sauvegarder maintenant".

   Dependances foundations : STATE, API, escapeHtml, el, btn, debounce,
   fmtDate, fmtBytes, I.*, setBreadcrumbs, setTopbarActions, toastOk,
   toastErr, confirmDialog, THEMES, getCurrentTheme, applyTheme.
   Forward-refs (app.js) : resetOnboarded, startFirstRunWizard,
   modalSystemUpdate, modalHooks, modalHooksErrorsViewer.

   Ref : CM-2 batch 6, refactor 2026-05-13.
   ================================================================ */
'use strict';

async function renderTools() {
  setBreadcrumbs([{ label: 'Outils' }]);
  setTopbarActions([]);

  const c = $('#content');
  c['innerHTML'] = '';
  const page = el('div', 'page');
  page.appendChild(el('div', 'page-header', `
    <div class="page-header-text">
      <div class="page-eyebrow"><span class="index">04.</span><span>Système</span></div>
      <h1 class="page-title">Outils</h1>
      <p class="page-subtitle">Accès rapide aux fichiers de configuration et utilitaires.</p>
    </div>
  `));

  const stack = el('div', 'tools-stack');

  // Demarrage -- note de redirection vers Home (la checklist complete y vit)
  stack.appendChild(el('div', 'section-label', '<span class="num">A.</span> Démarrage'));
  const startupNote = el('div', 'card');
  const startupP = document.createElement('p');
  startupP.className = 'muted';
  startupP.style.cssText = 'margin:0;font-size:13px';
  startupP.appendChild(document.createTextNode("L'état d'avancement de la mise en route est affiché sur la page "));
  const startupLink = document.createElement('a');
  startupLink.href = '#/';
  startupLink.style.color = 'var(--accent)';
  startupLink.textContent = 'Accueil';
  startupP.appendChild(startupLink);
  startupP.appendChild(document.createTextNode(" tant que la checklist n'est pas complète."));
  startupNote.appendChild(startupP);
  stack.appendChild(startupNote);

  // Apparence -- selecteur de theme
  stack.appendChild(el('div', 'section-label', '<span class="num">B.</span> Apparence & assistance'));
  const themeCard = el('div', 'card');
  themeCard['innerHTML'] = `<p class="muted" style="margin:0 0 var(--sp-3);font-size:13px">Choisis l'ambiance visuelle de ton dashboard. Le choix est mémorisé localement.</p>`;
  const themeGrid = el('div', 'theme-grid');
  const current = getCurrentTheme();
  for (const t of THEMES) {
    const card = el('button', 'theme-card' + (t.id === current ? ' is-active' : ''));
    card.type = 'button';
    card.dataset.theme = t.id;
    card['innerHTML'] = `
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
      themeGrid.querySelectorAll('.theme-card').forEach(c => c.classList.toggle('is-active', c.dataset.theme === t.id));
      toastOk(`Thème : ${t.label}`);
    });
    themeGrid.appendChild(card);
  }
  themeCard.appendChild(themeGrid);

  // Bouton "Rejouer le tutoriel"
  const tutorialRow = el('div');
  tutorialRow.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:var(--sp-3);margin-top:var(--sp-4);padding-top:var(--sp-3);border-top:1px solid var(--border)';
  tutorialRow['innerHTML'] = `
    <div>
      <div style="font-size:13px;font-weight:500;margin-bottom:2px">Tutoriel d'introduction</div>
      <div class="dim" style="font-size:11.5px">Le wizard de premier lancement (thème, import config, raccourcis…)</div>
    </div>
  `;
  const replayBtn = btn('Rejouer le tutoriel', 'btn-sm', I.sparkle);
  replayBtn.addEventListener('click', () => {
    resetOnboarded();
    startFirstRunWizard();
  });
  tutorialRow.appendChild(replayBtn);
  themeCard.appendChild(tutorialRow);

  // Verifier les mises a jour
  const updateRow = el('div');
  updateRow.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:var(--sp-3);margin-top:var(--sp-3);padding-top:var(--sp-3);border-top:1px solid var(--border)';
  updateRow['innerHTML'] = `
    <div>
      <div style="font-size:13px;font-weight:500;margin-bottom:2px">Mises à jour</div>
      <div class="dim" style="font-size:11.5px">Synchronisation avec le dépôt git officiel d'Nebula</div>
    </div>
  `;
  const updateBtn = btn('Vérifier maintenant', 'btn-sm', I.refresh);
  updateBtn.addEventListener('click', () => modalSystemUpdate());
  updateRow.appendChild(updateBtn);
  themeCard.appendChild(updateRow);

  stack.appendChild(themeCard);

  // Quick open
  stack.appendChild(el('div', 'section-label', '<span class="num">C.</span> Accès rapide'));
  const quick = el('div', 'quick-grid');
  const quickItems = [
    { label: '~/.claude.json', target: 'claude-json' },
    { label: '~/.claude/settings.json', target: 'claude-settings' },
    { label: 'Root CLAUDE.md', target: 'root-claude-md' },
    { label: 'mcp/registry.json', target: 'registry' },
    { label: '.env.local', target: 'env-local' },
    { label: 'workspaces.json', target: 'workspaces-json' },
    { label: 'memory/', target: 'global-memory' },
  ];
  for (const it of quickItems) {
    const b = el('button', 'quick-btn', `${I.folder}<span>${escapeHtml(it.label)}</span>`);
    b.addEventListener('click', async () => {
      try { const r = await API.post('/api/open', { target: it.target }); toastOk(r.message); }
      catch (e) { toastErr(e.message); }
    });
    quick.appendChild(b);
  }
  stack.appendChild(quick);

  // Hooks globaux + log d'erreurs
  stack.appendChild(el('div', 'section-label', '<span class="num">D.</span> Hooks globaux'));
  const hooksCard = el('div', 'card');
  hooksCard['innerHTML'] = `<div class="dim" style="font-size:12px;margin-bottom:var(--sp-2)">Édition complète via la modale. Le viewer d'erreurs ne couvre actuellement que les hooks réflexifs ; les autres hooks .sh écrivent leur stderr dans le transcript Claude Code, pas dans un log.</div>`;
  const hooksRow = el('div');
  hooksRow.style.cssText = 'display:flex;gap:var(--sp-2);flex-wrap:wrap';
  const hooksBtn = btn('Éditer hooks globaux', 'btn', I.zap);
  hooksBtn.addEventListener('click', () => modalHooks(null));
  const hooksLogBtn = btn('Erreurs hooks récentes', 'btn-ghost', I.alert);
  hooksLogBtn.title = "Voir les dernières erreurs des hooks réflexifs";
  hooksLogBtn.addEventListener('click', () => modalHooksErrorsViewer());
  hooksRow.append(hooksBtn, hooksLogBtn);
  hooksCard.appendChild(hooksRow);
  stack.appendChild(hooksCard);

  // Env vars
  stack.appendChild(el('div', 'section-label', '<span class="num">E.</span> Variables d\'environnement'));
  const envHost = el('div');
  stack.appendChild(envHost);
  loadEnvVars(envHost);

  // Backups
  stack.appendChild(el('div', 'section-label', '<span class="num">F.</span> Sauvegardes'));
  const backupHost = el('div');
  stack.appendChild(backupHost);
  loadBackups(backupHost);

  page.appendChild(stack);
  c.appendChild(page);
}

async function loadEnvVars(host) {
  host['innerHTML'] = '<div class="page-loader"><div class="spinner"></div></div>';
  try {
    const r = await API.get('/api/env/values');
    const vals = r.values || {};
    const allKeys = Object.keys(vals).sort((a, b) => a.localeCompare(b));
    const fileExists = !!r.exists;
    const encrypted = !!r.encrypted;
    const decErr = r.decryption_error || null;
    const wrap = el('div', 'card');
    const encBadge = encrypted
      ? '<span class="badge badge-ok" style="margin-left:6px" title="Chiffré via DPAPI Windows (compte utilisateur)">🔒 Chiffré (DPAPI)</span>'
      : (fileExists ? '<span class="badge badge-warn" style="margin-left:6px" title="Fichier en clair sur disque">⚠ Clair</span>' : '');
    const missBadge = (!fileExists && !encrypted) ? ' <span class="badge badge-warn" style="margin-left:6px">.env.local absent</span>' : '';
    wrap['innerHTML'] = `<div class="card-header" style="display:flex;align-items:center;justify-content:space-between;gap:var(--sp-2);flex-wrap:wrap"><h3 class="card-title">${allKeys.length} variable${allKeys.length > 1 ? 's' : ''}${encBadge}${missBadge}</h3><div data-enc-actions style="display:flex;gap:6px"></div></div>`;

    const encActions = wrap.querySelector('[data-enc-actions]');
    if (!encrypted) {
      const enableBtn = btn('Activer le chiffrement', 'btn-sm', I.key);
      enableBtn.title = 'Chiffre .env.local avec DPAPI (clé liée à ton compte Windows)';
      enableBtn.addEventListener('click', () => {
        confirmDialog(
          'Activer le chiffrement DPAPI ?\n\nLe fichier sera lié à ton compte Windows. Si tu réinstalles ou changes de poste, les secrets seront illisibles -- pense à exporter en clair pour backup avant.\n\nUn fichier .env.local.bak.<date> sera conservé.',
          async () => {
            try { const res = await API.post('/api/env/encrypt', {}); toastOk(`Chiffré (${res.keys} clé${res.keys > 1 ? 's' : ''})`); loadEnvVars(host); }
            catch (e) { toastErr(e.message); }
          }
        );
      });
      encActions.appendChild(enableBtn);
    } else {
      const disableBtn = btn('Désactiver / Exporter clair', 'btn-sm btn-ghost', I.unlock || I.key);
      disableBtn.title = 'Déchiffre et écrit .env.local en clair, supprime le fichier chiffré';
      disableBtn.addEventListener('click', () => {
        confirmDialog(
          'Désactiver le chiffrement ?\n\nLe fichier .env.local sera réécrit en clair sur disque. Pratique pour un backup hors-poste ou pour migrer. Pense à le supprimer ou à réactiver le chiffrement après.',
          async () => {
            try { const res = await API.post('/api/env/decrypt', {}); toastOk(`Déchiffré (${res.keys} clé${res.keys > 1 ? 's' : ''})`); loadEnvVars(host); }
            catch (e) { toastErr(e.message); }
          },
          { danger: true }
        );
      });
      encActions.appendChild(disableBtn);
    }

    if (decErr) {
      const errBox = el('div', 'callout callout-warn');
      errBox.style.marginBottom = 'var(--sp-3)';
      errBox['innerHTML'] = `
        <div>
          <strong>⚠ Déchiffrement impossible</strong>
          <p style="margin:4px 0 0;font-size:12.5px">Le fichier <code class="mono">.env.local.enc</code> est présent mais ne peut pas être déchiffré sur ce poste / compte utilisateur. Détail : <code class="mono">${escapeHtml(decErr)}</code>.</p>
          <p style="margin:4px 0 0;font-size:12.5px" class="dim">Probable changement de compte Windows, machine, ou profil corrompu. Si tu as un backup clair, restaure-le et réactive le chiffrement.</p>
        </div>
      `;
      wrap.appendChild(errBox);
    }

    if (!allKeys.length) {
      const intro = el('div', 'callout callout-info');
      intro.style.marginBottom = 'var(--sp-3)';
      intro['innerHTML'] = `
        <div>
          <strong>🔐 Stockage centralisé pour tes secrets</strong>
          <p style="margin:4px 0 6px;font-size:12.5px">
            <code class="mono">.env.local</code> est un fichier à la racine de Nebula où tu mets tes tokens, API keys, mots de passe.
            Tu y fais référence dans n'importe quel champ MCP avec <code class="mono">\${KEY}</code> -- Nebula substitue à la sync vers les workspaces.
            Le fichier reste local, jamais commité.
          </p>
          <pre class="help-code" style="margin:4px 0 6px;font-size:11.5px">GITHUB_TOKEN=ghp_xxxxxxxxxxxx
OPENAI_API_KEY=sk-xxxxxxxxxxxx
DB_PASSWORD=mon_mot_de_passe</pre>
          <p style="margin:0;font-size:11.5px" class="dim">
            ${fileExists
              ? `Le fichier existe (<code class="mono">${escapeHtml(r.file || '.env.local')}</code>) mais est vide. Ajoute ta première variable ci-dessous.`
              : `Le fichier sera <strong>créé automatiquement</strong> à ton premier ajout (chemin : <code class="mono">${escapeHtml(r.file || '.env.local')}</code>).`}
          </p>
        </div>
      `;
      wrap.appendChild(intro);
    }

    const toolbar = el('div');
    toolbar.style.cssText = 'display:flex;gap:var(--sp-2);margin-bottom:var(--sp-3);flex-wrap:wrap';
    toolbar['innerHTML'] = `<input class="input input-search" name="filter" placeholder="Filtrer…" style="flex:1;min-width:200px">`;
    wrap.appendChild(toolbar);

    const addRow = el('form');
    addRow.style.cssText = 'display:flex;gap:8px;margin-bottom:var(--sp-3)';
    addRow['innerHTML'] = `<input class="input mono" name="k" placeholder="KEY (ex. OPENAI_API_KEY)" style="max-width:260px"><input class="input" name="v" placeholder="value" style="flex:1">`;
    const addBtn = btn('Ajouter', 'btn-primary btn-sm', I.plus);
    addBtn.type = 'submit';
    addRow.appendChild(addBtn);
    addRow.addEventListener('submit', async (e) => {
      e.preventDefault();
      const k = addRow.querySelector('[name=k]').value.trim();
      const v = addRow.querySelector('[name=v]').value;
      if (!k) return;
      try { await API.post('/api/env', { key: k, value: v }); toastOk('Ajouté'); loadEnvVars(host); }
      catch (e) { toastErr(e.message); }
    });
    wrap.appendChild(addRow);

    if (!allKeys.length) {
      host['innerHTML'] = ''; host.appendChild(wrap);
      return;
    }

    const listHost = el('div');
    wrap.appendChild(listHost);

    const renderList = () => {
      const filter = (toolbar.querySelector('[name=filter]').value || '').trim().toLowerCase();
      const keys = filter
        ? allKeys.filter(k => k.toLowerCase().includes(filter) || (vals[k] || '').toLowerCase().includes(filter))
        : allKeys;
      if (!keys.length) {
        listHost['innerHTML'] = '<div class="dim" style="padding:var(--sp-3);font-size:12.5px">Aucun résultat.</div>';
        return;
      }
      // Groupement par prefixe avant le premier "_"
      const groups = {};
      for (const k of keys) {
        const prefix = k.includes('_') ? k.split('_')[0] : '_misc';
        (groups[prefix] = groups[prefix] || []).push(k);
      }
      const groupNames = Object.keys(groups).sort((a, b) => {
        if (a === '_misc') return 1;
        if (b === '_misc') return -1;
        return a.localeCompare(b);
      });

      listHost['innerHTML'] = '';
      for (const grpName of groupNames) {
        const grpHeader = el('div');
        grpHeader.style.cssText = 'font-family:var(--font-mono);font-size:10px;letter-spacing:0.16em;text-transform:uppercase;color:var(--text-dim);padding:var(--sp-3) 4px var(--sp-2);display:flex;align-items:center;gap:var(--sp-2)';
        grpHeader['innerHTML'] = `<span>${grpName === '_misc' ? 'Divers' : escapeHtml(grpName)}</span><span class="tabular dim" style="font-size:9.5px">(${groups[grpName].length})</span><span style="flex:1;height:1px;background:linear-gradient(90deg,var(--border),transparent)"></span>`;
        listHost.appendChild(grpHeader);

        const tbl = el('div', 'table-frame');
        tbl.style.marginBottom = 'var(--sp-2)';
        tbl['innerHTML'] = `<table class="table"><tbody></tbody></table>`;
        const tb = tbl.querySelector('tbody');
        for (const k of groups[grpName]) {
          const tr = el('tr');
          tr['innerHTML'] = `
            <td style="width:280px"><span class="mono" style="font-size:12.5px">${escapeHtml(k)}</span></td>
            <td class="mono" data-cell-val style="font-size:12.5px;color:var(--text-muted);max-width:520px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"><span data-revealed="0" data-real="${escapeHtml(vals[k])}">••••••••</span></td>
            <td style="text-align:right;width:120px;white-space:nowrap"></td>
          `;
          const valCell = tr.querySelector('[data-cell-val]');
          const valSpan = tr.querySelector('[data-real]');
          const eyeBtn = el('button', 'icon-btn btn-icon-only', I.eye);
          eyeBtn.title = 'Afficher / masquer';
          eyeBtn.addEventListener('click', () => {
            const shown = valSpan.dataset.revealed === '1';
            valSpan.textContent = shown ? '••••••••' : valSpan.dataset.real;
            valSpan.dataset.revealed = shown ? '0' : '1';
            eyeBtn['innerHTML'] = shown ? I.eye : I.eyeoff;
          });
          const editBtn = el('button', 'icon-btn btn-icon-only', I.edit);
          editBtn.title = 'Modifier';
          editBtn.addEventListener('click', () => {
            const current = valSpan.dataset.real;
            const input = document.createElement('input');
            input.className = 'input mono';
            input.type = 'text';
            input.value = current;
            input.style.cssText = 'width:100%;font-size:12.5px;padding:4px 8px';
            valCell.replaceChildren(input);
            input.focus();
            input.select();
            let done = false;
            const save = async () => {
              if (done) return; done = true;
              const newVal = input.value;
              if (newVal === current) { loadEnvVars(host); return; }
              try { await API.post('/api/env', { key: k, value: newVal }); toastOk('Modifié'); loadEnvVars(host); }
              catch (e) { toastErr(e.message); loadEnvVars(host); }
            };
            const cancel = () => { if (done) return; done = true; loadEnvVars(host); };
            input.addEventListener('keydown', (ev) => {
              if (ev.key === 'Enter') { ev.preventDefault(); save(); }
              else if (ev.key === 'Escape') { ev.preventDefault(); cancel(); }
            });
            input.addEventListener('blur', save);
          });
          const rm = el('button', 'icon-btn btn-icon-only btn-danger', I.trash);
          rm.title = 'Supprimer';
          rm.addEventListener('click', () => confirmDialog(`Supprimer ${k} ?`, async () => {
            try { await API.del('/api/env/' + encodeURIComponent(k)); toastOk('Supprimé'); loadEnvVars(host); }
            catch (e) { toastErr(e.message); }
          }, { danger: true }));
          tr.children[2].append(eyeBtn, editBtn, rm);
          tb.appendChild(tr);
        }
        listHost.appendChild(tbl);
      }
    };
    toolbar.querySelector('[name=filter]').addEventListener('input', debounce(renderList, 100));
    renderList();

    host['innerHTML'] = ''; host.appendChild(wrap);
  } catch (e) { host['innerHTML'] = `<div class="error-box">${escapeHtml(e.message)}</div>`; }
}

async function loadBackups(host) {
  host['innerHTML'] = '<div class="page-loader"><div class="spinner"></div></div>';
  try {
    const r = await API.get('/api/backups');
    const wrap = el('div', 'card');
    wrap['innerHTML'] = `<div class="card-header"><h3 class="card-title">${r.items.length} sauvegarde${r.items.length > 1 ? 's' : ''}</h3></div>`;
    const b = btn('Sauvegarder maintenant', 'btn-primary btn-sm', I.archive);
    b.style.marginBottom = 'var(--sp-3)';
    b.addEventListener('click', async () => {
      try { const r2 = await API.post('/api/backup', {}); toastOk(r2.message); loadBackups(host); }
      catch (e) { toastErr(e.message); }
    });
    wrap.appendChild(b);
    if (!r.items.length) {
      wrap.appendChild(el('div', 'dim', '<small>Aucune sauvegarde pour le moment.</small>'));
    } else {
      const list = el('div', 'stack');
      for (const it of r.items.slice(0, 10)) {
        const row = el('div', 'list-row');
        row['innerHTML'] = `<div class="list-row-main"><div class="list-row-name mono">${escapeHtml(it.name)}</div><div class="list-row-desc">${fmtDate(it.mtime)} · ${fmtBytes(it.size)}</div></div>`;
        list.appendChild(row);
      }
      wrap.appendChild(list);
    }
    host['innerHTML'] = ''; host.appendChild(wrap);
  } catch (e) { host['innerHTML'] = `<div class="error-box">${escapeHtml(e.message)}</div>`; }
}
