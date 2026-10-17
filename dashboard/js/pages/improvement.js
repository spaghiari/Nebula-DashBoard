/* ================================================================
   Nebula - Onglet workspace « Amelioration » (module claude-team)
   ----------------------------------------------------------------
   mountWsImprovementTab : monte le panneau (appele par wsMountPanel,
   app.js) seulement quand l'overlay claude-team est actif sur le
   workspace (STATE.overlaysActive, onglet optionnel de WS_TABS).

   Donnees :
   - GET /api/workspaces/<id>/improvement : journal, stats, pending, cas,
     pistes (todo_items), job (dernier ou en cours), auto, next_step ;
   - GET /api/workspaces/<id>/team : agents, propositions modele / effort ;
   - GET /api/claude/subscription?ws=<id> : plan + avertissements ;
   - GET /api/workspaces/<id>/improvement/job : vue legere du polling.
   Actions : POST .../improvement/run {kind, force_session?}, /abandon, /stop,
   /auto {enabled?, daily_budget?, resume?}, POST .../team/agents-config.

   Ordre de l'onglet : bandeau « Prochaine etape », panneau du job en
   cours, metriques, frise des iterations + courbe, mode automatique,
   pistes d'amelioration, jeu d'evals, carte « Equipe : modele et effort ».

   Suivi en direct : un seul intervalle par onglet (registerPagePoller,
   nettoye a chaque navigation par clearPagePollers), tick 3 s : job en
   cours -> GET .../job ; sinon GET .../improvement toutes les 30 s (re-rendu
   seulement si l'etat a change). Rien quand le document ou le panneau est
   masque ; arret quand le panneau est demonte (host deconnecte).

   Dependances foundations : STATE, API, escapeHtml, el, btn, I.*,
   hcAttrs, fmtCompact, fmtDateTime, withBusy, toast*, openModal,
   registerPagePoller, wsSetTabCount (app.js).
   ================================================================ */
'use strict';

const IMPR_TICK_MS = 3000;          // polling du job en cours
const IMPR_FULL_MS = 30000;         // relecture complete hors job
const IMPR_LIVE = {};               // wsId -> {host, timer, running, lastFull, sig, inflight}
const IMPR_SUB = {};                // wsId -> {at, promise} (abonnement, 60 s)

function mountWsImprovementTab(w, panel) {
  const host = el('div', 'impr');
  panel.el.appendChild(host);
  imprBind(w.id, host);
  renderWsImprovement(w.id, host);
  imprStartPolling(w.id, host);
}

// --- Donnees ------------------------------------------------------------------

function imprSubscription(wsId, fresh = false) {
  const c = IMPR_SUB[wsId];
  if (!fresh && c && Date.now() - c.at < 60000) return c.promise;
  const promise = API.get(`/api/claude/subscription?ws=${encodeURIComponent(wsId)}`).catch(() => null);
  IMPR_SUB[wsId] = { at: Date.now(), promise };
  return promise;
}

async function renderWsImprovement(wsId, host, { quiet = false } = {}) {
  const gen = (host._imprGen || 0) + 1;
  host._imprGen = gen;
  if (!quiet || !host.childElementCount) {
    host['innerHTML'] = `<div class="page-loader"><div class="spinner"></div><span>Lecture du journal…</span></div>`;
  }
  const subP = imprSubscription(wsId, !quiet);
  let impr, team, sub;
  try {
    [impr, team, sub] = await Promise.all([
      API.get(`/api/workspaces/${wsId}/improvement`),
      API.get(`/api/workspaces/${wsId}/team`).catch(() => null),
      Promise.race([subP, new Promise(r => setTimeout(() => r(undefined), 2500))]),
    ]);
  } catch (e) {
    if (host._imprGen !== gen) return;
    if (quiet && host.querySelector('.impr-next')) { toastErr(`Lecture de la boucle impossible : ${e.message}`); return; }
    host['innerHTML'] = `<div class="error-box">Impossible de lire l'état de la boucle : ${escapeHtml(e.message)}</div>`;
    return;
  }
  if (host._imprGen !== gen) return;
  imprPaint(wsId, host, impr, team, sub || null);
  // Abonnement arrive apres coup (detection lente) : repeint discret.
  if (sub === undefined) {
    subP.then(s => {
      if (s && host.isConnected && host._imprGen === gen && !imprTeamDirty(host)) imprPaint(wsId, host, impr, team, s);
    });
  }
}

// Etat resume pour decider d'un re-rendu (polling 30 s).
function imprSig(impr) {
  const st = impr.stats || {};
  const job = impr.job || {};
  const a = impr.auto || {};
  return JSON.stringify([st.iterations, st.accepted, st.rejected, st.pending, (impr.pending || {}).iteration,
    (impr.next_step || {}).state, job.job_id, job.status, a.enabled, a.paused_until, a.daily_budget,
    a.budget_reached, impr.baseline_current, (impr.todo_items || []).length]);
}

function imprTeamDirty(host) {
  for (const s of host.querySelectorAll('.impr-team-row select')) {
    if (s.value !== (s.dataset.cur || '')) return true;
  }
  return !!host.querySelector('[aria-busy="true"]') || !!document.querySelector('.modal-overlay [data-impr-modal]');
}

// --- Rendu complet ----------------------------------------------------------------

// Job lance par ce client (202) : si il est deja termine au premier rendu
// (moins d'un cycle de polling), le toast de fin est emis ici, une seule fois.
// S'il tourne encore, le flux normal (polling puis toast) prend le relais.
function imprAwaitJob(wsId, r) {
  const live = IMPR_LIVE[wsId];
  const id = r && r.data && r.data.job && r.data.job.job_id;
  if (live && id) live.awaitJobId = id;
}

function imprSettleAwaited(wsId, job) {
  const live = IMPR_LIVE[wsId];
  if (!live || !live.awaitJobId || !job || job.job_id !== live.awaitJobId) return;
  live.awaitJobId = null;
  if (job.status !== 'running') imprJobEndToast(job);
}

function imprPaint(wsId, host, impr, team, sub) {
  const st = impr.stats || {};
  const loop = impr.loop || {};
  const job = impr.job || null;
  const running = !!(job && job.status === 'running');
  const plan = (sub && sub.plan) || 'unknown';
  const iters = imprIterations(impr.journal || []);
  const agents = (team && team.agents) || [];
  wsSetTabCount(wsId, 'amelioration', st.iterations || 0);
  host._imprData = { impr, team, sub, plan, iters };

  const live = IMPR_LIVE[wsId];
  if (live && live.host === host) {
    live.running = running;
    live.jobId = running ? job.job_id : null;
    live.sig = imprSig(impr);
    live.lastFull = Date.now();
  }
  imprSettleAwaited(wsId, job);

  const accept = loop.accept_if || {};
  const gainMin = typeof accept.min_score_gain === 'number' ? accept.min_score_gain : 0.02;
  const routing = (team && team.routing) || null;
  const ROUTING_PILL = { auto: ['accent', 'Routage auto'], assiste: ['info', 'Routage assisté'], manuel: ['mute', 'Routage manuel'] };
  const rp = routing && routing.declared ? (ROUTING_PILL[routing.mode] || ROUTING_PILL.manuel) : null;

  const frag = document.createDocumentFragment();
  const head = el('div', 'impr-head');
  head['innerHTML'] = `<div><h2>Amélioration de l'équipe</h2><p class="muted">Nebula essaie une modification d'agent à la fois, la mesure sur le jeu d'évals, et ne la garde que si le score monte d'au moins ${escapeHtml(fmtScore(gainMin))} sans casser un cas qui passait.${rp ? ` <span class="pill ${escapeHtml(rp[0])}">${escapeHtml(rp[1])}</span>` : ''}${impr.invalid_lines ? ` <span class="pill warn">${escapeHtml(String(impr.invalid_lines))} ligne(s) du journal ignorée(s)</span>` : ''}</p></div>`;
  const refresh = btn('Rafraîchir', 'btn-sm btn-ghost', I.refresh);
  refresh.addEventListener('click', () => withBusy(refresh, () => renderWsImprovement(wsId, host, { quiet: true })));
  head.appendChild(refresh);
  frag.appendChild(head);

  frag.appendChild(el('div', null, imprNextStepHtml(impr.next_step, impr.pending, job)).firstElementChild);
  if (running) frag.appendChild(el('div', null, imprJobPanelHtml(job, plan)).firstElementChild);
  frag.appendChild(el('div', null, imprMetricsHtml(st, impr.auto, plan, iters)).firstElementChild);
  frag.appendChild(el('div', null, imprTimelineHtml(iters, st.scores || [])).firstElementChild);

  const grid = el('div', 'impr-cols');
  grid.appendChild(el('div', null, imprAutoHtml(impr.auto, plan)).firstElementChild);
  grid.appendChild(el('div', null, imprTodoHtml(impr.todo_items || [], impr.registers || {})).firstElementChild);
  frag.appendChild(grid);
  frag.appendChild(el('div', null, imprCasesHtml(impr, team, wsId)).firstElementChild);

  if (team && team.active && agents.length) frag.appendChild(teamConfigCard(wsId, host, team, impr, sub));

  host.replaceChildren(frag);
  if (typeof startSinceTimers === 'function') startSinceTimers();
}

// Une entree par iteration : la derniere ligne du journal fait foi.
function imprIterations(journal) {
  const by = new Map();
  for (const j of journal) by.set(j.iteration, j);
  return [...by.values()].sort((a, b) => (a.iteration || 0) - (b.iteration || 0));
}

// --- Petits formateurs (texte, jamais HTML) -------------------------------------

function fmtScore(v) {
  return (Math.round(v * 1000) / 1000).toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 3 });
}

function imprTokTotal(t) {
  if (!t || typeof t !== 'object') return 0;
  return ['input', 'output', 'cache_read', 'cache_creation'].reduce((s, k) => s + (Number(t[k]) || 0), 0);
}

function imprFmtTok(n) {
  return `${fmtCompact(Math.round(Number(n) || 0))} jetons`;
}

function imprFmtUsd(v) {
  return `${(Number(v) || 0).toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} $`;
}

function imprGain(g) {
  return g == null ? '-' : (g >= 0 ? '+' : '') + fmtScore(g);
}

// « 14:05 » aujourd'hui, sinon « 18 oct., 14:05 ».
function imprTime(iso) {
  const d = new Date(iso);
  if (!iso || isNaN(d)) return String(iso || '');
  const hm = d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
  return d.toDateString() === new Date().toDateString() ? hm : fmtDateTime(iso);
}

const IMPR_STATUS = {
  accepted: ['ok', 'gardée'],
  rejected: ['err', 'écartée'],
  pending: ['accent', 'en attente de verdict'],
};

const IMPR_STEPS = {
  'démarrage': 'Préparation',
  'mesure baseline': 'Mesure de référence de la configuration actuelle',
  'critique': 'Le critique cherche une modification à essayer',
  'mesure candidat': 'Mesure de la modification à l\'essai',
  'mesure': 'Mesure de la configuration actuelle',
  'terminé': 'Terminé',
};

const IMPR_KINDS = { iteration: 'Itération', measure: 'Mesure de référence', resolve: 'Verdict', abandon: 'Abandon du candidat' };

// Explication en langage simple de chaque etat de next_step.
const IMPR_HELP = {
  inactive: "Active le module « Équipe d'agents » dans l'onglet Configuration.",
  no_cases: "Le jeu d'évals est vide : sans cas à mesurer, impossible de savoir si une modification aide. Ajoute des cas avec /eval-add dans Claude.",
  job_running: "Claude travaille en tâche de fond. Tu peux quitter cet onglet : l'itération continue et le résultat s'affichera ici.",
  quota_paused: "Le quota de ton abonnement Claude est atteint. Le mode automatique reprendra tout seul après la remise à zéro.",
  pending: "Une modification d'agent est à l'essai. Tranche la mesure, puis Nebula décide : gardée si le score monte sans régression, écartée sinon (l'agent est alors restauré).",
  dirty_config: "Nebula ne mesure jamais une configuration qui contient des modifications non commitées : le résultat serait commité avec elles. Commite ou annule tes changements sur les fichiers de l'équipe, puis reprends.",
  undecidable: "Trop de cas d'évals n'ont pas pu s'exécuter pour trancher (souvent un quota atteint ou un agent introuvable). Tranche à nouveau plus tard, abandonne le candidat, ou reprends le mode automatique.",
  rejects_stop: "Les dernières modifications proposées ont toutes été écartées. Jette un œil aux pistes et au jeu d'évals avant de reprendre.",
  campaign_cap: "Le nombre d'itérations prévu pour cette campagne est atteint. Désactive puis réactive le mode automatique pour en ouvrir une nouvelle.",
  auto_waiting: "Le mode automatique a fait son nombre d'itérations du jour. Il reprendra demain.",
  no_baseline: "Avant d'essayer des modifications, Nebula mesure ton équipe actuelle sur le jeu d'évals : c'est la mesure de référence, le point de comparaison.",
  stale_baseline: "Un agent a changé depuis la dernière mesure. Refais la mesure de référence, ou lance directement une itération (elle la refera d'abord).",
  ready: "Une itération : le critique propose UNE modification d'un agent, Nebula la mesure, puis la garde ou l'écarte.",
};

const IMPR_TONE = {
  job_running: 'info', quota_paused: 'warn', pending: 'warn', undecidable: 'warn', dirty_config: 'warn', rejects_stop: 'err', campaign_cap: 'warn',
  auto_waiting: 'mute', no_cases: 'warn', inactive: 'mute',
};

// Boutons des actions de next_step : [libelle, classe, icone].
const IMPR_ACTIONS = {
  run: ['Lancer une itération', 'btn-primary', 'play'],
  measure: ['Mesurer', 'btn-primary', 'activity'],
  resolve: ['Trancher maintenant', 'btn-primary', 'check'],
  abandon: ['Abandonner ce candidat', 'btn-ghost', 'x'],
  resume: ['Reprendre', 'btn-primary', 'play'],
  cancel: ['Arrêter', 'btn-ghost btn-danger', 'stop'],
};

function imprBtnHtml(act, small) {
  const def = IMPR_ACTIONS[act];
  if (!def) return '';
  const ic = I[def[2]] || '';
  return `<button type="button" class="btn ${small ? 'btn-sm ' : ''}${escapeHtml(def[1])}" data-impr-act="${escapeHtml(act)}">${ic}<span>${escapeHtml(def[0])}</span></button>`;
}

// --- Bandeau « Prochaine etape » -----------------------------------------------

// Ligne discrete sur la derniere tentative refusee ou en echec.
function imprLastAttemptText(job) {
  if (!job || job.status === 'running') return '';
  if (job.verdict === 'refused') {
    const d = job.dirty_paths && job.dirty_paths.length ? ` (${job.dirty_paths.slice(0, 3).join(', ')})` : '';
    return `Dernière tentative refusée : fichiers de l'équipe non commités${d}`;
  }
  if (job.status === 'failed') return `Dernière tentative en échec${job.error ? ` : ${job.error}` : ''}`;
  return '';
}

function imprNextStepHtml(ns, pending, job) {
  ns = ns || { state: 'ready', title: 'Prête', detail: '', actions: [] };
  const tone = IMPR_TONE[ns.state] || 'accent';
  const icon = ns.state === 'job_running' ? I.activity : (tone === 'err' || tone === 'warn' ? I.alert : I.sparkle);
  let help = IMPR_HELP[ns.state] || '';
  if (ns.state === 'pending' && (ns.actions || []).length === 1 && ns.actions[0] === 'abandon') {
    help = "Le fichier à l'essai a été modifié depuis : le verdict ne serait plus fiable. Abandonne ce candidat pour revenir à la configuration de référence.";
  }
  const last = ns.state === 'job_running' ? '' : imprLastAttemptText(job);
  const acts = (ns.actions || []).filter(a => IMPR_ACTIONS[a]);
  const hyp = ns.state === 'pending' && pending && pending.hypothesis ? pending.hypothesis : '';
  return `<section class="card impr-next tone-${escapeHtml(tone)}" data-state="${escapeHtml(ns.state || '')}" aria-live="polite" aria-label="Prochaine étape">
    <span class="impr-next-ic">${icon}</span>
    <div class="impr-next-main">
      <div class="impr-next-k">Prochaine étape</div>
      <div class="impr-next-t">${escapeHtml(ns.title || '')}</div>
      <p class="impr-next-d">${ns.state === 'job_running' ? '' : escapeHtml(ns.detail || '')}${help ? ` ${escapeHtml(help)}` : ''}</p>
      ${last ? `<p class="impr-next-last muted">${escapeHtml(last)}</p>` : ''}
      ${hyp ? `<p class="impr-next-hyp"><b>Modification à l'essai :</b> ${escapeHtml(hyp)}${pending.target ? ` <code class="mono">${escapeHtml(pending.target)}</code>` : ''}</p>` : ''}
    </div>
    ${acts.length ? `<div class="impr-next-acts">${acts.map(a => imprBtnHtml(a, false)).join('')}</div>` : ''}
  </section>`;
}

// --- Panneau du job en cours ------------------------------------------------------

function imprJobPanelHtml(job, plan) {
  const done = Number(job.cases_done) || 0;
  const total = Number(job.cases_total) || 0;
  const pct = total ? Math.min(100, Math.round((100 * done) / total)) : 0;
  const tok = imprTokTotal(job.tokens);
  const step = IMPR_STEPS[job.step] || job.step || 'en cours';
  return `<section class="card impr-job" data-impr-job="${escapeHtml(job.job_id || '')}" aria-label="Itération en cours">
    <div class="card-h"><h3>${I.activity}${escapeHtml(IMPR_KINDS[job.kind] || 'Tâche')} en cours</h3><span class="r"><span class="muted impr-job-since">depuis <span data-since="${escapeHtml(job.started_at || '')}">…</span></span></span></div>
    <div class="impr-job-body">
      <div class="impr-job-step"><span class="impr-pulse" aria-hidden="true"></span>${escapeHtml(step)}</div>
      <div class="impr-job-bar${total ? '' : ' indet'}" role="progressbar" aria-label="Cas mesurés" aria-valuemin="0" aria-valuemax="${escapeHtml(String(total))}" aria-valuenow="${escapeHtml(String(done))}"><i style="width:${escapeHtml(String(pct))}%"></i></div>
      <div class="impr-job-facts">
        <span><b class="tab-num">${escapeHtml(String(done))}</b>${total ? ` / ${escapeHtml(String(total))}` : ''} cas mesurés</span>
        <span><b class="tab-num">${escapeHtml(fmtCompact(tok))}</b> jetons</span>
        <span><b class="tab-num">${escapeHtml(String(Number(job.calls) || 0))}</b> appels Claude</span>
        ${plan === 'api' ? `<span><b class="tab-num">${escapeHtml(imprFmtUsd(job.cost_usd))}</b> (estimation)</span>` : ''}
      </div>
      <div class="impr-job-acts">${imprBtnHtml('cancel', true)}</div>
    </div>
  </section>`;
}

// --- Metriques ------------------------------------------------------------------

function imprMetricsHtml(st, auto, plan, iters) {
  const kpi = (icon, value, label, sub, cls) => `<div class="card kpi"><span class="ic">${icon}</span>
      <div style="min-width:0"><div class="k-n"><b class="tab-num">${escapeHtml(value)}</b><span class="k-l">${escapeHtml(label)}</span></div>
      <span class="k-t ${escapeHtml(cls || '')}">${escapeHtml(sub)}</span></div></div>`;
  const resolved = (st.accepted || 0) + (st.rejected || 0);
  const rate = st.acceptance_rate;
  const gain = Number(st.cumulative_gain) || 0;
  const avgTok = imprTokTotal(st.avg_tokens);
  const costSub = plan === 'api' && st.avg_cost_usd != null
    ? `~${imprFmtUsd(st.avg_cost_usd)} par itération (estimation)` : (avgTok ? 'par itération, en moyenne' : 'aucune itération lancée par Nebula');
  const limit = auto && auto.enabled ? auto.daily_budget : null;
  const durs = (iters || []).map(j => Number(j.duration_ms)).filter(d => d > 0);
  const avgMin = durs.length ? Math.max(1, Math.round(durs.reduce((a, b) => a + b, 0) / durs.length / 60000)) : 0;
  const tokSub = avgMin ? costSub + ' ; ~' + String(avgMin) + ' min' : costSub;
  return `<section class="kpis impr-kpis" aria-label="Indicateurs de la boucle">
    ${kpi(I.activity, st.last_score != null ? fmtScore(st.last_score) : '-', 'score actuel', st.last_score == null ? 'aucune mesure' : 'sur 1, jeu d\'évals', '')}
    ${kpi(I.check, rate != null ? `${Math.round(rate * 100)} %` : '-', 'gardées', resolved ? `${st.accepted || 0} sur ${resolved} tranchée${resolved > 1 ? 's' : ''}` : 'aucune modification tranchée', st.accepted ? 'ok' : '')}
    ${kpi(I.up, imprGain(gain), 'gain cumulé', 'somme des gains gardés', gain > 0 ? 'ok' : '')}
    ${kpi(I.cpu, avgTok ? fmtCompact(Math.round(avgTok)) : '-', 'jetons', tokSub, '')}
    ${kpi(I.history, limit ? `${st.today_iterations || 0} / ${limit}` : String(st.today_iterations || 0), 'aujourd\'hui', limit ? 'itérations / budget du jour' : 'mode automatique désactivé', auto && auto.budget_reached ? 'warn' : '')}
  </section>`;
}

// --- Frise des iterations + courbe ----------------------------------------------

function imprTimelineHtml(iters, scores) {
  if (!iters.length) {
    return `<section class="card impr-timeline impr-timeline-empty" aria-label="Itérations">
      <div class="card-h"><h3>${I.history}Itérations</h3></div>
      <p class="muted impr-note">Aucune itération pour l'instant. Commence par la mesure de référence (bandeau ci-dessus) : chaque modification essayée apparaîtra ensuite ici, gardée ou écartée.</p>
    </section>`;
  }
  const dots = iters.map(j => {
    const s = IMPR_STATUS[j.status] || ['mute', j.status || '?'];
    const gain = (j.score_before != null && j.score_after != null) ? j.score_after - j.score_before : null;
    const regs = j.regressions || [];
    const hc = hcAttrs([{ title: `Itération ${j.iteration} : ${s[1]}`, text: true, items: [
      j.hypothesis || 'Hypothèse non renseignée',
      `Gain : ${imprGain(gain)}`,
      `Régressions : ${regs.length}`,
      `Coût : ${j.tokens ? imprFmtTok(imprTokTotal(j.tokens)) : 'non mesuré'}`,
    ] }]);
    return `<button type="button" class="impr-dot ${escapeHtml(s[0])}" data-impr-iter="${escapeHtml(String(j.iteration))}" aria-expanded="false" aria-label="Itération ${escapeHtml(String(j.iteration))}, ${escapeHtml(s[1])}"${hc}>${escapeHtml(String(j.iteration))}</button>`;
  }).join('');
  return `<section class="card impr-timeline" aria-label="Itérations">
    <div class="card-h"><h3>${I.history}Itérations</h3><span class="r impr-legend"><span class="impr-dot ok sm" aria-hidden="true"></span>gardée<span class="impr-dot err sm" aria-hidden="true"></span>écartée<span class="impr-dot accent sm" aria-hidden="true"></span>en attente</span></div>
    <div class="impr-dots" role="group" aria-label="Frise des itérations (clic : détail)">${dots}</div>
    <div class="impr-iter-detail" data-impr-detail hidden></div>
    ${scores.length ? `<div class="impr-curve-body"><div class="impr-curve-k">Score de la configuration gardée (mesure de référence puis chaque modification gardée)</div>${scoreCurveSvg(scores)}</div>` : ''}
  </section>`;
}

function imprIterDetailHtml(j, plan) {
  const s = IMPR_STATUS[j.status] || ['mute', j.status || '?'];
  const gain = (j.score_before != null && j.score_after != null) ? j.score_after - j.score_before : null;
  const regs = j.regressions || [];
  const tok = imprTokTotal(j.tokens);
  const row = (k, v) => `<div><dt>${escapeHtml(k)}</dt><dd>${v}</dd></div>`;
  return `<div class="impr-iter-h"><b>Itération ${escapeHtml(String(j.iteration))}</b> <span class="pill ${escapeHtml(s[0])}">${escapeHtml(s[1])}</span> <span class="muted">${escapeHtml(j.date || '')}</span></div>
    ${j.hypothesis ? `<p class="impr-iter-hyp">${escapeHtml(j.hypothesis)}</p>` : ''}
    <dl class="impr-iter-dl">
      ${row('Agent modifié', j.target ? `<code class="mono">${escapeHtml(j.target)}</code>` : '-')}
      ${row('Score', `${j.score_before != null ? escapeHtml(fmtScore(j.score_before)) : '-'} -> ${j.score_after != null ? escapeHtml(fmtScore(j.score_after)) : '-'} (${escapeHtml(imprGain(gain))})`)}
      ${row('Régressions', regs.length ? regs.map(r => `<code class="mono">${escapeHtml(r)}</code>`).join(' ') : 'aucune')}
      ${row('Raison', j.reason ? `${escapeHtml(j.reason)}` : '-')}
      ${row('Commit', j.commit ? `<code class="mono">${escapeHtml(j.commit)}</code>` : (j.status === 'accepted' ? 'non commitée' : '-'))}
      ${row('Lancée', j.runner === 'nebula' ? 'par Nebula' : 'à la main (/improve)')}
      ${row('Coût', tok ? `${escapeHtml(imprFmtTok(tok))}${j.calls ? `, ${escapeHtml(String(j.calls))} appels` : ''}${plan === 'api' && j.cost_usd != null ? `, ~${escapeHtml(imprFmtUsd(j.cost_usd))} (estimation)` : ''}` : 'non mesuré')}
      ${row('Durée', j.duration_ms ? escapeHtml(`${Math.max(1, Math.round(j.duration_ms / 60000))} min`) : '-')}
    </dl>`;
}

// --- Mode automatique ------------------------------------------------------------

function imprAutoHtml(auto, plan) {
  const off = !auto;
  const on = !!(auto && auto.enabled);
  const budget = (auto && auto.daily_budget) || 3;
  let state = '<span class="pill mute">Désactivé</span>';
  if (off) state = '<span class="pill warn">Planificateur indisponible</span>';
  else if (on && auto.paused_until) {
    state = `<span class="pill warn">En pause jusqu'à ${escapeHtml(imprTime(auto.paused_until))}${auto.pause_reason === 'quota' ? ' (quota)' : ''}</span>`;
  } else if (on && auto.budget_reached) state = '<span class="pill warn">Budget du jour atteint</span>';
  else if (on) state = '<span class="pill ok">Actif</span>';
  const opts = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(n => `<option value="${escapeHtml(String(n))}"${n === budget ? ' selected' : ''}>${escapeHtml(String(n))}</option>`).join('');
  return `<section class="card impr-auto" aria-label="Mode automatique">
    <div class="card-h"><h3>${I.zap}Mode automatique</h3><span class="r">${state}</span></div>
    <div class="impr-auto-row">
      <label class="impr-auto-sw"><span class="switch"><input type="checkbox" data-impr-auto${on ? ' checked' : ''}${off ? ' disabled' : ''}><span class="switch-slider"></span></span><span>Lancer les itérations tout seul</span></label>
      <label class="impr-auto-budget"><span>Itérations par jour</span><select class="select" data-impr-budget${off ? ' disabled' : ''}>${opts}</select></label>
    </div>
    <p class="muted impr-note">Nebula enchaîne les itérations en tâche de fond, dans la limite du budget du jour, et s'arrête tout seul sur un quota atteint ou après plusieurs modifications écartées de suite. Les modifications gardées sont commitées automatiquement (jamais poussées).${plan === 'api' && auto && auto.spent_today ? ` Dépensé aujourd'hui : ~${escapeHtml(imprFmtUsd(auto.spent_today))} (estimation).` : ''}</p>
    <p class="muted impr-note">Avant chaque itération, Nebula vérifie qu'aucune session Claude n'est ouverte ici, mais il ne voit que les sessions lancées par Nebula ou récemment actives : ferme celles ouvertes à la main.</p>
  </section>`;
}

// --- Pistes d'amelioration ------------------------------------------------------------

function imprTodoHtml(items, registers) {
  const imp = registers.improvements || {};
  const done = imp.DONE || 0;
  const list = items.length
    ? `<ul class="impr-todo">${items.map(t => `<li><span class="pill ${t.priority === 'P1' ? 'warn' : 'mute'}">${escapeHtml(t.priority || '-')}</span><span class="impr-todo-t">${escapeHtml(t.title || '')}</span>${t.date ? `<small class="muted">${escapeHtml(t.date)}</small>` : ''}</li>`).join('')}</ul>`
    : '<p class="muted impr-note">Aucune piste en attente. Les frictions notées comme <code class="mono">[TODO]</code> dans <code class="mono">improvements.md</code> apparaîtront ici.</p>';
  return `<section class="card impr-pistes" aria-label="Pistes d'amélioration">
    <div class="card-h"><h3>${I.book}Pistes d'amélioration</h3><span class="r"><span class="pill mute">${escapeHtml(String(items.length))} à essayer</span>${done ? ` <span class="pill ok">${escapeHtml(String(done))} faite${done > 1 ? 's' : ''}</span>` : ''}</span></div>
    <p class="muted impr-note">Le critique lit ces pistes pour choisir la prochaine modification à essayer.</p>
    ${list}
  </section>`;
}

// --- Jeu d'evals ------------------------------------------------------------------

const IMPR_GRADERS = { test: 'test automatique', regex: 'motif attendu', exact: 'réponse exacte', rubric: 'grille (évaluateur)' };
const IMPR_RESULTS = { pass: ['ok', 'réussi'], fail: ['err', 'échoué'], unrunnable: ['warn', 'inexécutable'] };

function imprCasesHtml(impr, team, wsId) {
  const cases = impr.cases || [];
  const evals = impr.evals || {};
  const loop = impr.loop || {};
  const pass = cases.filter(c => c.last_result === 'pass').length;
  const measured = cases.filter(c => c.last_result).length;
  const rows = cases.map(c => {
    const r = IMPR_RESULTS[c.last_result] || ['mute', 'pas encore mesuré'];
    return `<div class="impr-case" role="row"><code class="mono" role="cell">${escapeHtml(c.id || '')}</code><span role="cell">${escapeHtml(c.agent || '-')}</span><span role="cell" class="muted">${escapeHtml(IMPR_GRADERS[c.grader] || c.grader || '-')}</span><span role="cell"><span class="pill ${escapeHtml(r[0])}">${escapeHtml(r[1])}</span></span></div>`;
  }).join('');
  const lock = evals.locked
    ? (evals.unlocked ? '<span class="pill warn">Déverrouillé localement</span>' : '<span class="pill ok">Verrouillé</span>')
    : '<span class="pill warn">Non verrouillé</span>';
  const prefix = team && team.prefix ? team.prefix : wsId;
  return `<section class="card impr-cases" aria-label="Jeu d'évals">
    <div class="card-h"><h3>${I.shield}Jeu d'évals</h3><span class="r">${measured ? `<span class="pill ${pass === measured ? 'ok' : 'mute'}">${escapeHtml(String(pass))} / ${escapeHtml(String(measured))} réussis</span>` : ''}</span></div>
    <p class="muted impr-note">Les cas qui servent à noter l'équipe. Ils sont figés : la boucle ne peut pas modifier ce qui la mesure.</p>
    ${cases.length ? `<div class="impr-case-rows" role="table" aria-label="Cas d'évaluation"><div class="impr-case h" role="row"><span role="columnheader">Cas</span><span role="columnheader">Agent</span><span role="columnheader">Notation</span><span role="columnheader">Dernier résultat</span></div>${rows}</div>` : '<p class="muted impr-note">Aucun cas.</p>'}
    <details class="impr-tech">
      <summary>Détails techniques</summary>
      <div class="impr-facts">
        <div><b class="tab-num">${escapeHtml(String(evals.cases || 0))}</b><span>cas dans <code class="mono">eval-set.jsonl</code></span></div>
        <div><b class="tab-num">${escapeHtml(String(evals.holdout_cases || 0))}</b><span>cas cachés (<code class="mono">holdout.jsonl</code>)</span></div>
        <div><b class="tab-num">${escapeHtml(String(loop.runs_per_eval || 1))}</b><span>passe(s) par cas noté par l'évaluateur</span></div>
        <div><b class="tab-num mono impr-hash">${escapeHtml(impr.config_hash || '-')}</b><span>empreinte de la configuration ${impr.baseline_current ? '(mesure de référence à jour)' : '(pas de mesure de référence à jour)'}</span></div>
      </div>
      <p class="muted impr-note">${lock} Le hook <code class="mono">evals-lock.py</code> refuse toute écriture sous <code class="mono">.claude/evals/</code> ; pour ajouter un cas : <code class="mono">/eval-add</code> dans Claude, puis <code class="mono">"evals_unlocked": true</code> dans <code class="mono">.claude/settings.local.json</code> le temps de l'édition.</p>
      <p class="muted impr-note">À la main dans Claude : <code class="mono">/eval</code> (score actuel), <code class="mono">/improve</code> (une itération, en deux sessions), <code class="mono">/team &lt;objectif&gt;</code> (agents <code class="mono">${escapeHtml(prefix)}-*</code>).</p>
    </details>
  </section>`;
}

// --- Avertissements d'abonnement --------------------------------------------------

function imprWarningsHtml(warnings) {
  const list = (warnings || []).filter(w => w && w.message);
  if (!list.length) return '';
  return `<ul class="impr-warns">${list.map(w => `<li class="impr-warn ${w.level === 'alert' ? 'alert' : 'info'}">${w.level === 'alert' ? I.alert : I.info}<span>${escapeHtml(w.message)}${(w.agents || []).length ? ` <small>(${escapeHtml((w.agents || []).join(', '))})</small>` : ''}</span></li>`).join('')}</ul>`;
}

// Texte de la confirmation d'un lancement : appels Claude attendus, cout
// moyen constate (jetons ; $ seulement en facturation a l'usage).
function imprCostNoteHtml(kind, impr, plan) {
  const st = impr.stats || {};
  const n = (impr.evals || {}).cases || 0;
  const runs = (impr.loop || {}).runs_per_eval || 1;
  const avgTok = imprTokTotal(st.avg_tokens);
  const what = kind === 'iteration'
    ? 'Une itération lance environ une quinzaine d\'appels Claude : mesure de référence si besoin, proposition du critique, mesure de la modification à l\'essai.'
    : (kind === 'resolve'
      ? `Trancher mesure la modification à l'essai : environ ${n} appel(s) Claude (un par cas d'éval${runs > 1 ? `, ${runs} passes pour les cas notés par l'évaluateur` : ''}).`
      : `Une mesure lance environ ${n} appel(s) Claude (un par cas d'éval${runs > 1 ? `, ${runs} passes pour les cas notés par l'évaluateur` : ''}).`);
  const avg = avgTok ? `Ici, une itération coûte en moyenne ${imprFmtTok(avgTok)}${plan === 'api' && st.avg_cost_usd != null ? `, soit ~${imprFmtUsd(st.avg_cost_usd)} (estimation)` : ''}.` : '';
  return `<p>${escapeHtml(what)}</p>${avg ? `<p>${escapeHtml(avg)}</p>` : ''}<p class="muted">Tout tourne en tâche de fond dans ce workspace, avec ton abonnement Claude. Tu peux arrêter à tout moment.</p>`;
}

// --- Confirmations ------------------------------------------------------------------

// Modale de confirmation au contenu HTML (construit par les fonctions
// ci-dessus, deja echappe). Resout true sur le bouton d'action.
function imprConfirm({ title, html, confirmLabel, danger = false }) {
  return new Promise(resolve => {
    let done = false;
    const body = el('div', 'impr-confirm', html);
    body.setAttribute('data-impr-modal', '');
    const cancel = btn('Annuler', 'btn-ghost');
    const ok = btn(confirmLabel, danger ? 'btn-danger' : 'btn-primary');
    const { close } = openModal({ title, body, footer: [cancel, ok], onClose: () => { if (!done) { done = true; resolve(false); } } });
    cancel.addEventListener('click', () => close());
    ok.addEventListener('click', () => { done = true; resolve(true); close(); });
  });
}

// --- Actions --------------------------------------------------------------------

function imprBind(wsId, host) {
  host.addEventListener('click', (e) => {
    const b = e.target.closest('[data-impr-act]');
    if (b && host.contains(b)) { imprAction(wsId, host, b.dataset.imprAct, b); return; }
    const d = e.target.closest('[data-impr-iter]');
    if (d && host.contains(d)) imprToggleIter(host, d);
  });
  host.addEventListener('change', (e) => {
    const t = e.target;
    if (t.matches('[data-impr-auto]')) imprToggleAuto(wsId, host, t);
    else if (t.matches('[data-impr-budget]')) imprSetBudget(wsId, host, t);
  });
}

function imprToggleIter(host, dot) {
  const box = host.querySelector('[data-impr-detail]');
  const data = host._imprData;
  if (!box || !data) return;
  const n = Number(dot.dataset.imprIter);
  const open = dot.getAttribute('aria-expanded') === 'true';
  for (const x of host.querySelectorAll('[data-impr-iter]')) x.setAttribute('aria-expanded', 'false');
  if (open) { box.hidden = true; return; }
  const j = data.iters.find(x => x.iteration === n);
  if (!j) return;
  box['innerHTML'] = imprIterDetailHtml(j, data.plan);
  box.hidden = false;
  dot.setAttribute('aria-expanded', 'true');
}

async function imprAction(wsId, host, act, b) {
  const data = host._imprData || {};
  const impr = data.impr || {};
  const sub = await imprSubscription(wsId);
  const plan = (sub && sub.plan) || data.plan || 'unknown';
  const warn = imprWarningsHtml(sub && sub.warnings);
  if (act === 'run' || act === 'measure' || act === 'resolve') {
    const kind = act === 'run' ? 'iteration' : act;
    const labels = { iteration: ['Lancer une itération', 'Lancer'], measure: ['Mesure de référence', 'Mesurer'], resolve: ['Trancher maintenant', 'Mesurer et trancher'] };
    const ok = await imprConfirm({ title: labels[kind][0], html: imprCostNoteHtml(kind, impr, plan) + warn, confirmLabel: labels[kind][1] });
    if (ok) await imprLaunch(wsId, host, kind, b);
  } else if (act === 'abandon') {
    const ok = await imprConfirm({ title: 'Abandonner ce candidat', confirmLabel: 'Abandonner', danger: true,
      html: '<p>La modification à l\'essai est retirée et l\'agent revient à sa version précédente. L\'itération est notée écartée dans le journal.</p>' });
    if (ok) await imprPost(wsId, host, b, `/api/workspaces/${wsId}/improvement/abandon`, {}, 'Abandon en cours : l\'agent va être restauré');
  } else if (act === 'cancel') {
    const ok = await imprConfirm({ title: 'Arrêter', confirmLabel: 'Arrêter', danger: true,
      html: '<p>L\'itération en cours est interrompue (la modification à l\'essai éventuelle reste en attente de verdict). Le mode automatique est aussi désactivé.</p>' });
    if (!ok) return;
    try {
      const r = await withBusy(b, () => API.post(`/api/workspaces/${wsId}/improvement/stop`, {}));
      toast(r.cancelled ? 'Arrêt demandé : l\'itération s\'interrompt' : 'Rien ne tournait ; mode automatique désactivé', r.cancelled ? 'success' : 'info');
      await renderWsImprovement(wsId, host, { quiet: true });
    } catch (e) { toastErr(e.message); }
  } else if (act === 'resume') {
    const auto = impr.auto || {};
    if (auto.enabled) {
      await imprPost(wsId, host, b, `/api/workspaces/${wsId}/improvement/auto`, { resume: true }, 'Reprise enregistrée : le mode automatique repart');
      return;
    }
    const ok = await imprConfirm({ title: 'Reprendre', confirmLabel: 'Lancer une itération',
      html: '<p>Tu as revu les modifications écartées : Nebula relance une itération.</p>' + imprCostNoteHtml('iteration', impr, plan) + warn });
    if (!ok) return;
    try { await API.post(`/api/workspaces/${wsId}/improvement/auto`, { resume: true }); } catch { /* accuse de reception facultatif hors mode auto */ }
    await imprLaunch(wsId, host, 'iteration', b);
  }
}

async function imprPost(wsId, host, b, url, body, okMsg, forced = false) {
  try {
    const r = await withBusy(b, () => API.postStatus(url, body));
    if (r.status === 409 && r.data.reason === 'session' && !forced) {
      const go = await imprConfirm({ title: 'Session Claude ouverte ?', confirmLabel: 'Lancer quand même',
        html: `<p>${escapeHtml(r.data.error || 'Une session Claude semble ouverte dans ce workspace.')}</p><p class="muted">Si une session travaille ici en même temps, elle peut modifier les agents et fausser le résultat. Ferme-la, ou continue si elle est inactive.</p>` });
      if (go) return await imprPost(wsId, host, b, url, { ...body, force_session: true }, okMsg, true);
      return false;
    }
    if (!r.ok) { toastErr(imprErrText(r)); return false; }
    imprAwaitJob(wsId, r);
    toastOk(okMsg);
    await renderWsImprovement(wsId, host, { quiet: true });
    return true;
  } catch (e) { toastErr(e.message); return false; }
}

// Lancement d'un job : 202 -> toast + suivi ; 409 `session` -> proposition
// de forcer ; 409 `running` (un job tourne deja sur le poste) -> message.
function imprErrText(r) {
  const d = r.data || {};
  if (r.status === 409 && d.reason === 'daily_budget') {
    const m = /\(([^)]*)\)/.exec(d.error || '');
    return `Plafond du jour atteint${m ? ` (${m[1]})` : ''} : réessaie demain`;
  }
  return d.error || `HTTP ${r.status}`;
}

async function imprLaunch(wsId, host, kind, b, force = false) {
  let r;
  try {
    r = await withBusy(b, () => API.postStatus(`/api/workspaces/${wsId}/improvement/run`, { kind, force_session: force }));
  } catch (e) { toastErr(e.message); return; }
  if (r.status === 202 || r.ok) {
    imprAwaitJob(wsId, r);
    toastOk(kind === 'measure' ? 'Mesure de référence lancée' : (kind === 'resolve' ? 'Verdict lancé : mesure de la modification à l\'essai' : 'Itération lancée'));
    await renderWsImprovement(wsId, host, { quiet: true });
    return;
  }
  if (r.status === 409 && r.data.reason === 'session' && !force) {
    const go = await imprConfirm({ title: 'Session Claude ouverte ?', confirmLabel: 'Lancer quand même',
      html: `<p>${escapeHtml(r.data.error || 'Une session Claude semble ouverte dans ce workspace.')}</p><p class="muted">Si une session travaille ici en même temps, elle peut modifier les agents pendant la mesure et fausser le verdict. Ferme-la, ou lance quand même si elle est inactive.</p>` });
    if (go) await imprLaunch(wsId, host, kind, b, true);
    return;
  }
  toastErr(imprErrText(r));
  if (r.status === 409) renderWsImprovement(wsId, host, { quiet: true });
}

async function imprToggleAuto(wsId, host, input) {
  const want = input.checked;
  const sel = host.querySelector('[data-impr-budget]');
  const budget = sel ? Number(sel.value) : 3;
  if (want) {
    const sub = await imprSubscription(wsId);
    const ok = await imprConfirm({ title: 'Activer le mode automatique', confirmLabel: 'Activer',
      html: `<p>Nebula lancera jusqu'à ${escapeHtml(String(budget))} itération(s) par jour, seul, en tâche de fond (une quinzaine d'appels Claude chacune).</p><p><b>Les modifications gardées seront commitées automatiquement</b> sur la branche courante du workspace, jamais poussées.</p><p class="muted">Nebula ne voit que les sessions lancées par Nebula ou récemment actives : ferme les sessions Claude ouvertes à la main ici.</p>${imprWarningsHtml(sub && sub.warnings)}` });
    if (!ok) { input.checked = false; return; }
  }
  input.disabled = true;
  try {
    await API.post(`/api/workspaces/${wsId}/improvement/auto`, want ? { enabled: true, daily_budget: budget } : { enabled: false });
    toastOk(want ? 'Mode automatique activé' : 'Mode automatique désactivé');
    await renderWsImprovement(wsId, host, { quiet: true });
  } catch (e) {
    input.checked = !want;
    input.disabled = false;
    toastErr(e.message);
  }
}

async function imprSetBudget(wsId, host, sel) {
  sel.disabled = true;
  try {
    await API.post(`/api/workspaces/${wsId}/improvement/auto`, { daily_budget: Number(sel.value) });
    toastOk(`Budget du jour : ${sel.value} itération${Number(sel.value) > 1 ? 's' : ''}`);
    await renderWsImprovement(wsId, host, { quiet: true });
  } catch (e) {
    sel.disabled = false;
    toastErr(e.message);
  }
}

// --- Suivi en direct ------------------------------------------------------------------

function imprStartPolling(wsId, host) {
  imprStopPolling(wsId);
  const live = { wsId, host, timer: null, running: false, jobId: null, lastFull: Date.now(), sig: null, inflight: false };
  live.timer = setInterval(() => imprTick(live), IMPR_TICK_MS);
  registerPagePoller(live.timer);
  IMPR_LIVE[wsId] = live;
  if (!imprStartPolling._vis) {
    imprStartPolling._vis = true;
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) return;
      for (const l of Object.values(IMPR_LIVE)) { l.lastFull = 0; imprTick(l); }
    });
  }
}

function imprStopPolling(wsId) {
  const l = IMPR_LIVE[wsId];
  if (!l) return;
  clearInterval(l.timer);
  delete IMPR_LIVE[wsId];
}

// Vrai si le polling de l'onglet tourne encore (intervalle enregistre).
function imprPollingActive(wsId) {
  const l = IMPR_LIVE[wsId];
  return !!(l && l.host.isConnected && STATE.pagePollers.includes(l.timer));
}

async function imprTick(live) {
  if (IMPR_LIVE[live.wsId] !== live) return;
  if (!live.host.isConnected || !STATE.pagePollers.includes(live.timer)) { imprStopPolling(live.wsId); return; }
  if (document.hidden || live.host.closest('[hidden]') || live.inflight) return;
  live.inflight = true;
  try {
    if (live.running) await imprPollJob(live);
    else if (Date.now() - live.lastFull >= IMPR_FULL_MS) await imprPollFull(live);
  } catch { /* silencieux : prochaine tentative au tick suivant */ }
  finally { live.inflight = false; }
}

async function imprPollJob(live) {
  const { wsId, host } = live;
  const r = await API.get(`/api/workspaces/${wsId}/improvement/job`);
  if (IMPR_LIVE[wsId] !== live || !host.isConnected) return;
  const job = r.job || null;
  if (job && job.status === 'running') {
    const data = host._imprData || {};
    const panel = host.querySelector('.impr-job');
    if (panel && !panel.querySelector('[aria-busy="true"]')) panel.replaceWith(el('div', null, imprJobPanelHtml(job, data.plan)).firstElementChild);
    const next = host.querySelector('.impr-next');
    if (next && !next.querySelector('[aria-busy="true"]') && r.next_step) {
      next.replaceWith(el('div', null, imprNextStepHtml(r.next_step, data.impr && data.impr.pending)).firstElementChild);
    }
    if (live.jobId && job.job_id !== live.jobId) live.jobId = job.job_id;
    return;
  }
  // Fin du job : tout l'onglet est relu, puis toast du verdict.
  live.running = false;
  await renderWsImprovement(wsId, host, { quiet: true });
  if (job) imprJobEndToast(job);
}

async function imprPollFull(live) {
  const { wsId, host } = live;
  const impr = await API.get(`/api/workspaces/${wsId}/improvement`);
  if (IMPR_LIVE[wsId] !== live || !host.isConnected) return;
  live.lastFull = Date.now();
  const running = !!(impr.job && impr.job.status === 'running');
  if (imprSig(impr) === live.sig) return;
  if (!running && imprTeamDirty(host)) return;
  const data = host._imprData || {};
  const team = await API.get(`/api/workspaces/${wsId}/team`).catch(() => data.team || null);
  if (IMPR_LIVE[wsId] !== live || !host.isConnected) return;
  host._imprGen = (host._imprGen || 0) + 1;
  imprPaint(wsId, host, impr, team, data.sub || null);
}

function imprJobEndToast(job) {
  const it = job.iteration != null ? `Itération ${job.iteration} : ` : '';
  const score = job.score != null ? ` (score ${fmtScore(job.score)})` : '';
  if (job.status === 'succeeded') {
    if (job.kind === 'abandon') toastOk('Candidat abandonné : l\'agent est restauré');
    else if (job.kind === 'measure') toastOk(`Mesure de référence terminée${score}`);
    else if (job.verdict === 'accepted') toastOk(`${it}modification gardée${score}`);
    else if (job.verdict === 'rejected') toast(`${it}modification écartée${score}`, 'info', 6000);
    else if (job.verdict === 'refused') toastErr(`Itération refusée : fichiers de l'équipe modifiés et non commités${job.dirty_paths && job.dirty_paths.length ? ` (${job.dirty_paths.slice(0, 3).join(', ')})` : ''}. Commite-les ou annule-les.`);
    else if (job.verdict === 'pending') toast(`${it}modification à l'essai, en attente de verdict`, 'info', 6000);
    else toastOk('Tâche terminée');
  } else if (job.status === 'cancelled') toast('Itération arrêtée', 'info');
  else if (job.status === 'quota') toast(`Quota Claude atteint${job.quota_reset ? `, reprise vers ${imprTime(job.quota_reset)}` : ''}`, 'error', 8000);
  else if (job.status === 'budget') toastErr('Plafond de coût atteint : itération arrêtée');
  else if (job.status === 'timeout') toastErr('Itération trop longue : arrêtée');
  else if (job.status === 'interrupted') toastErr('Itération interrompue (serveur redémarré)');
  else toastErr(`Échec de l'itération${job.error ? ` : ${job.error}` : ''}`);
}

// --- Carte « Equipe : modele et effort » --------------------------------------------

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
// Avertissements d'abonnement en tete ; iteration en attente : selecteurs
// verrouilles + « Trancher maintenant » / « Abandonner » ; job en cours :
// selecteurs verrouilles (409 `job_running` sinon).
function teamConfigCard(wsId, host, team, impr, sub) {
  const card = el('section', 'card impr-team');
  card.setAttribute('aria-label', 'Modèle et effort des agents');
  const models = team.model_aliases || Object.keys(IMPR_MODEL_LABELS);
  const efforts = team.effort_levels || Object.keys(IMPR_EFFORT_LABELS);
  const sugg = {};
  for (const s of team.suggestions || []) sugg[s.agent] = s;
  const basis = team.suggestions_basis || {};
  const pend = impr && impr.pending;
  const running = !!(impr && impr.job && impr.job.status === 'running');
  const locked = !!pend || running;
  const note = IMPR_TEAM_NOTES[wsId];
  delete IMPR_TEAM_NOTES[wsId];
  const warnHtml = imprWarningsHtml(sub && sub.warnings);

  const basisPill = basis.measured
    ? `<span class="pill info" title="Propositions = règles par rôle + signal mesuré (agent avec au moins 2 cas et moins de la moitié réussis : effort +1 cran)">Mesure du ${escapeHtml(basis.date || '?')}</span>`
    : '<span class="pill mute" title="Aucune ligne du journal avec liste d\'échecs : propositions issues des seules règles par rôle. Lance une mesure pour un signal mesuré.">Règles seules (aucune mesure)</span>';
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
        <select class="select" data-k="model" data-cur="${escapeHtml(cur.model || '')}">${opt(models.includes(cur.model) ? models : [cur.model, ...models], cur.model, v => IMPR_MODEL_LABELS[v] || v)}</select></label>
      <label class="impr-team-sel" role="cell"><span class="sr-only">Effort de ${escapeHtml(a.id)}</span>
        <select class="select" data-k="effort" data-cur="${escapeHtml(cur.effort)}">${opt(['', ...efforts], cur.effort, imprEffortLabel)}</select></label>
      <span class="impr-team-prop" role="cell">${prop}</span>
      <span class="impr-team-act" role="cell"></span>
    </div>`;
  }).join('');

  const noteHtml = !note ? '' : (note.written
    ? `<p class="impr-team-msg ${note.stale ? 'warn' : 'ok'}">${I.check}<span>${escapeHtml(String(note.generated))} agent${note.generated > 1 ? 's' : ''} régénéré${note.generated > 1 ? 's' : ''}.${note.stale ? ' La mesure de référence est périmée : refais-la (bandeau « Prochaine étape »).' : ' Les agents modifiés servent dès la prochaine itération.'}${note.manual ? ` ${escapeHtml(String(note.manual))} agent${note.manual > 1 ? 's' : ''} édité${note.manual > 1 ? 's' : ''} à la main non réécrit${note.manual > 1 ? 's' : ''}.` : ''}</span></p>`
    : `<p class="impr-team-msg">${I.info}<span>Aucun changement : la configuration était déjà celle-ci.</span></p>`);
  const pendHtml = !pend ? '' : `<div class="impr-team-msg warn">${I.alert}<span>Itération ${escapeHtml(String(pend.iteration))} en attente de verdict : tranche-la ou abandonne-la avant de changer un modèle ou un effort, sinon la modification à l'essai serait mesurée sur une autre configuration.</span><span class="impr-team-msg-acts">${pend.in_place ? imprBtnHtml('resolve', true) : ''}${imprBtnHtml('abandon', true)}</span></div>`;
  const runHtml = running && !pend ? `<p class="impr-team-msg">${I.info}<span>Une itération tourne : modèle et effort se modifient à sa fin (ou après l'avoir arrêtée).</span></p>` : '';

  card['innerHTML'] = `<div class="card-h"><h3>${I.sliders}Équipe : modèle et effort</h3><span class="r">${basisPill}</span></div>
    <p class="muted impr-note">Modèle et effort de raisonnement de chaque agent, écrits dans <code class="mono">.claude/team.json</code> puis rendus dans l'agent généré. Les propositions ne font que compléter : la règle du rôle propose un modèle seulement à un agent qui n'en déclare pas, et un effort (jamais au-delà de « élevé ») seulement s'il est au-dessus de l'actuel ; un agent sans effort est compté comme « moyen » (défaut de Claude Code sur les modèles 5.5), la règle peut donc lui proposer « élevé ». S'il existe une mesure, un agent en échec reçoit +1 cran d'effort. Jamais de baisse d'effort, jamais de changement d'un modèle déclaré. Rien n'est appliqué sans clic.</p>
    ${warnHtml}
    ${noteHtml}
    ${pendHtml}
    ${runHtml}
    <div class="impr-team-rows" role="table" aria-label="Modèle et effort par agent">
      <div class="impr-team-row h" role="row"><span role="columnheader">Agent</span><span role="columnheader">Modèle</span><span role="columnheader">Effort</span><span role="columnheader">Proposition</span><span role="columnheader"><span class="sr-only">Action</span></span></div>
      ${rows}
    </div>
    <div class="impr-team-foot"></div>`;

  const save = async (b, payload) => {
    let r;
    try {
      r = await withBusy(b, () => API.postStatus(`/api/workspaces/${wsId}/team/agents-config`, { agents: payload }));
    } catch (e) { toastErr(e.message); return; }
    if (!r.ok) {
      if (r.status === 409 && r.data.reason === 'job_running') toastErr('Une itération est en cours : attends sa fin ou arrête-la avant de changer modèle ou effort.');
      else if (r.status === 409 && r.data.reason === 'pending') toastErr('Une modification à l\'essai attend son verdict : tranche-la ou abandonne-la d\'abord.');
      else toastErr(r.data.error || `HTTP ${r.status}`);
      if (r.status === 409) renderWsImprovement(wsId, host, { quiet: true });
      return;
    }
    const d = r.data;
    const manual = (d.skipped || []).filter(s => /main/.test(s.reason || '')).length;
    IMPR_TEAM_NOTES[wsId] = { written: d.written, stale: d.baseline_stale, generated: (d.generated || []).length, manual };
    toastOk(d.written ? 'Configuration de l\'équipe enregistrée' : 'Aucun changement');
    await renderWsImprovement(wsId, host, { quiet: true });
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
    if (locked) { selM.disabled = true; selE.disabled = true; }
    const saveBtn = btn('Enregistrer', 'btn-sm btn-primary', I.check);
    saveBtn.hidden = true;
    saveBtn.addEventListener('click', () => save(saveBtn, { [id]: { model: selM.value, effort: selE.value || null } }));
    const sync = () => { saveBtn.hidden = selM.value === cur.model && selE.value === cur.effort; if (applyBtn) applyBtn.hidden = !saveBtn.hidden; };
    let applyBtn = null;
    if (s && !locked) {
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
  const dots = pts.map(([x, y], i) => `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="4" class="d"><title>${i === 0 ? 'Mesure de référence' : `Modification gardée ${i}`} : ${escapeHtml(fmtScore(scores[i]))}</title></circle>`).join('');
  const labels = pts.map(([x], i) => (n <= 12 || i === 0 || i === n - 1 || i % Math.ceil(n / 12) === 0)
    ? `<text x="${x.toFixed(1)}" y="${H - 6}" text-anchor="middle" class="t">${i === 0 ? 'réf.' : i}</text>` : '').join('');
  return `<svg class="impr-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="Évolution du score : ${scores.map(s => escapeHtml(fmtScore(s))).join(', ')}">
    ${grid}${area ? `<path d="${area}" class="a"/>` : ''}<path d="${line}" class="l"/>${dots}${labels}</svg>`;
}
