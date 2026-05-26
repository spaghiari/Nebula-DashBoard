#!/usr/bin/env bash
# Stop hook : à la fin d'un turn Claude, si des modifications non-committées
# existent dans application/, library/ ou public/, rappelle de lancer
# /check-all avant commit.
#
# Best-effort : ne bloque jamais (exit 0), juste informer.

set -u

# git dispo ?
if ! command -v git >/dev/null 2>&1; then
    exit 0
fi

# Au cas où on n'est pas dans un repo git
if ! git rev-parse --git-dir >/dev/null 2>&1; then
    exit 0
fi

# Liste les fichiers modifiés/non-suivis dans application/, library/, public/
modified="$(git status --porcelain 2>/dev/null \
    | grep -E '^[ MARCU?]?[MARCU?]? (application|library|public)/' \
    || true)"

if [ -z "$modified" ]; then
    exit 0
fi

count="$(printf '%s\n' "$modified" | wc -l | tr -d ' ')"

# Message informatif à Claude (stdout en Stop hook → renvoyé en system reminder)
{
    printf '📋 Rappel : %s fichier(s) du module modifié(s) sans commit.\n' "$count"
    printf 'Avant commit, lance /check-all pour valider :\n'
    printf '  - lint-php / views / css / js / html\n'
    printf '  - check-pitfalls (27 items)\n'
    printf '  - readme-sync (cohérence READMEs sous-dossiers)\n'
    printf '\n'
    printf 'Pour un audit ciblé moins coûteux sur 1 fichier : /contracts-audit <path>.\n'
}

exit 0
