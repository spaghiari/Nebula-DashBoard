# Conventions de réponse

<!--
Règles générales que Claude Code doit suivre.
Personnalise selon tes préférences.
-->

- Répondre en français, code et logs en anglais
- Toujours proposer une version testable immédiatement (pas de pseudo-code)
- Réponses concises, orientées action — pas de résumé final inutile
- Jamais de secrets en clair dans les fichiers versionnés ; utiliser `.env.local` + `${VAR}`
- Pour les scripts `.bat` : éviter les caractères `& | < > ^ " %` dans les chaînes interpolées
