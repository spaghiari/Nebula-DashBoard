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

import re
from pathlib import Path

from dashcore.config import TEMPLATES_DIR, _MUTATION_LOCK, log
from dashcore.helpers import (
    apply_template, is_text_file, read_json, read_json_strict, render_placeholders,
    resolve_ws_dir, safe_id, write_json,
)


OVERLAY_MARKER = ".nebula-overlay.json"

# Modes projet supportes (cf. memory/overview.md § Mode projet du template).
VALID_MODES = ("solo", "equipe", "equipe-hierarchique")
# Modes pour lesquels l'attribution d'auteur est obligatoire.
AUTHOR_MODES = ("equipe", "equipe-hierarchique")
VALID_DEPTHS = ("minimal", "complete")


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


def _normalize_options(opts: dict | None) -> dict:
    """Valide et complete les options de bootstrap de l'overlay.

    Options reconnues :
      - mode : 'solo' | 'equipe' | 'equipe-hierarchique' (defaut solo)
      - depth : 'minimal' | 'complete' (defaut deduit du mode :
        solo -> minimal, equipe* -> complete)
      - language : code langue libre (defaut 'fr')
      - author : identifiant auteur (utilise dans les seeds + overview)
    """
    opts = dict(opts or {})
    mode = opts.get("mode") or "solo"
    if mode not in VALID_MODES:
        mode = "solo"
    depth = opts.get("depth")
    if depth not in VALID_DEPTHS:
        depth = "minimal" if mode == "solo" else "complete"
    language = (opts.get("language") or "fr").strip() or "fr"
    author = (opts.get("author") or "").strip()
    return {
        "mode": mode,
        "depth": depth,
        "language": language,
        "author": author,
        "validate_author": mode in AUTHOR_MODES,
    }


def _mode_gated_skip(rel_posix: str, marker: dict, mode: str) -> bool:
    """Vrai si `rel_posix` est mode-gated et que `mode` n'est pas autorise."""
    for entry in (marker.get("mode_gated") or []):
        if entry.get("path") == rel_posix:
            return mode not in (entry.get("modes") or [])
    return False


def _depth_skip(rel_posix: str, marker: dict, depth: str) -> bool:
    """Vrai si `rel_posix` doit etre exclu en profondeur minimale.

    En profondeur minimale, seuls les chemins de `depth.minimal_keep`
    sont conserves ; tout le reste est exclu. En complete, rien n'est
    exclu a ce titre.
    """
    if depth != "minimal":
        return False
    keep = (marker.get("depth") or {}).get("minimal_keep") or []
    return rel_posix not in keep


def _is_seed_path(rel_posix: str, marker: dict) -> bool:
    """Vrai si le chemin est un fichier seed (jamais copie tel quel)."""
    for s in (marker.get("seeds") or []):
        if s.get("seed") == rel_posix:
            return True
    # Tout le dossier seeds/ est considere comme source, jamais livrable.
    return rel_posix.startswith(".claude/seeds/")


def _claude_md_config(marker: dict) -> dict:
    cfg = marker.get("claude_md") or {}
    return {
        "full_file": cfg.get("full_file") or "CLAUDE.md",
        "fragment_file": cfg.get("fragment_file") or "CLAUDE.self-improving.md",
        "begin_marker": cfg.get("begin_marker") or "<!-- BEGIN claude-self-improving -->",
        "end_marker": cfg.get("end_marker") or "<!-- END claude-self-improving -->",
    }


def _handle_claude_md(src_dir: Path, ws_dir: Path, marker: dict,
                      vars: dict, copied: list, skipped: list,
                      appended: list) -> None:
    """Traite CLAUDE.md specialement (cf. P1 du brief de refonte) :

    (a) pas de CLAUDE.md hote        -> ecrire le complet rendu
    (b) CLAUDE.md hote SANS marqueur -> appender le fragment rendu
    (c) marqueur deja present        -> skip (idempotent)
    """
    cfg = _claude_md_config(marker)
    full_src = src_dir / cfg["full_file"]
    frag_src = src_dir / cfg["fragment_file"]
    target = ws_dir / cfg["full_file"]
    begin = cfg["begin_marker"]

    if not target.exists():
        # Cas (a) : pas de CLAUDE.md hote -> ecrire le complet.
        if not full_src.exists():
            return
        content = render_placeholders(full_src.read_text(encoding="utf-8"), vars)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        copied.append(cfg["full_file"])
        return

    existing = target.read_text(encoding="utf-8")
    if begin in existing:
        # Cas (c) : deja appende -> idempotent, on ne touche pas.
        skipped.append({"path": cfg["full_file"],
                        "reason": "marker already present"})
        return

    # Cas (b) : CLAUDE.md hote present sans marqueur -> append du fragment.
    if not frag_src.exists():
        skipped.append({"path": cfg["full_file"],
                        "reason": "fragment source absent"})
        return
    fragment = render_placeholders(frag_src.read_text(encoding="utf-8"), vars)
    sep = "" if existing.endswith("\n\n") else ("\n" if existing.endswith("\n") else "\n\n")
    target.write_text(existing + sep + fragment, encoding="utf-8")
    appended.append(cfg["full_file"])


def _apply_seeds(src_dir: Path, ws_dir: Path, marker: dict, depth: str,
                 mode: str, vars: dict, seeded: list) -> None:
    """Appende les exemples seed dans les registres cibles.

    Profondeur complete uniquement. Idempotent : on n'appende un seed
    que si le registre cible vient d'etre copie ET ne contient pas deja
    le marqueur EXEMPLE seed (evite la duplication au re-apply).
    """
    if depth != "complete":
        return
    sentinel = "EXEMPLE seed"
    for s in (marker.get("seeds") or []):
        seed_rel = s.get("seed") or ""
        target_rel = s.get("target") or ""
        seed_mode = s.get("mode")
        if not seed_rel or not target_rel:
            continue
        if seed_mode and mode != seed_mode:
            continue
        seed_src = src_dir / seed_rel
        target = ws_dir / target_rel
        if not seed_src.exists() or not target.exists():
            continue
        existing = target.read_text(encoding="utf-8")
        if sentinel in existing:
            continue
        fragment = render_placeholders(seed_src.read_text(encoding="utf-8"), vars)
        sep = "" if existing.endswith("\n") else "\n"
        target.write_text(existing + sep + fragment, encoding="utf-8")
        seeded.append(target_rel)


def _write_settings_local(ws_dir: Path, options: dict, written: list) -> None:
    """Ecrit/patche .claude/settings.local.json avec validate_author.

    En mode solo, pose `validate_author: false` pour ne pas bloquer les
    commits sans champ auteur (cf. P3 du brief). Ne pas ecraser une
    valeur deja posee par l'utilisateur : patch partiel.
    """
    path = ws_dir / ".claude" / "settings.local.json"
    data = read_json_strict(path, {})
    if not isinstance(data, dict):
        data = {}
    want = options["validate_author"]
    if data.get("validate_author") == want:
        return
    data["validate_author"] = want
    write_json(path, data)
    written.append(".claude/settings.local.json")


def _prefill_overview(ws_dir: Path, options: dict, prefilled: list) -> None:
    """Pre-coche le mode et la langue dans memory/overview.md (cases [ ]).

    Best-effort : si le fichier ou les libelles attendus sont absents,
    ne fait rien. Idempotent : ne re-coche pas une case deja cochee.
    """
    path = ws_dir / ".claude" / "memory" / "overview.md"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    original = text

    # Libelles de mode dans overview.md (du template).
    mode_labels = {
        "solo": "**Solo**",
        "equipe": "**Équipe sans hiérarchie**",
        "equipe-hierarchique": "**Équipe avec hiérarchie**",
    }
    label = mode_labels.get(options["mode"])
    if label and f"- [ ] {label}" in text:
        text = text.replace(f"- [ ] {label}", f"- [x] {label}", 1)

    # Langue : cocher Français / Anglais selon le code; sinon laisser.
    lang_labels = {
        "fr": "**Français**",
        "en": "**Anglais**",
    }
    lbl = lang_labels.get(options["language"].lower())
    if lbl and f"- [ ] {lbl}" in text:
        text = text.replace(f"- [ ] {lbl}", f"- [x] {lbl}", 1)

    if text != original:
        path.write_text(text, encoding="utf-8")
        prefilled.append(".claude/memory/overview.md")


# Capture les chemins de hooks references par settings.json, du type
# `python "${CLAUDE_PROJECT_DIR}/.claude/hooks/foo.py"`. Le [\\/]+ apres la
# variable consomme le(s) separateur(s) pour que le groupe capture soit
# RELATIF (sinon Path(ws_dir) / "/.claude/..." se reancrerait a la racine).
_HOOK_REF_RE = re.compile(r"\$\{CLAUDE_PROJECT_DIR\}[\\/]+([^\"']+?\.py)")


def _missing_hook_refs(ws_dir: Path) -> list[str]:
    """Liste les hooks reference par `.claude/settings.json` mais absents du
    workspace. Garde fail-fast post-generation : un settings.json qui pointe
    vers un hook inexistant deadlocke Claude Code (exit 2 d'un PreToolUse =
    refus bloquant sur Bash/Edit/Write, le workspace devient inutilisable).
    Retourne la liste dedupliquee (ordre preserve) des chemins manquants."""
    settings = ws_dir / ".claude" / "settings.json"
    if not settings.exists():
        return []
    try:
        text = settings.read_text(encoding="utf-8")
    except OSError:
        return []
    seen: set[str] = set()
    missing: list[str] = []
    for raw in _HOOK_REF_RE.findall(text):
        rel = raw.replace("\\", "/")
        if not (ws_dir / rel).exists() and rel not in seen:
            seen.add(rel)
            missing.append(rel)
    return missing


def apply_overlay(ws_id: str, overlay_id: str, vars: dict,
                  options: dict | None = None) -> tuple[int, dict]:
    """Applique l'overlay `overlay_id` sur le workspace `ws_id`.

    Idempotent : pour chaque fichier de l'overlay, copie uniquement s'il
    est absent du workspace. CLAUDE.md est traite specialement (fragment
    appende via marqueur, cf. _handle_claude_md). Les placeholders connus
    sont substitues comme a la creation normale.

    `options` (cf. _normalize_options) pilote le mode projet, la
    profondeur d'install, la langue et l'auteur. Le mode-gating et la
    profondeur sont declares dans `.nebula-overlay.json` (maps
    `mode_gated` / `depth` / `seeds`), jamais en dur ici.

    Retourne (status, payload) ou payload = {
        "ok": bool, "overlay_id": str,
        "copied": [rel, ...], "appended": [rel, ...],
        "seeded": [rel, ...], "skipped": [{"path","reason"}, ...],
        "options": {...},
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

    # Sérialise l'application sur le workspace (cf. review #10) : serveur
    # ThreadingHTTPServer + read-modify-write multi-fichiers (CLAUDE.md,
    # settings.local.json) -> deux applications concurrentes entrelaceraient
    # leurs écritures. _MUTATION_LOCK est réentrant (write_json le reprend
    # sans deadlock).
    with _MUTATION_LOCK:
        return _apply_overlay_body(ws_id, overlay_id, ws_dir, src_dir, vars, options)


def _apply_overlay_body(ws_id: str, overlay_id: str, ws_dir, src_dir,
                        vars: dict, options: dict | None) -> tuple[int, dict]:
    opts = _normalize_options(options)
    marker = read_json(src_dir / OVERLAY_MARKER, {}) or {}
    cfg = _claude_md_config(marker)

    # Enrichir les vars de substitution avec les options de bootstrap.
    vars = dict(vars or {})
    vars.setdefault("author", opts["author"] or vars.get("name") or "nebula")
    vars.setdefault("language", opts["language"])

    copied: list[str] = []
    appended: list[str] = []
    seeded: list[str] = []
    skipped: list[dict] = []

    # 1. CLAUDE.md : traitement special (fragment / complet / skip).
    _handle_claude_md(src_dir, ws_dir, marker, vars, copied, skipped, appended)

    # 2. Copie standard des autres fichiers (idempotente + gating).
    claude_md_names = {cfg["full_file"], cfg["fragment_file"]}
    for entry in src_dir.rglob("*"):
        rel = entry.relative_to(src_dir)
        rel_posix = rel.as_posix()
        if rel.name == OVERLAY_MARKER:
            continue
        if entry.is_dir():
            continue
        # CLAUDE.md (complet + fragment) deja gere a l'etape 1.
        if rel_posix in claude_md_names:
            continue
        # Les seeds ne sont jamais copies comme fichiers autonomes.
        if _is_seed_path(rel_posix, marker):
            continue
        # Mode-gating declaratif.
        if _mode_gated_skip(rel_posix, marker, opts["mode"]):
            skipped.append({"path": rel_posix,
                            "reason": f"mode-gated (hors mode {opts['mode']})"})
            continue
        # Profondeur d'install.
        if _depth_skip(rel_posix, marker, opts["depth"]):
            skipped.append({"path": rel_posix, "reason": "profondeur minimale"})
            continue

        target = ws_dir / rel
        if target.exists():
            skipped.append({"path": rel_posix, "reason": "already present"})
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            if is_text_file(entry):
                content = render_placeholders(entry.read_text(encoding="utf-8"), vars)
                target.write_text(content, encoding="utf-8")
            else:
                import shutil
                shutil.copy2(entry, target)
            copied.append(rel_posix)
        except OSError as e:
            log.warning("overlay copy failed %s -> %s : %s", entry, target, e)
            skipped.append({"path": rel_posix, "reason": f"copy error: {e}"})

    # 3. Seeds (profondeur complete uniquement, idempotent).
    _apply_seeds(src_dir, ws_dir, marker, opts["depth"], opts["mode"], vars, seeded)

    # 4. settings.local.json (validate_author selon le mode).
    written: list[str] = []
    _write_settings_local(ws_dir, opts, written)
    copied.extend(w for w in written if w not in copied)

    # 5. Pre-remplissage du mode + langue dans overview.md.
    prefilled: list[str] = []
    _prefill_overview(ws_dir, opts, prefilled)

    # 6. Garde fail-fast : refuser de livrer un workspace ou settings.json
    #    reference un hook absent (sinon deadlock Claude Code, cf.
    #    _missing_hook_refs). Verrouille le couplage settings <-> hooks que
    #    le mode-gating / la profondeur d'install pourraient rompre.
    missing_hooks = _missing_hook_refs(ws_dir)
    if missing_hooks:
        log.error("overlay %s on %s : settings.json reference %d hook(s) "
                  "absent(s), generation refusee : %s",
                  overlay_id, ws_id, len(missing_hooks), missing_hooks)
        return 500, {
            "ok": False,
            "overlay_id": overlay_id,
            "error": ("Génération incohérente : .claude/settings.json "
                      "référence des hooks absents du workspace ("
                      + ", ".join(missing_hooks)
                      + "). Workspace laissé en l'état — corriger l'overlay "
                        "puis réappliquer."),
            "missing_hooks": missing_hooks,
            "copied": copied,
            "appended": appended,
            "seeded": seeded,
            "prefilled": prefilled,
            "skipped": skipped,
            "options": opts,
        }

    log.info("overlay %s applied on %s (mode=%s depth=%s) : "
             "%d copied, %d appended, %d seeded, %d skipped",
             overlay_id, ws_id, opts["mode"], opts["depth"],
             len(copied), len(appended), len(seeded), len(skipped))
    return 200, {
        "ok": True,
        "overlay_id": overlay_id,
        "copied": copied,
        "appended": appended,
        "seeded": seeded,
        "prefilled": prefilled,
        "skipped": skipped,
        "options": opts,
    }
