# 🌌 Nebula — Claude Workspace Dashboard

Un environnement local pour gérer plusieurs workspaces Claude Code depuis une
interface web unique : workspaces, MCPs, skills, plugins, templates, hooks,
permissions et sessions.

**100 % local** — serveur Python stdlib sur `127.0.0.1:4777`, zéro dépendance
externe, zéro télémétrie, secrets dans `.env.local` jamais exposés au
navigateur.

---

## 🎯 Pourquoi

Claude Code est puissant, mais sa configuration (MCPs, skills, permissions,
hooks) vit éparpillée dans `~/.claude.json`, un `.mcp.json` par projet,
`~/.claude/skills/`, etc. Dès qu'on a plusieurs projets :

- Dupliquer ou modifier un MCP → édition manuelle de N fichiers
- Oublier un token dans un commit → fuite
- Activer un plugin seulement sur 2 workspaces sur 5 → usine à gaz
- Retrouver quelle session correspond à quel projet → galère

Nebula centralise tout ça.

---

## ✨ Fonctionnalités

### Pilotage
- **Workspaces** — CRUD, duplication, export ZIP, lancement en un clic, reprise
  de session (`claude -c`), enregistrement d'un dossier existant. Suppression
  avec **undo 10 secondes** (snackbar) sur soft delete, double confirmation
  pour la purge irréversible.
- **Templates** — création depuis modèle (Python, Node, audit, automation,
  YAML, blank) avec interpolation `{{name}}`, `{{label}}`, `{{description}}`,
  `{{tools}}`, `{{date}}`, `{{emoji}}`. Édition multi-fichiers depuis l'UI.
- **Overlays** — paquets de fichiers appliqués *par-dessus* un workspace
  existant sans rien écraser (ex. `claude-self-improving`, cf. §
  Auto-amélioration). Marqués par `.nebula-overlay.json`, appliqués depuis la
  carte du workspace.
- **MCPs** — registre unique, transport `stdio`/`http`/`sse`, champs `cwd` et
  `headers`, substitution `${VAR}` depuis `.env.local`, **auto-sync** des
  `.mcp.json` à chaque modif, import bulk depuis JSON Claude.
  Statuts calculés automatiquement (désactivé / à configurer / disponible),
  workspaces ciblés via cases à cocher, page MCPs avec **auto-refresh 30s**.
- **Recettes MCP** — catalogue 1-clic (8 recettes embarquées : Filesystem,
  GitHub, Brave Search, Fetch HTTP, Memory, Puppeteer, PostgreSQL, Slack)
  + **recettes locales** gitignored pour les MCPs perso/propriétaires.
  Éditeur GUI complet, conversion MCP → recette en 1 clic (avec détection
  auto des secrets), installation multi-instances avec auto-suffix d'ID.
- **Skills** — **bibliothèque centralisée** (magasin
  `dashboard/data/skills-library/`) comme source de vérité : édition
  multi-fichiers (SKILL.md + références), **distribution** vers le scope global
  (`~/.claude/skills/`) ou un workspace, avec **détection de désynchronisation**
  (les copies distribuées ne sont jamais écrasées en silence ; resync explicite).
- **Plugins** — browser marketplace (catalogue officiel + externes + README),
  install/uninstall en un clic, **vue scope par workspace** scalable
  (segmented control 3 états : Actif / Inactif / Hériter), actions de masse.
- **Sessions** — liste des conversations Claude Code passées par workspace.
  **Aperçu au hover** : tooltip avec les 3 premiers messages (cache client
  pour éviter les re-fetch).
- **Hooks & permissions** — éditeur GUI pour `settings.json` global + local.

### Auto-amélioration (overlay, optionnel)
- **Overlay `claude-self-improving`** — paquet de fichiers appliqué
  **par-dessus** un workspace existant (jamais d'écrasement d'un fichier déjà
  présent ; `CLAUDE.md` reçoit juste un fragment borné par marqueurs). Il
  installe une boucle d'auto-amélioration de Claude :
  - **mémoire structurée** `.claude/memory/` en hub-and-spoke (overview,
    architecture, conventions, pitfalls, sécurité…) ;
  - **pipeline d'amélioration** : `improvements.md` + (en profondeur complète)
    `ideas.md`, `backlog.md`, `roadmap.md` et **digests** hiérarchiques ;
  - **agents, slash commands et hooks pré-commit** en Python stdlib portable
    (protection des fichiers locaux, garde em-dash, validation, statusline).
  - **Bootstrap paramétrable** depuis la carte du workspace : mode projet
    (`solo` / `équipe` / `équipe-hiérarchique`) et profondeur d'install
    (`minimale` = squelette nu, `complète` = + exemples seed travaillés).
    **Idempotent** : ré-appliquer ne touche qu'aux fichiers manquants, et la
    génération échoue plutôt que de livrer un workspace incohérent (ex. un
    `settings.json` qui référencerait un hook absent).

### Confort & UX
- **5 thèmes** — Nebula sombre/clair, Marine (bleu), Solarized (cyan & ambre,
  classique reposant), Cuivre (bronze chaleureux). Persisté **côté serveur**
  (`dashboard/data/ui_state.json`) + cache localStorage pour éviter le flash
  au chargement.
- **Command palette** — `/` ou `Ctrl+K`, recherche globale.
- **Raccourcis clavier** — chord `g h/m/p/k/t/o/a` pour naviguer, `n`/`m`/`s`
  pour les actions rapides, `Ctrl+S` dans les éditeurs.
- **Page Aide** intégrée — hub de 8 cartes thématiques (Premiers pas,
  Workspaces, MCPs, Skills & Plugins, Templates, Secrets & sécurité, Outils,
  Référence & dépannage), chaque carte ouvre une sous-page focalisée.
- **Visite guidée** — tour interactif au 1er lancement (~2 min, 9 étapes)
  avec spotlight sur l'UI réelle.
- **Checklist de mise en route** — 6 étapes toujours accessibles (Outils →
  A. Démarrage). **Bandeau Home contextuel** affiché tant que la checklist
  n'est pas à 6/6.
- **Snackbar avec actions** — toast étendu avec bouton (UNDO, etc.).

### Onboarding
- **Wizard d'import** — scan de `~/.claude.json` (incluant les MCPs déclarés
  dans `projects.<path>.mcpServers`), `settings.json` et `settings.local.json`
  pour récupérer MCPs et projets existants en un clic.
- **Détection des conflits** — repère les MCPs présents à la fois dans
  `~/.claude.json`/`settings.json` et dans le registre Nebula, propose la
  migration ou le nettoyage avec backup automatique.
- **Auto-update bulletproof** — vérification git en arrière-plan (au démarrage
  + toutes les 30 min), badge gradient pulsant **"X MAJ"** dans le topbar
  + badge descriptif dans la sidebar. Modale avec changelog et `git pull`
  en un clic. **Auto-stash systématique** : tes modifs locales (modifiées,
  supprimées, untracked) sont automatiquement stashées avant le pull et
  re-poppées après. Aucun blocage possible. Si vrai conflit lors du pop :
  modifs préservées dans la pile stash. **Escape hatch** "Réinitialiser à
  la version distante" disponible si tout échoue. Détection du redémarrage
  nécessaire (Python vs frontend).

### Sécurité
- Bind `127.0.0.1` strict, pas d'auth (on suppose une machine perso).
- **Chiffrement DPAPI** (Windows) optionnel pour `.env.local` : un clic dans
  Outils → Variables d'environnement → *Activer le chiffrement*. Le fichier
  devient un blob lié à ton compte Windows + ACL stricte `icacls`. Édition
  transparente côté dashboard, illisible si copié ailleurs ou ouvert par un
  autre compte. Bouton *Désactiver / Exporter clair* pour migrer.
- Validation `safe_id` partout, regex stricte sur les paths.
- `_MUTATION_LOCK` réentrant pour les écritures concurrentes.
- Cap Content-Length 10 MB anti-DoS.
- Header CSRF `X-Nebula-XHR` requis sur les routes sensibles (env values,
  chiffrement DPAPI) — pose-able uniquement en fetch/XHR same-origin.
- Subprocess `shell=False`, encoding UTF-8 explicite, timeouts.
- Backups automatiques avant chaque modification destructive.

---

## 🗂 Architecture

```
claude-workspace/
├── CLAUDE.md                    # Contexte global chargé par Claude Code
├── .env.local.example           # Template des secrets
├── .env.local                   # ← LOCAL, gitignored
├── .gitignore
│
├── dashboard/                   # Le dashboard web
│   ├── server.py                # Serveur Python stdlib + dispatcher de routes
│   ├── index.html               # Squelette SPA
│   ├── app.css                  # Design system : tokens (8 thèmes) + composants
│   ├── css/                     # redesign.css (refonte 2026-10), editor-matrix.css, sessions.css
│   ├── app.js                   # SPA vanilla JS (page workspace, modales, palette)
│   ├── dashcore/                # Backend modulaire
│   │   ├── config.py            # Constantes & chemins
│   │   ├── helpers.py           # I/O, validation, fichiers
│   │   ├── env_local.py         # Gestion .env.local + ${VAR}
│   │   ├── env_crypto.py        # Chiffrement DPAPI Windows + ACL stricte
│   │   ├── journal.py           # Journal markdown
│   │   ├── workspace_io.py      # Paths workspace, stats, sanity check
│   │   ├── active_sessions.py   # Sessions Claude Code actives par workspace
│   │   ├── api_workspaces.py    # CRUD workspaces, templates, settings
│   │   ├── api_overlays.py      # Overlays (paquets appliqués par-dessus)
│   │   ├── api_files.py         # Explorateur de fichiers des workspaces
│   │   ├── api_mcps.py          # MCPs, conflicts, scan, sync, recettes
│   │   ├── api_plugins.py       # Plugins, skills, agents, commandes
│   │   ├── api_skills_library.py # Bibliothèque de skills centralisée (magasin)
│   │   ├── api_ui_state.py      # Persistance thème + onboarding côté serveur
│   │   └── system_update.py     # Auto-update bulletproof (auto-stash + reset)
│   ├── tests/                   # Tests unittest stdlib + CI GitLab (cf. tests/README.md)
│   └── data/                    # Déplaçable via NEBULA_DATA_DIR (sauf mcp_recipes.json)
│       ├── workspaces.json      # ← LOCAL, gitignored
│       ├── ui_state.json        # ← LOCAL, gitignored (thème, onboarded)
│       ├── skills-library/      # Magasin central de skills (source de vérité)
│       ├── mcp_recipes.json     # Catalogue public de recettes MCP
│       └── mcp_recipes.local.json # ← LOCAL, gitignored (recettes perso)
│
├── mcp/                         # Registre des MCPs
│   ├── registry.json            # ← LOCAL, gitignored (source unique)
│   └── configs/                 # Configs détaillées (samples)
│
├── memory/                      # Mémoire chargée via @import
│   ├── profil.md                # Qui tu es
│   ├── stack.md                 # Ta stack technique
│   ├── conventions.md           # Tes préférences
│   ├── global.md                # Notes globales
│   └── snippets/                # Bouts de code récurrents
│
├── scripts/                     # Utilitaires
│   ├── start-dashboard.bat      # Lance le serveur
│   ├── new-workspace.bat        # Création CLI rapide
│   ├── launch-TEMPLATE.bat      # Template (les launch-<id>.bat sont gitignored)
│   ├── statusline.py            # Statusline Claude Code
│   └── update-memory.bat        # Édite memory/global.md
│
├── templates/                   # Templates + overlays de workspace
│   ├── blank/, dev-python/, dev-node/
│   ├── audit/, automation/, config-yaml/
│   ├── claude-self-improving/   # Overlay (.nebula-overlay.json) — auto-amélioration
│   └── README.md
│
└── workspaces/                  # ← LOCAL, gitignored sauf .gitkeep
    └── <ton-projet>/
        ├── CLAUDE.md
        ├── .mcp.json            # Généré par le dashboard
        └── .claude/
            ├── settings.json    # Hooks + permissions + plugins
            ├── skills/, agents/, commands/
```

---

## 📋 Prérequis

- **Windows 10/11** -- le serveur tourne aussi sous Linux/macOS (`python3 server.py`),
  sans les fonctions propres à Windows (cf. [Linux / macOS](#-linux--macos))
- **Python 3.10+** — stdlib uniquement, aucun `pip install` requis
- **Node.js** + **npx** — pour les MCPs qui s'installent via `npx -y …`
- **Claude Code CLI** — `npm install -g @anthropic-ai/claude-code`
- **git** — pour l'auto-update

---

## 🚀 Installation

```cmd
git clone https://git.exemple.lan/erti/claude-dashboard.git C:\claude-workspace
cd C:\claude-workspace
copy .env.local.example .env.local
notepad .env.local              :: renseigne tes secrets
scripts\start-dashboard.bat
```

Ouvre http://127.0.0.1:4777/ — au premier lancement, la **visite guidée**
te montre les fonctions essentielles avec spotlight sur l'UI réelle (~2 min,
9 étapes). Tu peux la relancer à tout moment depuis la page Aide.

### ⚙️ Configuration (variables d'environnement)

Toutes optionnelles ; sans elles, le comportement est celui d'origine.

| Variable | Défaut | Rôle |
|---|---|---|
| `NEBULA_PORT` | `4777` | Port d'écoute (`--port` prime ; valeur invalide = avertissement + défaut) |
| `NEBULA_HOST` | `127.0.0.1` | Hôte d'écoute (`--host` prime). Hors boucle locale : **avertissement au démarrage**, l'API n'a pas d'authentification |
| `NEBULA_ALLOWED_HOSTS` | (vide) | Noms supplémentaires acceptés dans l'en-tête `Host` (ex. `nas.lan`, **sans port**), séparés par des virgules |
| `NEBULA_DATA_DIR` | `dashboard/data` | Dossier des données utilisateur (`workspaces.json`, `ui_state.json`, bibliothèque de skills, recettes locales, état de sync, sessions actives). Pour migrer : déplacer ces fichiers dans le nouveau dossier |
| `ATELIER_ROOT` | parent de `dashboard/` | Racine de l'installation (registre MCP, templates, workspaces, `.env.local`) |

Le contrôle anti DNS-rebinding accepte toujours `127.0.0.1` / `localhost`,
plus l'hôte configuré (sauf adresse joker `0.0.0.0` / `::`) et
`NEBULA_ALLOWED_HOSTS`. Pour un accès distant, préfère un tunnel SSH
(`ssh -L 4777:127.0.0.1:4777 poste`) à une écoute réseau.

### 🐧 Linux / macOS

```sh
cd claude-workspace/dashboard
python3 server.py              # ou : NEBULA_PORT=4800 python3 server.py --no-browser
```

Tout le pilotage (workspaces, MCPs, skills, plugins, `.env.local` en clair)
fonctionne. Restent propres à Windows et renvoient une erreur explicite
(HTTP 501) : le lancement d'une session dans une console (`cmd`), et
l'ouverture d'un fichier si `xdg-open` / `open` est absent. Le chiffrement
du coffre (DPAPI) est indisponible hors Windows.

### 🧪 Tests

```sh
python -m unittest discover -s dashboard/tests
```

Stdlib uniquement, en bac à sable (aucune donnée réelle lue ni écrite),
Windows et Linux. Détail, couverture et CI GitLab (fichier dédié, inactif
par défaut) : [`dashboard/tests/README.md`](dashboard/tests/README.md).

---

## 🧭 Utilisation au quotidien

Le dashboard a une sidebar fixe avec 6 sections principales :

| Onglet | Raccourci | Ce qu'on y fait |
|---|---|---|
| **Accueil** | `g h` | Vue d'ensemble : KPIs, grille des workspaces, sanity check, journal |
| **MCPs** | `g m` | Registre central, ajout/édition, test, import bulk |
| **Plugins** | `g p` | Marketplace, installés, **scope par workspace** |
| **Skills** | `g k` | Création, édition multi-fichiers, copier vers workspace |
| **Templates** | `g t` | Modèles avec édition GUI complète |
| **Outils** | `g o` | Apparence, onboarding, hooks, env, backups, maintenance |
| **Aide** | `g a` | Hub de documentation : 8 sujets en cartes thématiques |

Plus la **palette de recherche globale** : `/` ou `Ctrl+K`.

### Lancer un workspace

1. Page **Accueil** → bouton **Lancer** sur la carte
2. Un terminal s'ouvre dans le dossier, `claude` démarre, le `CLAUDE.md`
   local est chargé automatiquement
3. Les MCPs assignés sont déjà dans `.mcp.json`

### Créer un workspace

3 façons :
- **+ Nouveau** sur l'Accueil — création depuis template
- **+ Dossier** — enregistrer un dossier déjà sur disque
- **Importer config** — récupération depuis `~/.claude/projects/`

---

## 🔐 Le flux `.env.local` → `${VAR}` → `.mcp.json`

1. Tu renseignes tes secrets dans `.env.local` (jamais committé).
2. Dans le dashboard, tu déclares un MCP avec des placeholders :
   ```json
   "env": { "OPNSENSE_API_KEY": "${OPNSENSE_API_KEY}" }
   ```
3. Quand le dashboard écrit un `.mcp.json` dans un workspace, il substitue
   chaque `${VAR}` par la valeur de `.env.local`.
4. Claude Code lit ce `.mcp.json` local au démarrage — il ne voit jamais
   le placeholder.

Va dans **Outils → Variables d'environnement** pour gérer le `.env.local`
en GUI :

- Ajouter, **modifier** (crayon, édition inline avec Entrée pour valider),
  supprimer une variable
- Filtre rapide par nom, groupement par préfixe
- Bouton œil pour révéler les valeurs masquées
- **Bouton "Activer le chiffrement"** (Windows) : un clic et le fichier
  devient un blob DPAPI illisible sans ton compte Windows. ACL stricte
  appliquée (lecture limitée à toi + SYSTEM). L'édition reste transparente.
  Bouton "Désactiver / Exporter clair" pour récupérer une copie en clair
  (backup, migration, autre poste).

---

## 🔌 Ajouter un MCP

**Page MCPs → + Nouveau MCP**. Le formulaire change selon le transport :

### stdio
- `command` (npx, uvx, python…)
- `args` (un par ligne)
- `cwd` (working directory, optionnel, supporte `${VAR}`)
- `env` (KEY=VALUE par ligne)

### http / sse
- `url`
- `headers` (Authorization=Bearer ${TOKEN}, etc.)

Plus l'onglet **JSON brut** pour copier-coller un bloc complet (depuis un
README de MCP par exemple), et le bouton **Importer** sur la page MCPs pour
coller un format `{"mcpServers": {...}}` Claude Code standard.

Les **badges sur la card** (statut, env manquant, nombre de workspaces ciblés)
suffisent au quotidien — quand un MCP plante réellement, l'erreur remonte
directement dans Claude Code.

---

## 🍱 Recettes MCP — installation 1-clic

Plutôt que de chercher la commande/args/env de chaque MCP populaire dans des
README éparpillés, le dashboard embarque un **catalogue de recettes**
pré-configurées.

### Catalogue public (8 recettes embarquées)

📁 Filesystem · 🐙 GitHub · 🔍 Brave Search · 🌐 Fetch HTTP · 🧠 Memory ·
🎭 Puppeteer · 🐘 PostgreSQL · 💬 Slack

Servies depuis `dashboard/data/mcp_recipes.json` (versionné, mis à jour via
auto-update). Pour étendre le catalogue public, édite ce fichier et push.

### Recettes locales (perso, gitignored)

Pour les MCPs propriétaires ou hyper-personnels (firewall interne, BDD perso,
script local custom…), bouton **+ Nouvelle recette** dans la modale Recettes
ouvre l'éditeur GUI complet :

- Métadonnées : id, nom, emoji, description, doc URL
- Transport (stdio/http/sse) avec champs adaptés
- Liste dynamique de **paramètres** : key, label, placeholder, cases `secret`
  (input password + masquage preview) et `required`

Stocké dans `dashboard/data/mcp_recipes.local.json` (gitignored). Modifiable
ensuite via le bouton ✎ sur chaque carte locale.

### Multi-install (templates réutilisables)

Une recette n'est pas "à usage unique" — installe-la **N fois** avec des
configs différentes :

- 2 firewalls OPNsense → `opnsense-prod` + `opnsense-staging`
- 2 GitHub → `github-perso` + `github-pro` (tokens différents)
- 3 BDD PostgreSQL → `pg-local`, `pg-staging`, `pg-prod`

L'ID est auto-suffixé (`opnsense-2`, `opnsense-3`) avec hint visible si
des instances existent déjà. Tu peux personnaliser l'ID pour qu'il soit
sémantique.

### MCP existant → recette en 1 clic

Tu as déjà configuré un MCP qui marche ? Card MCP → **Modifier** → bouton
**✨ Sauver comme recette** dans le footer. Conversion intelligente :

- Chaque var d'env devient un param `${KEY}`
- Heuristique secret : `/token|key|secret|password|auth|credential|bearer/i`
  → marqué `secret: true` (input password + masqué dans la preview)
- Tu ajustes labels/placeholders avant de valider

Parfait pour transformer une config qui marche en template réutilisable
pour d'autres environnements.

---

## 🔄 Auto-update bulletproof

Quand tu pousses des commits sur la branche `main`, les utilisateurs voient
automatiquement un **badge gradient pulsant "X MAJ"** dans leur topbar
(vérif au démarrage + toutes les 30 min). Clic → modale avec :

- Version locale (sha court) + tracking branch
- Liste des commits à venir (sha + message + auteur + date relative)
- Bouton **Appliquer la mise à jour**
- Détection auto : si seuls JS/CSS/HTML ont changé → F5 suffit. Si du
  Python a changé → bandeau "Redémarrage requis".

### Garanties zéro blocage

L'update n'échoue **jamais** silencieusement :

1. **Pré-stash systématique** — si tu as des modifs locales (fichiers
   modifiés, supprimés, untracked), `git stash --include-untracked` avec
   un label horodaté avant le pull.
2. **Pull** — `git pull --ff-only` sur état propre.
3. **Pop** — `git stash pop` après le pull, dans tous les cas (même si pull
   a échoué) pour restaurer l'état local.
4. **Si pop conflit** — tes modifs sont préservées dans la pile (`git stash
   list` les retrouve), warning explicite avec le label pour récupération
   CLI manuelle.

### Modes de panne couverts

| Cas | Comportement |
|---|---|
| Modifs locales sur fichiers trackés | Auto-stash |
| Fichiers supprimés (`D ...`) | Auto-stash |
| Untracked qui collisionnent | Auto-stash --include-untracked |
| Lock orphelin `.git/index.lock` > 60s | Retiré automatiquement |
| Branches divergées | Hint + bouton "Réinitialiser à la version distante" |
| Réseau / auth / disque plein | Hint humain explicite |

### Escape hatch : Réinitialiser à la version distante

Si l'update échoue malgré l'auto-stash (cas exceptionnel), un panneau
"Forcer l'alignement" apparaît dans la modale avec un bouton qui exécute
`git fetch + git reset --hard origin/main` (avec pré-stash de sauvegarde).
Tes données utilisateur (registry, workspaces.json, .env.local, mémoire
perso) sont préservées via `.gitignore` et `--skip-worktree`.

### Workflow mainteneur

Pas de pipeline CI, pas de MR — push direct sur `main` depuis l'export :

```cmd
cd C:\claude-workspace-export
:: (sync depuis ton install perso si besoin)
python ../claude-workspace/dashboard/tools/preflight.py   :: validation pre-push
git add .
git commit -m "feat: ..."
git push origin main
```

Tous les utilisateurs reçoivent la mise à jour automatiquement.

---

## 🛠 Détection des conflits avec la config Claude globale

Si des MCPs existent à la fois dans `~/.claude.json` ou
`~/.claude/settings.json` **et** dans le registre Nebula, ils sont
dupliqués (ça marche par précédence project > user > global, mais c'est
fragile).

**Page MCPs** affiche un bandeau jaune si des conflits sont détectés. Clic
sur **Examiner** → modale avec :
- **Doublons** (mêmes IDs des deux côtés) → bouton "Retirer du global"
  (Nebula reste source de vérité, backup `.bak` créé)
- **Orphelins** (uniquement dans Claude global) → bouton "Migrer" pour les
  importer dans Nebula en un coup, ou poubelle si obsolètes

---

## 🎨 Thèmes

**Outils → Apparence & assistance** propose 5 thèmes :

| Thème | Style |
|---|---|
| Nebula | Sombre · violet & ocre (défaut) |
| Nebula clair | Clair · violet profond |
| Marine | Sombre · bleu profond |
| Solarized | Sombre · cyan & ambre (classique reposant pour les yeux) |
| Cuivre | Sombre · bronze chaleureux |

Application instantanée, persistance côté serveur + cache localStorage,
transitions douces.

---

## ⌨️ Raccourcis clavier

| Touche | Action |
|---|---|
| `/` ou `Ctrl+K` | Palette de recherche globale |
| `g` puis `h/m/p/k/t/o/a` | Naviguer (home/MCPs/plugins/skills/templates/outils/aide) |
| `n` | Nouveau workspace |
| `m` | Nouveau MCP |
| `s` | Sync tous les workspaces |
| `Ctrl+S` | Sauvegarder un fichier (modales d'édition) |
| `Esc` | Fermer modale ou palette |

---

## 🛡 Sécurité

- `.env.local` est dans `.gitignore`.
- Le serveur bind sur `127.0.0.1` uniquement.
- Pas d'authentification — on suppose une seule personne sur la machine.
- Validation `safe_id` (regex `[a-zA-Z0-9_-]{1,40}`) partout côté backend.
- Path traversal bloqué via `Path.relative_to()` strict.
- Subprocess sans `shell=True`, args en liste, encoding UTF-8 explicite.
- Backups `.bak` avant toute écriture destructive (registry, settings, hooks).
- `_MUTATION_LOCK` réentrant pour la cohérence concurrente.
- Les valeurs résolues des `${VAR}` ne quittent jamais le serveur : le
  navigateur voit le placeholder, pas la valeur.
- Les `.mcp.json` des workspaces contiennent les secrets résolus — ils sont
  gitignored par défaut.

---

## 📚 Lexique de MCPs prêts à l'emploi

Exporte ta config actuelle depuis **MCPs → Importer / exporter → Copier**
(généré à la demande depuis le registre, format Claude `mcpServers`, sans
secret résolu), ou colle l'un des exemples ci-dessous dans **MCPs → Importer**.
Les `${VAR}` sont à définir dans `.env.local` :

### 📁 filesystem — accès fichiers scopé

```json
"filesystem": {
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-filesystem", "C:\\claude-workspace\\workspaces"]
}
```

### 🛡 opnsense — pilotage du firewall

`.env.local` :
```env
OPNSENSE_URL=https://opnsense.exemple.lan:4443
OPNSENSE_API_KEY=...
OPNSENSE_API_SECRET=...
OPNSENSE_VERIFY_SSL=false
```

### 🔀 n8n — workflows via supergateway

`.env.local` :
```env
N8N_URL=https://n8n.exemple.lan
N8N_TOKEN=eyJhbGci...
```

### 📖 wikijs — Wiki.js read/write

`.env.local` :
```env
WIKIJS_API_URL=https://wiki.exemple.com
WIKIJS_TOKEN=eyJhbGci...
```

### 🔬 binary-ninja — reverse engineering

`.env.local` :
```env
BINJA_MCP_URL=http://127.0.0.1:42069
BINJA_MCP_KEY=binja-codemode-local
BINJA_MCP_SCRIPT=C:/path/to/mcp_bridge.py
```

### 🐞 x64dbg — debugger via script Python

`.env.local` :
```env
X64DBG_PYTHON=C:/path/to/python.exe
X64DBG_SCRIPT=C:/path/to/x64dbg_mcp.py
```

### 🏠 Home Assistant

```json
"homeassistant": { "type": "http", "url": "${HA_MCP_URL}" }
```

Pour récupérer le détail complet de ta config, utilise l'export depuis
**MCPs → Importer / exporter** (dérivé du registre `mcp/registry.json`).

---

## ➕ Ajouter un workspace

- **Dashboard** : bouton *+ Nouveau*, choisir un template
- **CLI** : `scripts\new-workspace.bat` (interactif)
- **Manuel** : voir `AJOUTER-WORKSPACE.md`

---

## 🧱 Ajouter un template

1. `cp -r templates/blank templates/mon-template`
2. Éditer `.template.json` (label, description, emoji)
3. Éditer les fichiers en utilisant les placeholders
4. Recharger le dashboard

Ou directement depuis le GUI : **Templates → Éditer** sur une carte ouvre un
éditeur multi-fichiers avec arborescence + sauvegarde par `Ctrl+S`.

Détails dans `templates/README.md`.

---

## 📄 Licence

MIT — fais-en ce que tu veux.
