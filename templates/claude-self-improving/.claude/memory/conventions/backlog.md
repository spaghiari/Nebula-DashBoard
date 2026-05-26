# conventions/backlog

Pattern de gestion du backlog projet (`.claude/backlog.md`). Permet de
conserver en mémoire les actions différées sans encombrer les
conversations Claude ni dépendre uniquement des issues GitLab.

## Quand ajouter un item au backlog

Signaux qui méritent un item :

| Signal | Type d'item |
|---|---|
| **Décision reportée** : un arbitrage de design tranché « plus tard » | P1 ou P2 selon urgence |
| **Refactor identifié non urgent** : un fichier qui dépasse les 500 lignes, une duplication de pattern, un trait qui pourrait être extrait | P2 |
| **Pitfall observé non corrigé** : un bug silencieux constaté mais non fixé dans le scope courant | P0 ou P1 |
| **Feature demandée hors scope courant** : idée d'amélioration UX ou nouvelle fonctionnalité différée | P1 ou P2 |
| **Doc à compléter** : section de mémoire identifiée comme manquante mais pas critique | P2 |
| **Migration future** : préparation à une montée de version (PHP, Icinga Web 2, Icinga2) | P1 ou P2 |
| **Tech debt** : raccourci pris dans un sprint, à payer plus tard | P2 |

## Quand NE PAS ajouter au backlog

- **Items éphémères de session** (point de reprise, état de travail
  en cours) → contexte conversationnel ou `TaskCreate`, pas backlog
- **Items déjà ouverts** ailleurs (issue GitLab, MR pending) →
  référencer plutôt que dupliquer
- **Items vagues non actionnables** (« améliorer la perf ») →
  refuser ou demander à scinder en items précis
- **Items perso** (idées d'exploration personnelle) → `CLAUDE.local.md`
  (gitignored)
- **Items déjà DONE** (déjà résolus dans le code) → pas la peine

## Priorisation

| Priorité | Critère | Délai cible |
|---|---|---|
| **P0** | Sécurité, donnée, bloquant en prod | Avant prochain commit |
| **P1** | Important, impacte la qualité ou l'UX | Prochaine release (mineure) |
| **P2** | Nice-to-have, peut attendre indéfiniment | Quand opportunité |

Une P0 doit être adressée immédiatement ou escalée à un fix urgent. Si
on accepte de garder une P0 au backlog plus de quelques heures, c'est
qu'elle est mal qualifiée (probablement P1).

## Format d'un item

```markdown
- **[TODO] Titre court actionnable** (P1, ajouté 2026-MM-DD par <author>)
  - Contexte : pourquoi cet item existe (issue, post-mortem, retour user)
  - Détail : ce qu'il faut faire concrètement (fichiers, contrats à
    respecter, tests à passer)
  - Bloqué par : si applicable (autre item du backlog, dépendance
    externe, validation user attendue)
```

## Cycle de vie d'un item

```
[TODO] → [IN PROGRESS] → [DONE]
   ↓        ↓
[BLOCKED] [ABANDONED]
```

- **[TODO]** : item identifié, pas commencé. Stage VALIDATED du
  pipeline (cf. [`pipeline.md`](pipeline.md)).
- **[IN PROGRESS]** : travail en cours. Stage IN PROGRESS. Format
  enrichi : ajouter `Démarré : YYYY-MM-DD`, `Branche : <nom>` (si
  branche dédiée), liste des commits au fil de l'eau. Transition
  déclenchée par décision user de démarrage.
- **[BLOCKED]** : attente d'une décision externe ou d'un autre item.
  Sous-état de IN PROGRESS - l'item reste compté en cours mais avec
  blocage explicite. Ajouter `Bloqué par : <raison>`.
- **[DONE]** : terminé. Stage DONE. Ajouter date de clôture
  (`[DONE YYYY-MM-DD]`) + référence commit/release. Déplacer dans
  la section « Items terminés ».
- **[ABANDONED]** : abandonné. Ajouter raison. Déplacer dans la
  section « Items abandonnés ».

Le pipeline complet (IDEAS → VALIDATED → IN PROGRESS → DONE) avec
règles de transition est documenté dans
[`pipeline.md`](pipeline.md).

## Pattern de proposition à l'utilisateur

Quand un signal est détecté en cours de session :

```
## Items backlog identifiés

Au fil de cette session, j'ai identifié les actions différées suivantes
qui mériteraient une entrée au backlog :

1. **[TODO] <titre>** (P1)
   - Contexte : <pourquoi>
   - Détail : <quoi faire>

Tu veux les ajouter au backlog maintenant, ou plus tard ?
```

L'utilisateur tranche ; si OK, ajout au `.claude/backlog.md` avec un
commit dédié `doc({{label}}): backlog - ajoute <résumé>`.

## Anti-pattern : backlog devenu cimetière

Si le backlog dépasse ~50 items actifs, c'est un signal qu'on
n'épure pas assez. Action :

1. Passer en revue les P2 - lesquels sont vraiment réalistes ?
   Abandonner ceux qui ne le sont pas.
2. Vérifier que les P1 sont bien priorisées. Si tout est P1, rien
   n'est P1.
3. Les items > 6 mois sans mouvement : abandonner ou rétrograder.

Cycle d'épuration recommandé : 1×/release majeure, sinon au feeling
quand on touche au backlog.

## Lien avec l'agent {{name}}-expert

L'agent expert (cf. `.claude/agents/{{name}}-expert.md`) inclut depuis
sa refonte un output gate « Items backlog identifiés » dans ses modes
implémentation, bug fix et refactor. C'est le mécanisme principal de
capture structurée.

Pour les sessions courtes (Q&A, fix 1-2 lignes), le rappel est dans la
règle ALWAYS-ON de `CLAUDE.md`.

## Lien avec l'auto-enrichissement de la mémoire

Le backlog et l'enrichissement de mémoire sont **distincts** :

- **Backlog** : actions différées (« à faire plus tard »)
- **Enrichissement mémoire** : connaissances acquises (« déjà fait,
  documentation à mettre à jour »)

Cf. [`memory-enrichment.md`](memory-enrichment.md).
