"""Overlays Nebula -- paquets de fichiers appliques par-dessus un template.

Un overlay vit dans `templates/<overlay_id>/` exactement comme un template
normal, mais est marque par un fichier `.nebula-overlay.json` a la racine
(en lieu et place de `.template.json`). Le marker decrit :

    {
        "id": "claude-self-improving",
        "label": "Auto-amelioration de Claude",
        "description": "...",
        "emoji": "...",
        "signature_file": ".claude/memory/MEMORY.md",
        "requires": ["autre-overlay"],          # optionnel : prérequis actifs
        "features": [{"icon","title","text"}], # optionnel : rendu par l'UI
        "after_apply": "...",                   # optionnel : phrase post-activation
        "settings_patch": {...},                # optionnel : fusionné dans settings.json
        "generators": ["team_agents"]           # optionnel : post-application
    }

Le `signature_file` (optionnel) sert a la detection "deja active" : si ce
fichier existe dans le workspace cible, on considere l'overlay deja
applique (afficher "Active" cote UI, masquer le bouton, etc.).

`requires` : apply_overlay refuse (409) si un prérequis n'est pas actif ;
create_workspace ordonne les overlays cochés par dépendances
(order_by_requires). `settings_patch` : fusion récursive dans le
`.claude/settings.json` du workspace, hooks fusionnés par matcher sans
doublon de command (idempotent). `generators` : hooks de post-application
(`team_agents` -> dashcore/api_team.generate_agents).

`managed` (optionnel) : globs relatifs (`*`, `?`, `**`) des fichiers GÉRÉS
par le module (hooks, commandes livrées...). À la ré-application, un fichier
géré présent mais différent du rendu de la nouvelle version est remplacé,
après sauvegarde `.bak` horodatée (cf. _update_managed_file). Le bloc
`BEGIN/END` du module dans `CLAUDE.md` est lui aussi remplacé par le
fragment rendu. Tout le reste n'est jamais écrasé.

Contraintes :
  - Idempotent : copie uniquement les fichiers absents (jamais d'ecrasement
    d'une version utilisateur), sauf fichiers gérés (`managed`) qui
    diffèrent du rendu ; une seconde application ne change plus rien.
  - Stdlib only (cohereent reste du projet).
  - Garde-fou CLAUDE.md : on ne le copie JAMAIS depuis un overlay si le
    workspace en a deja un, meme s'il est legitimement different. Trace
    en `skipped` avec raison `"would overwrite user file"`.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from dashcore.config import TEMPLATES_DIR, _MUTATION_LOCK, log
from dashcore.helpers import (
    CorruptJsonError, apply_template, is_text_file, read_json, read_json_strict,
    render_placeholders, resolve_ws_dir, safe_id, write_json,
)


OVERLAY_MARKER = ".nebula-overlay.json"

# Modes projet supportes (cf. memory/overview.md § Mode projet du template).
VALID_MODES = ("solo", "equipe", "equipe-hierarchique")
# Modes pour lesquels l'attribution d'auteur est obligatoire.
AUTHOR_MODES = ("equipe", "equipe-hierarchique")
VALID_DEPTHS = ("minimal", "complete")
# Artefacts de build a ne jamais lister ni copier (un overlay qui embarque
# des hooks Python genere des __pycache__ des qu'on les execute sur place).
_JUNK_DIRS = {"__pycache__"}
_JUNK_SUFFIXES = {".pyc", ".pyo"}


def _is_junk(rel: Path) -> bool:
    """Vrai si `rel` (relatif au dossier de l'overlay) est un artefact de build."""
    return rel.suffix in _JUNK_SUFFIXES or any(part in _JUNK_DIRS for part in rel.parts)


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
            if not entry.is_file() or entry.name == OVERLAY_MARKER:
                continue
            rel = entry.relative_to(d)
            if not _is_junk(rel) and not _is_no_copy(rel.as_posix(), meta):
                files.append(rel.as_posix())
        generators = [g for g in (meta.get("generators") or []) if isinstance(g, str)]
        managed = _managed_globs(meta)
        out.append({
            "id": meta.get("id") or d.name,
            "dir_id": d.name,
            "label": meta.get("label") or d.name,
            "description": meta.get("description") or "",
            "emoji": meta.get("emoji") or "🧩",
            "signature_file": meta.get("signature_file") or "",
            "files": files,
            "file_count": len(files),
            # Déclaratif (rendu par l'UI, plus rien de codé en dur par overlay).
            "features": [f for f in (meta.get("features") or []) if isinstance(f, dict)],
            "after_apply": meta.get("after_apply") or "",
            "requires": [r for r in (meta.get("requires") or []) if isinstance(r, str) and safe_id(r)],
            "generators": generators,
            "has_settings_patch": isinstance(meta.get("settings_patch"), dict),
            # Globs des fichiers que « Ré-appliquer » met à jour (UI : modale).
            "managed": managed,
            # Vrai si Ré-appliquer remplace aussi le bloc du module dans CLAUDE.md.
            "refresh_claude_md": _claude_md_config(meta)["refresh_block"],
            # Vrai si la modale doit proposer mode / langue / profondeur.
            "bootstrap_options": _uses_bootstrap_options(meta),
            "agents": _overlay_agents(d) if "team_agents" in generators else [],
        })
    return out


def _uses_bootstrap_options(marker: dict) -> bool:
    """Vrai si l'overlay exploite les options de bootstrap (mode / profondeur /
    seeds). Sinon settings.local.json et overview.md ne sont pas touchés :
    un second overlay ne doit pas réécrire le choix de mode du premier."""
    return any(marker.get(k) for k in ("mode_gated", "depth", "seeds"))


def _overlay_agents(d: Path) -> list[dict]:
    """Agents du manifeste `.claude/team.json` livré par l'overlay (pour la
    section « Modèles par rôle » de la modale d'activation)."""
    from dashcore.api_team import load_manifest, manifest_agents
    manifest = load_manifest(d)
    if not manifest:
        return []
    default = (manifest.get("models") or {}).get("default") or "sonnet"
    return [{"id": a["id"], "role": a.get("role") or "", "model": a.get("model") or default}
            for a in manifest_agents(manifest)]


def overlays_usage() -> dict[str, list[str]]:
    """{overlay_id: [ws_id où il est actif]} pour tous les overlays (section
    « Modules » de la page Templates). Registre lu une fois ; un `exists()`
    par couple workspace x overlay."""
    from dashcore.workspace_io import list_workspaces, _ws_dir_from_entry
    overlays = list_overlays()
    out: dict[str, list[str]] = {ov["id"]: [] for ov in overlays}
    if not overlays:
        return out
    for w in list_workspaces():
        ws_id = w.get("id")
        if not ws_id:
            continue
        try:
            ws_dir = _ws_dir_from_entry(w)
            if not ws_dir.is_dir():
                continue
            for ov in overlays:
                if overlay_is_active(ws_dir, ov):
                    out[ov["id"]].append(ws_id)
        except OSError:
            continue
    return out


def order_by_requires(ids: list[str]) -> tuple[list[str], dict[str, str]]:
    """Ordonne une sélection d'overlays pour que chaque prérequis passe avant
    l'overlay qui le requiert (création de workspace). Retourne (ordre,
    erreurs) ; un overlay dont un prérequis n'est pas dans la sélection est
    retiré de l'ordre et expliqué dans `erreurs[id]`. Les ids inconnus sont
    laissés dans l'ordre (apply_overlay rendra son 404)."""
    known = {ov["id"]: ov for ov in list_overlays()}
    errors: dict[str, str] = {}
    selected = [i for i in ids if isinstance(i, str)]
    sel_set = set(selected)
    for ov_id in selected:
        ov = known.get(ov_id)
        if not ov:
            continue
        missing = [r for r in ov["requires"] if r not in sel_set]
        if missing:
            labels = ", ".join(f"« {known[r]['label']} »" if r in known else f"« {r} »"
                               for r in missing)
            errors[ov_id] = (f"requiert {labels} : coche aussi ce module (ou active-le "
                             "d'abord sur le workspace)")
    ordered: list[str] = []
    pending = [i for i in selected if i not in errors]
    # Tri topologique simple (quelques overlays) : on passe un overlay quand
    # tous ses prérequis sélectionnés sont déjà passés.
    while pending:
        progressed = False
        for ov_id in list(pending):
            reqs = known[ov_id]["requires"] if ov_id in known else []
            if all(r in ordered or r not in sel_set for r in reqs):
                ordered.append(ov_id)
                pending.remove(ov_id)
                progressed = True
        if not progressed:  # cycle de prérequis : ordre soumis pour le reste
            ordered.extend(pending)
            break
    return ordered, errors


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
    # Options des générateurs (claude-team : modèle par rôle, régénération),
    # validées par api_team (valeurs invalides ignorées).
    from dashcore.api_team import normalize_team_options
    team = normalize_team_options(opts)
    return {
        "mode": mode,
        "depth": depth,
        "language": language,
        "author": author,
        "validate_author": mode in AUTHOR_MODES,
        "models": team["models"],
        "default_model": team["default_model"],
        "regenerate": team["regenerate"],
        "prefix": team["prefix"],
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
    # Overlay sans profondeur déclarée (une seule profondeur, ex. claude-team) :
    # rien n'est exclu, sinon un `minimal_keep` vide exclurait tout.
    if not isinstance(marker.get("depth"), dict):
        return False
    keep = marker["depth"].get("minimal_keep") or []
    return rel_posix not in keep


def _is_no_copy(rel_posix: str, marker: dict) -> bool:
    """Vrai si le chemin est declare `no_copy` dans le marker : il documente
    l'overlay dans le catalogue `templates/` (README du module...) mais n'est
    jamais copie dans un workspace ni compte dans `file_count`. Absence de
    la cle = aucun filtre (cf. pitfall « valeur par defaut vide »)."""
    return rel_posix in {p for p in (marker.get("no_copy") or []) if isinstance(p, str)}


def _is_seed_path(rel_posix: str, marker: dict) -> bool:
    """Vrai si le chemin est un fichier seed (jamais copie tel quel)."""
    for s in (marker.get("seeds") or []):
        if s.get("seed") == rel_posix:
            return True
    # Tout le dossier seeds/ est considere comme source, jamais livrable.
    return rel_posix.startswith(".claude/seeds/")


def _managed_globs(marker: dict) -> list[str]:
    """Globs `managed` valides du marker (relatifs, sans `..`, séparateur `/`).
    Absence de la clé = aucun fichier géré (comportement historique : copie
    si absent seulement), cf. pitfall « valeur par défaut vide »."""
    out: list[str] = []
    for g in marker.get("managed") or []:
        if not isinstance(g, str) or not g.strip():
            continue
        g = g.strip()
        if "\\" in g or ":" in g or g.startswith("/") or ".." in g.split("/"):
            continue
        out.append(g)
    return out


def _glob_match(parts: list[str], pats: list[str]) -> bool:
    """Correspondance segment par segment : `*` / `?` / `[...]` ne traversent
    jamais un `/` ; `**` couvre zéro ou plusieurs segments."""
    from fnmatch import fnmatchcase
    if not pats:
        return not parts
    if pats[0] == "**":
        return any(_glob_match(parts[i:], pats[1:]) for i in range(len(parts) + 1))
    return bool(parts) and fnmatchcase(parts[0], pats[0]) and _glob_match(parts[1:], pats[1:])


def _is_managed(rel_posix: str, marker: dict) -> bool:
    """Vrai si le chemin (relatif à l'overlay) est déclaré géré (`managed`)."""
    parts = rel_posix.split("/")
    return any(_glob_match(parts, g.split("/")) for g in _managed_globs(marker))


def _norm_eol(text: str) -> str:
    """Fins de ligne unifiées en LF : CRLF (autocrlf Windows) vs LF n'est pas
    une modification du contenu."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _inside_workspace(ws_root: Path, target: Path) -> bool:
    """Vrai si `target` (lien non suivi) n'est pas un lien symbolique et se
    résout sous `ws_root` (déjà résolu). Garde de toute RÉÉCRITURE : on ne
    suit jamais un lien qui sortirait du workspace."""
    try:
        if target.is_symlink():
            return False
        target.resolve().relative_to(ws_root)
        return True
    except (OSError, ValueError):
        return False


def _backup_path(target: Path) -> Path:
    """`<nom>.<AAAAMMJJ-HHMMSS>.bak` à côté de `target`, suffixé `-2`, `-3`...
    si ce nom existe déjà : une sauvegarde n'est jamais écrasée."""
    import datetime as _dt
    import os
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    n = 1
    while True:
        name = f"{target.name}.{stamp}.bak" if n == 1 else f"{target.name}.{stamp}-{n}.bak"
        cand = target.with_name(name)
        if not os.path.lexists(cand):
            return cand
        n += 1


def _write_backup(target: Path, ws_dir: Path, backups: list) -> bool:
    """Copie `target` en `.bak` (cf. _backup_path). Retourne False si la
    sauvegarde échoue : l'appelant n'écrit alors rien."""
    import shutil
    bak = _backup_path(target)
    try:
        shutil.copy2(target, bak)
    except OSError as e:
        log.warning("overlay : sauvegarde impossible %s -> %s : %s", target, bak, e)
        return False
    backups.append(bak.relative_to(ws_dir).as_posix())
    return True


def _update_managed_file(entry: Path, target: Path, rel_posix: str, ws_dir: Path,
                         ws_root: Path, vars: dict, updated: list,
                         backups: list, skipped: list) -> None:
    """Fichier géré déjà présent : remplacé par le rendu de la nouvelle
    version s'il en diffère (fins de ligne ignorées), après sauvegarde
    `.bak`. Identique : rien (ni écriture, ni `.bak`)."""
    if not _inside_workspace(ws_root, target):
        skipped.append({"path": rel_posix, "reason": "lien hors du workspace, non mis à jour"})
        return
    try:
        if is_text_file(entry):
            new_text = render_placeholders(entry.read_text(encoding="utf-8"), vars)
            try:
                same = _norm_eol(target.read_bytes().decode("utf-8")) == _norm_eol(new_text)
            except UnicodeDecodeError:
                same = False
            new_bytes = None
        else:
            new_text = None
            new_bytes = entry.read_bytes()
            same = target.read_bytes() == new_bytes
    except OSError as e:
        skipped.append({"path": rel_posix, "reason": f"read error: {e}"})
        return
    if same:
        skipped.append({"path": rel_posix, "reason": "already up to date"})
        return
    if not _write_backup(target, ws_dir, backups):
        skipped.append({"path": rel_posix, "reason": "sauvegarde .bak impossible, non mis à jour"})
        return
    try:
        if new_text is not None:
            target.write_text(new_text, encoding="utf-8")
        else:
            target.write_bytes(new_bytes)
        updated.append(rel_posix)
    except OSError as e:
        log.warning("overlay update failed %s -> %s : %s", entry, target, e)
        skipped.append({"path": rel_posix, "reason": f"update error: {e}"})


def _claude_md_config(marker: dict) -> dict:
    cfg = marker.get("claude_md") or {}
    return {
        "full_file": cfg.get("full_file") or "CLAUDE.md",
        "fragment_file": cfg.get("fragment_file") or "CLAUDE.self-improving.md",
        "begin_marker": cfg.get("begin_marker") or "<!-- BEGIN claude-self-improving -->",
        "end_marker": cfg.get("end_marker") or "<!-- END claude-self-improving -->",
        # Opt-in : ré-appliquer remplace le bloc seulement si le module le
        # déclare. Un bloc que l'utilisateur ou le bootstrap complète (pièges
        # du projet, langue, sommaire mémoire de claude-self-improving) ne doit
        # pas être réinitialisé à chaque ré-application.
        "refresh_block": cfg.get("refresh_block") is True,
    }


def _replace_claude_md_block(existing: str, frag_src: Path, target: Path, ws_dir: Path,
                             cfg: dict, overlay_id: str, vars: dict, updated: list,
                             backups: list, skipped: list) -> None:
    """Cas (c) : bloc `begin..end` déjà présent -> remplacé par le bloc du
    fragment rendu de la version courante, le reste du fichier intact.
    Identique (fins de ligne ignorées) : rien. Sans fragment source (module
    en CLAUDE.md complet seulement), bloc incomplet ou cible hors workspace :
    rien n'est touché."""
    name, begin, end = cfg["full_file"], cfg["begin_marker"], cfg["end_marker"]
    if not frag_src.exists():
        skipped.append({"path": name, "reason": "marker already present"})
        return
    fragment = _norm_eol(render_placeholders(frag_src.read_text(encoding="utf-8"), vars))
    fb, fe = fragment.find(begin), fragment.find(end)
    if fb < 0 or fe < fb:
        skipped.append({"path": name, "reason": "fragment source sans marqueurs"})
        return
    new_block = fragment[fb:fe + len(end)]
    text = _norm_eol(existing)
    b = text.find(begin)
    e = text.find(end, b)
    if e < 0:
        skipped.append({"path": name, "reason": "bloc du module incomplet (marqueur de fin absent)"})
        return
    if text[b:e + len(end)] == new_block:
        skipped.append({"path": name, "reason": "marker already present"})
        return
    if not _inside_workspace(ws_dir.resolve(), target):
        skipped.append({"path": name, "reason": "lien hors du workspace, non mis à jour"})
        return
    if not _write_backup(target, ws_dir, backups):
        skipped.append({"path": name, "reason": "sauvegarde .bak impossible, non mis à jour"})
        return
    try:
        target.write_text(text[:b] + new_block + text[e + len(end):], encoding="utf-8")
    except OSError as err:
        # Le .bak est déjà posé : rien de perdu, la ré-application continue.
        skipped.append({"path": name, "reason": f"écriture du bloc impossible : {err}"})
        return
    updated.append(f"{name} (bloc {overlay_id})")


def _handle_claude_md(src_dir: Path, ws_dir: Path, marker: dict,
                      vars: dict, copied: list, skipped: list,
                      appended: list, updated: list | None = None,
                      backups: list | None = None, overlay_id: str = "") -> None:
    """Traite CLAUDE.md specialement (cf. P1 du brief de refonte) :

    (a) pas de CLAUDE.md hote        -> ecrire le complet rendu
    (b) CLAUDE.md hote SANS marqueur -> appender le fragment rendu
    (c) marqueur deja present        -> bloc remplace par le fragment rendu
        s'il differe (sauvegarde .bak), sinon rien (idempotent)
    """
    cfg = _claude_md_config(marker)
    full_src = src_dir / cfg["full_file"]
    frag_src = src_dir / cfg["fragment_file"]
    target = ws_dir / cfg["full_file"]
    begin = cfg["begin_marker"]
    updated = [] if updated is None else updated
    backups = [] if backups is None else backups

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
    if begin in existing and not cfg["refresh_block"]:
        # Cas (c) sans opt-in : bloc laissé tel quel (contenu complété par le projet).
        skipped.append({"path": cfg["full_file"], "reason": "marker already present"})
        return
    if begin in existing:
        # Cas (c) avec `refresh_block` : bloc mis a jour s'il differe.
        _replace_claude_md_block(existing, frag_src, target, ws_dir, cfg,
                                 overlay_id or marker.get("id") or "module",
                                 vars, updated, backups, skipped)
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


def _merge_hook_lists(existing: list, patch: list) -> bool:
    """Fusionne une liste d'entrées de hooks (`[{matcher, hooks:[{command}]}]`)
    par `matcher`, sans doublon de `command`. Retourne True si modifiée.

    Un groupe SANS `matcher` (événements qui n'en ont pas : UserPromptSubmit,
    Stop, SessionStart...) est fusionné sous la clé vide : `matcher` absent,
    `null` ou `""` désignent le même groupe, sinon chaque ré-application
    ajouterait un doublon."""
    changed = False

    def key(e: dict) -> str:
        return str(e.get("matcher") or "")

    for entry in patch:
        if not isinstance(entry, dict):
            continue
        matcher = key(entry)
        target = next((e for e in existing if isinstance(e, dict) and key(e) == matcher), None)
        if target is None:
            existing.append(json.loads(json.dumps(entry)))
            changed = True
            continue
        hooks = target.setdefault("hooks", [])
        if not isinstance(hooks, list):
            hooks = target["hooks"] = []
        known = {h.get("command") for h in hooks if isinstance(h, dict)}
        for h in entry.get("hooks") or []:
            if isinstance(h, dict) and h.get("command") not in known:
                hooks.append(dict(h))
                known.add(h.get("command"))
                changed = True
    return changed


def _deep_merge(dst: dict, patch: dict, path: str = "") -> bool:
    """Fusion récursive de `patch` dans `dst` (en place). Dicts fusionnés clé
    par clé ; sous `hooks`, les listes d'événements sont fusionnées par
    matcher (cf. _merge_hook_lists) ; les autres listes reçoivent les
    éléments absents (égalité stricte) ; un scalaire absent est posé, un
    scalaire présent n'est jamais écrasé (valeur utilisateur). Idempotent.
    Retourne True si `dst` a changé."""
    changed = False
    for key, val in patch.items():
        if key.startswith("_comment"):
            continue
        cur = dst.get(key)
        if isinstance(val, dict):
            if not isinstance(cur, dict):
                if cur is not None:
                    continue  # type incompatible : on ne touche pas
                cur = dst[key] = {}
                changed = True
            if _deep_merge(cur, val, f"{path}.{key}" if path else key):
                changed = True
        elif isinstance(val, list):
            if not isinstance(cur, list):
                if cur is not None:
                    continue
                cur = dst[key] = []
                changed = True
            if path == "hooks":
                if _merge_hook_lists(cur, val):
                    changed = True
            else:
                for item in val:
                    if item not in cur:
                        cur.append(item)
                        changed = True
        elif key not in dst:
            dst[key] = val
            changed = True
    return changed


# Les templates lancent leurs hooks par le littéral `python`. Sous macOS /
# Linux ce nom manque souvent (seul `python3` existe) : le hook sort en 127,
# donc inerte en silence (verrou des évals non appliqué, statusline vide).
# L'interpréteur est adapté dans le settings.json du WORKSPACE, jamais dans
# les templates ; Windows et les postes où `python` existe sont inchangés.
# Motif appliqué au texte JSON (guillemets échappés `\"`).
_PY_HOOK_RE = re.compile(r'(?<![\w./\\-])python(?= \\"\$\{CLAUDE_PROJECT_DIR\})')


def _hook_interpreter() -> str:
    """`python`, ou `python3` si seul celui-ci est dans le PATH (hors Windows)."""
    import os
    import shutil
    if os.name == "nt" or shutil.which("python") or not shutil.which("python3"):
        return "python"
    return "python3"


def _adapt_hook_text(text: str) -> str:
    interp = _hook_interpreter()
    return text if interp == "python" else _PY_HOOK_RE.sub(interp, text)


def _adapt_settings_interpreter(ws_dir: Path, patched: list) -> None:
    """Réécrit l'interpréteur des hooks de `.claude/settings.json` (cf.
    _PY_HOOK_RE). Texte brut : la mise en forme du fichier est conservée."""
    path = ws_dir / ".claude" / "settings.json"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    new = _adapt_hook_text(text)
    if new != text:
        path.write_text(new, encoding="utf-8")
        if ".claude/settings.json" not in patched:
            patched.append(".claude/settings.json")


def _merge_settings_patch(ws_dir: Path, marker: dict, patched: list) -> None:
    """Fusionne `settings_patch` du marker dans `.claude/settings.json` du
    workspace (créé avec le patch seul s'il est absent). Lecture stricte :
    un settings.json corrompu lève CorruptJsonError (409 côté route),
    jamais écrasé. Idempotent : rien n'est écrit si rien ne change."""
    patch = marker.get("settings_patch")
    if not isinstance(patch, dict):
        return
    # Interpréteur adapté AVANT la fusion : la dédup des hooks compare les
    # commandes à l'identique, une ré-application ne doit pas les doubler.
    patch = json.loads(_adapt_hook_text(json.dumps(patch, ensure_ascii=False)))
    path = ws_dir / ".claude" / "settings.json"
    data = read_json_strict(path, {})
    if not isinstance(data, dict):
        raise CorruptJsonError(path, "objet JSON attendu")
    if _deep_merge(data, patch):
        write_json(path, data)
        patched.append(".claude/settings.json")


def _run_generators(ws_dir: Path, marker: dict, vars: dict, opts: dict,
                    generated: list, skipped: list) -> dict:
    """Exécute les générateurs déclarés par le marker après la copie.
    Retourne les informations à exposer dans la réponse (ex. `prefix`
    effectif des agents générés)."""
    extra: dict = {}
    for gen in marker.get("generators") or []:
        if gen == "team_agents":
            from dashcore.api_team import generate_agents
            r = generate_agents(ws_dir, vars, {"models": opts.get("models"),
                                               "default_model": opts.get("default_model"),
                                               "regenerate": opts.get("regenerate"),
                                               "prefix": opts.get("prefix")})
            generated.extend(r["generated"])
            skipped.extend(r["skipped"])
            extra["prefix"] = r.get("prefix")
        else:
            log.warning("overlay : générateur inconnu ignoré : %s", gen)
            skipped.append({"path": f"generator:{gen}", "reason": "générateur inconnu"})
    return extra


def _missing_requires(ws_dir: Path, marker: dict) -> list[dict]:
    """Prérequis (`requires`) de l'overlay non actifs sur le workspace."""
    missing = []
    for req in marker.get("requires") or []:
        if not isinstance(req, str) or not safe_id(req):
            continue
        ov = get_overlay(req)
        if ov is None or not overlay_is_active(ws_dir, ov):
            missing.append({"id": req, "label": ov["label"] if ov else req})
    return missing


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
    est absent du workspace ; un fichier géré (`managed`) présent est mis à
    jour s'il diffère du rendu (sauvegarde .bak). CLAUDE.md est traite specialement (fragment
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
        "updated": [rel | "CLAUDE.md (bloc <overlay>)", ...],
        "backups": [rel .bak, ...], "options": {...},
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
        # Mise à jour des fichiers gérés seulement en RÉ-application (module
        # déjà actif) : à la première activation, un fichier homonyme déjà
        # présent appartient à l'utilisateur et n'est jamais remplacé.
        was_active = overlay_is_active(ws_dir, overlay)
        return _apply_overlay_body(ws_id, overlay_id, ws_dir, src_dir, vars, options,
                                   was_active)


def _apply_overlay_body(ws_id: str, overlay_id: str, ws_dir, src_dir,
                        vars: dict, options: dict | None,
                        was_active: bool = False) -> tuple[int, dict]:
    opts = _normalize_options(options)
    marker = read_json(src_dir / OVERLAY_MARKER, {}) or {}
    cfg = _claude_md_config(marker)

    # 0. Prérequis (`requires`) : refus AVANT toute écriture si un overlay
    #    requis n'est pas actif sur le workspace (409, message clair).
    missing_req = _missing_requires(ws_dir, marker)
    if missing_req:
        labels = ", ".join(f"« {m['label']} »" for m in missing_req)
        return 409, {
            "ok": False,
            "overlay_id": overlay_id,
            "error": (f"Le module « {marker.get('label') or overlay_id} » requiert "
                      f"{labels} : active d'abord ce module sur le workspace."),
            "missing_requires": missing_req,
        }

    # Enrichir les vars de substitution avec les options de bootstrap.
    vars = dict(vars or {})
    vars.setdefault("author", opts["author"] or vars.get("name") or "nebula")
    vars.setdefault("language", opts["language"])

    copied: list[str] = []
    appended: list[str] = []
    seeded: list[str] = []
    skipped: list[dict] = []
    generated: list[str] = []
    patched: list[str] = []
    # Ré-application : fichiers gérés remplacés (et bloc CLAUDE.md) + .bak.
    updated: list[str] = []
    backups: list[str] = []
    ws_root = Path(ws_dir).resolve()

    # 1. CLAUDE.md : traitement special (fragment / complet / mise a jour du bloc).
    _handle_claude_md(src_dir, ws_dir, marker, vars, copied, skipped, appended,
                      updated, backups, marker.get("id") or overlay_id)

    # 2. Copie standard des autres fichiers (idempotente + gating).
    claude_md_names = {cfg["full_file"], cfg["fragment_file"]}
    for entry in src_dir.rglob("*"):
        rel = entry.relative_to(src_dir)
        rel_posix = rel.as_posix()
        if rel.name == OVERLAY_MARKER:
            continue
        if entry.is_dir() or _is_junk(rel):
            continue
        # CLAUDE.md (complet + fragment) deja gere a l'etape 1.
        if rel_posix in claude_md_names:
            continue
        # Les seeds ne sont jamais copies comme fichiers autonomes.
        if _is_seed_path(rel_posix, marker):
            continue
        # Doc de l'overlay (catalogue), jamais livree dans le workspace.
        if _is_no_copy(rel_posix, marker):
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
            # Fichier géré par le module : mis à jour s'il diffère du rendu
            # (sauvegarde .bak). Tout autre fichier présent est à l'utilisateur.
            if was_active and _is_managed(rel_posix, marker) and target.is_file():
                _update_managed_file(entry, target, rel_posix, ws_dir, ws_root, vars,
                                     updated, backups, skipped)
            else:
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

    # 4. settings.local.json (validate_author selon le mode) et
    # 5. pre-remplissage du mode + langue dans overview.md : seulement pour
    #    un overlay qui exploite les options de bootstrap. Un overlay sans
    #    mode-gating (claude-team) ne doit pas réécrire le choix de mode posé
    #    par le prérequis.
    prefilled: list[str] = []
    if _uses_bootstrap_options(marker):
        written: list[str] = []
        _write_settings_local(ws_dir, opts, written)
        copied.extend(w for w in written if w not in copied)
        _prefill_overview(ws_dir, opts, prefilled)

    # 5b. settings_patch : fusion déclarative dans .claude/settings.json
    #     (hooks par matcher sans doublon). Un settings.json corrompu n'est
    #     jamais écrasé : 409 (les fichiers déjà copiés restent, idempotents).
    try:
        _merge_settings_patch(ws_dir, marker, patched)
    except CorruptJsonError as e:
        return 409, {
            "ok": False, "overlay_id": overlay_id, "error": str(e),
            "copied": copied, "appended": appended, "seeded": seeded,
            "updated": updated, "backups": backups,
            "skipped": skipped, "options": opts,
        }

    # 5b-bis. Hooks copiés depuis le template (settings.json complet) :
    #     même adaptation de l'interpréteur que pour le patch.
    _adapt_settings_interpreter(ws_dir, patched)

    # 5c. Générateurs déclaratifs (ex. team_agents) : après la copie, donc
    #     les sources (manifeste, corps) sont en place.
    gen_extra = _run_generators(ws_dir, marker, vars, opts, generated, skipped)

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
            "generated": generated,
            "settings_patched": patched,
            "updated": updated,
            "backups": backups,
            "skipped": skipped,
            "options": opts,
        }

    log.info("overlay %s applied on %s (mode=%s depth=%s) : "
             "%d copied, %d appended, %d seeded, %d generated, %d updated "
             "(%d backups), %d skipped",
             overlay_id, ws_id, opts["mode"], opts["depth"],
             len(copied), len(appended), len(seeded), len(generated),
             len(updated), len(backups), len(skipped))
    return 200, {
        "ok": True,
        "overlay_id": overlay_id,
        "copied": copied,
        "appended": appended,
        "seeded": seeded,
        "prefilled": prefilled,
        "generated": generated,
        "settings_patched": patched,
        "updated": updated,
        "backups": backups,
        "skipped": skipped,
        "options": opts,
        **gen_extra,
    }
