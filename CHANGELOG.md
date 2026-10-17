# Notes de version

Les nouveautés de Nebula, version par version. La plus récente est en haut.
La mise à jour se fait depuis Nebula : badge « MAJ » en haut de l'écran, ou
Outils > Mises à jour.

## 2.4.0 - 2026-10-17

Première version avec des notes de version. Elle regroupe tout ce qui est
arrivé depuis la 2.3.

### Nouveautés

- **Équipe de 7 agents** (module « Équipe d'agents et amélioration
  mesurée ») : orchestrateur, chercheur, architecte, exécutant, relecteur,
  évaluateur et critique, avec un modèle par rôle. Boucle d'amélioration
  mesurée (`/eval`, `/improve`, `/eval-add`) et onglet « Amélioration » du
  workspace.
- **Routage automatique** : en mode auto, Claude délègue par défaut aux
  agents dès qu'il y a du code à produire. Les demandes larges sur tout le
  projet (« retravaille ce projet », « réorganise l'application ») passent par
  l'orchestration complète (`/team`).
- **Retrouver ses projets** :
  - « + Dossier » sait adopter **plusieurs projets d'un dossier** d'un coup ;
  - bouton **« Parcourir… »** qui ouvre le sélecteur de dossier du système ;
  - les projets dont Claude Code a effacé l'historique (après 30 jours) sont
    de nouveau proposés à l'import.
- **Mises à jour plus visibles** : Nebula vérifie à chaque ouverture de la
  page, et la section Outils > Mises à jour montre l'état, les changements
  en clair et des liens vers le projet, le README et le signalement de
  problèmes.
- **« Ré-appliquer » met à jour un module** déjà actif : ses hooks et ses
  commandes passent à la nouvelle version (ancienne version gardée en
  `.bak`), sans toucher à ton contenu.
- Page Aide : nouveau thème « Modules ».

### Correctifs

- « Reprendre » s'affiche bien après la fermeture du terminal d'une première
  session.
- Bouton « Tester » d'un MCP HTTPS : plus de faux « certificat invalide »
  avec une PKI interne (Python 3.13).
- Hooks des modules utilisables sous macOS / Linux quand seul `python3`
  existe.
- Icône « Requiert » de la carte d'un module affichée à la bonne taille.
- Sécurité : chemins du manifeste d'équipe confinés au projet ; sélecteur de
  dossier protégé contre l'injection d'options ; aucun identifiant du dépôt
  ne remonte au navigateur.

### À faire après la mise à jour

1. Redémarre le dashboard si Nebula le demande.
2. Sur chaque projet où « Équipe d'agents » est actif : onglet Configuration,
   **Ré-appliquer** sur le module, pour recevoir le nouveau routage.
3. Relance Claude Code dans ces projets, puis vérifie avec `/agents`.
