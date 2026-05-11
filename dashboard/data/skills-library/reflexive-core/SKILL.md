---
name: reflexive-core
description: Cœur de la boucle réflexive Nebula — schéma de scoring, accès à la DB, format des propositions. Utiliser pour évaluer une interaction Claude, produire une proposition d'amélioration, ou lire les leçons accumulées.
---

# Reflexive Core

Ce skill est le contrat entre Claude et la boucle Reflexive de Nebula. Il
décrit **comment scorer** une interaction, **où lire** les données accumulées,
et **comment écrire** une proposition d'amélioration.

Tout l'état persistant vit dans :

- DB SQLite : `dashboard/data/reflexive.db` (WAL mode, `foreign_keys=ON`)
- Propositions générées : `dashboard/data/proposals/<YYYYMMDD-HHMM>-<slug>.json`
- Log d'erreurs hooks : `dashboard/data/reflexive_hook_errors.log`

## Rubrique de scoring (4 dimensions, 0–10 chacune)

| Dimension | Question principale |
|-----------|--------------------|
| **Correctness** | La réponse fait-elle vraiment ce qui a été demandé, sans casser autre chose ? |
| **Efficiency**  | Le chemin emprunté est-il direct (peu de tool uses redondants, pas d'aller-retour inutile) ? |
| **Alignment**   | La réponse respecte-t-elle les conventions du workspace (CLAUDE.md, memory, patterns en place) ? |
| **Learning**    | Y a-t-il un signal réutilisable pour les prochaines interactions (pattern récurrent, écueil à documenter) ? |

`total` = somme des 4 dimensions (0–40, colonne générée par SQLite).

### Ancrages de score (≈)

- **0–3** : raté ou très loin du but
- **4–6** : passable, gros défauts
- **7–8** : correct, attentes remplies
- **9–10** : excellent, exemplaire

## Format de sortie de l'evaluator

L'agent `evaluator` doit produire **uniquement** un objet JSON valide,
sans texte autour. Champs :

```json
{
  "correctness": 8,
  "efficiency":  7,
  "alignment":   9,
  "learning":    5,
  "flags": ["redundant-grep", "missing-claude-md-read"],
  "justification": "Tâche accomplie mais 3 greps redondants avant d'éditer."
}
```

- `flags` : tags courts kebab-case, libres mais cohérents entre sessions.
- `justification` : 1–2 phrases factuelles, pas de jugement de valeur.

## Format d'une proposition

Fichier `dashboard/data/proposals/<YYYYMMDD-HHMM>-<slug>.json` :

```json
{
  "title": "Lire CLAUDE.md avant de répondre dans homeassistant",
  "workspace_id": "homeassistant",
  "target": ".claude/skills/respect-claude-md/SKILL.md",
  "evidence_count": 7,
  "rationale": "Sur 7 interactions évaluées avec alignment <= 5, 6 n'ont pas lu CLAUDE.md.",
  "change": {
    "type": "skill_create",
    "content": "..."
  },
  "measurement_plan": {
    "criteria": "alignment score sur homeassistant",
    "threshold_dimension": "alignment",
    "threshold_value": 7.5,
    "sample_size": 10
  }
}
```

Le serveur Nebula picke ces fichiers et les insère dans la table `proposals`
(commit 5+). En attendant l'ingestion automatique, on peut les lister via
`GET /api/reflexive/proposals` (vides tant qu'aucun runner n'a hydraté la DB).

## Lectures utiles depuis Claude

- **Leçons appliquées récemment** : `proposals WHERE status='applied'`
- **Plans de mesure actifs** : `measurement_plans WHERE status='active'`
- **Dimensions faibles à viser** : agrégat des `evals` par dimension sur 30j

Le hook `SessionStart` (load_context.py) fait déjà la synthèse de tout ça
en début de session — pas besoin de re-requêter sauf besoin précis.

## Garde-fous

- **Ne JAMAIS écrire dans la DB depuis un agent** : seuls les hooks Nebula
  et les routes API ont la responsabilité d'écrire. Un agent qui veut
  enregistrer un score le rend en JSON ; c'est l'orchestrateur côté hook
  qui l'insère.
- **Ne JAMAIS générer une proposition à partir d'une seule interaction** :
  exiger ≥ 5 occurrences cohérentes avant de proposer un changement.
- **Une proposition = un changement atomique** : pas de PR géante. Si plusieurs
  axes émergent, plusieurs fichiers de propositions.
