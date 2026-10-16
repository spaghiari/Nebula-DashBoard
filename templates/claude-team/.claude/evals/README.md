# Évals - `{{label}}`

Jeu d'évals **figé** de la boucle d'amélioration mesurée (module
`claude-team`). On n'améliore que ce qu'on mesure : chaque itération de
`/improve` est scorée contre ces cas, et gardée seulement si elle fait
mieux sans rien casser.

## Fichiers

| Fichier | Rôle |
|---|---|
| `eval-set.jsonl` | Jeu principal, une ligne JSON par cas. Lu par `/eval` et `/improve`. |
| `holdout.jsonl` | Jeu caché (~20 % des cas). **Jamais** utilisé par la boucle ; à vérifier à la main de temps en temps pour détecter le surapprentissage. |

## Format d'un cas

```json
{"id": "case-001", "agent": "researcher", "input": "...", "expected": "...", "grader": "test|regex|exact|rubric", "check": "<commande shell (test) | motif Python (regex)>", "target": "output|diff|file:<chemin>", "scope": "<dossier>", "runs": 1, "rubric": "...", "tags": ["..."]}
```

| Champ | Contenu |
|---|---|
| `id` | Identifiant stable (`case-NNN`, `hold-NNN` pour le jeu caché). Jamais réutilisé. |
| `agent` | Id d'agent du manifeste visé par le cas (défaut `orchestrator`). Le cas mesure **cet agent seul**, invoqué avec `input` ; pas l'équipe entière. |
| `input` | La demande telle qu'elle est envoyée à l'agent. **Auto-suffisante** : elle embarque le contexte nécessaire (livrable à juger, échecs à analyser, plan à exécuter) et n'exige jamais le web (sources = fichiers du workspace, ex. `CLAUDE.md`). |
| `expected` | Ce qu'un bon résultat contient. Pour `exact` : le texte attendu. Pour les autres graders : description lisible du critère (documentation du cas). |
| `grader` | Méthode de notation (4 graders ci-dessous). |
| `check` | Pour `test` : commande shell exécutée depuis la racine du workspace, exit 0 = succès. Pour `regex` : motif Python (`re.search`, mode multiline) appliqué sur `target`. Ignoré pour `exact` et `rubric`. |
| `target` | Sur quoi le grader s'applique : `output` (défaut) = la sortie de l'agent ; `diff` = état de l'arbre git après exécution (`git status --porcelain --untracked-files=all` suivi de `git diff`) ; `file:<chemin>` = contenu de ce fichier (relatif à la racine du workspace). |
| `scope` | Avec `target: diff` : le dossier annoncé par le cas. La restauration de l'arbre après le cas (`git checkout -- <scope>` + `git clean -fd <scope>`) est **limitée à ce dossier**, jamais globale. |
| `runs` | Passes par cas. Défaut : 1 pour `test` / `regex` / `exact` ; `improvement_loop.runs_per_eval` (`.claude/team.json`) pour `rubric`. Score du cas = moyenne des passes. |
| `rubric` | Grille de notation (seulement si `grader: rubric`). |
| `tags` | Thèmes (`discipline`, `format`, `scope`, `code`, `research`...) : le score par tag oriente le critique. |

Les champs ajoutés (`agent`, `check`, `target`, `scope`, `runs`) sont
optionnels : un cas à l'ancien format reste lisible (agent
`orchestrator`, cible `output`, 1 passe).

## Les 4 graders

| Grader | Qui note | Verdict |
|---|---|---|
| `exact` | le fil principal | `target` égal à `expected` après `strip()` des deux côtés. |
| `regex` | le fil principal | `re.search(check, target, re.M)` matche. Préfixer le motif de `(?s)` pour que `.` traverse les lignes. |
| `test` | le fil principal | `check` exécuté depuis la racine du workspace, exit 0 = succès. `{output}` y est remplacé par le chemin d'un fichier temporaire contenant la sortie de l'agent (ou le contenu de `target`), `{workspace}` par la racine du workspace. |
| `rubric` | `<préfixe>-evaluator`, **en aveugle** | L'évaluateur reçoit UNIQUEMENT la sortie, `expected` et `rubric` (jamais `input`, jamais le raisonnement de l'agent) et rend `{"id", "pass", "score", "reason"}`. Non déterministe : `runs` passes moyennées (3 par défaut). |

Un cas inexécutable (outil absent, commande introuvable, workspace sans
dépôt git pour `target: diff`) compte comme **échec** avec `reason`
explicite, et est compté dans `unrunnable` : une baseline qui en contient
n'est jamais réutilisée par `/improve`.

## Règle d'or : un cas = un agent, un critère observable

- **Un agent** : le cas invoque un seul agent généré (`<préfixe>-<agent>`)
  avec son `input`. Pour mesurer l'orchestration, viser `orchestrator`
  avec une tâche minuscule (il délègue réellement).
- **Un critère observable** : le verdict se lit dans la sortie, l'arbre
  git ou un fichier, par un motif ou une commande. Pas de « c'est bien
  écrit » sans grille.
- **Discipline avant domaine** : le jeu de démarrage mesure le respect
  des formats et des périmètres par chaque rôle (valable dans tout
  projet). Les cas métier du projet s'ajoutent ensuite via `/eval-add`.

## Écrire un `check` portable (Windows et Unix)

Le `check` d'un cas `test` est lancé tel quel par le shell du poste
(cmd / PowerShell / bash). Règles :

- **`python -c "..."`** ou **`python -m unittest ...`**, jamais du
  bash-only (`grep`, `test -f`, `[[ ]]`, `&&` enchaînés, redirections).
- Code Python en **guillemets simples** à l'intérieur de la commande
  (`"..."` pour le shell) ; pas de retour à la ligne ; pas de `\` autre
  que `\n` dans une chaîne Python ; **jamais de backtick** (substitution
  de commande sous bash, échappement sous PowerShell : la commande
  change de sens en silence). Pour tolérer des fences ```` ``` ````
  autour d'un JSON, garder le texte du premier `{` au dernier `}` :
  `t=t[t.find('{'):t.rfind('}')+1]`.
- Lire la sortie de l'agent depuis le fichier `{output}` passé en
  argument : `python -c "import sys,json;d=json.load(open(sys.argv[1],encoding='utf-8'));assert 'score' in d" "{output}"`
  (garder les guillemets autour de `{output}` : le chemin peut contenir
  des espaces).
- Un échec = `assert` ou `sys.exit(1)` ; imprimer un mot (`ok`) en cas de
  succès aide la lecture du rapport.

## Exemples par grader

```json
{"id": "case-010", "agent": "reviewer", "input": "OBJECTIF: ... CRITÈRES: ... LIVRABLE: ...", "expected": "Première ligne VERDICT: ...", "grader": "regex", "check": "(?s)\\A\\s*VERDICT: (?:APPROUVÉ|À CORRIGER)", "target": "output", "tags": ["format"]}
{"id": "case-011", "agent": "evaluator", "input": "Note ces 2 cas ... rends UNIQUEMENT ton JSON", "expected": "JSON valide avec score/passed/failed/total", "grader": "test", "check": "python -c \"import sys,json;d=json.load(open(sys.argv[1],encoding='utf-8'));assert d['passed']+d['failed']==d['total']\" \"{output}\"", "target": "output", "tags": ["format"]}
{"id": "case-012", "agent": "executor", "input": "Écris tmp-eval/x.txt contenant `ok`. Ne touche à rien d'autre.", "expected": "x.txt vaut ok", "grader": "exact", "target": "file:tmp-eval/x.txt", "scope": "tmp-eval", "tags": ["scope"]}
{"id": "case-013", "agent": "researcher", "input": "Question : ... (sources : fichiers du workspace)", "expected": "Conclusions sourcées, incertitudes nommées", "grader": "rubric", "rubric": "1 point par conclusion sourcée, 0 si une affirmation n'a pas de source, -1 par fait inventé", "runs": 3, "tags": ["research"]}
```

Le jeu de démarrage livré (`eval-set.jsonl`, 6 cas ; `holdout.jsonl`,
2 cas) couvre les 7 rôles sur la discipline de sortie : sections du
chercheur, verdict du relecteur, JSON unique du critique et de
l'évaluateur, livraison de l'orchestrateur, périmètre de l'exécutant
(`target: diff` sur `tmp-eval/`).

## Verrou

`improvement_loop.eval_set_locked: true` dans `.claude/team.json` : le
hook `.claude/hooks/evals-lock.py` (PreToolUse `Edit|Write|MultiEdit`)
**refuse toute écriture sous `.claude/evals/`**. Sinon la boucle apprend
à tricher (elle modifierait les cas plutôt que les agents).

Pour ajouter ou corriger un cas, l'utilisateur déverrouille
explicitement, le temps de l'édition, dans `.claude/settings.local.json`
(fichier user-local, jamais touché par Claude) :

```json
{ "evals_unlocked": true }
```

puis remet `false` (ou retire la clé). Le journal `.claude/journal/`
n'est jamais verrouillé.

## Ajouter un cas : `/eval-add`

Un échec réel observé en session (réponse fausse, livrable incomplet,
régression) vaut un cas d'éval. `/eval-add` transforme l'échec en
ligne JSONL candidate (id suivant, agent visé, grader adapté, `check`,
tags), la propose, et rappelle que l'ajout exige `evals_unlocked`.
Jamais d'ajout silencieux. Environ un cas sur cinq va dans
`holdout.jsonl`.
