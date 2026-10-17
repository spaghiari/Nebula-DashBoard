---
description: Boucle d'amélioration mesurée de l'équipe claude-team, en DEUX phases parce qu'une session Claude Code ne recharge pas la définition d'un agent modifié. Phase 1 (candidat) : baseline (journal réutilisé si l'empreinte est inchangée, sinon procédure de /eval), UNE modification proposée par le critique, appliquée et journalisée `pending`. Phase 2 (verdict, nouvelle session) : mesure du candidat, accepté seulement si gain >= min_score_gain et zéro régression, sinon restauré ; commit de l'itération acceptée si la cible est suivie par git ; pont avec improvements.md. `/improve` détecte seul la phase à jouer.
---

Applique la boucle de
[`.claude/memory/conventions/improvement-loop.md`](../memory/conventions/improvement-loop.md)
avec les paramètres de `.claude/team.json` section `improvement_loop`
(`accept_if`, `max_iterations`, `stop_after_consecutive_rejects`,
`runs_per_eval`, `journal`).

Préfixe `<p>` des agents générés = `team.prefix` de `.claude/team.json`
(défaut `{{name}}`).

## Pourquoi deux phases

Claude Code charge la liste **et le contenu** des sous-agents au
démarrage de la session ; un agent régénéré n'est pas relu à chaud
(vérifié : un marqueur ajouté au corps puis régénéré n'apparaît pas dans
la sortie de l'agent invoqué dans la même session). Mesurer un candidat
exige donc une **nouvelle session**. Une itération = `/improve` dans une
session (phase 1), puis `/improve` dans la session suivante (phase 2).

`/improve` lit la dernière ligne de `.claude/journal/changes.jsonl` :

- dernière ligne `status: pending` : jouer la **phase 2** (verdict) ;
- sinon : jouer la **phase 1** (candidat).

`/improve N` enchaîne N phases 1 ? Non : une seule phase 1 par session,
puisque le candidat suivant ne peut être mesuré qu'après un redémarrage.
L'argument N est ignoré avec un avertissement.

## Lignes écrites par Nebula

Le journal peut contenir des lignes écrites par Nebula (moteur
d'itération de l'onglet « Amélioration »), reconnaissables à
`runner: "nebula"` et à un `job_id`. Elles suivent le même format, avec
des différences à connaître avant de jouer `/improve` à la main :

- `branch: null` : Nebula n'ouvre jamais de branche `improve/<n>`. Une
  ligne `pending` avec `branch: null` ou `runner: nebula` n'a **aucune
  branche à fusionner ni à supprimer** ; la phase 2 ne touche pas à git
  pour cette itération.
- La sauvegarde de la cible est dans `.claude/journal/pending/<n>/`
  (comme en manuel). L'archive d'un candidat écarté est dans
  `.claude/journal/rejected/<n>/candidate.diff` (champ `diff_archive`).
- Champs de coût, **tous optionnels, ne jamais les exiger** : `cost_usd`,
  `tokens`, `duration_ms`, `calls`, `reason` (motif du verdict). Une ligne
  manuelle peut les omettre.
- `failures_after` : ids des cas échoués après le candidat. Ne pas
  l'inventer pour une ligne `pending`.

## Invariants (non négociables)

- **Évals verrouillées** : aucune écriture sous `.claude/evals/`
  (hook `evals-lock.py`). Un candidat qui touche aux évals est rejeté
  sans mesure.
- **Une seule modification par itération** : un fichier cible, un diff.
  Sinon le gain n'est pas attribuable.
- **Zéro régression** : un cas qui passait dans la baseline et échoue
  dans le candidat = rejet, quel que soit le gain global.
- **Jamais de modification** de `.claude/evals/`, de la section
  `improvement_loop` de `.claude/team.json`, ni du corps du critique
  (`.claude/team/agents/critic.md`).
- **Commits** : lancer `/improve` **vaut demande explicite de commit**
  pour ses itérations acceptées, sur la branche courante, au format
  `update(<p>): improve/<n> - <hypothèse courte>` ; aucun autre commit,
  jamais de push. Les hooks pre-commit du projet s'appliquent (pas
  d'em-dash dans le message, pas de trailer `Co-Authored-By`). Si la
  cible n'est **pas suivie par git** (workspace dont `.claude/` est
  ignoré, cas d'un `.gitignore` sur `workspaces/*`), pas de commit :
  `commit: null` et `untracked: true` dans le journal ; l'amélioration
  acceptée est à porter à la main dans le template overlay si elle est
  générique.
- **Pas d'ajout silencieux** : toute écriture dans `improvements.md` est
  annoncée dans la sortie.
- **Un seul candidat en attente** : phase 1 refusée tant qu'une ligne
  `pending` n'est pas résolue.

## Phase 1 : candidat

1. **Baseline** : calculer l'empreinte courante avec le one-liner de
   `/eval` (§ « Empreinte de configuration »). Si la dernière ligne
   résolue du journal (`accepted` ou `rejected`) a le même
   `config_version` ET `unrunnable` à 0, réutiliser sa mesure
   (`score_after` si acceptée, `score_before` si rejetée) et ses échecs ;
   sinon mesurer selon la procédure de `/eval` (le fil principal boucle,
   `<p>-evaluator` ne note que les `rubric`, en aveugle). Une mesure
   `/eval` faite dans la même session sur la même empreinte vaut
   baseline. L'onglet « Amélioration » de Nebula affiche « baseline à
   jour » / « périmée » sur ce même critère.
2. **Hypothèse** : déléguer à `<p>-critic` avec les échecs de la
   baseline, le journal et les items `[TODO]` de
   `.claude/improvements.md`. Le critique rend UN JSON (`hypothesis`,
   `improvement_item`, `target`, `kind`, `diff`, `expected_fixes`,
   `risk`).
3. **Candidat** : `n` = dernière itération du journal + 1. Sauvegarder la
   cible intacte dans `.claude/journal/pending/<n>/<nom du fichier>.before`
   (restauration en cas de rejet). Appliquer le diff (une cible : un
   corps `.claude/team/agents/<id>.md`, un modèle dans `.claude/team.json`
   section `agents`, une commande, une mémoire). Si la cible est un corps
   d'agent, régénérer les agents (`POST
   /api/workspaces/<ws>/overlays/claude-team` avec `{"regenerate": true}`
   sur Nebula, ou « Ré-appliquer » + « Régénérer » dans l'onglet
   Configuration) pour que la mesure porte sur l'agent réellement
   invoqué. Si la cible est suivie par git : branche `improve/<n>` depuis
   la branche courante, diff appliqué dessus (sans commit).
4. **Journal** : appender UNE ligne `pending` :

   ```json
   {"iteration": 3, "date": "YYYY-MM-DD", "target": ".claude/team/agents/architect.md", "hypothesis": "...", "expected_fixes": ["case-008"], "score_before": 0.75, "failures_before": ["case-005", "case-008", "case-010"], "status": "pending", "baseline_version": "1d681d641cb5", "config_version": "9c2e4f0a11bb", "unrunnable": 0, "untracked": true}
   ```

   `baseline_version` = empreinte mesurée par la baseline ;
   `config_version` = empreinte du **candidat** en place (recalculée
   après régénération) ; `failures_before` = ids échoués de la baseline.
5. **Arrêt de session** : annoncer à l'utilisateur qu'il doit **ouvrir
   une nouvelle session** dans ce workspace et relancer `/improve` pour
   la phase 2. Ne rien mesurer dans la session courante.

## Phase 2 : verdict

1. **Contrôle** : recalculer l'empreinte. Si elle diffère du
   `config_version` de la ligne `pending`, le candidat a été altéré entre
   les deux sessions : résoudre la ligne en `rejected` avec
   `reason: "candidat altéré"`, restaurer la sauvegarde, régénérer, et
   s'arrêter.
2. **Mesure** : procédure de `/eval` sur le candidat (configuration
   courante = le candidat, puisque la session vient de démarrer).
3. **Verdict** : `gain = score - score_before` ; `régressions` = ids
   absents de `failures_before` mais échoués maintenant. Accepté si
   `gain >= accept_if.min_score_gain` et
   `len(régressions) <= accept_if.max_regressions` ; sinon rejeté.
   - Accepté : supprimer la sauvegarde `.claude/journal/pending/<n>/` ;
     si suivi par git, fusion de `improve/<n>` dans la branche de travail,
     commit `update(<p>): improve/<n> - <hypothèse courte>`, branche
     supprimée. Si la ligne `pending` a `branch: null` ou
     `runner: nebula`, il n'y a pas de branche à fusionner : le candidat
     est déjà en place, seule la ligne de résolution est à écrire.
   - Rejeté : restaurer la cible depuis la sauvegarde, régénérer les
     agents, supprimer `.claude/journal/pending/<n>/` ; si suivi par git,
     revenir à la branche de travail et supprimer `improve/<n>` (sauf si
     `branch: null` : rien à supprimer). Archiver au besoin le diff écarté
     dans `.claude/journal/rejected/<n>/candidate.diff`.
4. **Journal** : appender UNE ligne de **résolution**, même `iteration`
   que la ligne `pending` (la dernière ligne d'une itération fait foi) :

   ```json
   {"iteration": 3, "date": "YYYY-MM-DD", "target": ".claude/team/agents/architect.md", "hypothesis": "...", "score_before": 0.75, "score_after": 0.83, "regressions": [], "status": "accepted", "commit": null, "untracked": true, "config_version": "9c2e4f0a11bb", "unrunnable": 0}
   ```

   `failures_after` = ids des cas échoués lors de la mesure du candidat
   (liste vide si aucun) ; ajouter-le toujours à la ligne de résolution,
   la baseline suivante s'en sert. Les champs de coût de Nebula
   (`cost_usd`, `tokens`, `duration_ms`, `calls`) ne sont pas à écrire à
   la main.
   `config_version` = empreinte de la configuration **en place après le
   verdict** (le candidat si acceptée, la baseline restaurée si rejetée),
   recalculée après restauration ou régénération. `unrunnable` = cas
   inexécutables de la mesure. Le journal n'est jamais verrouillé.
5. **improvements.md** : refléter le verdict (cf. Pont ci-dessous).
6. **Arrêt** : après `stop_after_consecutive_rejects` rejets
   consécutifs (journal inclus), s'arrêter et demander une revue humaine :
   résumer les hypothèses rejetées et les tags / agents qui résistent.
   Sinon, la même session peut enchaîner directement une **phase 1**
   (nouveau candidat), mesurable à la session suivante.

## Pont avec `improvements.md`

- Le critique lit les items **`[TODO]`** de `.claude/improvements.md`
  comme hypothèses candidates (`improvement_item` dans sa sortie).
- Itération **acceptée** sur un item : passer l'item en
  **`[DONE YYYY-MM-DD]`** avec, dans son bloc :
  `Mesure : score avant -> après (gain +0.0X, 0 régression), commit <hash ou aucun>, itération <n>`.
- Itération **rejetée** sur un item : passer l'item en **`[ABANDONED]`**
  avec `Mesure : score avant -> après (gain X, régressions : ...), itération <n>` ;
  l'item reste dans le registre comme hypothèse mesurée et écartée (le
  critique ne la reproposera pas).
- Hypothèse sans item : rien à écrire dans le registre, sauf si une
  friction nouvelle sur un outil Claude est observée (la **proposer**,
  cf. `conventions/self-improvement.md`).

## Sortie attendue

Phase 1 :

```
## /improve - itération <n>, phase 1 (candidat)
- Baseline : réutilisée (journal, config <hash>) | mesurée (config <hash>) : score <s>, échecs <ids>
- Hypothèse : <...> (item improvements : <titre ou aucun>)
- Cible : <fichier> (<kind>), sauvegarde .claude/journal/pending/<n>/
- Candidat en place : agents régénérés, empreinte <hash>
- Journal : ligne <n> pending écrite
- Suite : ouvrir une NOUVELLE session dans ce workspace et lancer /improve (phase 2)
```

Phase 2 :

```
## /improve - itération <n>, phase 2 (verdict)
- Candidat : <cible>, empreinte <hash> (contrôle OK)
- Score : <avant> -> <après> (gain <+/-0.0X>), régressions : <liste ou aucune>, inexécutables : <n>
- Verdict : ACCEPTÉ (commit <hash> | non suivi par git) | REJETÉ (cible restaurée)
- Journal : ligne de résolution <n> écrite (config_version <hash>)
- improvements.md : <item passé en DONE/ABANDONED, ou rien>
```
