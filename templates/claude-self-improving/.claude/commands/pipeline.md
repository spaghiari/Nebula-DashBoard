---
description: Vue synthétique du pipeline d'auto-amélioration. Compte d'items par stage dans les 4 registres d'engagement (`ideas`, `backlog`, `roadmap`, `improvements`), résumé des digests récents (5ème registre). Lecture seule, ne modifie rien.
---

Vue synthétique de l'état du pipeline d'auto-amélioration en un coup
d'œil. Conventions :
[`.claude/memory/conventions/pipeline.md`](../memory/conventions/pipeline.md)
(4 registres d'engagement) et
[`.claude/memory/conventions/digests.md`](../memory/conventions/digests.md)
(5ème registre, agrégation hebdomadaire).

Cette commande **ne modifie rien**. Elle agrège et produit un rapport.

## Sources

- `.claude/ideas.md`
- `.claude/backlog.md`
- `.claude/roadmap.md`
- `.claude/improvements.md`
- `.claude/digests/*-out.md` (semaines récentes)

## Format de sortie

```markdown
## Pipeline `{{label}}` — état au YYYY-MM-DD

### Stage 1 — IDEAS (`.claude/ideas.md`)

- [NEW] : N items
- [DEFERRED] : M items
- [PROMOTED -> backlog] : K items (ce trimestre)
- [PROMOTED -> roadmap] : J items (ce trimestre)
- [PROMOTED -> improvements] : I items (ce trimestre)
- [REJECTED] : R items (ce trimestre)

### Stage 2 — VALIDATED (TODO dans backlog / roadmap / improvements)

| Registre | P0 | P1 | P2 |
|---|---|---|---|
| backlog | x | y | z |
| improvements | x | y | z |
| roadmap (jalons engagés) | n/a | a | b |

### Stage 3 — IN PROGRESS

(Liste plate des items IN PROGRESS, tous registres, par priorité)

- **[IN PROGRESS] <titre>** — `<registre>` — démarré YYYY-MM-DD par
  <author> — branche `<nom>` — N jours

### Stage 4 — DONE (4 dernières semaines)

(Liste plate des items DONE des 4 dernières semaines, par date
décroissante)

- **[DONE YYYY-MM-DD] <titre>** — `<registre>` — <author>

### Registre digests (4 dernières semaines)

- `<YYYY-WW>-out.md` — produit par <author>, N items DONE / M idées
- `<YYYY-WW>-in/` — N digests reçus de N-1 (si manager)
- `<YYYY-WW>-mirror.md` — mirror du N+1 disponible ? oui/non

### Suggestions d'actions

(Sur le ton conseil, pas obligatoire)

- « N items VALIDATED en P1 dans backlog. Tu veux en démarrer un ? »
- « Item X en IN PROGRESS depuis 30 jours. À débloquer ou
  rétrograder ? »
- « Item Y en DEFERRED depuis 6 mois. Abandonner ou ré-examiner ? »
- « Pas de digest produit cette semaine. Lancer `/digest-week` ? »
```

## Cycle d'invocation

| Quand | Pourquoi |
|---|---|
| Début de session de travail | Voir l'état général avant d'attaquer |
| Avant tri d'idées | Préparer le tri user de `ideas.md` |
| Avant une release majeure | Vérifier que tous les items engagés sont DONE ou rétrogradés |
| Audit trimestriel | Identifier les items qui traînent |

## Anti-patterns

- **Compteur sans action** : si le rapport indique 50 items NEW
  depuis 6 mois, c'est qu'on ne fait pas le tri. Le rapport doit
  pointer la friction.
- **Vue figée** : `/pipeline` est read-only. Toute modification passe
  par les conventions de chaque registre (proposition à l'utilisateur,
  validation, commit).

Lance la collecte. Produis le rapport. Stop.
