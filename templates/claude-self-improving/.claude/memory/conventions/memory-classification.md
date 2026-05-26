# conventions/memory-classification

Test de classification **obligatoire** à appliquer AVANT toute
écriture de mémoire (user-locale vs projet versionnée). Évite la
dérive où des conventions de comportement Claude finissent en
mémoire user-locale (invisibles pour l'équipe) au lieu de
`.claude/memory/` versionné.

## Principe directeur

La mémoire projet `.claude/memory/` (et `CLAUDE.md` racine)
**s'auto-suffit** pour régir le comportement de Claude sur ce
projet. La mémoire user-locale
(`C:\Users\<user>\.claude\projects\{{label}}\memory\`) ne contient
**que** le profil de l'utilisateur courant.

Conséquence : tout signal de mémoire qui régit comment Claude
travaille sur ce projet (conventions, patterns, anti-patterns,
post-mortems, règles de délégation, format de commit, etc.) doit
aller dans `.claude/memory/` versionné, jamais en user-locale.

## Test à 3 questions

Appliquer **avant chaque écriture** de mémoire. Si **au moins
une réponse** oriente vers projet versionné, écrire dans
`.claude/memory/` (ou `CLAUDE.md` ALWAYS-ON), pas en user-locale.

| Question | Oriente vers projet versionné | Oriente vers user-locale |
|---|---|---|
| Si un autre dev rejoignait l'équipe sur ce projet, cette info devrait-elle être visible / applicable pour lui ? | Oui | Non (info perso à l'utilisateur courant) |
| Cette info changerait-elle si je travaillais avec un autre utilisateur sur ce projet ? | Non (la règle reste la même) | Oui (info varie selon l'utilisateur) |
| Cette info est-elle une convention de comportement Claude **sur ce projet** ou une préférence/profil personnel(le) ? | Convention Claude sur projet | Préférence / profil perso |

## Cas qui vont en mémoire **user-locale** (limités)

- Profil de l'utilisateur (rôle, expertise, environnement
  Windows/Linux, langue, mainteneur solo, etc.)
- Préférences perso non partageables (« préfère les réponses
  ultra-courtes sans préambule »)
- Notes ponctuelles d'historique conversationnel inter-session
  (« dernière session a buté sur X, reprendre Y »)
- Infos sur des projets / sujets parallèles que l'utilisateur
  mentionne hors scope du projet courant

## Cas qui vont en mémoire **projet versionnée**

- Conventions de comportement Claude sur le projet (délégation,
  format de commit, em-dash, accents, classification mémoire
  elle-même...)
- Règles ALWAYS-ON (`CLAUDE.md` racine)
- Patterns de code à reproduire ou éviter
  (`.claude/memory/pitfalls/`)
- Conventions d'équipe (workflow git, release, tests, hooks,
  slash commands)
- Patterns de délégation multi-agent (`multi-agent.md`)
- Diagnostics et post-mortems d'incidents (`diagnostics.md`)
- Pipeline d'auto-amélioration (4 registres `.claude/`)
- Procédures structurelles (auto-enrichissement de la mémoire,
  classification mémoire, etc.)

## Cas borderline

Si l'info est mi-perso mi-projet (ex: « l'utilisateur préfère X
pour ce projet précis ») :

1. Décomposer : la règle « préférer X » est-elle une convention
   équipe ou un goût perso ?
   - Convention équipe -> projet versionné
   - Goût perso -> user-locale
2. En cas de doute, **demander à l'utilisateur avant d'écrire**
   plutôt que d'inscrire silencieusement n'importe où.

## Workflow d'écriture mémoire

1. **Identifier le type** de l'info (user / feedback / project /
   reference, cf. instructions Claude Code).
2. **Appliquer le test à 3 questions** ci-dessus.
3. **Si user-locale** : écrire dans
   `C:\Users\<user>\.claude\projects\{{label}}\memory\<fichier>.md`
   + référencer dans `MEMORY.md` user-locale. Pas de commit
   (mémoire gérée par Claude Code, gitignored).
4. **Si projet versionné** : Edit dans
   `.claude/memory/<thème>.md` approprié. Si la règle est
   ALWAYS-ON, ajouter aussi une ligne dans `CLAUDE.md` racine
   pointant vers le fichier détaillé.
   - **Présenter le diff au user, attendre validation, commiter
     séparément** (convention git du projet : pas de commit
     silencieux).
5. **Si l'écriture user-locale a déjà eu lieu par erreur** :
   procédure de correction documentée ci-dessous.

## Procédure de correction (erreur de classification déjà commise)

Si une info de type « projet versionné » a été écrite par erreur
en user-locale :

1. **Supprimer** le fichier user-locale.
2. **Retirer** la ligne correspondante dans `MEMORY.md`
   user-locale.
3. **Migrer** le contenu (enrichi si pertinent) vers
   `.claude/memory/<thème>.md` approprié. Conserver la
   formulation post-mortem (« erreur observée 2026-MM-DD,
   contexte, ce qui a été fait pour corriger ») pour traçabilité
   et apprentissage.
4. **Lier** depuis `CLAUDE.md` ALWAYS-ON si critique.
5. **Cross-référencer** depuis les fichiers connexes
   (`memory-enrichment.md`, etc.).
6. **Commit dédié** documentant la correction
   (`doc({{label}}): migre <fichier> de user-locale vers
   mémoire projet versionnée`).

## Anti-patterns

- ❌ **« C'est l'utilisateur qui me l'a dit, donc c'est perso »**
  -> faux raisonnement. La **source** (utilisateur) ne détermine
  pas la **cible**. C'est l'**applicabilité** (perso vs équipe)
  qui tranche.
- ❌ **« C'est plus rapide en user-locale, pas de commit »**
  -> le coût d'un commit projet est mineur comparé au risque
  d'avoir une convention équipe invisible pour les autres.
- ❌ **« Je vais le mettre user-locale en attendant, je
  migrerai plus tard »** -> le « plus tard » ne vient jamais.
  Classer correctement dès la 1re écriture.
- ❌ **Inscrire silencieusement en mémoire projet** sans
  présenter le diff -> viole la convention git du projet (pas
  de commit/push sans demande explicite). Toujours présenter +
  attendre validation.
- ❌ **« C'est ma mémoire à moi (Claude), c'est forcément
  user-locale »** -> faux. Si la règle régit le comportement de
  Claude sur le projet, elle s'applique à TOUTE session Claude
  sur ce projet, indépendamment de l'utilisateur. Donc projet
  versionné.

## Post-mortems (apprentissages)

### 2026-05-10 : feedback de délégation `{{name}}-expert` mal classé

- **Erreur initiale** : feedback « déléguer plus à
  `{{name}}-expert` pour features M » écrit dans
  `delegation_preference.md` user-locale.
- **Pourquoi c'était erroné** : convention de comportement
  Claude **sur ce projet**, applicable à toute personne
  travaillant dessus, pas perso à l'utilisateur.
- **Détection** : par l'utilisateur lui-même (« Tu as omis un
  principe de base... »).
- **Correction** : suppression user-locale, migration enrichie
  vers `multi-agent.md` § « Du thread principal vers
  {{name}}-expert » + table de décision 8 types + 3
  anti-patterns, ligne ALWAYS-ON renforcée dans `CLAUDE.md`.
  Commit `deab017`.

### 2026-05-10 : test de classification mémoire lui-même mal classé

- **Erreur initiale** : juste après le post-mortem précédent,
  inscription du **test de classification mémoire** lui-même
  dans `memory_classification.md` user-locale.
- **Pourquoi c'était erroné** : raisonnement faux « c'est ma
  mémoire à moi (Claude), donc user-locale ». Le test régit le
  comportement Claude sur ce projet pour TOUTE session, donc
  projet versionné.
- **Détection** : par l'utilisateur immédiatement après
  l'écriture (« Justement, tu viens de réécrire cette règle dans
  la mémoire locale au lieu de la mémoire projet »).
- **Correction** : suppression user-locale, migration vers ce
  fichier (`memory-classification.md`), lien depuis
  `memory-enrichment.md` et `CLAUDE.md` ALWAYS-ON. La mémoire
  user-locale est désormais réduite au strict minimum (profil
  utilisateur uniquement).
- **Leçon transverse** : le test de classification s'applique
  **récursivement** à la décision d'écrire le test lui-même. Si
  le contenu écrit décrit une règle de comportement Claude sur
  le projet (même si la règle traite de la mémoire), c'est
  projet versionné. Pas d'exception.

## Lien avec les autres conventions

| Convention | Lien |
|---|---|
| [`memory-enrichment.md`](memory-enrichment.md) | Le test de classification est l'étape préalable à tout enrichissement de mémoire. La sous-section « Signaux qui NE doivent PAS enrichir la mémoire » de `memory-enrichment.md` reprend le cas user-locale ; la classification fine vit ici. |
| [`multi-agent.md`](multi-agent.md) | Cas concret : la règle de délégation à `{{name}}-expert` y a été migrée après le 1er post-mortem (2026-05-10). |
| [`pipeline.md`](pipeline.md) | Le pipeline d'auto-amélioration est un méta-pattern de mémoire projet versionnée (4 registres versionnés). N'a aucun équivalent user-locale par construction. |
