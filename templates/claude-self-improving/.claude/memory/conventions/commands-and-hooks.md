# conventions/commands-and-hooks

Maintenance continue des slash commands (`.claude/commands/`) et hooks
(`.claude/hooks/`). Ces outils évoluent avec le projet et doivent être
régulièrement revus pour rester pertinents.

**Périmètre de ce fichier** : méta-process (cycle de revue, signaux,
anti-patterns). La référence détaillée des commands et hooks vit dans
[`commands.md`](commands.md) et [`hooks.md`](hooks.md).

## Cycle de maintenance

| Phase | Quand | Fréquence |
|---|---|---|
| **Audit léger** | Vérifier que les commands/hooks existants sont alignés sur la doc mémoire (cohérence pointeurs, format de sortie attendu, listes synchronisées) | Avant chaque release majeure (`/bump-version 5.0`) ou trimestriellement |
| **Audit profond** | Lecture intégrale de chaque command/hook, vérification des pitfalls couverts, simplification des prompts trop verbose | À la refonte d'un sous-système ou tous les 6 mois |
| **Ajout** | Quand un pattern d'erreur récurrent émerge, ou un type d'audit/automatisation manque | Au feeling, sur signal |
| **Suppression** | Si une commande/hook n'a pas servi depuis 6+ mois | Audit léger |

## Quand mettre à jour un slash command

| Signal | Action |
|---|---|
| Nouvelle catégorie de pitfall créée dans `.claude/memory/pitfalls/` | Étendre `/check-pitfalls` pour couvrir |
| Nouvelle convention adoptée (par ex. format de fichier, nommage) | Ajouter le check dans le slash command linter pertinent (`/lint-php`, `/lint-views`, etc.) |
| Nouveau type de fichier dans le repo (`.claude/memory/`, `.claude/backlog.md`, etc.) | Vérifier que `/check-all` les couvre et que les linters s'y appliquent ou les ignorent correctement |
| Slash command devenu trop verbose | Refondre pour focaliser sur l'essentiel |
| Slash command qui rate des cas connus | Étendre la couverture |
| Slash command qui chevauche un autre | Fusionner ou clarifier les périmètres |

Workflow d'ajout/MAJ d'une commande : voir [`commands.md`](commands.md)
section « Pour ajouter une nouvelle slash command ».

## Quand mettre à jour un hook

| Signal | Action |
|---|---|
| Nouveau fichier user-local sensible | Étendre `protect-local-files.py` |
| Nouveau format de message à interdire (en plus de l'em-dash) | Étendre `em-dash-precommit.py` ou créer un nouveau hook précommit |
| Nouveau registre versionné à valider en format | Étendre `improvements-validate.py` ou créer un hook dédié |
| Lint automatique manquant sur un nouveau type de fichier | Étendre ou créer un hook postedit |
| Hook qui plante sur un environnement spécifique | Rendre best-effort (exit 0 si conditions non remplies) |
| Hook qui bloque trop souvent | Rendre plus permissif ou plus précis |

Workflow d'ajout/MAJ d'un hook : voir [`hooks.md`](hooks.md) section
« Ajout d'un nouveau hook ».

## Items à inscrire au registre `.claude/improvements.md`

Lors de chaque audit (léger ou profond), les frictions observées sur
les commands/hooks sont à inscrire au registre :

À documenter dans
[`.claude/improvements.md`](../../improvements.md) au fur et à mesure
des audits, avec priorisation P0/P1/P2 et pointeur vers le fichier
cible (`.claude/commands/<cmd>.md` ou `.claude/hooks/<hook>.py`).

## Anti-patterns

- **Empiler des slash commands sans audit** : si on ajoute une commande
  par feature, on finit avec un overlap (par ex. plusieurs `/lint-*`
  qui se chevauchent). Préférer étendre une commande existante.
- **Hook qui bloque sans message clair** : si un hook refuse une
  action, il doit dire **pourquoi** et **comment résoudre**.
- **Audit qui devient un sondage** : un slash command qui retourne 100
  items à examiner manuellement n'est pas actionnable. Préférer < 30
  items focalisés.
- **Hook qui modifie l'état** : un hook PreToolUse peut bloquer mais
  pas modifier silencieusement. Un PostToolUse peut analyser/lint mais
  pas modifier le fichier (sauf cas explicite documenté).
- **Tables d'inventaire dupliquées** : ne pas dupliquer la liste des
  commands/hooks dans plusieurs fichiers. Laisser
  [`commands.md`](commands.md) et [`hooks.md`](hooks.md) être les
  sources de vérité ; les autres fichiers (CLAUDE.md, claude-tooling)
  font des survols sans réplication détaillée.

## Lien avec les autres systèmes

| Système | Lien |
|---|---|
| [`self-improvement.md`](self-improvement.md) | Items d'amélioration sur slash commands et hooks vont dans `.claude/improvements.md` |
| [`backlog.md`](backlog.md) | Pas pour les outils Claude (qui vont dans improvements.md) - le backlog cible le module produit |
| [`memory-enrichment.md`](memory-enrichment.md) | Si une convention de slash command/hook se solidifie, l'enrichir dans ce fichier |
| [`commands.md`](commands.md) | Référence détaillée des slash commands actuels (table + 1 section par command) |
| [`hooks.md`](hooks.md) | Référence détaillée des hooks actuels (table + 1 section par hook) |
