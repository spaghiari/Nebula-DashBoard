/* ================================================================
   Nebula - Themes
   ----------------------------------------------------------------
   5 themes (nebula, nebula-clair, marine, solarized, cuivre).
   Persiste en localStorage pour eviter le flash au chargement,
   puis sync serveur via /api/ui-state.
   Charge APRES api.js (applyTheme appelle API.post sur save=true).
   Ref : CM-2 split app.js, refactor 2026-05-13.
   ================================================================ */
'use strict';

const THEMES = [
  { id: 'nebula',        label: 'Nebula',        desc: 'Sombre · violet & ocre',        accent: '#a78bfa', warm: '#f4a672', bg: '#0a0a0f' },
  { id: 'nebula-clair',  label: 'Nebula clair',  desc: 'Clair · violet',                accent: '#7c3aed', warm: '#c2410c', bg: '#f8f7fb' },
  { id: 'marine',         label: 'Marine',         desc: 'Sombre · bleu profond',         accent: '#60a5fa', warm: '#fbbf24', bg: '#08101c' },
  { id: 'solarized',     label: 'Solarized',     desc: 'Sombre · cyan & ambre',         accent: '#2aa198', warm: '#b58900', bg: '#002b36' },
  { id: 'cuivre',        label: 'Cuivre',        desc: 'Sombre · bronze chaleureux',    accent: '#d97706', warm: '#fde68a', bg: '#1a0e05' },
];

function applyTheme(id, { save = true } = {}) {
  const valid = THEMES.find(t => t.id === id) ? id : 'nebula';
  if (valid === 'nebula') document.documentElement.removeAttribute('data-theme');
  else document.documentElement.setAttribute('data-theme', valid);
  try { localStorage.setItem('nebula-theme', valid); } catch {}
  if (save) API.post('/api/ui-state', { theme: valid }).catch(e => console.warn('[ui-state] sync thème échoué :', e.message));
}

function getCurrentTheme() {
  try {
    const stored = localStorage.getItem('nebula-theme');
    if (stored && THEMES.find(t => t.id === stored)) return stored;
  } catch {}
  return 'nebula';
}

// Appliquer immédiatement au chargement depuis le cache local (évite le flash)
applyTheme(getCurrentTheme(), { save: false });
