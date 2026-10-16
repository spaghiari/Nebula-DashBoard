/* ================================================================
   Nebula - Onglet workspace « Amelioration » (module claude-team)
   ----------------------------------------------------------------
   mountWsImprovementTab : monte le panneau (appele par wsMountPanel,
   app.js) seulement quand l'overlay claude-team est actif sur le
   workspace (STATE.overlaysActive, onglet optionnel de WS_TABS).

   Donnees : GET /api/workspaces/<id>/improvement (journal parse, stats,
   verrou des evals, compteurs des registres) + GET /api/workspaces/<id>/team
   (agents generes, modele effectif). Cf. dashcore/api_team.py.

   Contenu : 4 KPI, courbe des scores (SVG inline, aucune lib), journal
   (tableau .tbl/.tr), evals + agents, registres par statut, « Comment
   lancer ». Etat vide soigne quand le journal est vide. Rafraichir.

   Dependances foundations : STATE, API, escapeHtml, el, btn, I.*,
   hcAttrs, fmtNum, withBusy, toastErr, wsSetTabCount (app.js).
   ================================================================ */
'use strict';

function mountWsImprovementTab(w, panel) {
  const host = el('div', 'impr');
  panel.el.appendChild(host);
  renderWsImprovement(w.id, host);
}

async function renderWsImprovement(wsId, host) {
  host['innerHTML'] = `<div class="page-loader"><div class="spinner"></div><span>Lecture du journal…</span></div>`;
  let impr, team;
  try {
    [impr, team] = await Promise.all([
      API.get(`/api/workspaces/${wsId}/improvement`),
      API.get(`/api/workspaces/${wsId}/team`).catch(() => null),
    ]);
  } catch (e) {
    host['innerHTML'] = `<div class="error-box">Impossible de lire l'état de la boucle : ${escapeHtml(e.message)}</div>`;
    return;
  }
  const st = impr.stats || {};
  const journal = impr.journal || [];
  const evals = impr.evals || {};
  const loop = impr.loop || {};
  const accept = loop.accept_if || {};
  const gainMin = typeof accept.min_score_gain === 'number' ? accept.min_score_gain : 0.02;
  const agents = (team && team.agents) || [];
  wsSetTabCount(wsId, 'amelioration', st.iterations || 0);

  const frag = document.createDocumentFragment();

  // --- En-tete + Rafraichir ------------------------------------------
  const head = el('div', 'impr-head');
  // Mode de routage always-on (GET /api/workspaces/<id>/team routing) : pill
  // en en-tete, modifiable depuis la ligne du module (onglet Configuration).
  const routing = (team && team.routing) || null;
  const ROUTING_PILL = { auto: ['accent', 'Routage auto'], assiste: ['info', 'Routage assisté'], manuel: ['mute', 'Routage manuel'] };
  const routingPill = !routing ? '' : (!routing.declared
    ? '<span class="pill warn" title="Section routing absente de .claude/team.json (module activé avant le routage) : onglet Configuration, ligne du module, « Activer le routage »">Routage non déclaré</span>'
    : `<span class="pill ${(ROUTING_PILL[routing.mode] || ROUTING_PILL.manuel)[0]}" title="routing.mode = ${escapeHtml(routing.mode)} ; relecture du code : ${escapeHtml(routing.review_gate || 'always')} ; modifiable dans l'onglet Configuration, ligne du module">${escapeHtml((ROUTING_PILL[routing.mode] || ROUTING_PILL.manuel)[1])}</span>`);
  head['innerHTML'] = `<div><h2>Boucle d'amélioration mesurée</h2><p class="muted">Un changement d'agent n'est gardé que s'il améliore le score du jeu d'évals d'au moins ${escapeHtml(fmtScore(gainMin))} sans régression. ${routingPill}${impr.invalid_lines ? `<span class="pill warn" title="Lignes du journal ignorées (JSON invalide)">${impr.invalid_lines} ligne${impr.invalid_lines > 1 ? 's' : ''} invalide${impr.invalid_lines > 1 ? 's' : ''}</span>` : ''}</p></div>`;
  const refresh = btn('Rafraîchir', 'btn-sm btn-ghost', I.refresh);
  refresh.addEventListener('click', () => withBusy(refresh, () => renderWsImprovement(wsId, host)));
  head.appendChild(refresh);
  frag.appendChild(head);

  // --- 4 KPI ------------------------------------------------------------
  const last = st.last_score;
  const prevScore = (st.scores || []).length > 1 ? st.scores[st.scores.length - 2] : null;
  const delta = (last != null && prevScore != null) ? last - prevScore : null;
  const kpi = (icon, n, label, trend, cls) => `
    <div class="card kpi"><span class="ic">${icon}</span>
      <div style="min-width:0"><div class="k-n"><b class="tab-num">${escapeHtml(String(n))}</b><span class="k-l">${escapeHtml(label)}</span></div>
      <span class="k-t ${cls}">${escapeHtml(trend)}</span></div></div>`;
  const kpis = el('section', 'kpis impr-kpis');
  kpis.setAttribute('aria-label', 'Indicateurs de la boucle');
  kpis['innerHTML'] =
    kpi(I.activity, last != null ? fmtScore(last) : '-', 'score courant',
      last == null ? 'aucune mesure' : (delta == null ? 'baseline' : (delta >= 0 ? '+' : '') + fmtScore(delta) + ' à la dernière itération acceptée'),
      last == null ? '' : (delta == null ? '' : (delta > 0 ? 'ok' : (delta < 0 ? 'err' : ''))))
    + kpi(I.history, st.iterations || 0, st.iterations > 1 ? 'itérations' : 'itération',
      loop.max_iterations ? `max ${escapeHtml(String(loop.max_iterations))} par /improve` : 'journal', '')
    + kpi(I.check, st.accepted || 0, st.accepted > 1 ? 'acceptées' : 'acceptée',
      st.iterations ? `${Math.round(100 * (st.accepted || 0) / st.iterations)} % des itérations` : 'gain >= ' + fmtScore(gainMin) + ', 0 régression', st.accepted ? 'ok' : '')
    + kpi(I.x, st.rejected || 0, st.rejected > 1 ? 'rejetées' : 'rejetée',
      st.consecutive_rejects >= (loop.stop_after_consecutive_rejects || 3)
        ? `${st.consecutive_rejects} rejets consécutifs : revue humaine`
        : (st.consecutive_rejects ? `${st.consecutive_rejects} consécutif${st.consecutive_rejects > 1 ? 's' : ''}` : 'aucun rejet en cours'),
      st.consecutive_rejects >= (loop.stop_after_consecutive_rejects || 3) ? 'err' : (st.consecutive_rejects ? 'warn' : ''));
  frag.appendChild(kpis);

  // --- Courbe des scores + journal --------------------------------------
  if (!journal.length) {
    const empty = el('div', 'empty impr-empty');
    empty['innerHTML'] = `
      <div class="empty-title">Aucune itération pour l'instant</div>
      <p class="muted">Le journal <code class="mono">.claude/journal/changes.jsonl</code> est vide. Lance Claude dans ce workspace et dis <code class="mono">/eval</code> pour mesurer la baseline, puis <code class="mono">/improve</code> pour une première itération : le critique propose un changement, l'évaluateur le mesure, la ligne apparaît ici.</p>`;
    frag.appendChild(empty);
  } else {
    const curve = el('section', 'card impr-curve');
    curve.setAttribute('aria-label', 'Courbe des scores');
    curve['innerHTML'] = `<div class="card-h"><h3>${I.activity}Scores</h3><span class="r"><span class="muted" style="font-size:12px">${(st.scores || []).length} point${(st.scores || []).length > 1 ? 's' : ''} (baseline puis chaque itération acceptée)</span></span></div>
      <div class="impr-curve-body">${scoreCurveSvg(st.scores || [])}</div>`;
    frag.appendChild(curve);

    const tbl = el('section', 'card tbl impr-journal');
    tbl.setAttribute('role', 'table');
    tbl.setAttribute('aria-label', 'Journal des itérations');
    tbl['innerHTML'] = `<div class="tr h" role="row"><span role="columnheader">#</span><span role="columnheader">Date</span><span role="columnheader">Cible</span><span role="columnheader">Hypothèse</span><span class="num" role="columnheader">Score</span><span role="columnheader">Régressions</span><span role="columnheader">Statut</span><span role="columnheader">Commit</span></div>`;
    for (const j of journal.slice().reverse()) {
      const row = el('div', 'tr');
      row.setAttribute('role', 'row');
      const hyp = String(j.hypothesis || '');
      const short = hyp.length > 70 ? hyp.slice(0, 68).trimEnd() + '…' : hyp;
      const regs = j.regressions || [];
      const statusPill = j.status === 'accepted' ? '<span class="pill ok">accepté</span>'
        : j.status === 'rejected' ? '<span class="pill err">rejeté</span>'
          : j.status === 'pending' ? '<span class="pill accent" title="Candidat posé (phase 1), à mesurer dans une nouvelle session (phase 2)">à mesurer</span>'
            : `<span class="pill mute">${escapeHtml(j.status || '?')}</span>`;
      const gain = (j.score_before != null && j.score_after != null) ? j.score_after - j.score_before : null;
      row['innerHTML'] = `
        <span class="num" role="cell">${escapeHtml(String(j.iteration))}</span>
        <span role="cell">${escapeHtml(j.date || '-')}</span>
        <span role="cell" class="mono impr-target" title="${escapeHtml(j.target || '')}">${escapeHtml(j.target || '-')}</span>
        <span role="cell" class="impr-hyp"${hyp.length > 70 ? hcAttrs([{ title: 'Hypothèse', items: [hyp], text: true }]) : ''}>${escapeHtml(short || '-')}</span>
        <span role="cell" class="num tab-num">${j.score_before != null ? escapeHtml(fmtScore(j.score_before)) : '-'} <span class="muted">-></span> ${j.score_after != null ? escapeHtml(fmtScore(j.score_after)) : '-'}${gain != null ? ` <small class="${gain > 0 ? 'ok' : (gain < 0 ? 'err' : '')}">(${gain >= 0 ? '+' : ''}${escapeHtml(fmtScore(gain))})</small>` : ''}</span>
        <span role="cell"${regs.length ? hcAttrs([{ title: 'Cas en régression', items: regs }]) : ''}>${regs.length ? `<span class="pill err">${regs.length}</span>` : '<span class="muted">0</span>'}</span>
        <span role="cell">${statusPill}</span>
        <span role="cell" class="mono">${j.commit ? escapeHtml(j.commit) : '<span class="muted">-</span>'}</span>`;
      tbl.appendChild(row);
    }
    frag.appendChild(tbl);
  }

  // --- Evals + agents | registres + comment lancer ----------------------
  const grid = el('div', 'impr-grid');

  // Baseline : la derniere ligne du journal mesure-t-elle la configuration
  // courante (config_version == hash manifeste + corps + agents generes) ?
  const baselinePill = !journal.length
    ? '<span class="pill mute" title="Aucune mesure journalisée : /improve mesure la baseline au premier passage">Aucune baseline</span>'
    : (impr.baseline_current
      ? `<span class="pill ok" title="Dernière ligne du journal = configuration courante (${escapeHtml(impr.config_hash || '')}) : /improve la réutilise">Baseline à jour</span>`
      : `<span class="pill warn" title="Journal mesuré sur ${escapeHtml(impr.baseline_version || '?')}, configuration courante ${escapeHtml(impr.config_hash || '?')} : /improve re-mesure d'abord">Baseline périmée</span>`);
  // Candidat pose par la phase 1 de /improve, a mesurer dans une NOUVELLE
  // session (la definition d'un agent n'est pas relue a chaud).
  const pend = impr.pending;
  const pendingPill = !pend ? '' : (pend.in_place
    ? `<span class="pill accent" title="Itération ${escapeHtml(String(pend.iteration))} : ${escapeHtml(pend.target || '')} modifié (${escapeHtml(pend.hypothesis || '')}). Ouvrir une nouvelle session Claude dans ce workspace et lancer /improve pour mesurer et trancher.">Candidat ${escapeHtml(String(pend.iteration))} à mesurer : nouvelle session puis /improve</span>`
    : `<span class="pill err" title="Le candidat de l'itération ${escapeHtml(String(pend.iteration))} (empreinte ${escapeHtml(pend.config_version || '?')}) ne correspond plus à la configuration courante (${escapeHtml(impr.config_hash || '?')}) : /improve le rejettera et restaurera la cible.">Candidat ${escapeHtml(String(pend.iteration))} altéré</span>`);
  const evalsCard = el('section', 'card impr-evals');
  evalsCard['innerHTML'] = `<div class="card-h"><h3>${I.shield}Jeu d'évals</h3><span class="r">${pendingPill} ${baselinePill} ${evals.locked
    ? (evals.unlocked ? '<span class="pill warn" title="evals_unlocked: true dans .claude/settings.local.json">Déverrouillé localement</span>' : '<span class="pill ok">Verrouillé</span>')
    : '<span class="pill warn">Non verrouillé</span>'}</span></div>
    <div class="impr-facts">
      <div><b class="tab-num">${escapeHtml(String(evals.cases || 0))}</b><span>cas dans <code class="mono">eval-set.jsonl</code></span></div>
      <div><b class="tab-num">${escapeHtml(String(evals.holdout_cases || 0))}</b><span>cas cachés (<code class="mono">holdout.jsonl</code>)</span></div>
      <div><b class="tab-num">${escapeHtml(String(loop.runs_per_eval || 1))}</b><span>passe${(loop.runs_per_eval || 1) > 1 ? 's' : ''} par cas noté par LLM</span></div>
      <div><b class="tab-num mono" style="font-size:13px">${escapeHtml(impr.config_hash || '-')}</b><span>empreinte de la configuration (<code class="mono">config_version</code>)</span></div>
    </div>
    <p class="muted impr-note">${evals.locked
      ? "Le hook <code class=\"mono\">evals-lock.py</code> refuse toute écriture sous <code class=\"mono\">.claude/evals/</code>. Pour ajouter un cas : <code class=\"mono\">/eval-add</code>, puis <code class=\"mono\">\"evals_unlocked\": true</code> dans <code class=\"mono\">.claude/settings.local.json</code> le temps de l'édition."
      : "<code class=\"mono\">eval_set_locked</code> est faux dans <code class=\"mono\">.claude/team.json</code> : la boucle pourrait modifier ce qui la mesure."}</p>
    ${agents.length ? `<div class="impr-agents">${agents.map(a => `<span class="chip${a.generated ? '' : ' missing'}" title="${escapeHtml(a.generated ? (a.generated_by_nebula ? 'Généré par Nebula' : 'Édité à la main') : 'Agent non généré : ré-appliquer le module')}">${escapeHtml(a.id)} <b>${escapeHtml(a.effective_model || a.model)}</b>${a.generated ? '' : ' ' + I.alert}</span>`).join('')}</div>` : ''}`;
  grid.appendChild(evalsCard);

  const regs = impr.registers || {};
  const REG_LABELS = [['ideas', 'ideas.md'], ['backlog', 'backlog.md'], ['improvements', 'improvements.md']];
  const STATUSES = ['IDEAS', 'VALIDATED', 'TODO', 'IN PROGRESS', 'DONE', 'ABANDONED', 'REJECTED', 'BACKLOG'];
  const regCard = el('section', 'card impr-regs');
  regCard['innerHTML'] = `<div class="card-h"><h3>${I.book}Registres</h3><span class="r"><span class="muted" style="font-size:12px">items par statut</span></span></div>
    <div class="impr-reg-rows">${REG_LABELS.map(([k, label]) => {
      const c = regs[k] || {};
      const chips = STATUSES.filter(s => c[s]).map(s => `<span class="chip ${s === 'TODO' || s === 'VALIDATED' ? 'todo' : (s === 'DONE' ? 'done' : (s === 'IN PROGRESS' ? 'prog' : ''))}">${escapeHtml(s)} <b>${escapeHtml(String(c[s]))}</b></span>`).join('');
      return `<div class="impr-reg-row"><code class="mono">${escapeHtml(label)}</code><span class="chips">${chips || '<span class="muted">aucun item</span>'}</span></div>`;
    }).join('')}</div>
    <p class="muted impr-note">Le critique lit les items <code class="mono">[TODO]</code> de <code class="mono">improvements.md</code> comme hypothèses ; une itération acceptée passe l'item en <code class="mono">[DONE]</code> avec la mesure, une rejetée en <code class="mono">[ABANDONED]</code>.</p>`;
  grid.appendChild(regCard);

  const how = el('section', 'card impr-how');
  how['innerHTML'] = `<div class="card-h"><h3>${I.terminal}Comment lancer</h3></div>
    <ol class="impr-steps">
      <li><code class="mono">/team &lt;objectif&gt;</code> : le fil principal joue l'orchestrateur et délègue aux agents <code class="mono">${escapeHtml(team && team.prefix ? team.prefix : wsId)}-*</code>.</li>
      <li><code class="mono">/eval</code> : score de la configuration courante (lecture seule ; <code class="mono">--tag</code>, <code class="mono">--agent</code>, <code class="mono">--id</code>).</li>
      <li><code class="mono">/improve</code> : une itération (baseline réutilisée si l'empreinte est inchangée, UN diff du critique, mesure, verdict, commit, journal). <code class="mono">/improve 3</code> pour trois.</li>
      <li><code class="mono">/eval-add</code> : transformer un échec observé en cas d'éval (déverrouillage explicite requis).</li>
    </ol>
    <p class="muted impr-note">Arrêt automatique après ${escapeHtml(String(loop.stop_after_consecutive_rejects || 3))} rejets consécutifs (revue humaine). Détail : <code class="mono">.claude/memory/conventions/improvement-loop.md</code>.</p>`;
  grid.appendChild(how);
  frag.appendChild(grid);

  host.replaceChildren(frag);
}

function fmtScore(v) {
  return (Math.round(v * 1000) / 1000).toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 3 });
}

// Courbe simple des scores (0..1) en SVG inline : aire + ligne + points,
// axes 0 / 0,5 / 1, valeur au survol via <title>.
function scoreCurveSvg(scores) {
  const W = 640, H = 160, PL = 36, PR = 12, PT = 12, PB = 22;
  const n = scores.length;
  if (!n) return '';
  const xs = (i) => n === 1 ? (PL + (W - PL - PR) / 2) : PL + (i * (W - PL - PR)) / (n - 1);
  const ys = (v) => PT + (1 - Math.max(0, Math.min(1, v))) * (H - PT - PB);
  const pts = scores.map((v, i) => [xs(i), ys(v)]);
  const line = pts.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' ');
  const area = n > 1 ? `${line} L${pts[n - 1][0].toFixed(1)} ${ys(0).toFixed(1)} L${pts[0][0].toFixed(1)} ${ys(0).toFixed(1)} Z` : '';
  const grid = [0, 0.5, 1].map(v => `<line x1="${PL}" x2="${W - PR}" y1="${ys(v).toFixed(1)}" y2="${ys(v).toFixed(1)}" class="g"/><text x="${PL - 6}" y="${(ys(v) + 4).toFixed(1)}" text-anchor="end" class="t">${v.toLocaleString('fr-FR')}</text>`).join('');
  const dots = pts.map(([x, y], i) => `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="4" class="d"><title>${i === 0 ? 'Baseline' : `Point ${i}`} : ${escapeHtml(fmtScore(scores[i]))}</title></circle>`).join('');
  const labels = pts.map(([x], i) => (n <= 12 || i === 0 || i === n - 1 || i % Math.ceil(n / 12) === 0)
    ? `<text x="${x.toFixed(1)}" y="${H - 6}" text-anchor="middle" class="t">${i === 0 ? 'base' : i}</text>` : '').join('');
  return `<svg class="impr-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="Évolution du score : ${scores.map(s => escapeHtml(fmtScore(s))).join(', ')}">
    ${grid}${area ? `<path d="${area}" class="a"/>` : ''}<path d="${line}" class="l"/>${dots}${labels}</svg>`;
}
