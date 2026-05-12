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
    a['innerHTML'] = `${item.icon}<span>${escapeHtml(item.label)}</span>${item.key ? `<kbd>g ${item.key}</kbd>` : ''}`;
    nav.appendChild(a);
  }
  updateActiveNav();
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
