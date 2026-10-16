---
description: Transforme un échec réel observé en session (réponse fausse, livrable incomplet, régression) en cas d'éval candidat pour .claude/evals/eval-set.jsonl (ou holdout.jsonl) : un agent visé, un critère observable (grader + check + target). Propose la ligne JSONL, n'écrit qu'après accord ET déverrouillage explicite (evals_unlocked). Jamais d'ajout silencieux.
---

Un échec vu en session vaut un cas d'éval : c'est ainsi que le jeu grandit
avec les vrais problèmes du projet, pas avec des exemples inventés.
`/eval-add <description de l'échec>` ou `/eval-add` seul (l'échec est
alors celui discuté juste avant dans la conversation).

## Procédure

1. **Caractériser l'échec** : quel agent (`agent`, un id du manifeste),
   quelle demande (`input`, auto-suffisante : elle embarque le contexte,
   jamais le web), quel résultat était attendu (`expected`), comment on
   sait que c'est raté. S'il manque un élément, poser UNE question.
2. **Choisir le grader et la cible** (cf. `.claude/evals/README.md`) :
   - résultat exact connu -> `exact` (`expected` = le texte) ;
   - motif vérifiable -> `regex` (`check` = motif Python) ;
   - comportement testable par une commande -> `test` (`check` =
     `python -c "..." "{output}"` ou `python -m unittest ...`, portable
     Windows / Unix, exit 0 = succès, jamais de backtick ni de bash-only) ;
   - qualité à juger -> `rubric` (critères explicites dans `rubric`,
     noté en aveugle par l'évaluateur, `runs` = `runs_per_eval`).
   - `target` : `output` (défaut), `diff` (avec `scope` = dossier
     annoncé), ou `file:<chemin>`.
3. **Id suivant** : lire `.claude/evals/eval-set.jsonl` et
   `holdout.jsonl`, prendre `case-NNN` (ou `hold-NNN`) suivant. Un id
   n'est jamais réutilisé.
4. **Destination** : environ un cas sur cinq va dans `holdout.jsonl`
   (jeu caché, jamais vu par la boucle) ; le proposer explicitement.
5. **Proposer la ligne** JSONL complète, par exemple :

   ```json
   {"id": "case-007", "agent": "reviewer", "input": "OBJECTIF: ... CRITÈRES: ... LIVRABLE: ...", "expected": "VERDICT: À CORRIGER en première ligne", "grader": "regex", "check": "(?s)\\A\\s*VERDICT: À CORRIGER", "target": "output", "runs": 1, "tags": ["format", "reviewer"]}
   ```

   Vérifier le motif ou la commande sur l'échec réel avec `python -c`
   (le cas doit échouer sur la sortie fautive et passer sur une sortie
   correcte).
6. **Rappeler le verrou** : `.claude/evals/` est verrouillé par le hook
   `evals-lock.py`. L'ajout exige que l'utilisateur pose
   `"evals_unlocked": true` dans `.claude/settings.local.json` (fichier
   user-local : Claude ne le modifie jamais), puis le remette à `false`
   après l'ajout.
7. **N'écrire qu'après accord explicite** de l'utilisateur et
   déverrouillage effectif (si le hook refuse, le dire et s'arrêter :
   ne pas contourner). Appender la ligne, sans réécrire le fichier.

## Règles

- Jamais d'ajout silencieux, jamais de modification d'un cas existant
  via cette commande (un cas faux se corrige en le remplaçant par un
  nouvel id, l'ancien est retiré à la main par l'utilisateur).
- Un cas = un agent, un critère observable, un échec observé et sourcé
  (session, date). Pas de cas spéculatif.
- Après ajout, signaler que la baseline du journal est périmée (le jeu a
  changé) : le prochain `/improve` doit re-mesurer.
