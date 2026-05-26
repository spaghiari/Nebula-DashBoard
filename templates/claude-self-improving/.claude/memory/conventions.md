# conventions

Hub des conventions du projet : workflow git, tests, hooks
d'automatisation, conventions de code, méta-conventions de pilotage
du système. À lire pour les détails ; les règles ALWAYS-ON sont
rappelées dans `CLAUDE.md`.

## Sous-thématiques

### Méta-pilotage (les doctrines)

| Fichier | À lire avant |
|---|---|
| [`pipeline.md`](conventions/pipeline.md) | Comprendre le flux 4 stages IDEAS / VALIDATED / IN PROGRESS / DONE qui orchestre les 4 registres d'engagement (`ideas`, `backlog`, `roadmap`, `improvements`) |
| [`digests.md`](conventions/digests.md) | 5ème registre (hebdomadaire). Producteur de digests verticaux pour la hiérarchie. Doctrine séparée du pipeline d'engagement. |
| [`memory-classification.md`](conventions/memory-classification.md) | Test à 3 questions obligatoire avant toute écriture de mémoire (user-locale vs projet versionnée) |
| [`memory-enrichment.md`](conventions/memory-enrichment.md) | Auto-enrichissement de la mémoire projet : signaux, recettes par type, anti-patterns |
| [`self-improvement.md`](conventions/self-improvement.md) | Auto-amélioration des outils Claude eux-mêmes (`improvements.md`) |
| [`ideas-generation.md`](conventions/ideas-generation.md) | Auto-production d'idées (`ideas.md`) : funnel pré-engagement, modes de production, tri |
| [`done-lifecycle.md`](conventions/done-lifecycle.md) | Cycle de vie des items DONE : récents → cristallisation → archivage |
| [`effort-sizing.md`](conventions/effort-sizing.md) | Barème XXS-XXL, règle de découpage des features XL+, mesure effort humain vs IA + ratio |
| [`backlog.md`](conventions/backlog.md) | Gestion du backlog (priorisation P0/P1/P2, cycle de vie) |
| [`roadmap.md`](conventions/roadmap.md) | Gestion de la roadmap (vision, axes, jalons) |
| [`multi-agent.md`](conventions/multi-agent.md) | Délégation au sous-agent expert + patterns de sous-agents |
| [`parallelization.md`](conventions/parallelization.md) | Multi-tool calls et forks parallèles pour réduire le wall-clock |
| [`commands-and-hooks.md`](conventions/commands-and-hooks.md) | Maintenance continue des slash commands et hooks (cycle de revue, signaux) |

### Code et workflow projet (à instancier)

Les fichiers ci-dessous sont à créer pour chaque projet selon sa
stack technique :

| Fichier (à créer) | Contenu |
|---|---|
| `conventions/git.md` | Format de commit, branches, version inline, etc. |
| `conventions/<langage>.md` | Conventions code spécifiques (PHP, Go, TypeScript, ...) |
| `conventions/testing.md` | Tests manuels / automatisés, checklist déploiement |
| `conventions/playbooks.md` | Recettes pas-à-pas (ajouter une mutation, release, etc.) |
| `conventions/commands.md` | Référence détaillée des slash commands actifs |
| `conventions/hooks.md` | Référence détaillée des hooks actifs |

## Conventions ALWAYS-ON

Rappel de `CLAUDE.md` :

- Langue projet déclarée dans `memory/overview.md` (par défaut :
  français).
- **Cite `file:line`** pour toute référence de code.
- Conventions typographiques (em-dash, caractères accentués) enforced
  par hooks pre-commit.
- **Attribution d'auteur obligatoire en mode équipe** sur tous les
  items des 5 registres : `(Pn, ajouté YYYY-MM-DD par <author>)`.

## Pattern d'enrichissement de la mémoire

Quand une convention évolue ou s'enrichit :

1. Si c'est ALWAYS-ON (à appliquer immédiatement sans relecture) →
   modifier `CLAUDE.md`
2. Si c'est du détail (procédure, exemple, pitfall) → modifier le
   fichier `conventions/<thème>.md` concerné
3. Si nouveau thème transversal → créer `conventions/<nom>.md` et MAJ
   le sommaire dans ce hub
