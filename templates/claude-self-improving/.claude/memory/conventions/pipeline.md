# conventions/pipeline

Pipeline interne unifié d'auto-amélioration du projet
`{{label}}`. Orchestre les **4 registres d'engagement** versionnés
(`ideas`, `backlog`, `roadmap`, `improvements`) en un flux séquentiel
qui couvre :

1. **Production** d'idées (Claude proactif)
2. **Validation** par l'utilisateur (tri et engagement)
3. **Implémentation** des items validés
4. **Amélioration continue** (capture des frictions, retour au pipeline)

## Vue d'ensemble du pipeline

```
[IDEAS]            [VALIDATED]            [IN PROGRESS]            [DONE]
  ↓                   ↓                       ↓                      ↓
production          tri user             commit start           livraison
proactive          + décision           (début travail)         + commit final
(Claude)           promotion             par user/Claude         + archivage
                                        + référence branche
                                          ou commits

(.claude/ideas.md)  (.claude/{backlog,    (statut `[IN PROGRESS]`  (statut `[DONE
                    roadmap,             dans le registre cible)   YYYY-MM-DD]`
                    improvements}.md)                              + section
                                                                   archivée)
```

Les 4 registres existants gardent leur focus :

| Registre | Cible / Horizon | Stage typique des items |
|---|---|---|
| `ideas.md` | Toutes catégories, pré-engagement | IDEAS uniquement |
| `backlog.md` | Projet produit, court/moyen terme | VALIDATED / IN PROGRESS / DONE |
| `roadmap.md` | Projet produit, long terme structurant | VALIDATED (jalons) / IN PROGRESS (jalon en cours) / DONE (archivé par version) |
| `improvements.md` | Outils Claude (commands, hooks, mémoire, agents) | VALIDATED / IN PROGRESS / DONE |

> **Note sur le 5ème registre `digests/`** : il n'appartient **pas**
> à ce pipeline d'engagement. Il vit dans un flux séparé (agrégation
> hebdomadaire des signaux produits par les 4 autres registres +
> sessions + commits). Le digest **agrège** les transitions de stage
> de la semaine ; il ne **produit** pas de nouveaux items. Doctrine
> séparée : [`digests.md`](digests.md).

## Stages détaillés

### Stage 1 - IDEAS (production)

**Source unique** : `.claude/ideas.md` (registre pré-engagement).

**Acteurs** : Claude proactif (au fil des sessions, via output gate
de l'agent `{{name}}-expert`, ou via slash command `/brainstorm`).

**Format** : voir [`ideas-generation.md`](ideas-generation.md). Items
en `[NEW]`, parcimonieux (1-3 par session max), avec constatation
factuelle, bénéfice, effort estimé.

**Transition vers stage 2** : tri par l'utilisateur (cycle
mensuel + avant release majeure). Items NEW deviennent :
- `[PROMOTED -> backlog]` (promotion vers stage 2 backlog)
- `[PROMOTED -> roadmap]` (promotion vers stage 2 roadmap)
- `[PROMOTED -> improvements]` (promotion vers stage 2 improvements)
- `[DEFERRED]` (reste à stage 1, à réexaminer plus tard)
- `[REJECTED]` (sort du pipeline)

### Stage 2 - VALIDATED (engagement)

**Sources** : `.claude/backlog.md` (court/moyen terme), `roadmap.md`
(long terme), `improvements.md` (outils Claude). Items en `[TODO]`.

**Acteurs** : utilisateur (décision d'engagement + priorisation).
Claude peut suggérer la priorité initiale lors de la promotion mais
le user tranche.

**Format** : conforme au registre cible (voir conventions
[`backlog.md`](backlog.md), [`roadmap.md`](roadmap.md),
[`self-improvement.md`](self-improvement.md)). Au minimum : titre,
contexte, détail, priorité (P0/P1/P2 pour backlog/improvements).

**Transition vers stage 3** : décision de démarrage par
l'utilisateur (« on attaque cet item »). Item passe de `[TODO]` à
`[IN PROGRESS]`.

### Stage 3 - IN PROGRESS (implémentation)

**Source** : item dans son registre (backlog/roadmap/improvements)
avec statut `[IN PROGRESS]`.

**Acteurs** : Claude (implémente sous validation user) ou utilisateur
direct.

**Format** : statut `[IN PROGRESS]` remplace `[TODO]`. Métadonnées
ajoutées :

```markdown
- **[IN PROGRESS] <titre>** (P1, ajouté 2026-MM-DD)
  - Contexte : ...
  - Détail : ...
  - **Démarré** : 2026-MM-DD
  - **Branche** : `feature/xxx` ou `main` directement (selon ampleur)
  - **Commits** : <commit1>, <commit2>, ... (au fil de l'eau)
```

**Transition vers stage 4** : commit final (livraison). Item passe
de `[IN PROGRESS]` à `[DONE YYYY-MM-DD]`. Référence au commit final
ajoutée. Si nécessaire, item déplacé dans la section « Items
terminés » du registre.

### Stage 4 - DONE (livraison)

**Source** : item archivé dans son registre d'origine, section
« Items terminés ».

**Format** (pratique systémique post-4.4.0) :

```markdown
- **[DONE 2026-MM-DD] <titre>** (P1)
  - Cibles livrées : <fichiers touchés avec ~lignes nettes>
  - Action effectuée : <résumé synthétique>
  - Bénéfice : <ce que ça apporte>
  - Validation : <php -l clean / grep d'audit / autres checks>
  - Tests manuels recommandés : <checklist ciblée à dérouler en
    pré-prod>
  - Démarré : YYYY-MM-DD
  - Branche : `main` ou `feature/xxx`
  - Commits : `<hash1>` (IN PROGRESS), `<hash2>` (impl),
    commit de clôture (cet item)
```

**La rubrique « Tests manuels recommandés » est obligatoire** sur
les items DONE qui touchent du code module produit (controller,
presenter, vue, API, IDO). Le module n'a pas de suite de tests
automatisés - la rubrique consolide la checklist de validation
manuelle à dérouler avant un déploiement prod.

Format de la checklist tests manuels :

- 1 ligne par cas à tester (cas nominal + cas dégradé + cas
  limite)
- Étapes UI (« naviguer vers `<route>`, vérifier `<comportement>` »)
- Vérifications côté Icinga2 si la mutation a un effet API (« via
  `icinga2 console`, dans Icinga Web 2 Monitoring, ou dans le
  journal `{{label}}` »)
- Cas de régression spécifiques à vérifier

**Transition** : aucune. L'item est archivé. Si problème
post-livraison (régression, friction nouvelle), créer un
**nouvel item** (amélioration continue) qui rentre via stage 1
(idée) ou stage 2 (item direct si évident).

## Règles de transition

| De | Vers | Déclencheur | Acteur |
|---|---|---|---|
| Rien | IDEAS | Observation proactive (output gate, brainstorm, session) | Claude (toujours avec proposition au user) |
| IDEAS | VALIDATED | Tri user (mensuel ou avant release) | User |
| IDEAS | DEFERRED | Tri user, item pas mûr | User |
| IDEAS | REJECTED | Tri user, item rejeté avec justification | User |
| DEFERRED | VALIDATED | Réexamen user, idée mûrie | User |
| DEFERRED | REJECTED | Réexamen user, plus pertinente | User |
| VALIDATED | IN PROGRESS | Décision de démarrage | User (« on attaque cet item ») |
| IN PROGRESS | DONE | Commit final, validation | User (souvent via commit final) |
| IN PROGRESS | BLOCKED | Dépendance externe ou décision en attente | User ou Claude (avec justification) |
| BLOCKED | IN PROGRESS | Déblocage | User |
| Tout stage | ABANDONED | Décision d'abandon (rare) | User |

## Garde-fous

### Le hook `improvements-validate.sh`

Vérifie au commit que les statuts utilisés dans
`.claude/improvements.md` et `.claude/backlog.md` sont dans la
whitelist : `TODO`, `IN PROGRESS`, `BLOCKED`, `DONE`, `ABANDONED`,
`DONE YYYY-MM-DD`. Le statut `[IN PROGRESS]` est donc déjà couvert.

Cf. [`hooks.md § improvements-validate`](hooks.md).

### Pas d'auto-promotion par Claude

Claude **ne promeut jamais** une idée directement de stage 1 vers
stage 2 ou de stage 2 vers stage 3 sans validation user explicite.
Toute transition à conséquence d'engagement passe par le user.

Exception unique : Claude peut **proposer** la transition (« je peux
démarrer cet item maintenant ? ») mais c'est le user qui dit oui.

### Pas de stage skip

Un item ne peut pas passer directement de IDEAS à DONE. Il doit
suivre les 4 stages. Cas d'usage exceptionnel (fix 1 ligne) : pas
besoin du pipeline du tout, traiter direct sans inscription. Le
pipeline est pour les améliorations qui méritent traçabilité.

### Une seule source de vérité par item

Un item vit dans **un seul registre à la fois** (sauf transition
ponctuelle où il est marqué PROMOTED dans `ideas.md` avec lien vers
le registre cible). Pas de duplication.

## Slash command `/pipeline`

Vue synthétique de l'état des 4 registres en un coup d'œil. Affiche :

- Compte d'items par stage (IDEAS / VALIDATED / IN PROGRESS / DONE
  récents)
- Items en `[IN PROGRESS]` actuellement (par registre)
- Items VALIDATED prêts à démarrer (par priorité)
- Suggestions d'actions : « Tu as 3 items VALIDATED en P1, tu veux
  en démarrer un ? », « Item X en IN PROGRESS depuis 30 jours, à
  débloquer ? »

Read-only - ne modifie rien. Cf.
[`commands.md`](commands.md) pour les détails d'invocation.

## Lien avec les autres systèmes

| Système | Lien |
|---|---|
| [`ideas-generation.md`](ideas-generation.md) | Stage 1 du pipeline (production proactive) |
| [`backlog.md`](backlog.md) | Stages 2-4 pour les items court/moyen terme module |
| [`roadmap.md`](roadmap.md) | Stages 2-4 pour les items long terme structurants |
| [`self-improvement.md`](self-improvement.md) | Stages 2-4 pour les items outils Claude |
| [`memory-enrichment.md`](memory-enrichment.md) | Côté droit du pipeline : si une livraison fait émerger un nouveau pattern, enrichir la mémoire en plus de marquer DONE |
| [`commands-and-hooks.md`](commands-and-hooks.md) | Maintenance des outils du pipeline (`/brainstorm`, `/self-review`, `/pipeline`, hook validate) |
| [`digests.md`](digests.md) | 5ème registre (hebdomadaire) qui **agrège** les transitions de stage du pipeline. Pas de flux d'engagement propre, mais consomme l'historique du pipeline pour produire les digests verticaux. |

## Cycle de revue du pipeline

Trimestriellement ou avant chaque release majeure :

1. Lancer `/pipeline` pour avoir la vue globale
2. Items IN PROGRESS depuis > 30 jours : à débloquer ou rétrograder
3. Items DEFERRED depuis > 6 mois : abandonner ou ré-examiner
4. Items DONE récents : vérifier qu'ils ont bien été archivés et
   commités
5. Items VALIDATED non engagés : re-prioriser ou retirer si plus
   pertinents

## Anti-patterns

- **Item bloqué sans suivi** : un item `[IN PROGRESS]` qui ne bouge
  pas pendant 30+ jours doit être marqué `[BLOCKED]` avec raison.
- **Skip de stage** : un item DONE sans avoir été VALIDATED → pas
  de traçabilité de la décision. Toujours passer par le pipeline.
- **Item dupliqué entre registres** : un seul registre par item
  vivant.
- **Auto-engagement** : Claude qui démarre un item IN PROGRESS sans
  validation user → contournement du gating.
- **Pipeline bypass total** : si on commits ad-hoc sans inscrire
  d'item, on perd la traçabilité. Le pipeline est pour les items
  qui méritent ce suivi (toutes améliorations non triviales).
