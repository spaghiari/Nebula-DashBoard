# conventions/improvement-loop

Boucle d'amélioration **mesurée** de l'équipe d'agents (module
`claude-team`). Principe : on n'améliore que ce qu'on mesure. Chaque
changement est testé contre un jeu d'évals figé et gardé seulement s'il
fait mieux sans rien casser.

Complète [`self-improvement.md`](self-improvement.md) (module
`claude-self-improving`) : ce dernier dit **quoi retenir et comment
trier** (registres, frictions observées) ; cette boucle dit **comment
prouver qu'un changement d'agent est une amélioration**.

## Fichiers (chemins Nebula, relatifs à la racine du workspace)

| Fichier | Rôle |
|---|---|
| `.claude/team.json` | Manifeste : agents, modèles, `team.prefix` (préfixe des agents générés), section `improvement_loop` (paramètres de la boucle). Source de vérité. |
| `.claude/team/agents/<id>.md` | Corps source des agents (sans frontmatter). Cibles des modifications de prompt. |
| `.claude/agents/<préfixe>-<id>.md` | Agents **générés** par Nebula (frontmatter Claude Code + contraintes + corps). Régénérés via le module (« Régénérer »). |
| `.claude/evals/eval-set.jsonl` | Jeu d'évals figé (verrouillé). Un cas = un agent, un critère observable (`agent`, `grader`, `check`, `target`, `scope`, `runs` : cf. `.claude/evals/README.md`). |
| `.claude/evals/holdout.jsonl` | Jeu caché, jamais vu par la boucle. |
| `.claude/journal/changes.jsonl` | Journal des itérations (une ligne JSON par itération). |
| `.claude/improvements.md` | Registre des frictions (module self-improving) : hypothèses en entrée, verdicts mesurés en sortie. |

## Topologie d'exécution

| Qui | Fait quoi |
|---|---|
| **Fil principal** (`/eval`, `/improve`) | Boucle sur les cas ; délègue chaque `input` à l'agent visé `<préfixe>-<agent>` ; construit `target` (sortie, `git status --porcelain --untracked-files=all` + `git diff`, ou fichier) ; calcule lui-même les graders `test` (exécute `check`, `{output}` = fichier temporaire de la sortie), `regex` (motif Python, `re.M`) et `exact` ; restaure l'arbre après un cas `target: diff` (`git checkout -- <scope>` + `git clean -fd <scope>`, jamais globaux) ; tient le journal ; commite les itérations acceptées. |
| `<préfixe>-evaluator` | **Note seulement**, en aveugle : reçoit `id`, la sortie, `expected`, `rubric` (jamais `input` ni le raisonnement), rend `{"id", "pass", "score", "reason"}`. Température conceptuelle 0. Moyenné sur `runs` (défaut `runs_per_eval`). |
| `<préfixe>-critic` | UN diff par itération (hypothèse, cible, kind, expected_fixes, risk). Jamais hors de `/improve`. |
| `/team <objectif>` | Le fil principal joue l'orchestrateur (corps `team/agents/orchestrator.md` tel quel). L'agent `<préfixe>-orchestrator` sert à la délégation explicite et aux cas d'éval qui mesurent l'orchestration. |

## Empreinte de configuration (`config_version`)

sha1 court (12 hex) sur les chemins relatifs triés + contenus bruts de
`.claude/team.json`, `.claude/team/agents/*.md` et des agents générés
`.claude/agents/<préfixe>-*.md`. Calculée par le one-liner `python -c`
de `.claude/commands/eval.md` (à exécuter depuis la racine du workspace)
et, avec le même algorithme, par Nebula (`team_config_hash`) qui
l'affiche dans l'onglet « Amélioration » et compare la dernière ligne du
journal à l'empreinte courante : **baseline à jour** (réutilisable par
`/improve`) ou **périmée** (re-mesure d'abord). Ce n'est pas le hash git
HEAD : un corps modifié sans commit change l'empreinte.

## Deux phases, deux sessions

Claude Code charge la liste et le contenu des sous-agents au démarrage
de la session et ne relit pas un agent régénéré (vérifié par sonde :
un marqueur ajouté au corps, régénéré, n'apparaît pas dans la sortie de
l'agent invoqué dans la même session). Une itération se joue donc en
deux `/improve` :

| Phase | Session | Fait | Journal |
|---|---|---|---|
| 1 : candidat | A | baseline, critique, diff appliqué, agents régénérés, cible sauvegardée dans `.claude/journal/pending/<n>/` | ligne `status: pending` (`baseline_version` = empreinte mesurée, `config_version` = empreinte du candidat) |
| 2 : verdict | B (nouvelle) | contrôle de l'empreinte, mesure, accepté ou restauré | ligne de résolution, même `iteration` (la dernière ligne d'une itération fait foi) |

Un seul candidat en attente à la fois. Nebula (onglet Amélioration)
affiche « Candidat n à mesurer » tant que la résolution n'est pas
journalisée, et « altéré » si l'empreinte courante n'est plus celle du
candidat. Si la cible n'est pas suivie par git (`.claude/` ignoré),
`commit: null` et `untracked: true` ; l'amélioration acceptée est à
porter à la main dans le template overlay si elle est générique.

## Étapes

```
baseline = journal.dernière_ligne si config_version == empreinte courante et unrunnable == 0
           sinon mesure(config_actuelle)                 # procédure de /eval

pour i de 1 à max_iterations:
    proposition = critic.analyse(baseline.failures, journal, items [TODO] de improvements.md)
    candidat    = appliquer(proposition.diff) sur une branche improve/<n>
    résultat    = mesure(candidat)

    gain        = résultat.score - baseline.score
    régressions = cas passés dans baseline mais échoués dans résultat

    si gain >= accept_if.min_score_gain et régressions <= accept_if.max_regressions:
        fusionner(candidat) ; commit ; baseline = résultat ; statut = "accepted"
    sinon:
        abandonner(candidat) ; statut = "rejected"

    journal.ajouter({iteration, date, target, hypothesis, score_before, score_after, regressions, status, commit, config_version, unrunnable})

    si stop_after_consecutive_rejects rejets consécutifs: arrêter et demander une revue humaine
```

Paramètres par défaut (`.claude/team.json` § `improvement_loop`) :
`min_score_gain: 0.02`, `max_regressions: 0`, `max_iterations: 10`,
`stop_after_consecutive_rejects: 3`, `runs_per_eval: 3`.

Commandes : `/eval [--tag] [--agent] [--id]` (mesure seule),
`/improve [N]` (itérations), `/eval-add` (nouveau cas depuis un échec
réel), `/team <objectif>` (orchestration par le fil principal).

## Garde-fous

| Garde-fou | Pourquoi | Mécanique |
|---|---|---|
| **Évals verrouillées** | Sinon la boucle apprend à tricher | Hook `evals-lock.py` (PreToolUse Edit/Write) refuse `.claude/evals/` tant que `eval_set_locked` est vrai ; déverrouillage par `"evals_unlocked": true` dans `.claude/settings.local.json` |
| **Une modification à la fois** | Attribuer le gain | Le critique rend UN diff, une cible |
| **Zéro régression** | Un gain global qui casse un cas existant est refusé | `max_regressions: 0` |
| **Variance** | Notation LLM non déterministe | `runs_per_eval: 3` pour `rubric`, moyennes comparées ; `test` / `regex` / `exact` déterministes, 1 passe |
| **Notation en aveugle** | L'évaluateur ne doit pas être influencé | Il ne reçoit que sortie + attendu + grille |
| **Jeu caché** | Détecter le surapprentissage | `holdout.jsonl`, vérifié à la main |
| **Baseline fraîche** | Comparer des mesures de la même chose | `config_version` = empreinte ; réutilisation seulement si égale ET `unrunnable == 0` |
| **Périmètre git** | Un cas `diff` ne doit pas effacer le travail en cours | Arbre propre ou stash explicite avant ; restauration limitée à `scope` |
| **Versionnage** | Retour arrière | `/improve` vaut demande de commit pour ses itérations acceptées (`update(<préfixe>): improve/<n> - <hypothèse>`), branche `improve/<n>` jetée si rejet, jamais de push |
| **Section `improvement_loop` intouchable** | Ne pas baisser le seuil pour « réussir » | Interdit au critique et à `/improve` |

## Format du journal (`.claude/journal/changes.jsonl`)

```json
{"iteration": 3, "date": "2026-10-14", "target": ".claude/team/agents/researcher.md", "hypothesis": "...", "score_before": 0.82, "score_after": 0.86, "regressions": [], "status": "accepted", "commit": "a1b2c3d", "config_version": "3f9a1c0b7d2e", "unrunnable": 0}
```

`status` : `accepted` | `rejected`. `commit` : hash court, ou `null`
si rejeté. `config_version` : empreinte de la configuration en place
**après** l'itération (candidat si acceptée, baseline si rejetée).
`unrunnable` : cas inexécutables de la mesure (une baseline qui en
contient n'est pas réutilisée). Une ligne invalide est ignorée par
l'onglet « Amélioration » de Nebula (comptée comme invalide), jamais
réécrite.

### Lignes écrites par Nebula

Le moteur d'itération de Nebula écrit dans le même journal. Ses lignes
portent `runner: "nebula"` et un `job_id`, et diffèrent ainsi :

- `branch: null` : pas de branche `improve/<n>` ; une ligne `pending`
  avec `branch: null` ou `runner: nebula` n'a rien à fusionner. Sa
  sauvegarde est dans `.claude/journal/pending/<n>/`.
- `diff_archive` : chemin de l'archive d'un candidat écarté,
  `.claude/journal/rejected/<n>/candidate.diff`.
- `failures_after` : ids des cas échoués après le candidat, écrit sur la
  ligne de résolution (à reproduire aussi en manuel).
- Champs de coût **optionnels**, jamais exigés : `cost_usd`, `tokens`,
  `duration_ms`, `calls`, et `reason` (motif du verdict). Une ligne
  manuelle valide peut tous les omettre.

## Pont avec `improvements.md`

```
[TODO] (friction observée)  --critic-->  hypothèse  --/improve-->  mesure
      accepté : [DONE YYYY-MM-DD] + « Mesure : avant -> après, commit, itération »
      rejeté  : [ABANDONED]       + « Mesure : avant -> après, régressions, itération »
```

Le registre reste tenu selon `self-improvement.md` (format d'item,
attribution d'auteur) ; la boucle n'y ajoute que la ligne « Mesure » et
le changement de statut, toujours annoncés dans la sortie de `/improve`.

## Cohabitation avec les agents du module Auto-amélioration

Si `.claude/agents/` contient `*-expert`, c'est lui l'exécutant des
tâches conséquentes (feature M+, 10 fichiers ou plus, multi-domaines,
refactor à effets de bord) : il porte la mémoire projet.
`<préfixe>-executor` exécute les tâches S et les étapes atomiques d'un
plan. `*-impl-validator` complète `<préfixe>-reviewer` (après lui,
jamais à sa place). Règle portée par `team/agents/orchestrator.md` et le
bloc always-on de `CLAUDE.md`.

## Anti-patterns

- Lancer `/improve` sur une baseline périmée (empreinte différente, ou
  cas inexécutables) : re-mesurer d'abord.
- Laisser l'évaluateur exécuter les cas ou voir l'entrée : il note, en
  aveugle, c'est tout.
- Modifier directement un agent généré `.claude/agents/<préfixe>-<id>.md`
  : la prochaine régénération l'écraserait (marqueur généré). Modifier
  le corps source dans `.claude/team/agents/`.
- Grouper plusieurs changements « pour aller plus vite » : le gain n'est
  plus attribuable, l'itération ne vaut rien.
- `git checkout -- .` ou `git clean -fd` globaux après un cas `diff` :
  toujours limités au `scope` du cas.
