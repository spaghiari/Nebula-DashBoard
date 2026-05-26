---
description: Produit le brouillon du digest hebdomadaire `<YYYY-WW>-out.md` en agrégeant les signaux structurés de la semaine : diffs des 4 registres d'engagement, cristallisations mémoire, output gates d'agents, commits significatifs. Lecture des transcripts uniquement en complément. Ne publie rien automatiquement - draft proposé à l'utilisateur pour validation.
argument-hint: [YYYY-WW]
---

Production du digest hebdomadaire. Convention détaillée :
[`.claude/memory/conventions/digests.md`](../memory/conventions/digests.md).

Cette commande **ne publie rien** automatiquement. Elle produit un
draft, à l'utilisateur de valider, amender, ou rejeter avant commit.

**Argument** : `<YYYY-WW>` (optionnel). Semaine ISO 8601 à digérer.
Défaut : la semaine courante. Exemples : `2026-W19`, `2026-W20`.

## Mode projet requis

Cette commande n'a de sens qu'en **mode équipe** (cf.
`memory/overview.md § Mode projet`). En mode solo, le digest n'a pas
de destinataire ; la commande peut être lancée mais produira un draft
inutile.

## Sources à agréger

### Source 1 — Diffs des 4 registres d'engagement

Calculer le diff de chaque registre entre le **lundi de la semaine
cible 00:00** et le **dimanche 23:59** :

```bash
# Plage temporelle
since="<YYYY-MM-DD du lundi de la semaine cible>"
until="<YYYY-MM-DD du dimanche de la semaine cible> 23:59:59"

# Diff de chaque registre
git log --since="$since" --until="$until" -p -- .claude/ideas.md
git log --since="$since" --until="$until" -p -- .claude/backlog.md
git log --since="$since" --until="$until" -p -- .claude/roadmap.md
git log --since="$since" --until="$until" -p -- .claude/improvements.md
```

Extraire de chaque diff :
- **Idées nouvelles** ajoutées (statut `[NEW]`)
- **Items VALIDATED** (`[TODO]`) ajoutés au backlog/roadmap/improvements
- **Transitions** observées (`[TODO] → [IN PROGRESS]`, `[IN PROGRESS]
  → [DONE]`, `[IN PROGRESS] → [BLOCKED]`)
- **Promotions** d'idées (`[PROMOTED -> registre]`)

**Conserver `par <author>`** sur chaque item — c'est ce qui permet
au compileur du N+1 (s'il existe) d'attribuer correctement quand il
agrège les digests incoming de ses subordonnés.

### Source 2 — Cristallisations mémoire récentes

```bash
git log --since="$since" --until="$until" --name-only \
    -- .claude/memory/ | grep '\.md$' | sort -u
```

Pour chaque fichier de mémoire enrichi cette semaine :
- Lire le diff
- Extraire l'ajout net (sections nouvelles, items ajoutés)
- Résumer en 1 ligne par enrichissement

### Source 3 — Output gates d'agents (transcripts)

Les sessions Claude des sous-agents produisent en fin de mode des
sections normalisées : « Idées proactives identifiées », « Items
backlog identifiés », « Enrichissements mémoire proposés », « Tests
manuels recommandés », « Items improvements identifiés ».

Si l'environnement permet de retrouver les transcripts (par exemple
via le storage Claude Code dans `~/.claude/projects/`), grep ces
sections. Sinon, indiquer dans le draft « Transcripts non
disponibles - section partielle ».

### Source 4 — Commits significatifs

```bash
git log --since="$since" --until="$until" \
    --format='%h %s' --no-merges
```

Filtrer les commits :
- `feature(*)` et `fix(*)` → travaux livrés
- `doc(*)` → enrichissements mémoire (croiser avec source 2)
- `update(*)` → travaux livrés (ajustements non-features)
- `push(*)` → publications externes (rare)

Pour chaque commit `feature` ou `fix` : faire le lien avec l'item
DONE correspondant dans `backlog.md` ou `improvements.md` quand
identifiable par titre.

## Méthode

### Étape 1 — Pré-vol

1. Valider `$1` : format `YYYY-WNN` (regex `^[0-9]{4}-W[0-9]{2}$`).
   Si absent, calculer la semaine courante avec `date +"%G-W%V"`.
2. Calculer les bornes lundi 00:00 et dimanche 23:59 de la semaine.
3. Identifier l'auteur (cf. `memory/overview.md § Identité auteur`).
4. Vérifier qu'aucun fichier `digests/<YYYY-WW>-out.md` n'existe déjà
   (sinon : signaler à l'utilisateur, proposer écrasement ou abandon).

### Étape 2 — Agrégation (parallélisable)

Lancer en **parallèle** (multi-tool calls dans un même message) :
- Source 1 : 4 `git log` sur les registres
- Source 2 : 1 `git log` sur `memory/`
- Source 4 : 1 `git log` sur les commits

Source 3 (transcripts) si activée : grep parallèle aux autres.

### Étape 3 — Composition du draft

Suivre le format documenté dans
[`conventions/digests.md § Format d'un digest outgoing`](../memory/conventions/digests.md).
Sections à remplir, dans cet ordre :

1. Travaux livrés
2. Idées poussées (non discutées)
3. Travaux en cours
4. Directives reçues et appliquées cette semaine
5. Demandes implicites au N+1
6. Patterns transverses détectés
7. Enrichissements mémoire de la semaine
8. Métriques

**Appliquer la charte éditoriale** documentée dans
[`digests.md § Charte éditoriale du compileur`](../memory/conventions/digests.md) :
préserver toujours les idées originales, agréger les statuts récurrents,
supprimer les explorations ratées, marquer `[à arbitrer]` les cas
litigieux.

### Étape 4 — Proposition à l'utilisateur

Présenter le draft selon le pattern documenté dans
[`digests.md § Pattern de proposition à l'utilisateur`](../memory/conventions/digests.md).
Mettre en évidence les choix éditoriaux qui méritent arbitrage.

### Étape 5 — Publication (si validation)

Si l'utilisateur valide :
1. Écrire `digests/<YYYY-WW>-out.md` avec le contenu finalisé.
2. Commit dédié : `doc({{label}}): digest <YYYY-WW> de <author>`.

Si l'utilisateur rejette ou veut repartir : abandonner sans écrire.

## Format de sortie de la commande

```markdown
## Digest hebdomadaire <YYYY-WW> — draft

Période : <YYYY-MM-DD> → <YYYY-MM-DD>
Auteur : <author>
Sources lues :
- 4 registres : N items modifiés (idées : x, backlog : y, roadmap :
  z, improvements : w)
- mémoire : M fichiers enrichis
- commits : K commits non-merge
- transcripts : <disponibles / partiels / indisponibles>

---

<draft complet au format `digests.md`>

---

Choix éditoriaux qui méritent ton arbitrage :
1. <item litigieux 1> — proposé inclus / à arbitrer
2. <item litigieux 2> — proposé omis / à arbitrer

Options :
- ✅ Publier tel quel
- ✏ Amender (préciser les changements)
- 🔄 Repartir de zéro
- ❌ Abandonner sans publication
```

## Anti-patterns

- **Inclure du verbatim transcript** : interdit par la doctrine. Les
  transcripts sont LUS, leur contenu EXTRAIT, jamais COPIÉ.
- **Inventer une métrique non sourcée** : les métriques de la
  section finale doivent toutes provenir des registres ou de mesures
  réelles (durée wall-clock, tokens). Pas d'extrapolation.
- **Publier sans validation utilisateur** : interdit par la doctrine.
  Le draft est toujours présenté avant écriture.
- **Cascade lossy non documentée** : si ce digest est destiné à être
  agrégé par un manager (N+1) dans son propre digest la semaine
  suivante, chaque item doit pouvoir pointer vers sa source pour
  préserver le drill-down. Ne pas oublier les références (commit
  hash, lien vers item dans registre).

Lance l'agrégation. Produis le draft. Stop avant écriture.
