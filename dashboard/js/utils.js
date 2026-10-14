/* ================================================================
   Nebula - Utils (DOM, format, helpers purs)
   ----------------------------------------------------------------
   Selecteurs DOM, formatage, escape, debounce, factories btn/el.
   Charge AVANT app.js. Aucune dependance.
   Ref : CM-2 split app.js, refactor 2026-05-13.
   ================================================================ */
'use strict';

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

const escapeHtml = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

// Filtre une URL avant de l'injecter dans un href : bloque javascript:, data:, vbscript:
const safeUrl = (u) => {
  const s = String(u ?? '').trim();
  return /^(https?:\/\/|\/|#|mailto:)/i.test(s) ? s : '';
};

const fmtDate = (iso) => {
  if (!iso) return '-';
  try {
    const d = new Date(iso);
    if (isNaN(d)) return iso;
    const now = new Date();
    const diff = (now - d) / 1000;
    if (diff < 60) return 'à l\'instant';
    if (diff < 3600) return Math.round(diff / 60) + ' min';
    if (diff < 86400) return Math.round(diff / 3600) + ' h';
    if (diff < 86400 * 7) return Math.round(diff / 86400) + ' j';
    return d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' });
  } catch { return iso; }
};

const fmtNum = (n) => (n == null) ? '-' : new Intl.NumberFormat('fr-FR').format(n);

const fmtBytes = (b) => {
  if (b == null) return '-';
  if (b < 1024) return b + ' o';
  if (b < 1024 * 1024) return (b / 1024).toFixed(1) + ' Kio';
  return (b / 1024 / 1024).toFixed(1) + ' Mio';
};

const debounce = (fn, ms) => {
  let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
};

// Hash deterministe d'une chaine -> teinte HSL [0,360). Meme nom = meme
// couleur a chaque rendu (pas de Math.random). Sert aux degrades
// "nebuleuse" uniques par workspace (cf. prototype command-center).
function nameHue(s) {
  let h = 7;
  for (const c of String(s ?? '')) h = (h * 33 + c.charCodeAt(0)) % 360;
  return h;
}

// Applique un degrade "nebuleuse" derive du nom sur un element : pose les
// custom properties --g1/--g2 (deux teintes HSL voisines) que le CSS
// consomme pour le halo radial + le gem. C'est la SEULE couleur "en dur"
// autorisee par le brief (generee, pas codee). Retourne la teinte de base
// pour reutilisation (ex. accent d'un sparkline si on en ajoute un).
function wsGradient(el, name) {
  const h = nameHue(name);
  if (el) {
    el.style.setProperty('--g1', `hsl(${h} 82% 64%)`);
    el.style.setProperty('--g2', `hsl(${(h + 48) % 360} 78% 58%)`);
  }
  return h;
}
window.nameHue = nameHue;
window.wsGradient = wsGradient;

// Factory bouton standardise : icone optionnelle (SVG trust) + label escape via escapeHtml.
function btn(label, cls = 'btn', icon = null) {
  const b = document.createElement('button');
  b.type = 'button';
  b.className = 'btn ' + cls;
  if (label) {
    b['innerHTML'] = (icon || '') + `<span>${escapeHtml(label)}</span>`;
  } else {
    b['innerHTML'] = icon || '';
  }
  return b;
}

// Factory element generique avec classe + html optionnel (trust caller).
function el(tag, cls, html) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html != null) e['innerHTML'] = html;
  return e;
}

// withBusy : protege un bouton de submit contre le double-clic pendant un
// appel async. Desactive le bouton, sauvegarde son contenu, affiche un
// label de chargement (« ... »), execute asyncFn, puis restaure et reactive
// dans un finally (meme en cas d'erreur). Re-leve l'erreur eventuelle pour
// que l'appelant la toaste comme avant.
//   await withBusy(okBtn, () => API.post(...));
// Option keepBusyOnSuccess : pour les actions « fire + redirect » (lancer un
// workspace puis re-render via setTimeout(route)), NE PAS reactiver le bouton
// sur succes -- sinon il redevient cliquable entre la fin de l'appel et le
// re-render, et un double-clic relance l'action (cf. double-CMD au lancement).
// Le bouton reste desactive (la page va le remplacer) ; on ne restaure que sur
// erreur.
//   launch.addEventListener('click', () => withBusy(launch, fn, { keepBusyOnSuccess: true }));
// Expose en global (comme btn/el/debounce, declares au top-level). Alias
// window.withBusy pour les call-sites qui prefixent explicitement.
async function withBusy(btn, asyncFn, { keepBusyOnSuccess = false } = {}) {
  if (!btn) return asyncFn();
  const prevDisabled = btn.disabled;
  const prevHtml = btn['innerHTML'];
  const restore = () => {
    btn['innerHTML'] = prevHtml;
    btn.disabled = prevDisabled;
    btn.removeAttribute('aria-busy');
  };
  btn.disabled = true;
  btn.setAttribute('aria-busy', 'true');
  // Conserve la largeur pour eviter un saut de layout pendant le spinner.
  btn['innerHTML'] = '<span class="btn-spinner" aria-hidden="true"></span><span>...</span>';
  try {
    const result = await asyncFn();
    if (!keepBusyOnSuccess) restore();
    return result;
  } catch (e) {
    restore();
    throw e;
  }
}
window.withBusy = withBusy;

// Selecteur des elements focusables (partage par modal.js et les overlays
// maison : wizard premier lancement, tour guide).
const FOCUSABLE_SELECTOR = [
  'a[href]', 'button:not([disabled])', 'input:not([disabled]):not([type=hidden])',
  'select:not([disabled])', 'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

// Liste les elements focusables visibles d'un conteneur. Filtre sur
// getClientRects().length (un element en position:fixed a offsetParent null
// mais reste visible et focusable -- cf. AXE 7d).
function getFocusables(container) {
  return Array.from(container.querySelectorAll(FOCUSABLE_SELECTOR))
    .filter(el => el.getClientRects().length > 0 || el === container);
}

// Pile des pieges clavier actifs : SEUL le piege du dessus reagit aux
// touches. Sans cela, ouvrir une modale B au-dessus d'une modale A laissait
// le piege de A actif : au premier Tab, A detectait un focus « hors de A » et
// le ramenait de force dans A (piege orphelin).
const _trapStack = [];

// Installe un focus trap clavier sur un conteneur : Tab/Shift-Tab cyclent
// entre les focusables, Escape declenche onEscape. Retourne une fonction de
// desinstallation (a appeler a la fermeture de l'overlay).
//   const release = createFocusTrap(modal, { onEscape: close });
//   ... release();
// Exemption : un element portant [data-no-trap] (ex. l'editeur JSON, ou Tab
// sert a indenter) garde sa touche Tab -- le piege ne l'intercepte pas.
// L'element retire l'attribut quand il veut laisser Tab quitter le champ
// (le piege reprend alors la main et cycle correctement dans la modale).
function createFocusTrap(container, { onEscape = null } = {}) {
  const token = {};
  const onKey = (e) => {
    if (_trapStack[_trapStack.length - 1] !== token) return;
    if (e.key === 'Escape') {
      if (onEscape) { e.preventDefault(); onEscape(); }
      return;
    }
    if (e.key !== 'Tab') return;
    if (e.target && e.target.closest && e.target.closest('[data-no-trap]')) return;
    const focusables = getFocusables(container);
    if (!focusables.length) { e.preventDefault(); return; }
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    const active = document.activeElement;
    if (e.shiftKey) {
      if (active === first || !container.contains(active)) {
        e.preventDefault();
        last.focus();
      }
    } else {
      if (active === last || !container.contains(active)) {
        e.preventDefault();
        first.focus();
      }
    }
  };
  _trapStack.push(token);
  document.addEventListener('keydown', onKey, true);
  return () => {
    document.removeEventListener('keydown', onKey, true);
    const i = _trapStack.indexOf(token);
    if (i >= 0) _trapStack.splice(i, 1);
  };
}
window.getFocusables = getFocusables;
window.createFocusTrap = createFocusTrap;
window.FOCUSABLE_SELECTOR = FOCUSABLE_SELECTOR;

// Garde anti-perte de saisie pour les editeurs en modale. Suit un etat
// « dirty » et fournit un confirmClose a passer a openModal : si dirty,
// ouvre une confirmation et bloque la fermeture immediate. Usage :
//   const guard = makeDirtyGuard();
//   ta.addEventListener('input', guard.markDirty);
//   const { close, requestClose } = openModal({ ..., confirmClose: guard.confirmClose });
//   guard.bind(close);                 // fournit le close reel au garde
//   cancel.addEventListener('click', requestClose);
//   // apres sauvegarde reussie : guard.markSaved(); close();
// Editeurs multi-fichiers (sauvegardes successives sans fermer) : passer
// `opts.isDirty` (fonction) -- le garde interroge alors cet etat a chaque
// fermeture au lieu de markDirty/markSaved (qui eux sont definitifs).
function makeDirtyGuard(message = 'Modifications non sauvegardées. Fermer sans enregistrer ?', opts = {}) {
  let dirty = false;
  let saved = false;
  let realClose = () => {};
  let confirming = false;   // une confirmation est deja ouverte (anti double ouverture)
  const probe = (opts && typeof opts.isDirty === 'function') ? opts.isDirty : null;
  const dirtyNow = () => (probe ? !!probe() : (dirty && !saved));
  return {
    markDirty: () => { dirty = true; },
    markSaved: () => { saved = true; },
    bind: (closeFn) => { realClose = closeFn; },
    isDirty: dirtyNow,
    // Renvoie true si la fermeture est autorisee immediatement, false sinon
    // (auquel cas une confirmation est ouverte ; oui -> realClose()).
    confirmClose: () => {
      if (!dirtyNow()) return true;
      if (confirming) return false;
      confirming = true;
      // Annuler referme SEULEMENT la confirmation : l'editeur (empile dessous)
      // est intact, saisie comprise.
      confirmDialog(message, () => realClose(), {
        danger: true,
        confirmLabel: 'Fermer sans enregistrer',
        cancelLabel: "Revenir à l'édition",
        onClose: () => { confirming = false; },
      });
      return false;
    },
  };
}
window.makeDirtyGuard = makeDirtyGuard;

/* ================================================================
   Refonte 2026-10 (prototype nebula-redesign) : helpers d'affichage
   partages par l'accueil, la page workspace, les MCPs et la palette.
   ================================================================ */

// Gem d'un workspace : emoji sur une teinte derivee du nom (--h), sans
// couleur codee en dur (saturation / luminosite / alpha = tokens --gem-*).
function wsGem(w, cls = '') {
  const name = (w && (w.label || w.id)) || '';
  return `<span class="gem ${cls}" style="--h:${nameHue(name)}" aria-hidden="true">${escapeHtml((w && w.emoji) || '📁')}</span>`;
}

// 1250000 -> « 1,3 M » ; 1,25e9 -> « 1,25 Md ».
function fmtCompact(n) {
  n = Number(n) || 0;
  const f = (v, d) => v.toLocaleString('fr-FR', { maximumFractionDigits: d });
  if (n >= 1e9) return f(n / 1e9, 2) + ' Md';
  if (n >= 1e6) return f(n / 1e6, 1) + ' M';
  if (n >= 1e3) return f(n / 1e3, 1) + ' k';
  return String(n);
}

// « il y a 3 j », « hier », « jamais ».
function fmtAgo(iso) {
  if (!iso) return 'jamais';
  const t = Date.parse(iso);
  if (isNaN(t)) return String(iso);
  const m = Math.round((Date.now() - t) / 60000);
  if (m < 2) return "à l'instant";
  if (m < 60) return `il y a ${m} min`;
  const h = Math.round(m / 60);
  if (h < 24) return `il y a ${h} h`;
  const d = Math.round(h / 24);
  return d === 1 ? 'hier' : `il y a ${d} j`;
}

// « 14 oct., 00:48 »
function fmtDateTime(iso) {
  if (!iso) return 'jamais';
  const d = new Date(iso);
  if (isNaN(d)) return String(iso);
  return d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' }) + ', '
    + d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
}

// Duree ecoulee « 1 h 12 min 23 s » (chronometres « depuis »).
function fmtElapsed(ms) {
  const s = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(s / 3600);
  const m = Math.floor(s / 60) % 60;
  return (h ? h + ' h ' : '') + String(m).padStart(2, '0') + ' min ' + String(s % 60).padStart(2, '0') + ' s';
}

// Les animations decoratives (compteurs) ne tournent que si l'utilisateur
// n'a pas demande de mouvement reduit.
function motionOK() {
  try { return !matchMedia('(prefers-reduced-motion: reduce)').matches; } catch { return true; }
}

// Compteurs animes : uniquement les entiers marques data-count (texte seul,
// pas de reflow de mise en page : largeur tabulaire).
function countUp(root) {
  for (const node of (root || document).querySelectorAll('[data-count]')) {
    const to = Number(node.dataset.count) || 0;
    if (!motionOK() || to < 2) { node.textContent = fmtNum(to); continue; }
    const t0 = performance.now();
    const step = (t) => {
      const p = Math.min(1, (t - t0) / 900);
      node.textContent = fmtNum(Math.round(to * (1 - Math.pow(1 - p, 4))));
      if (p < 1 && node.isConnected) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }
}

// Segmented control : boutons aria-pressed + pouce glissant (transform/width).
function placeSegThumb(seg) {
  if (!seg) return;
  const on = seg.querySelector('button[aria-pressed="true"]');
  const th = seg.querySelector('.thumb');
  if (!on || !th) return;
  th.style.width = on.offsetWidth + 'px';
  th.style.transform = `translateX(${on.offsetLeft - 3}px)`;
}
function bindSeg(seg, onChange) {
  if (!seg) return;
  requestAnimationFrame(() => placeSegThumb(seg));
  seg.addEventListener('click', (e) => {
    const b = e.target.closest('button[data-v]');
    if (!b || b.getAttribute('aria-pressed') === 'true') return;
    seg.querySelectorAll('button[data-v]').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
    placeSegThumb(seg);
    onChange(b.dataset.v);
  });
}
// Les pouces se recalent apres un changement de police / taille de fenetre.
window.addEventListener('resize', debounce(() => document.querySelectorAll('.seg').forEach(placeSegThumb), 80));
if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => document.querySelectorAll('.seg').forEach(placeSegThumb));

// Overlay « Auto-amelioration de Claude » actif sur un workspace (donnee
// /api/overview overlays_active, aucune requete par workspace).
const SELF_IMPROVING_ID = 'claude-self-improving';
function wsHasOverlay(wsId, ovId = SELF_IMPROVING_ID) {
  const m = (typeof STATE !== 'undefined' && STATE.overlaysActive) || {};
  return (m[wsId] || []).includes(ovId);
}
function selfImprovingMark(wsId) {
  return wsHasOverlay(wsId)
    ? '<span class="si" title="Auto-amélioration de Claude active" role="img" aria-label="Auto-amélioration active">' + (typeof I !== 'undefined' && I.selfImprove ? I.selfImprove : '') + '</span>'
    : '';
}

/* ================================================================
   Hovercard : liste au survol, delimitee et aux couleurs du theme
   ----------------------------------------------------------------
   Remplace les `title` natifs (petit cadre clair du systeme, non
   themable, noms colles a la suite). Declencheur = n'importe quel
   element portant hcAttrs(groups) ; une seule carte partagee
   (#hovercard), delegation sur document.
     groups : [{ title, ws: [ids] }  -> pastille + libelle + id, lien
               { title, items: [txt] } -> liste simple]
   Ergonomie : ouverture 200 ms au survol (pas de clignotement en
   traversant une grille), immediate au focus clavier ; fermeture
   150 ms (le pointeur peut entrer dans la carte, liens cliquables) ;
   Echap / defilement / navigation ferment ; appui tactile = bascule ;
   au-dessous du declencheur, retournee au-dessus si la place manque.
   ================================================================ */
function hcAttrs(groups) {
  const g = (groups || []).filter(x => (x.ws && x.ws.length) || (x.items && x.items.length));
  return g.length ? ` data-hc="${escapeHtml(JSON.stringify(g))}" tabindex="0"` : '';
}

const HC = { el: null, trigger: null, openT: 0, closeT: 0 };

function _hcEl() {
  if (HC.el) return HC.el;
  const d = document.createElement('div');
  d.id = 'hovercard';
  d.className = 'hovercard';
  d.setAttribute('role', 'tooltip');
  d.hidden = true;
  d.addEventListener('pointerenter', () => clearTimeout(HC.closeT));
  d.addEventListener('pointerleave', () => _hcScheduleClose());
  d.addEventListener('click', () => hcClose());
  document.body.appendChild(d);
  return (HC.el = d);
}

function _hcRender(groups) {
  const byId = new Map(((typeof STATE !== 'undefined' && STATE.workspaces) || []).map(w => [w.id, w]));
  return groups.map(g => {
    const rows = g.ws
      ? g.ws.map(id => {
        const w = byId.get(id);
        return w
          ? `<a class="hc-row" href="#/workspace/${encodeURIComponent(id)}" tabindex="-1">${wsGem(w)}<span class="hc-name">${escapeHtml(w.label || id)}</span><span class="hc-id">${escapeHtml(id)}</span></a>`
          : `<span class="hc-row"><span class="hc-ext" aria-hidden="true"></span><span class="hc-name">${escapeHtml(id)}</span></span>`;
      })
      : g.items.map(t => `<span class="hc-row"><span class="hc-ext" aria-hidden="true"></span><span class="hc-name">${escapeHtml(t)}</span></span>`);
    const n = (g.ws || g.items).length;
    return `<div class="hc-group"><div class="hc-title">${escapeHtml(g.title)} <b>${n}</b></div>${rows.join('')}</div>`;
  }).join('');
}

function _hcPlace(trigger) {
  const card = HC.el;
  const r = trigger.getBoundingClientRect();
  const gap = 6, m = 8;
  const w = card.offsetWidth, h = card.offsetHeight;
  const below = window.innerHeight - r.bottom - gap - m;
  const top = (below >= h || below >= r.top) ? r.bottom + gap : r.top - gap - h;
  const left = Math.max(m, Math.min(r.left, window.innerWidth - w - m));
  card.style.top = `${Math.max(m, top)}px`;
  card.style.left = `${left}px`;
}

function hcOpen(trigger) {
  let groups;
  try { groups = JSON.parse(trigger.dataset.hc || '[]'); } catch { return; }
  if (!groups.length) return;
  const card = _hcEl();
  clearTimeout(HC.closeT);
  card.innerHTML = _hcRender(groups);
  card.hidden = false;
  card.classList.remove('on');
  _hcPlace(trigger);
  requestAnimationFrame(() => card.classList.add('on'));
  if (HC.trigger && HC.trigger !== trigger) HC.trigger.removeAttribute('aria-describedby');
  HC.trigger = trigger;
  trigger.setAttribute('aria-describedby', 'hovercard');
}

function hcClose() {
  clearTimeout(HC.openT);
  clearTimeout(HC.closeT);
  if (HC.trigger) HC.trigger.removeAttribute('aria-describedby');
  HC.trigger = null;
  if (HC.el) { HC.el.classList.remove('on'); HC.el.hidden = true; }
}

function _hcScheduleClose() {
  clearTimeout(HC.openT);
  clearTimeout(HC.closeT);
  HC.closeT = setTimeout(hcClose, 150);
}

document.addEventListener('pointerover', (e) => {
  if (e.pointerType === 'touch') return;
  const t = e.target.closest && e.target.closest('[data-hc]');
  if (!t) return;
  clearTimeout(HC.closeT);
  if (HC.trigger === t) return;
  clearTimeout(HC.openT);
  // Une carte est deja ouverte : on passe d'un declencheur a l'autre sans attendre.
  HC.openT = setTimeout(() => hcOpen(t), HC.trigger ? 0 : 200);
});
document.addEventListener('pointerout', (e) => {
  if (e.pointerType === 'touch') return;
  const t = e.target.closest && e.target.closest('[data-hc]');
  if (!t || (e.relatedTarget && t.contains(e.relatedTarget))) return;
  _hcScheduleClose();
});
document.addEventListener('pointerdown', (e) => {
  const t = e.target.closest && e.target.closest('[data-hc]');
  if (e.pointerType === 'touch' && t) {
    if (HC.trigger === t) hcClose(); else hcOpen(t);
    return;
  }
  if (HC.trigger && !(HC.el && HC.el.contains(e.target)) && t !== HC.trigger) hcClose();
});
document.addEventListener('focusin', (e) => {
  const t = e.target.closest && e.target.closest('[data-hc]');
  if (t) hcOpen(t);
});
document.addEventListener('focusout', (e) => {
  if (HC.trigger && e.target === HC.trigger) _hcScheduleClose();
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && HC.trigger) hcClose();
}, true);
window.addEventListener('scroll', () => { if (HC.trigger) hcClose(); }, true);
window.addEventListener('hashchange', hcClose);
