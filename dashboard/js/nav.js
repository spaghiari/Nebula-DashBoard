/* ================================================================
   Nebula - Navigation (sidebar, breadcrumbs, topbar actions)
   ----------------------------------------------------------------
   renderSidebar : injecte les liens de navigation dans .sidebar-nav
   (+ indicateur glissant, compteurs MCPs / Plugins).
   renderRecentWorkspaces : « Workspaces recents » (point d'etat de
   session), mis a jour par le polling des sessions (router.js).
   renderThemeSwitch : selecteur de style en pied de sidebar.
   updateActiveNav : surligne le lien correspondant a la route courante.
   setBreadcrumbs : remplit #breadcrumbs avec les segments fournis.
   setTopbarActions : remplit #topbar-actions avec une liste d'elements
   (docke ensuite dans l'en-tete de page par router.js dockPageActions).

   Charge APRES icons.js (I.*), utils.js (escapeHtml, el, $, $$, wsGem).
   Ref : CM-2 split app.js, refactor 2026-05-13 ; refonte 2026-10.
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
  { id: 'tools',     label: 'Outils',      route: '#/tools',     icon: I.tools,   key: 'o' },
  { id: 'aide',      label: 'Aide',        route: '#/aide',      icon: I.book,    key: 'a' },
];

// Styles proposes en un clic dans la sidebar (les autres restent dans
// Outils > Theme, accessibles par le bouton « ... »).
const QUICK_THEMES = ['nebula', 'sobre', 'doux', 'pop'];

function renderSidebar() {
  const nav = $('#sidebar-nav');
  nav['innerHTML'] = '<span class="nav-ind" aria-hidden="true"></span>';
  for (const item of NAV_ITEMS) {
    if (item.section) {
      // Sections conservees dans le DOM (lecteurs d'ecran) mais masquees
      // visuellement par la refonte (liste plate du prototype).
      nav.appendChild(el('div', 'nav-section', escapeHtml(item.section)));
      continue;
    }
    const a = document.createElement('a');
    a.href = item.route;
    a.className = 'nav-link';
    a.dataset.id = item.id;
    // Nom accessible + infobulle : sous 900px (barre horizontale,
    // css/shell-mobile.css) seul l'icone reste affiche.
    a.setAttribute('aria-label', item.label);
    a.title = item.label;
    // Compteur (MCPs, Plugins) alimente par updateNavCounts() ; badge
    // generique setNavBadge() (lot E item 3) conserve.
    a['innerHTML'] = `${item.icon}<span>${escapeHtml(item.label)}</span>` +
      `<span class="nav-count" data-nav-count hidden></span>` +
      `<span class="nav-badge" data-nav-badge hidden></span>` +
      `${item.key ? `<kbd>g ${item.key}</kbd>` : ''}`;
    nav.appendChild(a);
  }
  renderThemeSwitch();
  updateActiveNav();
}

// Compteurs de la nav (donnees deja chargees par loadAll, aucun appel).
function updateNavCounts() {
  const counts = {
    mcps: (STATE.mcps || []).length,
    plugins: (STATE.plugins && STATE.plugins.count) || Object.keys((STATE.plugins && STATE.plugins.enabled) || {}).length,
  };
  for (const [id, n] of Object.entries(counts)) {
    const c = $(`.nav-link[data-id="${id}"] [data-nav-count]`, $('#sidebar'));
    if (!c) continue;
    c.hidden = !(n > 0);
    c.textContent = n > 999 ? '999+' : String(n);
  }
  placeNavInd();
}

// Met à jour le badge compteur d'une entrée de nav. count <= 0 (ou non-fini)
// -> badge caché. Robuste si la sidebar n'est pas encore rendue (appel précoce
// au boot). Helper générique, prêt à être recâblé sur un futur compteur.
function setNavBadge(itemId, count, label) {
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
  badge.title = label || `${n} en attente`;
  badge.hidden = false;
}

function updateActiveNav() {
  const route = location.hash || '#/';
  for (const link of $$('.nav-link', $('#sidebar'))) {
    const itemId = link.dataset.id;
    // La page workspace n'allume plus « Accueil » : c'est la ligne du
    // workspace dans « Workspaces recents » qui porte l'etat actif.
    const isActive = (itemId === 'home' && route === '#/') ||
                     (itemId !== 'home' && route.startsWith('#/' + itemId));
    link.classList.toggle('active', isActive);
    if (isActive) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current');
  }
  const m = route.match(/^#\/workspace\/([^/]+)/);
  let wsId = null;
  if (m) { try { wsId = decodeURIComponent(m[1]); } catch { wsId = m[1]; } }
  for (const a of $$('.side-ws-item', $('#sidebar'))) {
    const on = a.dataset.ws === wsId;
    a.classList.toggle('active', on);
    if (on) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
  }
  placeNavInd();
}

// Indicateur glissant (transform uniquement) sous le lien actif.
function placeNavInd() {
  const ind = $('#sidebar-nav .nav-ind');
  if (!ind) return;
  const on = $('#sidebar-nav .nav-link.active');
  ind.style.opacity = on ? '1' : '0';
  if (on) ind.style.setProperty('--y', (on.offsetTop + (on.offsetHeight - 22) / 2) + 'px');
}

// Rang d'etat : running < idle < aucun (sessionState vient de router.js,
// resolu a l'appel).
function _wsStateRank(id) {
  const st = (typeof sessionState === 'function') ? sessionState(id) : null;
  return st === 'running' ? 0 : st === 'idle' ? 1 : 2;
}

// Les 6 workspaces les plus pertinents : sessions en cours d'abord, puis
// derniere activite (STATE.stats). Reconstruit en entier (6 liens) : appele
// au chargement et quand une session apparait / change d'etat.
function renderRecentWorkspaces() {
  const host = $('#side-ws');
  const group = $('#side-group');
  if (!host) return;
  const stats = STATE.stats || {};
  const last = (id) => (stats[id] && stats[id].last) || '';
  const list = (STATE.workspaces || []).slice().sort((a, b) =>
    (_wsStateRank(a.id) - _wsStateRank(b.id)) || (last(b.id) > last(a.id) ? 1 : last(b.id) < last(a.id) ? -1 : 0)
  ).slice(0, 6);
  if (group) group.hidden = !list.length;
  host['innerHTML'] = list.map(w => {
    const st = (typeof sessionState === 'function') ? sessionState(w.id) : null;
    const dot = st === 'running'
      ? '<span class="sdot st-run live" title="Session en cours"></span><span class="sr-only">session en cours</span>'
      : st === 'idle' ? '<span class="sdot st-idle" title="Terminal ouvert"></span><span class="sr-only">terminal ouvert</span>' : '';
    return `<a class="side-ws-item" href="#/workspace/${encodeURIComponent(w.id)}" data-ws="${escapeHtml(w.id)}">${wsGem(w)}<span class="n">${escapeHtml(w.label || w.id)}</span>${dot}</a>`;
  }).join('');
  updateActiveNav();
}

// Selecteur de style : 4 styles en un clic + « ... » vers Outils (8 themes).
function renderThemeSwitch() {
  const host = $('#theme-switch');
  if (!host || typeof THEMES === 'undefined') return;
  const cur = getCurrentTheme();
  host['innerHTML'] = QUICK_THEMES.map(id => THEMES.find(t => t.id === id)).filter(Boolean).map(t =>
    `<button class="theme-sw" type="button" data-theme-id="${escapeHtml(t.id)}" aria-pressed="${t.id === cur}" title="Style ${escapeHtml(t.label)}" aria-label="Style ${escapeHtml(t.label)}"><i style="background:linear-gradient(135deg, ${escapeHtml(t.accent)} 50%, ${escapeHtml(t.warm)} 50%)"></i></button>`
  ).join('') + `<button class="theme-sw" type="button" data-theme-more title="Tous les thèmes (Outils)" aria-label="Tous les thèmes">${I.dots}</button>`;
  if (!host.dataset.bound) {
    host.dataset.bound = '1';
    host.addEventListener('click', (e) => {
      const b = e.target.closest('button');
      if (!b) return;
      if (b.hasAttribute('data-theme-more')) { location.hash = '#/tools'; return; }
      applyTheme(b.dataset.themeId);
    });
    // Tout changement de theme (ici, Outils, sync serveur) resynchronise
    // l'etat presse et recale les indicateurs (les polices changent).
    window.addEventListener('nebula-theme', () => {
      const now = getCurrentTheme();
      host.querySelectorAll('[data-theme-id]').forEach(x => x.setAttribute('aria-pressed', String(x.dataset.themeId === now)));
      requestAnimationFrame(() => {
        placeNavInd();
        document.querySelectorAll('.seg').forEach(placeSegThumb);
        if (typeof placeWsTabInd === 'function') placeWsTabInd();
      });
    });
  }
}

window.addEventListener('resize', debounce(() => { placeNavInd(); }, 80));
if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => placeNavInd());

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
   mountHelpLink : greffe ce lien a cote du titre de la page (refonte
   2026-10 : l'eyebrow « 00. ACCUEIL » n'est plus affiche) ; repli sur
   le .page-eyebrow. No-op si deja monte (anti-doublon).
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
  const host = page.querySelector('.page-title') || page.querySelector('.page-eyebrow');
  if (!host || host.querySelector('.help-eyebrow-link')) return;
  host.appendChild(helpLink(topicId, sujet));
}
window.helpLink = helpLink;
window.mountHelpLink = mountHelpLink;
