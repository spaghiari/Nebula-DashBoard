# Auto-amélioration des agents et capacités Claude

Registre versionné des améliorations identifiées pour Claude, les
sous-agents, les slash commands, les hooks et la mémoire projet.

Convention de gestion :
[`.claude/memory/conventions/self-improvement.md`](memory/conventions/self-improvement.md).

## Légende

- **P0** : friction critique qui dégrade fortement la qualité ou le
  coût (faux résultats, hallucinations, prompts qui font dérailler)
- **P1** : friction notable (verbosity excessive, slash command
  imprécis, mémoire incomplète sur un aspect courant)
- **P2** : amélioration nice-to-have (optimisation marginale,
  refactor de prompt, simplification)

Statuts : **[TODO]**, **[IN PROGRESS]**, **[DONE]**, **[ABANDONED]**

Format d'un item :

```markdown
- **[STATUT] <titre court actionnable>** (Pn, ajouté YYYY-MM-DD par <author>)
  - Cible : `.claude/agents/{{name}}-xxx.md` (ou autre)
  - Symptôme : <comportement observé>
  - Cause probable : <pourquoi ça arrive>
  - Action proposée : <quoi changer>
  - Bénéfice attendu : <ce qu'on gagne>
```

Le champ `par <author>` est **obligatoire en mode équipe** et validé
par le hook `improvements-validate.sh` au commit. Optionnel en mode
solo.

## Items actifs

### P0 - critique

(aucun pour l'instant)

### P1 - important

(aucun pour l'instant)

### P2 - nice-to-have

(aucun pour l'instant)

## Items terminés

(aucun pour l'instant)
