# conventions/self-improvement

Pattern d'auto-amélioration de Claude, des agents et des capacités
outillage du projet. Permet de capturer et faire évoluer la qualité de
l'assistant au fil des sessions.

## Périmètre

L'auto-amélioration cible **l'outillage Claude**, distinct du module
produit lui-même :

| Cible | Améliorer si |
|---|---|
| `CLAUDE.md` | Une règle ALWAYS-ON manque, une autre est ambiguë, une priorité doit être ajustée |
| `.claude/memory/<thème>.md` | Une section manque, est obsolète, ou ambiguë sur un aspect courant |
| `.claude/agents/<agent>.md` | Un agent produit régulièrement des outputs hors format, une règle manque, le coût est excessif |
| `.claude/commands/<commande>.md` | Un slash command est imprécis, manque un cas, génère trop de bruit |
| `.claude/hooks/<hook>.sh` | Un hook ne couvre pas un cas, plante sur un environnement, ou est trop strict |
| Conventions du projet | Un pattern observé répétitivement mérite d'être codifié |

## Différence avec les autres systèmes

| Système | Cible | Trigger |
|---|---|---|
| **Auto-enrichissement** ([`memory-enrichment.md`](memory-enrichment.md)) | Mémoire projet | Connaissance acquise sur le **module produit** |
| **Backlog** ([`backlog.md`](backlog.md)) | Module produit | Action différée court/moyen terme sur **le code** |
| **Roadmap** ([`roadmap.md`](roadmap.md)) | Module produit | Vision long terme du **module** |
| **Auto-amélioration** (ce fichier) | Outillage Claude | Friction sur **l'assistant** lui-même |

## Signaux qui déclenchent une amélioration

| Signal | Cible probable |
|---|---|
| **Hallucination répétée** : Claude invente un identifiant, une route, un helper qui n'existe pas | Renforcer la checklist anti-hallucination dans agent ou ajouter règle ALWAYS-ON dans CLAUDE.md |
| **Prompt utilisateur souvent ambigu** sur un type de tâche | Améliorer la doc du sous-agent ou créer un nouveau slash command spécialisé |
| **Output verbose ou hors format** d'un agent | Renforcer le format de sortie dans le prompt de l'agent |
| **Règle ALWAYS-ON oubliée** par Claude principal ou un agent | Reformuler la règle, la rendre plus visible, ou ajouter un check (hook, slash command) |
| **Friction de coût** : une tâche prend systématiquement trop de tokens | Optimiser le prompt, déléguer à un sous-agent plus ciblé, ou raccourcir la mémoire chargée |
| **Slash command qui rate des cas** | Étendre le périmètre de la commande ou créer une variante |
| **Mémoire incomplète** sur un aspect que Claude a dû redécouvrir | Enrichir le fichier `.claude/memory/<thème>.md` concerné |
| **Sous-agent qui se chevauche avec un autre** | Fusionner ou clarifier les périmètres |

## Quand NE PAS améliorer

- **Friction one-off** : un seul incident, pas un pattern. Attendre la
  récurrence avant d'investir.
- **Optimisation prématurée** sans signal clair que ça vaut le coup.
- **Item perso** (préférence d'un utilisateur unique) →
  `CLAUDE.local.md`.
- **Item qui appartient au module** (bug du module, feature à ajouter)
  → backlog ou roadmap, pas ce registre.

## Format d'un item

```markdown
- **[TODO] Titre court actionnable** (P1, ajouté 2026-MM-DD par <author>)
  - Cible : `.claude/agents/am-xxx.md` (ou autre)
  - Symptôme : <comportement observé>
  - Cause probable : <pourquoi ça arrive>
  - Action proposée : <quoi changer>
  - Bénéfice attendu : <ce qu'on gagne>
```

## Cycle de vie

```
[TODO] → [IN PROGRESS] → [DONE]
   ↓
[ABANDONED]
```

Aligné sur le pipeline unifié
([`pipeline.md`](pipeline.md)) :

- **[TODO]** = stage VALIDATED
- **[IN PROGRESS]** = stage IN PROGRESS (ajouter `Démarré`, `Branche`,
  commits au fil de l'eau)
- **[DONE YYYY-MM-DD]** = stage DONE (avec référence commit final)

Quand un item est terminé, déplacer en section « Items terminés »
avec date et lien vers le commit qui l'a appliqué.

## Pattern de proposition à l'utilisateur

Quand un signal est détecté en cours de session :

```
## Améliorations Claude/agents identifiées

Au fil de cette session, j'ai identifié les frictions suivantes qui
mériteraient une entrée au registre `.claude/improvements.md` :

1. **[TODO] <titre>** (P1)
   - Cible : <fichier ou agent>
   - Symptôme : <comportement>
   - Action : <quoi changer>

Tu veux les ajouter au registre maintenant, ou plus tard ?
```

L'utilisateur tranche ; si OK, ajout au `.claude/improvements.md` avec
un commit dédié `doc({{label}}): improvements - ajoute <résumé>`.

## Cycle de revue

| Phase | Quand |
|---|---|
| **Création** | Bootstrap ou refonte (4.3.0+) |
| **Enrichissement** | À chaque session où une friction est observée |
| **Application** | Au feeling : un user qui revisite le registre P1 décide d'appliquer 1-2 items |
| **Revue trimestrielle** | Épurer les P2 obsolètes, ré-évaluer les P1 |

## Exemples (prospectifs)

Items types qu'on pourrait voir :

```markdown
### P1 - important

- **[TODO] {{name}}-expert hallucine parfois des classes CSS** (P1, ajouté 2026-MM-DD par <author>)
  - Cible : `.claude/agents/{{name}}-expert.md`
  - Symptôme : citations de classes `.am-xxx` qui n'existent pas dans
    `module.less`, par ex. `.am-pretty-card`
  - Cause probable : la checklist anti-hallucination n'est pas
    appliquée systématiquement sur les classes CSS
  - Action : renforcer le pattern « grep avant cite » dans la règle
    dure anti-hallucination + ajouter exemple explicite dans le prompt
  - Bénéfice attendu : 0 hallucination CSS dans les livrables

- **[TODO] /check-pitfalls n'audite pas la nouvelle catégorie « locks »** (P2, ajouté 2026-MM-DD par <author>)
  - Cible : `.claude/commands/check-pitfalls.md`
  - Symptôme : la feature concurrent writes (4.2.0) n'a pas de check
    automatique pour `flock` / lockfile
  - Cause probable : la feature est récente, le slash command n'a pas
    été étendu
  - Action : ajouter une catégorie « Locks et concurrence » avec 2-3
    items dans `/check-pitfalls`
  - Bénéfice attendu : couverture complète post-4.2.0
```

## Lien avec l'agent {{name}}-expert

L'agent expert (cf. `.claude/agents/{{name}}-expert.md`) inclut depuis
sa refonte un output gate « Améliorations Claude/agents identifiées »
en fin de mode implémentation et bug fix - quand l'agent observe une
friction sur lui-même ou sur les outils.

Pour les sessions courtes, le rappel est dans la règle ALWAYS-ON de
`CLAUDE.md`.

## Anti-patterns

- **Auto-amélioration silencieuse** : Claude modifie son propre
  prompt ou la mémoire sans demander. **Toujours proposer à
  l'utilisateur**.
- **Améliorations sans signal** : ajouter un item au registre sans
  exemple concret de friction observée → bruit qui pollue le registre.
- **Refonte permanente** : itérer sur les prompts trop souvent perd la
  stabilité. Préférer 1-2 améliorations par release majeure.
