# conventions/roadmap

Pattern de gestion de la roadmap projet (`.claude/roadmap.md`). Permet
de définir et faire évoluer la vision long terme du module avec
contributeurs humains et agents Claude.

## Différence avec backlog et auto-enrichissement

| Système | Horizon | Granularité | Format |
|---|---|---|---|
| **Backlog** ([`backlog.md`](backlog.md)) | Court/moyen terme (< 6 mois) | Action concrète actionnable | Item priorisé P0/P1/P2 |
| **Roadmap** (ce fichier) | Long terme (6 mois - 2 ans+) | Axe stratégique ou jalon de version | Vision + axes + jalons |
| **Auto-enrichissement** ([`memory-enrichment.md`](memory-enrichment.md)) | Présent / immédiat | Connaissance acquise | Documentation versionnée |

Les 3 sont complémentaires et ne se chevauchent pas.

## Structure de la roadmap

```
# Roadmap

## Vision
(1 paragraphe global sur la direction long terme)

## Axes stratégiques
(2-5 axes thématiques, stables sur plusieurs versions)

## Jalons par version
### vX.Y
(items engagés ou en discussion)

## Idées en exploration
(items à mûrir avant engagement)

## Items archivés (livrés)
(historique par version)
```

## Quand ajouter un item à la roadmap

| Signal | Type d'item |
|---|---|
| **Idée d'évolution majeure** : nouvelle feature qui dépasse une release mineure | Item dans « Idées en exploration » ou jalon de version |
| **Refactor structurel** : refonte architecturale, migration de stack | Jalon de version (typiquement vX.0 majeure) |
| **Axe stratégique nouveau** : direction long terme à formaliser | Section « Axes stratégiques » |
| **Décision de mise à l'agenda** d'une feature attendue | Jalon de version (engagement) |

## Quand NE PAS ajouter à la roadmap

- **Action à faire à court terme** (< 1 release) → backlog, pas
  roadmap
- **Bug fix** → fix immédiat, pas roadmap
- **Idée vague non actionnable** (« faire mieux ») → reformuler ou
  refuser
- **Feature déjà en cours** (issue ouverte, MR pending) → pas la peine
- **Item perso** → `CLAUDE.local.md` (gitignored)

## Cycle de vie d'un item roadmap

```
[Idée en exploration] → [Jalon vX.Y] → [Livré (archive)]
        ↓                    ↓
[Abandonné]            [Reporté à vX.Y+1]
```

- **Idée en exploration** : pas d'engagement de version. Maturation.
- **Jalon vX.Y** : engagement de livraison à la version cible.
- **Reporté** : déplacé vers une version ultérieure (ajouter une note
  expliquant pourquoi).
- **Livré** : déplacé dans la section « Items archivés » avec date /
  commit / release.
- **Abandonné** : retiré (raison conservée en commentaire).

## Pattern de proposition à l'utilisateur

Quand un signal est détecté en cours de session (généralement design
ou refactor) :

```
## Items roadmap identifiés

Au fil de cette session, j'ai identifié les axes long terme suivants
qui mériteraient une entrée en roadmap :

1. **Axe stratégique** : <description>
2. **Jalon vX.Y** : <feature engageable à cette version>
3. **Idée en exploration** : <à mûrir avant engagement>

Tu veux les ajouter à la roadmap maintenant, ou plus tard ?
```

L'utilisateur tranche ; si OK, ajout au `.claude/roadmap.md` avec un
commit dédié `doc({{label}}): roadmap - ajoute <résumé>`.

## Anti-patterns

- **Roadmap fourre-tout** : éviter d'y mettre tout et n'importe quoi.
  Les items vagues vont au backlog ou en exploration.
- **Engagements irréalistes** : ne pas mettre dans un jalon vX.Y des
  features qui n'ont pas été chiffrées. Préférer « Idées en
  exploration » jusqu'à validation.
- **Roadmap fantôme** : si elle n'est pas mise à jour 6+ mois, elle
  perd sa valeur. Cycle de revue minimal : 1× par release majeure.

## Lien avec l'agent {{name}}-expert

L'agent expert (cf. `.claude/agents/{{name}}-expert.md`) inclut depuis
sa refonte un output gate « Items roadmap identifiés » dans son mode
design (et optionnellement en refactor) - quand une feature ouvre un
axe stratégique nouveau ou un jalon de version, l'agent le signale.

Pour les sessions courtes, le rappel est dans la règle ALWAYS-ON de
`CLAUDE.md`.

## Cycle de vie de la roadmap

| Phase | Quand |
|---|---|
| **Création** | Bootstrap ou refonte (4.3.0+) |
| **Enrichissement** | À chaque session de design ou décision stratégique |
| **Revue** | 1× par release majeure - épurer les idées obsolètes, archiver les livrés |
| **Refonte** | Si la vision change significativement (rare) |
