# conventions/ideas-generation

Auto-production d'idées par Claude pour améliorer le module
`{{label}}` ou ses propres capacités sur le module. Stade
**pré-engagement** dans le funnel d'évolution.

## Funnel d'évolution

```
[Claude observe une opportunité]
              ↓
[Idée inscrite dans .claude/ideas.md]
              ↓
[Tri par l'utilisateur]
       /      |      \      \
PROMOTED   PROMOTED  PROMOTED  REJECTED
   ↓          ↓         ↓
backlog    roadmap   improvements
(court)    (long)    (outils Claude)
```

`ideas.md` est le **funnel d'entrée**. Les autres registres sont des
sorties après tri.

## Périmètre

### 2 catégories d'idées

| Catégorie | Cible | Exemple |
|---|---|---|
| **Module <Projet>** | Capacités produit côté utilisateur Icinga Web 2 | Tableau de bord santé, export CSV journal, vue diagnostic IDO |
| **Outillage Claude** | Capacités de Claude sur le projet (agents, commands, hooks, mémoire) | Nouveau sous-agent, slash command, hook automation |

### Différence avec les autres systèmes

| Système | Origine | Engagement | Tri |
|---|---|---|---|
| **`ideas.md`** | Claude proactif | Aucun (brainstorm) | À faire par user |
| **`backlog.md`** | Décision user (souvent post-tri d'une idée) | Court/moyen terme actionnable | Déjà trié, prioritaire |
| **`roadmap.md`** | Décision cosignée user/Claude | Long terme structurant | Déjà engagé |
| **`improvements.md`** | Friction observée | Outils Claude | Déjà identifié |

Un item peut entrer dans `ideas.md` puis migrer vers un autre registre
après validation.

## Quand produire une idée

Signaux qui justifient une nouvelle idée :

| Signal | Catégorie probable |
|---|---|
| **Donnée existante mais non synthétisée** dans une vue (par ex. journal + KPIs + état IDO épars) | Module - vue d'agrégation |
| **Workflow répétitif** observé dans une session (par ex. lancer 3 commandes manuellement à chaque review) | Outillage - slash command |
| **Sous-tâche déléguée plusieurs fois** sous forme de fork ad-hoc | Outillage - sous-agent persistant |
| **Friction non bloquante observée par un utilisateur** ailleurs (Slack, ticket) | Module - feature |
| **Pattern récurrent dans le code** qui pourrait être extrait | Module - refactor |
| **Trou dans la couverture pitfalls/lints** | Outillage - extension de slash command ou hook |

## Quand NE PAS produire une idée

- **Pas d'observation factuelle** : si l'idée vient « parce que ce
  serait cool », pas de constatation à étayer → ne pas inscrire.
- **Doublonne une idée existante** : grep `.claude/ideas.md` avant.
- **Action court terme actionnable** déjà identifiée → backlog
  directement, pas le funnel.
- **Item perso ou exploratoire** : `CLAUDE.local.md` (gitignored).
- **Refactor mineur d'un fichier que je suis en train de toucher** :
  faire le refactor inline, pas une idée.

## Format d'une idée

```markdown
- **[STATUT] <titre court actionnable>** (proposée YYYY-MM-DD par
  <author> lors de <contexte session>)
  - Constatation : <observation factuelle - 1-2 phrases ; pour
    topics code-rattachés : `file:line` précis obligatoire>
  - Idée : <description de l'amélioration - 2-4 phrases>
  - Bénéfice attendu : <pour qui, quoi ; pour topics
    code-rattachés : coût quantifié (N appels, M ms, K rows)>
  - Effort estimé : S (< 1 j), M (1-3 j), L (> 3 j)
```

## Critères qualité d'une idée valide

Suite au retour d'expérience post-4.4.0 (7 sessions
`/brainstorm` + 2 audits ciblés) qui a montré un écart
significatif de pertinence entre idées spéculatives et idées
issues d'une lecture systématique du code, les critères de
validité d'une idée sont durcis pour les topics code-rattachés.

| Critère | Topics code-rattachés (perf, security, holiday, journal, ui) | Topics conceptuels (outillage, tests, exploration) |
|---|---|---|
| **Constatation factuelle** | `file:line` précis + observation directe du code | Référence à un fichier ou un pattern identifié |
| **Coût / bénéfice** | Quantifié : N appels API, M round-trips DB, K rows scannées, latence en ms | Estimé qualitativement |
| **Scénario** | Exploit ou dégradation observable (chiffre ou cas d'usage concret) | Cas d'usage utilisateur |
| **Effort** | S / M / L estimé | S / M / L estimé |
| **Anti-doublon** | Vérifié contre `ideas.md` + `backlog.md` + `roadmap.md` + `improvements.md` + section « Patterns rejetés » ci-dessous | Idem |

Une idée qui ne passe pas ces critères doit être classée en
« exploration interne, pas à inscrire » dans la recommandation
finale, ou reformulée jusqu'à passer les critères.

## Patterns rejetés observés (anti-suggestions)

Capturent les apprentissages transverses du tri utilisateur. À
**ne pas** re-proposer sauf justification explicite qui contre-
attaque le rejet précédent.

### Vues transverses d'agrégation à faible VA marginale

2 abandons consécutifs sur la 4.4.0 :

- Vue passation d'astreinte V1 livrée puis retirée pour faible
  VA (cf. `.claude/backlog.md` § Items terminés `[ABANDONED]`).
- Tableau de bord santé du module abandonné sans impl pour la
  même raison.

**Le module privilégie l'enrichissement des vues existantes**
plutôt que de nouvelles vues globales. Exemple positif :
`IdoFreshnessHelper` ajouté en 4.4.0 sur les 3 vues lecture
(badge inline) au lieu d'une vue « santé IDO » dédiée.

Avant de proposer une nouvelle vue transverse / dashboard /
rapport global, vérifier que :
1. Le besoin n'est pas couvert par enrichissement d'une vue
   existante.
2. Le bénéfice utilisateur est explicite (combien d'opérateurs
   utiliseraient effectivement la vue ?).
3. Si validation utilisateur n'est pas évidente, proposer
   l'idée en `[DEFERRED]` avec mention « validation utilisateur
   requise avant impl ».

### Caches cross-request sans signal de charge mesurée

Le module privilégie le cache per-request (simple, pas
d'invalidation) sur le cache cross-request (complexe,
invalidation, staleness, concurrence). Avant de proposer un
cache filesystem/APC TTL, exiger une mesure de charge réelle
qui justifie le coût additionnel.

### Nouvelles permissions ad-hoc

Le RBAC du module est délibérément simple (`scope`,
`scope/manage`, `bulkactions`, `holiday`, `timeperiod`). Avant
de proposer une nouvelle permission `{{label}}/<x>`,
vérifier qu'aucune existante ne couvre le besoin. Préférer
réutiliser `scope` pour la lecture, `scope/manage` pour la
mutation cible scope, `bulkactions` pour l'impact global.

### Durcissement TLS forcé par défaut sur l'API Icinga2

Acceptable tant que l'API cible reste en localhost (risque MITM
réel faible, surface d'attaque limitée à un attaquant local).
À ré-ouvrir si la roadmap v5.0 « Refonte authentification API
Icinga2 » déplace l'API sur un endpoint distant.

Statuts :

| Statut | Sens |
|---|---|
| `[NEW]` | Idée fraîche, en attente de tri user |
| `[DEFERRED]` | Examinée mais reportée. Ajouter raison. |
| `[PROMOTED -> backlog]` | Promue. Lien vers item du backlog. |
| `[PROMOTED -> roadmap]` | Promue. Lien vers axe/jalon roadmap. |
| `[PROMOTED -> improvements]` | Promue. Lien vers item improvements. |
| `[REJECTED]` | Rejetée. Ajouter raison. |

## Modes de production des idées

### Mode 1 : output gate de l'agent `{{name}}-expert`

L'agent ajoute une section « Idées proactives » optionnelle en fin de
mode design / impl / refactor. Si une opportunité a été observée
pendant le travail, propose 1-3 idées. Si rien : ne pas écrire la
section.

### Mode 2 : routine d'auto-amélioration `/self-review`

La routine `/self-review` peut produire des idées en plus des
frictions identifiées (axe 8 optionnel). Cible : axes outillage
Claude principalement.

### Mode 3 : slash command `/brainstorm <topic>`

Sur demande explicite, Claude produit 3-5 idées concrètes sur le
topic. **Mode audit-driven obligatoire** pour les topics
code-rattachés (`performance`, `security`, `holiday`, `journal`,
`ui`) : lecture systématique du hot path correspondant **avant**
production des idées, exigence `file:line` + coût quantifié.
Mode exploration pour les topics conceptuels. Détail :
[`.claude/commands/brainstorm.md`](../../commands/brainstorm.md).

### Mode 4 : Claude principal en cours de session

Si Claude observe une opportunité claire pendant une session normale
(pas dans un agent), il peut proposer d'ajouter une idée au registre
**avant la fin du turn** - jamais d'ajout silencieux.

## Pattern de proposition à l'utilisateur

```
## Idées proactives identifiées

Au fil de cette session, j'ai identifié les opportunités suivantes
qui mériteraient une entrée au registre `.claude/ideas.md` :

1. **<catégorie>** : « <titre> » - <constatation courte>
2. **<catégorie>** : ...

Tu veux les ajouter au registre maintenant, ou plus tard ?
```

L'utilisateur tranche ; si OK, ajout au registre avec un commit dédié
`doc({{label}}): ideas - ajoute <résumé>`.

## Cycle de tri par l'utilisateur

| Phase | Quand |
|---|---|
| **Tri rapide** | Au fil de l'eau quand le user lit le registre, marquer en `DEFERRED` ou `REJECTED` les évidences |
| **Tri profond** | 1× par mois ou avant chaque release majeure (X.Y.0) - examiner chaque idée NEW, décider promotion ou rejet |
| **Épuration** | Si une idée NEW traîne depuis 6+ mois sans décision, la rétrograder en `DEFERRED` ou supprimer (probablement plus pertinente) |

## Pattern de promotion

Quand une idée est promue vers un autre registre :

1. Ajouter l'item dans le registre cible (backlog/roadmap/improvements)
   avec le format propre à ce registre
2. Mettre à jour le statut de l'idée dans `ideas.md` :
   - `[PROMOTED -> backlog]` (ou roadmap/improvements)
   - Ajouter un lien : « Voir : `.claude/backlog.md` § <titre> »
3. Déplacer l'idée dans la section « Idées promues »
4. Commit : `doc({{label}}): promote idea <titre> -> <cible>`

## Anti-patterns

- **Inscrire 20 idées par session** : la production d'idées doit être
  parcimonieuse et factuelle. 1-3 par session max.
- **Idées vagues** (« on devrait faire mieux ») : refuser ou
  reformuler avec une constatation et un effort estimé.
- **Auto-promotion** : Claude n'inscrit JAMAIS une idée directement
  dans backlog/roadmap/improvements - elle passe par le funnel
  `ideas.md` et est triée par l'user.
- **Doublon avec un autre registre** : avant inscription, grep dans
  `backlog.md`, `roadmap.md`, `improvements.md` pour vérifier que
  l'idée n'y est pas déjà.

## Lien avec les autres systèmes

| Système | Lien |
|---|---|
| [`pipeline.md`](pipeline.md) | Stage 1 (IDEAS) du pipeline unifié. Toute promotion passe par les transitions documentées dans le pipeline |
| [`backlog.md`](backlog.md) | Cible de promotion pour les idées court/moyen terme actionnables |
| [`roadmap.md`](roadmap.md) | Cible de promotion pour les idées long terme structurantes |
| [`self-improvement.md`](self-improvement.md) | Cible de promotion pour les idées d'outillage Claude (`.claude/improvements.md`) |
| [`memory-enrichment.md`](memory-enrichment.md) | Si une idée se concrétise et qu'un nouveau pattern émerge, enrichir la mémoire en plus de l'item promu |
| [`multi-agent.md`](multi-agent.md) | Sous-agent `{{name}}-impl-validator` (idée actuelle) ou autres futurs sous-agents passent par ce funnel |
