/* ================================================================
   Nebula - Helpers de validation préventive (lint client)
   ----------------------------------------------------------------
   Garde-fous front réutilisables qui empêchent la saisie invalide
   « qui casse en silence » (Lot B de l'audit UX 2026-05-25) :
     - extractVars / lintInterpolation : interpolation ${VAR} dans
       les configs MCP (char parasite, var absente de .env.local) ;
     - lintPermissionLine : format des règles de permission Claude
       Code (mcp__server__tool ou outil natif).

   Script-scope partagé : chargé avant les pages dans index.html.
   Dépendances script-scope : STATE (envKeys).
   ================================================================ */
'use strict';

/* ----------------------------------------------------------------
   Interpolation ${VAR}
   ---------------------------------------------------------------- */

// Extrait tous les noms de variables ${VAR} d'une chaîne.
// Convention projet : VAR en MAJUSCULES, chiffres et underscore
// (cf. ENV_VAR_PATTERN backend + lint mcps.js existant).
function extractVars(str) {
  const out = [];
  const re = /\$\{([A-Z0-9_]+)\}/g;
  let m;
  while ((m = re.exec(String(str || ''))) !== null) out.push(m[1]);
  return out;
}

// Détecte un caractère alphanumérique collé juste après le `}` d'un
// ${VAR} : ${TOKEN}Q = typo probable (le bug réel wikijs). On NE
// flagge PAS les délimiteurs légitimes (${VAR}/path, ${VAR}:port,
// ${VAR}&&..., ${VAR}-suffixe) - uniquement [A-Za-z0-9] accolé.
// Retourne [{varName, char}] pour chaque collision trouvée.
function detectStuckCharAfterVar(str) {
  const out = [];
  const re = /\$\{([A-Z0-9_]+)\}([A-Za-z0-9])/g;
  let m;
  while ((m = re.exec(String(str || ''))) !== null) {
    out.push({ varName: m[1], char: m[2] });
  }
  return out;
}

// Champs interpolables d'un payload MCP -> liste de chaînes à scanner.
// Couvre command, args, env (valeurs), headers (valeurs), url, cwd.
function mcpInterpolableStrings(payload) {
  const strs = [];
  const push = (v) => { if (v) strs.push(String(v)); };
  push(payload.command);
  push(payload.url);
  push(payload.cwd);
  for (const a of (payload.args || [])) push(a);
  for (const v of Object.values(payload.env || {})) push(v);
  for (const v of Object.values(payload.headers || {})) push(v);
  return strs;
}

// Lint complet de l'interpolation sur une liste de chaînes.
// envKeys : noms de variables présentes dans .env.local (STATE.envKeys).
// Retourne { stuck: [{varName, char}], missing: [VAR, ...] }.
function lintInterpolation(strings, envKeys) {
  const known = new Set(envKeys || []);
  const stuck = [];
  const missing = new Set();
  for (const s of strings) {
    for (const hit of detectStuckCharAfterVar(s)) stuck.push(hit);
    for (const v of extractVars(s)) {
      if (!known.has(v)) missing.add(v);
    }
  }
  return { stuck, missing: [...missing] };
}

/* ----------------------------------------------------------------
   Format des règles de permission Claude Code
   ---------------------------------------------------------------- */

// Une permission MCP : mcp__<server>__<tool> (doubles underscores),
// `*` autorisé en tool (mcp__server__* ou mcp__server pour tout).
const _PERM_MCP_RE = /^mcp__[A-Za-z0-9_-]+(__([A-Za-z0-9_*-]+|\*))?$/;
// Un outil natif : Tool ou Tool(pattern) - ex Bash(npm:*), Read, Edit,
// WebFetch(domain:*). On reste permissif sur le pattern interne.
const _PERM_NATIVE_RE = /^[A-Z][A-Za-z0-9]*(\([^)]*\))?$/;

// Retourne true si la ligne de permission a un format plausible.
// Détecte notamment le piège mcp_server_tool (underscores simples)
// au lieu de mcp__server__tool (doubles) -> ignoré en silence par
// Claude Code. La liste des outils natifs n'étant pas exhaustive, on
// reste tolérant : on ne flagge que ce qui est clairement douteux.
function isValidPermissionLine(line) {
  const s = String(line || '').trim();
  if (!s) return true;
  // Piège ciblé : commence par "mcp" mais pas au format double-underscore.
  if (/^mcp/i.test(s)) return _PERM_MCP_RE.test(s);
  // Sinon : outil natif (avec ou sans pattern entre parenthèses).
  return _PERM_NATIVE_RE.test(s);
}

/* ----------------------------------------------------------------
   Hooks Claude Code : chemin .sh relatif (miroir du lint backend)
   ---------------------------------------------------------------- */

// Vrai si le chemin d'un script .sh de hook est robuste au cwd.
// Sûr : ${VAR}/..., /..., C:\..., C:/..., ~/...  Dangereux : relatif.
function _shPathIsSafe(p) {
  const s = String(p || '').trim();
  if (!s) return true;
  if (s.startsWith('${') || s.startsWith('$')) return true;
  if (s.startsWith('~')) return true;
  if (s.startsWith('/') || s.startsWith('\\')) return true;
  if (/^[A-Za-z]:[\\/]/.test(s)) return true;
  return false;
}

// Parcourt un objet hooks Claude Code et retourne les chemins .sh
// relatifs (3a, BLOQUANT). Miroir léger du backend pour feedback
// immédiat. Retourne [{event, badPath, command}].
function lintHooksRelativeSh(hooks) {
  const out = [];
  if (!hooks || typeof hooks !== 'object') return out;
  const re = /["']?([^\s"']*\.sh)["']?/g;
  for (const [event, entries] of Object.entries(hooks)) {
    if (!Array.isArray(entries)) continue;
    for (const entry of entries) {
      for (const sub of ((entry && entry.hooks) || [])) {
        const cmd = (sub && sub.command) || '';
        if (typeof cmd !== 'string') continue;
        let m;
        while ((m = re.exec(cmd)) !== null) {
          if (!_shPathIsSafe(m[1])) out.push({ event, badPath: m[1], command: cmd });
        }
      }
    }
  }
  return out;
}

// Message d'aide pour une ligne douteuse (POURQUOI + COMMENT).
function permissionHint(line) {
  const s = String(line || '').trim();
  if (/^mcp/i.test(s) && !_PERM_MCP_RE.test(s)) {
    return `format douteux : attends-tu \`mcp__server__tool\` (doubles underscores) ? « ${s} » serait ignoré en silence par Claude Code.`;
  }
  return `format douteux : « ${s} » ne ressemble ni à \`mcp__server__tool\` ni à un outil natif (\`Bash(npm:*)\`, \`Read\`…).`;
}

/* ----------------------------------------------------------------
   Frontmatter SKILL.md
   ---------------------------------------------------------------- */

// Vérifie la présence d'un frontmatter YAML (--- ... ---) en tête de
// fichier avec au moins les clés `name` et `description`. Sans ça,
// l'auto-découverte de Claude échoue -> skill invisible.
// Retourne { ok, missing: [clés manquantes parmi name/description] }.
function validateSkillFrontmatter(content) {
  const text = String(content || '');
  // Frontmatter : --- en tout début (BOM/espaces tolérés), bloc jusqu'au --- suivant.
  const m = text.match(/^\uFEFF?\s*---\r?\n([\s\S]*?)\r?\n---/);
  if (!m) return { ok: false, missing: ['name', 'description'] };
  const block = m[1];
  const missing = [];
  // Clé YAML en début de ligne avec une valeur non vide SUR LA MÊME LIGNE.
  // [^\S\r\n] = espace horizontal uniquement (pas \n) pour ne pas « sauter »
  // sur la valeur de la clé suivante quand la valeur courante est vide.
  if (!/^[^\S\r\n]*name[^\S\r\n]*:[^\S\r\n]*\S/m.test(block)) missing.push('name');
  if (!/^[^\S\r\n]*description[^\S\r\n]*:[^\S\r\n]*\S/m.test(block)) missing.push('description');
  return { ok: missing.length === 0, missing };
}
