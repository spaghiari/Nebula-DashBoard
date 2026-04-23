# Claude Workspace

Un environnement local pour gérer plusieurs workspaces Claude Code depuis une
interface web unique : MCPs, skills, plugins, templates, hooks et permissions.

**100 % local** — serveur Python stdlib sur `127.0.0.1:4777`, zéro dépendance
externe, zéro télémétrie, secrets dans `.env.local` jamais exposés au
navigateur.

---

## Pourquoi

Claude Code est puissant mais sa config (MCPs, skills, permissions, hooks) vit
éparpillée dans `~/.claude.json`, `.mcp.json` par projet, `~/.claude/skills/`,
etc. Dès qu'on a plusieurs projets :

- Dupliquer/modifier un MCP → édition manuelle de N fichiers
- Oublier un token dans un commit → fuite
- Activer un plugin seulement sur 2 workspaces sur 5 → usine à gaz
- Retrouver quelle session correspond à quel projet → galère

Ce dashboard centralise tout ça.

---

## Fonctionnalités

- **Workspaces** — CRUD, duplication, export, lancement 1 clic (ouvre un
  terminal `claude` dans le bon dossier)
- **Templates** — création d'un workspace depuis un template (Python, Node,
  audit, automation, YAML, blank) avec interpolation `{{name}}`, `{{date}}`…
- **MCPs** — registre unique, substitution `${VAR}` depuis `.env.local`,
  auto-sync des `.mcp.json` de chaque workspace quand un MCP change, import
  JSON, test de connexion
- **Skills / Agents / Commands** — scope global (`~/.claude/skills/`) ou local
  (`<ws>/.claude/skills/`), matrice skill × workspace
- **Plugins** — parcours du marketplace officiel, install/uninstall/enable/
  disable via la CLI `claude plugin`, override par workspace via
  `enabledPlugins` dans `settings.json`
- **Sessions** — browser des sessions Claude Code passées par workspace
- **Hooks & permissions** — éditeur pour `~/.claude/settings.json` et
  `<ws>/.claude/settings.json`
- **Statusline** — affiche workspace, branche git, modèle, nb de MCPs actifs

---

## Architecture

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
├── memory/                   # Mémoire globale chargée via @import dans CLAUDE.md
│   ├── profil.md             # Qui tu es
│   ├── stack.md              # Ta stack technique
│   ├── conventions.md        # Tes préférences de collaboration
│   └── snippets/             # Bouts de code récurrents
│
├── scripts/                  # Utilitaires Windows
│   ├── start-dashboard.bat   # Lance le serveur
│   ├── new-workspace.bat     # Création rapide en ligne de commande
│   ├── launch-TEMPLATE.bat   # Template de script de lancement par workspace
│   ├── statusline.py         # Statusline Claude Code
│   └── update-memory.bat     # Ouvre memory/global.md dans notepad
│
├── templates/                # Templates de workspace
│   ├── README.md             # Format d'un template
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

## Prérequis

- **Windows 10/11** (adaptation Linux/macOS possible, scripts `.bat` à porter)
- **Python 3.10+** (stdlib uniquement — aucun `pip install` requis)
- **Node.js** + **npx** (pour les MCPs qui s'installent via `npx -y …`)
- **Claude Code CLI** (`npm install -g @anthropic-ai/claude-code`)

---

## Installation

```cmd
git clone https://git.exemple.lan/erti/claude-dashboard.git C:\claude-workspace
cd C:\claude-workspace
copy .env.local.example .env.local
notepad .env.local              :: renseigne tes secrets
scripts\start-dashboard.bat
```

Puis ouvre http://127.0.0.1:4777/

---

## Le flux `.env.local` → `${VAR}` → `.mcp.json`

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

## Ajouter un workspace

**Via le dashboard** : bouton "+ Nouveau", choisir un template, remplir
label/description/outils.

**Via la ligne de commande** : `scripts\new-workspace.bat` (interactif).

**Manuellement** : voir `AJOUTER-WORKSPACE.md`.

---

## Ajouter un template

1. `cp -r templates/blank templates/mon-template`
2. Éditer `.template.json` (label, description, emoji)
3. Éditer `CLAUDE.md` (utiliser `{{name}}`, `{{label}}`, `{{description}}`,
   `{{tools}}`, `{{date}}`, `{{emoji}}`)
4. Recharger le dashboard — le template apparaît dans le sélecteur.

Détails complets dans `templates/README.md`.

---

## Ajouter un MCP

**Via le dashboard** : MCPs → "+ Nouveau MCP" ou "↧ Importer JSON".

Un import JSON ressemble à :

```json
{
  "mcpServers": {
    "mon-mcp": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@org/mon-mcp"],
      "env": { "API_KEY": "${MON_API_KEY}" }
    }
  }
}
```

Puis dans le panneau de scopes : choisir sur quels workspaces il s'applique.
Les `.mcp.json` concernés sont régénérés immédiatement.

---

## Sécurité

- `.env.local` est dans `.gitignore` dès le départ
- Le serveur bind sur `127.0.0.1` uniquement (jamais exposé au LAN)
- Pas d'auth : il est parti du principe qu'une seule personne accède à la
  machine locale. Si ce n'est pas ton cas, ajoute un reverse-proxy avec auth.
- Les valeurs résolues de `${VAR}` ne quittent jamais le serveur — le
  navigateur voit le placeholder, pas la valeur.

---

## Licence

MIT — fais-en ce que tu veux.
