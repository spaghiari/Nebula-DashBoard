<!-- BEGIN claude-team -->
<!--
  Bloc always-on injecté par le module « Équipe d'agents et amélioration
  mesurée » (Nebula). Ne pas éditer manuellement entre les marqueurs
  BEGIN/END : le ré-apply du module remplace ce bloc par sa version
  courante (ancien CLAUDE.md sauvegardé en .bak).
-->

## Équipe d'agents et amélioration mesurée (always-on)

`claude-self-improving` retient et trie (mémoire, registres,
conventions) ; `claude-team` ajoute une **équipe d'agents** avec routage
de modèle par rôle et une **boucle d'amélioration mesurée** : on ne garde
un changement d'agent que s'il fait mieux sur un jeu d'évals figé, sans
régression.

### Les 7 agents générés (`.claude/agents/<préfixe>-*.md`)

Préfixe = `team.prefix` de `.claude/team.json` (choisi à l'activation,
par défaut l'id du workspace) ; `/agents` les liste. Rôles :
`orchestrator` (opus, point d'entrée en délégation), `researcher`
(sonnet, lecture seule), `architect` (opus, lecture seule), `executor`
(sonnet, escalade opus), `reviewer` (opus, relecture à froid),
`evaluator` (sonnet, note en aveugle), `critic` (opus, boucle
uniquement). Générés depuis `.claude/team.json` ; les corps s'éditent
dans `.claude/team/agents/<id>.md`, jamais dans l'agent généré.

### Routage automatique (always-on)

L'utilisateur parle normalement : le fil principal route vers l'équipe
sans appel explicite et rend **une** réponse, sourcée et relue
(`<p>` = `team.prefix`, les noms exacts sont dans `/agents`).

Le mode actif est `routing.mode` de `.claude/team.json` (`auto` par
défaut). En `auto`, Claude principal applique la table ci-dessous sans
qu'on le lui demande ; en `assiste`, il suit la suggestion injectée par
le hook `team-router.py` sauf raison explicite ; en `manuel`, il ne
délègue que sur `/team` ou demande explicite. Le mode se change depuis
Nebula (onglet Configuration, ligne du module) ; aucune régénération.

| Demande | Ce que fait Claude principal | Agents | Modèle |
|---|---|---|---|
| Question sur le code, le projet, un comportement (« où », « pourquoi », « comment ça marche », « liste ») | délègue en silence, répond avec des sources `fichier:ligne` | `<p>-researcher` | sonnet |
| « Comment on ferait », conception, choix technique | demande un plan en étapes vérifiables, le présente avec ses compromis | `<p>-architect` | opus |
| Tâche S (1 à 3 fichiers, périmètre clair) | fait exécuter, puis **relecture aveugle obligatoire** avant de présenter | `<p>-executor` puis `<p>-reviewer` | sonnet + opus |
| Feature M+ (10 fichiers ou plus, multi-domaines, refactor à effets de bord) | `*-expert` s'il existe (règle de cohabitation inchangée), puis relecture, puis validation | `*-expert`, `<p>-reviewer`, `*-impl-validator` | opus |
| Relecture demandée d'un diff ou d'un fichier | transmet objectif + critères + diff | `<p>-reviewer` | opus |
| Demande ambiguë ou multi-étapes | `/team` (orchestration par le fil principal) | selon le plan | selon le plan |
| Jamais en routage automatique | réservés à `/eval` et `/improve` | `<p>-critic`, `<p>-evaluator` | - |

- **Délégation par défaut (`auto`)** : dès qu'une demande produit ou
  modifie du code, Claude principal ne l'écrit **pas** lui-même : il
  délègue (`<p>-executor`, `*-expert` ou `/team` selon la taille), puis
  applique la gate reviewer. Une demande large sur le projet entier
  (« retravaille », « améliore », « réorganise le projet ») se traite
  comme `/team` : plan par `<p>-architect`, exécution étape par étape,
  relecture. Seules exceptions : un échange sans travail (salutation,
  validation, question de suivi sur ce qui vient d'être livré). Dans le
  doute, déléguer. Le hook `team-router.py` le rappelle à chaque
  demande ; son absence de classe n'est jamais une raison de coder seul.
- **Gate reviewer** (`routing.review_gate`, `always` par défaut) : tout
  fichier de code créé ou modifié passe par `<p>-reviewer` (objectif +
  critères + diff, jamais le raisonnement) avant d'être présenté.
  Verdict À CORRIGER -> corriger puis re-relire (2 allers-retours max,
  sinon le dire). `from_3_files` : dès 3 fichiers touchés ; `never` :
  relecture seulement sur demande.
- **Sortie unifiée** : l'utilisateur ne voit jamais les rapports bruts
  des agents. Claude principal synthétise (réponse, sources, ce que la
  relecture a corrigé) et termine par une ligne discrète
  `équipe : researcher, reviewer` (noms des agents mobilisés). Pas de
  narration « je délègue à... » en cours de route au-delà d'une phrase.
- **Budget** (`routing.budget` = `sonnet-first`) : en `auto`, un
  sous-agent sonnet au plus par question simple ; opus seulement pour
  reviewer et architect ; une **question** qui tient en une lecture d'un
  seul fichier connu peut recevoir une réponse directe, signalée
  (`équipe : aucun`). Le budget ne dispense jamais de la délégation ni
  de la relecture pour du code livré.

### Commandes

- `/team <objectif>` : **le fil principal joue l'orchestrateur** (corps
  de `team/agents/orchestrator.md` appliqué tel quel : comprendre,
  découper, déléguer aux agents générés, boucler, livrer). Voie explicite
  pour une orchestration complète ; en `auto` elle reste utile pour les
  demandes multi-étapes. L'agent `<préfixe>-orchestrator` sert à la
  délégation explicite.
- `/eval [--tag X] [--agent Y] [--id Z]` : le fil principal boucle sur
  `.claude/evals/eval-set.jsonl`, délègue chaque cas à l'agent visé, note
  (`test` / `regex` / `exact`) ou fait noter en aveugle par l'évaluateur
  (`rubric`). Lecture seule. `config_version` = empreinte manifeste +
  corps + agents générés (one-liner dans la commande).
- `/improve` : une itération de la boucle en **deux phases**, car une
  session ne recharge pas la définition d'un agent modifié. Phase 1 :
  baseline (journal si l'empreinte est inchangée), UN diff du critique,
  candidat appliqué et régénéré, ligne `pending` au journal. Phase 2,
  dans une **nouvelle session** : mesure du candidat, accepté si gain
  >= 0,02 et zéro régression, sinon cible restaurée ; journal
  `.claude/journal/changes.jsonl`. `/improve` détecte seul la phase.
- `/eval-add` : transforme un échec observé en cas d'éval candidat.

### Règles

- **Cohabitation avec le bloc Auto-amélioration** : la règle
  « Délégation à `*-expert` par défaut pour les tâches conséquentes »
  (agent `<id du workspace>-expert`, indépendant du préfixe de
  l'équipe) reste vraie. Dans l'équipe, `*-expert` (s'il existe
  dans `.claude/agents/`) est l'exécutant des tâches conséquentes
  (feature M+, 10 fichiers ou plus, multi-domaines, refactor à effets de
  bord) : il porte la mémoire projet ; `<préfixe>-executor` exécute les
  tâches S et les étapes atomiques d'un plan ; `*-impl-validator`
  complète `<préfixe>-reviewer` (après lui, jamais à sa place).
- **Commits de la boucle** : lancer `/improve` vaut demande explicite de
  commit pour ses itérations acceptées, sur la branche courante, au
  format `update(<préfixe>): improve/<n> - <hypothèse>` ; aucun autre
  commit, jamais de push. Les hooks pre-commit s'appliquent.
- **Évals verrouillées** : aucune écriture sous `.claude/evals/` (hook
  `evals-lock.py`). Déverrouillage explicite par l'utilisateur seulement
  (`"evals_unlocked": true` dans `.claude/settings.local.json`).
- **Une modification par itération, zéro régression**, jamais de
  modification de la section `improvement_loop` de `.claude/team.json`.
- **Pont avec `improvements.md`** : le critique lit les items `[TODO]`
  comme hypothèses ; une itération acceptée passe l'item en `[DONE]` avec
  score avant/après et commit, une itération rejetée le passe en
  `[ABANDONED]` avec la mesure. Toujours annoncé, jamais silencieux.

### Sommaire mémoire (ajouts du module)

| Fichier | Quand le lire |
|---|---|
| [`conventions/improvement-loop.md`](.claude/memory/conventions/improvement-loop.md) | Avant `/improve` : topologie, étapes, garde-fous, empreinte, format du journal, pont avec `improvements.md` |
| [`subsystems/claude-team.md`](.claude/memory/subsystems/claude-team.md) | Manifeste, préfixe, génération des agents, mapping, hook, commandes, cohabitation |
<!-- END claude-team -->
