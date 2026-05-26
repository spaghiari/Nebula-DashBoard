# Registre digests — synthèses hebdomadaires

5ème registre du projet. Matérialise la couche verticale d'échange
d'information entre un contributeur et sa hiérarchie.

Convention de gestion :
[`.claude/memory/conventions/digests.md`](../memory/conventions/digests.md).

## Structure

```
.claude/digests/
├── README.md                              # ce fichier
├── <YYYY-WW>-out.md                       # ce que je produis chaque semaine (push N+1)
├── <YYYY-WW>-in/                          # ce que je reçois de mes N-1 (si manager)
│   ├── <author-1>.md
│   └── <author-2>.md
├── <YYYY-WW>-mirror.md                    # comment je suis cité par mon N+1 (transparence)
└── archive/
    └── <YYYY>/                            # digests > 90 jours
        ├── <YYYY-WW>-out.md
        └── ...
```

## Activation par mode de projet

| Mode projet | `out.md` | `in/` | `mirror.md` |
|---|---|---|---|
| **Solo** (mono-mainteneur, pas de hiérarchie) | Non | Non | Non |
| **Équipe sans hiérarchie** (peer collaboration) | Optionnel (digest interne) | Non | Non |
| **Équipe avec hiérarchie** (N+1 défini) | **Obligatoire** | Si manager | **Obligatoire si actif** |

Le mode du projet est déclaré dans
[`memory/overview.md § Mode projet`](../memory/overview.md).

## Pas de digest sans validation utilisateur

Le digest est **proposé** par l'agent compileur, **validé** par
l'utilisateur, **commit** par lui aussi. Aucune publication
automatique. C'est explicitement codifié dans la doctrine.

## Nommage

- **Semaine ISO 8601** : `<YYYY>-W<NN>` au format `2026-W19` →
  fichier `2026-W19-out.md`.
- **Auteur** : identifiant court selon la convention du projet (cf.
  [`overview.md § Identité auteur`](../memory/overview.md)).

## Cycle de vie

| Phase | Localisation |
|---|---|
| Brouillon (en cours d'agrégation) | Pas de fichier, buffer de session |
| Validé et publié | `digests/<YYYY-WW>-out.md` (ou variantes) |
| Référencé | Lien depuis les digests suivants (drill-down) |
| Archivé (> 90 jours) | `digests/archive/<YYYY>/<YYYY-WW>-*.md` |
