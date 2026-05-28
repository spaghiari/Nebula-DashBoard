# Template projet Claude — auto-amélioration, mémoire structurée, digests hiérarchiques

Squelette de projet pour utiliser Claude Code (ou Claude au sens
large) comme partenaire principal de développement, avec une mémoire
projet structurée, un système d'auto-amélioration continu, et un
mécanisme de digests hebdomadaires verticaux pour les projets
d'équipe avec hiérarchie.

Inspiré du projet AstreinteManager (i-TRACING) après refactorisation
4.7.0+ pour usage générique.

## Ce que ce template fournit

### 5 registres versionnés (`.claude/`)

| Registre | Rôle |
|---|---|
| `ideas.md` | Funnel pré-engagement (idées produites par Claude, à trier) |
| `backlog.md` | Actions différées court/moyen terme (P0/P1/P2) |
| `roadmap.md` | Vision long terme + axes + jalons |
| `improvements.md` | Auto-amélioration des outils Claude eux-mêmes |
| `digests/` | **5ème registre** : synthèses hebdomadaires verticales (mode équipe) |

### Pipeline d'auto-amélioration 4 stages

`IDEAS → VALIDATED → IN PROGRESS → DONE`, avec cristallisation des
patterns en mémoire centrale au passage DONE.

### Mémoire `hub-and-spoke` (`.claude/memory/`)

11 hubs thématiques (overview, domain, architecture, security,
frontend, subsystems, performance, conventions, pitfalls,
diagnostics, claude-tooling), chacun pouvant accueillir des spokes
détaillés dans un sous-dossier homonyme quand le contenu grossit.

### Doctrines de pilotage (`.claude/memory/conventions/`)

13 fichiers de doctrine qui codifient :
- le pipeline d'auto-amélioration (`pipeline.md`)
- l'auto-enrichissement de la mémoire (`memory-enrichment.md`)
- la classification mémoire user-locale vs projet (`memory-classification.md`)
- l'auto-amélioration des outils Claude (`self-improvement.md`)
- la production proactive d'idées (`ideas-generation.md`)
- le cycle de vie des items DONE (`done-lifecycle.md`)
- la mesure d'effort humain vs IA (`effort-sizing.md`)
- la délégation multi-agent (`multi-agent.md`)
- la parallélisation (`parallelization.md`)
- la gestion du backlog et de la roadmap (`backlog.md`, `roadmap.md`)
- la maintenance des outils (`commands-and-hooks.md`)
- **la production de digests hebdomadaires (`digests.md`)** — nouveau

### Outillage Claude Code

- 3 templates de sous-agents : expert, impl-validator, pitfall-auditor
- 1 template de sous-agent pour mode équipe : digest-compiler
- 7+ slash commands génériques : `/pipeline`, `/brainstorm`,
  `/self-review`, `/diff-review`, `/feature-start`, `/readme-sync`,
  `/check-all`, `/digest-week`
- 6 hooks pre/post-commit et stop, **en Python stdlib** (portables
  Windows/Unix, aucun bash requis) : em-dash, co-authored-by,
  improvements-validate, protect-local-files, remind-check-all,
  statusline. Câblés via `python "${CLAUDE_PROJECT_DIR}/.claude/hooks/X.py"`.

### Attribution d'auteur

Tous les items des 5 registres portent l'auteur via `par <author>`.
En mode équipe, le hook `improvements-validate.sh` valide la
présence du champ au commit.

## Bootstrap d'un nouveau projet

1. **Cloner** le template dans le dépôt du nouveau projet :
   ```bash
   git clone <template-repo> {{label}}
   cd {{label}}
   rm -rf .git
   git init
   ```

2. **Remplacer les placeholders** dans tous les fichiers :
   - `{{label}}` → nom du projet (par exemple `astreintemanager`,
     `cmdb`, ...)
   - `{{name}}-` → préfixe court pour agents et identifiants (par
     exemple `am-`, `cmdb-`, ...)

   Commande type (à adapter selon plateforme) :
   ```bash
   find . -type f \( -name '*.md' -o -name '*.json' -o -name '*.sh' \) \
       -not -path './.git/*' -exec sed -i \
       -e 's/{{label}}/monprojet/g' \
       -e 's/{{name}}-/mp-/g' {} \;
   ```

3. **Activer les agents** en renommant les `.md.example` :
   ```bash
   cd .claude/agents
   for f in slug-*.md.example; do
       mv "$f" "${f%.example}"
       # Puis remplacer 'slug-' par '<vrai-slug>-' dans le nom de fichier
   done
   ```

4. **Compléter `memory/overview.md`** avec les décisions de
   bootstrap :
   - Cocher le **mode projet** (solo / équipe / équipe avec
     hiérarchie)
   - Cocher l'**identité auteur** (`git config user.name` court,
     initiales, etc.)
   - Cocher la **langue projet**

5. **Mode projet** : si l'overlay est appliqué via Nebula (bouton
   « Activer »), le mode choisi dans la modale écrit automatiquement
   `.claude/settings.local.json` (`validate_author: false` en solo),
   pré-coche le mode + la langue dans `overview.md`, filtre les
   fichiers mode-gated (digests/digest-week/digest-compiler =
   équipe-hiérarchique uniquement) et seed les exemples en profondeur
   complète. En bootstrap manuel : créer `.claude/settings.local.json`
   avec `{"validate_author": false}` pour le mode solo.

6. **Compléter les hubs mémoire** au fil du travail :
   `domain.md`, `architecture.md`, etc. selon les besoins.

7. **Créer les fichiers de conventions spécifiques** à la stack du
   projet :
   - `memory/conventions/git.md`
   - `memory/conventions/<langage>.md`
   - `memory/conventions/testing.md`
   - `memory/conventions/playbooks.md`
   - `memory/conventions/commands.md`
   - `memory/conventions/hooks.md`

8. **Ajouter les hooks projet-spécifiques** (lint syntaxique selon
   stack) dans `.claude/hooks/` (en Python stdlib, comme les 6 hooks
   fournis) et les câbler dans `.claude/settings.json` via
   `python "${CLAUDE_PROJECT_DIR}/.claude/hooks/X.py"`. Prérequis
   runtime : `python` dans le PATH (cf. `.claude/hooks/README.md`).

9. **Commit initial** :
   ```bash
   git add .
   git commit -m "feature(bootstrap): template projet Claude initialisé"
   ```

## Modes projet

| Mode | Auteur dans registres | Registre digests | Hook validate_author |
|---|---|---|---|
| Solo | implicite (peut être omis) | inactif | `false` |
| Équipe sans hiérarchie | **obligatoire** | inactif ou optionnel | `true` |
| Équipe avec hiérarchie | **obligatoire** | **actif** | `true` |

Le mode peut évoluer (par ex. solo → équipe à l'embauche d'un second
contributeur) - documenter le changement comme post-mortem.

## Lecture conseillée

Dans l'ordre, pour comprendre le système :

1. `CLAUDE.md` (entrée always-on)
2. `.claude/memory/conventions/pipeline.md` (le flux 4 stages)
3. `.claude/memory/conventions/digests.md` (le 5ème registre)
4. `.claude/memory/conventions/memory-classification.md` (test à 3
   questions)
5. `.claude/memory/conventions/memory-enrichment.md` (auto-enrichissement)
6. `.claude/memory/conventions/done-lifecycle.md` (cristallisation)
7. `.claude/memory/conventions/effort-sizing.md` (barème + ratio
   humain/IA)
