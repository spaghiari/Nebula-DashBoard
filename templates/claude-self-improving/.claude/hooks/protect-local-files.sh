#!/usr/bin/env bash
# PreToolUse hook : refuse toute Edit/Write/MultiEdit ciblant un fichier
# user-local protégé : CLAUDE.local.md, .claude/settings.local.json.
#
# Ces fichiers contiennent des notes/préférences user-locales qui ne doivent
# jamais être touchées par Claude (consigne projet).

set -u

input="$(cat)"
if [ -z "$input" ]; then
    exit 0
fi

# Extraire file_path
file_path="$(printf '%s' "$input" \
    | grep -oE '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' \
    | head -n 1 \
    | sed -E 's/.*"file_path"[[:space:]]*:[[:space:]]*"([^"]*)".*/\1/')"

if [ -z "$file_path" ]; then
    exit 0
fi

# Normaliser : extraire le basename ou matcher sur la fin du path
case "$file_path" in
    *CLAUDE.local.md|*"CLAUDE.local.md")
        printf '⛔ Modification de CLAUDE.local.md interdite (notes user-locales gitignored).\n' >&2
        printf 'Si tu as besoin de mettre à jour la mémoire projet, édite CLAUDE.md à la racine.\n' >&2
        exit 2
        ;;
    *settings.local.json|*"settings.local.json")
        printf '⛔ Modification de .claude/settings.local.json interdite (préférences user-locales).\n' >&2
        printf 'Pour ajouter une permission projet, édite .claude/settings.json à la place.\n' >&2
        exit 2
        ;;
esac

exit 0
