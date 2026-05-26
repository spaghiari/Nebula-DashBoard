#!/usr/bin/env bash
# Statusline : affiche dans la barre de statut Claude Code
#   <module>[bold/cyan] v<version>[magenta][next <jalon>][yellow] · <branch>[cyan][↑N ↓N][yellow] · <state>[green|yellow|red]
# où :
#   [next <jalon>]  apparaît si au moins un jalon du cycle de
#                   release est en attente. <jalon> ∈ {tag, push,
#                   prod, release} indique le PROCHAIN jalon à
#                   atteindre, en cascade (tag -> push -> prod ->
#                   release).
#                   - tag     : tag git annoté local pas encore
#                               créé (bump fait, tag à créer via
#                               /release-prep)
#                   - push    : tag local créé mais pas pushé sur
#                               origin (= pas encore visible côté
#                               GitLab UI)
#                   - prod    : tag pushé mais validation prod pas
#                               encore marquée
#                   - release : prod validée mais Release GitLab
#                               formelle pas encore publiée via API
#                   Source : .git/am-release-state.txt (lignes
#                   <tag>:<jalon>=<date>) avec <jalon> ∈ {prod,
#                   release}. Cf. /release-publish.
#                   Si tous les jalons sont atteints, segment OMIS
#                   (release close).
#   ↑N ↓N           commits ahead/behind vs upstream (silencieux si
#                   pas d'upstream ou si à jour)
#   state           clean (vert) | dirty (X code · Y doc) (rouge si
#                   code, orange si doc seul)
#                   où code = fichiers hors .claude/, hors *.md,
#                   hors module.info ; doc = le reste
#
# Couleurs ANSI (palette riche) :
#   - module        bold cyan
#   - version       magenta
#   - branche       cyan
#   - markers       yellow ([next ...], ↑↓)
#   - clean         green
#   - dirty (code)  red
#   - dirty (doc)   yellow
#
# Best-effort : si git absent, repo invalide, upstream absent ou
# aucun tag, fallback silencieux (pas d'erreur affichée).

set -u

# Codes ANSI (palette riche)
RST=$'\033[0m'
BOLD=$'\033[1m'
CYAN=$'\033[36m'
MAGENTA=$'\033[35m'
YELLOW=$'\033[33m'
GREEN=$'\033[32m'
RED=$'\033[31m'

# 1. Module name (statique)
module_name="{{label}}"

# 2. Version depuis module.info
version="?"
if [ -f module.info ]; then
    version="$(grep -E '^Version:' module.info 2>/dev/null \
        | head -n 1 \
        | sed -E 's/^Version:[[:space:]]*//')"
fi

# 3. État du cycle de release : déterminer le PROCHAIN jalon
#    manquant en cascade (tag -> push -> prod -> release).
#    Source : .git/am-release-state.txt (cf. /release-publish).
release_seg=""
if command -v git >/dev/null 2>&1 \
    && git rev-parse --git-dir >/dev/null 2>&1 \
    && [ "$version" != "?" ]; then
    tag_done=0
    push_done=0
    prod_done=0
    release_done=0

    # Tag : tag local existe pour la version courante ?
    last_tag="$(git tag --sort=-v:refname 2>/dev/null | head -n 1)"
    if [ -n "$last_tag" ] && [ "$last_tag" = "$version" ]; then
        tag_done=1
    fi

    # Push : tag présent sur origin ? (ne pas tester si le tag
    # local n'existe pas - sinon le `ls-remote` interroge inutilement
    # le serveur)
    if [ "$tag_done" -eq 1 ] \
        && git ls-remote --tags origin "refs/tags/${version}" \
            2>/dev/null | grep -q "refs/tags/${version}"; then
        push_done=1
    fi

    # Prod + Release : lecture du cache local
    cache_file=".git/am-release-state.txt"
    if [ -f "$cache_file" ]; then
        prod_line="$(grep "^${version}:prod=" \
            "$cache_file" 2>/dev/null | tail -n 1)"
        if [ -n "$prod_line" ] \
            && [ -n "${prod_line##*=}" ]; then
            prod_done=1
        fi

        release_line="$(grep "^${version}:release=" \
            "$cache_file" 2>/dev/null | tail -n 1)"
        if [ -n "$release_line" ] \
            && [ -n "${release_line##*=}" ]; then
            release_done=1
        fi
    fi

    # Cascade : afficher le PROCHAIN jalon manquant en priorité
    # (tag -> push -> prod -> release). Si tous atteints,
    # segment OMIS (release close).
    if [ "$tag_done" -eq 0 ]; then
        release_seg=" [next tag]"
    elif [ "$push_done" -eq 0 ]; then
        release_seg=" [next push]"
    elif [ "$prod_done" -eq 0 ]; then
        release_seg=" [next prod]"
    elif [ "$release_done" -eq 0 ]; then
        release_seg=" [next release]"
    fi
fi

# 4. Branch + ahead/behind + dirty décomposé
branch="?"
diverge=""
state="?"
if command -v git >/dev/null 2>&1 && git rev-parse --git-dir >/dev/null 2>&1; then
    branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"

    # Ahead/behind vs upstream (silencieux si pas d'upstream)
    counts="$(git rev-list --left-right --count HEAD...@{u} 2>/dev/null \
        || true)"
    if [ -n "$counts" ]; then
        ahead="$(printf '%s\n' "$counts" | awk '{print $1+0}')"
        behind="$(printf '%s\n' "$counts" | awk '{print $2+0}')"
        if [ "$ahead" -gt 0 ] && [ "$behind" -gt 0 ]; then
            diverge=" ↓${behind} ↑${ahead}"
        elif [ "$ahead" -gt 0 ]; then
            diverge=" ↑${ahead}"
        elif [ "$behind" -gt 0 ]; then
            diverge=" ↓${behind}"
        fi
    fi

    # Dirty décomposé code vs doc
    porcelain="$(git status --porcelain 2>/dev/null || true)"
    if [ -z "$porcelain" ]; then
        state="clean"
    else
        # Ventilation par catégorie via awk
        # code = hors .claude/, hors *.md, hors module.info
        # doc  = le reste (.claude/**, *.md, module.info)
        counts_state="$(printf '%s\n' "$porcelain" | awk '
            {
                file = $2
                if (file ~ /^\.claude\// \
                    || file ~ /\.md$/ \
                    || file == "module.info") {
                    doc++
                } else {
                    code++
                }
            }
            END { printf "%d %d", code+0, doc+0 }
        ')"
        code="$(printf '%s' "$counts_state" | awk '{print $1}')"
        doc="$(printf '%s' "$counts_state" | awk '{print $2}')"
        if [ "$code" -gt 0 ] && [ "$doc" -gt 0 ]; then
            state="dirty (${code} code · ${doc} doc)"
        elif [ "$code" -gt 0 ]; then
            state="dirty (${code} code)"
        else
            state="dirty (${doc} doc)"
        fi
    fi
fi

# 5. Colorisation des segments (palette riche)
module_disp="${BOLD}${CYAN}${module_name}${RST}"
version_disp="${MAGENTA}v${version}${RST}"
branch_disp="${CYAN}${branch}${RST}"

marker_disp=""
if [ -n "$release_seg" ]; then
    marker_disp="${YELLOW}${release_seg}${RST}"
fi

diverge_disp=""
if [ -n "$diverge" ]; then
    diverge_disp="${YELLOW}${diverge}${RST}"
fi

# state coloré selon le contenu : clean -> vert ; dirty avec code
# -> rouge (régression potentielle module produit) ; dirty avec doc
# seul -> orange (changement non critique).
case "$state" in
    clean)
        state_disp="${GREEN}${state}${RST}"
        ;;
    *code*)
        state_disp="${RED}${state}${RST}"
        ;;
    *)
        state_disp="${YELLOW}${state}${RST}"
        ;;
esac

# 6. Output
printf '%s %s%s · %s%s · %s' \
    "$module_disp" "$version_disp" "$marker_disp" \
    "$branch_disp" "$diverge_disp" "$state_disp"
