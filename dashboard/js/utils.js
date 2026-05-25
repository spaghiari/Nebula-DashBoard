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

// Installe un focus trap clavier sur un conteneur : Tab/Shift-Tab cyclent
// entre les focusables, Escape declenche onEscape. Retourne une fonction de
// desinstallation (a appeler a la fermeture de l'overlay).
//   const release = createFocusTrap(modal, { onEscape: close });
//   ... release();
function createFocusTrap(container, { onEscape = null } = {}) {
  const onKey = (e) => {
    if (e.key === 'Escape') {
      if (onEscape) { e.preventDefault(); onEscape(); }
      return;
    }
    if (e.key !== 'Tab') return;
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
  document.addEventListener('keydown', onKey, true);
  return () => document.removeEventListener('keydown', onKey, true);
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
function makeDirtyGuard(message = 'Modifications non sauvegardées. Fermer sans enregistrer ?') {
  let dirty = false;
  let saved = false;
  let realClose = () => {};
  return {
    markDirty: () => { dirty = true; },
    markSaved: () => { saved = true; },
    bind: (closeFn) => { realClose = closeFn; },
    isDirty: () => dirty && !saved,
    // Renvoie true si la fermeture est autorisee immediatement, false sinon
    // (auquel cas une confirmation est ouverte ; oui -> realClose()).
    confirmClose: () => {
      if (!dirty || saved) return true;
      confirmDialog(message, () => realClose(), { danger: true });
      return false;
    },
  };
}
window.makeDirtyGuard = makeDirtyGuard;
