# Notes de version

Les nouveautés de Nebula, version par version. La plus récente est en haut.
La mise à jour se fait depuis Nebula : badge « MAJ » en haut de l'écran, ou
Outils > Mises à jour.

## 2.6.0 - 2026-10-17

### Nouveautés

- **Boucle d'amélioration pilotée par Nebula** : bouton « Lancer une
  itération » dans l'onglet Amélioration. Nebula fait tourner Claude Code en
  arrière-plan (permissions restreintes, jamais de contournement) : mesure
  de départ, une seule proposition du critique, mesure du candidat, puis
  verdict. Un changement n'est gardé (et commité sur ta branche courante)
  que s'il améliore le score sans aucune régression ; sinon tout revient à
  l'identique et le diff écarté est archivé. Bouton « Arrêter » à tout
  moment, plafonds de 4 $ estimés par itération et 12 $ par jour.
- **Mode automatique** (désactivé par défaut) : jusqu'à N itérations par
  jour (de 1 à 10). Il attend qu'aucune session Claude Code ne soit ouverte
  sur le projet (il voit celles lancées par Nebula ou actives récemment),
  se met en pause si ton quota est atteint (reprise à l'heure de réinitialisation
  annoncée) ou après plusieurs rejets d'affilée (reprise sur ton clic).
- **Onglet Amélioration repensé** : la prochaine étape en premier, puis le
  score, le taux d'itérations gardées, le gain cumulé, la consommation et
  la durée moyennes, et une frise des itérations (pourquoi un changement a été gardé ou
  écarté).
- **Abonnement Claude détecté** (Pro, Max, API) depuis la configuration
  locale de Claude Code, sans lire tes jetons, et corrigeable dans Outils.
  Des avertissements signalent les réglages gourmands pour ton abonnement,
  à l'activation de l'équipe et dans l'onglet Amélioration.
- **Visite guidée enrichie** : 13 étapes, dont les modules, l'équipe
  d'agents et l'amélioration mesurée.
- **Méthode de délégation sobre** pour l'équipe d'agents : petites tâches
  sur des fichiers distincts, en parallèle, l'exécutant économique par
  défaut, des tests ciblés pendant le travail et la suite complète une
  seule fois à la fin. Les sessions longues et coûteuses deviennent rares.

### À faire après la mise à jour

1. Redémarre le dashboard.
2. Sur chaque projet où l'équipe d'agents est active : onglet
   Configuration, ligne « Équipe d'agents », **Ré-appliquer**. Cela installe
   la nouvelle méthode de délégation et la commande `/improve` qui
   comprend les itérations lancées par Nebula (l'ancienne version est
   sauvegardée en `.bak`). Relance ensuite Claude Code sur ce projet.
3. Vérifie ton abonnement dans Outils, carte « Mon abonnement Claude », et corrige-le
   si la détection se trompe.

## 2.5.0 - 2026-10-17

### Nouveautés

- **Retirer un module** (« Auto-amélioration de Claude », « Équipe
  d'agents ») depuis l'onglet Configuration du projet, avec un aperçu avant
  de confirmer. **Rien n'est supprimé** : les fichiers du module partent dans
  une archive `.claude/.nebula-removed/<module>-<date>/`, avec une notice
  pour tout remettre en place. Dans `settings.json`, seuls les hooks du
  module sont retirés, et dans `CLAUDE.md`, seul son bloc. Tes fichiers
  modifiés, ton `.gitignore` et tes réglages locaux restent en place. Option
  « Garder ma mémoire et mes registres en place ».
- **Modèle et effort de chaque agent** réglables dans l'onglet Amélioration
  (carte « Équipe : modèle et effort ») et à l'activation de l'équipe :
  modèles sonnet, opus, haiku, fable ou celui de la session, effort de
  faible à max.
- **Propositions de réglage expliquées**, appliquées seulement si tu
  cliques : règles par rôle (ex. « élevé » pour l'architecte et le
  relecteur) et un cran d'effort en plus pour un agent qui échoue aux
  évaluations. Jamais de baisse ni de changement de modèle automatique.

### Correctifs

- Les modèles choisis à l'activation de l'équipe ne sont plus perdus lors
  d'un « Régénérer ».
- Pendant une itération `/improve` en attente de verdict, aucun réglage ne
  peut fausser la mesure (carte et Ré-appliquer verrouillés, avec
  explication).

### À faire après la mise à jour

1. Redémarre le dashboard.
2. Rien d'autre d'obligatoire : tes modules restent actifs et tes agents
   sont générés à l'identique tant que tu ne règles pas d'effort. Les
   modèles que tu avais choisis à l'activation de l'équipe sont repris
   tels quels.
3. Si ton projet est suivi par git et que tu comptes retirer un module :
   ajoute ces deux lignes à son `.gitignore` (les nouveaux projets les ont
   déjà), pour que l'archive et les sauvegardes locales ne soient pas
   commitées :

   ```
   .claude/.nebula-removed/
   .claude/settings.local.json*
   ```

## 2.4.1 - 2026-10-17

### Correctifs

- **Mises à jour qui ne se vérifiaient pas** (« v2.4.0 ? », « Jamais
  vérifié », bouton « Vérifier maintenant » sans effet) quand Nebula est
  lancé par double-clic sur `start-dashboard.bat` et que Git for Windows est
  installé sans être dans le PATH (option « Git Bash seulement ») : Nebula
  trouve maintenant git à son emplacement habituel.
- Si git échoue malgré tout, l'écran des mises à jour affiche la cause et la
  solution au lieu de rester muet.
- Les liens « Voir le projet », « Lire le README », « Signaler un problème »
  et le détail des changements pointent toujours vers le dépôt GitHub.

### À faire après la mise à jour

1. Redémarre le dashboard (le correctif est côté serveur).

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
