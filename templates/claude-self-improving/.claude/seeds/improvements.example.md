
<!-- EXEMPLE seed (profondeur complète). À supprimer après lecture. -->

### Exemples (à supprimer)

- **[ABANDONED] EXEMPLE — supprimer après lecture : préciser le brief de délégation à `{{name}}-expert`** (P2, ajouté {{date}} par {{author}})
  - Cible : `.claude/agents/{{name}}-expert.md`
  - Symptôme : sur une première feature, l'agent expert lit trop large (charge toute la mémoire) faute de pointeurs précis dans le brief.
  - Cause probable : le brief de délégation ne liste pas les `file:line` cibles ni le pattern de référence à reproduire.
  - Action proposée : enrichir le prompt de délégation type avec une checklist « contexte fonctionnel + cibles probables + pattern de référence » (cf. `conventions/multi-agent.md § Comment déléguer`).
  - Bénéfice attendu : moins de tokens de lecture, livrable plus ciblé.
  - Note : ceci est un EXEMPLE de format. Le remplacer par de vrais items et supprimer ce bloc.
