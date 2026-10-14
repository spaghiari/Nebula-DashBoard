/* ================================================================
   Nebula - Modal + confirmDialog
   ----------------------------------------------------------------
   openModal : modal a11y avec focus trap (Tab/Shift-Tab cycle),
   autofocus 1er input/textarea/select du body, restauration focus a la fermeture.
   confirmDialog : sucre par-dessus openModal pour confirmations Oui/Non.

   Contrat a11y (CM-3 starter) :
   - role=dialog + aria-modal=true + aria-labelledby sur le <h2>
   - autofocus sur le premier element focusable du body a l'ouverture
   - focus trap : Tab/Shift-Tab cycle entre les elements focusables du
     modal, ne sort jamais (Escape pour fermer)
   - restauration du focus sur l'element qui avait le focus avant l'ouverture

   Pile de modales : ouvrir une modale depuis une autre ne detruit pas la
   premiere. Elle devient inerte (attribut inert + aria-hidden) tant qu'une
   modale la recouvre, puis redevient interactive, saisie intacte, quand la
   modale du dessus se ferme. Le piege clavier est empile de la meme facon
   (cf. createFocusTrap dans utils.js).

   Charge APRES utils.js (escapeHtml, btn) et icons.js (I.x).
   Ref : CM-2 split app.js, refactor 2026-05-13.
   ================================================================ */
'use strict';

// Selecteur + focus trap partages : voir js/utils.js (FOCUSABLE_SELECTOR,
// getFocusables, createFocusTrap). Reutilises ici et par les overlays
// maison (wizard, tour).
let _modalIdCounter = 0;

// Pile des modales ouvertes (la derniere = celle du dessus).
const _modalStack = [];

function _refreshModalStack() {
  _modalStack.forEach((entry, i) => {
    const isTop = i === _modalStack.length - 1;
    entry.overlay.inert = !isTop;
    if (isTop) entry.overlay.removeAttribute('aria-hidden');
    else entry.overlay.setAttribute('aria-hidden', 'true');
  });
}

// Inscrit un overlay maison (wizard de premier lancement) dans la pile :
// les modales deja ouvertes deviennent inertes au lieu d'etre detruites, et
// une modale ouverte par-dessus le rend inerte a son tour. Retourne la
// fonction de retrait (idempotente), a appeler a la fermeture.
function pushModalLayer(overlay, modal) {
  const entry = { overlay, modal, prev: null };
  _modalStack.push(entry);
  _refreshModalStack();
  return () => {
    const idx = _modalStack.indexOf(entry);
    if (idx < 0) return;
    _modalStack.splice(idx, 1);
    _refreshModalStack();
  };
}

function openModal({ title, body, footer = null, wide = false, onClose = null, closeOnBackdrop = false, confirmClose = null }) {
  const root = $('#modal-root');
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  const modal = document.createElement('div');
  modal.className = 'modal' + (wide ? ' modal-wide' : '');
  modal.setAttribute('role', 'dialog');
  modal.setAttribute('aria-modal', 'true');
  const titleId = `modal-title-${++_modalIdCounter}`;
  modal.setAttribute('aria-labelledby', titleId);
  modal.tabIndex = -1;
  modal['innerHTML'] = `
    <div class="modal-header">
      <h2 class="modal-title" id="${titleId}">${escapeHtml(title)}</h2>
      <button class="icon-btn" data-close aria-label="Fermer">${I.x}</button>
    </div>
    <div class="modal-body"></div>
    ${footer ? `<div class="modal-footer"></div>` : ''}
  `;
  modal.querySelector('.modal-body').append(...(Array.isArray(body) ? body : [body]));
  if (footer) modal.querySelector('.modal-footer').append(...(Array.isArray(footer) ? footer : [footer]));
  overlay.appendChild(modal);

  // Sauvegarde du focus precedent pour restauration a la fermeture. A lire
  // AVANT d'ajouter l'overlay et avant que _refreshModalStack rende la
  // modale du dessous inerte (ce qui lui ferait perdre le focus).
  const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  root.appendChild(overlay);

  const entry = { overlay, modal, prev: previouslyFocused };
  let closed = false;

  const close = () => {
    if (closed) return;   // idempotent : close() peut etre appele deux fois (callbacks async)
    closed = true;
    const idx = _modalStack.indexOf(entry);
    const wasTop = idx === _modalStack.length - 1;
    // Une modale situee au-dessus herite du focus a restaurer si celui-ci
    // pointait dans celle qu'on ferme (sinon le focus se perdrait sur <body>).
    for (let i = idx + 1; i < _modalStack.length; i++) {
      const above = _modalStack[i];
      if (above.prev && modal.contains(above.prev)) above.prev = entry.prev;
    }
    if (idx >= 0) _modalStack.splice(idx, 1);
    overlay.remove();
    releaseTrap();
    _refreshModalStack();
    if (onClose) onClose();
    if (!wasTop) return;
    // Restauration du focus : element qui avait le focus avant l'ouverture,
    // sinon la modale du dessous (jamais <body>).
    const target = entry.prev && document.body.contains(entry.prev) ? entry.prev : null;
    const below = _modalStack[_modalStack.length - 1];
    if (target && !target.closest('[inert]')) {
      try { target.focus(); } catch { /* noop */ }
    } else if (below) {
      try { below.modal.focus(); } catch { /* noop */ }
    }
  };

  // Fermeture protegee : si confirmClose est fourni et renvoie false, on
  // bloque (ex. modifications non sauvegardees). Utilisee par les
  // declencheurs « softs » : croix, Escape, clic sur le voile.
  const requestClose = () => {
    if (confirmClose && confirmClose() === false) return;
    close();
  };

  const releaseTrap = createFocusTrap(modal, { onEscape: requestClose });
  _modalStack.push(entry);
  _refreshModalStack();
  modal.querySelector('[data-close]').addEventListener('click', requestClose);
  // Fermeture sur clic du voile : OFF par defaut pour eviter la perte de saisie.
  if (closeOnBackdrop) {
    overlay.addEventListener('click', (e) => { if (e.target === overlay) requestClose(); });
  }

  // Autofocus : premier element focusable du body (input/textarea/select
  // de preference), sinon le modal lui-meme
  setTimeout(() => {
    if (closed) return;
    const focusables = Array.from(modal.querySelector('.modal-body').querySelectorAll(FOCUSABLE_SELECTOR));
    const preferred = focusables.find(el => /^(INPUT|TEXTAREA|SELECT)$/i.test(el.tagName));
    const target = preferred || focusables[0] || modal;
    try { target.focus(); } catch { /* noop */ }
  }, 30);

  // close() ferme sans condition (a utiliser apres une sauvegarde reussie) ;
  // requestClose() consulte confirmClose (a brancher sur le bouton Annuler
  // des editeurs avec garde anti-perte de saisie).
  return { modal, close, requestClose };
}

// confirmDialog(message, onYes, opts)
//   danger       : style destructif (bouton rouge, libelle par defaut « Supprimer »)
//   confirmLabel : libelle du bouton de confirmation (« Arrêter », « Détacher »...)
//   cancelLabel  : libelle du bouton d'annulation (defaut « Annuler »)
//   onClose      : rappel a la fermeture de la confirmation (quelle qu'en soit la cause)
// Le message accepte les sauts de ligne (\n) : affichage en white-space: pre-line.
function confirmDialog(message, onYes, { danger = false, confirmLabel = null, cancelLabel = 'Annuler', onClose = null } = {}) {
  const body = document.createElement('div');
  body['innerHTML'] = `<p class="confirm-text" style="margin:0;color:var(--text-muted);white-space:pre-line">${escapeHtml(message)}</p>`;
  const cancel = btn(cancelLabel, 'btn-ghost');
  const ok = btn(confirmLabel || (danger ? 'Supprimer' : 'Confirmer'), danger ? 'btn-danger' : 'btn-primary');
  const { close } = openModal({ title: 'Confirmation', body, footer: [cancel, ok], onClose });
  cancel.addEventListener('click', close);
  // La modale reste ouverte pendant l'execution de onYes (qui peut etre
  // async). On desactive OK + spinner via withBusy, on ferme au succes et on
  // reactive en cas d'erreur (deja toastee en amont par les onYes existants).
  // wrapper en Promise.resolve pour rester compatible avec les onYes sync.
  ok.addEventListener('click', async () => {
    cancel.disabled = true;
    try {
      await withBusy(ok, () => Promise.resolve(onYes()));
      close();
    } catch {
      // Erreur : on garde la modale ouverte, withBusy a deja restaure le
      // bouton OK. On reactive Annuler pour permettre de sortir.
      cancel.disabled = false;
    }
  });
}
