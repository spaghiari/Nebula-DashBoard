---
description: Mesure la configuration d'équipe claude-team contre le jeu d'évals figé (.claude/evals/eval-set.jsonl). Le fil principal boucle sur les cas, délègue chaque input à l'agent visé, note (test / regex / exact) ou fait noter en aveugle (rubric), et rend le JSON de score (global, par tag, par agent, échecs). Filtres --tag, --agent, --id. N'écrit rien.
---

Mesure la configuration d'équipe courante contre le jeu d'évals figé.
Cette commande **n'écrit rien** : ni journal, ni évals, ni agents. Pour
une itération d'amélioration (qui journalise), utiliser `/improve`.

`/eval` seul = tous les cas. Filtres optionnels, cumulables :
`/eval --tag format`, `/eval --agent reviewer`, `/eval --id case-003`.

## Entrées

- `.claude/team.json` : manifeste. `team.prefix` = préfixe `<p>` des
  agents générés (défaut `{{name}}`) ; `improvement_loop` : `eval_set`,
  `runs_per_eval`.
- `.claude/evals/eval-set.jsonl` : un cas par ligne (format et champs
  `agent`, `check`, `target`, `scope`, `runs` dans
  `.claude/evals/README.md`). Jamais `holdout.jsonl` (jeu caché).
- Les agents générés `.claude/agents/<p>-*.md` (configuration mesurée).

## Topologie

C'est **toi, le fil principal**, qui boucles sur les cas. Tu ne juges
jamais toi-même une sortie « au feeling » : tu appliques le grader.

Pour chaque cas :

1. **Préparer** (`target: diff` seulement) : exiger un arbre git propre
   (`git status --porcelain` vide) ou faire un `git stash push -m
   "eval <id>"` explicite et annoncé. Workspace sans dépôt git : le cas
   est inexécutable (échec explicite, `reason`), pas ignoré.
2. **Déléguer** `input` tel quel à l'agent généré visé `<p>-<agent>`
   (outil Agent, sous-agent de ce workspace ; `agent` absent =
   `orchestrator`). Capturer sa sortie finale, sans la retoucher.
3. **Construire `target`** : `output` = la sortie capturée ; `diff` =
   `git status --porcelain --untracked-files=all` suivi de `git diff` ;
   `file:<chemin>` = contenu du fichier (absent = échec explicite).
4. **Noter** :
   - `exact` : `target.strip() == expected.strip()`.
   - `regex` : `re.search(check, target, re.M)` (motif Python ; le
     calculer avec `python -c`, pas de tête).
   - `test` : écrire `target` dans un fichier temporaire, remplacer
     `{output}` par son chemin et `{workspace}` par la racine du
     workspace dans `check`, exécuter depuis la racine du workspace ;
     exit 0 = succès. Commande introuvable = inexécutable (échec,
     `reason`, compté dans `unrunnable`).
   - `rubric` : déléguer à `<p>-evaluator` **en aveugle** : il reçoit
     UNIQUEMENT `id`, la sortie (`target`), `expected` et `rubric` ;
     jamais `input`, jamais le raisonnement ni le transcript de l'agent
     mesuré. Il rend `{"id", "pass", "score", "reason"}`. Répéter `runs`
     fois (défaut `runs_per_eval`) et moyenner ; `pass` = moyenne >= 0,5.
5. **Restaurer** (`target: diff` seulement) : `git checkout -- <scope>`
   puis `git clean -fd <scope>`, **limités au dossier `scope` du cas**,
   jamais `git checkout -- .` ni `git clean -fd` globaux. Dépiler le
   stash de l'étape 1 s'il y en a eu un.

Score global = cas passés / cas notés. `by_tag` et `by_agent` = même
ratio restreint au tag / à l'agent.

## Empreinte de configuration (`config_version`)

Ce n'est plus le hash git : c'est l'empreinte de ce qui est mesuré
(manifeste + corps sources + agents générés), calculée depuis la racine
du workspace par ce one-liner, **tel quel** (même algorithme que
`team_config_hash` dans Nebula, qui l'affiche dans l'onglet
« Amélioration » et s'en sert pour dire si la baseline du journal est à
jour) :

```bash
python -c "import hashlib,json,pathlib;c=pathlib.Path('.claude');p=((json.loads(c.joinpath('team.json').read_text(encoding='utf-8-sig')).get('team') or {}).get('prefix') or '{{name}}');f=sorted([c/'team.json',*c.glob('team/agents/*.md'),*c.glob('agents/'+p+'-*.md')],key=lambda x:x.relative_to(c.parent).as_posix());h=hashlib.sha1();[h.update(x.relative_to(c.parent).as_posix().encode('utf-8')+bytes(1)+x.read_bytes()+bytes(1)) for x in f];print(h.hexdigest()[:12])"
```

## Sortie attendue

Rendre le JSON **tel quel**, puis un résumé de 3 lignes : score, tag et
agent les plus faibles, nombre d'échecs (dont inexécutables).

```json
{
  "config_version": "3f9a1c0b7d2e",
  "score": 0.83,
  "passed": 5, "failed": 1, "total": 6, "unrunnable": 0,
  "by_tag": {"format": 0.8, "scope": 1.0},
  "by_agent": {"researcher": 1.0, "reviewer": 0.0},
  "failures": [{"id": "case-002", "agent": "reviewer", "expected": "...", "got": "...", "reason": "..."}]
}
```

## Règles

- Ne modifie jamais `.claude/evals/` (verrou `evals-lock.py`), ni les
  agents, ni le journal.
- Même configuration + mêmes cas = même procédure : mêmes commandes,
  même ordre, résultats bruts notés (sortie, exit code, motif).
- Un cas inexécutable compte comme échec avec `reason` explicite et
  incrémente `unrunnable` : jamais ignoré en silence.
- `got` dans `failures` : extrait court (10 lignes max) de `target`,
  jamais le transcript de l'agent.
