"""Bibliothèque de skills — magasin centralisé.

Modèle :
- `dashboard/data/skills-library/<name>/SKILL.md` = source de vérité (le magasin).
- Distribution = copie complète du dossier vers une cible :
    - Global : `~/.claude/skills/<name>/`
    - Workspace : `<ws>/.claude/skills/<name>/`
- Aucun auto-sync : si on édite la bibliothèque, les copies déjà distribuées
  sont marquées "désynchronisées" mais NE sont PAS écrasées en silence.
- Resync explicite via `distribute()` qui set le complet (ajoute/écrase/retire).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import threading
from pathlib import Path

from dashcore.config import SKILLS_LIBRARY_DIR, CLAUDE_HOME
from dashcore.helpers import (
    _remove_dir_or_link, parse_skill_frontmatter, safe_id, resolve_ws_dir,
)
from dashcore.workspace_io import _ws_dir_from_entry, list_workspaces


def _ensure_library() -> None:
    SKILLS_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)


def _target_parent(target: str) -> Path | None:
    """Retourne le dossier *parent* (qui contiendra <name>/) selon la cible."""
    if target == "global":
        return CLAUDE_HOME / "skills"
    if target.startswith("workspace:"):
        ws_id = target.split(":", 1)[1]
        if not safe_id(ws_id):
            return None
        return resolve_ws_dir(ws_id) / ".claude" / "skills"
    return None


# Cache de `_hash_dir` (même principe que le cache de stats de
# `workspace_io.py`). Clé : chemin absolu du dossier ; valeur : (signature,
# hash). La signature = tuple trié (chemin relatif, st_mtime_ns, st_size) de
# chaque fichier pris en compte : tout ajout, suppression, renommage ou
# réécriture d'un fichier change la signature et force un recalcul. Le
# parcours + stat reste fait à chaque appel (peu coûteux) ; seule la lecture
# du contenu (le coût réel) est évitée. Hash produit strictement identique à
# la version sans cache (mêmes octets hachés dans le même ordre).
_HASH_CACHE: dict[str, tuple[tuple, str]] = {}
_HASH_CACHE_LOCK = threading.Lock()
# Garde-fou mémoire : bibliothèque + copies global/workspaces restent bien
# en dessous ; au-delà on vide tout (les dossiers disparus ne s'accumulent pas).
_HASH_CACHE_MAX = 2048


def _walk_files(d: Path) -> list[tuple[Path, os.stat_result]]:
    """Fichiers réguliers sous `d` (liens vers fichier suivis, liens vers
    dossier non parcourus, comme `rglob` en 3.13) avec leur stat.

    `DirEntry.stat()` réutilise les métadonnées du listage sous Windows :
    pas d'appel système par fichier (le coût dominant de `_hash_dir`).
    """
    out: list[tuple[Path, os.stat_result]] = []
    stack = [d]
    while stack:
        cur = stack.pop()
        try:
            with os.scandir(cur) as it:
                entries = list(it)
        except OSError:
            continue
        for e in entries:
            try:
                if e.is_dir(follow_symlinks=False):
                    stack.append(Path(e.path))
                    continue
                st = e.stat()
            except OSError:
                continue  # équivalent de `is_file()` -> False
            if stat.S_ISREG(st.st_mode):
                out.append((Path(e.path), st))
    return out


def _hash_dir(d: Path) -> str:
    """Hash récursif du contenu d'un dossier (ignore .nebula-origin.json).

    Mis en cache par dossier, invalidé par la signature (mtime_ns, taille)
    de ses fichiers (cf. `_HASH_CACHE`).
    """
    if not d.exists():
        return ""
    files: list[tuple[Path, str]] = []
    sig: list[tuple[str, int, int]] = []
    # Même ordre que l'ancien `sorted(d.rglob("*"))` (tri des Path) ; le
    # parcours `os.scandir` évite un stat() système par fichier sous Windows.
    for f, st in sorted(_walk_files(d), key=lambda item: item[0]):
        if f.name == ".nebula-origin.json":
            continue
        rel = f.relative_to(d).as_posix()
        files.append((f, rel))
        sig.append((rel, st.st_mtime_ns, st.st_size))
    key = str(d.absolute())
    signature = tuple(sig)
    with _HASH_CACHE_LOCK:
        hit = _HASH_CACHE.get(key)
    if hit is not None and hit[0] == signature:
        return hit[1]

    h = hashlib.sha256()
    cacheable = True
    for f, rel in files:
        # Ordre des update() conservé à l'identique (y compris le cas d'un
        # fichier illisible : chemin + séparateur déjà hachés, contenu absent).
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        try:
            h.update(f.read_bytes())
        except OSError:
            cacheable = False  # résultat transitoire : ne pas le figer
            continue
        h.update(b"\0")
    digest = h.hexdigest()
    if cacheable:
        with _HASH_CACHE_LOCK:
            if len(_HASH_CACHE) >= _HASH_CACHE_MAX:
                _HASH_CACHE.clear()
            _HASH_CACHE[key] = (signature, digest)
    return digest


def _read_origin(d: Path) -> dict | None:
    """Lit `.nebula-origin.json` d'un skill importé (repo, commit, source_path).

    Écrit par l'import GitHub (cf. `import_dir_into_library`). Retourné par
    `list_library` pour le chip « GitHub: owner/repo@sha » (lot E item 5).
    Tolérant : retourne None si absent ou JSON cassé.
    """
    f = d / ".nebula-origin.json"
    if not f.exists():
        return None
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def list_library() -> list[dict]:
    _ensure_library()
    # Racines skills des workspaces calculées UNE fois : avant, chaque skill
    # relisait workspaces.json une fois par workspace (resolve_ws_dir) ->
    # O(skills x workspaces) lectures JSON.
    ws_roots = _workspace_skill_roots()
    # Sous-dossiers de chaque racine listés une fois (au lieu de 2 exists()
    # par skill et par workspace) : cf. `_distribution_for`.
    listing: dict[str, set[str]] = {}
    out = []
    for sub in sorted(SKILLS_LIBRARY_DIR.iterdir()):
        if not sub.is_dir():
            continue
        skill_md = sub / "SKILL.md"
        if not skill_md.exists():
            continue
        meta = parse_skill_frontmatter(skill_md)
        dist = _distribution_for(sub.name, _hash_dir(sub), ws_roots, listing)
        out.append({
            "id": sub.name,
            "name": meta.get("name") or sub.name,
            "description": meta.get("description") or "",
            "distributed_to": [t["target"] for t in dist],
            "outdated_count": sum(1 for t in dist if t["outdated"]),
            # Origine GitHub (lot E item 5) : None si le skill n'a pas été importé.
            "origin": _read_origin(sub),
        })
    return out


def _workspace_skill_roots() -> list[tuple[str, str, Path]]:
    """[(ws_id, libellé, <ws>/.claude/skills)] pour tous les workspaces du
    registre, lu une seule fois (ordre du registre conservé)."""
    roots: list[tuple[str, str, Path]] = []
    for ws in list_workspaces():
        ws_id = ws.get("id")
        if not ws_id:
            continue
        roots.append((ws_id, ws.get("name") or ws_id,
                      _ws_dir_from_entry(ws) / ".claude" / "skills"))
    return roots


def _subdir_names(root: Path, listing: dict[str, set[str]] | None) -> set[str] | None:
    """Noms (normcase) des sous-dossiers de `root`, mémorisés dans `listing`.

    None si `listing` n'est pas fourni (appel isolé : pas de pré-filtre).
    """
    if listing is None:
        return None
    key = str(root)
    names = listing.get(key)
    if names is None:
        names = set()
        try:
            with os.scandir(root) as it:
                for e in it:
                    try:
                        if e.is_dir():
                            names.add(os.path.normcase(e.name))
                    except OSError:
                        continue
        except OSError:
            pass
        listing[key] = names
    return names


def _distribution_for(name: str, src_hash: str,
                      ws_roots: list[tuple[str, str, Path]] | None = None,
                      listing: dict[str, set[str]] | None = None) -> list[dict]:
    """Liste les cibles où <name> est actuellement présent + flag outdated.

    `ws_roots` : résultat de `_workspace_skill_roots()` à réutiliser quand on
    boucle sur plusieurs skills (list_library) ; calculé ici sinon.
    `listing` : cache partagé des sous-dossiers de chaque racine (cf.
    `_subdir_names`) ; pré-filtre seulement, les contrôles d'existence
    d'origine restent appliqués aux candidats.
    """
    if ws_roots is None:
        ws_roots = _workspace_skill_roots()
    key = os.path.normcase(name)
    out: list[dict] = []
    g_root = CLAUDE_HOME / "skills"
    g = g_root / name
    g_names = _subdir_names(g_root, listing)
    if (g_names is None or key in g_names) and g.exists() and (g / "SKILL.md").exists():
        out.append({
            "target": "global",
            "label": "Global (~/.claude/skills/)",
            "outdated": _hash_dir(g) != src_hash,
        })
    for ws_id, ws_label, skills_root in ws_roots:
        ws_names = _subdir_names(skills_root, listing)
        if ws_names is not None and key not in ws_names:
            continue
        ws_skill = skills_root / name
        if ws_skill.exists() and (ws_skill / "SKILL.md").exists():
            out.append({
                "target": f"workspace:{ws_id}",
                "label": f"Workspace : {ws_label}",
                "outdated": _hash_dir(ws_skill) != src_hash,
            })
    return out


def get_distribution(name: str) -> tuple[int, dict]:
    if not safe_id(name):
        return 400, {"error": "nom invalide"}
    src = SKILLS_LIBRARY_DIR / name
    if not src.exists():
        return 404, {"error": "skill introuvable dans la bibliothèque"}
    src_hash = _hash_dir(src)
    return 200, {
        "name": name,
        "library_hash": src_hash,
        "targets": _distribution_for(name, src_hash),
    }


def distribute(name: str, targets: list[str]) -> tuple[int, dict]:
    """Set complet : copie/écrase là où c'est dans `targets`, retire là où ce
    n'est plus. C'est l'opération unique du modèle 'distribute'.
    """
    if not safe_id(name):
        return 400, {"error": "nom invalide"}
    src = SKILLS_LIBRARY_DIR / name
    if not src.exists():
        return 404, {"error": "skill introuvable dans la bibliothèque"}

    src_hash = _hash_dir(src)
    current_targets = {t["target"] for t in _distribution_for(name, src_hash)}
    desired = set(t for t in (targets or []) if isinstance(t, str))

    added: list[str] = []
    updated: list[str] = []
    removed: list[str] = []
    errors: list[dict] = []

    for t in desired:
        parent = _target_parent(t)
        if parent is None:
            errors.append({"target": t, "error": "cible invalide"})
            continue
        try:
            parent.mkdir(parents=True, exist_ok=True)
            dst = parent / name
            if dst.exists():
                _remove_dir_or_link(dst)
                shutil.copytree(src, dst)
                updated.append(t)
            else:
                shutil.copytree(src, dst)
                added.append(t)
        except OSError as e:
            errors.append({"target": t, "error": str(e)})

    for t in current_targets - desired:
        parent = _target_parent(t)
        if parent is None:
            continue
        dst = parent / name
        if dst.exists():
            try:
                _remove_dir_or_link(dst)
                removed.append(t)
            except OSError as e:
                errors.append({"target": t, "error": str(e)})

    return 200, {
        "ok": True, "added": added, "updated": updated,
        "removed": removed, "errors": errors,
    }


def create_library_skill(payload: dict) -> tuple[int, dict]:
    name = (payload.get("name") or "").strip()
    description = (payload.get("description") or "").strip()
    body = payload.get("body") or ""
    if not safe_id(name):
        return 400, {"error": "nom invalide (a-z, 0-9, -, _, max 40)"}
    if not description:
        return 400, {"error": "description requise"}
    _ensure_library()
    skill_dir = SKILLS_LIBRARY_DIR / name
    if skill_dir.exists():
        return 409, {"error": "skill déjà présent dans la bibliothèque"}
    skill_dir.mkdir()
    desc_escaped = description.replace('"', '\\"').replace("\n", " ")
    content = (
        f"---\nname: {name}\ndescription: \"{desc_escaped}\"\n---\n\n"
        f"# {name}\n\n{(body or '').strip() or '(instructions du skill)'}\n"
    )
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
    return 201, {"ok": True}


def delete_library_skill(name: str, also_remove_distributed: bool = False) -> tuple[int, dict]:
    if not safe_id(name):
        return 400, {"error": "nom invalide"}
    src = SKILLS_LIBRARY_DIR / name
    if not src.exists():
        return 404, {"error": "introuvable"}
    removed_targets: list[str] = []
    if also_remove_distributed:
        for t in _distribution_for(name, _hash_dir(src)):
            parent = _target_parent(t["target"])
            if parent:
                dst = parent / name
                if dst.exists():
                    try:
                        _remove_dir_or_link(dst)
                        removed_targets.append(t["target"])
                    except OSError:
                        pass
    _remove_dir_or_link(src)
    return 200, {"ok": True, "removed_distributed": removed_targets}


def get_library_skill_content(name: str) -> tuple[int, dict]:
    if not safe_id(name):
        return 400, {"error": "nom invalide"}
    f = SKILLS_LIBRARY_DIR / name / "SKILL.md"
    if not f.exists():
        return 404, {"error": "introuvable"}
    return 200, {"content": f.read_text(encoding="utf-8")}


def save_library_skill_content(name: str, content: str) -> tuple[int, dict]:
    if not safe_id(name):
        return 400, {"error": "nom invalide"}
    d = SKILLS_LIBRARY_DIR / name
    if not d.exists():
        return 404, {"error": "introuvable"}
    skill_md = d / "SKILL.md"
    # Backup auto avant écrasement (aligné sur save_skill_content dans
    # api_plugins.py : une édition qui casse le frontmatter rend le skill
    # invisible pour Claude, le .bak permet de revenir en arrière).
    backup = None
    if skill_md.exists():
        bak = skill_md.with_suffix(".md.bak")
        bak.write_text(skill_md.read_text(encoding="utf-8"), encoding="utf-8")
        backup = str(bak)
    skill_md.write_text(content or "", encoding="utf-8")
    return 200, {"ok": True, "backup": backup}


# ── Navigateur de fichiers de la bibliothèque ────────────────────────────────
# La bibliothèque expose l'arborescence complète de chaque skill (SKILL.md +
# fichiers annexes : README.md, references/*.md, examples/*…), pas seulement
# SKILL.md. On réutilise tel quel l'outillage fichiers de `api_plugins.py` via
# le scope « library » (cf. `_skill_dir` dans api_plugins.py) : sécurité
# path-traversal (`_SKILL_PATH_RE`, refus `..`, refus suppression de SKILL.md)
# et backup `.bak` à l'écriture sont déjà gérés là-bas. Aucune duplication.


def get_library_skill_detail(name: str) -> tuple[int, dict]:
    """Meta + arborescence des fichiers d'un skill de la bibliothèque."""
    from dashcore.api_plugins import get_skill_detail
    return get_skill_detail("library", name)


def get_library_skill_file(name: str, rel_path: str) -> tuple[int, dict]:
    """Contenu d'un fichier annexe d'un skill de la bibliothèque."""
    from dashcore.api_plugins import get_skill_file
    return get_skill_file("library", name, rel_path)


def write_library_skill_file(name: str, rel_path: str, content: str) -> tuple[int, dict]:
    """Écrit (avec backup `.bak`) un fichier annexe d'un skill de la bibliothèque."""
    from dashcore.api_plugins import write_skill_file
    return write_skill_file("library", name, rel_path, content)


def delete_library_skill_file(name: str, rel_path: str) -> tuple[int, dict]:
    """Supprime un fichier annexe d'un skill de la bibliothèque (refuse SKILL.md)."""
    from dashcore.api_plugins import delete_skill_file
    return delete_skill_file("library", name, rel_path)


def import_dir_into_library(src_dir: Path, requested_name: str | None = None,
                            overwrite: bool = False, origin: dict | None = None) -> tuple[int, dict]:
    """Copie un dossier (validé comme skill : contient SKILL.md) dans la bibliothèque."""
    if not src_dir.is_dir() or not (src_dir / "SKILL.md").exists():
        return 400, {"error": "dossier source invalide (SKILL.md manquant)"}
    name = (requested_name or src_dir.name).strip()
    if not safe_id(name):
        return 400, {"error": f"nom de skill invalide : {name}"}
    _ensure_library()
    dst = SKILLS_LIBRARY_DIR / name
    if dst.exists():
        if not overwrite:
            return 409, {"error": "skill déjà dans la bibliothèque", "name": name}
        _remove_dir_or_link(dst)
    shutil.copytree(src_dir, dst, ignore=shutil.ignore_patterns(".git", "node_modules"))
    if origin:
        import json as _json
        try:
            (dst / ".nebula-origin.json").write_text(_json.dumps(origin, indent=2), encoding="utf-8")
        except OSError:
            pass
    return 201, {"ok": True, "name": name}


def migrate_existing_to_library() -> dict:
    """Importe vers la bibliothèque tous les skills uniques (par nom) trouvés
    dans `~/.claude/skills/` et `<ws>/.claude/skills/`. Ne touche jamais aux
    copies existantes.
    """
    _ensure_library()
    seen = {p.name for p in SKILLS_LIBRARY_DIR.iterdir() if p.is_dir()}
    imported: list[dict] = []

    g = CLAUDE_HOME / "skills"
    if g.exists():
        for sub in g.iterdir():
            if sub.is_dir() and (sub / "SKILL.md").exists() and sub.name not in seen:
                try:
                    shutil.copytree(sub, SKILLS_LIBRARY_DIR / sub.name,
                                    ignore=shutil.ignore_patterns(".git", "node_modules"))
                    imported.append({"name": sub.name, "from": "global"})
                    seen.add(sub.name)
                except OSError:
                    pass

    for ws in list_workspaces():
        ws_id = ws.get("id")
        if not ws_id:
            continue
        ws_skills = _ws_dir_from_entry(ws) / ".claude" / "skills"
        if not ws_skills.exists():
            continue
        for sub in ws_skills.iterdir():
            if sub.is_dir() and (sub / "SKILL.md").exists() and sub.name not in seen:
                try:
                    shutil.copytree(sub, SKILLS_LIBRARY_DIR / sub.name,
                                    ignore=shutil.ignore_patterns(".git", "node_modules"))
                    imported.append({"name": sub.name, "from": f"workspace:{ws_id}"})
                    seen.add(sub.name)
                except OSError:
                    pass

    return {"ok": True, "imported": imported}
