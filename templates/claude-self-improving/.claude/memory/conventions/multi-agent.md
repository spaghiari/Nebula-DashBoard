# conventions/multi-agent

Pattern de délégation multi-agent à 2 niveaux :

1. **Thread principal Claude Code -> `{{name}}-expert`** pour les
   tâches d'impl conséquentes sur le module (cf. § « Du thread
   principal vers {{name}}-expert » ci-dessous).
2. **`{{name}}-expert` -> sous-agents spécialisés ou forks** pour
   paralléliser, isoler du contexte, ou exécuter des tâches
   répétitives focalisées (cf. § « Quand déléguer » et patterns A / B
   ci-dessous).

## Du thread principal vers `{{name}}-expert`

**Règle ALWAYS-ON** : pour les tâches non triviales sur le module,
Claude principal **délègue à `{{name}}-expert`** plutôt que de
travailler directement dans le thread principal. Le coût d'un
sous-agent (~250-300K tokens pour une feature M) est précisément ce
qu'il fait gagner : isolation du contexte parent, expertise
focalisée, rapport structuré, validation 5 axes via
`{{name}}-impl-validator` en fin de mode impl.

### Pourquoi cette règle a été inscrite

Constat empirique post-refonte mémoire 4.3.0+ : la mémoire
`.claude/memory/` chargée en cache warm dans le thread principal a
créé un faux sentiment d'autonomie - Claude se met à travailler en
direct sur des features qui devraient pourtant aller à
`{{name}}-expert`. Le user (2026-05-10) a explicitement signalé que
ce comportement réduit la qualité du livrable (pas de validation
structurée 5 axes, pas d'isolation de contexte, rapport moins
formaté).

### Quand déléguer à `{{name}}-expert` (depuis le thread principal)

| Type de tâche | Délégation | Raison |
|---|---|---|
| Feature M (10-20 fichiers, design non-trivial, multi-domaines : API + controller + vues + doc) | ✅ **Oui** | Pattern complet à reproduire ou à designer, validation 5 axes obligatoire |
| Bug fix multi-fichiers (3+ fichiers touchés) | ✅ Oui | Risque de régression collatérale élevé sans review structurée |
| Refactor à effets de bord (>1 fichier) | ✅ Oui | Audit pitfalls + cohérence transverse mémoire |
| Review pré-commit conséquent (~30-60K tokens) | ✅ Oui (vers `{{name}}-impl-validator` directement, ou via `/diff-review`) | Format standardisé, verdict GO / NO-GO |
| Q&A simple sur le code | ❌ Non - traiter directement | Lecture de 1 fichier suffit |
| Fix 1-2 lignes (typo, em-dash, accent) | ❌ Non - traiter directement | Coût d'orchestration > bénéfice |
| Lecture / exploration ciblée | ❌ Non (sauf > 3 rounds de queries -> Explore) | Idem |
| Exécution d'un slash command | ❌ Non - le thread principal exécute le slash | Le slash command est déjà la routine cadrée |
| Fix critique en prod (incident) | ⚠ Selon ampleur : direct si fix 1-3 lignes évident, déléguer si analyse design nécessaire | Trade-off temps de réponse vs qualité review |

### Comment déléguer

```
Agent({
    description: "<résumé court>",
    subagent_type: "{{name}}-expert",
    prompt: "<brief auto-suffisant>"
})
```

Le brief envoyé à `{{name}}-expert` doit être **auto-suffisant** :
le sous-agent ne voit pas le thread principal. Inclure :

1. **Contexte fonctionnel** : pointage vers l'item du backlog /
   improvements + résumé en 2-3 phrases
2. **Périmètre fonctionnel précis** : ce qui est in-scope vs
   out-of-scope
3. **Pattern de référence à reproduire** si applicable (file:line
   précis)
4. **Cibles probables** identifiées en amont (à valider par l'agent)
5. **Encadrement explicite** des cas limites (non-présence,
   validation, RBAC...)
6. **Tests manuels attendus** dans le rapport final
7. **Documentation à produire** (READMEs, mémoire, PHPDoc)
8. **Workflow imposé** : lecture exhaustive -> plan -> impl ->
   `/check-all` -> délégation `{{name}}-impl-validator` -> rapport
9. **Contraintes ALWAYS-ON** rappelées (PHP 7.2, accents, em-dash,
   CSRF, encodeObjectName, deny-by-default)
10. **Pas de commit/push** : présentation du diff propre, validation
    utilisateur d'abord

### Anti-patterns spécifiques au court-circuit

- ❌ **« Le contexte est déjà chargé en cache, je peux faire moi-même »**
  → faux raisonnement. Le cache warm aide la lecture, pas la
  validation structurée. La feature mérite un sous-agent.
- ❌ **« C'est juste 5 fichiers, c'est petit »** → 5 fichiers qui
  touchent à la fois API + controller + vue = feature M, pas S.
  Vérifier le compte avant d'estimer.
- ❌ **« On va vite avec un fix direct »** → si le fix nécessite de
  lire 3+ fichiers pour comprendre, c'est déjà un signal de
  délégation.

## Quand déléguer (depuis `{{name}}-expert`)

## Quand déléguer

| Signal | Type de délégation |
|---|---|
| **Tâche répétitive sur N éléments indépendants** (ex: audit pitfalls sur 10 fichiers, lecture massive de READMEs) | Forks parallèles |
| **Sous-tâche cadrée hors du flow principal** (ex: enrichissement mémoire en fin de livrable) | Sous-agent persistant ou fork |
| **Tâche avec contexte lourd à isoler** (ex: lecture intégrale d'un gros fichier pour extraction d'info) | Fork (le résultat synthétique revient sans pollution de contexte) |
| **Tâche spécialisée récurrente** (ex: review pré-commit, audit des pitfalls profond) | Sous-agent persistant dans `.claude/agents/` |

## Quand NE PAS déléguer

- **Tâche linéaire courte** (lecture 1 fichier, fix 1 ligne) - faire
  directement, le coût d'orchestration dépasse le bénéfice
- **Tâche centrale du livrable** (impl du cœur de la feature) - reste
  dans {{name}}-expert pour cohérence
- **Tâche avec interaction utilisateur attendue** - les sous-agents ne
  peuvent pas poser de question, tout doit être tranché en amont
- **Plus de 3-4 sous-agents en parallèle** - difficile à coordonner et
  à debugger

## Pattern A : fork pour sous-tâche ad-hoc

Le fork (Agent sans `subagent_type`) hérite du contexte du parent et
exécute une sous-tâche en arrière-plan. Le résultat synthétique
revient au parent. Idéal pour :

- Recherche / lecture massive (audit, grep multi-fichiers)
- Sous-tâche cadrée hors du flow narratif principal
- Tâche dont le bruit ne doit pas polluer le contexte du parent

Pattern type :

```
{{name}}-expert :
  ├─ fork « audit pitfalls profond sur ScopeController.php »
  │     → retourne tableau de violations avec file:line
  ├─ fork « audit pitfalls profond sur HolidayController.php »
  │     → retourne tableau idem
  └─ consolide les 2 retours dans le rapport final
```

Coût : chaque fork démarre avec le contexte parent en cache (pas de
re-chargement de CLAUDE.md ou `.claude/memory/`), donc l'overhead est
modeste.

## Pattern B : sous-agent persistant spécialisé

Sous-agent défini dans `.claude/agents/<nom>.md` avec un rôle ciblé.
Démarre frais (sans contexte du parent), charge `CLAUDE.md` et la
mémoire selon ses règles. Idéal pour :

- Tâche récurrente avec format de sortie standardisé
- Spécialisation profonde (ex: `{{name}}-pitfall-auditor` qui maîtrise les
  27 items du `/check-pitfalls` à fond)
- Découpe en équipe d'agents (ex: designer + implementer + reviewer)

Sous-agents installés et exemples (à créer au besoin) :

| Sous-agent | Statut | Rôle | Prompt typique |
|---|---|---|---|
| `{{name}}-pitfall-auditor` | **Installé** | Audit profond des 27 pitfalls sur un fichier ou diff | « Audit `<file>` ou `<diff>`, retourne tableau de violations avec file:line + correction proposée » |
| `{{name}}-impl-validator` | **Installé** | Valide une impl finie en 5 axes (pitfalls, lints, docs, tests manuels, conventions). Verdict GO / NO-GO. Peut déléguer à `{{name}}-pitfall-auditor` pour l'axe 1 | « Valide `<diff>` livré, retourne matrice de validation 5 axes + verdict » |
| `{{name}}-memory-keeper` | À créer | Propose enrichissements de mémoire à partir d'un livrable | « Analyse `<commit/diff>`, propose les enrichissements de `.claude/memory/<thème>.md` qui s'imposent » |
| `{{name}}-doc-syncer` | À créer | Vérifie la cohérence des READMEs et CHANGELOG après une feature | « Diff la feature `<X>` et propose les MAJ de doc nécessaires » |

Au démarrage, ils chargent `CLAUDE.md` (et les fichiers `.claude/memory/`
qu'ils trouvent pertinents). Pas de contexte parent.

## Coordination des résultats

Quand {{name}}-expert délègue à plusieurs sous-agents en parallèle :

1. **Sérialiser les retours** dans un seul rapport au format imposé
2. **Dédupliquer** les violations / propositions identiques
3. **Hiérarchiser** par criticité (P0 d'abord)
4. **Cite la source** : « D'après `{{name}}-pitfall-auditor` : ... »

Le rapport final reste rédigé par {{name}}-expert, qui synthétise. Les
sous-agents ne s'adressent pas directement à l'utilisateur.

## Anti-patterns

### ❌ Délégation pour tout

Déléguer la lecture de 1 fichier ou un fix 1-ligne est plus coûteux que
faire directement. La délégation a un overhead (prompt, parsing, etc.).
Réserver aux tâches qui en valent vraiment la peine (parallélisme,
isolation de contexte, spécialisation profonde).

### ❌ Délégation en cascade

{{name}}-expert spawn {{name}}-pitfall-auditor qui spawn un autre
sous-agent... La cascade rend le coût et le debugging incontrôlables.
**Limiter à 1 niveau de délégation** depuis {{name}}-expert.

### ❌ Sous-agents redondants

Créer 5 sous-agents qui font des choses similaires (par ex. 5 variantes
d'audit de pitfalls par fichier) est inutile. Préférer 1 sous-agent
paramétrable.

### ❌ Délégation silencieuse

{{name}}-expert doit **annoncer** ses délégations dans son rapport :
« J'ai délégué l'audit profond de X à `{{name}}-pitfall-auditor`, voici le
retour synthétisé. ». L'utilisateur doit pouvoir tracer le coût et la
provenance des conclusions.

### ❌ Sous-agent qui ne rend pas un format propre

Chaque sous-agent doit retourner un **format standardisé** consommable
par {{name}}-expert sans transformation lourde. Si le retour est de
la prose libre, c'est mal cadré.

## Exemple complet

Cas : {{name}}-expert reçoit une demande d'implémentation feature M.

```
1. {{name}}-expert :
   - Charge CLAUDE.md + .claude/memory/<thèmes pertinents>
   - Mode design forcé (≥ 5 fichiers)
   - Produit le doc de design + STOP attente validation user

2. User valide le design.

3. {{name}}-expert :
   - Implémente les fichiers (~10-20 fichiers)
   - DÉLÈGUE en parallèle :
     ├─ fork « audit pitfalls sur les 5 fichiers PHP critiques »
     ├─ fork « lecture des 3 READMEs sous-dossiers à mettre à jour »
     └─ fork « vérif cohérence du CHANGELOG vs feature livrée »
   - Synthétise les 3 retours dans le rapport final
   - Output gates standards (Pitfalls vérifiés, /check-pitfalls, /check-all,
     Enrichissements mémoire proposés, Items backlog, Items roadmap)

4. {{name}}-expert (validation finale) :
   - DÉLÈGUE à `{{name}}-impl-validator` la matrice 5 axes (pitfalls,
     lints, docs, tests manuels, conventions globales)
   - Récupère le verdict GO / NO-GO
   - Inclut le verdict + tests manuels recommandés en sortie

5. User commit / pousse selon verdict.
```

## Pattern de délégation `{{name}}-impl-validator`

En fin de mode impl, ou pour toute review de diff conséquente
(via le slash command `/diff-review`), `{{name}}-expert` peut
déléguer la routine de QA à `{{name}}-impl-validator`. L'avantage :
isolation du contexte de validation (l'agent expert reste centré
sur l'impl, le validator gère la QA), format de sortie
standardisé, possibilité de re-déléguer en cascade contrôlée
(`{{name}}-impl-validator` peut lui-même déléguer l'axe 1 à
`{{name}}-pitfall-auditor` si > 3 fichiers critiques).

Pattern type :

```
{{name}}-expert (en fin de mode impl) :
  └─ délègue à {{name}}-impl-validator (sous-agent persistant)
        ├─ axe 1 (pitfalls) :
        │     └─ délègue éventuellement à {{name}}-pitfall-auditor
        │           (si > 3 fichiers critiques)
        ├─ axe 2 (lints projet)
        ├─ axe 3 (cohérence doc)
        ├─ axe 4 (tests manuels recommandés)
        └─ axe 5 (conventions globales)
        → matrice + verdict GO / GO avec réserves / NO-GO
  └─ inclut le verdict + checklist Axe 4 dans le rapport final
```

Limite stricte : **2 niveaux max** de délégation depuis
{{name}}-expert (validator → pitfall-auditor). Pas de cascade
au-delà.

### Mode d'invocation alternatif (diff pré-généré)

Le validator accepte deux modes d'entrée :

- **Mode 1 (standard)** : l'appelant fournit un range git
  (`main..HEAD`) ou une liste de fichiers. Le validator collecte
  lui-même le diff et l'historique via `git diff` / `git log`.
  Suppose Bash autorisé chez le validator (cas du thread
  principal Claude Code).
- **Mode 2 (dégradé)** : l'appelant pré-collecte le diff via Bash
  autorisé chez lui et le passe en clair entre marqueurs
  `===DIFF===` / `===END DIFF===` dans le prompt. Le validator
  parse directement, sans `git diff`. Suppose Bash bloqué chez le
  validator (cas d'un thread d'agent secondaire sandboxé).

Cas de bascule observé : pendant la validation post-livraison
4.3.0, `/diff-review v4.2.0..HEAD` délégué à un agent secondaire
a vu Bash refusé par sandbox -> verdict INDÉTERMINÉ. Mode 2
résoudrait ce cas en pré-collectant le diff côté thread principal
puis en le passant à un sous-agent générique pour analyse.

Protocole prompt mode 2 (à respecter par l'appelant) :

```
<contexte fonctionnel>

===DIFF===
<sortie brute de `git diff <range>`>
===END DIFF===

===COMMITS===
<sortie de `git log --format='%h %s' <range>'`, optionnel - permet
l'axe 5bis allégé limité aux sujets de commit>
===END COMMITS===
```

Verdict en mode 2 : suffixé obligatoirement par `(mode dégradé :
pas d'audit historique git)` ou `(mode dégradé : audit historique
limité aux sujets fournis)` selon le contenu du prompt.

## Nommage des sous-agents

Convention : préfixe `am-` (cohérent avec `{{name}}-expert`,
`amFilter`, etc.). Suffixe descriptif court : `-auditor`, `-keeper`,
`-validator`, `-syncer`.

Les sous-agents vivent dans `.claude/agents/<nom>.md` (versionnés). Le
frontmatter YAML standard Claude Code :

```yaml
---
name: am-xxx
description: <rôle court, ce qu'il fait, quand l'invoquer>
---
```

## Cycle de vie

| Phase | Quand |
|---|---|
| **Création d'un sous-agent** | Quand un pattern de délégation se répète et qu'un format standardisé émerge |
| **Évolution** | Si le rôle s'enrichit (par ex. nouvelles catégories de pitfalls), MAJ le sous-agent |
| **Fusion** | Si 2 sous-agents font des choses proches, les fusionner |
| **Suppression** | Si plus utilisé depuis 6+ mois, supprimer (le pattern fork peut le remplacer ad-hoc) |

## Lien avec les autres systèmes

| Système | Lien |
|---|---|
| [`memory-enrichment.md`](memory-enrichment.md) | `{{name}}-memory-keeper` peut être un sous-agent spécialisé pour proposer les enrichissements |
| [`backlog.md`](backlog.md) | Items différés de délégation (ex: « créer un sous-agent X ») vont au backlog |
| [`roadmap.md`](roadmap.md) | Évolutions long terme du système multi-agent (ex: passer en mode équipe d'agents) |
| [`playbooks.md`](playbooks.md) | Le playbook « Ajouter une mutation action » peut bénéficier d'une délégation à `{{name}}-impl-validator` en fin |
