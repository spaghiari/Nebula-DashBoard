---
description: Production proactive d'idées d'amélioration sur `{{label}}` ou ses outils Claude. Format `/brainstorm <topic>` (mode audit-driven obligatoire pour topics code-rattachés) ou `/brainstorm` (sans topic = exploration ouverte). Produit 3-5 idées concrètes avec `file:line` + coût quantifié + scénario. Aucune modification automatique - les idées vont dans `.claude/ideas.md` après validation.
---

Production proactive d'idées d'amélioration. Convention détaillée :
[`.claude/memory/conventions/ideas-generation.md`](../memory/conventions/ideas-generation.md).

Cette commande **ne modifie rien** d'office. Elle produit un rapport
d'idées, à l'utilisateur de décider lesquelles inscrire au registre
`.claude/ideas.md`.

## Modes d'invocation

### `/brainstorm <topic-code-rattaché>` - mode **audit-driven** (obligatoire)

Pour les topics qui ont un correspondant code identifiable dans le
repo, la production d'idées **doit** s'appuyer sur une lecture
systématique du hot path correspondant **avant** de produire les
idées. Sinon le ratio idées-retenues s'effondre.

**Configuration projet** : la table des « hot paths par topic » est
à définir dans `conventions/playbooks.md § Hot paths par topic`
(fichier à créer au bootstrap selon la stack du projet). Format
typique :

| Topic | Hot path à lire avant production d'idées |
|---|---|
| `performance` | (fichiers où la perf compte) |
| `security` | (controllers, validations, auth) |
| `<domaine-x>` | (sous-système concerné) |
| `<sous-système-y>` | (idem) |
| `ui` | (vues, CSS, JS) |
| `tests` | (pas de hot path code, voir mode exploration) |

**Méthode audit-driven** :

1. Lire `CLAUDE.md` + hub `.claude/memory/<thème>.md` correspondant
   au topic.
2. **Lire systématiquement les fichiers du hot path**, pas en survol
   mais en repérant les patterns concrets (boucles N+1, filtres
   tardifs, propagation d'exceptions, manques de validation, etc.).
3. Lire les registres (`ideas.md`, `backlog.md`, `roadmap.md`,
   `improvements.md`) pour anti-doublons et **patterns rejetés**
   (cf. section ci-dessous).
4. Pour **chaque** idée produite, exiger :
   - **`file:line`** précis de la localisation
   - **Coût quantifié** : N appels, M round-trips, K rows, ou délai
     estimé en ms
   - **Scénario concret** : exploit / dégradation observable / cas
     d'usage qui matérialise le besoin
5. Format de sortie aligné sur `ideas.md` (cf. ci-dessous).

### `/brainstorm <topic-libre>` - mode **exploration**

Pour les topics non code-rattachés (`outillage`, `tests`, `product`,
processus, etc.) ou pour les explorations conceptuelles : mode
classique. Réflexion 5-10 minutes sur le sujet, lecture de la mémoire
pertinente, production de 3-5 idées concrètes mais sans exigence de
`file:line`.

### `/brainstorm` (sans argument) - mode **exploration ouverte**

Sans topic, lire l'état du projet (`CLAUDE.md` + hubs pertinents +
fichiers récemment touchés) et produire 3-5 idées variées (mix
projet/outillage) sans contrainte de catégorie.

## Patterns rejetés observés (anti-suggestions)

Cette section est à enrichir au fil des tris utilisateur. Voir la
section équivalente dans
[`conventions/ideas-generation.md`](../memory/conventions/ideas-generation.md)
qui consolide les apprentissages transverses au projet (« ne pas
re-proposer X sauf justification explicite »).

## Critères qualité d'une idée valide

| Critère | Mode audit-driven | Mode exploration |
|---|---|---|
| Constatation factuelle | **`file:line`** précis + observation du code | Référence à un fichier ou pattern identifié |
| Coût / bénéfice | **Quantifié** | Estimé qualitativement |
| Scénario | **Exploit ou dégradation concrète** | Cas d'usage utilisateur |
| Effort | S / M / L estimé | S / M / L estimé |
| Anti-doublon | Vérifié contre les 4 registres + section « Patterns rejetés » | Idem |

Si une idée ne passe pas ces critères : la classer en « exploration
interne, pas à inscrire » dans la recommandation finale.

## Format de sortie

```markdown
## Brainstorm - <topic ou "exploration ouverte">

**Date** : YYYY-MM-DD
**Topic** : <topic>
**Contexte lu** : <fichiers de mémoire consultés>
**Idées produites** : N

### Idée 1 - <catégorie projet/outillage>

- **Titre** : <titre court actionnable>
- **Constatation** : <observation factuelle>
- **Idée** : <description, 2-4 phrases>
- **Bénéfice attendu** : <pour qui, quoi>
- **Effort estimé** : S / M / L
- **Pourquoi pas déjà fait ?** : <freinage perçu, dépendance, etc.>

### Idée 2 - ...

(...)

## Recommandation

Pour chaque idée :
- ✅ **À inscrire au registre** : <titres des idées qui méritent>
- ⚠ **À examiner avant inscription** : <idées avec risque de doublon
  ou freinage>
- ❌ **Brainstorm interne, pas à inscrire** : <idées trop spéculatives
  ou doublons identifiés>

L'utilisateur tranche.
```

## Anti-patterns

- **Inscrire 20 idées vagues** : préférer 3-5 idées concrètes.
- **Doublonner avec les registres existants** : grep avant inscription.
- **Idées sans bénéfice clair** : si on ne peut pas dire à qui ça sert
  et pourquoi, l'idée n'est pas mûre.
- **Auto-inscription** : la commande **ne modifie pas
  `.claude/ideas.md`** automatiquement. Toujours proposer à
  l'utilisateur qui tranche.
- **Skipper la lecture code en mode audit-driven** : pour un topic
  code-rattaché, produire des idées sans avoir lu le hot path → idées
  spéculatives. Si les outils sont bloqués, **dire explicitement** que
  la commande ne peut pas s'exécuter en mode audit-driven plutôt que
  produire un brainstorm classique dégradé.

Lance la réflexion. Produis le rapport. Stop.
