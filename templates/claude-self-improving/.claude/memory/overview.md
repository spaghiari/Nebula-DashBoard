# overview

Cadre projet, décisions de bootstrap, layout du repo, commandes ops,
point d'entrée pour comprendre `{{label}}` dans son ensemble.

## Project context

(À rédiger lors du bootstrap : description en 2-3 phrases - à quoi
sert le projet, dans quel contexte technique il vit, qui le maintient,
quelle stack.)

## Mode projet

Le mode détermine plusieurs comportements transverses (attribution
d'auteur obligatoire, registre `digests` actif, hooks de validation).

- [ ] **Solo** : un seul mainteneur. Auteur implicite, registre
  `digests` inactif, hook `improvements-validate.sh` peut être passé
  en `validate_author: false`.
- [ ] **Équipe sans hiérarchie** : plusieurs contributeurs au même
  niveau. Auteur **obligatoire** sur tous les items. Pas de digests
  verticaux (le registre reste inactif sauf si besoin de cohérence
  inter-équipes).
- [ ] **Équipe avec hiérarchie** : multi-niveau (collaborateurs →
  manager → manager de managers). Auteur **obligatoire**, **digests
  hebdomadaires actifs**, transparence symétrique requise (mirror
  pour chaque subordonné).

Cocher l'une des cases ci-dessus au bootstrap. Le mode peut évoluer
(par ex. solo → équipe au moment d'embaucher un second contributeur)
- documenter le changement comme post-mortem dans
[`memory-classification.md`](conventions/memory-classification.md).

## Identité auteur

L'identifiant utilisé dans les champs `par <author>` des registres
suit la convention déclarée ici. Choisir une et **une seule**
convention au bootstrap, puis s'y tenir :

- [ ] **`git config user.name` court** (par ex. `antoine.b`)
- [ ] **Initiales** (par ex. `ab`, `mp`)
- [ ] **Email tronqué** (par ex. `antoine.b` extrait de
  `antoine.b@i-tracing.fr`)
- [ ] **Slug équipe interne** (par ex. `@antoine.b` ou identifiant
  Active Directory)
- [ ] **Autre** : (à préciser)

Le hook `improvements-validate.sh` valide la **présence** du champ
(`par <quelque-chose-de-non-vide>`) en mode équipe, pas la **forme
exacte**. La cohérence du choix est de la responsabilité de l'équipe.

## Langue projet

Tous les artefacts rédigés dans la langue déclarée ci-dessous :
commentaires de code, doc inline, READMEs, CHANGELOG, CLAUDE.md ET
messages de commit git.

- [ ] **Français**
- [ ] **Anglais**
- [ ] **Autre** : (à préciser)

## Repository layout

(À rédiger lors du bootstrap. Format type :

```
{{label}}/
├── <dossier 1>/    # description
├── <dossier 2>/    # description
└── ...
```

Le bloc équivalent existe dans le README utilisateur ; ce fichier ne
fait que pointer vers les zones avec annotations Claude-spécifiques
si pertinent.)

## Commandes ops courantes

(À rédiger lors du bootstrap : commandes de build, run, test, déploiement,
maintenance.)

## Décisions techniques structurantes

(À rédiger lors du bootstrap : choix de stack, versions minimales,
dépendances bloquantes, contraintes runtime.)
