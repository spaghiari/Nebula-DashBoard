---
description: Vérifie que chaque README.md de sous-dossier référence bien les fichiers réellement présents, et que la mémoire `.claude/memory/` est cohérente (hubs ↔ spokes, pointeurs croisés valides). Ne modifie rien.
---

Convention du projet : chaque sous-dossier code a son propre
`README.md` à maintenir en phase avec les fichiers réels. La mémoire
projet `.claude/memory/` suit le même principe : chaque hub référence
ses spokes, aucun spoke orphelin. Cette commande produit un rapport
d'écart sur les 2 axes. Elle ne modifie rien.

## Partie 1 : Sous-dossiers code

### Sous-dossiers à contrôler

À configurer pour chaque projet en éditant ce fichier au bootstrap.
Liste de référence des dossiers qui doivent avoir un `README.md`
synchronisé :

**Code projet** :

- (à compléter au bootstrap : `<dossier-1>/`, `<dossier-2>/`, ...)

**Outillage Claude** :

- `.claude/hooks/` (README liste les hooks `.sh` actifs)
- `.claude/agents/` (README liste les sous-agents)

### Pour chaque dossier

1. Liste les fichiers présents (hors `README.md` lui-même).
2. Lis le `README.md` et extrais les noms de fichiers mentionnés
   (repère par patterns d'extension et de classes selon la stack du
   projet, à définir au bootstrap).
3. Compare :
   - **Manques** : fichier présent sur disque mais absent du README.
   - **Fantômes** : fichier cité dans le README mais absent du
     disque.

### Parallélisation obligatoire

Les lectures de README sont **indépendantes**. **Regrouper les appels
`Read` dans un même message** pour exécution parallèle côté runtime -
gain wall-clock direct (typiquement -50% sur cette routine). De même
pour les listages `ls` ou `Glob` des fichiers présents par dossier
(parallélisables). Cf.
[`conventions/parallelization.md`](../memory/conventions/parallelization.md).

## Partie 2 : Mémoire `.claude/memory/`

### Structure attendue

- 11 hubs à la racine de `.claude/memory/` : `overview.md`,
  `domain.md`, `architecture.md`, `security.md`, `frontend.md`,
  `subsystems.md`, `performance.md`, `conventions.md`, `pitfalls.md`,
  `diagnostics.md`, `claude-tooling.md`.
- 5 sous-dossiers contenant des spokes : `security/`, `frontend/`,
  `subsystems/`, `conventions/`, `pitfalls/`.
- Les hubs `overview`, `domain`, `architecture`, `performance`,
  `diagnostics`, `claude-tooling` sont par défaut en single-file (pas
  de spokes), c'est attendu — un projet peut en faire évoluer
  certains en hub-and-spoke si le contenu grossit.

### Vérifications

Pour chaque hub avec spokes (`security`, `frontend`, `subsystems`,
`conventions`, `pitfalls`) :

1. Liste les spokes présents dans `<hub>/` (fichiers `.md`).
2. Lis le hub `<hub>.md` et extrais les références aux spokes
   (pattern : liens Markdown vers `<hub>/<sous>.md`).
3. Compare :
   - **Spoke orphelin** : fichier présent dans `<hub>/` mais non
     cité dans `<hub>.md`.
   - **Référence fantôme** : spoke cité dans `<hub>.md` mais absent
     du disque.

### Pointeurs croisés

Pour chaque fichier `.md` de la mémoire (hubs et spokes), vérifier
que les liens internes pointent vers des fichiers existants :

- Pattern : `[texte](../<chemin>.md)`, `[texte](<hub>/<spoke>.md)`,
  `[texte](.claude/memory/<thème>.md)`.
- Pour chaque lien, vérifier l'existence du fichier cible.
- **Lien cassé** : fichier cible absent du disque.

### Pas de scan des ancres

Ne pas vérifier les ancres `#section` (coût élevé, peu de valeur).
Juste les fichiers cibles.

## Format de sortie

```
## Partie 1 : Sous-dossiers code

### <dossier-1>/ (N fichiers)
- ✅ En phase

### <dossier-2>/ (M fichiers)
- ⚠ Manque : `<fichier>` présent mais non documenté
- ⚠ Fantôme : `<autre>` cité mais absent

(...)

## Partie 2 : Mémoire .claude/memory/

### Hubs avec spokes

#### security.md (N spokes)
- ✅ En phase

#### conventions.md (M spokes)
- ⚠ Spoke orphelin : `nouveau-thème.md` présent mais non cité dans `conventions.md`

(...)

### Pointeurs croisés
- ⚠ `pitfalls/<catégorie>.md:12` → lien vers `pitfalls/<autre>.md` (n'existe pas)
- ✅ Tous les autres pointeurs sont valides.

## Résumé global

| Périmètre | En phase | En écart |
|---|---|---|
| Sous-dossiers code | N | M |
| Mémoire (hubs/spokes) | N | M |
| Pointeurs croisés | N | M |
```

Ne modifie rien - l'utilisateur corrigera manuellement les écarts
(README sous-dossier, pointeurs cassés, sommaires des hubs).
