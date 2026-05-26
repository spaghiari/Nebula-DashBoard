# conventions/done-lifecycle

Cycle de vie des items DONE dans `.claude/backlog.md` et
`.claude/improvements.md` : conservation court terme,
**cristallisation des patterns récurrents** en mémoire centrale,
archivage long terme. But : capitaliser sur l'expérience passée
plutôt que d'accumuler des entrées qui ne sont plus consultées.

## Principe directeur

Un item DONE n'a de valeur **résiduelle** que si la connaissance
qu'il porte est **réinvestissable** dans une future décision.
Cette connaissance prend deux formes :

- **Trace narrative** (ce qui s'est passé, dans quel ordre, avec
  quels arbitrages) -> conservée dans le registre d'origine ou
  archivée par année si très ancienne.
- **Pattern récurrent** (règle réutilisable, pitfall à éviter,
  recette à appliquer) -> **cristallisée** dans la mémoire
  centrale (`pitfalls/`, `conventions/`, `playbooks.md`,
  `subsystems/`, etc.) où elle redevient consultable
  proactivement par Claude.

## 3 phases du cycle de vie

### Phase 1 - Récents (< 90 jours après DONE)

- **Position** : conservés tels quels dans le registre d'origine
  (`backlog.md` § Items terminés ou `improvements.md` § Items
  terminés).
- **Format** : item complet (cibles livrées, effort estimé,
  effort IA réel, ratio, commits).
- **Usage** : référence directe pour des questions « qu'a-t-on
  fait sur X ? » ou « comment a-t-on réglé Y la dernière fois ? ».
- **Pas d'action particulière** à entreprendre.

### Phase 2 - Cristallisation (à partir de 30 jours, opportuniste)

Quand un pattern se répète sur 2+ items DONE OU quand un nouvel
item DONE révèle une généralisation utile, **cristalliser** la
connaissance dans la mémoire centrale.

**Recettes par type d'item à cristalliser** :

| Type d'item DONE | Cible de cristallisation |
|---|---|
| Fix d'un bug avec cause racine non triviale | `pitfalls/<catégorie>.md` (nouvelle entrée) + Top dans `pitfalls.md` (si critique) + ALWAYS-ON dans `CLAUDE.md` (si récurrent) |
| Feature qui introduit un sous-système | `subsystems/<nom>.md` (nouveau fichier ou enrichissement) |
| Refacto qui établit un pattern | `architecture.md` ou `conventions/<thème>.md` |
| Convention adoptée et appliquée 2+ fois | `conventions/<thème>.md` (nouvelle section) ; si ALWAYS-ON, MAJ `CLAUDE.md` |
| Nouvelle classe / méthode pivot | `architecture.md` ou `frontend/helpers.md` selon nature |
| Friction outillage Claude résolue | `claude-tooling.md` ou `conventions/multi-agent.md` |
| Diagnostic récurrent | `diagnostics.md` (table des symptômes) |
| Workflow / procédure fréquente | `conventions/playbooks.md` (nouvelle recette) |
| Auto-amélioration d'un pattern Claude | `conventions/self-improvement.md` |

**Validation utilisateur obligatoire** avant cristallisation :
le proposer en fin de session ou en fin de turn (« Cet item DONE
révèle un pattern. Je propose de cristalliser dans X. OK ? »).
Pas de cristallisation silencieuse.

**Une fois cristallisé** : laisser une note dans l'item DONE
d'origine (« Pattern cristallisé dans
`<chemin>` 2026-MM-DD ») pour traçabilité, et préparer son
archivage en phase 3.

### Phase 3 - Archivage (> 90 jours après DONE, ou après cristallisation complète)

**Conditions** : item DONE depuis >90 jours OU patterns
intégralement cristallisés (le contenu est désormais accessible
via la mémoire centrale).

**Action** : déplacer l'item du registre d'origine vers
`.claude/archive/<année>.md` (créer le fichier si inexistant).
Le registre d'origine ne conserve qu'un **lien archivé** :

```markdown
- **[ARCHIVED 2026-MM-DD] <titre court>** -> voir `.claude/archive/<année>.md`
```

**Format de `.claude/archive/<année>.md`** :

```markdown
# Archive <année>

Items DONE archivés depuis `backlog.md` et `improvements.md`. Les
patterns récurrents qu'ils ont fait émerger ont été cristallisés
dans la mémoire centrale (cf. notes individuelles).

## <YYYY-MM> - <Titre court>

(format identique à l'item DONE original)

...
```

**Bénéfice** : les registres actifs (`backlog.md`,
`improvements.md`) restent légers et focalisés sur les phases
1-2. L'archive long terme reste consultable mais ne pollue pas
la lecture courante.

## Anti-patterns

- ❌ **Cristallisation silencieuse sans validation utilisateur** :
  même règle que pour `memory-enrichment.md` - jamais
  d'enrichissement de mémoire sans accord explicite.
- ❌ **Archivage sans cristallisation** : si un item DONE >90
  jours n'a pas été examiné pour pattern récurrent, **ne pas
  l'archiver à l'aveugle**. La phase 2 doit avoir lieu d'abord
  (sauf si l'item est trivial sans pattern réutilisable, auquel
  cas archivage direct est OK).
- ❌ **Re-création de la même cristallisation** : avant de
  cristalliser, vérifier que le pattern n'existe pas déjà dans
  la mémoire (grep ciblé).
- ❌ **Cristallisation prématurée** : un seul cas isolé n'est
  pas un pattern. Attendre 2+ occurrences ou un signal
  utilisateur fort.
- ❌ **Item supprimé au lieu d'archivé** : la trace narrative a
  une valeur historique (`git blame`, debugging d'une
  régression). Toujours archiver, jamais supprimer.

## Audit périodique

À effectuer **trimestriellement** (ou avant une release majeure
X.Y.0) :

1. Lister les items DONE de `backlog.md` + `improvements.md`
   classés par date de DONE.
2. Identifier ceux > 30 jours (candidats cristallisation).
3. Pour chaque candidat, examiner si un pattern réutilisable
   peut être cristallisé. Proposer à l'utilisateur les
   cristallisations utiles.
4. Identifier ceux > 90 jours (candidats archivage).
5. Pour chaque candidat archivable : vérifier qu'il n'y a plus
   de pattern à cristalliser, puis archiver dans
   `.claude/archive/<année>.md`.

## Workflow d'enrichissement initial du système

À mise en place de cette convention (2026-05-10) : pas de
backport des items DONE existants vers archives. Le système
s'applique aux **nouveaux items DONE post-2026-05-10**. Les
items DONE existants restent dans leur registre d'origine
jusqu'au prochain audit trimestriel.

## Lien avec les autres conventions

| Convention | Lien |
|---|---|
| [`memory-enrichment.md`](memory-enrichment.md) | Cristallisation phase 2 = enrichissement mémoire ciblé. Reprend les recettes par type. |
| [`memory-classification.md`](memory-classification.md) | La cristallisation va toujours en mémoire **projet versionnée** (jamais user-locale) - cf. test à 3 questions. |
| [`effort-sizing.md`](effort-sizing.md) | Le format des items DONE inclut `Effort estimé` + `Effort IA réel` + `Ratio`. À conserver lors de la cristallisation pour stats long terme. |
| [`backlog.md`](backlog.md) | Convention générale du backlog (priorisation, statuts). Cycle de vie des DONE en complément. |
| [`self-improvement.md`](self-improvement.md) | Convention `improvements.md`. Cycle de vie des DONE également applicable. |
