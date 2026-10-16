/* ================================================================
   Nebula - State global
   ----------------------------------------------------------------
   Etat partage de l'application. Charge AVANT app.js dans index.html
   pour que toutes les fonctions de app.js puissent referencer STATE
   en lecture/ecriture sans import.

   Pourquoi un fichier dedie : extraction structurelle du monolithe
   app.js (~8000 lignes) sans changement de contrat. Les <script>
   classiques partagent leur scope declaratif via le global record,
   donc aucune exposition window.* n'est necessaire entre fichiers
   tant qu'on reste sur du JS classique (pas type="module").

   Ref : CM-2 split app.js, refactor 2026-05-13.
   ================================================================ */
'use strict';

const STATE = {
  workspaces: [],
  mcps: [],
  envKeys: [],
  envFile: null,
  envExists: false,
  templates: [],
  overlays: [],     // overlays Nebula (paquets de fichiers opt-in par-dessus un template)
  plugins: { enabled: {}, count: 0 },
  skills: [],
  skillsLibrary: [],
  stats: {},
  wsMcps: {},      // ws_id -> {active, has_file}
  overlaysActive: {}, // ws_id -> [overlay_id actif] (/api/overview, badge « Auto-amélioration »)
  teamRouting: {},   // ws_id -> mode de routage claude-team (manuel | assiste | auto), /api/overview team_routing
  homePrefetch: null, // { at, stats, sanity: Promise, history: Promise } pose par loadAll pour renderHome
  loadErrors: {},  // ressource -> message d'erreur du dernier loadAll (cf. js/router.js loadErrorsFor)
  activeSessions: {},  // ws_id -> {pid, launched_at, label} - sessions Claude Code lancees depuis Nebula
  sanity: null,
  journalCount: 0,
  filter: { mcp: '' },
  loading: true,
  panelsReloading: false, // loadAll de wsRefreshPanels en cours (ne coupe pas la garde de navigation)
  pagePollers: [],   // setInterval ids actifs sur la page courante (cleared a chaque navigation)
  pageTimeouts: [],  // setTimeout ids en attente sur la page courante
  uiState: null,     // {theme, onboarded} charge depuis /api/ui-state au demarrage
  tour: null,        // Tour guide actif : { name, step, definition }
};

// Enregistre un poller a nettoyer lors du prochain changement de page
function registerPagePoller(intervalId) {
  STATE.pagePollers.push(intervalId);
}

// Enregistre un setTimeout a nettoyer lors du prochain changement de page
function registerPageTimeout(timeoutId) {
  STATE.pageTimeouts.push(timeoutId);
  return timeoutId;
}

function clearPagePollers() {
  for (const id of STATE.pagePollers) clearInterval(id);
  for (const id of STATE.pageTimeouts) clearTimeout(id);
  STATE.pagePollers = [];
  STATE.pageTimeouts = [];
}
