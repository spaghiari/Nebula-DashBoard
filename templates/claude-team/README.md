# Module Nebula `claude-team` - équipe d'agents et amélioration mesurée

Overlay (module) Nebula qui se pose par-dessus un workspace déjà équipé de
`claude-self-improving`. Il ajoute :

- **une équipe de 7 agents Claude Code** générés depuis un manifeste
  (`.claude/team.json`) : orchestrateur, chercheur, architecte,
  exécutant, relecteur, évaluateur, critique, chacun avec un modèle
  (sonnet / opus), des outils dérivés de ses capacités et des
  contraintes d'exécution ; préfixe des noms choisi à l'activation ;
- **`/team <objectif>`** : le fil principal joue l'orchestrateur et
  délègue aux agents générés ;
- **une boucle d'amélioration mesurée** : jeu d'évals verrouillé (un cas
  = un agent, un critère observable), un seul changement par itération
  proposé par le critique, re-mesure, acceptation seulement si gain
  >= 0,02 et zéro régression, journal JSONL, un commit par itération
  acceptée.

## Positionnement

| Module | Répond à |
|---|---|
| `claude-self-improving` | **Quoi retenir, comment trier** : mémoire structurée, registres (ideas, backlog, improvements), conventions, hooks de commit. |
| `claude-team` (ce module) | **Qui fait quoi, et comment prouver qu'un changement est une amélioration** : équipe d'agents avec routage de modèle, évals figées, boucle mesurée. |

Le pont : le critique lit les items `[TODO]` de `.claude/improvements.md`
comme hypothèses ; une itération acceptée par `/improve` écrit l'item en
`[DONE]` avec score avant/après et commit ; une itération rejetée le passe
en `[ABANDONED]` avec la mesure.

Cohabitation avec les agents du module Auto-amélioration : si
`.claude/agents/` contient `*-expert`, c'est lui l'exécutant des tâches
conséquentes (feature M+, 10 fichiers ou plus, multi-domaines, refactor
à effets de bord) ; `<préfixe>-executor` exécute les tâches S et les
étapes atomiques ; `*-impl-validator` complète `<préfixe>-reviewer`
(après lui, jamais à sa place).

## Contenu

```
.nebula-overlay.json                      marker (requires, features, settings_patch, generators)
CLAUDE.claude-team.md                     fragment always-on appendé au CLAUDE.md du workspace
.claude/team.json                         manifeste (source de vérité, signature du module, team.prefix)
.claude/team/agents/<id>.md               corps des 7 agents (sans frontmatter)
.claude/evals/eval-set.jsonl              jeu de démarrage : 6 cas génériques (discipline des 7 rôles)
.claude/evals/holdout.jsonl               jeu caché : 2 cas (jamais vu par la boucle)
.claude/evals/README.md                   schéma d'un cas (agent, grader, check, target, scope, runs), verrou, /eval-add
.claude/journal/changes.jsonl             journal des itérations (vide au départ)
.claude/hooks/evals-lock.py               PreToolUse : refuse les écritures sous .claude/evals/
.claude/hooks/team-router.py              UserPromptSubmit : injecte le routage suggéré selon routing.mode
.claude/commands/{team,eval,improve,eval-add}.md
.claude/memory/conventions/improvement-loop.md
.claude/memory/subsystems/claude-team.md
```

À l'activation, Nebula génère en plus `.claude/agents/<préfixe>-<id>.md`
pour chaque agent (frontmatter Claude Code `name`, `description`, `model`,
`tools` + bloc « Contraintes d'exécution » + corps), écrit le préfixe
dans `.claude/team.json` (`team.prefix`) et fusionne les entrées des hooks
`evals-lock.py` (PreToolUse `Edit|Write|MultiEdit` et `Bash`) et
`team-router.py` (UserPromptSubmit, sans matcher) dans
`.claude/settings.json`.

### Hooks livrés (`.claude/hooks/`)

Python stdlib, `python "${CLAUDE_PROJECT_DIR}/.claude/hooks/<x>.py"`,
stdin lu en UTF-8 explicite, stdout / stderr reconfigurés en UTF-8,
fail-open (fichier manquant ou illisible = exit 0 sans sortie). Le README
`.claude/hooks/README.md` du workspace est posé par `claude-self-improving`
et ne connaît pas ces deux hooks : leur doc est ici.

| Hook | Événement | Rôle |
|---|---|---|
| `evals-lock.py` | PreToolUse `Edit\|Write\|MultiEdit`, `Bash` | exit 2 (refus) sur toute écriture sous `.claude/evals/` tant que `improvement_loop.eval_set_locked` est vrai, sauf `"evals_unlocked": true` dans `.claude/settings.local.json` |
| `team-router.py` | UserPromptSubmit | classe le prompt (question / conception / implementation / relecture / inconnu) et injecte UNE ligne de contexte `[équipe claude-team] routage auto : ...` (JSON `hookSpecificOutput.additionalContext`) ; silencieux en mode `manuel`, sans section `routing`, ou sur une slash command |

## Always-on : routage automatique

L'utilisateur parle normalement ; le fil principal route vers les agents
sans appel explicite et rend **une** réponse, sourcée et relue. Trois
couches, toutes lues depuis `.claude/team.json` :

1. **Table de routage** dans le fragment `CLAUDE.md` (§ « Routage
   automatique (always-on) ») : question -> `<p>-researcher` (sonnet,
   sources `fichier:ligne`) ; conception -> `<p>-architect` (opus) ; tâche
   S -> `<p>-executor` puis **relecture aveugle `<p>-reviewer`** ; feature
   M+ -> `*-expert` (cohabitation inchangée) puis reviewer puis
   `*-impl-validator` ; relecture -> `<p>-reviewer` ; ambigu ou
   multi-étapes -> `/team` ; jamais `<p>-critic` ni `<p>-evaluator`.
   Règles : gate reviewer, sortie unifiée (pied `équipe : ...`), budget
   sonnet-first.
2. **Déclencheurs** : chaque agent du manifeste porte `auto: true|false`
   et `triggers: [...]` ; la description générée se termine par « À
   utiliser automatiquement quand : <déclencheurs> » (ou « Jamais en
   routage automatique : réservé à /eval et /improve »). C'est ce que
   Claude Code lit pour déléguer de lui-même ; le bloc « Contraintes
   d'exécution » reçoit une ligne « Routage ».
3. **Hook `team-router.py`** (UserPromptSubmit) : routage déterministe par
   regex, une ligne de contexte par prompt selon le mode.

Modes (`routing.mode`, défaut `auto`) :

| Mode | Fil principal | Hook |
|---|---|---|
| `manuel` | délègue seulement sur `/team` ou demande explicite | silencieux |
| `assiste` | suit la suggestion injectée sauf raison explicite | `suggestion : ...` |
| `auto` | applique la table sans qu'on le lui demande | `routage auto : ...` |

`routing.review_gate` : `always` (défaut, tout code livré est relu),
`from_3_files`, `never`. `routing.budget` : `sonnet-first`. Le mode et la
gate se changent depuis Nebula (onglet Configuration, ligne du module :
sélecteurs « Routage » et « Relecture du code », pill d'état dans
l'en-tête) ou par `POST /api/workspaces/<id>/team/routing`
(`{"mode": ..., "review_gate": ...}`) ; aucune régénération des agents.

**Rétro-compatibilité** : un workspace activé avant le routage a un
`team.json` sans section `routing` : mode effectif `manuel`, déclencheurs
vides, descriptions inchangées, pill « Routage non déclaré ». La
ré-application ne recopie pas un `team.json` déjà présent : le bouton
« Activer le routage » de la ligne du module (ou `POST .../team/routing`
avec `mode: auto`) écrit la section par défaut complète. La
ré-application met à jour le bloc `CLAUDE.md` (§ Routage) et pose le hook
`team-router.py` avec son entrée `UserPromptSubmit` dans `settings.json`
(cf. § Idempotence) ; reste à reporter `auto` / `triggers` dans
`team.json` puis « Régénérer » les agents pour obtenir les descriptions
à déclencheurs.

## Activation

Depuis Nebula : onglet Configuration du workspace (le prérequis
`claude-self-improving` doit être actif, la modale propose de l'activer
d'abord), ou case à cocher à la création d'un workspace (coche et
verrouille le prérequis), ou page Templates § Modules. La modale permet
de choisir le **préfixe des agents** (défaut : id du workspace ; ex.
`dash` pour obtenir `dash-orchestrator` à côté de `dash-expert` ; règle
`^[a-zA-Z0-9_-]{1,40}$`), le modèle par rôle (sonnet / opus / haiku)
et, en ré-application, de régénérer les agents générés. Une
ré-application sans préfixe relit celui mémorisé.

Payload de `POST /api/workspaces/<id>/overlays/claude-team` : `prefix`,
`models` ({agent: alias}), `default_model`, `regenerate`. Routage :
`POST /api/workspaces/<id>/team/routing` (`mode`, `review_gate`), état
dans `GET /api/workspaces/<id>/team` (`routing`, et `auto` / `triggers`
par agent) et dans l'entrée du module de `GET /api/workspaces/<id>/overlays`.

Ensuite, dans Claude : `/team <objectif>` pour une tâche orchestrée,
`/eval` pour la baseline, `/improve` pour une itération, `/eval-add`
pour transformer un échec observé en cas d'éval.

## Topologie d'exécution

- `/team` : le **fil principal** applique le corps de l'orchestrateur et
  délègue aux agents générés. L'agent `<préfixe>-orchestrator` reste
  généré pour la délégation explicite.
- `/eval` : le **fil principal** boucle sur les cas, délègue chaque
  `input` à l'agent visé, calcule lui-même `test` / `regex` / `exact`,
  fait noter `rubric` par `<préfixe>-evaluator` **en aveugle** (sortie +
  attendu + grille seulement). L'évaluateur note, il n'orchestre rien.
- `config_version` = empreinte sha1 courte de `.claude/team.json` +
  `.claude/team/agents/*.md` + agents générés, calculée par un one-liner
  stdlib donné dans la commande et, avec le même algorithme, par Nebula
  (`team_config_hash`). L'onglet « Amélioration » dit si la baseline du
  journal est **à jour** ou **périmée**.
- `/improve` réutilise la baseline du journal si l'empreinte est
  inchangée et sans cas inexécutable ; lancer `/improve` vaut demande
  explicite de commit pour ses itérations acceptées
  (`update(<préfixe>): improve/<n> - <hypothèse>`), jamais de push.

## Mapping capacités -> outils Claude Code

| Capacité | Outils |
|---|---|
| `filesystem` | Read, Glob, Grep (+ Edit, Write si l'agent n'est pas `read_only`) |
| `code_exec` | Bash |
| `repo` | Bash (git) |
| `web_search` | WebSearch, WebFetch |
| `knowledge` | Read, Grep (mémoire `.claude/memory/`) |
| `eval_runner` | Bash, Read |

Le point d'entrée (`team.entrypoint`) reçoit en plus `Agent` (il délègue).
`max_turns`, `isolation: blind`, `escalate_to`, `temperature: 0` et
`scope: improvement_loop_only` n'ont pas d'équivalent natif : ils
deviennent des règles dans le bloc « Contraintes d'exécution » du corps
généré. Table dans `dashcore/config.py` (`CAPABILITY_TOOLS`).

## Idempotence

Ré-appliquer le module copie les fichiers absents et **met à jour les
fichiers gérés** (`managed` du marker : `.claude/hooks/*.py`, les quatre
commandes `/team`, `/eval`, `/improve`, `/eval-add`)
ainsi que le bloc `claude-team` du `CLAUDE.md` (`refresh_block`), quand ils diffèrent de la
version du module ; l'ancienne version est sauvegardée en
`<nom>.<AAAAMMJJ-HHMMSS>.bak`. C'est ainsi qu'un correctif du module
(ex. `team-router.py`) parvient à un workspace déjà équipé. Relancer
Claude Code ensuite. Ne sont jamais réécrits : `team.json`,
`team/agents/*.md` (édités par `/improve`), `evals/**`, `journal/**`,
`memory/**` (enrichie par Claude au fil du projet).
Elle n'écrase jamais un autre fichier utilisateur, ne duplique pas l'entrée de hook, ne
réécrit `team.prefix` que s'il change, et ne réécrit un agent généré que
sur demande explicite (« Régénérer »), et seulement s'il porte encore le
marqueur `<!-- generated by nebula claude-team -->`.
