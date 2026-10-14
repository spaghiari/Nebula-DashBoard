"""Plugins Claude Code : installé vs clone local du marketplace.

Répond à « mes plugins sont-ils à jour ? » SANS réseau : on compare ce que
Claude Code a installé (`~/.claude/plugins/installed_plugins.json`) au clone
local de chaque marketplace (`~/.claude/plugins/marketplaces/<nom>/`). Ce
clone n'est rafraîchi que par `claude plugin marketplace update` (au
démarrage de Claude Code pour les marketplaces en mise à jour auto, ou à la
demande via `refresh_marketplaces`) : la réponse vaut « d'après le
marketplace local, rafraîchi le ... », jamais plus.

Règles de comparaison (`compare_plugin`) :
1. Version explicite côté marketplace (entrée du `marketplace.json`, ou
   `plugin.json` du plugin dans le clone) : comparaison de versions.
2. Sinon, plugin hébergé DANS le clone (source relative) : Claude Code le
   versionne par la révision du marketplace. Même révision -> à jour ; sinon
   on compare le CONTENU installé à celui du clone (une nouvelle révision du
   marketplace ne touche souvent pas ce plugin) : identique -> à jour.
3. Sinon, plugin hébergé ailleurs (dépôt git, URL) : révision épinglée
   comparée à la révision installée quand c'est significatif ; dans le doute
   (version déclarée dans un dépôt non cloné, branche suivie), « inconnu »
   avec la raison, plutôt qu'un « à jour » non étayé.
"""
from __future__ import annotations

import hashlib
import re
import threading
from pathlib import Path

from dashcore import config as _config
from dashcore.helpers import read_json

UP_TO_DATE, OUTDATED, UNKNOWN = "up_to_date", "outdated", "unknown"
REFRESH_TIMEOUT_S = 180
_SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")
_VERSION_RE = re.compile(r"^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$")
_NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]{0,79}$")
# Marqueurs posés par Claude Code dans le dossier installé, absents du clone.
_CONTENT_SKIP = {".in_use", ".git", ".orphaned_at"}
_CONTENT_MAX_FILES = 5000
_CONTENT_MAX_BYTES = 20 * 1024 * 1024  # par fichier ; au-delà : empreinte inconnue
_REFRESH_LOCK = threading.Lock()


def plugins_dir() -> Path:
    return _config.CLAUDE_HOME / "plugins"


# ── Versions ─────────────────────────────────────────────────────────────────

def version_key(v: str):
    """Clé triable d'une version semver-like, None si non reconnue.

    Une pré-version (`1.2.0-beta`) passe avant la version finale (`1.2.0`).
    """
    m = _VERSION_RE.match((v or "").strip())
    if not m:
        return None
    nums = tuple(int(x) if x else 0 for x in m.group(1, 2, 3))
    pre = m.group(4)
    return nums + ((1, "") if pre is None else (0, pre))


def compare_versions(installed: str, available: str) -> int | None:
    """-1 si installé < disponible, 0 si égal, 1 si plus récent ; None si incomparable."""
    if (installed or "").strip() == (available or "").strip():
        return 0
    a, b = version_key(installed), version_key(available)
    if a is None or b is None:
        return None
    return (a > b) - (a < b)


def _looks_like_sha(v: str) -> bool:
    return bool(_SHA_RE.match((v or "").strip().lower()))


# ── Marketplaces locaux ──────────────────────────────────────────────────────

def _git_head_sha(repo: Path) -> str | None:
    """Révision HEAD d'un clone git, lue sur disque (aucun process lancé)."""
    git = repo / ".git"
    try:
        head = (git / "HEAD").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if _looks_like_sha(head):
        return head.lower()
    if not head.startswith("ref:"):
        return None
    ref = head[4:].strip()
    try:
        sha = (git / ref).read_text(encoding="utf-8").strip()
        if _looks_like_sha(sha):
            return sha.lower()
    except OSError:
        pass
    try:
        for line in (git / "packed-refs").read_text(encoding="utf-8").splitlines():
            parts = line.strip().split(" ", 1)
            if len(parts) == 2 and parts[1] == ref and _looks_like_sha(parts[0]):
                return parts[0].lower()
    except OSError:
        pass
    return None


def _marketplace_revision(path: Path) -> str | None:
    """Révision du clone : `.gcs-sha` (archive téléchargée) ou HEAD git."""
    try:
        sha = (path / ".gcs-sha").read_text(encoding="utf-8").strip().lower()
        if _looks_like_sha(sha):
            return sha
    except OSError:
        pass
    return _git_head_sha(path)


def load_marketplaces(base: Path | None = None) -> dict:
    """{nom: {path, exists, last_updated, revision, manifest}} des marketplaces connus."""
    base = base or plugins_dir()
    known = read_json(base / "known_marketplaces.json", {}) or {}
    out: dict = {}
    names = set(known) if isinstance(known, dict) else set()
    mroot = base / "marketplaces"
    if mroot.is_dir():
        names |= {p.name for p in mroot.iterdir() if p.is_dir()}
    for name in sorted(names):
        if not _NAME_RE.match(name):
            continue
        info = known.get(name) if isinstance(known, dict) else None
        info = info if isinstance(info, dict) else {}
        loc = info.get("installLocation")
        path = Path(loc) if isinstance(loc, str) and loc else mroot / name
        exists = path.is_dir()
        manifest = read_json(path / ".claude-plugin" / "marketplace.json", None) if exists else None
        out[name] = {
            "path": path,
            "exists": exists,
            "last_updated": info.get("lastUpdated") if isinstance(info.get("lastUpdated"), str) else None,
            "revision": _marketplace_revision(path) if exists else None,
            "manifest": manifest if isinstance(manifest, dict) else None,
        }
    return out


# ── Comparaison ──────────────────────────────────────────────────────────────

def _content_digest(root: Path) -> str | None:
    """Empreinte du contenu d'un dossier (chemins relatifs + octets)."""
    if not root.is_dir():
        return None
    h = hashlib.sha256()
    files: list[Path] = []
    try:
        # Parcours sans suivre liens symboliques ni jonctions, arrêt dès que
        # le plafond est dépassé (l'Accueil appelle ce calcul à chaque visite).
        stack = [root]
        while stack:
            d = stack.pop()
            for p in d.iterdir():
                if p.name in _CONTENT_SKIP or p.is_symlink() or _is_junction(p):
                    continue
                if p.is_dir():
                    stack.append(p)
                elif p.is_file():
                    files.append(p)
                    if len(files) > _CONTENT_MAX_FILES:
                        return None
        for f in sorted(files):
            if f.stat().st_size > _CONTENT_MAX_BYTES:
                return None
            fh = hashlib.sha256()
            with f.open("rb") as stream:
                for chunk in iter(lambda: stream.read(65536), b""):
                    fh.update(chunk)
            h.update(f.relative_to(root).as_posix().encode("utf-8") + b"\0")
            h.update(fh.digest())
    except OSError:
        return None
    return h.hexdigest()


def _is_junction(p: Path) -> bool:
    """Jonction Windows (Path.is_junction n'existe qu'à partir de 3.12)."""
    fn = getattr(p, "is_junction", None)
    return bool(fn and fn())


def _relative_source_dir(mkt_path: Path, source: str) -> Path | None:
    """Dossier d'un plugin à source relative, confiné au clone du marketplace."""
    try:
        base = mkt_path.resolve()
        target = (mkt_path / source).resolve()
    except OSError:
        return None
    if target == base or not target.is_relative_to(base):
        return None
    return target


def _short(v: str | None) -> str:
    v = (v or "").strip()
    return v[:12] if _looks_like_sha(v) else v


def _result(state: str, installed: str, available: str | None, reason: str, basis: str = "") -> dict:
    return {"state": state, "installed": _short(installed), "available": _short(available) or None,
            "reason": reason, "basis": basis}


def compare_plugin(name: str, entry: dict, mkt: dict | None, mkt_name: str | None) -> dict:
    """Verdict « à jour » d'UN plugin installé (cf. docstring du module)."""
    inst_version = str(entry.get("version") or "").strip()
    inst_sha = str(entry.get("gitCommitSha") or "").strip().lower()
    installed = inst_version if inst_version and inst_version != "unknown" else inst_sha
    if not mkt_name:
        return _result(UNKNOWN, installed, None, "Plugin sans marketplace : rien à comparer.")
    if not mkt or not mkt["exists"]:
        return _result(UNKNOWN, installed, None, f"Marketplace « {mkt_name} » absent localement.")
    manifest = mkt["manifest"]
    if not manifest:
        return _result(UNKNOWN, installed, None, f"Manifeste du marketplace « {mkt_name} » illisible.")
    plist = manifest.get("plugins") if isinstance(manifest.get("plugins"), list) else []
    spec = next((p for p in plist if isinstance(p, dict) and p.get("name") == name), None)
    if spec is None:
        return _result(UNKNOWN, installed, None, f"Plus listé dans le marketplace « {mkt_name} ».")

    source = spec.get("source")
    src_dir = _relative_source_dir(mkt["path"], source) if isinstance(source, str) else None
    if isinstance(source, str) and src_dir is None:
        return _result(UNKNOWN, installed, None, "Source relative hors du clone du marketplace : ignorée.")
    avail_version = str(spec.get("version") or "").strip()
    if not avail_version and src_dir is not None:
        meta = read_json(src_dir / ".claude-plugin" / "plugin.json", {}) or {}
        avail_version = str(meta.get("version") or "").strip() if isinstance(meta, dict) else ""

    # 1. Version explicite côté marketplace.
    if avail_version:
        cmp = compare_versions(inst_version, avail_version)
        if cmp is not None and cmp >= 0:
            return _result(UP_TO_DATE, installed, avail_version, "Même version que le marketplace.", "version")
        if cmp is not None:
            return _result(OUTDATED, installed, avail_version,
                           f"Version {avail_version} disponible dans le marketplace.", "version")
        # Installé versionné par révision (SHA) alors que le marketplace
        # déclare désormais une version : le changement de schéma est réel.
        if _looks_like_sha(inst_version):
            return _result(OUTDATED, installed, avail_version,
                           f"Version {avail_version} disponible dans le marketplace.", "version")
        why = ("Version installée inconnue." if inst_version.lower() in ("", "unknown")
               else f"Versions non comparables ({inst_version} / {avail_version}).")
        return _result(UNKNOWN, installed, avail_version, why, "version")

    # 2. Plugin hébergé dans le clone : versionné par la révision du marketplace.
    if src_dir is not None:
        rev = mkt["revision"]
        if not rev:
            return _result(UNKNOWN, installed, None, "Révision du marketplace inconnue.")
        if (inst_sha and inst_sha == rev) or (_looks_like_sha(inst_version) and rev.startswith(inst_version.lower())):
            return _result(UP_TO_DATE, installed, rev, "Même révision que le marketplace.", "revision")
        install_path = Path(entry["installPath"]) if isinstance(entry.get("installPath"), str) else None
        mine = _content_digest(install_path) if install_path else None
        theirs = _content_digest(src_dir)
        if mine is None or theirs is None:
            return _result(UNKNOWN, installed, rev, "Contenu installé ou du marketplace illisible.")
        if mine == theirs:
            return _result(UP_TO_DATE, installed, rev,
                           "Révision différente mais contenu identique à celui du marketplace.", "content")
        return _result(OUTDATED, installed, rev, "Le contenu du plugin a changé dans le marketplace.", "content")

    # 3. Plugin hébergé ailleurs (git, url, github).
    pinned = str(source.get("sha") or "").strip().lower() if isinstance(source, dict) else ""
    if not _looks_like_sha(pinned):
        return _result(UNKNOWN, installed, None,
                       "Source distante non épinglée : non vérifiable sans réseau.")
    if inst_sha and (inst_sha == pinned or pinned.startswith(inst_sha) or inst_sha.startswith(pinned)):
        return _result(UP_TO_DATE, installed, pinned, "Même révision que celle épinglée par le marketplace.", "revision")
    if inst_version and not _looks_like_sha(inst_version):
        return _result(UNKNOWN, installed, pinned,
                       "Révision épinglée différente, mais la version est déclarée dans le dépôt du plugin "
                       "(non téléchargé) : non vérifiable sans réseau.")
    return _result(OUTDATED, installed, pinned, "Nouvelle révision épinglée par le marketplace.", "revision")


def _pick_entry(entries) -> dict:
    """Même choix que la page Plugins : scope user d'abord, sinon la 1re entrée."""
    if not isinstance(entries, list):
        return {}
    good = [e for e in entries if isinstance(e, dict)]
    return next((e for e in good if e.get("scope") == "user"), None) or (good[0] if good else {})


def plugin_updates(base: Path | None = None) -> dict:
    """Synthèse pour l'Accueil et la page Plugins (`GET /api/plugins/outdated`)."""
    base = base or plugins_dir()
    installed = (read_json(base / "installed_plugins.json", {}) or {}).get("plugins") or {}
    mkts = load_marketplaces(base)
    plugins: dict = {}
    used: set = set()
    if isinstance(installed, dict):
        for key, entries in installed.items():
            name, _, mkt_name = str(key).partition("@")
            mkt_name = mkt_name or None
            if mkt_name:
                used.add(mkt_name)
            plugins[key] = compare_plugin(name, _pick_entry(entries), mkts.get(mkt_name), mkt_name)
    counts = {UP_TO_DATE: 0, OUTDATED: 0, UNKNOWN: 0}
    for r in plugins.values():
        counts[r["state"]] += 1
    dates = [mkts[m]["last_updated"] for m in used if m in mkts and mkts[m]["last_updated"]]
    return {
        "plugins": plugins,
        "counts": counts,
        "total": len(plugins),
        "marketplaces": {
            n: {"exists": m["exists"], "last_updated": m["last_updated"], "used": n in used}
            for n, m in mkts.items()
        },
        # Le plus ANCIEN rafraîchissement parmi les marketplaces utilisés :
        # la date affichée ne surestime jamais la fraîcheur de l'information.
        "checked_at": min(dates) if dates else None,
    }


def refresh_marketplaces(name: str | None = None) -> tuple[int, dict]:
    """`claude plugin marketplace update [nom]` à la demande (bouton de la page Plugins).

    Échec (CLI absente, timeout, code retour non nul) -> HTTP non-ok +
    `{"error"}` : jamais de faux succès côté interface.
    """
    if name is not None and (not isinstance(name, str) or not _NAME_RE.match(name)):
        return 400, {"error": "nom de marketplace invalide"}
    if not _REFRESH_LOCK.acquire(blocking=False):
        return 409, {"error": "Un rafraîchissement des marketplaces est déjà en cours."}
    try:
        # Import local : api_plugins importe des modules lourds (workspaces...).
        from dashcore.api_plugins import claude_plugin_cli
        args = ["marketplace", "update"] + ([name] if name else [])
        status, r = claude_plugin_cli(args, timeout=REFRESH_TIMEOUT_S)
        if status != 200:
            return 502, {"error": r.get("error") or "échec de claude plugin marketplace update"}
        if not r.get("ok"):
            tail = ((r.get("stderr") or "").strip() or (r.get("stdout") or "").strip())[-400:]
            return 502, {"error": "claude plugin marketplace update a échoué"
                                  + (f" (code {r.get('returncode')}) : {tail}" if tail else f" (code {r.get('returncode')})")}
        return 200, {"ok": True, "updates": plugin_updates()}
    finally:
        _REFRESH_LOCK.release()
