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
import time
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


def _check_stale_lock() -> tuple[bool, str]:
    """Détecte un .git/index.lock orphelin (process git crashé). Retourne (removed, message)."""
    lock = ROOT / ".git" / "index.lock"
    if not lock.exists():
        return False, ""
    try:
        age = time.time() - lock.stat().st_mtime
    except OSError:
        return False, ""
    if age > 60:  # > 1 min : très probablement orphelin
        try:
            lock.unlink()
            log.warning("Removed stale .git/index.lock (%ds old)", int(age))
            return True, f"Lock orphelin retiré (âge: {int(age)}s)"
        except OSError as e:
            return False, f"Lock orphelin détecté mais retrait échoué: {e}"
    return False, f"Lock actif (âge: {int(age)}s) — un autre git tourne ?"


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
    1. Pré-check : retire un index.lock orphelin (si > 60s)
    2. Si dirty (status non vide), pré-stash systématique (--include-untracked)
       avec timestamp pour ne pas collisionner avec les autres autostash
    3. Pull --ff-only (peut maintenant pas planter sur dirty)
    4. Si on a stashé : pop pour restaurer. Si pop conflit → modifs préservées
       dans la pile, warning explicite, l'utilisateur peut récupérer via CLI
    5. Si pull échoue malgré ça : on hint sur le mode de panne (réseau,
       diverged, auth…) et on suggère le reset hard si pertinent
    6. Aucune perte de données possible : le stash reste tant qu'il n'est
       pas explicitement drop
    """
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
    rc_st, status, _ = _git("status", "--porcelain")
    has_local_changes = bool(status.strip())

    stash_applied = False
    stash_pop_warning = None
    stash_label = f"nebula-autostash-{int(time.time())}"

    # Avant de stasher, on détecte les fichiers de données utilisateur connus
    # (.env.local, registry.json, workspaces.json…) qui pourraient se retrouver
    # dans le stash si l'utilisateur n'a pas configuré skip-worktree.
    sensitive_in_stash: list[str] = []
    if has_local_changes:
        sensitive_patterns = (".env.local", "mcp/registry.json",
                              "dashboard/data/workspaces.json")
        for line in status.splitlines():
            # format porcelain : "XY path"
            path = line[3:].strip().strip('"')
            if any(p in path for p in sensitive_patterns):
                sensitive_in_stash.append(path)

        rc_s, _, stash_err = _git(
            "stash", "push", "--include-untracked", "-m", stash_label,
            timeout=GIT_TIMEOUT_QUICK,
        )
        if rc_s == 0:
            stash_applied = True
            log.info("Pre-pull stash effectué (%d entrées status, label=%s)",
                     len(status.splitlines()), stash_label)
            if sensitive_in_stash:
                log.warning("Stash contient des fichiers sensibles : %s — label %s",
                            sensitive_in_stash, stash_label)
        else:
            # Stash a échoué — on continue quand même, peut-être que pull marchera
            log.warning("git stash a échoué (continuons quand même) : %s", stash_err)

    # 3. Pull --ff-only sur état propre (ou presque)
    rc_p, pull_out, pull_err = _git("pull", "--ff-only", timeout=GIT_TIMEOUT_PULL)

    # 4. Si on a stashé, toujours essayer le pop (même si pull a échoué :
    #    on veut restaurer l'état local plutôt que laisser le user en limbo)
    if stash_applied:
        rc_pop, _pop_out, pop_err = _git("stash", "pop", timeout=GIT_TIMEOUT_QUICK)
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
    - garder les `keep` stash nebula-* les plus récents (tous labels
      confondus, ordre `git stash list` = plus récent en tête) ;
    - dropper EN PLUS tout `nebula-pre-reset-*` VIDE (0 fichier tracké,
      `empty == True`), même s'il fait partie des `keep` les plus récents --
      un pre-reset vide n'a aucune valeur de récupération ;
    - ne JAMAIS toucher un stash non-nebula (garanti par `_list_nebula_stashes`
      qui ne remonte que les labels nebula-*).

    PITFALL INDEX GIT : les `stash@{N}` se décalent à chaque drop. On
    raisonne donc par LABEL (stable), puis on re-résout la ref via un re-scan
    `_list_nebula_stashes` AVANT chaque drop, et `_drop_stash_ref` revalide
    encore une fois. Jamais de drop sur une ref figée d'un scan obsolète.

    Best-effort : ne lève jamais ; renvoie un récap `{dropped, kept, errors}`.
    """
    result = {"dropped": [], "kept": [], "errors": []}
    try:
        stashes = _list_nebula_stashes()
        if not stashes:
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
    """
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
    rc_a, _apply_out, apply_err = _git("stash", "apply", target["ref"], timeout=GIT_TIMEOUT_QUICK)
    if rc_a != 0:
        # Conflit ou échec : on revient à un état propre pour ne pas laisser
        # de marqueurs de conflit. checkout -- . annule les fichiers trackés
        # modifiés par l'apply partiel ; le stash intact reste récupérable.
        _git("checkout", "--", ".")
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
    """
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
      pre-reset vides).

    PITFALL INDEX GIT : en mode `refs`, on traduit d'abord les refs en LABELS
    (stables), puis on droppe en re-résolvant à chaque itération. Drop direct
    par `stash@{N}` figé décalerait les autres refs et supprimerait le mauvais
    stash.

    INVARIANT DUR : seuls les stash nebula-* sont touchés (garde dans
    `_drop_stash_ref`). Un stash utilisateur (« WIP … » sans label nebula-*)
    n'est jamais droppé, même si sa ref est passée explicitement.
    """
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
                    if res["dropped"] else "Aucune sauvegarde à purger."),
    }


def system_reset_to_upstream() -> tuple[int, dict]:
    """Escape hatch : force l'alignement sur la branche distante (git reset --hard).

    À utiliser uniquement quand `system_apply_update` échoue à cause d'une
    branche divergée, d'un état corrompu, ou d'un fichier qui résiste au
    stash. Pré-stash systématique pour ne JAMAIS perdre les modifs locales.

    Données utilisateur (registry, workspaces.json, .env.local…) préservées
    via .gitignore et skip-worktree — non touchées par reset --hard.
    """
    if not _is_git_repo():
        return 400, {"ok": False, "error": "Pas un dépôt git"}
    upstream = _tracking_branch()
    if not upstream:
        return 400, {"ok": False, "error": "Aucune branche distante trackée"}

    # Lock orphelin
    _check_stale_lock()

    # 1. Stash de sauvegarde (au cas où, label horodaté)
    rc_st, status, _ = _git("status", "--porcelain")
    stash_label = f"nebula-pre-reset-{int(time.time())}"
    stash_applied = False
    if status.strip():
        rc_s, _, _ = _git("stash", "push", "--include-untracked", "-m", stash_label,
                          timeout=GIT_TIMEOUT_QUICK)
        if rc_s == 0:
            stash_applied = True
            log.info("Pre-reset stash effectué (label=%s)", stash_label)

    # 2. Fetch
    rc_f, _, fetch_err = _git("fetch", "--quiet", timeout=GIT_TIMEOUT_FETCH)
    if rc_f != 0:
        return 500, {"ok": False, "error": "git fetch a échoué", "stderr": fetch_err}

    # 3. Reset --hard sur upstream
    rc_b, head_before, _ = _git("rev-parse", "HEAD")
    rc_r, _, reset_err = _git("reset", "--hard", upstream)
    if rc_r != 0:
        return 500, {"ok": False, "error": "git reset --hard a échoué",
                     "stderr": reset_err, "stash_applied": stash_applied}

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
        "stashes_pruned": pruned["dropped"],
        "message": (
            f"Repo réinitialisé sur {upstream}. "
            + (f"Tes modifs sont sauvegardées dans `git stash list` (label: {stash_label})." if stash_applied else "")
        ),
    }
