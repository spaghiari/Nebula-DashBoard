#!/usr/bin/env bash
# PreToolUse hook (matcher Bash) : intercepte les `git commit` et valide
# le format des registres `.claude/improvements.md`, `.claude/backlog.md`,
# `.claude/ideas.md` et `.claude/digests/*.md` si ces fichiers sont
# staged.
#
# Vérifications :
#   - Statuts entre [ ] dans la whitelist : TODO, IN PROGRESS, BLOCKED,
#     DONE, ABANDONED, DONE YYYY-MM-DD, NEW, DEFERRED, REJECTED,
#     PROMOTED -> backlog, PROMOTED -> roadmap, PROMOTED -> improvements
#   - Priorités entre ( ) : P0, P1, P2
#   - Format de date : YYYY-MM-DD
#   - Champ `par <author>` présent sur tout item daté (mode équipe).
#     Désactivable en mode solo via .claude/settings.local.json ->
#     `validate_author: false` (parsing simple).
#
# Bloque le commit (exit 2) si format invalide détecté.
# Best-effort : silencieux si git/grep absents ou si les fichiers
# concernés ne sont pas staged.

set -u

# Lire stdin
input="$(cat)"
if [ -z "$input" ]; then
    exit 0
fi

# Extraire la commande Bash
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

# Liste des fichiers staged
staged="$(git diff --cached --name-only 2>/dev/null || true)"
if [ -z "$staged" ]; then
    exit 0
fi

# Cibles : improvements.md, backlog.md, ideas.md, digests/*.md
# (roadmap.md exclu - format libre vision/axes/jalons, pas de [STATUT]
# obligatoire sur chaque ligne)
targets=""
for f in ".claude/improvements.md" ".claude/backlog.md" ".claude/ideas.md"; do
    if printf '%s\n' "$staged" | grep -qxF "$f"; then
        targets="$targets $f"
    fi
done
# Digests staged (un fichier par semaine, on les valide tous)
digest_targets="$(printf '%s\n' "$staged" \
    | grep -E '^\.claude/digests/[^/]+\.md$' || true)"
if [ -n "$digest_targets" ]; then
    targets="$targets $digest_targets"
fi

if [ -z "$targets" ]; then
    # Aucune cible staged, rien à valider
    exit 0
fi

# Mode équipe / solo : lire .claude/settings.local.json (best-effort,
# grep simple, pas de jq nécessaire). Par défaut : mode équipe (auteur
# obligatoire).
validate_author="true"
if [ -r ".claude/settings.local.json" ]; then
    if grep -qE '"validate_author"[[:space:]]*:[[:space:]]*false' \
            ".claude/settings.local.json"; then
        validate_author="false"
    fi
fi

# Whitelist des statuts (regex ERE)
# Couvre les statuts cycle de vie, idea-funnel, et promoted
status_whitelist='\[TODO\]|\[IN PROGRESS\]|\[BLOCKED\]|\[DONE\]|\[ABANDONED\]|\[DONE [0-9]{4}-[0-9]{2}-[0-9]{2}\]|\[NEW\]|\[DEFERRED\]|\[REJECTED\]|\[PROMOTED -> (backlog|roadmap|improvements)\]'
priority_whitelist='\(P[0-2]'
date_pattern='[0-9]{4}-[0-9]{2}-[0-9]{2}'
author_pattern='par [a-zA-Z0-9._@-]+'

problems=""

for file in $targets; do
    if [ ! -r "$file" ]; then
        continue
    fi

    # Extraire toutes les lignes qui ont l'air d'être un item (commencent
    # par "- **[" ou "**["), en EXCLUANT le contenu des blocs fenced
    # ```. Les légendes des registres contiennent souvent des exemples
    # de format DANS des blocs ```markdown qui ne sont pas de vrais
    # items et ne doivent pas être validés.
    #
    # Approche : utiliser awk pour tracker l'état fence et numéroter
    # les lignes hors fence qui matchent le pattern item.
    item_lines="$(awk '
        /^```/ { in_fence = !in_fence; next }
        !in_fence && /^[[:space:]]*-[[:space:]]+\*\*\[/ {
            print NR ":" $0
        }
    ' "$file" || true)"

    if [ -z "$item_lines" ]; then
        continue
    fi

    # Pour chaque ligne d'item, valider statut + priorité + date + auteur
    while IFS= read -r line; do
        [ -z "$line" ] && continue
        lineno="$(printf '%s' "$line" | cut -d: -f1)"
        content="$(printf '%s' "$line" | cut -d: -f2-)"

        # Status présent et valide ?
        if ! printf '%s' "$content" \
            | grep -qE "(${status_whitelist})"; then
            problems="${problems}${file}:${lineno} : statut invalide ou manquant entre [ ]\n"
            problems="${problems}  Whitelist : TODO, IN PROGRESS, BLOCKED, DONE, ABANDONED, DONE YYYY-MM-DD,\n"
            problems="${problems}             NEW, DEFERRED, REJECTED, PROMOTED -> {backlog,roadmap,improvements}\n"
            problems="${problems}  Ligne : ${content}\n\n"
        fi

        # Si la ligne mentionne une priorité (P_), vérifier qu'elle est valide
        if printf '%s' "$content" | grep -qE '\(P[^,)]'; then
            if ! printf '%s' "$content" \
                | grep -qE "${priority_whitelist}"; then
                problems="${problems}${file}:${lineno} : priorité invalide (attendu : P0, P1 ou P2)\n"
                problems="${problems}  Ligne : ${content}\n\n"
            fi
        fi

        # Si la ligne mentionne "ajouté <date>" ou "proposée <date>",
        # valider le format de la date
        if printf '%s' "$content" | grep -qE '(ajouté|proposée) '; then
            if ! printf '%s' "$content" \
                | grep -qE "(ajouté|proposée) ${date_pattern}"; then
                problems="${problems}${file}:${lineno} : date invalide (attendu : YYYY-MM-DD)\n"
                problems="${problems}  Ligne : ${content}\n\n"
            fi

            # Si mode équipe : exiger le champ `par <author>` après la date
            if [ "$validate_author" = "true" ]; then
                if ! printf '%s' "$content" \
                    | grep -qE "${author_pattern}"; then
                    problems="${problems}${file}:${lineno} : champ \`par <author>\` manquant (mode équipe)\n"
                    problems="${problems}  Format attendu : (Pn, ajouté YYYY-MM-DD par <author>)\n"
                    problems="${problems}  Pour désactiver en mode solo : .claude/settings.local.json :\n"
                    problems="${problems}     { \"validate_author\": false }\n"
                    problems="${problems}  Ligne : ${content}\n\n"
                fi
            fi
        fi
    done <<EOF
${item_lines}
EOF
done

if [ -z "$problems" ]; then
    exit 0
fi

# Bloquer
{
    printf '⛔ Format invalide détecté dans les registres `.claude/`:\n\n'
    # shellcheck disable=SC2059
    printf "${problems}"
    printf 'Référence du format attendu :\n'
    printf '  - **[STATUT] <titre>** (Pn, ajouté YYYY-MM-DD par <author>)\n'
    printf '  - **[DONE YYYY-MM-DD] <titre>** (Pn, ajouté YYYY-MM-DD par <author>, livré par <author>)\n\n'
    printf 'Conventions : `.claude/memory/conventions/{backlog,self-improvement,digests}.md`\n'
} >&2

exit 2
