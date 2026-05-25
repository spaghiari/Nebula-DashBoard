/* ================================================================
   Nebula - Navigation (sidebar, breadcrumbs, topbar actions)
   ----------------------------------------------------------------
   renderSidebar : injecte les liens de navigation dans .sidebar-nav.
   updateActiveNav : surligne le lien correspondant a la route courante.
   setBreadcrumbs : remplit #breadcrumbs avec les segments fournis.
   setTopbarActions : remplit #topbar-actions avec une liste d'elements.

   Charge APRES icons.js (I.*), utils.js (escapeHtml, el, $, $$).
   Ref : CM-2 split app.js, refactor 2026-05-13.
   ================================================================ */
'use strict';

const NAV_ITEMS = [
  { section: 'Espace de travail' },
  { id: 'home',      label: 'Accueil',     route: '#/',          icon: I.home,    key: 'h' },
  { id: 'mcps',      label: 'MCPs',        route: '#/mcps',      icon: I.box,     key: 'm' },
  { id: 'plugins',   label: 'Plugins',     route: '#/plugins',   icon: I.plug,    key: 'p' },
  { id: 'skills',    label: 'Skills',      route: '#/skills',    icon: I.sparkle, key: 'k' },
  { id: 'templates', label: 'Templates',   route: '#/templates', icon: I.layers,  key: 't' },
  { section: 'Système' },
  { id: 'reflexive', label: 'Reflexive',   route: '#/reflexive', icon: I.brain,   key: 'r' },
  { id: 'tools',     label: 'Outils',      route: '#/tools',     icon: I.tools,   key: 'o' },
  { id: 'aide',      label: 'Aide',        route: '#/aide',      icon: I.book,    key: 'a' },
];

function renderSidebar() {
  const nav = $('#sidebar-nav');
  nav['innerHTML'] = '';
  for (const item of NAV_ITEMS) {
    if (item.section) {
      nav.appendChild(el('div', 'nav-section', escapeHtml(item.section)));
      continue;
    }
    const a = document.createElement('a');
    a.href = item.route;
    a.className = 'nav-link';
    a.dataset.id = item.id;
    // Slot de badge compteur (lot E item 3) : caché par défaut, alimenté par
    // setNavBadge(). Placé avant le <kbd> pour rester lisible.
    a['innerHTML'] = `${item.icon}<span>${escapeHtml(item.label)}</span>` +
      `<span class="nav-badge" data-nav-badge hidden></span>` +
      `${item.key ? `<kbd>g ${item.key}</kbd>` : ''}`;
    nav.appendChild(a);
  }
  updateActiveNav();
}

// Met à jour le badge compteur d'une entrée de nav (lot E item 3).
// count <= 0 (ou non-fini) -> badge caché. Robuste si la sidebar n'est pas
// encore rendue (appel précoce au boot).
function setNavBadge(itemId, count) {
  const link = $(`.nav-link[data-id="${itemId}"]`, $('#sidebar'));
  if (!link) return;
  const badge = link.querySelector('[data-nav-badge]');
  if (!badge) return;
  const n = Number(count);
  if (!Number.isFinite(n) || n <= 0) {
    badge.hidden = true;
    badge.textContent = '';
    return;
  }
  badge.textContent = n > 99 ? '99+' : String(n);
  badge.title = `${n} proposition(s) Reflexive en attente`;
  badge.hidden = false;
}

// Rafraîchit le badge « propositions en attente » de l'entrée Reflexive.
// Source : GET /api/reflexive/stats (proposals_pending). Appelé au boot,
// après une action sur une proposition, et au rendu de l'overview Reflexive.
// Silencieux : un blip réseau ne doit pas casser la nav.
async function refreshReflexiveBadge() {
  try {
    const stats = await API.get('/api/reflexive/stats?days=30');
    setNavBadge('reflexive', stats && stats.proposals_pending);
  } catch { /* silencieux */ }
}

function updateActiveNav() {
  const route = location.hash || '#/';
  for (const link of $$('.nav-link', $('#sidebar'))) {
    const itemId = link.dataset.id;
    const isActive = (itemId === 'home' && route === '#/') ||
                     (itemId !== 'home' && route.startsWith('#/' + itemId)) ||
                     (itemId === 'home' && route.startsWith('#/workspace/'));
    link.classList.toggle('active', isActive);
  }
}

function setBreadcrumbs(items) {
  const bc = $('#breadcrumbs');
  bc['innerHTML'] = items.map((it, i) => {
    const last = i === items.length - 1;
    const sep = i > 0 ? `<span class="breadcrumb-sep">/</span>` : '';
    const cls = 'breadcrumb-item' + (last ? ' current' : '');
    if (it.href && !last) {
      return `${sep}<a href="${it.href}" class="${cls}">${escapeHtml(it.label)}</a>`;
    }
    return `${sep}<span class="${cls}">${escapeHtml(it.label)}</span>`;
  }).join('');
}

function setTopbarActions(actions = []) {
  const c = $('#topbar-actions');
  c['innerHTML'] = '';
  for (const a of actions) c.appendChild(a);
}

/* ================================================================
   AIDE CONTEXTUELLE (lot F item 1)
   ----------------------------------------------------------------
   helpLink : petit lien « ? » discret qui pointe vers un topic d'aide
   ciblé (#/aide/<topicId>). topicId DOIT être un id de HELP_TOPICS
   (cf. js/pages/help.js), pas un id de section. Mapping page -> topic
   géré côté appelant.
   mountHelpLink : greffe ce lien dans le .page-eyebrow d'une page déjà
   construite (même point d'ancrage que la live-dot des MCPs). No-op si
   l'eyebrow est absent ou si un lien d'aide y est déjà monté (anti-doublon).
   ================================================================ */
function helpLink(topicId, sujet) {
  const a = document.createElement('a');
  a.href = `#/aide/${topicId}`;
  a.className = 'help-eyebrow-link';
  a.setAttribute('aria-label', `Aide : ${sujet}`);
  a.title = `Aide : ${sujet}`;
  a['innerHTML'] = I.info;
  return a;
}

function mountHelpLink(page, topicId, sujet) {
  if (!page) return;
  const eyebrow = page.querySelector('.page-eyebrow');
  if (!eyebrow || eyebrow.querySelector('.help-eyebrow-link')) return;
  eyebrow.appendChild(helpLink(topicId, sujet));
}
window.helpLink = helpLink;
window.mountHelpLink = mountHelpLink;
