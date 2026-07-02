# Bootstrap — première conversation

Protocole déclenché quand `CLAUDE.md § Projet` affiche « Non
initialisé », ou quand l'utilisateur dit « **bootstrap le projet** ».

Objectif : remplir `CLAUDE.md` et `.claude/memory/overview.md` par une
courte conversation, sans que l'utilisateur touche un seul fichier.
Claude pose les questions, puis édite lui-même les fichiers.

## Étape 0 — placeholders résiduels

Si des `{{label}}` / `{{name}}` subsistent dans les fichiers (cas d'un
bootstrap manuel, hors application via Nebula) :

1. Demander le **nom du projet** (→ `{{label}}`) et le **préfixe court**
   pour les agents et identifiants (→ `{{name}}`, ex. `app`).
2. Les substituer dans tous les fichiers `.md` / `.json` / `.py` de
   `.claude/` et dans `CLAUDE.md`.

Si l'overlay a été appliqué via Nebula, la substitution est déjà faite :
passer cette étape.

## Étape 1 — les 5 questions (une par une)

Poser une question, attendre la réponse, confirmer, enchaîner.

1. **Nom et rôle du projet** — 2-3 phrases : à quoi il sert, dans quel
   contexte technique, qui le maintient.
2. **Stack technique** — langages, frameworks, versions, base de
   données. Si l'utilisateur ne sait pas encore : « À définir ».
3. **Commandes principales** — build, tests (un seul + tous), lint /
   format, démarrage dev. Si inconnu, proposer les standards de la
   stack déclarée.
4. **Structure du projet** — si le code existe, la lister (`ls` /
   `find` / `git ls-files`) ; s'il n'existe pas encore, proposer une
   arborescence standard pour la stack.
5. **Mode, langue et pièges** :
   - **Mode projet** : `solo` (défaut) / `équipe` / `équipe-hiérarchique`
   - **Langue** : français (défaut) / anglais
   - Des **pièges ou contraintes** connus d'entrée ? (monorepo, base en
     lecture seule en prod, legacy à ne pas toucher…)

## Étape 2 — écrire les fichiers

1. **`CLAUDE.md § Projet`** : renseigner Nom, Stack, Mode. Retirer le
   commentaire de déclenchement du bootstrap.
2. **`.claude/memory/overview.md`** : remplir *Project context*, cocher
   la case du **Mode projet**, de la **Langue** et de l'**Identité
   auteur** ; remplir *Repository layout*, *Commandes ops courantes*,
   *Décisions techniques structurantes*. Mettre la date du jour dans les
   décisions de bootstrap.
3. **Mode solo** : s'assurer que `.claude/settings.local.json` contient
   `{"validate_author": false}` (déjà posé si appliqué via Nebula ;
   sinon le créer) — sinon le hook `improvements-validate.py` exigera un
   champ `par <author>` sur chaque item de registre.
4. **Pièges mentionnés** → les ajouter dans
   `.claude/memory/pitfalls.md § Spécifiques au projet`.
5. **Cohérence des liens** : dans le sommaire mémoire de `CLAUDE.md`, ne
   garder que les hubs réellement présents dans `.claude/memory/`
   (retirer les liens morts en profondeur minimale ; recréer un hub
   quand le besoin apparaît — règle du 3). Idem pour les spokes
   `conventions/*.md` et `pitfalls/*.md` référencés mais absents.
6. **Linters** : adapter `.claude/hooks/post-edit.py` et la commande
   `/check-all` aux linters réels de la stack.

## Étape 3 — résumer

Lister ce qui a été configuré, confirmer que le projet est prêt, et
proposer les 2-3 gestes suivants les plus utiles (créer un hub mémoire,
première feature, etc.).

## Ton de la conversation

Direct et efficace. Une question à la fois, on enchaîne. Pas de blabla.
L'utilisateur veut que ce soit rapide.
