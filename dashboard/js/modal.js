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

const _FOCUSABLE_SELECTOR = [
  'a[href]', 'button:not([disabled])', 'input:not([disabled]):not([type=hidden])',
  'select:not([disabled])', 'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

let _modalIdCounter = 0;

function openModal({ title, body, footer = null, wide = false, onClose = null, closeOnBackdrop = false }) {
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
    document.removeEventListener('keydown', onKey, true);
    if (onClose) onClose();
    if (previouslyFocused && document.body.contains(previouslyFocused)) {
      try { previouslyFocused.focus(); } catch { /* noop */ }
    }
  };

  const getFocusables = () => Array.from(modal.querySelectorAll(_FOCUSABLE_SELECTOR))
    .filter(el => el.offsetParent !== null || el === modal);

  const onKey = (e) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      close();
      return;
    }
    if (e.key === 'Tab') {
      const focusables = getFocusables();
      if (!focusables.length) { e.preventDefault(); return; }
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const active = document.activeElement;
      if (e.shiftKey) {
        if (active === first || !modal.contains(active)) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (active === last || !modal.contains(active)) {
          e.preventDefault();
          first.focus();
        }
      }
    }
  };
  document.addEventListener('keydown', onKey, true);
  modal.querySelector('[data-close]').addEventListener('click', close);
  // Fermeture sur clic du voile : OFF par defaut pour eviter la perte de saisie.
  if (closeOnBackdrop) {
    overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
  }

  // Autofocus : premier element focusable du body (input/textarea/select
  // de preference), sinon le modal lui-meme
  setTimeout(() => {
    const focusables = Array.from(modal.querySelector('.modal-body').querySelectorAll(_FOCUSABLE_SELECTOR));
    const preferred = focusables.find(el => /^(INPUT|TEXTAREA|SELECT)$/i.test(el.tagName));
    const target = preferred || focusables[0] || modal;
    try { target.focus(); } catch { /* noop */ }
  }, 30);

  return { modal, close };
}

function confirmDialog(message, onYes, { danger = false } = {}) {
  const body = document.createElement('div');
  body['innerHTML'] = `<p style="margin:0;color:var(--text-muted)">${escapeHtml(message)}</p>`;
  const cancel = btn('Annuler', 'btn-ghost');
  const ok = btn(danger ? 'Supprimer' : 'Confirmer', danger ? 'btn-danger' : 'btn-primary');
  const { close } = openModal({ title: 'Confirmation', body, footer: [cancel, ok] });
  cancel.addEventListener('click', close);
  ok.addEventListener('click', () => { close(); onYes(); });
}
