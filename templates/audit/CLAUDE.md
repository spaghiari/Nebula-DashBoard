# Workspace — {{label}}

## Contexte
{{description}}

## Structure
- `checklists/` — checklists par type de cible (linux, docker, réseau, …)
- `reports/`    — rapports datés `YYYY-MM-DD-<cible>.md`
- `evidence/`   — captures, sorties de commandes, configs (gitignore)

## Tâches fréquentes
1. Auditer une config (sshd, fail2ban, nginx, docker-compose…)
2. Appliquer une checklist CIS / ANSSI
3. Générer un rapport structuré
4. Proposer une remédiation par finding (commande + impact)
5. Prioriser et trier les findings

## Conventions
- Classification stricte : **CRITIQUE** / **IMPORTANT** / **AMÉLIORATION**
- Chaque finding : description du risque, preuve (commande + sortie), commande de remédiation
- Rapport : Markdown, titre H1, résumé exécutif, puis sections par catégorie
- Jamais de mot de passe / token en clair dans les rapports
- Nom des rapports : `YYYY-MM-DD-cible.md`

## Templates de rapport
- `reports/_template.md` — rapport Markdown structuré (notes internes, checklist)
- `reports/_template.html` — rapport HTML rendu pro (livrable client/audit final)

Pour un rapport HTML, remplace toutes les variables `{{variable}}` par les valeurs réelles.
Variables obligatoires : `{{type}}`, `{{cible}}`, `{{date}}`, `{{domaine}}`, `{{score}}`,
`{{nb_critique}}`, `{{nb_important}}`, `{{nb_amelioration}}`.
Sections facultatives : bandeau révision (commenté par défaut), activité d'attaques.
