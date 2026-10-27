# Politique de sécurité

## Signaler une vulnérabilité

Utilise le **signalement privé de GitHub** : onglet *Security* du dépôt,
puis *Report a vulnerability*. N'ouvre pas d'issue publique pour une faille.

Indique la version de Nebula, le système, et les étapes pour reproduire.

## Périmètre

Nebula est un outil **local** : le serveur écoute sur `127.0.0.1`, sans
compte ni télémétrie. Sont notamment pertinents :

- contournement de la validation de l'en-tête `Host` ou de `X-Nebula-XHR` ;
- lecture ou écriture de fichiers hors des dossiers autorisés ;
- fuite de secrets (`.env.local`, jetons) dans les réponses API ou les logs ;
- exécution de commandes via les routes de lancement, d'import ou de mise à jour.

## Versions prises en charge

Seule la dernière version publiée (voir `CHANGELOG.md`) reçoit des correctifs.
