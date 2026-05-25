/* ================================================================
   Nebula - Page Reflexive (boucle reflexive autonome)
   ----------------------------------------------------------------
   renderReflexive : page Reflexive avec 4 onglets (overview,
   interactions, proposals, measurements).
   renderReflexiveOverview : KPIs + dim bars.
   renderReflexiveInteractions : liste paginee des interactions.
   modalReflexiveInteraction : detail d'une interaction.
   renderReflexiveProposals : liste des propositions extraites.
   modalRejectProposal : modal de rejet avec raison.
   renderReflexiveMeasurements : metriques de la collecte.
   Helpers : refxScore, refxTrend, refxSparkline, refxDimBar,
   refxLoader, refxEmpty, refxKpi.

   Dependances foundations : STATE, API, escapeHtml, el, btn, I.*,
   setBreadcrumbs, setTopbarActions, openModal, toastOk, toastErr,
   confirmDialog, registerPagePoller.

   Ref : CM-2 batch 9, refactor 2026-05-13.
   ================================================================ */
'use strict';

const REFX_TABS = [
  ['overview',     "Vue d'ensemble"],
  ['interactions', 'Interactions'],
  ['proposals',    'Propositions'],
  ['measurements', 'Mesures en cours'],
];

function refxScore(v, denom = 12) {
  if (v == null) return '—';
  return Number(v).toFixed(1) + ' / ' + denom;
}

function refxTrend(curr, prev) {
  if (curr == null || prev == null) return '';
  const d = curr - prev;
  const span = document.createElement('span');
  if (Math.abs(d) < 0.05) {
    span.className = 'refx-trend refx-trend-flat';
    span.textContent = '±0';
  } else if (d > 0) {
    span.className = 'refx-trend refx-trend-up';
    span.textContent = '↑ +' + d.toFixed(1);
  } else {
    span.className = 'refx-trend refx-trend-down';
    span.textContent = '↓ ' + d.toFixed(1);
  }
  return span.outerHTML;
}

function refxSparkline(series) {
  if (!series || series.length === 0) return '';
  const W = 600, H = 120, PAD = 8;
  const vals = series.map(p => p.avg_total).filter(v => v != null);
  if (vals.length === 0) return '';
  const max = Math.max(...vals, 12);
  const min = Math.min(...vals, 0);
  const range = (max - min) || 1;
  const stepX = (W - 2 * PAD) / Math.max(1, series.length - 1);
  let d = '';
  series.forEach((p, i) => {
    if (p.avg_total == null) return;
    const x = PAD + i * stepX;
    const y = H - PAD - ((p.avg_total - min) / range) * (H - 2 * PAD);
    d += (d ? ' L' : 'M') + x.toFixed(1) + ',' + y.toFixed(1);
  });
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('class', 'refx-spark');
  svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
  svg.setAttribute('preserveAspectRatio', 'none');
  svg.setAttribute('role', 'img');
  svg.setAttribute('aria-label', 'Courbe de progression du score');
  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('d', d);
  path.setAttribute('fill', 'none');
  path.setAttribute('stroke', 'var(--accent)');
  path.setAttribute('stroke-width', '2');
  path.setAttribute('stroke-linejoin', 'round');
  path.setAttribute('stroke-linecap', 'round');
  svg.appendChild(path);
  return svg.outerHTML;
}

/* ================================================================
   PAGE REFLEXIVE (overview + interactions + propositions + mesures)
   ================================================================ */
async function renderReflexive() {
  const hash = location.hash || '#/reflexive';
  const sub = hash.replace(/^#\/reflexive\/?/, '') || 'overview';
  const tab = REFX_TABS.some(t => t[0] === sub) ? sub : 'overview';

  setBreadcrumbs([{ label: 'Reflexive' }]);

  // Diagnostic automatique : le backend est encore un stub (501). Plutôt
  // qu'un bouton actif qui échoue avec un message dev brut, on l'affiche
  // désactivé avec un libellé/tooltip explicite. Sera réactivé quand le
  // diagnostician sera implémenté (lot C de l'audit UX 2026-05-25).
  const runBtn = btn('Diagnostic automatique — bientôt disponible', 'btn-primary', I.sparkle);
  runBtn.disabled = true;
  runBtn.title = "Le diagnostic automatique (génération de propositions à partir des évaluations) est en cours de déploiement.";
  setTopbarActions([runBtn]);

  const c = $('#content');
  c['innerHTML'] = '';

  const page = el('div', 'page');
  const header = el('div', 'page-header');
  const headerText = el('div', 'page-header-text');
  const eyebrow = el('div', 'page-eyebrow');
  const idx = el('span', 'index'); idx.textContent = '06.';
  const lbl = el('span'); lbl.textContent = 'Réflexion';
  eyebrow.appendChild(idx); eyebrow.appendChild(lbl);
  const h1 = el('h1', 'page-title'); h1.textContent = 'Reflexive';
  const sub2 = el('p', 'page-subtitle');
  sub2.textContent = "Observe, score et améliore Claude au fil des sessions. Active la boucle par workspace.";
  headerText.appendChild(eyebrow); headerText.appendChild(h1); headerText.appendChild(sub2);
  header.appendChild(headerText);
  page.appendChild(header);
  mountHelpLink(page, 'reflexive', 'la boucle Reflexive');

  const tabs = el('nav', 'tabs');
  tabs.setAttribute('aria-label', 'Sections Reflexive');
  // Pastille « propositions en attente » sur l'onglet Propositions (lot E
  // item 3). On réutilise le compteur déjà calculé pour le badge sidebar
  // (alimenté au boot / après action) -- aucun appel réseau supplémentaire.
  const pendingForTab = (function () {
    const b = $('.nav-link[data-id="reflexive"] [data-nav-badge]', $('#sidebar'));
    if (!b || b.hidden) return 0;
    const n = parseInt(b.textContent, 10);
    return Number.isFinite(n) ? n : 0;
  })();
  for (const [id, label] of REFX_TABS) {
    const a = document.createElement('a');
    a.href = id === 'overview' ? '#/reflexive' : '#/reflexive/' + id;
    a.className = 'tab' + (id === tab ? ' active' : '');
    a.textContent = label;
    if (id === 'proposals' && pendingForTab > 0) {
      const pill = el('span', 'tab-badge');
      pill.textContent = pendingForTab > 99 ? '99+' : String(pendingForTab);
      pill.title = `${pendingForTab} proposition(s) en attente`;
      a.appendChild(pill);
    }
    tabs.appendChild(a);
  }
  page.appendChild(tabs);

  const body = el('div', 'refx-body');
  page.appendChild(body);
  c.appendChild(page);

  if (tab === 'overview')          await renderReflexiveOverview(body);
  else if (tab === 'interactions') await renderReflexiveInteractions(body);
  else if (tab === 'proposals')    await renderReflexiveProposals(body);
  else if (tab === 'measurements') await renderReflexiveMeasurements(body);
}

function refxDimBar(label, value, max = 10) {
  const v = value == null ? 0 : Math.max(0, Math.min(max, value));
  const pct = (v / max) * 100;
  const display = value == null ? '—' : value.toFixed(1) + '/' + max;
  const wrap = el('div', 'refx-dim');
  const lab = el('span', 'refx-dim-label'); lab.textContent = label;
  const track = el('span', 'refx-dim-track');
  const fill = el('span', 'refx-dim-fill');
  fill.style.width = pct.toFixed(1) + '%';
  track.appendChild(fill);
  const val = el('span', 'refx-dim-val mono'); val.textContent = display;
  wrap.appendChild(lab); wrap.appendChild(track); wrap.appendChild(val);
  return wrap;
}

function refxLoader(host) {
  host['innerHTML'] = '';
  const loader = el('div', 'page-loader');
  loader.appendChild(el('div', 'spinner'));
  const span = el('span'); span.textContent = 'Chargement…';
  loader.appendChild(span);
  host.appendChild(loader);
}

function refxEmpty(host, title, hint) {
  host['innerHTML'] = '';
  const card = el('div', 'card empty');
  const p1 = el('p', 'muted'); p1.textContent = title;
  card.appendChild(p1);
  if (hint) {
    const p2 = el('p', 'muted');
    p2.style.fontSize = '12px';
    p2.textContent = hint;
    card.appendChild(p2);
  }
  host.appendChild(card);
}

function refxKpi(label, value, sub) {
  const card = el('div', 'card refx-kpi');
  const l = el('div', 'refx-kpi-label'); l.textContent = label;
  const v = el('div', 'refx-kpi-value mono'); v.textContent = value;
  card.appendChild(l); card.appendChild(v);
  if (sub) {
    const s = el('div', 'refx-kpi-sub');
    if (sub instanceof Node) s.appendChild(sub);
    else s.textContent = sub;
    card.appendChild(s);
  }
  return card;
}

async function renderReflexiveOverview(host) {
  refxLoader(host);
  const stats = await safe('/api/reflexive/stats?days=30', null);
  host['innerHTML'] = '';
  if (!stats) {
    refxEmpty(host, 'Stats indisponibles — vérifie que le backend est joignable.');
    return;
  }

  const kpiRow = el('div', 'refx-kpi-row');
  // Score moyen : DB stocke un total /40 (somme des 4 dims), on affiche
  // la moyenne par dimension sur 12 (plafond visuel, max réel = 10).
  const avgPerDim = stats.avg_total != null ? stats.avg_total / 4 : null;
  const prevPerDim = stats.avg_total_prev != null ? stats.avg_total_prev / 4 : null;
  const trendSub = el('span');
  if (avgPerDim != null && prevPerDim != null) {
    const d = avgPerDim - prevPerDim;
    let cls = 'refx-trend-flat', txt = '±0';
    if (Math.abs(d) >= 0.05) {
      cls = d > 0 ? 'refx-trend-up' : 'refx-trend-down';
      txt = (d > 0 ? '↑ +' : '↓ ') + d.toFixed(1);
    }
    trendSub.className = 'refx-trend ' + cls;
    trendSub.textContent = txt;
  } else {
    trendSub.className = 'muted';
    trendSub.textContent = 'pas encore de tendance';
  }
  kpiRow.appendChild(refxKpi('Score moyen (30j)', refxScore(avgPerDim), trendSub));

  const interSub = el('span', 'muted'); interSub.textContent = 'sur 30 derniers jours';
  kpiRow.appendChild(refxKpi('Interactions', fmtNum(stats.interactions), interSub));

  const propSub = document.createElement('a');
  propSub.className = 'link';
  propSub.href = '#/reflexive/proposals';
  propSub.textContent = 'Voir →';
  kpiRow.appendChild(refxKpi('Propositions en attente', fmtNum(stats.proposals_pending), propSub));

  host.appendChild(kpiRow);

  // Synchronise le badge sidebar avec les stats déjà chargées (pas de re-fetch).
  setNavBadge('reflexive', stats.proposals_pending);

  // Sparkline
  const sparkCard = el('div', 'card');
  const eb = el('div', 'card-eyebrow'); eb.textContent = 'Progression du score · 30 derniers jours';
  sparkCard.appendChild(eb);
  if (!stats.series || !stats.series.some(p => p.avg_total != null)) {
    const empty = el('div', 'refx-spark-empty');
    empty.textContent = 'Aucune donnée encore — active Reflexive sur un workspace pour commencer.';
    sparkCard.appendChild(empty);
  } else {
    // Convertir sum-of-4-dims (0-40) → moyenne par dim (0-10) pour rester
    // cohérent avec le KPI "Score moyen"
    const seriesPerDim = stats.series.map(p => ({
      day: p.day,
      avg_total: p.avg_total != null ? p.avg_total / 4 : null,
      n: p.n,
    }));
    const wrap = el('div'); wrap['innerHTML'] = refxSparkline(seriesPerDim);
    sparkCard.appendChild(wrap);
  }
  host.appendChild(sparkCard);

  // Dimensions
  const dims = stats.dimensions || {};
  const dimCard = el('div', 'card');
  const eb2 = el('div', 'card-eyebrow'); eb2.textContent = 'Score par dimension';
  dimCard.appendChild(eb2);
  const dimWrap = el('div', 'refx-dims');
  dimWrap.appendChild(refxDimBar('Correctness', dims.correctness));
  dimWrap.appendChild(refxDimBar('Efficiency',  dims.efficiency));
  dimWrap.appendChild(refxDimBar('Alignment',   dims.alignment));
  dimWrap.appendChild(refxDimBar('Learning',    dims.learning));
  dimCard.appendChild(dimWrap);
  host.appendChild(dimCard);

  // Workspaces
  const wsCard = el('div', 'card refx-ws-card');
  const wsLeft = el('div');
  const eb3 = el('div', 'card-eyebrow'); eb3.textContent = 'Workspaces observés';
  const count = el('div', 'refx-ws-count mono');
  count.textContent = stats.workspaces_enabled + ' / ' + stats.workspaces_total;
  const hint = el('p', 'muted');
  hint.style.cssText = 'margin:6px 0 0;font-size:12px';
  hint.textContent = "Active Reflexive sur un workspace depuis sa fiche pour qu'il soit observé.";
  wsLeft.appendChild(eb3); wsLeft.appendChild(count); wsLeft.appendChild(hint);
  wsCard.appendChild(wsLeft);
  const goBtn = btn('Gérer les workspaces', 'btn-sm', I.right);
  goBtn.addEventListener('click', () => location.hash = '#/');
  wsCard.appendChild(goBtn);
  host.appendChild(wsCard);
}

async function renderReflexiveInteractions(host) {
  refxLoader(host);
  const data = await safe('/api/reflexive/interactions?limit=100', { items: [], total: 0 });
  host['innerHTML'] = '';
  if (!data.items.length) {
    refxEmpty(host,
      "Aucune interaction enregistrée pour l'instant.",
      "Active Reflexive sur un workspace et lance une session Claude pour commencer.");
    return;
  }
  const table = el('table', 'data-table');
  const thead = el('thead');
  const trh = el('tr');
  for (const h of ['Démarré', 'Workspace', 'Tâche', 'Outcome', 'Score', 'Flags']) {
    const th = el('th'); th.textContent = h; trh.appendChild(th);
  }
  thead.appendChild(trh); table.appendChild(thead);
  const tbody = el('tbody');
  for (const it of data.items) {
    const tr = el('tr', 'refx-row');
    tr.tabIndex = 0;
    tr.setAttribute('role', 'button');
    tr.setAttribute('aria-label', "Voir le détail de l'interaction");
    const td1 = el('td', 'mono dim'); td1.textContent = fmtDate(it.started_at);
    const td2 = el('td'); td2.textContent = it.workspace_id || '—';
    const td3 = el('td');
    const sumDiv = el('div', 'refx-summary');
    sumDiv.textContent = it.task_summary || '(non résumée)';
    sumDiv.title = it.task_summary || '';
    td3.appendChild(sumDiv);
    const td4 = el('td');
    const oc = it.outcome || 'unknown';
    const ocSpan = el('span', 'refx-outcome refx-outcome-' + oc); ocSpan.textContent = oc;
    td4.appendChild(ocSpan);
    const td5 = el('td', 'mono');
    td5.textContent = it.eval_total != null ? (it.eval_total + '/40') : '—';
    const td6 = el('td');
    const flags = Array.isArray(it.eval_flags) ? it.eval_flags : [];
    for (const f of flags) {
      const chip = el('span', 'chip'); chip.textContent = f; td6.appendChild(chip);
      td6.appendChild(document.createTextNode(' '));
    }
    tr.appendChild(td1); tr.appendChild(td2); tr.appendChild(td3);
    tr.appendChild(td4); tr.appendChild(td5); tr.appendChild(td6);
    const openDetail = () => modalReflexiveInteraction(it.id);
    tr.addEventListener('click', openDetail);
    tr.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openDetail(); }
    });
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  host.appendChild(table);
  const meta = el('div', 'muted refx-meta');
  meta.textContent = data.items.length + ' / ' + data.total + ' interactions';
  host.appendChild(meta);
}

async function modalReflexiveInteraction(id) {
  let d;
  try { d = await API.get('/api/reflexive/interactions/' + id); }
  catch (e) { toastErr(e.message); return; }
  const i = d.interaction || {};
  const ev = d.eval || null;
  const tools = Array.isArray(i.tools_used) ? i.tools_used : [];
  const files = Array.isArray(i.files_touched) ? i.files_touched : [];
  const body = el('div');

  const grid = el('div', 'refx-detail-grid');
  const addCell = (label, value, mono = false) => {
    const cell = el('div');
    const lab = el('span', 'dim'); lab.textContent = label;
    const val = el('div', mono ? 'mono' : null); val.textContent = value || '—';
    cell.appendChild(lab); cell.appendChild(val);
    grid.appendChild(cell);
  };
  addCell('Workspace', i.workspace_id, true);
  addCell('Session', i.session_id, true);
  addCell('Début', i.started_at, true);
  addCell('Fin', i.ended_at, true);
  addCell('Outcome', i.outcome || 'unknown');
  addCell('Self-confidence', i.self_confidence != null ? i.self_confidence.toFixed(2) : null, true);
  body.appendChild(grid);

  const h1 = el('h4', 'refx-section-h'); h1.textContent = 'Résumé';
  body.appendChild(h1);
  const p1 = el('p'); p1.textContent = i.task_summary || '(non résumée)';
  body.appendChild(p1);

  const h2 = el('h4', 'refx-section-h'); h2.textContent = 'Outils utilisés (' + tools.length + ')';
  body.appendChild(h2);
  const chips = el('div', 'refx-chips');
  if (tools.length) {
    for (const t of tools) {
      const c = el('span', 'chip mono'); c.textContent = t; chips.appendChild(c);
      chips.appendChild(document.createTextNode(' '));
    }
  } else {
    const m = el('span', 'muted'); m.textContent = '—'; chips.appendChild(m);
  }
  body.appendChild(chips);

  const h3 = el('h4', 'refx-section-h'); h3.textContent = 'Fichiers touchés (' + files.length + ')';
  body.appendChild(h3);
  const filesEl = el('div', 'refx-files mono');
  if (files.length) {
    for (const f of files) { const d = el('div'); d.textContent = f; filesEl.appendChild(d); }
  } else {
    const m = el('span', 'muted'); m.textContent = '—'; filesEl.appendChild(m);
  }
  body.appendChild(filesEl);

  if (ev) {
    const hE = el('h4', 'refx-section-h');
    hE.textContent = 'Évaluation · ' + (ev.evaluated_at || '');
    body.appendChild(hE);
    const wrap = el('div', 'refx-dims');
    wrap.appendChild(refxDimBar('Correctness', ev.correctness));
    wrap.appendChild(refxDimBar('Efficiency',  ev.efficiency));
    wrap.appendChild(refxDimBar('Alignment',   ev.alignment));
    wrap.appendChild(refxDimBar('Learning',    ev.learning));
    body.appendChild(wrap);
    const p = el('p', 'muted');
    p.style.marginTop = 'var(--sp-3)';
    const strong = el('strong'); strong.textContent = 'Total : ';
    p.appendChild(strong);
    p.appendChild(document.createTextNode(ev.total + '/40 — ' + (ev.justification || '')));
    body.appendChild(p);
  } else {
    const m = el('p', 'muted'); m.textContent = "Pas encore d'évaluation pour cette interaction.";
    body.appendChild(m);
  }

  const close = btn('Fermer', 'btn-ghost btn-sm');
  const { close: doClose } = openModal({ title: 'Interaction #' + id, body, footer: close, wide: true });
  close.addEventListener('click', doClose);
}

// Filtre de statut courant pour l'onglet Propositions. Persisté en mémoire
// module (pas en URL) : on reste sur l'onglet, on bascule juste la vue.
let _refxPropStatus = 'pending';

const REFX_PROP_FILTERS = [
  ['pending',  'En attente'],
  ['applied',  'Traitées'],
  ['rejected', 'Rejetées'],
];

const REFX_PROP_EMPTY = {
  pending:  ['Aucune proposition en attente.', 'Le diagnosticien génère des propositions à partir des évaluations accumulées.'],
  applied:  ['Aucune proposition traitée.', "Les propositions que tu marques comme traitées apparaîtront ici (annulables)."],
  rejected: ['Aucune proposition rejetée.', 'Les propositions rejetées apparaîtront ici (annulables).'],
};

async function renderReflexiveProposals(host) {
  refxLoader(host);
  const status = _refxPropStatus;
  const data = await safe('/api/reflexive/proposals?status=' + status, { items: [] });
  host['innerHTML'] = '';

  // Barre de filtres par statut : permet d'accéder aux traitées/rejetées
  // pour pouvoir les annuler (item 5 lot D).
  const filterBar = el('div', 'refx-prop-filters');
  filterBar.style.cssText = 'display:flex;gap:6px;margin-bottom:var(--sp-3);flex-wrap:wrap';
  for (const [id, label] of REFX_PROP_FILTERS) {
    const b = btn(label, 'btn-sm' + (id === status ? ' btn-primary' : ' btn-ghost'));
    b.addEventListener('click', () => {
      if (_refxPropStatus === id) return;
      _refxPropStatus = id;
      renderReflexiveProposals(host);
    });
    filterBar.appendChild(b);
  }
  host.appendChild(filterBar);

  if (!data.items.length) {
    const [t, hint] = REFX_PROP_EMPTY[status] || ['Aucune proposition.', ''];
    const emptyHost = el('div');
    host.appendChild(emptyHost);
    refxEmpty(emptyHost, t, hint);
    return;
  }
  for (const p of data.items) {
    const card = el('div', 'card refx-proposal');
    const head = el('div', 'refx-proposal-head');
    const left = el('div');
    const eb = el('div', 'card-eyebrow');
    eb.textContent = (p.target || 'global') + ' · ' + (p.evidence_count || 0) + ' preuves';
    const h = el('h3', 'refx-proposal-title'); h.textContent = p.title || '(sans titre)';
    const path = el('div', 'mono dim');
    path.style.fontSize = '12px';
    path.textContent = p.path || '';
    left.appendChild(eb); left.appendChild(h); left.appendChild(path);
    const actions = el('div', 'refx-proposal-actions');
    head.appendChild(left); head.appendChild(actions);
    card.appendChild(head);

    if (status === 'pending') {
      // « Marquer comme traitée » plutôt que « Apply » : le backend ne fait
      // qu'enregistrer la décision en DB (status='applied'), il ne modifie
      // AUCUN fichier de config. La modification fichier reste manuelle pour
      // l'instant (automatisation = lot ultérieur). Le libellé et la note
      // ci-dessous évitent de laisser croire à un correctif appliqué.
      const applyBtn = btn('Marquer comme traitée', 'btn-primary btn-sm', I.check);
      applyBtn.title = "Enregistre ta décision (proposition traitée). Aucun fichier n'est modifié automatiquement -- applique le changement toi-même.";
      const rejectBtn = btn('Rejeter', 'btn-ghost btn-sm', I.x);
      applyBtn.addEventListener('click', () => withBusy(applyBtn, async () => {
        try {
          await API.post('/api/reflexive/proposals/' + p.id + '/apply');
          snackbar('Proposition « ' + (p.title || p.id) + ' » marquée comme traitée (aucun fichier modifié)', {
            actionLabel: 'Voir',
            onAction: () => location.hash = '#/reflexive/proposals',
          });
          renderReflexiveProposals(host);
          refreshReflexiveBadge();  // lot E item 3 : maj du compteur sidebar
        } catch (e) { toastErr(e.message); }
      }));
      rejectBtn.addEventListener('click', () => modalRejectProposal(p));
      actions.appendChild(applyBtn);
      actions.appendChild(rejectBtn);

      // Note honnête : on enregistre une décision, pas une mutation fichier.
      const note = el('p', 'muted');
      note.style.cssText = 'margin:var(--sp-2) 0 0;font-size:11.5px';
      note.textContent = "« Marquer comme traitée » enregistre seulement ta décision. La modification du fichier de config n'est pas encore automatisée -- applique-la manuellement.";
      card.appendChild(note);
    } else {
      // Statut traité/rejeté : badge + bouton « Annuler » (revert → pending).
      // L'annulation ne défait aucun fichier (rien n'a été muté), c'est juste
      // un changement de statut DB -- pas besoin de confirmation destructive.
      const badge = el('span', 'badge ' + (status === 'applied' ? 'badge-ok' : 'badge-warn'));
      badge.textContent = status === 'applied' ? 'traitée' : 'rejetée';
      actions.appendChild(badge);

      const undoBtn = btn('Annuler', 'btn-ghost btn-sm', I.refresh);
      undoBtn.title = "Remet cette proposition en attente (aucun fichier n'est touché)";
      undoBtn.addEventListener('click', () => withBusy(undoBtn, async () => {
        try {
          await API.post('/api/reflexive/proposals/' + p.id + '/revert');
          toastOk('Proposition remise en attente');
          renderReflexiveProposals(host);
          refreshReflexiveBadge();  // lot E item 3 : maj du compteur sidebar
        } catch (e) { toastErr(e.message); }
      }));
      actions.appendChild(undoBtn);

      if (status === 'rejected' && p.rejection_reason) {
        const reason = el('p', 'muted');
        reason.style.cssText = 'margin:var(--sp-2) 0 0;font-size:11.5px';
        reason.textContent = 'Raison du rejet : ' + p.rejection_reason;
        card.appendChild(reason);
      }
    }

    host.appendChild(card);
  }
}

function modalRejectProposal(p) {
  const body = el('div');
  const intro = el('p', 'muted');
  intro.style.marginTop = '0';
  intro.textContent = 'Pourquoi rejeter cette proposition ? La raison sera utilisée pour ajuster le diagnostician.';
  body.appendChild(intro);
  const ta = document.createElement('textarea');
  ta.className = 'textarea';
  ta.rows = 4;
  ta.placeholder = 'Ex. : trop spécifique, pas applicable globalement, contredit une convention…';
  body.appendChild(ta);
  const cancel = btn('Annuler', 'btn-ghost btn-sm');
  const ok = btn('Rejeter', 'btn-danger btn-sm');
  const { close } = openModal({
    title: 'Rejeter « ' + (p.title || ('#' + p.id)) + ' »',
    body, footer: [cancel, ok],
  });
  cancel.addEventListener('click', close);
  ok.addEventListener('click', async () => {
    const reason = ta.value.trim();
    if (!reason) { toastErr('Raison requise'); return; }
    try {
      await API.post('/api/reflexive/proposals/' + p.id + '/reject', { reason });
      toastOk('Proposition rejetée');
      close();
      refreshReflexiveBadge();  // lot E item 3 : maj du compteur sidebar
      route();
    } catch (e) { toastErr(e.message); }
  });
}

async function renderReflexiveMeasurements(host) {
  refxLoader(host);
  const data = await safe('/api/reflexive/measurement-plans?status=active', { items: [] });
  host['innerHTML'] = '';
  if (!data.items.length) {
    refxEmpty(host,
      'Aucun plan de mesure actif.',
      "Chaque proposition appliquée déclenche un plan de mesure pour vérifier qu'elle aide réellement.");
    return;
  }
  for (const m of data.items) {
    const card = el('div', 'card refx-plan');
    const eb = el('div', 'card-eyebrow');
    eb.textContent = m.threshold_dimension + ' ≥ ' + m.threshold_value + ' · ' + m.sample_size + ' interactions';
    const h = el('h3', 'refx-proposal-title'); h.textContent = m.criteria;
    const meta = el('div', 'muted mono');
    meta.style.fontSize = '12px';
    meta.textContent = 'créé le ' + fmtDate(m.created_at) + ' · proposition #' + m.proposal_id;
    card.appendChild(eb); card.appendChild(h); card.appendChild(meta);
    host.appendChild(card);
  }
}
