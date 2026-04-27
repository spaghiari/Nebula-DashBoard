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
import shutil
from pathlib import Path

from dashcore.config import SKILLS_LIBRARY_DIR, CLAUDE_HOME
from dashcore.helpers import (
    _remove_dir_or_link, parse_skill_frontmatter, safe_id, resolve_ws_dir,
)
from dashcore.api_workspaces import list_workspaces


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


def _hash_dir(d: Path) -> str:
    """Hash récursif du contenu d'un dossier (ignore .nebula-origin.json)."""
    h = hashlib.sha256()
    if not d.exists():
        return ""
    for f in sorted(d.rglob("*")):
        if not f.is_file():
            continue
        if f.name == ".nebula-origin.json":
            continue
        try:
            h.update(f.relative_to(d).as_posix().encode("utf-8"))
            h.update(b"\0")
            h.update(f.read_bytes())
            h.update(b"\0")
        except OSError:
            continue
    return h.hexdigest()


def list_library() -> list[dict]:
    _ensure_library()
    out = []
    for sub in sorted(SKILLS_LIBRARY_DIR.iterdir()):
        if not sub.is_dir():
            continue
        skill_md = sub / "SKILL.md"
        if not skill_md.exists():
            continue
        meta = parse_skill_frontmatter(skill_md)
        dist = _distribution_for(sub.name, _hash_dir(sub))
        out.append({
            "id": sub.name,
            "name": meta.get("name") or sub.name,
            "description": meta.get("description") or "",
            "distributed_to": [t["target"] for t in dist],
            "outdated_count": sum(1 for t in dist if t["outdated"]),
        })
    return out


def _distribution_for(name: str, src_hash: str) -> list[dict]:
    """Liste les cibles où <name> est actuellement présent + flag outdated."""
    out: list[dict] = []
    g = CLAUDE_HOME / "skills" / name
    if g.exists() and (g / "SKILL.md").exists():
        out.append({
            "target": "global",
            "label": "Global (~/.claude/skills/)",
            "outdated": _hash_dir(g) != src_hash,
        })
    for ws in list_workspaces():
        ws_id = ws.get("id")
        if not ws_id:
            continue
        ws_skill = resolve_ws_dir(ws_id) / ".claude" / "skills" / name
        if ws_skill.exists() and (ws_skill / "SKILL.md").exists():
            out.append({
                "target": f"workspace:{ws_id}",
                "label": f"Workspace : {ws.get('name') or ws_id}",
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
    (d / "SKILL.md").write_text(content or "", encoding="utf-8")
    return 200, {"ok": True}


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
        ws_skills = resolve_ws_dir(ws_id) / ".claude" / "skills"
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
