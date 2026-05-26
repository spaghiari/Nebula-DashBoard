#!/usr/bin/env bash
# PreToolUse hook (matcher Bash) : intercepte les `git commit` et bloque
# si le message contient le trailer `Co-Authored-By: Claude`
# (case-insensitive). Convention projet (CLAUDE.md règle ALWAYS-ON git) :
# aucun trailer Co-Authored-By Claude dans aucun commit.
#
# Symétrique à em-dash-precommit.sh.
#
# Approche : grep tolérant directement sur le JSON brut stdin, plutôt
# que d'extraire le command field (qui casse sur les heredocs
# $(cat <<'EOF' ... EOF) à cause des escapes JSON sur les guillemets).
# Le pré-filtre s'appuie quand même sur l'extraction du command pour
# n'agir que sur les `git commit` (évite les faux-positifs sur les
# autres Bash).
#
# Bloque le commit (exit 2) si violation détectée.

set -u

# Lire stdin
input="$(cat)"
if [ -z "$input" ]; then
    exit 0
fi

# Extraire le command pour pré-filtrer (best-effort comme em-dash)
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

# Grep tolérant sur le JSON brut (couvre les escapes JSON \n / \"
# présents dans les heredocs sérialisés). Le pattern matche :
#   Co-Authored-By: Claude / Co-authored-by: Claude / coauthoredby Claude
# avec n'importe quel séparateur non-alphabétique entre `by` et `claude`
# (espace, deux-points, retour ligne escapé, etc.).
if printf '%s\n' "$input" \
    | grep -qiE 'co-?authored-?by[^a-z]+claude'; then
    {
        printf '⛔ Trailer Co-Authored-By Claude détecté dans le message de commit.\n'
        printf '\n'
        printf 'Convention projet (CLAUDE.md règle ALWAYS-ON git) :\n'
        printf '  Pas de trailer "Co-Authored-By: Claude" dans aucun commit.\n'
        printf '\n'
        printf 'Pour corriger : retirer le trailer du message et relancer\n'
        printf 'le git commit. Le message s'\''arrête au corps utile.\n'
    } >&2
    exit 2
fi

exit 0
