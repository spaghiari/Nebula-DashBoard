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
