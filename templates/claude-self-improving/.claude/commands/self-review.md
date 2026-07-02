---
description: Routine d'auto-amélioration des outils Claude (commands, hooks, mémoire, agents, registres). Audit léger qui identifie les frictions et propose des items à inscrire dans `.claude/improvements.md`. Aucune modification automatique.
---

Routine d'auto-amélioration **read-only** qui audite les outils Claude
du projet pour identifier les frictions à inscrire au registre
[`.claude/improvements.md`](../improvements.md). Convention détaillée :
[`.claude/memory/conventions/self-improvement.md`](../memory/conventions/self-improvement.md).

Cette commande **ne modifie rien**. Elle produit un rapport. À toi de
trancher si les items identifiés vont au registre, sont fixés
directement, ou sont ignorés.

## Cibles d'audit

### 1. Cohérence des références versionnées

Grep dans `.claude/` (mémoire, agents, commands, hooks, registres) des
mentions de version (`X.Y.Z`, `actuel : X.Y.Z`, `depuis X.Y.Z`,
`X.Y.Z+`). Comparer avec la version courante du `module.info`.

Friction si une mémoire générale (par ex. `overview.md`,
`conventions/git.md`) mentionne une version obsolète. Les mentions
« depuis X.Y.Z » dans les fichiers thématiques (architecture, domain,
features Holiday/SMS/etc.) sont **conservées** car elles datent les
features livrées à cette version.

### 2. Pointeurs croisés dans la mémoire

Grep des liens Markdown dans `.claude/` pointant vers `.claude/memory/`,
`.claude/<fichier>.md`, `CLAUDE.md`, autres `.md` du projet. Pour
chaque lien, vérifier que le fichier cible existe.

Friction si un pointeur cible un fichier supprimé/déplacé.

### 3. Hubs ↔ spokes de la mémoire

Pour chaque hub avec spokes (`security`, `frontend`, `subsystems`,
`conventions`, `pitfalls`) :

- Liste les spokes présents dans `<hub>/`
- Liste les spokes référencés dans `<hub>.md` (sommaire)
- Compare : spoke orphelin (présent mais non référencé) ou référence
  fantôme (référencé mais absent)

Friction si écart constaté.

Note : `/readme-sync` Partie 2 fait déjà ce check de manière
exhaustive. `/self-review` peut s'en remettre à `/readme-sync` pour
cet axe (ne pas dupliquer).

### 4. Cohérence des registres

`.claude/improvements.md`, `.claude/backlog.md`, `.claude/roadmap.md` :

- Format des items conforme aux conventions ?
- Statuts dans la whitelist ?
- Priorités P0/P1/P2 ?
- Dates au format YYYY-MM-DD ?

Note : le hook `improvements-validate.py` fait ce check au commit. La
commande `/self-review` peut s'en remettre au hook pour cet axe (mais
peut signaler les items en `IN PROGRESS` qui traînent depuis longtemps,
ou les `BLOCKED` à débloquer).

### 5. Cohérence de l'agent `{{name}}-expert`

Vérifier que les pointeurs vers `.claude/memory/<thème>.md` dans le
prompt de l'agent existent. Vérifier que les sous-agents listés
(`{{name}}-pitfall-auditor`, etc.) existent bien dans `.claude/agents/`.

Friction si pointeur cassé ou sous-agent listé absent.

### 6. CLAUDE.md vs sommaire de la mémoire

Vérifier que les 11 hubs listés au sommaire de `CLAUDE.md` existent
bien dans `.claude/memory/`. Vérifier qu'aucun hub ne manque au
sommaire.

Friction si écart.

### 7. READMEs `.claude/{hooks,agents}/`

Vérifier que `.claude/hooks/README.md` liste tous les `.sh` présents,
et que `.claude/agents/README.md` liste tous les `.md` agents.

Friction si écart.

Note : `/readme-sync` couvre cet axe également.

## Format de sortie

```markdown
## Routine d'auto-amélioration - rapport

**Date** : YYYY-MM-DD
**Cibles auditées** : 7 axes
**Frictions détectées** : N

### Frictions

| # | Friction | Sévérité | Cibles |
|---|---|---|---|
| 1 | <description> | P1 | <fichier:ligne> |
| 2 | <description> | P2 | <fichier> |

### Items satellites observés (sans friction immédiate)

- ✅ <axe vérifié sans écart>

### Proposition

Pour chaque friction, propose à l'utilisateur :
- Option A : fixer maintenant en commits thématiques
- Option B : inscrire au registre `.claude/improvements.md` comme TODO
- Option C : ignorer (justifier)

L'utilisateur tranche. Pas d'action sans validation.
```

## Cycle recommandé

| Quand | Quoi |
|---|---|
| Après une release majeure (X.Y.0) | Auto-amélioration complète sur les 7 cibles |
| Trimestriellement | Audit léger sur les axes 1-2-3 (versions, pointeurs, hubs/spokes) |
| Sur signal | Si hallucination ou friction observée pendant une session, lancer `/self-review` ciblé |

## Anti-patterns

- **Modifier en silence** : `/self-review` est read-only par
  conception. Toujours proposer à l'utilisateur.
- **Inscrire 100 items au registre** : si le rapport remonte > 10
  frictions, c'est qu'on a sur-audité. Cibler les axes vraiment
  critiques.
- **Doublonner avec `/readme-sync` ou `improvements-validate.py`** :
  ces 2 outils couvrent déjà des axes. `/self-review` les complète,
  ne les remplace pas.

Lance la routine. Produis le rapport. Stop.
