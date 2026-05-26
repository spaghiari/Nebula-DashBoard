# conventions/digests

Pattern de gestion du **5ème registre** : les digests hebdomadaires.
Le registre `digests/` matérialise la **couche verticale d'échange
d'information** entre un contributeur et sa hiérarchie : ce qu'il
produit chaque semaine, ce qu'il reçoit du dessus, et ce qu'il voit
remonté de lui à l'étage supérieur.

C'est le registre qui distingue un projet d'équipe d'un projet solo.
Sur un projet mono-mainteneur, il peut rester inactif.

## Principe directeur

Le digest hebdomadaire n'est **pas** un compte-rendu produit à la
main, ni un tail de transcripts à condenser. C'est une **agrégation
automatique** de signaux déjà structurés par le reste du système :

- diffs des 4 registres (`ideas`, `backlog`, `roadmap`,
  `improvements`) sur la semaine,
- cristallisations mémoire récentes (`memory/<thème>.md` enrichies),
- output gates produits par les agents (idées proactives, items
  identifiés, enrichissements proposés, tests manuels recommandés),
- commits significatifs (sujets et scopes) et items DONE.

Les transcripts bruts ne sont consultés qu'**en complément**, pour
combler ce qui n'a pas été capté par les 3 sources ci-dessus.

## Trois sous-flux

Un même contributeur peut être à la fois producteur et destinataire.
Le registre encode trois sous-flux distincts :

| Sous-flux | Origine | Destination | Fichier |
|---|---|---|---|
| **Outgoing** | Soi-même (compileur agrégé) | Hiérarchie N+1 | `digests/<YYYY-WW>-out.md` |
| **Incoming** | Subordonnés N-1 (un fichier par personne) | Soi-même (manager) | `digests/<YYYY-WW>-in/<author>.md` |
| **Transparency** | Hiérarchie N+1 (citation de soi dans son digest) | Soi-même (transparence symétrique) | `digests/<YYYY-WW>-mirror.md` |

Le **mirror** est ce qui implémente la règle de symétrie de
visibilité documentée dans la doctrine système (cf. discussion de
conception de la pyramide) : ce que ton manager remonte de toi à
son N+1 doit pouvoir être relu par toi.

## Quand un digest est produit

| Cadence | Producteur | Déclencheur |
|---|---|---|
| Hebdomadaire (vendredi soir ou lundi matin) | Agent compileur (cf. `{{name}}-digest-compiler` à créer) | Manuel via slash command `/digest-week`, ou automatisable via cron |
| Sur événement (incident majeur, livraison release) | Idem | Manuel via `/digest-event <description>` |
| Trimestriel (rétrospective) | Idem en mode étendu | `/digest-quarter` |

Le présent fichier décrit le digest **hebdomadaire** uniquement. Les
variantes événementielles et trimestrielles héritent du même schéma
avec ajustements de profondeur.

## Format d'un digest outgoing

```markdown
# Digest <YYYY-WW> — <author>

Période : lundi <YYYY-MM-DD> → dimanche <YYYY-MM-DD>
Producteur : <author>
Destinataire(s) : <N+1>
Compilé : <YYYY-MM-DD HH:MM> par <agent-compiler> (<modèle>)
Sources : <N transcripts agrégés>, <N items registres>, <N commits>

## Travaux livrés

(Items DONE de la semaine, agrégés depuis `backlog.md` et
`improvements.md`. Format compact, 1 ligne par item, avec lien vers
le commit.)

- **<titre court>** (taille, effort estimé Xh humain / Y min IA, ratio
  Z×) — <fichiers principaux touchés> — commit `<hash>`

## Idées poussées (non discutées à l'oral)

(Items ajoutés à `ideas.md` cette semaine en statut [NEW]. Marqués
comme « non discutés » s'ils n'apparaissent pas dans les notes de
réunion. Survivent à plusieurs cycles : ré-inclus dans les digests
suivants tant qu'ils restent [NEW].)

- **<titre>** (proposée <YYYY-MM-DD>, statut NEW) — <constatation
  courte>

## Travaux en cours

(Items [IN PROGRESS] dans backlog/roadmap/improvements.)

- **<titre>** (priorité, démarré <YYYY-MM-DD>, blocage si applicable)

## Directives reçues et appliquées cette semaine

(Items VALIDATED en début de semaine qui sont passés à IN PROGRESS ou
DONE. Trace de la « redescente » exécutée.)

- **<directive>** (source : digest N+1 du <YYYY-WW-1>) → <action prise>

## Demandes implicites au N+1

(Décisions en attente, arbitrages demandés, ressources nécessaires.
Sont remontées comme **demandes**, pas comme statut.)

- **<demande>** — <pourquoi maintenant>

## Patterns transverses détectés

(Insights produits par le corrélateur d'agent : sujets qui croisent
plusieurs domaines/équipes, doublons, contradictions. Optionnel.)

- **<pattern>** — <croise <domaine A> et <domaine B>>

## Enrichissements mémoire de la semaine

(Cristallisations validées dans `memory/<thème>.md`. Synthèse 1 ligne
par enrichissement.)

- `pitfalls/<catégorie>.md` : <nouveau pattern documenté>
- `conventions/<thème>.md` : <nouvelle règle codifiée>

## Métriques

- Effort total semaine : ~X h humain équiv. / ~Y min IA wall-clock
- Tokens consommés : ~Z K
- Ratio humain/IA cumulé : ~W×
- Items DONE : N / IN PROGRESS : M / Idées nouvelles : K
```

## Format d'un digest incoming

(Reçu d'un subordonné, lu par le manager.)

Le **format est identique au format outgoing** (le digest est le
même artefact - c'est le destinataire qui change). Le manager reçoit
1 fichier par subordonné dans `digests/<YYYY-WW>-in/<author>.md`.

## Format d'un digest mirror

(Citation de soi dans le digest du N+1.)

```markdown
# Digest <YYYY-WW> — comment je suis cité par <N+1>

Source : `digests/<YYYY-WW>-out.md` de <N+1>
Reçu : <YYYY-MM-DD>

## Citation

(Extrait littéral du digest du N+1 qui me concerne. L'agent
compileur du N+1 produit son propre digest outgoing en agrégeant les
digests incoming de ses subordonnés - chaque subordonné peut donc
voir sa propre citation.)

> <extrait>

## Comparaison avec mon digest outgoing

(Diff résumé : ce qui a été retenu, ce qui a été condensé, ce qui a
été ajouté par interprétation du N+1. Permet de détecter les
distorsions cumulatives en cascade.)

- **Retenu** : <items reportés intégralement>
- **Condensé** : <items résumés en 1 phrase>
- **Reformulé** : <items dont la formulation a changé, avec écart
  signalé>
- **Omis** : <items présents dans outgoing absents du mirror>
- **Ajouté** : <interprétation du N+1 non présente dans l'outgoing>
```

Le mirror n'est **pas** produit automatiquement par défaut : il
implique un coût (lire le digest du N+1, le grep pour son propre
nom, produire la comparaison). Activer via slash command
`/digest-mirror` quand on veut vérifier.

## Charte éditoriale du compileur

L'agent qui produit le digest fait des choix éditoriaux. Pour éviter
la dérive et garantir la comparabilité d'une semaine à l'autre,
**ces choix sont codifiés** :

### À préserver toujours

- Toute **idée originale** ajoutée à `ideas.md` (même si pas poussée
  à l'oral - c'est précisément le point)
- Toute **décision actée** dans un item passé à DONE
- Tout **blocage signalé** (item IN PROGRESS → BLOCKED ou demande au
  N+1)
- Toute **directive reçue** et son traitement
- Tout **enrichissement mémoire** validé
- Toute **demande implicite** au N+1 identifiée

### À agréger ou résumer

- **Statuts opérationnels** récurrents (« j'ai continué le travail
  sur X »)
- **Sujets répétitifs** entre transcripts
- **Workflows habituels** (revues, lints, releases routinières)

### À supprimer

- **Explorations ratées** sans suite
- **Brainstorming non concluant** sans inscription en `ideas.md`
- **Conversations purement personnelles** (météo, vie privée)
- **Sessions de debug stériles** sans pattern retenu

### Cas litigieux

Si l'agent hésite à inclure ou non, **inclure et marquer**
explicitement : `[à arbitrer]` à la fin de la ligne. Le destinataire
tranche à la lecture.

## Anti-patterns

### ❌ Digest produit en mode roman

Le digest n'est pas une narration. C'est une **liste structurée
agrégée**. Si le compileur écrit en prose libre, il invente. Le
format ci-dessus est strict.

### ❌ Inclusion de verbatim transcript

Les transcripts bruts ne **figurent pas** dans le digest. Ils sont
**lus** par le compileur, qui en extrait des items structurés. Si on
ressent le besoin d'inclure du verbatim, c'est que la matière première
n'a pas été correctement triée par les autres registres en amont -
remonter la friction comme item `improvements.md`.

### ❌ Cascade lossy non documentée

Quand un manager produit son propre outgoing en agrégeant les
incoming de ses subordonnés, **chaque citation doit pointer vers la
source** (`from: digests/<YYYY-WW>-in/<author>.md`). Sans ça,
l'historique remonte au N+2 sans traçabilité - le drill-down devient
impossible.

### ❌ Production silencieuse

Comme tout le reste du système, le digest est **proposé à
l'utilisateur** avant publication. L'agent compileur produit un
draft, l'utilisateur valide ou amende, puis le digest est commit.
Pas d'envoi automatique au N+1.

### ❌ Surveillance déguisée

Le digest n'est **pas un outil de mesure individuelle de productivité**.
Sa fonction explicite : faire émerger des idées non poussées, faciliter
les décisions de N+1, tracer les directives. Si l'agent compileur
produit des indicateurs qui ressemblent à une notation individuelle
(« productivité : X items/semaine ») → ces indicateurs sont **retirés**
du format. Les métriques d'effort (humain équiv. / IA / ratio) sont là
pour suivre le ROI Claude, pas pour comparer des humains entre eux.

### ❌ Digest sans transparency mirror activé

Si le système est utilisé en mode hiérarchique réel (multi-niveau),
**la transparence symétrique n'est pas optionnelle**. Le mirror doit
être consultable par le subordonné à tout moment. Côté juridique
(droit du travail, RGPD), c'est la principale digue contre la
qualification de dispositif de surveillance. Cf.
[`memory-classification.md`](memory-classification.md) sur le rôle
de la doctrine vis-à-vis des risques RH/légaux.

## Cycle de vie d'un digest

```
[Brouillon agent] → [Validé user] → [Publié (commit)] → [Référencé semaines suivantes] → [Archivé > 90 jours]
```

| Statut | Position |
|---|---|
| Brouillon agent | Pas inscrit (en buffer de session) |
| Validé user | Inscrit dans `digests/<YYYY-WW>-out.md`, commit dédié |
| Publié | Idem - le commit le marque comme livré au N+1 |
| Référencé | Les digests suivants peuvent y faire référence (drill-down vers les sources via les liens) |
| Archivé | Déplacé dans `digests/archive/<YYYY>/` après 90 jours, cf. `done-lifecycle.md` |

## Pattern de proposition à l'utilisateur

À la fin de la semaine (ou sur invocation `/digest-week`) :

```
## Digest hebdomadaire <YYYY-WW> — draft

Période : <YYYY-MM-DD> → <YYYY-MM-DD>
Sources lues : N transcripts, M items registres, K commits.

<draft du digest au format ci-dessus>

Quelques choix éditoriaux qui méritent ton arbitrage :
1. <item litigieux 1> — inclus / à arbitrer
2. <item litigieux 2> — omis / à arbitrer

Tu veux publier ce digest tel quel, l'amender, ou repartir de zéro ?
```

L'utilisateur tranche ; si OK, commit dédié :
`doc({{label}}): digest <YYYY-WW> de <author>`.

## Cycle de revue de la doctrine elle-même

| Phase | Quand |
|---|---|
| **Création** | Bootstrap du registre (mise en place du système multi-personne) |
| **Enrichissement** | À chaque session où l'agent compileur observe une friction (item dans `improvements.md`) |
| **Audit trimestriel** | Re-lire les digests des 13 dernières semaines, identifier les distorsions cumulatives (cascade lossy non détectée, items omis répétitivement) |
| **Refonte** | Si le pattern d'usage change (par ex. passage d'une cadence hebdo à bi-hebdo) |

## Lien avec les autres conventions

| Convention | Lien |
|---|---|
| [`pipeline.md`](pipeline.md) | Le digest agrège les transitions IDEAS/VALIDATED/IN PROGRESS/DONE de la semaine. Le pipeline reste la **source unique de vérité** pour le statut des items - le digest ne fait que les agréger. |
| [`memory-enrichment.md`](memory-enrichment.md) | Les cristallisations mémoire de la semaine sont reportées dans la section « Enrichissements mémoire » du digest. |
| [`memory-classification.md`](memory-classification.md) | Le digest est **toujours** projet versionné (pas user-locale). Le test à 3 questions s'applique trivialement (un autre dev de l'équipe doit pouvoir le lire). |
| [`done-lifecycle.md`](done-lifecycle.md) | Les digests > 90 jours sont archivés dans `digests/archive/<YYYY>/` selon le même cycle de vie que les autres registres. |
| [`effort-sizing.md`](effort-sizing.md) | Les métriques en bas du digest reprennent les conventions de mesure : taille, effort humain équiv., effort IA wall-clock, tokens, ratio. |
| [`ideas-generation.md`](ideas-generation.md) | Les idées NEW de la semaine sont la matière première du digest. Le compileur ne reformule pas - il copie/cite avec lien. |
| [`self-improvement.md`](self-improvement.md) | Si le compileur observe une friction sur lui-même pendant la production d'un digest, item à inscrire dans `improvements.md`. |
| [`multi-agent.md`](multi-agent.md) | L'agent compileur (`{{name}}-digest-compiler` à créer si projet d'équipe) est un sous-agent persistant dédié, avec output gate standardisé. |
