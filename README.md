# 🌌 Nebula

**Ton tableau de bord pour Claude Code. Tout au même endroit, tout en local.**

Salut 👋

Si tu utilises Claude Code sur plusieurs projets, tu connais sûrement la
chanson : un MCP configuré ici, un token collé là, un `.mcp.json` par
dossier, et au bout d'un mois plus personne ne sait ce qui est branché où.

Nebula est né de cette pagaille. C'est une petite interface web qui tourne
sur ta machine et qui range tout : tes projets, tes MCPs, tes skills, tes
plugins, tes secrets. Tu cliques sur « Lancer » et Claude démarre dans le
bon dossier, avec les bons outils déjà branchés.

Rien ne part sur Internet : pas de compte, pas de télémétrie, juste un
serveur Python sur `127.0.0.1`, sans aucune dépendance à installer.

### Ce que ça change au quotidien

- 🚀 **Un clic pour lancer** un projet, ou reprendre ta dernière session.
- 🔌 **Un seul registre de MCPs**, distribué automatiquement aux projets qui
  en ont besoin. Tu modifies une fois, c'est à jour partout.
- 🔐 **Tes secrets au même endroit**, dans `.env.local`, chiffrables en un
  clic sous Windows. Fini les tokens oubliés dans un commit.
- 🍱 **Des recettes prêtes à l'emploi** pour installer les MCPs courants
  (GitHub, Filesystem, PostgreSQL…) sans fouiller dans les docs.
- 🧩 **Skills, plugins, hooks et permissions** gérés depuis l'interface,
  projet par projet.
- 🔄 **Les mises à jour arrivent toutes seules** : un badge s'allume, un clic
  et c'est fait, sans jamais perdre tes réglages.

---

## 🚀 Installer en 5 minutes

Il te faut :

- **Windows 10/11** (Linux et macOS marchent aussi, cf. plus bas) ;
- **Python 3.10+**, rien d'autre côté Python (sous macOS/Linux, si seul
  `python3` existe, Nebula configure les hooks des modules avec lui) ;
- **Node.js** avec `npx`, pour les MCPs qui s'installent via `npx -y …` ;
- **git**, pour les mises à jour ;
- **Claude Code** : `npm install -g @anthropic-ai/claude-code`.

Puis :

```cmd
git clone https://github.com/spaghiari/Nebula-DashBoard.git C:\claude-workspace
cd C:\claude-workspace
copy .env.local.example .env.local
scripts\start-dashboard.bat
```

Ouvre http://127.0.0.1:4777/ et laisse-toi guider : au premier lancement,
une **visite guidée** (9 étapes, spotlight sur l'interface réelle) te
montre l'essentiel. Tu peux la relancer à tout moment depuis la page Aide.

---

## 🤖 Laisse ton Claude t'installer

Tu préfères être accompagné ? Copie ce message (bouton en haut à droite du
bloc) et colle-le à Claude Code :

````text
Salut Claude ! Je veux installer Nebula, un tableau de bord local pour gérer
mes projets Claude Code : https://github.com/spaghiari/Nebula-DashBoard

Guide-moi pas à pas, une étape à la fois, et attends ma réponse avant de
passer à la suivante. Explique simplement ce que fait chaque commande avant
de la lancer.

1. Vérifie les prérequis sur ma machine : Python 3.10+, Node.js avec npx,
   git, Claude Code. Dis-moi ce qui manque et comment l'installer.
2. Clone le dépôt dans C:\claude-workspace (demande-moi si je préfère un
   autre dossier), puis crée .env.local à partir de .env.local.example.
3. Lance le dashboard (scripts\start-dashboard.bat) et vérifie qu'il
   répond sur http://127.0.0.1:4777/.
4. Si j'utilise déjà Claude Code, aide-moi à récupérer ma config existante
   avec l'assistant d'import du dashboard (Outils > Onboarding).
5. Demande-moi quels MCPs je veux brancher, et aide-moi à les ajouter
   depuis la page MCPs (les recettes en 1 clic quand elles existent).

Règles importantes :
- Mes secrets (tokens, mots de passe, clés API) vont UNIQUEMENT dans
  .env.local, référencés par ${NOM_VARIABLE}. Ne les écris jamais ailleurs
  et ne me demande pas de te les coller dans la conversation : je les saisis
  moi-même dans Outils > Variables d'environnement.
- Ne modifie jamais un .mcp.json à la main : Nebula les régénère depuis son
  registre. On passe toujours par l'interface.
- Si quelque chose échoue, lis l'erreur et explique-moi la cause avant de
  proposer une correction.

Lis d'abord le README.md du dépôt pour comprendre l'outil, puis commence
par l'étape 1.
````

---

## 🌱 Ta première journée avec Nebula

### Créer ou retrouver tes projets

Sur l'**Accueil**, trois façons de faire :

- **+ Nouveau** : un projet tout neuf, à partir d'un modèle (Python, Node,
  audit, automatisation, YAML ou vierge) ;
- **+ Dossier** : tu as déjà un dossier sur le disque, Nebula l'enregistre ;
- **Importer config** : Nebula récupère tes projets et MCPs existants depuis
  ta config Claude Code (`~/.claude.json`, `settings.json`).

### Lancer un projet

Bouton **Lancer** sur la carte du projet : un terminal s'ouvre dans le bon
dossier, `claude` démarre avec le `CLAUDE.md` du projet et ses MCPs déjà
branchés. **Reprendre** relance ta dernière conversation (`claude -c`).

### Brancher un MCP

Page **MCPs** :

- **Recettes** : installation en 1 clic des MCPs courants. Tu peux installer
  la même recette plusieurs fois (`github-perso` et `github-pro`, par
  exemple).
- **+ Nouveau MCP** : formulaire adapté au transport (`stdio`, `http`,
  `sse`), ou onglet **JSON brut** pour coller un bloc trouvé dans un README.
- **Importer** : colle un bloc `{"mcpServers": {...}}` au format Claude Code.

Coche les projets qui doivent en profiter : Nebula écrit leurs `.mcp.json`
pour toi, et les tient à jour à chaque modification.

### Ranger un secret

Ne colle jamais un token directement dans un MCP. À la place :

1. Dans **Outils → Variables d'environnement**, ajoute
   `OPNSENSE_API_KEY=ta-clé`.
2. Dans le MCP, écris `"OPNSENSE_API_KEY": "${OPNSENSE_API_KEY}"`.
3. Nebula remplace `${OPNSENSE_API_KEY}` par la vraie valeur au moment
   d'écrire le `.mcp.json`. Ton navigateur, lui, ne voit jamais que le
   nom de la variable.

Sous Windows, le bouton **Activer le chiffrement** transforme `.env.local`
en coffre DPAPI : illisible depuis un autre compte ou une autre machine,
sans rien changer à ton usage.

Pour aller plus vite partout : **`/`** ou **`Ctrl+K`** ouvre la recherche
globale, et la page **Aide** répond à la plupart des questions.

---

## ✨ Tout ce que Nebula sait faire

Clique sur une section pour la déplier.

<details>
<summary><strong>🗂 Projets, templates, skills et plugins</strong></summary>

- **Workspaces** : création, duplication, export ZIP, lancement et reprise
  de session en un clic. Une suppression s'annule pendant 10 secondes ; la
  purge définitive demande une double confirmation.
- **Templates** : création depuis un modèle avec interpolation `{{name}}`,
  `{{label}}`, `{{description}}`, `{{tools}}`, `{{date}}`, `{{emoji}}`.
  Édition multi-fichiers directement dans l'interface.
- **Overlays** : paquets de fichiers posés *par-dessus* un workspace
  existant, sans jamais rien écraser (cf. « Auto-amélioration » ci-dessous).
- **Skills** : une bibliothèque centrale (`dashboard/data/skills-library/`)
  sert de source de vérité. Tu distribues un skill vers le scope global
  (`~/.claude/skills/`) ou vers un workspace, et Nebula repère les copies
  désynchronisées sans jamais les écraser en silence.
- **Plugins** : navigateur de marketplace (officiel et externes, avec
  README), installation en un clic, activation projet par projet (Actif /
  Inactif / Hériter) et actions de masse.
- **Sessions** : la liste de tes conversations passées par workspace, avec
  un aperçu des premiers messages au survol.
- **Hooks et permissions** : éditeur graphique pour les `settings.json`
  global et local.

</details>

<details>
<summary><strong>🍱 Recettes MCP</strong></summary>

**Catalogue embarqué** : 📁 Filesystem · 🐙 GitHub · 🔍 Brave Search ·
🌐 Fetch HTTP · 🧠 Memory · 🎭 Puppeteer · 🐘 PostgreSQL · 💬 Slack.
Servi depuis `dashboard/data/mcp_recipes.json`, mis à jour avec Nebula.

**Recettes perso** : pour tes MCPs maison (firewall interne, base de
données perso, script local), le bouton **+ Nouvelle recette** ouvre un
éditeur complet : métadonnées, transport, paramètres avec cases `secret` et
`required`. Elles restent chez toi, dans
`dashboard/data/mcp_recipes.local.json` (jamais versionné).

**Installations multiples** : une recette s'installe autant de fois que tu
veux (`opnsense-prod` et `opnsense-staging`, `pg-local` et `pg-prod`…). L'id
est suffixé automatiquement, et tu peux le renommer.

**Transformer un MCP en recette** : sur un MCP qui marche, **Modifier →
✨ Sauver comme recette**. Chaque variable d'environnement devient un
paramètre, et celles qui ressemblent à un secret (`token`, `key`,
`password`…) sont masquées d'office.

</details>

<details>
<summary><strong>🧠 Auto-amélioration de Claude (optionnel)</strong></summary>

L'overlay **`claude-self-improving`** s'applique depuis la carte d'un
workspace. Il ne remplace aucun fichier existant (le `CLAUDE.md` reçoit
juste un fragment délimité par des marqueurs) et installe une boucle qui
aide Claude à apprendre de ton projet :

- une **mémoire structurée** dans `.claude/memory/` (architecture,
  conventions, pièges, sécurité…) ;
- un **pipeline d'amélioration** : `improvements.md`, et en installation
  complète `ideas.md`, `backlog.md`, `roadmap.md` et des digests ;
- des **agents, slash commands et hooks pré-commit** en Python portable.

Tu choisis le mode (`solo`, `équipe`, `équipe-hiérarchique`) et la
profondeur (`minimale` ou `complète`). Réappliquer l'overlay ne touche
qu'aux fichiers manquants.

<!-- claude-team -->
L'overlay **`claude-team`** (qui requiert le précédent) ajoute une **équipe
de 7 agents** générés depuis `.claude/team.json` : orchestrateur,
chercheur, architecte, exécutant, relecteur, évaluateur et critique, avec un
modèle choisi par rôle. Il apporte aussi une **boucle d'amélioration
mesurée** : un jeu d'évals verrouillé, `/eval`, `/improve` (un seul
changement par itération, gardé seulement s'il gagne au moins 0,02 sans
régression) et `/eval-add`. Scores et journal sont visibles dans l'onglet
« Amélioration » du workspace.

Un **routage always-on** oriente chaque demande vers le bon agent. Il est
livré en mode `auto`, avec une relecture systématique par le relecteur
(modèle opus) : c'est le plus complet, mais aussi le plus gourmand en
tokens. Sur la ligne du module, dans l'onglet Configuration du workspace,
tu peux passer le routage en « assisté » (suggestions seulement) ou
« manuel », et la relecture du code en « dès 3 fichiers » ou « jamais ».
<!-- /claude-team -->

</details>

<details>
<summary><strong>🎨 Confort : thèmes, raccourcis, aide intégrée</strong></summary>

**5 thèmes**, mémorisés côté serveur :

| Thème | Style |
|---|---|
| Nebula | Sombre · violet et ocre (défaut) |
| Nebula clair | Clair · violet profond |
| Marine | Sombre · bleu profond |
| Solarized | Sombre · cyan et ambre, reposant pour les yeux |
| Cuivre | Sombre · bronze chaleureux |

**Raccourcis clavier** :

| Touche | Action |
|---|---|
| `/` ou `Ctrl+K` | Recherche globale |
| `g` puis `h/m/p/k/t/o/a` | Aller à Accueil / MCPs / Plugins / Skills / Templates / Outils / Aide |
| `n` | Nouveau workspace |
| `m` | Nouveau MCP |
| `s` | Synchroniser tous les workspaces |
| `Ctrl+S` | Sauvegarder (éditeurs) |
| `Esc` | Fermer une fenêtre ou la recherche |

**Pour t'aider** : une page Aide en 9 thèmes, la visite guidée, et une
checklist de mise en route (Outils → Démarrage) affichée sur l'Accueil tant
qu'elle n'est pas terminée.

</details>

<details>
<summary><strong>🔄 Mises à jour automatiques</strong></summary>

Nebula vérifie les nouveautés au démarrage puis toutes les 30 minutes. Quand
il y en a, un badge **« X MAJ »** s'allume en haut de l'écran. Un clic
affiche la liste des changements et le bouton **Appliquer la mise à jour**.
Nebula te dit ensuite s'il suffit de rafraîchir la page ou s'il faut
redémarrer le serveur.

**Tes réglages ne sont jamais perdus** : avant chaque mise à jour, tes
modifications locales sont mises de côté (`git stash`), puis remises en
place après. Si un vrai conflit survient, elles restent sauvegardées dans
la pile de stash.

| Situation | Ce que fait Nebula |
|---|---|
| Fichiers modifiés ou supprimés en local | Mis de côté puis restaurés |
| Fichiers non suivis qui gêneraient | Mis de côté eux aussi |
| Verrou git orphelin (plus de 60 s) | Retiré automatiquement |
| Historique divergent | Bouton « Réinitialiser à la version distante » |
| Réseau, authentification, disque plein | Message clair sur la cause |

En dernier recours, **Réinitialiser à la version distante** réaligne ton
installation (avec une sauvegarde préalable). Tes données (registre MCP,
workspaces, `.env.local`, mémoire perso) ne sont pas versionnées et ne
bougent pas.

</details>

<details>
<summary><strong>🛠 Ménage dans ta config Claude existante</strong></summary>

Si un même MCP est déclaré à la fois dans ta config Claude globale
(`~/.claude.json`, `~/.claude/settings.json`) et dans Nebula, ça marche,
mais c'est fragile. La page MCPs affiche alors un bandeau jaune. **Examiner**
te propose :

- pour les **doublons** : les retirer de la config globale (Nebula reste la
  référence, une sauvegarde `.bak` est créée) ;
- pour les **orphelins** (présents seulement côté Claude) : les migrer dans
  Nebula en un coup, ou les supprimer s'ils sont obsolètes.

</details>

---

## 🛡 Tes données restent chez toi

- Le serveur n'écoute que sur `127.0.0.1` : personne d'autre sur le réseau
  n'y accède.
- `.env.local`, le registre MCP, tes workspaces et tes `.mcp.json` ne sont
  jamais versionnés.
- Les secrets résolus ne quittent jamais le serveur : le navigateur ne voit
  que les noms des variables.
- Une sauvegarde `.bak` est faite avant chaque écriture destructive.

<details>
<summary><strong>Détail technique</strong></summary>

- Pas d'authentification : Nebula part du principe que la machine est à
  toi seul.
- En-tête anti-CSRF `X-Nebula-XHR` exigé sur les routes sensibles (valeurs
  des variables, chiffrement) ; contrôle anti DNS-rebinding sur l'en-tête
  `Host`.
- Validation `safe_id` (`[a-zA-Z0-9_-]{1,40}`) partout, chemins vérifiés
  par `Path.relative_to()` contre le path traversal.
- Sous-processus sans `shell=True`, arguments en liste, UTF-8 explicite,
  timeouts.
- Corps de requête plafonné à 10 Mo ; verrou `_MUTATION_LOCK` réentrant pour
  les écritures concurrentes.
- Chiffrement DPAPI optionnel de `.env.local` (Windows), avec ACL stricte
  `icacls` (toi et SYSTEM uniquement). **Désactiver / Exporter clair**
  récupère une copie en clair pour une migration.

</details>

---

## 📚 Référence technique

<details>
<summary><strong>🗂 Architecture</strong></summary>

```
claude-workspace/
├── CLAUDE.md                    # Contexte global chargé par Claude Code
├── .env.local.example           # Modèle des secrets
├── .env.local                   # ← LOCAL, gitignored
│
├── dashboard/                   # Le dashboard web
│   ├── server.py                # Serveur Python stdlib + routes
│   ├── index.html               # Squelette SPA
│   ├── app.css                  # Design system : tokens (thèmes) + composants
│   ├── css/                     # redesign.css, shell-mobile.css, editor-matrix.css, sessions.css
│   ├── app.js                   # SPA vanilla JS
│   ├── dashcore/                # Backend modulaire
│   │   ├── config.py            # Constantes et chemins
│   │   ├── helpers.py           # I/O, validation, fichiers
│   │   ├── env_local.py         # Gestion de .env.local + ${VAR}
│   │   ├── env_crypto.py        # Chiffrement DPAPI + ACL stricte
│   │   ├── journal.py           # Journal markdown
│   │   ├── workspace_io.py      # Chemins des workspaces, stats, sanity check
│   │   ├── active_sessions.py   # Sessions Claude Code actives
│   │   ├── api_workspaces.py    # Workspaces, templates, settings
│   │   ├── api_overlays.py      # Overlays
│   │   ├── api_team.py          # Module claude-team : agents, boucle d'amélioration
│   │   ├── api_files.py         # Explorateur de fichiers
│   │   ├── api_mcps.py          # MCPs, conflits, scan, sync, recettes
│   │   ├── api_plugins.py       # Plugins, skills, agents, commandes
│   │   ├── api_skills_library.py # Bibliothèque de skills centralisée
│   │   ├── api_ui_state.py      # Thème + onboarding côté serveur
│   │   ├── data_migration.py    # Migration vers NEBULA_DATA_DIR
│   │   └── system_update.py     # Mises à jour automatiques
│   ├── tests/                   # Tests unittest stdlib
│   └── data/                    # Déplaçable via NEBULA_DATA_DIR (sauf mcp_recipes.json)
│       ├── workspaces.json      # ← LOCAL, gitignored
│       ├── ui_state.json        # ← LOCAL, gitignored
│       ├── skills-library/      # Bibliothèque de skills
│       ├── mcp_recipes.json     # Recettes MCP publiques
│       └── mcp_recipes.local.json # ← LOCAL, gitignored
│
├── mcp/
│   ├── registry.json            # ← LOCAL, gitignored (registre unique)
│   └── configs/                 # Exemples de configs
│
├── memory/                      # Mémoire chargée via @import
│   ├── profil.md, stack.md, conventions.md, global.md
│   └── snippets/
│
├── scripts/
│   ├── start-dashboard.bat      # Lance le serveur
│   ├── new-workspace.bat        # Création rapide en ligne de commande
│   ├── launch-TEMPLATE.bat      # Modèle (les launch-<id>.bat sont gitignored)
│   ├── statusline.py            # Statusline Claude Code
│   └── update-memory.bat        # Édite memory/global.md
│
├── templates/                   # Templates et overlays
│   ├── blank/, dev-python/, dev-node/, audit/, automation/, config-yaml/
│   ├── claude-self-improving/   # Overlay d'auto-amélioration
│   └── README.md
│
└── workspaces/                  # ← LOCAL, gitignored
    └── <ton-projet>/
        ├── CLAUDE.md
        ├── .mcp.json            # Généré par Nebula
        └── .claude/             # settings.json, skills/, agents/, commands/
```

</details>

<details>
<summary><strong>⚙️ Variables d'environnement</strong></summary>

Toutes optionnelles.

| Variable | Défaut | Rôle |
|---|---|---|
| `NEBULA_PORT` | `4777` | Port d'écoute (`--port` prime ; valeur invalide = avertissement + défaut) |
| `NEBULA_HOST` | `127.0.0.1` | Hôte d'écoute (`--host` prime). Hors boucle locale : **avertissement au démarrage**, l'API n'a pas d'authentification |
| `NEBULA_ALLOWED_HOSTS` | (vide) | Noms supplémentaires acceptés dans l'en-tête `Host` (ex. `nas.lan`, **sans port**), séparés par des virgules |
| `NEBULA_DATA_DIR` | `dashboard/data` | Dossier des données utilisateur. Au 1er lancement sur un dossier vide, les données existantes y sont **copiées** (jamais d'écrasement) ; dossier déjà utilisé : `python server.py --migrate-data` recopie seulement les fichiers manquants |
| `ATELIER_ROOT` | parent de `dashboard/` | Racine de l'installation (registre MCP, templates, workspaces, `.env.local`) |

Le contrôle anti DNS-rebinding accepte toujours `127.0.0.1` et
`localhost`, plus l'hôte configuré (sauf `0.0.0.0` / `::`) et
`NEBULA_ALLOWED_HOSTS`. Pour un accès à distance, préfère un tunnel SSH
(`ssh -L 4777:127.0.0.1:4777 poste`) à une écoute réseau.

</details>

<details>
<summary><strong>🐧 Linux / macOS</strong></summary>

```sh
cd claude-workspace/dashboard
python3 server.py              # ou : NEBULA_PORT=4800 python3 server.py --no-browser
```

Tout le pilotage fonctionne (workspaces, MCPs, skills, plugins,
`.env.local` en clair). Restent propres à Windows, avec une erreur
explicite (HTTP 501) : le lancement d'une session dans une console `cmd`,
et l'ouverture d'un fichier si `xdg-open` / `open` est absent. Le
chiffrement DPAPI n'existe pas hors Windows.

</details>

<details>
<summary><strong>📚 Exemples de MCPs</strong></summary>

Exporte ta config depuis **MCPs → Importer / exporter → Copier** (format
Claude `mcpServers`, sans secret résolu), ou colle l'un de ces exemples dans
**MCPs → Importer**. Les `${VAR}` se définissent dans `.env.local`.

**📁 filesystem** : accès fichiers limité à un dossier

```json
"filesystem": {
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-filesystem", "C:\\claude-workspace\\workspaces"]
}
```

**🏠 Home Assistant**

```json
"homeassistant": { "type": "http", "url": "${HA_MCP_URL}" }
```

Variables attendues par quelques MCPs courants :

```env
# 🛡 opnsense : pilotage du firewall
OPNSENSE_URL=https://opnsense.exemple.lan:4443
OPNSENSE_API_KEY=...
OPNSENSE_API_SECRET=...

# 🔀 n8n : workflows via supergateway
N8N_URL=https://n8n.exemple.lan
N8N_TOKEN=eyJhbGci...

# 📖 wikijs : Wiki.js en lecture et écriture
WIKIJS_API_URL=https://wiki.exemple.com
WIKIJS_TOKEN=eyJhbGci...

# 🔬 binary-ninja : reverse engineering
BINJA_MCP_URL=http://127.0.0.1:42069
BINJA_MCP_KEY=binja-codemode-local
BINJA_MCP_SCRIPT=C:/path/to/mcp_bridge.py

# 🐞 x64dbg : debugger via script Python
X64DBG_PYTHON=C:/path/to/python.exe
X64DBG_SCRIPT=C:/path/to/x64dbg_mcp.py
```

</details>

<details>
<summary><strong>🧱 Ajouter un workspace ou un template à la main</strong></summary>

**Workspace** : bouton *+ Nouveau* du dashboard, `scripts\new-workspace.bat`
en ligne de commande, ou à la main en suivant `AJOUTER-WORKSPACE.md`.

**Template** :

1. `cp -r templates/blank templates/mon-template`
2. Édite `.template.json` (label, description, emoji)
3. Édite les fichiers en utilisant les placeholders
4. Recharge le dashboard

Ou depuis l'interface : **Templates → Éditer** ouvre un éditeur
multi-fichiers (`Ctrl+S` pour sauvegarder). Détails dans
`templates/README.md`.

</details>

<details>
<summary><strong>🧪 Tests</strong></summary>

```sh
python -m unittest discover -s dashboard/tests
```

Stdlib uniquement, en bac à sable (aucune donnée réelle lue ni écrite),
sous Windows comme sous Linux. Détail et couverture :
[`dashboard/tests/README.md`](dashboard/tests/README.md).

</details>

<details>
<summary><strong>🧰 Pour le mainteneur : publier une version</strong></summary>

Le développement se fait dans une installation de travail, puis le code
est copié dans un export propre (sans données perso), validé et poussé sur
`main`. Les utilisateurs reçoivent la mise à jour automatiquement.

```cmd
cd C:\claude-workspace-export
:: copier les fichiers modifiés depuis l'installation de travail
python ..\claude-workspace\dashboard\tools\preflight.py
git status --porcelain
git commit -am "fix(scope): message"
git push origin main
git push github main
```

</details>

---

## 💬 Un souci, une idée ?

Nebula grandit avec ceux qui l'utilisent. Si quelque chose coince, ou si
une idée te passe par la tête, ouvre une
[issue sur GitHub](https://github.com/spaghiari/Nebula-DashBoard/issues).
Elle sera lue avec plaisir. Bonne route avec Claude ✨

## 📄 Licence

MIT : fais-en ce que tu veux.
