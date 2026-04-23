# 🧩 Claude Workspace

Un environnement local pour gérer plusieurs workspaces Claude Code depuis une
interface web unique : MCPs, skills, plugins, templates, hooks et permissions.

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

Ce dashboard centralise tout ça.

---

## ✨ Fonctionnalités

- **Workspaces** — CRUD, duplication, export, lancement en un clic.
- **Templates** — création d'un workspace depuis un template (Python, Node,
  audit, automation, YAML, blank) avec interpolation `{{name}}`, `{{date}}`…
- **MCPs** — registre unique, substitution `${VAR}` depuis `.env.local`,
  auto-sync des `.mcp.json` quand un MCP change, import JSON, test.
- **Skills / Agents / Commands** — scope global ou local, matrice
  skill × workspace.
- **Plugins** — marketplace officiel, install/uninstall/enable/disable via
  `claude plugin`, override par workspace dans `settings.json`.
- **Sessions** — browser des sessions passées par workspace.
- **Hooks & permissions** — éditeur pour `settings.json` global et local.
- **Statusline** — workspace, branche git, modèle, nombre de MCPs actifs.

---

## 🗂 Architecture

```
claude-workspace/
├── CLAUDE.md                 # Contexte global chargé par Claude Code
├── .env.local.example        # Template des secrets (à copier en .env.local)
├── .gitignore
│
├── dashboard/                # Le dashboard web
│   ├── server.py             # Serveur Python stdlib (ThreadingHTTPServer)
│   ├── index.html            # SPA (hash router, vanilla JS)
│   └── data/
│       └── workspaces.json   # Liste des workspaces déclarés
│
├── mcp/                      # Registre des MCPs
│   ├── registry.json         # MCPs avec placeholders ${VAR}
│   ├── import-mcps.json      # Bundle d'exemples à importer
│   └── configs/              # Configs détaillées par MCP (optionnel)
│
├── memory/                   # Mémoire chargée via @import dans CLAUDE.md
│   ├── profil.md             # Qui tu es
│   ├── stack.md              # Ta stack technique
│   ├── conventions.md        # Tes préférences de collaboration
│   └── snippets/             # Bouts de code récurrents
│
├── scripts/                  # Utilitaires Windows
│   ├── start-dashboard.bat   # Lance le serveur
│   ├── new-workspace.bat     # Création rapide en ligne de commande
│   ├── launch-TEMPLATE.bat   # Template de script de lancement
│   ├── statusline.py         # Statusline Claude Code
│   └── update-memory.bat     # Ouvre memory/global.md dans notepad
│
├── templates/                # Templates de workspace
│   ├── blank/                # Minimal
│   ├── dev-python/           # Projet Python (src/ + tests/ + requirements)
│   ├── dev-node/             # Projet Node.js ESM
│   ├── audit/                # Audit sécurité (rapports datés)
│   ├── automation/           # Workflows / scripts d'automatisation
│   └── config-yaml/          # Configs YAML (HA, k8s, compose…)
│
└── workspaces/               # Tes workspaces (vide à l'origine)
    └── <ton-projet>/
        ├── CLAUDE.md         # Contexte du workspace
        ├── .mcp.json         # Généré par le dashboard
        └── .claude/
            ├── settings.json # Hooks + permissions + enabledPlugins
            ├── skills/       # Skills locales
            ├── agents/       # Subagents
            └── commands/     # Slash commands
```

---

## 📋 Prérequis

- **Windows 10/11** — adaptation Linux/macOS possible, scripts `.bat` à porter
- **Python 3.10+** — stdlib uniquement, aucun `pip install` requis
- **Node.js** + **npx** — pour les MCPs qui s'installent via `npx -y …`
- **Claude Code CLI** — `npm install -g @anthropic-ai/claude-code`

---

## 🚀 Installation

```cmd
git clone https://git.exemple.lan/erti/claude-dashboard.git C:\claude-workspace
cd C:\claude-workspace
copy .env.local.example .env.local
notepad .env.local              :: renseigne tes secrets
scripts\start-dashboard.bat
```

Puis ouvre http://127.0.0.1:4777/

---

## 🧭 Utilisation au quotidien

Le dashboard est une SPA avec cinq onglets :

| Onglet | Ce qu'on y fait |
|---|---|
| **Workspaces** | Créer, dupliquer, lancer (`claude` s'ouvre dans le bon dossier), supprimer, exporter un workspace. Voir les sessions passées. |
| **MCPs** | Registre central des MCPs. Assigner un MCP à N workspaces — les `.mcp.json` correspondants sont écrits automatiquement avec les `${VAR}` résolus. |
| **Plugins** | Parcourir le marketplace officiel, installer en un clic, activer/désactiver par workspace via une matrice plugin × workspace. |
| **Templates** | Voir la liste des templates disponibles avec aperçu du `CLAUDE.md`. |
| **Outils** | Hooks & permissions globaux, skills, agents, commandes, cleanup. |

### Lancer un workspace

1. Onglet **Workspaces** → bouton ▶ sur la ligne du workspace
2. Un terminal s'ouvre dans le bon dossier, `claude` démarre, le `CLAUDE.md`
   local est chargé automatiquement.
3. Les MCPs assignés à ce workspace sont déjà présents dans `.mcp.json`.

### Créer un workspace

Onglet **Workspaces** → **+ Nouveau** :
- Choisis un template (blank, dev-python, dev-node, audit, automation, …).
- Remplis label / description / outils.
- Le dossier est créé, le `CLAUDE.md` interpolé avec tes valeurs, le script de
  lancement ajouté dans `scripts\`.

### Éditer un workspace

Bouton ✎ → édition du label, description, emoji, path. Bouton 📋 pour
dupliquer, 🗑 pour supprimer.

### Retrouver une session

Ouvrir un workspace → onglet **Sessions** → liste des conversations Claude
Code passées pour ce dossier (transcripts JSONL dans
`~/.claude/projects/<hash>/`).

---

## 🔐 Le flux `.env.local` → `${VAR}` → `.mcp.json`

1. Tu renseignes tes secrets dans `.env.local` (jamais committé, jamais
   envoyé au navigateur).
2. Dans le dashboard, tu déclares un MCP avec des placeholders :
   ```json
   "env": { "OPNSENSE_API_KEY": "${OPNSENSE_API_KEY}" }
   ```
3. Quand le dashboard écrit un `.mcp.json` dans un workspace, il substitue
   chaque `${VAR}` par la valeur de `.env.local`.
4. Claude Code lit ce `.mcp.json` local au démarrage — il ne voit jamais
   le placeholder.

---

## 🔌 Ajouter un MCP

Trois façons :

**A. Formulaire** — onglet **MCPs** → **+ Nouveau MCP** → remplir type
(`stdio` ou `http`), command, args, env, workspaces concernés.

**B. Import JSON** — onglet **MCPs** → **↧ Importer JSON** → coller un bloc
`mcpServers` (format Claude Code standard). Pratique pour migrer depuis
`~/.claude.json`.

**C. Bundle d'exemples** — ouvrir `mcp/import-mcps.json`, copier la partie
`mcpServers`, la coller dans l'import. Tous les MCPs du lexique ci-dessous y
sont prêts à l'emploi.

Après ajout, dans le panneau de scopes : coche les workspaces où le MCP doit
être actif. Les `.mcp.json` sont régénérés immédiatement, avec les `${VAR}`
résolus. Claude Code les lit au prochain démarrage du workspace.

---

## 📚 Lexique de MCPs prêts à l'emploi

Tous les MCPs ci-dessous utilisent des `${VAR}` — à définir dans
`.env.local` avant import.

### 📁 filesystem — accès fichiers scopé

Sert d'accès fichiers contrôlé pour Claude Code. **Toujours scoper à un
dossier précis**, jamais `C:\` entier.

**Prérequis** : aucun (téléchargé à la volée par `npx -y`).

```json
"filesystem": {
  "type": "stdio",
  "command": "npx",
  "args": [
    "-y",
    "@anthropic-ai/mcp-server-filesystem",
    "C:\\claude-workspace\\workspaces"
  ],
  "env": {}
}
```

---

### 🛡 opnsense — pilotage du firewall OPNsense

Lecture/écriture de la config OPNsense via son API REST.

**Prérequis** : package npm `@richard-stovall/opnsense-mcp-server`
(installé à la volée par `npx`). Générer une API key + secret dans OPNsense :
*System → Access → Users → ton user → API keys*.

`.env.local` :
```env
OPNSENSE_URL=https://opnsense.exemple.lan:4443
OPNSENSE_API_KEY=...
OPNSENSE_API_SECRET=...
OPNSENSE_VERIFY_SSL=false
```

```json
"opnsense": {
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "@richard-stovall/opnsense-mcp-server"],
  "env": {
    "OPNSENSE_URL": "${OPNSENSE_URL}",
    "OPNSENSE_API_KEY": "${OPNSENSE_API_KEY}",
    "OPNSENSE_API_SECRET": "${OPNSENSE_API_SECRET}",
    "OPNSENSE_VERIFY_SSL": "${OPNSENSE_VERIFY_SSL}"
  }
}
```

---

### 🔀 n8n — workflows via supergateway

n8n expose un endpoint MCP en HTTP streamable. Pour le consommer en stdio
(format attendu par Claude Code), on utilise `supergateway` comme bridge.

**Prérequis** : le plugin MCP activé côté n8n, puis le token JWT copié depuis
l'UI n8n. Le package `supergateway` est téléchargé à la volée par `npx`.

`.env.local` :
```env
N8N_URL=https://n8n.exemple.lan
N8N_TOKEN=eyJhbGci...
```

```json
"n8n": {
  "type": "stdio",
  "command": "cmd",
  "args": [
    "/c", "npx", "-y", "supergateway",
    "--streamableHttp", "${N8N_URL}/mcp-server/http",
    "--header", "Authorization: Bearer ${N8N_TOKEN}"
  ],
  "env": {}
}
```

---

### 📖 wikijs — lecture/écriture Wiki.js

**Prérequis** : package npm `wikijs-mcp` (installé à la volée par `npx`).
Générer un token dans Wiki.js : *Administration → API Access → New API Key*
avec les droits `read:pages`, `write:pages`.

`.env.local` :
```env
WIKIJS_API_URL=https://wiki.exemple.com
WIKIJS_TOKEN=eyJhbGci...
```

```json
"wikijs": {
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "wikijs-mcp", "server"],
  "env": {
    "WIKIJS_API_URL": "${WIKIJS_API_URL}",
    "WIKIJS_TOKEN": "${WIKIJS_TOKEN}"
  }
}
```

---

### 🔬 binary-ninja — reverse engineering (pont local)

**Prérequis** :
- Binary Ninja installé.
- Plugin `akrutsinger/binja_codemode_mcp` installé via le Plugin Manager de
  Binary Ninja (communauté).
- Python 3 disponible en CLI (`python3`).
- Binary Ninja doit être **ouvert** avec un binaire chargé pour que le pont
  réponde (le plugin écoute en local).

`.env.local` :
```env
BINJA_MCP_URL=http://127.0.0.1:42069
BINJA_MCP_KEY=binja-codemode-local
BINJA_MCP_SCRIPT=C:/Users/Toi/AppData/Roaming/Binary Ninja/repositories/community/plugins/akrutsinger_binja_codemode_mcp/bridge/mcp_bridge.py
```

```json
"binary-ninja": {
  "type": "stdio",
  "command": "python3",
  "args": ["${BINJA_MCP_SCRIPT}"],
  "env": {
    "BINJA_MCP_URL": "${BINJA_MCP_URL}",
    "BINJA_MCP_KEY": "${BINJA_MCP_KEY}"
  }
}
```

---

### 🐞 x64dbg — debugger via script Python

**Prérequis** : x64dbg installé, script Python local qui expose le MCP
(à fournir toi-même ou récupérer depuis un projet tiers). Le chemin Python
pointe vers l'interpréteur embarqué de x64dbg si tu l'utilises.

`.env.local` :
```env
X64DBG_PYTHON=C:/Users/Toi/AppData/Local/Python/pythoncore-3.14-64/python.exe
X64DBG_SCRIPT=C:/chemin/vers/x64dbg_mcp.py
```

```json
"x64dbg": {
  "type": "stdio",
  "command": "${X64DBG_PYTHON}",
  "args": ["${X64DBG_SCRIPT}"],
  "env": {}
}
```

---

### 🏠 Home Assistant — domotique (HTTP direct)

Home Assistant expose nativement un endpoint MCP (add-on officiel).

**Prérequis** : HA ≥ 2024.11, add-on *MCP Server* activé. Copier l'URL depuis
l'onglet *Intégrations* → *MCP Server*.

```json
"homeassistant": {
  "type": "http",
  "url": "${HA_MCP_URL}"
}
```

---

## ➕ Ajouter un workspace

- **Dashboard** : bouton *+ Nouveau*, choisir un template, remplir
  label/description/outils.
- **CLI** : `scripts\new-workspace.bat` (interactif).
- **Manuel** : voir `AJOUTER-WORKSPACE.md`.

---

## 🧱 Ajouter un template

1. `cp -r templates/blank templates/mon-template`
2. Éditer `.template.json` (label, description, emoji).
3. Éditer `CLAUDE.md` en utilisant les placeholders `{{name}}`, `{{label}}`,
   `{{description}}`, `{{tools}}`, `{{date}}`, `{{emoji}}`.
4. Recharger le dashboard — le template apparaît dans le sélecteur.

Détails complets dans `templates/README.md`.

---

## 🛡 Sécurité

- `.env.local` est dans `.gitignore` dès le départ.
- Le serveur bind sur `127.0.0.1` uniquement — jamais exposé au LAN.
- Pas d'authentification : on part du principe qu'une seule personne accède à
  la machine. Sinon, ajoute un reverse-proxy avec auth.
- Les valeurs résolues des `${VAR}` ne quittent jamais le serveur : le
  navigateur voit le placeholder, pas la valeur.
- Les `.mcp.json` des workspaces **contiennent les secrets résolus** — ils
  sont déjà dans `.gitignore`, ne les commit jamais.

---

## 📄 Licence

MIT — fais-en ce que tu veux.
