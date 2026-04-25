# 🧩 Atelier — Claude Workspace Dashboard

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

Atelier centralise tout ça.

---

## ✨ Fonctionnalités

### Pilotage
- **Workspaces** — CRUD, duplication, export ZIP, lancement en un clic, reprise
  de session (`claude -c`), enregistrement d'un dossier existant.
- **Templates** — création depuis modèle (Python, Node, audit, automation,
  YAML, blank) avec interpolation `{{name}}`, `{{label}}`, `{{description}}`,
  `{{tools}}`, `{{date}}`, `{{emoji}}`. Édition multi-fichiers depuis l'UI.
- **MCPs** — registre unique, transport `stdio`/`http`/`sse`, champs `cwd` et
  `headers`, substitution `${VAR}` depuis `.env.local`, sync automatique des
  `.mcp.json`, test live, import bulk depuis JSON Claude.
- **Skills** — page dédiée avec édition multi-fichiers (SKILL.md + références),
  copier vers workspaces, cross-référence.
- **Plugins** — browser marketplace (catalogue officiel + externes + README),
  install/uninstall en un clic, **vue scope par workspace** scalable
  (segmented control 3 états : Actif / Inactif / Hériter), actions de masse.
- **Sessions** — liste des conversations Claude Code passées par workspace.
- **Hooks & permissions** — éditeur GUI pour `settings.json` global + local.

### Confort & UX
- **5 thèmes** — Atelier sombre/clair, Marine (bleu), Forêt (émeraude),
  Brique (orange). Persisté en localStorage.
- **Command palette** — `/` ou `Ctrl+K`, recherche globale.
- **Raccourcis clavier** — chord `g h/m/p/k/t/o/a` pour naviguer, `n`/`m`/`s`
  pour les actions rapides, `Ctrl+S` dans les éditeurs.
- **Page Aide** intégrée — 12 sections couvrant tout, avec sommaire sticky.
- **Wizard premier lancement** — 5 étapes (bienvenue, thème, import config,
  workspace, raccourcis) qui se déclenche automatiquement au 1er run.

### Onboarding
- **Wizard d'import** — scan de `~/.claude/` pour récupérer MCPs et projets
  existants en un clic.
- **Détection des conflits** — repère les MCPs présents à la fois dans
  `~/.claude.json`/`settings.json` et dans le registre Atelier, propose la
  migration ou le nettoyage avec backup automatique.
- **Auto-update** — vérification git en arrière-plan, badge dans la sidebar
  quand des updates sont dispos, modale avec changelog et `git pull` en un
  clic. Détection du redémarrage nécessaire (Python vs frontend).

### Sécurité
- Bind `127.0.0.1` strict, pas d'auth (on suppose une machine perso).
- Validation `safe_id` partout, regex stricte sur les paths.
- `_MUTATION_LOCK` réentrant pour les écritures concurrentes.
- Cap Content-Length 10 MB anti-DoS.
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
│   ├── app.css                  # Design system (5 thèmes)
│   ├── app.js                   # SPA vanilla JS (router, pages, modales)
│   ├── dashcore/                # Backend modulaire
│   │   ├── config.py            # Constantes & chemins
│   │   ├── helpers.py           # I/O, validation, fichiers
│   │   ├── env_local.py         # Gestion .env.local + ${VAR}
│   │   ├── journal.py           # Journal markdown
│   │   ├── workspace_io.py      # Paths workspace, stats, sanity check
│   │   ├── api_workspaces.py    # CRUD workspaces, templates, settings
│   │   ├── api_mcps.py          # MCPs, conflicts, scan, sync
│   │   ├── api_plugins.py       # Plugins, skills, agents, commandes
│   │   └── system_update.py     # Auto-update via git
│   └── data/
│       └── workspaces.json      # ← LOCAL, gitignored
│
├── mcp/                         # Registre des MCPs
│   ├── registry.json            # ← LOCAL, gitignored
│   ├── import-mcps.json         # Bundle d'exemples à importer
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
├── templates/                   # Templates de workspace
│   ├── blank/, dev-python/, dev-node/
│   ├── audit/, automation/, config-yaml/
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

- **Windows 10/11** — adaptable Linux/macOS (les scripts `.bat` sont à porter)
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

Ouvre http://127.0.0.1:4777/ — au premier lancement, le **wizard
d'introduction** te guide en 5 étapes : choix du thème, import auto de ta
config Claude existante, création d'un premier workspace, raccourcis clavier.

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
| **Aide** | `g a` | Documentation utilisateur intégrée (12 sections) |

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
en GUI (filtre, groupement par préfixe, masquage des valeurs).

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

---

## 🔄 Auto-update

Quand tu pousses des commits sur la branche `main` du repo, les utilisateurs
voient automatiquement un **badge violet** dans leur sidebar au prochain
démarrage (vérification toutes les 6 h en cache). Clic → modale avec :
- Version locale (sha court) et tracking branch
- Liste des commits à venir (sha + message + auteur + date relative)
- Bouton **Appliquer la mise à jour** → `git pull --ff-only`
- Détection automatique : si seuls les fichiers JS/CSS/HTML ont changé,
  un simple F5 suffit. Si du Python a changé, message demande de
  redémarrer `start-dashboard.bat`.

Sécurité : refus si modifications locales non committées, commandes git
hardcodées (pas d'injection possible).

### Workflow mainteneur (pour pousser une mise à jour)

Pas de pipeline CI, pas de MR — push direct sur `main` :

```cmd
cd C:\claude-workspace-export
:: (sync depuis ton install perso si besoin via le script)
git add .
git commit -m "feat: ..."
git push origin main
```

Tous les utilisateurs verront la mise à jour à leur prochain démarrage du
dashboard.

---

## 🛠 Détection des conflits avec la config Claude globale

Si des MCPs existent à la fois dans `~/.claude.json` ou
`~/.claude/settings.json` **et** dans le registre Atelier, ils sont
dupliqués (ça marche par précédence project > user > global, mais c'est
fragile).

**Page MCPs** affiche un bandeau jaune si des conflits sont détectés. Clic
sur **Examiner** → modale avec :
- **Doublons** (mêmes IDs des deux côtés) → bouton "Retirer du global"
  (Atelier reste source de vérité, backup `.bak` créé)
- **Orphelins** (uniquement dans Claude global) → bouton "Migrer" pour les
  importer dans Atelier en un coup, ou poubelle si obsolètes

---

## 🎨 Thèmes

**Outils → Apparence & assistance** propose 5 thèmes :

| Thème | Style |
|---|---|
| Atelier | Sombre · violet & ocre (défaut) |
| Atelier clair | Clair · violet profond |
| Marine | Sombre · bleu profond |
| Forêt | Sombre · vert émeraude |
| Brique | Sombre · orange chaud |

Application instantanée, persistance localStorage, transitions douces.

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

Bundle prêt dans `mcp/import-mcps.json` — copie la partie `mcpServers` dans
**MCPs → Importer**. Les `${VAR}` à définir dans `.env.local` :

### 📁 filesystem — accès fichiers scopé

```json
"filesystem": {
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "@anthropic-ai/mcp-server-filesystem", "C:\\claude-workspace\\workspaces"]
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

Voir le détail complet de chaque MCP dans `mcp/import-mcps.json`.

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
