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

import re
import shutil
import subprocess
import threading
import time

from dashcore.config import LEGACY_ORIGIN_URL, ORIGIN_URL, ROOT, log


GIT_TIMEOUT_FETCH = 20
GIT_TIMEOUT_QUICK = 5
GIT_TIMEOUT_PULL = 60

# Âge minimum (secondes) avant de considérer un .git/index.lock comme
# orphelin. 5 min : un repack/gc ou un fetch lent peut légitimement tenir
# le lock bien au-delà d'une minute.
STALE_LOCK_AGE = 300

# Sérialise TOUTES les opérations git mutantes du dashboard. Le serveur est
# un ThreadingHTTPServer : deux requêtes concurrentes (double-clic « Mettre à
# jour », retry navigateur) pourraient sinon lancer stash/pull/reset en
# parallèle et corrompre l'index. RLock (et non Lock) pour tolérer des appels
# imbriqués entre ces fonctions sans deadlock.
_GIT_LOCK = threading.RLock()

# Fichiers connus comme contenant des données utilisateur — leurs modifications
# locales ne doivent PAS bloquer un git pull (le pull n'écrasera pas ces
# fichiers tant que les commits distants n'y touchent pas).
USER_DATA_FILES = frozenset({
    "mcp/registry.json",
    "mcp/registry.json.bak",
    "dashboard/data/workspaces.json",
    "dashboard/data/ui_state.json",
    "dashboard/data/mcp_sync_state.json",
    "dashboard/data/mcp_sync_state.json.bak",
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


def _porcelain_v2_path(line: str) -> str:
    """Chemin d'une ligne `git status --porcelain=v2` (chemin de destination
    pour un renommage). Le v2 ne commence jamais par un espace : le strip()
    de `_git()` ne tronque donc pas la 1re ligne, contrairement au v1 (" M x").
    """
    # Nombre de champs avant le chemin, selon le type d'entree.
    fields = {"1": 8, "2": 9, "u": 10, "?": 1, "!": 1}.get(line[:1])
    if fields is None:
        return ""
    parts = line.split(" ", fields)
    path = parts[fields] if len(parts) > fields else ""
    # Renommage/copie (type 2) : "<dest><TAB><origine>".
    return path.split("\t", 1)[0].strip('"')


def _is_git_repo() -> bool:
    return (ROOT / ".git").exists()


# « hôte/chemin » d'une URL git, sans schéma, identifiants, port, `.git` ni
# barres finales : https://u:t@h/a/b.git, ssh://git@h:22/a/b, git@h:a/b -> h/a/b.
_SCP_LIKE_RE = re.compile(r"^(?:[^@/]+@)?([^:/]+):(?!//)(.+)$")


def _normalize_git_url(url: str) -> str:
    u = (url or "").strip()
    m = re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://(.*)$", u)
    if m:
        rest = m.group(1)
        host, _, path = rest.partition("/")
        host = host.rsplit("@", 1)[-1].split(":", 1)[0]
    else:
        m = _SCP_LIKE_RE.match(u)
        if not m:
            return ""
        host, path = m.group(1), m.group(2)
    path = path.strip("/")
    if path.lower().endswith(".git"):
        path = path[:-4]
    path = path.strip("/")
    if not host or not path:
        return ""
    return f"{host}/{path}".lower()


def _migrate_origin_remote() -> bool:
    """Réoriente `origin` de l'ancien GitLab vers Forgejo (cf. config.py).

    À appeler avant tout fetch/pull. Idempotent : sans effet si `origin`
    pointe déjà ailleurs (nouveau dépôt, fork, miroir) ou n'existe pas.
    Retourne True si l'URL a été changée.
    """
    with _GIT_LOCK:
        rc, url, _ = _git("remote", "get-url", "origin")
        if rc != 0 or not url:
            return False
        legacy = _normalize_git_url(LEGACY_ORIGIN_URL)
        if not legacy or _normalize_git_url(url) != legacy:
            return False
        # Cible injoignable (poste hors du LAN, Forgejo arrêté) : on garde
        # l'ancien origin plutôt que de basculer vers un dépôt mort.
        rc_l, _, err_l = _git("ls-remote", "--heads", ORIGIN_URL, timeout=GIT_TIMEOUT_FETCH)
        if rc_l != 0:
            log.info("Bascule du remote origin différée, %s injoignable : %s", ORIGIN_URL, err_l)
            return False
        rc_s, _, err = _git("remote", "set-url", "origin", ORIGIN_URL)
        if rc_s != 0:
            log.warning("Bascule du remote origin vers %s échouée : %s", ORIGIN_URL, err)
            return False
        log.info("Remote origin basculé de l'ancien dépôt GitLab vers %s", ORIGIN_URL)
        return True


def _new_stash_label(prefix: str) -> str:
    """Label unique (ms) : deux opérations dans la même seconde ne collisionnent pas."""
    return f"{prefix}-{time.time_ns() // 1_000_000}"


def _find_stash_ref_by_label(label: str) -> str | None:
    """Ref `stash@{N}` du stash dont le message est EXACTEMENT `label`.

    Les `stash@{N}` se décalent à chaque push/drop : on ne mémorise jamais
    un index, on re-résout par le message juste avant chaque pop/apply.
    Sujet git : « On <branche>: <label> » (ou « <label> » selon la version).
    """
    rc, out, _ = _git("stash", "list", "--format=%gd%x1f%gs")
    if rc != 0:
        return None
    for line in out.splitlines():
        ref, _, subject = line.partition("\x1f")
        if subject.strip().rsplit(": ", 1)[-1] == label:
            return ref.strip()
    return None


def _stash_push_verified(label: str, *, include_untracked: bool,
                         exclude: tuple[str, ...] = ()) -> tuple[bool, str]:
    """`git stash push -m <label>` puis VÉRIFIE que le stash existe par son message.

    `git stash push` renvoie 0 même quand il n'a rien stashé (« No local
    changes to save ») : sans vérification, un `stash pop` ultérieur
    dépilerait le stash d'un AUTRE (stash utilisateur antérieur).
    Retourne (créé, message d'erreur éventuel).
    """
    args = ["stash", "push"]
    if include_untracked:
        args.append("--include-untracked")
    args += ["-m", label]
    if exclude:
        args += ["--", "."] + [f":(exclude){p}" for p in exclude]
    rc, out, err = _git(*args, timeout=GIT_TIMEOUT_QUICK)
    if rc != 0:
        return False, err or out or "git stash push a échoué"
    if _find_stash_ref_by_label(label) is None:
        return False, out or "aucun stash créé (rien à sauvegarder)"
    return True, ""


def _status_paths() -> dict[str, str] | None:
    """{chemin: code} du working tree via `git status --porcelain=v2`.

    v2 et non v1 : `_git` fait un strip() de stdout, ce qui mange l'espace de
    tête du code v1 « ␣M chemin » sur la 1re ligne et décale le chemin.
    En v2 chaque ligne commence par un type (1/2/u/?) : aucun risque.
    None si git échoue.
    """
    rc, out, _ = _git("status", "--porcelain=v2")
    if rc != 0:
        return None
    paths: dict[str, str] = {}
    for line in out.splitlines():
        if line.startswith("? "):
            paths[line[2:].strip('"')] = "??"
        elif line.startswith("1 "):
            parts = line.split(" ", 8)
            if len(parts) == 9:
                paths[parts[8].strip('"')] = parts[1]
        elif line.startswith("2 "):
            parts = line.split(" ", 9)
            if len(parts) == 10:
                paths[parts[9].split("\t", 1)[0].strip('"')] = parts[1]
        elif line.startswith("u "):
            parts = line.split(" ", 10)
            if len(parts) == 11:
                paths[parts[10].strip('"')] = parts[1]
    return paths


def _undo_partial_apply(pre: dict[str, str]) -> tuple[list[str], list[str]]:
    """Annule un `git stash apply` échoué SANS toucher aux modifs préexistantes.

    Seuls les fichiers trackés absents de `pre` (donc propres avant l'apply)
    sont restaurés depuis HEAD (index + working tree). Les fichiers non suivis
    créés par l'apply ne sont PAS supprimés (ils sont aussi dans le stash) :
    on les liste pour l'utilisateur. Retourne (restaurés, non_suivis_laissés).
    """
    post = _status_paths() or {}
    reverted: list[str] = []
    leftovers: list[str] = []
    for path, code in post.items():
        if path in pre:
            continue
        if code == "??":
            leftovers.append(path)
            continue
        # Conflit (U/AA/DD) ou modif : sortir de l'index puis restaurer depuis HEAD.
        _git("reset", "-q", "--", path)
        rc_c, _, _ = _git("checkout", "HEAD", "--", path)
        if rc_c == 0:
            reverted.append(path)
    if reverted or leftovers:
        log.warning("Apply de stash annulé : %d restauré(s), %d non suivi(s) laissé(s)",
                    len(reverted), len(leftovers))
    return reverted, leftovers


def _snapshot_user_data() -> dict[str, bytes]:
    """Copie mémoire des USER_DATA_FILES présents (restaurés après un reset --hard)."""
    snap: dict[str, bytes] = {}
    for rel in USER_DATA_FILES:
        p = ROOT / rel
        try:
            if p.is_file():
                snap[rel] = p.read_bytes()
        except OSError:
            pass
    return snap


def _restore_user_data(snap: dict[str, bytes]) -> list[str]:
    """Réécrit les USER_DATA_FILES dont le contenu a changé. Retourne la liste restaurée."""
    restored = []
    for rel, data in snap.items():
        p = ROOT / rel
        try:
            if not p.is_file() or p.read_bytes() != data:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(data)
                restored.append(rel)
        except OSError as e:
            log.error("Restauration user-data %s impossible : %s", rel, e)
    return restored


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
    from dashcore import __version__ as _pkg_version
    if not _is_git_repo():
        return {
            "available": False,
            "reason": "Pas un dépôt git — auto-update indisponible.",
            "is_git": False,
            "version": _pkg_version,
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
        "version": _pkg_version,
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
        _migrate_origin_remote()
        rcf, _, errf = _git("fetch", "--quiet", timeout=GIT_TIMEOUT_FETCH)
        if rcf != 0:
            info["fetch_error"] = errf or "git fetch a échoué"
            return info
        info["fetched"] = True

    # Compte les commits en retard ET en avance pour détecter une divergence.
    # Cas courant qui matérialise une divergence ici : workflow dev→export
    # où le dev a ses propres commits granulaires et le remote contient
    # leurs équivalents bundlés. Même contenu, graphes différents → ni
    # fast-forward dans un sens, ni dans l'autre.
    rc4, behind_str, _ = _git("rev-list", "--count", f"HEAD..{upstream}")
    if rc4 == 0 and behind_str.isdigit():
        info["behind"] = int(behind_str)
    rc4b, ahead_str, _ = _git("rev-list", "--count", f"{upstream}..HEAD")
    info["ahead"] = int(ahead_str) if (rc4b == 0 and ahead_str.isdigit()) else 0
    info["diverged"] = info["behind"] > 0 and info["ahead"] > 0

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


def _git_process_running() -> bool | None:
    """Best-effort : détecte un process git.exe vivant (Windows, stdlib only).

    Utilise `tasklist` (shell=False, arguments hardcodés). Retourne True si au
    moins un git.exe tourne, False si aucun, None si la vérification elle-même
    a échoué (tasklist indisponible, timeout…) — l'appelant retombe alors sur
    le seul critère d'âge.
    """
    try:
        r = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq git.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=GIT_TIMEOUT_QUICK,
        )
        if r.returncode != 0:
            return None
        # Sans correspondance, tasklist affiche un message informatif
        # (« INFO: ... ») au lieu d'une ligne CSV — on cherche simplement
        # le nom d'image dans la sortie.
        return "git.exe" in (r.stdout or "").lower()
    except (OSError, subprocess.TimeoutExpired):
        return None


def _check_stale_lock() -> tuple[bool, str]:
    """Détecte un .git/index.lock orphelin (process git crashé). Retourne (removed, message)."""
    lock = ROOT / ".git" / "index.lock"
    if not lock.exists():
        return False, ""
    try:
        age = time.time() - lock.stat().st_mtime
    except OSError:
        return False, ""
    if age <= STALE_LOCK_AGE:
        return False, f"Lock actif (âge: {int(age)}s) — un autre git tourne ?"
    # Vieux lock : avant de le retirer, vérifie qu'aucun process git n'est
    # vivant. Un repack/gc lent ou un git manuel dans un autre terminal peut
    # détenir le lock légitimement bien au-delà du seuil — le supprimer
    # tuerait son travail en cours.
    running = _git_process_running()
    if running:
        return False, (f"Un git est en cours d'exécution (lock âgé de {int(age)}s) "
                       "— on ne retire pas le lock.")
    if running is None:
        log.warning("Vérification des process git impossible (tasklist) — "
                    "repli sur le seul critère d'âge du lock.")
    try:
        lock.unlink()
        log.warning("Removed stale .git/index.lock (%ds old)", int(age))
        return True, f"Lock orphelin retiré (âge: {int(age)}s)"
    except OSError as e:
        return False, f"Lock orphelin détecté mais retrait échoué: {e}"


def _diagnose_pull_failure(pull_err: str, pull_out: str) -> str | None:
    """Retourne un hint humain selon l'erreur git observée."""
    blob = (pull_err + " " + pull_out).lower()
    if "non-fast-forward" in blob or "diverged" in blob or "rejected" in blob:
        return ("Ton dépôt local a des commits que le distant n'a pas (branche divergée). "
                "Utilise « Réinitialiser à la version distante » pour forcer l'alignement "
                "(tes modifs seront sauvées dans `git stash list`).")
    if "could not resolve host" in blob or "failed to connect" in blob or "could not read from remote" in blob:
        return "Connexion au serveur git impossible. Vérifie ta connexion internet."
    if "authentication failed" in blob or "permission denied" in blob or "could not read username" in blob:
        return "Authentification git échouée. Vérifie tes identifiants ou ta clé SSH."
    if "fatal: refusing to merge unrelated histories" in blob:
        return "Histoires git non-liées. Cas rare — utilise « Réinitialiser à la version distante »."
    if "no space left" in blob:
        return "Disque plein."
    return None


def system_apply_update() -> tuple[int, dict]:
    """Applique la mise à jour via git pull. JAMAIS bloquant pour des modifs locales.

    Stratégie défense en profondeur :
    1. Pré-check : retire un index.lock orphelin (vieux ET sans git vivant)
    2. Si dirty (status non vide), pré-stash systématique (--include-untracked)
       avec timestamp pour ne pas collisionner avec les autres autostash
    3. Pull --ff-only (peut maintenant pas planter sur dirty)
    4. Si on a stashé : pop pour restaurer. Si pop conflit → modifs préservées
       dans la pile, warning explicite, l'utilisateur peut récupérer via CLI
    5. Si pull échoue malgré ça : on hint sur le mode de panne (réseau,
       diverged, auth…) et on suggère le reset hard si pertinent
    6. Aucune perte de données possible : le stash reste tant qu'il n'est
       pas explicitement drop

    Sérialisé par _GIT_LOCK : une seule opération git mutante à la fois
    (le serveur HTTP est multithread).
    """
    with _GIT_LOCK:
        if not _is_git_repo():
            return 400, {"ok": False, "error": "Pas un dépôt git"}

        upstream = _tracking_branch()
        if not upstream:
            return 400, {"ok": False, "error": "Aucune branche distante trackée"}

        # 1. Lock orphelin
        lock_removed, lock_msg = _check_stale_lock()
        if lock_msg and not lock_removed:
            # Lock actif récent : on ne touche pas, on rapporte
            return 423, {"ok": False, "error": lock_msg, "hint": "Réessaye dans quelques secondes."}

        # 2. Snapshot HEAD + pré-stash systématique si dirty
        rc_b, head_before, _ = _git("rev-parse", "HEAD")
        rc_st, status, _ = _git("status", "--porcelain=v2")
        has_local_changes = bool(status.strip())

        stash_applied = False
        stash_pop_warning = None
        stash_label = _new_stash_label("nebula-autostash")

        # Avant de stasher, on détecte les fichiers de données utilisateur connus
        # (.env.local, registry.json, workspaces.json…) qui pourraient se retrouver
        # dans le stash si l'utilisateur n'a pas configuré skip-worktree.
        sensitive_in_stash: list[str] = []
        if has_local_changes:
            sensitive_patterns = (".env.local", "mcp/registry.json",
                                  "dashboard/data/workspaces.json")
            for line in status.splitlines():
                path = _porcelain_v2_path(line)
                if any(p in path for p in sensitive_patterns):
                    sensitive_in_stash.append(path)

            # Stash NOMMÉ et VÉRIFIÉ par son message (cf. _stash_push_verified).
            stash_applied, stash_err = _stash_push_verified(stash_label, include_untracked=True)
            if stash_applied:
                log.info("Pre-pull stash effectué (%d entrées status, label=%s)",
                         len(status.splitlines()), stash_label)
                if sensitive_in_stash:
                    log.warning("Stash contient des fichiers sensibles : %s — label %s",
                                sensitive_in_stash, stash_label)
            else:
                # Pas de stash : on continue, `pull --ff-only` refuse de lui-même
                # d'écraser des modifs locales (aucune perte possible).
                log.warning("git stash non effectué (continuons quand même) : %s", stash_err)

        # 3. Pull --ff-only sur état propre (ou presque). 4. Restauration
        #    GARANTIE (finally) : même si le pull échoue ou lève, on dépile
        #    NOTRE stash, retrouvé par son label (jamais `stash@{0}` à l'aveugle).
        rc_p, pull_out, pull_err = -1, "", "pull non exécuté"
        try:
            _migrate_origin_remote()
            rc_p, pull_out, pull_err = _git("pull", "--ff-only", timeout=GIT_TIMEOUT_PULL)
        finally:
            if stash_applied:
                ref = _find_stash_ref_by_label(stash_label)
                if ref is None:
                    stash_pop_warning = (
                        f"Stash « {stash_label} » introuvable au moment de la restauration : "
                        "vérifie `git stash list` (aucun autre stash n'a été dépilé)."
                    )
                    log.error("Stash %s introuvable avant pop", stash_label)
                else:
                    rc_pop, _pop_out, pop_err = _git("stash", "pop", ref, timeout=GIT_TIMEOUT_QUICK)
                    if rc_pop != 0:
                        stash_pop_warning = (
                            f"Conflit lors de la restauration de tes modifs (`git stash pop`). "
                            f"Elles sont SAUVES dans la pile (`git stash list` → label '{stash_label}'). "
                            f"Pour les récupérer : `git stash pop` manuel quand tu auras résolu le conflit. "
                            f"Détail: {pop_err[:300]}"
                        )
                        log.warning("git stash pop a échoué (label=%s) : %s", stash_label, pop_err)

        # 5. Pull a échoué : on diagnostique et on rapporte
        if rc_p != 0:
            hint = _diagnose_pull_failure(pull_err, pull_out)
            # 200 (et non 500) volontaire : echec recuperable rapporte EN BANDE
            # (ok:false) pour que le front rende le panneau riche (hint, recup du
            # stash, reset). API.post throw sur HTTP non-ok, ce qui court-circuiterait
            # ce panneau (cf. lot D, audit-ux-2026-05-25).
            return 200, {
                "ok": False,
                "error": "git pull a échoué",
                "stderr": pull_err,
                "stdout": pull_out,
                "hint": hint,
                "stash_applied": stash_applied,
                "stash_pop_warning": stash_pop_warning,
                "can_reset_to_upstream": True,
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

        # Rétention auto : purge les vieux stash nebula-* après un cycle réussi.
        # Garde-fou : on ne purge QUE si le pop a réussi (pas de conflit en
        # suspens). Un `stash_pop_warning` signifie qu'un stash est laissé
        # volontairement dans la pile pour récupération -- on n'y touche pas.
        pruned = None
        if not stash_pop_warning:
            pruned = _prune_nebula_stashes()

        return 200, {
            "ok": True,
            "applied": True,
            "from": head_before[:7],
            "to": head_after[:7],
            "files_changed": changed_files,
            "needs_restart": needs_restart,
            "stash_applied": stash_applied,
            "stash_pop_warning": stash_pop_warning,
            "stashes_pruned": pruned["dropped"] if pruned else [],
            "sensitive_in_stash": sensitive_in_stash if stash_applied else [],
            "message": (
                "Mise à jour appliquée. Redémarre le dashboard pour activer les changements."
                if needs_restart
                else "Mise à jour appliquée. Recharge la page (F5) pour voir les changements."
            ),
        }


def _stash_file_count(ref: str) -> int:
    """Nombre de fichiers trackés capturés par un stash (`git stash show`).

    `git stash show --name-only <ref>` liste un fichier par ligne. Un stash
    `nebula-pre-reset-*` créé sur un working tree sans modif trackée (cas le
    plus fréquent : seuls des untracked / user-data) ressort à 0 fichier --
    donc aucune valeur de récupération.

    Best-effort : en cas d'échec git (ref volatile, erreur), on renvoie -1
    (« inconnu ») pour ne JAMAIS classer à tort un stash comme vide.
    """
    rc, out, _ = _git("stash", "show", "--name-only", ref, timeout=GIT_TIMEOUT_QUICK)
    if rc != 0:
        return -1
    return len([ln for ln in out.splitlines() if ln.strip()])


def _list_nebula_stashes() -> list[dict]:
    """Liste les entrées de stash créées par l'auto-update Nebula.

    Repère les labels `nebula-autostash-*` / `nebula-pre-reset-*` posés par
    `system_apply_update` / `system_reset_to_upstream`. Retourne une liste
    ordonnée (le plus récent en premier, comme `git stash list`) de dicts
    `{ref, label, subject, kind, file_count, empty}` où `ref` est la
    référence stable (`stash@{N}`).

    `kind` vaut `"autostash"` ou `"pre-reset"`. `file_count` est le nombre de
    fichiers trackés capturés (-1 = inconnu). `empty` est True uniquement
    pour un `pre-reset` à 0 fichier tracké (candidat à purge sans condition).
    """
    rc, out, _ = _git("stash", "list", "--format=%gd%x1f%gs")
    if rc != 0 or not out.strip():
        return []
    stashes = []
    for line in out.splitlines():
        parts = line.split("\x1f", 1)
        if len(parts) != 2:
            continue
        ref, subject = parts[0].strip(), parts[1].strip()
        is_autostash = "nebula-autostash-" in subject
        is_pre_reset = "nebula-pre-reset-" in subject
        if is_autostash or is_pre_reset:
            # Extrait le label nebula-* lisible pour l'UI.
            label = ""
            for token in subject.replace(":", " ").split():
                if token.startswith("nebula-"):
                    label = token
                    break
            file_count = _stash_file_count(ref)
            kind = "pre-reset" if is_pre_reset else "autostash"
            stashes.append({
                "ref": ref,
                "label": label or subject,
                "subject": subject,
                "kind": kind,
                "file_count": file_count,
                # Un pre-reset à 0 fichier tracké n'a aucune valeur : purge
                # systématique. On exige file_count == 0 (pas -1 « inconnu »).
                "empty": kind == "pre-reset" and file_count == 0,
            })
    return stashes


def _drop_stash_ref(ref: str, nebula: list[dict] | None = None) -> tuple[bool, str]:
    """Drop sécurisé d'UN stash, garde de sécurité partagée.

    INVARIANT DUR : on ne droppe QUE des stash créés par l'auto-update Nebula
    (labels nebula-autostash-* / nebula-pre-reset-*), JAMAIS un stash
    utilisateur arbitraire. La ref est revalidée contre la liste courante des
    stash nebula (passée en `nebula` pour éviter un re-scan, ou recalculée).

    Retourne `(dropped, message)`. Cette garde est la SEULE source de vérité
    pour `system_drop_stash` (drop unitaire UI) et `_prune_nebula_stashes`
    (rétention auto) -- ne jamais la dupliquer ailleurs.
    """
    ref = (ref or "").strip()
    if not ref:
        return False, "Référence de stash manquante."
    if nebula is None:
        nebula = _list_nebula_stashes()
    match = next((s for s in nebula if s["ref"] == ref), None)
    if not match:
        return False, "Stash introuvable ou non géré par Nebula."
    rc, _out, err = _git("stash", "drop", ref, timeout=GIT_TIMEOUT_QUICK)
    if rc != 0:
        return False, f"Échec du drop ({(err or '')[:200]})."
    log.info("Stash nebula supprimé : %s (%s)", ref, match["label"])
    return True, f"Stash « {match['label']} » supprimé."


def _prune_nebula_stashes(keep: int = 3) -> dict:
    """Applique la politique de rétention sur les stash nebula-* (best-effort).

    Politique :
    - GARDE-FOU BACKLOG : si la pile contient PLUS D'UN stash nebula non vide,
      c'est le signe d'un backlog non résolu (un `stash pop` en conflit laisse
      le stash dans la pile ; un vieux stash peut détenir la SEULE copie des
      modifs pré-conflit de l'utilisateur). Dans ce cas on ne purge RIEN et on
      renvoie une note `skipped` ;
    - sinon : garder les `keep` stash nebula-* les plus récents (tous labels
      confondus, ordre `git stash list` = plus récent en tête) ;
    - dropper EN PLUS tout `nebula-pre-reset-*` VIDE (0 fichier tracké,
      `empty == True`), même s'il fait partie des `keep` plus récents --
      un pre-reset vide n'a aucune valeur de récupération ;
    - ne JAMAIS toucher un stash non-nebula (garanti par `_list_nebula_stashes`
      qui ne remonte que les labels nebula-*).

    PITFALL INDEX GIT : les `stash@{N}` se décalent à chaque drop. On
    raisonne donc par LABEL (stable), puis on re-résout la ref via un re-scan
    `_list_nebula_stashes` AVANT chaque drop, et `_drop_stash_ref` revalide
    encore une fois. Jamais de drop sur une ref figée d'un scan obsolète.

    Best-effort : ne lève jamais ; renvoie un récap `{dropped, kept, errors}`
    (+ `skipped` si la purge a été ignorée par sécurité).
    """
    result = {"dropped": [], "kept": [], "errors": []}
    try:
        stashes = _list_nebula_stashes()
        if not stashes:
            return result

        # GARDE-FOU BACKLOG : « non vide » = tout stash dont `empty` est False
        # (autostash toujours, pre-reset avec >=1 fichier tracké ou file_count
        # inconnu). Plus d'un non-vide → des modifs utilisateur potentiellement
        # uniques dorment encore dans la pile : on ne purge rien tant que le
        # backlog n'est pas récupéré/trié.
        non_empty = [s for s in stashes if not s.get("empty")]
        if len(non_empty) > 1:
            result["kept"] = [s["label"] for s in stashes]
            result["skipped"] = (
                "Purge ignorée par sécurité : plusieurs sauvegardes nebula non "
                "vides en attente (conflits de stash non résolus ?). Récupère "
                "ou supprime-les manuellement avant la purge automatique."
            )
            log.info("Prune stash nebula ignorée par sécurité : %d stash non vides en attente.",
                     len(non_empty))
            return result

        # Candidats au drop, ciblés par label (stable). Au-delà des `keep`
        # plus récents OU pre-reset vide quelle que soit la position.
        to_drop_labels: list[str] = []
        for idx, s in enumerate(stashes):
            beyond_retention = idx >= keep
            if beyond_retention or s.get("empty"):
                to_drop_labels.append(s["label"])
            else:
                result["kept"].append(s["label"])

        # Drop label par label en re-résolvant la ref à chaque itération.
        for label in to_drop_labels:
            current = _list_nebula_stashes()
            match = next((s for s in current if s["label"] == label), None)
            if not match:
                # Déjà parti (collision de labels improbable) -- on saute.
                continue
            dropped, msg = _drop_stash_ref(match["ref"], nebula=current)
            if dropped:
                result["dropped"].append(label)
            else:
                result["errors"].append(f"{label}: {msg}")
    except Exception as e:  # noqa: BLE001 -- best-effort, ne jamais casser l'update
        log.warning("Prune des stash nebula a échoué (non bloquant) : %s", e)
        result["errors"].append(str(e))
    if result["dropped"]:
        log.info("Rétention stash nebula : %d droppé(s), %d gardé(s).",
                 len(result["dropped"]), len(result["kept"]))
    return result


def system_recover_stash() -> tuple[int, dict]:
    """Tente de récupérer les modifs stashées par l'auto-update (le plus récent).

    Contexte (lot D-4) : quand `git stash pop` échoue après un pull, les modifs
    restent dans `git stash list`. Cet endpoint évite à l'utilisateur de
    passer en CLI : il applique le stash nebula le plus récent.

    Sécurité -- ne JAMAIS laisser un état cassé :
    - On refuse si le working tree a déjà des modifs non committées (un
      apply par-dessus produirait des conflits ingérables) ; l'utilisateur
      doit d'abord traiter ses modifs courantes.
    - On utilise `git stash apply` (PAS `pop`) : le stash reste TOUJOURS dans
      la pile, donc zéro perte possible.
    - En cas de conflit à l'apply, on annule proprement les fichiers trackés
      modifiés (`git checkout -- .`) pour revenir à un état propre, et on
      signale clairement. Le stash intact reste récupérable.
    - Les fichiers user-data (cf. USER_DATA_FILES) ne sont jamais touchés ici :
      on ne fait aucun reset/clean destructif, juste un apply de stash.
    - Sérialisé par _GIT_LOCK (serveur HTTP multithread).
    """
    with _GIT_LOCK:
        if not _is_git_repo():
            return 400, {"ok": False, "error": "Pas un dépôt git"}

        _check_stale_lock()

        stashes = _list_nebula_stashes()
        if not stashes:
            return 404, {
                "ok": False,
                "error": "Aucune modification stashée par Nebula à récupérer.",
                "hint": "Le `git stash list` ne contient aucun stash nebula-* "
                        "(soit aucun pull n'a stashé, soit les modifs ont déjà été récupérées).",
            }

        target = stashes[0]  # le plus récent

        # Refus si le working tree n'est pas propre (hors user-data attendues).
        rc_st, status, _ = _git("status", "--porcelain")
        raw_lines = status.splitlines() if status.strip() else []
        significant = _filter_user_data(raw_lines)
        if significant:
            return 409, {
                "ok": False,
                "error": "Tu as des modifications locales non sauvegardées.",
                "hint": "Commit, stash ou annule tes modifs courantes avant de "
                        "récupérer le stash, pour éviter des conflits ingérables.",
                "dirty_files": significant[:10],
                "stashes": stashes,
            }

        # Apply (pas pop) : le stash reste dans la pile quoi qu'il arrive.
        # Ref re-résolue par label juste avant (les stash@{N} se décalent).
        apply_ref = _find_stash_ref_by_label(target["label"]) or target["ref"]
        pre_status = _status_paths()
        if pre_status is None:
            return 500, {"ok": False, "error": "git status a échoué : récupération annulée"}
        rc_a, _apply_out, apply_err = _git("stash", "apply", apply_ref, timeout=GIT_TIMEOUT_QUICK)
        if rc_a != 0:
            # Conflit ou échec : on annule UNIQUEMENT les fichiers trackés que
            # l'apply partiel vient de modifier (propres avant). Jamais de
            # `checkout -- .` global : il écraserait les modifs locales tolérées
            # (USER_DATA_FILES : registre, workspaces.json...). Le stash intact
            # reste récupérable.
            reverted, leftovers = _undo_partial_apply(pre_status)
            return 409, {
                "ok": False,
                "error": "Conflit lors de la récupération du stash.",
                "hint": f"Tes modifs sont SAUVES dans la pile (label '{target['label']}'). "
                        f"L'application automatique provoque un conflit avec la version "
                        f"actuelle des fichiers. Résous-le manuellement : "
                        f"`git stash apply {target['ref']}` puis traite les conflits.",
                "stderr": (apply_err or "")[:300],
                "stash_label": target["label"],
                "stash_ref": target["ref"],
                "stashes": stashes,
                "reverted_files": reverted,
                "untracked_left": leftovers,
            }

        # Apply réussi. On laisse le stash dans la pile par prudence (l'utilisateur
        # peut le dropper manuellement une fois sûr que tout est OK).
        rc_d, diff_out, _ = _git("diff", "--name-only")
        changed_files = diff_out.splitlines() if rc_d == 0 else []
        needs_restart = any(f.endswith(".py") for f in changed_files)

        log.info("Stash récupéré (apply %s, %d fichiers, restart=%s)",
                 target["ref"], len(changed_files), needs_restart)

        return 200, {
            "ok": True,
            "applied_ref": target["ref"],
            "stash_label": target["label"],
            "files_changed": changed_files,
            "needs_restart": needs_restart,
            "remaining_stashes": _list_nebula_stashes(),
            "message": (
                f"Modifs récupérées depuis le stash « {target['label']} ». "
                "Le stash est conservé dans la pile par sécurité (supprime-le "
                "manuellement via `git stash drop` une fois que tout est vérifié)."
                + (" Des fichiers Python ont changé : redémarre le dashboard."
                   if needs_restart else "")
            ),
        }


def system_drop_stash(ref: str) -> tuple[int, dict]:
    """Supprime un stash nebula-* de la pile (`git stash drop`).

    Contexte (lot D-4 raffinement) : apres une recuperation reussie via
    `system_recover_stash`, le stash est conserve par securite. Une fois ses
    modifs verifiees, l'utilisateur peut l'oublier en 1-clic, sans CLI.

    Securite : on ne droppe QUE des stash crees par l'auto-update Nebula
    (labels nebula-autostash-* / nebula-pre-reset-*), jamais un stash
    utilisateur arbitraire. La ref est revalidee contre la liste courante.
    Sérialisé par _GIT_LOCK (serveur HTTP multithread).
    """
    with _GIT_LOCK:
        if not _is_git_repo():
            return 400, {"ok": False, "error": "Pas un dépôt git"}
        ref = (ref or "").strip()
        if not ref:
            return 400, {"ok": False, "error": "Référence de stash manquante."}

        nebula = _list_nebula_stashes()
        match = next((s for s in nebula if s["ref"] == ref), None)
        if not match:
            return 404, {
                "ok": False,
                "error": "Stash introuvable ou non géré par Nebula.",
                "hint": "La référence a peut-être changé (un autre stash supprimé "
                        "entre-temps). Rouvre la fenêtre de mise à jour.",
                "stashes": nebula,
            }

        dropped, msg = _drop_stash_ref(ref, nebula=nebula)
        if not dropped:
            return 500, {"ok": False, "error": "Échec de la suppression du stash.",
                         "stderr": msg}

        return 200, {
            "ok": True,
            "message": msg,
            "remaining_stashes": _list_nebula_stashes(),
        }


def system_prune_stashes(refs: list | None = None, keep: int = 3) -> tuple[int, dict]:
    """Purge groupée des stash nebula-* depuis l'UI (« Nettoyer les sauvegardes »).

    Deux modes :
    - `refs` fourni (liste non vide) : drop ciblé de ces refs précises (chaque
      ref est revalidée comme stash nebula-* par `_drop_stash_ref` -- une ref
      non-nebula ou inconnue est IGNORÉE, jamais droppée) ;
    - `refs` absent / vide : applique la politique de rétention auto
      (`_prune_nebula_stashes`, garde les `keep` plus récents + droppe les
      pre-reset vides ; purge ignorée si backlog non résolu -- cf. garde-fou).

    PITFALL INDEX GIT : en mode `refs`, on traduit d'abord les refs en LABELS
    (stables), puis on droppe en re-résolvant à chaque itération. Drop direct
    par `stash@{N}` figé décalerait les autres refs et supprimerait le mauvais
    stash.

    INVARIANT DUR : seuls les stash nebula-* sont touchés (garde dans
    `_drop_stash_ref`). Un stash utilisateur (« WIP … » sans label nebula-*)
    n'est jamais droppé, même si sa ref est passée explicitement.
    Sérialisé par _GIT_LOCK (serveur HTTP multithread).
    """
    with _GIT_LOCK:
        if not _is_git_repo():
            return 400, {"ok": False, "error": "Pas un dépôt git"}

        _check_stale_lock()

        if refs:
            nebula = _list_nebula_stashes()
            # Traduit les refs demandées en labels nebula valides (ignore le reste).
            labels = []
            ignored = []
            for ref in refs:
                match = next((s for s in nebula if s["ref"] == (ref or "").strip()), None)
                if match:
                    labels.append(match["label"])
                else:
                    ignored.append(ref)
            dropped, errors = [], []
            for label in labels:
                current = _list_nebula_stashes()
                match = next((s for s in current if s["label"] == label), None)
                if not match:
                    continue
                ok, msg = _drop_stash_ref(match["ref"], nebula=current)
                (dropped if ok else errors).append(label if ok else f"{label}: {msg}")
            return 200, {
                "ok": True,
                "dropped": dropped,
                "errors": errors,
                "ignored": ignored,
                "remaining_stashes": _list_nebula_stashes(),
                "message": (f"{len(dropped)} sauvegarde(s) supprimée(s)."
                            if dropped else "Aucune sauvegarde supprimée."),
            }

        # Mode politique de rétention.
        res = _prune_nebula_stashes(keep=keep)
        return 200, {
            "ok": True,
            "dropped": res["dropped"],
            "kept": res["kept"],
            "errors": res["errors"],
            "remaining_stashes": _list_nebula_stashes(),
            "message": (f"{len(res['dropped'])} sauvegarde(s) ancienne(s) purgée(s) "
                        f"(rétention : {keep} récentes conservées)."
                        if res["dropped"]
                        else res.get("skipped") or "Aucune sauvegarde à purger."),
        }


def system_reset_to_upstream() -> tuple[int, dict]:
    """Escape hatch : force l'alignement sur la branche distante (git reset --hard).

    À utiliser uniquement quand `system_apply_update` échoue à cause d'une
    branche divergée, d'un état corrompu, ou d'un fichier qui résiste au
    stash. Pré-stash systématique pour ne JAMAIS perdre les modifs locales.

    Données utilisateur (registry, workspaces.json, .env.local…) préservées
    via .gitignore et skip-worktree — non touchées par reset --hard.
    Sérialisé par _GIT_LOCK (serveur HTTP multithread).
    """
    with _GIT_LOCK:
        if not _is_git_repo():
            return 400, {"ok": False, "error": "Pas un dépôt git"}
        upstream = _tracking_branch()
        if not upstream:
            return 400, {"ok": False, "error": "Aucune branche distante trackée"}

        # Lock orphelin
        _check_stale_lock()

        # 1. Fetch D'ABORD : s'il échoue (réseau, auth), rien n'a été touché
        #    (avant : le stash -u était fait avant le fetch et un fetch KO
        #    laissait les fichiers non suivis de l'utilisateur rangés dans la pile).
        _migrate_origin_remote()
        rc_f, _, fetch_err = _git("fetch", "--quiet", timeout=GIT_TIMEOUT_FETCH)
        if rc_f != 0:
            return 500, {"ok": False, "error": "git fetch a échoué", "stderr": fetch_err}

        # 2. Stash de sauvegarde des fichiers TRACKÉS modifiés uniquement :
        #    `reset --hard` ne touche pas aux non suivis, inutile de les retirer
        #    du disque. USER_DATA_FILES exclus du stash (préservés à part, cf. 3).
        #    Stash nommé + vérifié par message ; si des modifs trackées existent
        #    et que le stash n'est pas confirmé -> ABANDON (pas de reset).
        rc_st, status, _ = _git("status", "--porcelain", "--untracked-files=no")
        tracked_dirty = _filter_user_data(status.splitlines() if status.strip() else [])
        stash_label = _new_stash_label("nebula-pre-reset")
        stash_applied = False
        if rc_st != 0:
            return 500, {"ok": False, "error": "git status a échoué : reset annulé"}
        if tracked_dirty:
            stash_applied, stash_err = _stash_push_verified(
                stash_label, include_untracked=False, exclude=tuple(sorted(USER_DATA_FILES)))
            if not stash_applied:
                return 500, {"ok": False,
                             "error": "Sauvegarde (stash) des modifs locales impossible : reset annulé.",
                             "stderr": stash_err, "dirty_files": tracked_dirty[:10]}
            log.info("Pre-reset stash effectué (label=%s)", stash_label)

        # 3. Reset --hard sur upstream, USER_DATA_FILES restaurés à l'identique
        #    (registre, workspaces.json... s'ils sont trackés sans skip-worktree).
        user_snap = _snapshot_user_data()
        rc_b, head_before, _ = _git("rev-parse", "HEAD")
        try:
            rc_r, _, reset_err = _git("reset", "--hard", upstream)
        finally:
            restored_user_data = _restore_user_data(user_snap)
        if rc_r != 0:
            return 500, {"ok": False, "error": "git reset --hard a échoué",
                         "stderr": reset_err, "stash_applied": stash_applied,
                         "stash_label": stash_label if stash_applied else None}

        rc_a, head_after, _ = _git("rev-parse", "HEAD")
        rc_d, diff_out, _ = _git("diff", "--name-only", head_before, head_after)
        changed_files = diff_out.splitlines() if rc_d == 0 else []
        needs_restart = any(f.endswith(".py") for f in changed_files)

        log.warning("system reset to upstream: %s → %s (%d fichiers, restart=%s)",
                    head_before[:7], head_after[:7], len(changed_files), needs_restart)

        # Rétention auto après reset réussi. Le pre-reset fraîchement créé est le
        # plus récent (gardé par la politique) SAUF s'il est vide -- un pre-reset
        # à 0 fichier tracké ne protège rien et est purgé systématiquement. Purge
        # aussi les anciens pre-reset vides accumulés.
        pruned = _prune_nebula_stashes()

        return 200, {
            "ok": True,
            "from": head_before[:7],
            "to": head_after[:7],
            "files_changed": changed_files,
            "needs_restart": needs_restart,
            "stash_applied": stash_applied,
            "stash_label": stash_label if stash_applied else None,
            "user_data_restored": restored_user_data,
            "stashes_pruned": pruned["dropped"],
            "message": (
                f"Repo réinitialisé sur {upstream}. "
                + (f"Tes modifs sont sauvegardées dans `git stash list` (label: {stash_label})." if stash_applied else "")
            ),
        }
