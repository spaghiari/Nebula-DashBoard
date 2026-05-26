# conventions/effort-sizing

Conventions de mesure de l'effort des features et modifications du
projet : barème de tailles XXS → XXL avec critères, et comparatif
effort humain vs effort IA (temps réel Claude) pour les items DONE.

## Barème de tailles - 7 catégories

| Taille | Lignes nettes | Fichiers touchés | Durée humaine équiv. | Durée Claude wall-clock | Caractéristiques |
|---|---|---|---|---|---|
| **XXS** | <10 L | 1 | <15 min | <2 min | Typo, fix em-dash, accent oublié, 1 ligne ALWAYS-ON ajoutée |
| **XS** | 10-30 L | 1-2 | 15-30 min | 2-5 min | Fix 1 line bug + lint, 1 nouveau item registre, ajout d'1 case dans un switch |
| **S** | 30-100 L | 2-4 | 30 min-2 h | 5-15 min | Petite feature, ajout 1 méthode + son test, 1 nouveau slash command simple |
| **M** | 100-500 L | 4-15 | 2-6 h | 15-45 min | Feature standard (controller + vue + helper + doc), refacto ciblé, post-mortem riche |
| **L** | 500-1500 L | 15-30 | 6-15 h | 45 min-2 h | Refonte UX large, nouveau sous-système, refacto transverse, intégration API |
| **XL** | 1500-3500 L | 30-60 | 15-40 h | 2-5 h | Architecture nouvelle, sous-système complet, migration majeure |
| **XXL** | >3500 L | >60 | >40 h | >5 h | Refonte structurelle d'un module entier, migration majeure de version Icinga2 |

### Estimation avec marge ±

Pour les items en design (avant impl), inscrire l'effort comme
**X (± Y)** où Y reflète l'incertitude :

- **Connue** : périmètre clair, pattern reproductible, dépendances
  identifiées -> ± 20% maximum (ex: « M (~3 h ± 30 min) »).
- **Modérée** : périmètre précis mais design partiel, ou dépendance
  externe à valider -> ± 50% (ex: « M (~3 h ± 1 h 30) »).
- **Forte** : périmètre flou, exploration nécessaire, plusieurs
  designs possibles -> ± 100% ou ouvrir à la taille supérieure
  (ex: « M ou L selon arbitrage », ou « M (~3 h ± 3 h) »).

Si l'incertitude vaut une catégorie complète (ex: « M ou L »),
**ouvrir le design** avant d'engager : produire un doc de design
court qui réduit l'incertitude à ± 50% maximum, puis engager.

## Découpage des features XL+ en étapes plus petites

**Règle stricte** : aucune feature XL ou XXL ne doit être engagée
en une seule livraison continue. **Découper obligatoirement** en
étapes M ou L livrées individuellement.

### Recettes de découpage

| Type de feature XL+ | Pattern de découpage |
|---|---|
| Refonte UX d'un module | Vague 1 (ex: palette + réorganisation) -> Vague 2 (ex: composants + colonnes) -> Vague 3 (cards collapsibles, etc.). 1 vague par étape M-L. |
| Nouveau sous-système | Étape 1 = squelette + 1 fonctionnalité minimale. Étape 2-N = enrichissement progressif. Chaque étape livrable et testable seule. |
| Migration de version | Étape 1 = compat shim + tests. Étape 2 = bascule progressive par sous-module. Étape 3 = retrait du shim. |
| Refacto transverse | Étape 1 = nouveau pattern + 1 caller migré. Étape 2-N = migration des autres callers. Étape finale = retrait de l'ancien pattern. |

### Indicateurs de besoin de découpage

Si tu détectes au design qu'une feature dépasse :

- **>15 fichiers touchés** : signal fort, découper.
- **>500 L nettes anticipées** : signal fort, découper.
- **>6 h estimées (humain équiv.)** : signal fort, découper.
- **3+ axes fonctionnels indépendants** dans une même feature
  (ex: « refonte UX vague 1 = palette + réorganisation + danger
  zone ») : OK si l'utilisateur les valide groupés, sinon
  découper.

## Comparatif effort humain vs effort IA

Pour chaque item **DONE** dans `.claude/backlog.md` ou
`.claude/improvements.md`, inscrire **2 mesures complémentaires** :

| Champ | Description | Source |
|---|---|---|
| **Effort humain équivalent** | Temps qu'un développeur senior aurait passé à livrer cette feature seul, design + impl + tests + doc | Estimation projetée (taille du barème) |
| **Effort IA réel** | Temps wall-clock cumulé de toutes les sessions Claude qui ont contribué (lecture + design + impl + validation) | Mesure post-livraison (notes de session) |

### Format dans les items DONE

```markdown
- **[DONE 2026-MM-DD] <titre>** (Pn, ...)
  - ...
  - **Effort estimé** : <taille> (~Xh humain équiv. ± Y)
  - **Effort IA réel** : ~Z min wall-clock Claude, ~W K tokens
  - **Ratio humain/IA** : ~XX× (ex: 3 h humain / 30 min IA = 6×)
  - ...
```

### Comment mesurer l'effort IA réel

Sources disponibles côté Claude Code :

- **Durée wall-clock** : timestamps des messages utilisateur début/fin
  de session approximatifs. Pour les sessions longues multi-turn,
  noter à la livraison « N min cumulés sur M turns ».
- **Tokens consommés** : visible via la status line (si configurée
  pour) ou via les rapports de fin de session des sous-agents
  (`<usage>total_tokens: ... duration_ms: ...</usage>` dans la
  trace de retour).
- **Délégations sous-agents** : à additionner explicitement (ex:
  `{{name}}-expert` ~30 min + `{{name}}-impl-validator` ~5 min + thread
  principal ~20 min = ~55 min wall-clock total).

### Pourquoi mesurer

À court terme : conscience du coût (durée + tokens) vs gain humain
sur chaque livraison. Permet d'ajuster le pattern de délégation
(ex: éviter `{{name}}-expert` pour des features S où le coût
d'invocation dépasse le gain).

À long terme : statistiques cumulées qui matérialisent le **ROI
Claude vs humain** sur la maintenance du module. Données pour
décider d'investir dans des optimisations sous-agent (cf.
improvements.md « optim contexte {{name}}-expert »).

## Anti-patterns

- **Inscrire un effort sans taille** (« ~2h » sans « S » ou « M ») :
  le barème permet la cohérence inter-items et la comparaison.
  Toujours préfixer par la taille.
- **Engager une feature XL en une seule livraison** : viole la règle
  stricte. Découper.
- **Estimer humain mais oublier l'IA réel** : empêche le ratio. Si
  l'IA réel n'est pas mesuré (ex: livraison hors session Claude),
  noter explicitement « IA réel : non mesuré ».
- **Surestimation systématique de la marge ±** : plus de 50% de
  marge = signal de design insuffisant, ouvrir le design ou changer
  la taille catégorielle.

## Application rétroactive

Les items DONE déjà existants dans `backlog.md` /
`improvements.md` n'ont pas le champ « Effort IA réel ». Ne pas
backporter rétroactivement (perte de temps, données peu fiables).
La convention s'applique **à partir des nouveaux items DONE**
(post-2026-05-10).

Pour les items refacto en cours (DONE depuis quelques jours
seulement, mémoire des sessions encore fraîche), enrichir si
opportun mais pas obligatoire.
