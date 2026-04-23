# Workspace — {{label}}

## Contexte
{{description}}

## Structure
- `workflows/`   — exports JSON (n8n), fichiers YAML, scripts
- `scripts/`     — helpers locaux (bash, powershell, python)
- `credentials.md` — référentiel des creds (nom, type, scope — **pas les valeurs**)
- `notes.md`     — journal

## Tâches fréquentes
1. Construire un workflow (trigger → transformation → action)
2. Brancher un webhook entrant + valider la signature
3. Chaîner plusieurs APIs avec gestion de retry / backoff
4. Documenter un flux (diagramme texte ou mermaid)
5. Exporter en JSON versionnable

## Conventions
- Nommage explicite des étapes (`GET weather API`, pas `HTTP`)
- Tout credential passe par `.env.local` / gestionnaire de secrets — jamais dans les exports
- Retry exponentiel par défaut sur appels externes (3 essais, backoff 1→4s)
- Documenter payload attendu + payload retourné par chaque intégration
