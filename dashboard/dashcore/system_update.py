"""Auto-update via git.

Le dashboard suppose que l'installation est un clone git (le repo public).
On utilise git pour :
- détecter le nombre de commits en retard sur la branche tracking ;
- lister les changements à venir ;
- appliquer la mise à jour via git pull.

Tous les appels git ont un timeout court et n'exécutent que des commandes
hardcodées (pas d'injection possible via les paramètres utilisateur).
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from dashcore.config import ROOT, log


GIT_TIMEOUT_FETCH = 20
GIT_TIMEOUT_QUICK = 5
GIT_TIMEOUT_PULL = 60

# Fichiers connus comme contenant des données utilisateur — leurs modifications
# locales ne doivent PAS bloquer un git pull (le pull n'écrasera pas ces
# fichiers tant que les commits distants n'y touchent pas).
USER_DATA_FILES = frozenset({
    "mcp/registry.json",
    "mcp/registry.json.bak",
    "dashboard/data/workspaces.json",
    "dashboard/data/ui_state.json",
    "memory/journal.md",
    # Fichiers de config locale non committés (ne bloquent pas git pull)
    ".gitlab-ci.yml",
    ".gitignore",
})


def _filter_user_data(status_lines: list[str]) -> list[str]:
    """Retire les lignes `git status --porcelain` qui concernent des données utilisateur.

    Robuste à toutes les variations de format git status (porcelain v1 avec 2
    chars status, version courte avec 1 char, lignes avec ou sans espace de
    tête). On extrait simplement tout ce qui ressemble à un chemin et on
    matche par substring contre USER_DATA_FILES.
    """
    out = []
    for line in status_lines:
        if not line.strip():
            continue
        # Untracked (`??`) ne bloque jamais `git pull --ff-only` tant qu'aucun
        # commit distant n'introduit un fichier au même chemin. Si conflit réel,
        # git pull échouera explicitement et on remontera son erreur. Pas de
        # raison de bloquer en amont sur les fichiers locaux du client.
        if line.startswith("??"):
            continue
        # Normalise les backslashes Windows en forward slashes
        normalized = line.replace("\\", "/")
        # Match par substring : si un fichier utilisateur apparait dans la
        # ligne, on filtre. Plus permissif mais robuste à tous les formats.
        if any(f in normalized for f in USER_DATA_FILES):
            continue
        out.append(line)
    return out


def _git(*args: str, timeout: int = GIT_TIMEOUT_QUICK) -> tuple[int, str, str]:
    """Lance une commande git dans ROOT et retourne (returncode, stdout, stderr)."""
    git_cli = shutil.which("git") or "git"
    try:
        r = subprocess.run(
            [git_cli, *args],
            cwd=str(ROOT),
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=timeout,
        )
        return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()
    except FileNotFoundError:
        return -1, "", "git introuvable dans le PATH"
    except subprocess.TimeoutExpired:
        return -1, "", f"git timeout ({timeout}s)"
    except OSError as e:
        return -1, "", f"erreur : {e}"


def _is_git_repo() -> bool:
    return (ROOT / ".git").exists()


def _current_branch() -> str:
    rc, out, _ = _git("rev-parse", "--abbrev-ref", "HEAD")
    return out if rc == 0 else ""


def _tracking_branch() -> str:
    """Renvoie la branche distante trackée (ex. 'origin/main') ou ''."""
    rc, out, _ = _git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    return out if rc == 0 else ""


def system_version_info(check_remote: bool = False) -> dict:
    """Infos détaillées sur la version locale et l'état de mise à jour.

    Si `check_remote` est True, lance `git fetch` (lent, à éviter au load).
    """
    if not _is_git_repo():
        return {
            "available": False,
            "reason": "Pas un dépôt git — auto-update indisponible.",
            "is_git": False,
        }

    branch = _current_branch()
    upstream = _tracking_branch()

    rc, head_sha, _ = _git("rev-parse", "--short", "HEAD")
    rc2, last_msg, _ = _git("log", "-1", "--pretty=%s")

    # Détecte les changements locaux non committés (porcelain est silencieux si propre)
    # Les fichiers de données utilisateur (registry.json, workspaces.json...) sont
    # filtrés — leurs modifications sont attendues et ne bloquent pas l'update.
    rc3, status, _ = _git("status", "--porcelain")
    raw_lines = status.splitlines() if status.strip() else []
    significant_lines = _filter_user_data(raw_lines)
    dirty = bool(significant_lines)

    info = {
        "available": True,
        "is_git": True,
        "branch": branch,
        "upstream": upstream,
        "head": head_sha if rc == 0 else "?",
        "head_message": last_msg if rc2 == 0 else "",
        "dirty": dirty,
        "dirty_files": significant_lines[:10] if dirty else [],
        "behind": 0,
        "commits": [],
        "fetched": False,
    }

    if not upstream:
        info["reason"] = "Aucune branche distante trackée."
        return info

    if check_remote:
        rcf, _, errf = _git("fetch", "--quiet", timeout=GIT_TIMEOUT_FETCH)
        if rcf != 0:
            info["fetch_error"] = errf or "git fetch a échoué"
            return info
        info["fetched"] = True

    # Compte les commits en retard
    rc4, behind_str, _ = _git("rev-list", "--count", f"HEAD..{upstream}")
    if rc4 == 0 and behind_str.isdigit():
        info["behind"] = int(behind_str)

    # Liste des commits à venir (max 30, format compact)
    if info["behind"] > 0:
        rc5, log_out, _ = _git(
            "log", f"HEAD..{upstream}",
            "--pretty=%h\x1f%s\x1f%an\x1f%ar",
            "--max-count=30",
        )
        if rc5 == 0:
            info["commits"] = [
                {
                    "sha": parts[0],
                    "subject": parts[1],
                    "author": parts[2] if len(parts) > 2 else "",
                    "relative": parts[3] if len(parts) > 3 else "",
                }
                for line in log_out.splitlines()
                for parts in [line.split("\x1f")]
                if len(parts) >= 2
            ]

    return info


def system_apply_update() -> tuple[int, dict]:
    """Applique la mise à jour via git pull.

    Détecte si des fichiers Python ont changé pour signaler qu'un redémarrage
    du serveur est nécessaire. Les fichiers JS/CSS/HTML sont rechargés au F5.
    """
    if not _is_git_repo():
        return 400, {"ok": False, "error": "Pas un dépôt git"}

    upstream = _tracking_branch()
    if not upstream:
        return 400, {"ok": False, "error": "Aucune branche distante trackée"}

    # Refus si modifications locales non committées qui ne sont PAS des fichiers
    # de données utilisateur. Les data files (registry, workspaces.json...) sont
    # filtrés car leurs changements sont normaux et ne risquent rien lors d'un
    # git pull --ff-only tant que les commits distants n'y touchent pas.
    rc_st, status, _ = _git("status", "--porcelain")
    if rc_st == 0 and status.strip():
        significant = _filter_user_data(status.splitlines())
        if significant:
            return 409, {
                "ok": False,
                "error": "Modifications locales non committées détectées. Commit ou stash avant l'update.",
                "dirty_files": significant[:10],
            }

    # Snapshot du HEAD avant pull pour détecter les fichiers changés
    rc_b, head_before, _ = _git("rev-parse", "HEAD")

    # Pull
    rc_p, pull_out, pull_err = _git("pull", "--ff-only", timeout=GIT_TIMEOUT_PULL)
    if rc_p != 0:
        return 500, {
            "ok": False,
            "error": "git pull a échoué",
            "stderr": pull_err,
            "stdout": pull_out,
        }

    rc_a, head_after, _ = _git("rev-parse", "HEAD")
    if head_before == head_after:
        return 200, {"ok": True, "applied": False, "message": "Déjà à jour."}

    # Liste des fichiers changés
    rc_d, diff_out, _ = _git("diff", "--name-only", head_before, head_after)
    changed_files = diff_out.splitlines() if rc_d == 0 else []

    # Détection : faut-il redémarrer le serveur Python ?
    # Si un .py change, oui. Sinon (HTML/CSS/JS uniquement) un F5 suffit.
    needs_restart = any(f.endswith(".py") for f in changed_files)

    log.info(
        "system update applied: %s → %s (%d fichiers, restart=%s)",
        head_before[:7], head_after[:7], len(changed_files), needs_restart,
    )

    return 200, {
        "ok": True,
        "applied": True,
        "from": head_before[:7],
        "to": head_after[:7],
        "files_changed": changed_files,
        "needs_restart": needs_restart,
        "message": (
            "Mise à jour appliquée. Redémarre le dashboard pour activer les changements."
            if needs_restart
            else "Mise à jour appliquée. Recharge la page (F5) pour voir les changements."
        ),
    }
