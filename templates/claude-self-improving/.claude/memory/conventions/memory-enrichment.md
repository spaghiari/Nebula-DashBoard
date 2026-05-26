# conventions/memory-enrichment

Pattern d'**auto-enrichissement de la mémoire projet** au fil des
sessions. La mémoire `.claude/memory/` doit grandir avec le projet,
sinon elle vieillit et devient inexacte.

## Signaux qui déclenchent un enrichissement

Quand un de ces signaux est détecté en fin de session ou de livrable,
proposer un enrichissement à l'utilisateur **avant la fin du
turn** :

| Signal | Type d'enrichissement |
|---|---|
| **Bug silencieux post-mortem** : un comportement inattendu identifié dont la cause racine est non-obvious | Nouvelle entrée dans `pitfalls/<catégorie>.md` (créer une catégorie si nouvelle) + éventuellement règle ALWAYS-ON dans `CLAUDE.md` si critique |
| **Nouveau sous-système stabilisé** : une feature livrée qui constitue un sous-système autonome (config, classes dédiées, vues spécifiques) | Nouveau fichier `subsystems/<nom>.md`, MAJ sommaire `subsystems.md` |
| **Nouvelle convention adoptée** : une règle de code ou de workflow tranchée et appliquée | Entrée dans `conventions/<thème>.md` ou nouveau fichier si transversal. Si ALWAYS-ON, MAJ aussi `CLAUDE.md` |
| **Nouveau pattern d'implémentation récurrent** : 2-3 endroits du code qui font la même chose de la même façon | Section dans `architecture.md` ou playbook dans `conventions/playbooks.md` |
| **Nouveau diagnostic récurrent** : un symptôme observé au moins 2 fois avec sa cause | Nouvelle ligne dans `diagnostics.md` |
| **Nouvelle classe / méthode pivot** : helper, value object, trait introduit qui sera réutilisé | Section dans `architecture.md` ou `frontend/helpers.md` selon la nature |
| **Nouveau slash command** : ajout dans `.claude/commands/` | Entrée dans `claude-tooling.md` |
| **Refonte UX significative** : changement de pattern UI documenté ailleurs | Ligne ou section dans `frontend/<spoke>.md` |
| **Migration ou bump majeur** : montée de version Icinga Web 2, Icinga2, PHP, etc. | MAJ `overview.md` + `conventions/php.md` si compat change |

## Signaux qui NE doivent PAS enrichir la mémoire

- **État éphémère de session** (point de reprise, plan en cours,
  diff de travail) → reste dans la conversation, pas dans la mémoire.
- **Notes utilisateur perso** (préférences, profil, historique
  perso) → mémoire user-locale `~/.claude/projects/.../memory/`,
  pas mémoire partagée. Pour trancher entre user-locale et projet
  versionné, **appliquer le test à 3 questions** documenté dans
  [`memory-classification.md`](memory-classification.md). En cas
  de doute, demander à l'utilisateur avant d'écrire.
- **Décisions à valider** non encore tranchées → conversation,
  pas mémoire.
- **Contenu déjà couvert** ailleurs dans la mémoire → ne pas
  dupliquer. Si redondant, référencer plutôt qu'enrichir.

## Recettes par type d'enrichissement

### Ajouter un pitfall

1. Identifier la catégorie : `api-encoding`, `post-flow`,
   `html-structure`, `js-ajax`, `restrictions`, `ido`, `conventions`,
   ou nouvelle catégorie.
2. Ouvrir `.claude/memory/pitfalls/<catégorie>.md`.
3. Ajouter une section H2 `## <titre du pitfall>` avec :
   - Symptôme observé
   - Cause racine
   - Code exemple (FAUX vs CORRECT)
   - Vérification (commande grep, lint, etc.)
4. Si critique (ALWAYS-ON), ajouter une ligne dans `CLAUDE.md`
   section « Pièges silencieux à toujours garder en tête ».
5. Si nouvelle catégorie : créer `pitfalls/<nouvelle>.md` + MAJ
   sommaire dans `pitfalls.md`.

### Ajouter un sous-système

1. Créer `.claude/memory/subsystems/<nom>.md` avec sections :
   - Architecture (classes/fichiers)
   - Configuration (`config.ini`)
   - API publique
   - Failure modes / pitfalls associés
   - Pattern d'utilisation
2. MAJ sommaire dans `subsystems.md`.
3. Si la feature ajoute des permissions ou classes notables, MAJ
   aussi `architecture.md` et/ou `security/rbac.md`.

### Ajouter une convention

1. Choisir le fichier cible : `conventions/php.md`, `conventions/git.md`,
   `conventions/testing.md`, `conventions/hooks.md`,
   `conventions/playbooks.md`, ou nouveau `conventions/<nom>.md`.
2. Ajouter une section avec règle + justification (Why) + comment
   l'appliquer (How).
3. Si ALWAYS-ON (à appliquer sans relecture), ajouter aussi à
   `CLAUDE.md`.

### Mettre à jour le sommaire d'un hub

Quand un nouveau spoke est créé, mettre à jour le sommaire du hub
parent :

```markdown
| [`<thème>/<nouveau>.md`](<thème>/<nouveau>.md) | <description en 1 ligne> |
```

Garder l'ordre alphabétique ou logique du tableau.

## Pattern de proposition à l'utilisateur

À la fin d'une session ou d'un livrable significatif :

```
## Enrichissements mémoire proposés

Au fil de cette session, j'ai identifié les patterns suivants qui
mériteraient un enrichissement de la mémoire projet :

1. **Pitfall** : « <description courte> » → nouvelle entrée dans
   `.claude/memory/pitfalls/<catégorie>.md`
2. **Sous-système** : la feature `xxx` ajoute un sous-système qui
   pourrait justifier `.claude/memory/subsystems/xxx.md`
3. **Convention** : règle de code introduite (« ... ») → entrée dans
   `.claude/memory/conventions/<thème>.md` + ligne ALWAYS-ON dans
   `CLAUDE.md` (si critique)

Tu veux que j'enrichisse maintenant, ou plus tard ?
```

L'utilisateur tranche ; si OK, l'enrichissement est fait avec un commit
dédié `doc({{label}}): enrichit la mémoire avec <résumé>`.

## Anti-pattern : auto-enrichissement silencieux

**Ne JAMAIS** enrichir la mémoire sans validation utilisateur. La
mémoire est versionnée et partagée à toute l'équipe ; un ajout doit
être conscient et validé.

Le seul auto-enrichissement légitime est dans la **mémoire user-locale**
(via le système Claude Code de feedback memory standard). La mémoire
projet partagée nécessite toujours validation explicite.

## Cycle de vie de la mémoire

| Phase | Quand |
|---|---|
| **Création** | Refonte structurelle (4.2.0) ou nouveau projet |
| **Enrichissement** | À chaque feature livrée, post-mortem de bug, nouvelle convention |
| **Refactor** | Si un fichier hub dépasse ~200 lignes : split en spokes |
| **Dédoublonnage** | Périodiquement (1×/release majeure) : grep des cross-références cassées et duplicates |
| **Audit** | Avant une release majeure : passage agent `{{name}}-expert` qui valide la cohérence du `.claude/memory/` |

## Lien avec l'agent {{name}}-expert

L'agent expert (cf. `.claude/agents/{{name}}-expert.md`) inclut depuis
sa refonte un output gate « Enrichissements mémoire proposés » dans
ses modes implémentation et bug fix. C'est le mécanisme principal
d'auto-enrichissement structuré.

Pour les sessions courtes (Q&A, fix 1-2 lignes), l'enrichissement est
au feeling de Claude principal - règle ALWAYS-ON dans `CLAUDE.md`
rappelle de proposer un enrichissement quand un signal est détecté.
