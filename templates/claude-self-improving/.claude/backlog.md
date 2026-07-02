# Backlog du projet `{{label}}`

Actions en attente ou à adresser ultérieurement. Versionné, partagé à
toute l'équipe.

Convention de gestion :
[`.claude/memory/conventions/backlog.md`](memory/conventions/backlog.md).

## Légende

- **P0** : critique, bloquant ou risque sécurité - à adresser
  immédiatement
- **P1** : important, à adresser à la prochaine release
- **P2** : nice-to-have, sans urgence
- Statuts : **[TODO]**, **[IN PROGRESS]**, **[BLOCKED]**, **[DONE]**,
  **[ABANDONED]**

Format d'un item :

```
- **[STATUT] <titre court>** (Pn, ajouté YYYY-MM-DD par <author>)
  - Contexte : <pourquoi c'est dans le backlog>
  - Détail : <description précise, fichiers/contrats concernés>
  - Bloqué par : <si applicable>
```

Pour un item DONE livré par un autre que l'auteur initial, ajouter
aussi `livré par <author>` dans le bloc DONE.

Le champ `par <author>` est **obligatoire en mode équipe** et validé
par le hook `improvements-validate.py` au commit. Optionnel en mode
solo (cf. `CLAUDE.md § Attribution d'auteur` et `memory/overview.md
§ Mode projet`).

## Items actifs

### P0 - critique

(aucun pour l'instant)

### P1 - important

(aucun pour l'instant)

### P2 - nice-to-have

(aucun pour l'instant)

## Items terminés

(aucun pour l'instant)

## Items abandonnés

(aucun pour l'instant)
