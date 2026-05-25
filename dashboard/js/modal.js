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

   Charge APRES utils.js (escapeHtml, btn) et icons.js (I.x).
   Ref : CM-2 split app.js, refactor 2026-05-13.
   ================================================================ */
'use strict';

// Selecteur + focus trap partages : voir js/utils.js (FOCUSABLE_SELECTOR,
// getFocusables, createFocusTrap). Reutilises ici et par les overlays
// maison (wizard, tour).
let _modalIdCounter = 0;

function openModal({ title, body, footer = null, wide = false, onClose = null, closeOnBackdrop = false, confirmClose = null }) {
  const root = $('#modal-root');
  root['innerHTML'] = '';
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
  root.appendChild(overlay);

  // Sauvegarde du focus precedent pour restauration a la fermeture
  const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null;

  const close = () => {
    root['innerHTML'] = '';
    releaseTrap();
    if (onClose) onClose();
    if (previouslyFocused && document.body.contains(previouslyFocused)) {
      try { previouslyFocused.focus(); } catch { /* noop */ }
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
  modal.querySelector('[data-close]').addEventListener('click', requestClose);
  // Fermeture sur clic du voile : OFF par defaut pour eviter la perte de saisie.
  if (closeOnBackdrop) {
    overlay.addEventListener('click', (e) => { if (e.target === overlay) requestClose(); });
  }

  // Autofocus : premier element focusable du body (input/textarea/select
  // de preference), sinon le modal lui-meme
  setTimeout(() => {
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

function confirmDialog(message, onYes, { danger = false } = {}) {
  const body = document.createElement('div');
  body['innerHTML'] = `<p style="margin:0;color:var(--text-muted)">${escapeHtml(message)}</p>`;
  const cancel = btn('Annuler', 'btn-ghost');
  const ok = btn(danger ? 'Supprimer' : 'Confirmer', danger ? 'btn-danger' : 'btn-primary');
  const { close } = openModal({ title: 'Confirmation', body, footer: [cancel, ok] });
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
