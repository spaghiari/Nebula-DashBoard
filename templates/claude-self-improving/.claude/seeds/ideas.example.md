
<!-- EXEMPLE seed (profondeur complète). À supprimer après lecture. -->

### Outillage Claude (capacités méta)

- **[ABANDONED] EXEMPLE — supprimer après lecture : ajouter un hook de lint syntaxique au PostToolUse** (proposée {{date}} par {{author}} lors du bootstrap de `{{label}}`)
  - Constatation : aucun lint n'est lancé automatiquement après une édition de code ; une erreur de syntaxe peut passer jusqu'au `/check-all` manuel (cf. `.claude/hooks/README.md § Hooks à ajouter par projet`).
  - Idée : ajouter un hook `PostToolUse Edit|Write|MultiEdit` qui lance le linter de la stack (`python -m py_compile`, `node --check`, `php -l`, ...) sur le fichier fraîchement modifié et alerte si parse error.
  - Bénéfice attendu : feedback immédiat sur les erreurs de syntaxe, sans attendre le commit. Coût : ~1 hook + 1 entrée settings.json.
  - Effort estimé : S
  - Note : ceci est un EXEMPLE de format. Le remplacer par de vraies idées et supprimer ce bloc.
