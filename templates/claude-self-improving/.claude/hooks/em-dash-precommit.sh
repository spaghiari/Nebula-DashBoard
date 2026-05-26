#!/usr/bin/env bash
# PreToolUse hook (matcher Bash) : intercepte les `git commit` et vérifie que
# le diff staged ne contient pas d'em-dash hors les 3 fichiers d'exception
# autorisés (CLAUDE.md, CONTRIBUTING.md, .claude/commands/check-pitfalls.md).
#
# Bloque le commit (exit 2) si violation détectée.

set -u

# Lire stdin
input="$(cat)"
if [ -z "$input" ]; then
    exit 0
fi

# Extraire la command Bash
command="$(printf '%s' "$input" \
    | grep -oE '"command"[[:space:]]*:[[:space:]]*"[^"]*"' \
    | head -n 1 \
    | sed -E 's/.*"command"[[:space:]]*:[[:space:]]*"([^"]*)".*/\1/')"

if [ -z "$command" ]; then
    exit 0
fi

# Filtrer : seulement les git commit
case "$command" in
    *"git commit"*) ;;
    *) exit 0 ;;
esac

# git dispo ?
if ! command -v git >/dev/null 2>&1; then
    exit 0
fi

# Diff staged + grep em-dash, en excluant les 3 fichiers d'exception
violations="$(git diff --cached --no-color 2>/dev/null \
    | grep -nE '^\+.*—' \
    | head -n 20 \
    || true)"

if [ -z "$violations" ]; then
    exit 0
fi

# Vérifier que les violations ne sont pas dans les 3 fichiers d'exception.
# Approche pragmatique : récupérer la liste des fichiers staged contenant
# des ajouts d'em-dash, retirer les 3 exceptions.
files_with_em_dash="$(git diff --cached --name-only 2>/dev/null \
    | while read -r f; do
        if git diff --cached --no-color -- "$f" 2>/dev/null \
            | grep -qE '^\+.*—'; then
            printf '%s\n' "$f"
        fi
    done)"

# Filtrer les exceptions
problem_files="$(printf '%s\n' "$files_with_em_dash" \
    | grep -vE '^(CLAUDE\.md|CONTRIBUTING\.md|\.claude/commands/check-pitfalls\.md)$' \
    || true)"

if [ -z "$problem_files" ]; then
    # Toutes les violations sont dans les fichiers d'exception, OK
    exit 0
fi

# Bloquer
{
    printf '⛔ Em-dash (—) détecté dans le diff staged hors fichiers d'\''exception :\n'
    printf '%s\n' "$problem_files" | sed 's/^/  - /'
    printf '\n'
    printf 'Convention projet : remplacer par "-" ou ":". Exceptions autorisées :\n'
    printf '  CLAUDE.md, CONTRIBUTING.md, .claude/commands/check-pitfalls.md\n'
    printf '\n'
    printf 'Pour voir les lignes : git diff --cached | grep -n "—"\n'
} >&2

exit 2
