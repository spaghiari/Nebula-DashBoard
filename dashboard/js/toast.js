/* ================================================================
   Nebula - Toast / Snackbar
   ----------------------------------------------------------------
   Notifications transitoires. Snackbar = toast avec un bouton d'action
   (ex: UNDO sur suppression).
   Charge APRES utils.js (escapeHtml) et icons.js (I.*).
   Ref : CM-2 split app.js, refactor 2026-05-13.
   ================================================================ */
'use strict';

function toast(msg, type = 'info', duration = 3000) {
  const root = $('#toast-root');
  const node = document.createElement('div');
  node.className = `toast toast-${type === true ? 'error' : type === 'error' ? 'error' : type === 'success' ? 'success' : 'info'}`;
  const icon = type === 'error' || type === true ? I.alert : type === 'success' ? I.success : I.info;
  node['innerHTML'] = `<span class="toast-icon">${icon}</span><div class="toast-content">${escapeHtml(msg)}</div>`;
  root.appendChild(node);
  setTimeout(() => {
    node.classList.add('toast-out');
    setTimeout(() => node.remove(), 200);
  }, duration);
}

const toastErr = (msg) => toast(msg, 'error');
const toastOk = (msg) => toast(msg, 'success');

function snackbar(msg, { actionLabel, onAction, type = 'success', duration = 8000 } = {}) {
  const root = $('#toast-root');
  const node = document.createElement('div');
  node.className = `toast toast-${type} toast-action`;
  const icon = type === 'error' ? I.alert : type === 'success' ? I.success : I.info;
  let timer = null;
  const close = () => {
    if (timer) { clearTimeout(timer); timer = null; }
    node.classList.add('toast-out');
    setTimeout(() => node.remove(), 200);
  };
  node['innerHTML'] = `<span class="toast-icon">${icon}</span><div class="toast-content">${escapeHtml(msg)}</div>`;
  if (actionLabel && typeof onAction === 'function') {
    const btnEl = document.createElement('button');
    btnEl.className = 'toast-action-btn';
    btnEl.type = 'button';
    btnEl.textContent = actionLabel;
    btnEl.addEventListener('click', () => {
      close();
      try { onAction(); } catch (e) { toastErr(e.message); }
    });
    node.appendChild(btnEl);
  }
  root.appendChild(node);
  timer = setTimeout(close, duration);
}
