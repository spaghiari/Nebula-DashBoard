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

  // --- Equipe : modele et effort par agent (propositions au clic) ---------
  if (team && team.active && agents.length) frag.appendChild(teamConfigCard(wsId, host, team, impr));

  host.replaceChildren(frag);
}

// Libelles des alias de modele et des niveaux d'effort (valeurs = celles de
// dashcore/config.py TEAM_MODEL_ALIASES / TEAM_EFFORT_LEVELS, renvoyees par
// GET /team ; un alias inconnu s'affiche tel quel).
const IMPR_MODEL_LABELS = { sonnet: 'sonnet (rapide)', opus: 'opus (profond)', haiku: 'haiku (léger)', fable: 'fable', inherit: 'inherit (session)' };
const IMPR_EFFORT_LABELS = { low: 'faible', medium: 'moyen', high: 'élevé', xhigh: 'très élevé', max: 'max' };
// Resultat du dernier enregistrement, affiche apres le re-rendu de l'onglet.
const IMPR_TEAM_NOTES = {};

function imprEffortLabel(e) {
  return e ? (IMPR_EFFORT_LABELS[e] || e) : 'par défaut';
}

// Carte « Equipe : modele et effort » : une ligne par agent (selecteurs
// modele + effort, proposition expliquee, « Appliquer »), « Appliquer toutes
// les propositions ». POST /api/workspaces/<id>/team/agents-config puis
// re-rendu ; mention « baseline perimee » si la configuration mesuree change.
function teamConfigCard(wsId, host, team, impr) {
  const card = el('section', 'card impr-team');
  card.setAttribute('aria-label', 'Modèle et effort des agents');
  const models = team.model_aliases || Object.keys(IMPR_MODEL_LABELS);
  const efforts = team.effort_levels || Object.keys(IMPR_EFFORT_LABELS);
  const sugg = {};
  for (const s of team.suggestions || []) sugg[s.agent] = s;
  const basis = team.suggestions_basis || {};
  const pend = impr && impr.pending;
  const note = IMPR_TEAM_NOTES[wsId];
  delete IMPR_TEAM_NOTES[wsId];

  const basisPill = basis.measured
    ? `<span class="pill info" title="Propositions = règles par rôle + signal mesuré (agent avec au moins 2 cas et moins de la moitié réussis : effort +1 cran)">Mesure du ${escapeHtml(basis.date || '?')}</span>`
    : '<span class="pill mute" title="Aucune ligne du journal avec liste d\'échecs : propositions issues des seules règles par rôle. Lance /eval puis /improve pour un signal mesuré.">Règles seules (aucune mesure)</span>';
  const opt = (vals, cur, label) => vals.map(v => `<option value="${escapeHtml(v)}"${v === cur ? ' selected' : ''}>${escapeHtml(label(v))}</option>`).join('');
  const rows = (team.agents || []).map(a => {
    const s = sugg[a.id];
    const cur = { model: a.effective_model || a.model, effort: a.effective_effort || '' };
    const manual = a.generated && !a.generated_by_nebula;
    const prop = !s ? '<span class="muted">Aucune proposition</span>'
      : `<b class="mono">${escapeHtml(s.proposed.model)} · ${escapeHtml(imprEffortLabel(s.proposed.effort))}</b>
         <small>${(s.reasons || []).map(r => escapeHtml(r)).join(' ')}</small>`;
    return `<div class="impr-team-row" role="row" data-agent="${escapeHtml(a.id)}">
      <span class="impr-team-name" role="cell"><b class="mono">${escapeHtml(a.name || a.id)}</b>${a.role ? `<small>${escapeHtml(a.role)}</small>` : ''}${manual ? ' <span class="pill warn" title="Agent édité à la main (marqueur généré absent) : le manifeste change, le fichier non">édité à la main</span>' : ''}</span>
      <label class="impr-team-sel" role="cell"><span class="sr-only">Modèle de ${escapeHtml(a.id)}</span>
        <select class="select" data-k="model">${opt(models.includes(cur.model) ? models : [cur.model, ...models], cur.model, v => IMPR_MODEL_LABELS[v] || v)}</select></label>
      <label class="impr-team-sel" role="cell"><span class="sr-only">Effort de ${escapeHtml(a.id)}</span>
        <select class="select" data-k="effort">${opt(['', ...efforts], cur.effort, imprEffortLabel)}</select></label>
      <span class="impr-team-prop" role="cell">${prop}</span>
      <span class="impr-team-act" role="cell"></span>
    </div>`;
  }).join('');

  const noteHtml = !note ? '' : (note.written
    ? `<p class="impr-team-msg ${note.stale ? 'warn' : 'ok'}">${I.check}<span>${escapeHtml(String(note.generated))} agent${note.generated > 1 ? 's' : ''} régénéré${note.generated > 1 ? 's' : ''}.${note.stale ? ' Baseline périmée : relance <code class="mono">/eval</code> (ou <code class="mono">/improve</code>, qui re-mesure d\'abord) dans une nouvelle session.' : ' Nouvelle session Claude nécessaire pour que les agents modifiés soient pris en compte.'}${note.manual ? ` ${escapeHtml(String(note.manual))} agent${note.manual > 1 ? 's' : ''} édité${note.manual > 1 ? 's' : ''} à la main non réécrit${note.manual > 1 ? 's' : ''}.` : ''}</span></p>`
    : `<p class="impr-team-msg">${I.info}<span>Aucun changement : la configuration était déjà celle-ci.</span></p>`);

  card['innerHTML'] = `<div class="card-h"><h3>${I.sliders}Équipe : modèle et effort</h3><span class="r">${basisPill}</span></div>
    <p class="muted impr-note">Modèle et effort de raisonnement de chaque agent, écrits dans <code class="mono">.claude/team.json</code> puis rendus dans l'agent généré. Les propositions ne font que compléter : la règle du rôle propose un modèle seulement à un agent qui n'en déclare pas, et un effort (jamais au-delà de « élevé ») seulement s'il est au-dessus de l'actuel ; un agent sans effort est compté comme « moyen » (défaut de Claude Code sur les modèles 5.5), la règle peut donc lui proposer « élevé ». S'il existe une mesure, un agent en échec reçoit +1 cran d'effort. Jamais de baisse d'effort, jamais de changement d'un modèle déclaré. Rien n'est appliqué sans clic.</p>
    ${noteHtml}
    ${pend ? `<p class="impr-team-msg warn">${I.alert}<span>Itération ${escapeHtml(String(pend.iteration))} de <code class="mono">/improve</code> en attente de verdict : trancher d'abord (nouvelle session puis <code class="mono">/improve</code>), sinon le candidat serait mesuré sur une autre configuration.</span></p>` : ''}
    <div class="impr-team-rows" role="table" aria-label="Modèle et effort par agent">
      <div class="impr-team-row h" role="row"><span role="columnheader">Agent</span><span role="columnheader">Modèle</span><span role="columnheader">Effort</span><span role="columnheader">Proposition</span><span role="columnheader"><span class="sr-only">Action</span></span></div>
      ${rows}
    </div>
    <div class="impr-team-foot"></div>`;

  const save = async (b, payload) => {
    try {
      const r = await withBusy(b, () => API.post(`/api/workspaces/${wsId}/team/agents-config`, { agents: payload }));
      const manual = (r.skipped || []).filter(s => /main/.test(s.reason || '')).length;
      IMPR_TEAM_NOTES[wsId] = { written: r.written, stale: r.baseline_stale, generated: (r.generated || []).length, manual };
      toastOk(r.written ? 'Configuration de l\'équipe enregistrée' : 'Aucun changement');
      await renderWsImprovement(wsId, host);
    } catch (e) {
      toastErr(e.message);
    }
  };

  const allPayload = {};
  for (const row of card.querySelectorAll('.impr-team-row[data-agent]')) {
    const id = row.dataset.agent;
    const a = (team.agents || []).find(x => x.id === id) || {};
    const cur = { model: a.effective_model || a.model, effort: a.effective_effort || '' };
    const selM = row.querySelector('[data-k=model]');
    const selE = row.querySelector('[data-k=effort]');
    const act = row.querySelector('.impr-team-act');
    const s = sugg[id];
    if (pend) { selM.disabled = true; selE.disabled = true; }
    const saveBtn = btn('Enregistrer', 'btn-sm btn-primary', I.check);
    saveBtn.hidden = true;
    saveBtn.addEventListener('click', () => save(saveBtn, { [id]: { model: selM.value, effort: selE.value || null } }));
    const sync = () => { saveBtn.hidden = selM.value === cur.model && selE.value === cur.effort; if (applyBtn) applyBtn.hidden = !saveBtn.hidden; };
    let applyBtn = null;
    if (s && !pend) {
      applyBtn = btn('Appliquer', 'btn-sm btn-ghost', I.zap);
      applyBtn.title = `Passer à ${s.proposed.model} · ${imprEffortLabel(s.proposed.effort)}`;
      applyBtn.addEventListener('click', () => save(applyBtn, { [id]: { model: s.proposed.model, effort: s.proposed.effort || null } }));
      act.appendChild(applyBtn);
      allPayload[id] = { model: s.proposed.model, effort: s.proposed.effort || null };
    }
    act.appendChild(saveBtn);
    selM.addEventListener('change', sync);
    selE.addEventListener('change', sync);
  }
  const n = Object.keys(allPayload).length;
  if (n > 1) {
    const all = btn(`Appliquer toutes les propositions (${n})`, 'btn-sm btn-primary', I.sparkle);
    all.addEventListener('click', () => save(all, allPayload));
    card.querySelector('.impr-team-foot').appendChild(all);
  }
  return card;
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
