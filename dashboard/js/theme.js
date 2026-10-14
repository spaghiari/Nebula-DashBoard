/* ================================================================
   Nebula - Themes
   ----------------------------------------------------------------
   8 themes (nebula, nebula-clair, marine, solarized, cuivre, + sobre,
   doux, pop issus de la maquette « 3 styles »). Les ids clairs
   (nebula-clair, doux) doivent aussi poser `color-scheme: light` cote CSS.
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
  { id: 'sobre',         label: 'Sobre',         desc: 'Sombre neutre · dense · indigo', accent: '#5e5ce6', warm: '#9296a3', bg: '#0d0e11' },
  { id: 'doux',          label: 'Doux',          desc: 'Clair · arrondi · dégradé',      accent: '#6a5cff', warm: '#3f8cff', bg: '#f3f4fa' },
  { id: 'pop',           label: 'Pop',           desc: 'Sombre bleuté · citron & corail', accent: '#c6ff3d', warm: '#ff6b4a', bg: '#10131f' },
];

function applyTheme(id, { save = true } = {}) {
  const valid = THEMES.find(t => t.id === id) ? id : 'nebula';
  if (valid === 'nebula') document.documentElement.removeAttribute('data-theme');
  else document.documentElement.setAttribute('data-theme', valid);
  try { localStorage.setItem('nebula-theme', valid); } catch {}
  // Selecteur de la sidebar / indicateurs : se resynchronisent (js/nav.js).
  try { window.dispatchEvent(new CustomEvent('nebula-theme', { detail: valid })); } catch {}
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
