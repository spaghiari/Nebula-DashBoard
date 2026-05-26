# conventions/parallelization

Convention transverse de **parallélisation des appels d'outils** pour
réduire le wall-clock cumulé des sessions Claude. Complément naturel
de la convention `effort-sizing.md` (mesure de l'effort) et du
mécanisme `===CONTEXT===` pré-mâché des sous-agents (livré 4.7.0
grappe « Perf sous-agent »).

## Principe central : multi-tool calls dans un même message

Quand plusieurs appels d'outils sont **indépendants** (résultat de
l'un ne conditionne pas l'entrée d'un autre), les **regrouper dans
un même message** pour qu'ils s'exécutent en parallèle côté runtime
Claude Code. Cas usage typiques :

- N lectures `Read` de fichiers indépendants
- N appels `Grep` sur patterns différents ou globs distincts
- 1 `Bash` (ex: `git status`) + N `Read` de fichiers déjà connus

Au contraire, sérialiser quand :

- L'entrée du 2ème appel dépend de la sortie du 1er (ex: `Grep` pour
  trouver un fichier puis `Read` du résultat)
- Un fail-fast s'impose (ex: `php -l` doit valider la syntaxe avant
  de lancer les autres lints)
- L'appel modifie l'état (`Edit`, `Write`) - mieux vaut séquencer
  pour vérifier l'effet de chaque mutation

## Quand paralléliser - tableau de référence

| Pattern | Parallélisable ? | Comment |
|---|---|---|
| Lecture de N fichiers de mémoire (hubs + spokes selon mots-clés) | ✅ Oui | N `Read` dans un même message |
| Grep ciblés sur patterns différents (ex: 27 pitfalls par catégorie) | ✅ Oui | N `Grep` dans un même message |
| Lecture de N READMEs sous-dossiers (`/readme-sync`) | ✅ Oui | N `Read` dans un même message |
| Audit pitfalls multi-fichiers indépendants | ✅ Oui | Forks parallèles ou multi-`Grep` |
| `git status` + `git diff` + `git log` (3 sondes indépendantes) | ✅ Oui | 1 `Bash` qui chaîne avec `;` ou 3 `Bash` parallèles |
| Lints `lint-views` + `lint-css` + `lint-html` + `lint-js` (après `lint-php` OK) | ✅ Oui | Multi-tool calls après fail-fast PHP |
| `php -l` puis `Edit` du fichier | ❌ Sériel | Fail-fast obligatoire |
| `Grep` pour identifier puis `Read` du résultat | ❌ Sériel | Dépendance de données |
| `Edit` puis `git diff` pour vérifier le résultat | ❌ Sériel | L'effet précède la vérif |
| Mutations API Icinga2 successives (création + lecture pour confirmer) | ❌ Sériel | Idempotence + ordre métier |

## Pattern A : forks parallèles (Agent sans subagent_type)

Pour les sous-tâches lourdes en lecture/grep mais dont le résultat
synthétique tient en quelques lignes, un **fork parallèle** est plus
efficace qu'une lecture intégrée (le fork hérite du contexte parent
en cache, son rapport synthétique revient sans pollution).

Cas usage typique côté `{{name}}-expert` :

```
{{name}}-expert :
  ├─ fork « audit pitfalls profond sur ScopeController.php »
  │     → tableau de violations avec file:line
  ├─ fork « audit pitfalls profond sur HolidayController.php »
  │     → tableau idem
  ├─ fork « lecture des 5 READMEs sous-dossiers à mettre à jour »
  │     → liste des sections à enrichir
  └─ consolide les 3 retours dans le rapport final
```

Limite : **3-4 forks max en parallèle** (cf. `multi-agent.md` §
« Quand NE PAS déléguer »). Au-delà, la coordination devient
difficile et l'overhead par fork (~5-10K tokens de prompt minimal
+ chargement contexte) dépasse le gain.

## Routines parallélisables identifiées (cibles ALWAYS-ON)

Les 4 routines suivantes ont été migrées vers parallélisation
explicite dans leur prompt/instructions respectives :

| Routine | Localisation | Parallélisation |
|---|---|---|
| Lecture lazy par mots-clés `{{name}}-expert` | `.claude/agents/{{name}}-expert.md` § Étape 2 | Multi-`Read` des hubs/spokes correspondant aux mots-clés détectés (typiquement 2-4 fichiers) |
| Audit pitfalls multi-fichiers `{{name}}-pitfall-auditor` | `.claude/agents/{{name}}-pitfall-auditor.md` § Méthode | Multi-`Grep` sur les pitfalls par catégorie (par fichier audité) |
| Scan des READMEs `/readme-sync` | `.claude/commands/readme-sync.md` § Partie 1 | Multi-`Read` des 18 READMEs sous-dossiers |
| Lints orchestrés `/check-all` | `.claude/commands/check-all.md` § Phases | Phase 2 parallélisée (`lint-views` + `lint-css` + `lint-html` + `lint-js`) après Phase 1 (`lint-php` fail-fast) |

D'autres routines pourront être identifiées au fil des sessions et
ajoutées à ce tableau.

## Boucle rétroactive : tracking et identification des hot spots

L'idée : capitaliser sur les sessions passées pour identifier les
patterns chronophages (lectures sérielles qui auraient dû être
parallèles, audits longs qui auraient pu être forkés, etc.) et
proposer des optimisations dans `improvements.md`.

### Convention de tracking obligatoire

**Chaque rapport de livraison sous-agent OU thread principal sur
feature M+ doit inclure** :

- **Wall-clock cumulé** : durée totale en minutes (somme des sous-tâches)
- **Tokens entrants/sortants** : estimation grossière côté
  `{{name}}-expert` ou compteur réel si disponible
- **Compteur d'économie** : tokens économisés vs lecture exhaustive
  (cf. `{{name}}-expert.md` § « Compteur d'économie »)
- **Sous-tâches déléguées** : liste des forks/sous-agents avec
  durée individuelle si mesurable

Format suggéré dans le rapport final :

```
## Effort IA réel

- Wall-clock cumulé : ~14 min ({{name}}-expert ~10 min +
  {{name}}-impl-validator ~4 min)
- Tokens entrants : ~25K côté sous-agent (ex: brief avec
  ===CONTEXT=== pré-mâché)
- Compteur d'économie : ~70-80K tokens vs lecture exhaustive
  (mécanisme ===CONTEXT=== + lecture lazy par mots-clés)
- Sous-tâches : 1 délégation {{name}}-expert + 1 délégation
  {{name}}-impl-validator (séquentielles, pas de fork parallèle)
```

Cette convention est aussi ALWAYS-ON dans `{{name}}-expert.md` §
« Compteur d'économie » (étendue à tous les rapports M+).

### Recette d'analyse rétroactive (audit trimestriel)

Toutes les ~3 mois ou avant une release majeure, audit des stats
des livraisons passées pour identifier les patterns chronophages :

```bash
# Récupérer les commit messages contenant des stats d'effort
git log --grep='Effort IA réel\|wall-clock\|tokens\|Ratio humain' \
    --format='%h %s%n%b' --since='3 months ago'

# Filtrer les livraisons avec wall-clock élevé (>30 min) ou
# ratio humain/IA faible (<5x = potentiel d'amélioration)
git log --grep='wall-clock' --format='%h %s%n%b' \
    --since='3 months ago' \
    | grep -E 'wall-clock|Ratio' \
    | awk '/wall-clock/{wc=$0} /Ratio/{print wc; print $0; print "---"}'
```

Si des patterns chronophages émergent (ex: « les audits
multi-fichiers prennent >20 min wall-clock cumulé »), proposer
une amélioration dans `improvements.md` :

```markdown
- **[TODO YYYY-MM-DD] Optimiser <routine> via parallélisation
  <pattern>** (P2)
  - Constatation : observée sur N livraisons (commits xxx, yyy,
    zzz), wall-clock moyen ~M min sur cette routine
  - Idée : appliquer parallélisation <pattern> identifiée dans
    parallelization.md
  - Bénéfice attendu : -X% wall-clock estimé
```

Cycle vertueux : la mesure alimente l'identification des hot
spots, qui alimentent les optimisations futures, qui réduisent
encore le wall-clock cumulé.

## Anti-patterns

### ❌ Parallélisation aveugle

Tout paralléliser sans réfléchir aux dépendances. Les fail-fast
existent pour de bonnes raisons (`php -l` avant les autres lints
évite des faux positifs sur du code invalide). La convention
exige le **discernement par cas**.

### ❌ Multi-tool calls qui mélangent Read/Edit/Write

Sérialiser les mutations (`Edit`, `Write`, `git commit`) - ne pas
les mettre dans le même message que des lectures. La cohérence de
l'état du filesystem prime sur le gain wall-clock marginal.

### ❌ Forks excessifs

Plus de 4 forks en parallèle pour `{{name}}-expert` rend le
rapport final difficile à synthétiser et augmente le coût total
plus vite que le gain wall-clock. Limite stricte (cf.
`multi-agent.md`).

### ❌ Tracking sans usage

Mesurer le wall-clock et les tokens dans tous les rapports mais
ne jamais en faire l'audit rétroactif. La convention exige le
cycle complet : mesure → analyse → propositions
`improvements.md`.

### ❌ Optimisation prématurée

Paralléliser un appel qui prend déjà <2s ne change rien (le
wall-clock est dominé par d'autres facteurs : la latence runtime
de chaque tool call, l'attente utilisateur entre les rounds).
Réserver la parallélisation aux routines **réellement
chronophages** (>10s wall-clock cumulé sur la sous-tâche).

## Lien avec les autres conventions

| Convention | Lien |
|---|---|
| [`multi-agent.md`](multi-agent.md) | Pattern A des forks parallèles + limite 3-4 sous-agents max |
| [`effort-sizing.md`](effort-sizing.md) | Format obligatoire pour items DONE incluant wall-clock IA + tokens |
| [`memory-enrichment.md`](memory-enrichment.md) | Convention de tracking peut alimenter `improvements.md` |
| [`done-lifecycle.md`](done-lifecycle.md) | L'audit rétroactif est un signal de cristallisation des patterns récurrents |

## Cycle de vie

| Phase | Quand |
|---|---|
| **Identification d'une routine parallélisable** | Au fil des sessions, par observation de wall-clock cumulé |
| **Migration explicite** | MAJ du prompt/instructions de la routine cible (ajout d'une mention « préférer multi-tool calls parallèles ») |
| **Mesure du gain** | Comparaison wall-clock avant/après sur 2-3 livraisons consécutives |
| **Validation** | Si gain ≥ 20% wall-clock confirmé, item DONE dans `improvements.md` ; sinon, retour arrière ou ajustement |
| **Audit rétroactif** | Trimestriel ou avant release majeure (recette ci-dessus) |
