"""Overlays Nebula -- paquets de fichiers appliques par-dessus un template.

Un overlay vit dans `templates/<overlay_id>/` exactement comme un template
normal, mais est marque par un fichier `.nebula-overlay.json` a la racine
(en lieu et place de `.template.json`). Le marker decrit :

    {
        "id": "claude-self-improving",
        "label": "Auto-amelioration de Claude",
        "description": "...",
        "emoji": "...",
        "signature_file": ".claude/memory/MEMORY.md"
    }

Le `signature_file` (optionnel) sert a la detection "deja active" : si ce
fichier existe dans le workspace cible, on considere l'overlay deja
applique (afficher "Active" cote UI, masquer le bouton, etc.).

Contraintes :
  - Idempotent : copie uniquement les fichiers absents (jamais d'ecrasement
    d'une version utilisateur).
  - Stdlib only (cohereent reste du projet).
  - Garde-fou CLAUDE.md : on ne le copie JAMAIS depuis un overlay si le
    workspace en a deja un, meme s'il est legitimement different. Trace
    en `skipped` avec raison `"would overwrite user file"`.
"""
from __future__ import annotations

from pathlib import Path

from dashcore.config import TEMPLATES_DIR, log
from dashcore.helpers import (
    apply_template, is_text_file, read_json, render_placeholders,
    resolve_ws_dir, safe_id,
)


OVERLAY_MARKER = ".nebula-overlay.json"


def is_overlay_dir(d: Path) -> bool:
    """Vrai si `d` est un dossier d'overlay (contient le marker)."""
    return d.is_dir() and (d / OVERLAY_MARKER).is_file()


def list_overlays() -> list[dict]:
    """Liste les overlays disponibles. Format identique a list_templates
    pour les champs communs (id, label, description, emoji, file_count)."""
    if not TEMPLATES_DIR.exists():
        return []
    out: list[dict] = []
    for d in sorted(TEMPLATES_DIR.iterdir()):
        if not is_overlay_dir(d):
            continue
        meta = read_json(d / OVERLAY_MARKER, {}) or {}
        files: list[str] = []
        for entry in d.rglob("*"):
            if entry.is_file() and entry.name != OVERLAY_MARKER:
                files.append(str(entry.relative_to(d)).replace("\\", "/"))
        out.append({
            "id": meta.get("id") or d.name,
            "dir_id": d.name,
            "label": meta.get("label") or d.name,
            "description": meta.get("description") or "",
            "emoji": meta.get("emoji") or "🧩",
            "signature_file": meta.get("signature_file") or "",
            "files": files,
            "file_count": len(files),
        })
    return out


def get_overlay(overlay_id: str) -> dict | None:
    """Retourne le dict d'overlay correspondant a `overlay_id` ou None."""
    if not safe_id(overlay_id):
        return None
    for ov in list_overlays():
        if ov["id"] == overlay_id or ov["dir_id"] == overlay_id:
            return ov
    return None


def overlay_is_active(ws_dir: Path, overlay: dict) -> bool:
    """Heuristique 'overlay deja applique' : presence du signature_file
    dans le workspace. Si pas de signature_file declaree, retombe sur
    'au moins un fichier de l'overlay est present'."""
    sig = overlay.get("signature_file") or ""
    if sig:
        return (ws_dir / sig).exists()
    # Fallback : au moins un fichier de l'overlay est present.
    for rel in overlay.get("files", []):
        if (ws_dir / rel).exists():
            return True
    return False


def apply_overlay(ws_id: str, overlay_id: str, vars: dict) -> tuple[int, dict]:
    """Applique l'overlay `overlay_id` sur le workspace `ws_id`.

    Idempotent : pour chaque fichier de l'overlay, copie uniquement s'il
    est absent du workspace. CLAUDE.md n'est jamais ecrase non plus.
    Les placeholders connus sont substitues comme a la creation normale.

    Retourne (status, payload) ou payload = {
        "ok": bool,
        "overlay_id": str,
        "copied": [rel_path, ...],
        "skipped": [{"path": rel_path, "reason": "..."}, ...]
    }.
    """
    if not safe_id(ws_id):
        return 400, {"error": "ws_id invalide"}
    if not safe_id(overlay_id):
        return 400, {"error": "overlay_id invalide"}

    overlay = get_overlay(overlay_id)
    if not overlay:
        return 404, {"error": f"Overlay introuvable : {overlay_id}"}

    ws_dir = resolve_ws_dir(ws_id)
    if not ws_dir.exists():
        return 404, {"error": "workspace absent sur disque"}

    src_dir = TEMPLATES_DIR / overlay["dir_id"]
    if not src_dir.exists():
        return 404, {"error": f"Dossier d'overlay introuvable : {overlay['dir_id']}"}

    copied: list[str] = []
    skipped: list[dict] = []

    for entry in src_dir.rglob("*"):
        rel = entry.relative_to(src_dir)
        if rel.name == OVERLAY_MARKER:
            continue
        if entry.is_dir():
            (ws_dir / rel).mkdir(parents=True, exist_ok=True)
            continue
        target = ws_dir / rel
        rel_posix = rel.as_posix()
        # CLAUDE.md = jamais ecrase (regle explicite du brief).
        # Les autres fichiers : skip si deja present (idempotence).
        if target.exists():
            if target.name == "CLAUDE.md":
                skipped.append({"path": rel_posix, "reason": "would overwrite user file"})
            else:
                skipped.append({"path": rel_posix, "reason": "already present"})
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            if is_text_file(entry):
                content = entry.read_text(encoding="utf-8")
                content = render_placeholders(content, vars)
                target.write_text(content, encoding="utf-8")
            else:
                import shutil
                shutil.copy2(entry, target)
            copied.append(rel_posix)
        except OSError as e:
            log.warning("overlay copy failed %s -> %s : %s", entry, target, e)
            skipped.append({"path": rel_posix, "reason": f"copy error: {e}"})

    log.info("overlay %s applied on %s : %d copied, %d skipped",
             overlay_id, ws_id, len(copied), len(skipped))
    return 200, {
        "ok": True,
        "overlay_id": overlay_id,
        "copied": copied,
        "skipped": skipped,
    }
