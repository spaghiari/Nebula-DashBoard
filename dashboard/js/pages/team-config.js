/* ================================================================
   Nebula - Ligne « Modèle et effort » du module claude-team
   ----------------------------------------------------------------
   mountTeamConfigRow (appelé par renderWsOverlays, app.js) : sous
   « Routage » et « Relecture du code » de la ligne du module, un résumé
   (ex. « 7 agents · opus ×4, sonnet ×3 ») + bouton « Régler » qui déplie la
   table par agent (repliée par défaut), et un badge « N agent(s) à
   régénérer » + bouton « Régénérer » si GET /team renvoie `stale_agents`.

   Données :
   - GET /api/workspaces/<id>/team : agents, suggestions, effort_levels,
     model_aliases, pending, stale_agents (absent = liste vide) ;
   - GET /api/claude/subscription?ws=<id> : avertissements d'abonnement.
   Écriture : POST /api/workspaces/<id>/team/agents-config
   ({"agents": {}} = régénère sans rien changer).

   Dépendances foundations : API, escapeHtml, el, btn, I.*, withBusy, toast*.
   ================================================================ */
'use strict';

const IMPR_SUB = {};                // wsId -> {at, promise} (abonnement, 60 s)
// Libelles des alias de modele et des niveaux d'effort (valeurs = celles de
// dashcore/config.py TEAM_MODEL_ALIASES / TEAM_EFFORT_LEVELS, renvoyees par
// GET /team ; un alias inconnu s'affiche tel quel).
const IMPR_MODEL_LABELS = { sonnet: 'sonnet (rapide)', opus: 'opus (profond)', haiku: 'haiku (léger)', fable: 'fable', inherit: 'inherit (session)' };
const IMPR_EFFORT_LABELS = { low: 'faible', medium: 'moyen', high: 'élevé', xhigh: 'très élevé', max: 'max' };

function imprSubscription(wsId, fresh = false) {
  const c = IMPR_SUB[wsId];
  if (!fresh && c && Date.now() - c.at < 60000) return c.promise;
  const promise = API.get(`/api/claude/subscription?ws=${encodeURIComponent(wsId)}`).catch(() => null);
  IMPR_SUB[wsId] = { at: Date.now(), promise };
  return promise;
}

function imprEffortLabel(e) {
  return e ? (IMPR_EFFORT_LABELS[e] || e) : 'par défaut';
}

function imprWarningsHtml(warnings) {
  const list = (warnings || []).filter(w => w && w.message);
  if (!list.length) return '';
  return `<ul class="impr-warns">${list.map(w => `<li class="impr-warn ${w.level === 'alert' ? 'alert' : 'info'}">${w.level === 'alert' ? I.alert : I.info}<span>${escapeHtml(w.message)}${(w.agents || []).length ? ` <small>(${escapeHtml((w.agents || []).join(', '))})</small>` : ''}</span></li>`).join('')}</ul>`;
}

// Résumé « 7 agents · opus ×4, sonnet ×3 » (modèles effectifs).
function teamCfgSummary(team) {
  const agents = team.agents || [];
  if (!agents.length) return 'Aucun agent';
  const by = {};
  for (const a of agents) {
    const m = a.effective_model || a.model || '?';
    by[m] = (by[m] || 0) + 1;
  }
  const parts = Object.entries(by).sort((x, y) => y[1] - x[1] || x[0].localeCompare(y[0])).map(([m, n]) => `${m} ×${n}`);
  return `${agents.length} agent${agents.length > 1 ? 's' : ''} · ${parts.join(', ')}`;
}

// Monte la ligne dans `slot` (conteneur `.mod-routing` de la ligne du module).
async function mountTeamConfigRow(wsId, slot) {
  const gen = (slot._tcGen || 0) + 1;
  slot._tcGen = gen;
  let team;
  try {
    team = await API.get(`/api/workspaces/${wsId}/team`);
  } catch (e) {
    if (slot._tcGen !== gen) return;
    slot['innerHTML'] = `<div class="mod-routing-row"><span class="mod-routing-l">Modèle et effort</span><span class="muted">Lecture impossible : ${escapeHtml(e.message)}</span></div>`;
    return;
  }
  if (slot._tcGen !== gen || !slot.isConnected) return;
  const open = !!slot._tcOpen;
  const stale = Array.isArray(team.stale_agents) ? team.stale_agents : [];
  const refresh = () => mountTeamConfigRow(wsId, slot);
  slot['innerHTML'] = `<div class="mod-routing-row"><span class="mod-routing-l">Modèle et effort</span><span class="mono" data-tc-summary>${escapeHtml(teamCfgSummary(team))}</span>${stale.length ? `<span class="pill warn" title="${escapeHtml(stale.join(', '))}">${escapeHtml(String(stale.length))} agent${stale.length > 1 ? 's' : ''} à régénérer</span>` : ''}<span class="mod-teamcfg-acts"></span></div><div class="mod-teamcfg-body" hidden></div>`;
  const acts = slot.querySelector('.mod-teamcfg-acts');
  const bodyEl = slot.querySelector('.mod-teamcfg-body');
  if (stale.length) {
    const regen = btn('Régénérer', 'btn-sm', I.refresh);
    regen.title = 'Réécrit les agents générés depuis leur corps .claude/team/agents/<id>.md (aucun réglage modifié)';
    if (team.pending) {
      regen.disabled = true;
      regen.title = 'Indisponible : une itération /improve attend son verdict (la trancher d\'abord, nouvelle session puis /improve), sinon le candidat serait mesuré sur une autre configuration.';
    }
    regen.addEventListener('click', async () => {
      let r;
      try {
        r = await withBusy(regen, () => API.postStatus(`/api/workspaces/${wsId}/team/agents-config`, { agents: {} }));
      } catch (e) { toastErr(e.message); return; }
      if (!r.ok) {
        if (r.status === 409 && (r.data.reason === 'pending' || r.data.pending)) toastErr('Une modification à l\'essai attend son verdict : tranche-la d\'abord.');
        else toastErr(r.data.error || `HTTP ${r.status}`);
        if (r.status === 409) refresh();
        return;
      }
      const n = (r.data.generated || []).length;
      toastOk(n ? `${n} agent${n > 1 ? 's' : ''} régénéré${n > 1 ? 's' : ''}` : 'Agents à jour');
      refresh();
    });
    acts.appendChild(regen);
  }
  const toggle = btn('Régler', 'btn-sm', I.sliders);
  toggle.setAttribute('aria-expanded', 'false');
  acts.appendChild(toggle);
  const fill = async () => {
    if (bodyEl.childElementCount) return;
    const sub = await Promise.race([imprSubscription(wsId), new Promise(r => setTimeout(() => r(null), 2500))]);
    if (!bodyEl.childElementCount) bodyEl.appendChild(teamConfigCard(wsId, refresh, team, sub));
  };
  const setOpen = (v) => {
    slot._tcOpen = v;
    bodyEl.hidden = !v;
    toggle.setAttribute('aria-expanded', String(v));
    toggle.lastChild.textContent = v ? 'Replier' : 'Régler';
    if (v) fill();
  };
  toggle.addEventListener('click', () => setOpen(!slot._tcOpen));
  if (open) setOpen(true);
}

// Table « modèle et effort » : une ligne par agent (sélecteurs modèle +
// effort, proposition expliquée, « Appliquer »), « Appliquer toutes les
// propositions ». POST .../team/agents-config puis `refresh()`. Itération
// /improve en attente de verdict (GET /team `pending`) : sélecteurs
// verrouillés (409 `pending` sinon).
function teamConfigCard(wsId, refresh, team, sub) {
  const card = el('div', 'impr-team');
  card.setAttribute('aria-label', 'Modèle et effort des agents');
  const models = team.model_aliases || Object.keys(IMPR_MODEL_LABELS);
  const efforts = team.effort_levels || Object.keys(IMPR_EFFORT_LABELS);
  const sugg = {};
  for (const s of team.suggestions || []) sugg[s.agent] = s;
  const basis = team.suggestions_basis || {};
  const pend = team.pending || null;
  const locked = !!pend;
  const warnHtml = imprWarningsHtml(sub && sub.warnings);

  const basisPill = basis.measured
    ? `<span class="pill info" title="Propositions = règles par rôle + signal mesuré (agent avec au moins 2 cas et moins de la moitié réussis : effort +1 cran)">Mesure du ${escapeHtml(basis.date || '?')}</span>`
    : '<span class="pill mute" title="Aucune mesure disponible : propositions issues des seules règles par rôle.">Règles seules</span>';
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

  const pendHtml = !pend ? '' : `<div class="impr-team-msg warn">${I.alert}<span>Itération ${escapeHtml(String(pend.iteration))} de <code class="mono">/improve</code> en attente de verdict : trancher d'abord (nouvelle session puis <code class="mono">/improve</code>) avant de changer un modèle ou un effort.</span></div>`;

  card['innerHTML'] = `<div class="impr-team-top">${basisPill}</div>
    <p class="muted impr-note">Modèle et effort de raisonnement de chaque agent, écrits dans <code class="mono">.claude/team.json</code> puis rendus dans l'agent généré. La règle du rôle ne propose un modèle qu'à un agent qui n'en déclare pas, et un effort (jamais au-delà de « élevé ») que s'il est au-dessus de l'actuel ; un agent sans effort est compté comme « moyen ». Jamais de baisse d'effort, jamais de changement d'un modèle déclaré. Rien n'est appliqué sans clic.</p>
    ${warnHtml}
    ${pendHtml}
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
      if (r.status === 409 && r.data.reason === 'pending') toastErr('Une modification à l\'essai attend son verdict : tranche-la d\'abord.');
      else toastErr(r.data.error || `HTTP ${r.status}`);
      if (r.status === 409) refresh();
      return;
    }
    const d = r.data;
    const manual = (d.skipped || []).filter(s => /main/.test(s.reason || '')).length;
    const n = (d.generated || []).length;
    toastOk(d.written
      ? `Équipe enregistrée : ${n} agent${n > 1 ? 's' : ''} régénéré${n > 1 ? 's' : ''}${manual ? `, ${manual} édité${manual > 1 ? 's' : ''} à la main non réécrit${manual > 1 ? 's' : ''}` : ''}`
      : 'Aucun changement');
    refresh();
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
    let applyBtn = null;
    const sync = () => { saveBtn.hidden = selM.value === cur.model && selE.value === cur.effort; if (applyBtn) applyBtn.hidden = !saveBtn.hidden; };
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
