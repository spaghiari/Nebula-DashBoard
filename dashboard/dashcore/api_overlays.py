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
import os
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
    return [{"id": a["id"], "role": a.get("role") or "", "model": a.get("model") or default,
             "effort": a.get("effort") if isinstance(a.get("effort"), str) else None}
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
    return _valid_globs(marker.get("managed"))


def _valid_globs(raw) -> list[str]:
    """Globs relatifs valides d'une liste du marker (sans `\\`, `:`, `/` de
    tête ni segment `..`). Liste absente ou invalide = aucun glob."""
    out: list[str] = []
    for g in raw if isinstance(raw, list) else []:
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


def _render_entry(entry: Path, vars: dict) -> tuple[str | None, bytes | None]:
    """Rendu d'un fichier de l'overlay : (texte rendu, None) pour un fichier
    texte (placeholders substitués), (None, octets) sinon. OSError remontée."""
    if is_text_file(entry):
        return render_placeholders(entry.read_text(encoding="utf-8"), vars), None
    return None, entry.read_bytes()


def _same_as_rendered(target: Path, new_text: str | None, new_bytes: bytes | None) -> bool:
    """Vrai si `target` a le contenu du rendu (cf. _render_entry) ; fins de
    ligne ignorées pour un texte. OSError remontée."""
    if new_text is not None:
        try:
            return _norm_eol(target.read_bytes().decode("utf-8")) == _norm_eol(new_text)
        except UnicodeDecodeError:
            return False
    return target.read_bytes() == new_bytes


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
        new_text, new_bytes = _render_entry(entry, vars)
        same = _same_as_rendered(target, new_text, new_bytes)
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


def _missing_hook_refs(ws_dir: Path, include_local: bool = False) -> list[str]:
    """Liste les hooks reference par `.claude/settings.json` (et
    `.claude/settings.local.json` si `include_local`) mais absents du
    workspace. Garde fail-fast post-generation : un settings.json qui pointe
    vers un hook inexistant deadlocke Claude Code (exit 2 d'un PreToolUse =
    refus bloquant sur Bash/Edit/Write, le workspace devient inutilisable).
    Retourne la liste dedupliquee (ordre preserve) des chemins manquants."""
    names = ["settings.json"] + (["settings.local.json"] if include_local else [])
    seen: set[str] = set()
    missing: list[str] = []
    for name in names:
        try:
            text = (ws_dir / ".claude" / name).read_text(encoding="utf-8")
        except OSError:
            continue
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

    # 0b. Itération /improve en attente de verdict : refus AVANT toute
    #     écriture si un modèle d'agent changerait réellement (le candidat
    #     serait mesuré sur une autre configuration). Sans changement réel
    #     (modale qui renvoie les modèles actuels), la ré-application passe.
    #     Même règle pour les agents générés : refus si `generate_agents`
    #     réécrirait réellement un agent (« Régénérer » après une édition de
    #     team.json ou d'un corps depuis la phase 1, nouveau préfixe...).
    #     Modèles ou régénération demandés sur un manifeste présent mais
    #     corrompu : 409 ici, avant toute copie (sinon application partielle).
    if "team_agents" in (marker.get("generators") or []):
        from dashcore.api_team import (
            MANIFEST_REL, agents_rewrite_pending, models_change_pending, pending_message,
        )
        wants = bool(opts["models"] or opts["default_model"] or opts["regenerate"])
        if wants and (ws_dir / MANIFEST_REL).exists():
            try:
                read_json_strict(ws_dir / MANIFEST_REL, None)
            except CorruptJsonError as e:
                return 409, {"ok": False, "overlay_id": overlay_id,
                             "error": f"manifeste corrompu : {e} ; rien n'a été modifié"}
        if opts["models"] or opts["default_model"]:
            pend = models_change_pending(ws_dir, opts["models"], opts["default_model"], vars)
            if pend:
                return 409, {"ok": False, "overlay_id": overlay_id, "pending": pend,
                             "error": pending_message(pend, "les modèles des agents")}
        if was_active:
            pend = agents_rewrite_pending(ws_dir, vars, opts)
            if pend:
                return 409, {"ok": False, "overlay_id": overlay_id, "pending": pend,
                             "error": pending_message(pend, "les agents générés")}

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
    #     Manifeste corrompu alors que des modèles sont à mémoriser : 409.
    from dashcore.api_team import PendingIterationError
    try:
        gen_extra = _run_generators(ws_dir, marker, vars, opts, generated, skipped)
    except (CorruptJsonError, PendingIterationError) as e:
        pending = isinstance(e, PendingIterationError)
        return 409, {
            "ok": False, "overlay_id": overlay_id,
            "error": str(e) if pending else f"manifeste corrompu : {e}",
            **({"pending": e.pending} if pending else {}),
            "copied": copied, "appended": appended, "seeded": seeded,
            "updated": updated, "backups": backups,
            "skipped": skipped, "options": opts,
        }

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


# --- Variables de substitution ---------------------------------------------------

def overlay_vars(ws_obj: dict) -> dict:
    """Variables de substitution d'un overlay pour le workspace `ws_obj`
    (entrée du registre) : mêmes clés que create_workspace. Partagé par
    l'application, le retrait (comparaison au rendu) et la régénération."""
    import datetime as _dt
    return {
        "name": ws_obj["id"],
        "label": ws_obj.get("label") or ws_obj["id"],
        "description": ws_obj.get("description") or "(a completer)",
        "tools": "(a completer)",
        "date": _dt.date.today().isoformat(),
        "emoji": ws_obj.get("emoji") or "📁",
    }


# --- Retrait d'un module ---------------------------------------------------------
#
# Principe : rien n'est supprimé. Chaque fichier du module est DÉPLACÉ dans
# `.claude/.nebula-removed/<module>-<AAAAMMJJ-HHMMSS>/` (même chemin relatif),
# avec `removal.json` (plan + restauration). settings.json et CLAUDE.md ne
# perdent que ce qui appartient au module (hooks / statusLine pointant un de
# ses scripts, bloc BEGIN..END), après sauvegarde .bak.

REMOVED_DIR_REL = Path(".claude") / ".nebula-removed"
_SETTINGS_REL = ".claude/settings.json"
_SETTINGS_LOCAL_REL = ".claude/settings.local.json"
# Sauvegarde de settings.local.json écrite à la racine du dossier d'archive
# du retrait (jamais à côté du fichier : elle échapperait au .gitignore).
LOCAL_BACKUP_NAME = "settings.local.json.bak"
# Fichiers jamais déplacés par un retrait, même identiques au rendu :
# réglages locaux de l'utilisateur, et `.gitignore` qui porte la règle
# `.claude/.nebula-removed/` (sans elle, l'archive du retrait serait suivie
# par git).
_ALWAYS_KEEP = {
    _SETTINGS_LOCAL_REL: "settings.local.json toujours conservé",
    ".gitignore": ".gitignore toujours conservé (il ignore l'archive .claude/.nebula-removed/)",
}
# Jetons « chemin de script Python » d'une commande de hook : `python`,
# `python3`, `py -3`, chemin préfixé par ${CLAUDE_PROJECT_DIR} ou absolu.
_PY_TOKEN_RE = re.compile(r"[^\s\"']+\.py\b")
_PROJECT_DIR_PREFIXES = ("${CLAUDE_PROJECT_DIR}", "$CLAUDE_PROJECT_DIR", "%CLAUDE_PROJECT_DIR%")


def _move(src: Path, dst: Path) -> None:
    """Déplacement atomique (même volume : le workspace). Point unique, pour
    que les tests puissent simuler un échec."""
    os.replace(src, dst)


def _sha1_bytes(data: bytes) -> str:
    import hashlib
    return hashlib.sha1(data, usedforsecurity=False).hexdigest()  # nosemgrep - empreinte de contenu, pas de sécurité


def _removal_config(marker: dict) -> dict:
    """Section `removal` du marker : `living` (contenu du projet, archivé par
    défaut, laissé en place avec `keep_living`) et `keep_if_modified`
    (gardé s'il diffère du rendu). Absence = aucun glob (cf. pitfall
    « valeur par défaut vide »)."""
    raw = marker.get("removal")
    cfg = raw if isinstance(raw, dict) else {}
    return {"living": _valid_globs(cfg.get("living")),
            "keep_if_modified": _valid_globs(cfg.get("keep_if_modified"))}


def _matches_any(rel_posix: str, globs: list[str]) -> bool:
    parts = rel_posix.split("/")
    return any(_glob_match(parts, g.split("/")) for g in globs)


def _module_files(src_dir: Path, marker: dict) -> list[tuple[str, Path]]:
    """Fichiers livrables du module (même parcours que la copie, sans
    no_copy, seeds ni CLAUDE.md complet / fragment), triés. Le mode et la
    profondeur ne filtrent pas : on retire ce qui a pu être copié."""
    cfg = _claude_md_config(marker)
    names = {cfg["full_file"], cfg["fragment_file"]}
    out: list[tuple[str, Path]] = []
    for entry in src_dir.rglob("*"):
        rel = entry.relative_to(src_dir)
        rel_posix = rel.as_posix()
        if rel.name == OVERLAY_MARKER or entry.is_dir() or _is_junk(rel):
            continue
        if rel_posix in names or _is_seed_path(rel_posix, marker) or _is_no_copy(rel_posix, marker):
            continue
        out.append((rel_posix, entry))
    return sorted(out)


def _script_refs(command: str, ws_root: Path) -> set[str]:
    """Scripts `.py` (chemins relatifs au workspace, posix) lancés par une
    commande de hook. Comparaison par CHEMIN : résiste à `python3`, aux
    guillemets et aux séparateurs `\\`."""
    out: set[str] = set()
    for tok in _PY_TOKEN_RE.findall(command or ""):
        t = tok.replace("\\", "/")
        for pre in _PROJECT_DIR_PREFIXES:
            if t.startswith(pre):
                t = t[len(pre):].lstrip("/")
                break
        else:
            if re.match(r"^[A-Za-z]:/", t) or t.startswith("/"):
                try:
                    t = Path(tok).resolve().relative_to(ws_root).as_posix()
                except (OSError, ValueError):
                    continue
        while t.startswith("./"):
            t = t[2:]
        out.add(t)
    return out


def _strip_module_hooks(data: dict, scripts: set[str], ws_root: Path) -> tuple[list[dict], bool]:
    """Retire EN PLACE de `data` (settings.json parsé) les hooks dont la
    commande lance un script de `scripts`, puis les groupes et événements
    devenus vides, et `statusLine` s'il lance un script du module. Un hook
    utilisateur du même matcher est conservé ; `permissions` et toute autre
    clé ne sont jamais touchées. Retourne (entrées retirées
    [{event, matcher, command}], statusLine retiré)."""
    removed: list[dict] = []
    hooks = data.get("hooks")
    if isinstance(hooks, dict):
        for event in list(hooks):
            groups = hooks[event]
            if not isinstance(groups, list):
                continue
            kept_groups = []
            removed_here = False
            for g in groups:
                inner = g.get("hooks") if isinstance(g, dict) else None
                if not isinstance(inner, list):
                    kept_groups.append(g)
                    continue
                kept = []
                for h in inner:
                    cmd = h.get("command") if isinstance(h, dict) else None
                    if isinstance(cmd, str) and _script_refs(cmd, ws_root) & scripts:
                        removed.append({"event": event, "matcher": str(g.get("matcher") or ""),
                                        "command": cmd})
                        removed_here = True
                    else:
                        kept.append(h)
                if len(kept) == len(inner):
                    kept_groups.append(g)
                elif kept:
                    g["hooks"] = kept
                    kept_groups.append(g)
            if removed_here:
                if kept_groups:
                    hooks[event] = kept_groups
                else:
                    del hooks[event]
        if not hooks and removed:
            del data["hooks"]
    statusline_removed = False
    sl = data.get("statusLine")
    if isinstance(sl, dict) and isinstance(sl.get("command"), str) \
            and _script_refs(sl["command"], ws_root) & scripts:
        del data["statusLine"]
        statusline_removed = True
    return removed, statusline_removed


def _settings_script_refs(data, ws_root: Path) -> set[str]:
    """Tous les scripts référencés par settings.json (hooks + statusLine)."""
    refs: set[str] = set()
    if not isinstance(data, dict):
        return refs
    hooks = data.get("hooks")
    for groups in (hooks.values() if isinstance(hooks, dict) else []):
        for g in groups if isinstance(groups, list) else []:
            for h in (g.get("hooks") if isinstance(g, dict) else None) or []:
                if isinstance(h, dict) and isinstance(h.get("command"), str):
                    refs |= _script_refs(h["command"], ws_root)
    sl = data.get("statusLine")
    if isinstance(sl, dict) and isinstance(sl.get("command"), str):
        refs |= _script_refs(sl["command"], ws_root)
    return refs


def _claude_md_removal(ws_dir: Path, marker: dict) -> dict:
    """Plan du retrait du bloc BEGIN..END du module dans CLAUDE.md. Seul le
    bloc part ; fichier entier archivé seulement s'il ne reste que des
    blancs ; sans marqueurs : rien, signalé (`note`). Les clés `_*` sont
    internes (non renvoyées)."""
    cfg = _claude_md_config(marker)
    out = {"file": cfg["full_file"], "block_present": False, "whole_file": False, "note": "",
           "_new_text": None, "_block": None, "_sha1": None}
    if not isinstance(marker.get("claude_md"), dict):
        out["note"] = "module sans bloc CLAUDE.md"
        return out
    target = ws_dir / cfg["full_file"]
    if not target.is_file():
        out["note"] = f"{cfg['full_file']} absent"
        return out
    if not _inside_workspace(ws_dir.resolve(), target):
        out["note"] = f"{cfg['full_file']} est un lien hors du workspace : rien retiré"
        return out
    try:
        raw = target.read_bytes()
        text = _norm_eol(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError) as e:
        out["note"] = f"{cfg['full_file']} illisible : {e}"
        return out
    begin, end = cfg["begin_marker"], cfg["end_marker"]
    b = text.find(begin)
    if b < 0:
        out["note"] = "marqueurs du module absents : rien retiré (à vérifier à la main)"
        return out
    e = text.find(end, b)
    if e < 0:
        out["note"] = "marqueur de fin absent : rien retiré (à vérifier à la main)"
        return out
    before = text[:b].rstrip("\n")
    after = text[e + len(end):].lstrip("\n")
    if before and after:
        new = before + "\n\n" + after
    elif before:
        new = before + "\n"
    else:
        new = after
    out.update(block_present=True, whole_file=not new.strip(), _new_text=new,
               _block=text[b:e + len(end)] + "\n", _sha1=_sha1_bytes(raw))
    return out


def _team_agent_paths(ws_dir: Path, src_dir: Path, marker: dict,
                      ws_id: str) -> tuple[str | None, list[str], bool]:
    """Agents générés par le module (générateur `team_agents`) : (préfixe,
    chemins relatifs, manifeste lisible). Préfixe lu AVANT tout déplacement
    (team.prefix, sinon id du workspace). team.json illisible : seuls les
    `agents/*-<id>.md` portant le marqueur généré sont retenus."""
    if "team_agents" not in (marker.get("generators") or []):
        return None, [], True
    from dashcore.api_team import (
        AGENTS_DIR_REL, MANIFEST_REL, _is_generated, effective_prefix, load_manifest,
        manifest_agents,
    )
    try:
        data = read_json_strict(ws_dir / MANIFEST_REL, None)
    except CorruptJsonError:
        data = None
    if isinstance(data, dict) and isinstance(data.get("agents"), list):
        prefix = effective_prefix(data, {"name": ws_id})
        return prefix, [(AGENTS_DIR_REL / f"{prefix}-{a['id']}.md").as_posix()
                        for a in manifest_agents(data)], True
    tpl = load_manifest(src_dir)
    ids = [a["id"] for a in manifest_agents(tpl)] if tpl else []
    adir = ws_dir / AGENTS_DIR_REL
    found: list[str] = []
    for aid in ids:
        for p in (sorted(adir.glob(f"*-{aid}.md")) if adir.is_dir() else []):
            try:
                if p.is_file() and _is_generated(p.read_text(encoding="utf-8")):
                    found.append(p.relative_to(ws_dir).as_posix())
            except OSError:
                continue
    return None, found, False


def _local_settings_plan(ws_dir: Path, ws_root: Path, data, scripts: set[str]) -> dict:
    """Retrait ciblé dans `.claude/settings.local.json` (jamais archivé
    entier) : mêmes règles que settings.json (hooks / statusLine lançant un
    script du module retirés, permissions et autres clés intactes)."""
    out = {"present": isinstance(data, dict), "note": "", "entries_removed": [],
           "statusline_removed": False, "_data": None, "_sha1": None}
    if not isinstance(data, dict):
        return out
    path = ws_dir / _SETTINGS_LOCAL_REL
    try:
        out["_sha1"] = _sha1_bytes(path.read_bytes())
    except OSError:
        pass
    if not _inside_workspace(ws_root, path):
        out["note"] = "settings.local.json est un lien hors du workspace : non modifié"
        return out
    copy = json.loads(json.dumps(data))
    removed, sl_removed = _strip_module_hooks(copy, scripts, ws_root)
    out.update(entries_removed=removed, statusline_removed=sl_removed, _data=copy)
    return out


def plan_overlay_removal(ws_dir: Path, overlay: dict, src_dir: Path, marker: dict,
                         vars: dict, *, ws_id: str, keep_living: bool = False,
                         settings_data=None, shared: dict | None = None,
                         local_data=None, active: bool = True) -> dict:
    """Plan de retrait (aucune écriture). Classe chaque fichier du module :

      - `archive` (déplacé) : identique au rendu, modifié, contenu vivant,
        agent généré, signature du module (toujours, même avec keep_living) ;
      - `keep` (laissé en place) : lien ou jonction, `keep_if_modified`
        modifié, contenu vivant avec `keep_living`, agent généré sans
        marqueur (édité à la main), _ALWAYS_KEEP (settings.local.json,
        .gitignore), fichier aussi livré par un autre module actif ;
      - `not_found` : absent du workspace (renommé, jamais copié...).

    Module INACTIF (`active` faux, signature absente) : un fichier de même
    chemin appartient au projet (README.md, .gitignore, mémoire...) et n'est
    jamais déplacé. Seules les traces certaines d'un retrait partiel sont
    traitées : hooks (settings.json et settings.local.json) qui lancent un
    script du module ABSENT du disque, bloc CLAUDE.md du module (marqueurs
    propres au module), agents portant le marqueur généré.

    `settings_data` / `local_data` = settings.json / settings.local.json
    déjà lus strictement (None si absents). `plan_id` = sha1 du plan
    canonique, contenus compris : un fichier modifié entre l'aperçu et
    l'exécution change l'identifiant."""
    shared = shared or {}
    ws_root = Path(ws_dir).resolve()
    vars = dict(vars or {})
    vars.setdefault("author", vars.get("name") or "nebula")
    vars.setdefault("language", "fr")
    rcfg = _removal_config(marker)
    signature = overlay.get("signature_file") or marker.get("signature_file") or ""
    archive: list[dict] = []
    keep: list[dict] = []
    not_found: list[str] = []
    hashes: dict[str, str] = {}

    def add_archive(rel: str, reason: str, target: Path) -> None:
        try:
            hashes[rel] = _sha1_bytes(target.read_bytes())
        except OSError as e:
            keep.append({"path": rel, "reason": f"illisible, laissé en place : {e}"})
            return
        archive.append({"path": rel, "reason": reason})

    files = _module_files(src_dir, marker)
    seen = {rel for rel, _ in files}
    if signature and signature not in seen and (src_dir / signature).is_file():
        files.append((signature, src_dir / signature))
    template_settings = None
    for rel, entry in files:
        if rel == _SETTINGS_REL:
            template_settings = entry  # traité à part (section settings)
            continue
        target = ws_dir / rel
        if not os.path.lexists(target):
            not_found.append(rel)
            continue
        if not active:
            # Signature absente : rien ne prouve que ce fichier vient du
            # module, il est au projet (jamais listé ni déplacé).
            continue
        if rel in _ALWAYS_KEEP:
            keep.append({"path": rel, "reason": _ALWAYS_KEEP[rel]})
            continue
        if not _inside_workspace(ws_root, target) or not target.is_file():
            keep.append({"path": rel, "reason": "lien ou jonction : laissé en place"})
            continue
        if rel in shared:
            keep.append({"path": rel, "reason": f"aussi livré par le module actif « {shared[rel]} »"})
            continue
        try:
            same = _same_as_rendered(target, *_render_entry(entry, vars))
        except OSError:
            same = False
        living = _matches_any(rel, rcfg["living"])
        if rel == signature:
            add_archive(rel, "signature du module", target)
        elif living and keep_living:
            keep.append({"path": rel, "reason": "contenu vivant conservé (keep_living)"})
        elif not same and _matches_any(rel, rcfg["keep_if_modified"]):
            keep.append({"path": rel, "reason": "modifié : conservé"})
        elif living:
            add_archive(rel, "contenu vivant", target)
        else:
            add_archive(rel, "identique au rendu" if same else "modifié", target)

    # Agents générés (claude-team).
    prefix, agent_paths, manifest_ok = _team_agent_paths(ws_dir, src_dir, marker, ws_id)
    from dashcore.api_team import _is_generated
    for rel in agent_paths:
        target = ws_dir / rel
        if not os.path.lexists(target):
            not_found.append(rel)
        elif not _inside_workspace(ws_root, target) or not target.is_file():
            keep.append({"path": rel, "reason": "lien ou jonction : laissé en place"})
        else:
            try:
                gen = _is_generated(target.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError):
                gen = False
            if gen:
                add_archive(rel, "agent généré", target)
            else:
                keep.append({"path": rel, "reason": "agent édité à la main (marqueur généré absent)"})

    # settings.json : fichier entier archivé s'il est identique au rendu,
    # sinon retrait ciblé des hooks / statusLine du module.
    # Module inactif : seuls les scripts du module ABSENTS du disque (hooks
    # cassés, trace d'un retrait partiel) ; un script présent de même nom
    # peut être celui du projet, ses hooks restent.
    scripts = {rel for rel in not_found if rel.endswith(".py")}
    if active:
        scripts |= {a["path"] for a in archive if a["path"].endswith(".py")}
        scripts |= {k["path"] for k in keep if k["path"].endswith(".py") and k["path"] not in shared}
    settings = {"present": isinstance(settings_data, dict), "archive_whole": False, "note": "",
                "entries_removed": [], "statusline_removed": False, "_data": None, "_sha1": None}
    spath = ws_dir / _SETTINGS_REL
    if isinstance(settings_data, dict):
        try:
            settings["_sha1"] = _sha1_bytes(spath.read_bytes())
        except OSError:
            pass
        if active and template_settings is not None and _inside_workspace(ws_root, spath):
            try:
                text = render_placeholders(template_settings.read_text(encoding="utf-8"), vars)
                renders = [json.loads(_adapt_hook_text(text)), json.loads(text)]
            except (OSError, ValueError):
                renders = []
            if settings_data in renders:
                settings["archive_whole"] = True
        if not _inside_workspace(ws_root, spath):
            settings["note"] = "settings.json est un lien hors du workspace : non modifié"
        elif not settings["archive_whole"]:
            data = json.loads(json.dumps(settings_data))
            removed, sl_removed = _strip_module_hooks(data, scripts, ws_root)
            settings.update(entries_removed=removed, statusline_removed=sl_removed, _data=data)

    local = _local_settings_plan(ws_dir, ws_root, local_data, scripts)
    claude_md = _claude_md_removal(ws_dir, marker)
    nothing = not archive and not settings["archive_whole"] and not settings["entries_removed"] \
        and not settings["statusline_removed"] and not claude_md["block_present"] \
        and not local["entries_removed"] and not local["statusline_removed"]
    canonical = {
        "overlay_id": overlay.get("id"), "keep_living": bool(keep_living), "active": bool(active),
        "archive": [[a["path"], a["reason"], hashes.get(a["path"])] for a in archive],
        "keep": [[k["path"], k["reason"]] for k in keep], "not_found": sorted(not_found),
        "settings": [settings["_sha1"], settings["archive_whole"], settings["entries_removed"],
                     settings["statusline_removed"]],
        "settings_local": [local["_sha1"], local["entries_removed"], local["statusline_removed"]],
        "claude_md": [claude_md["_sha1"], claude_md["block_present"], claude_md["whole_file"]],
        "prefix": prefix,
    }
    plan_id = _sha1_bytes(json.dumps(canonical, sort_keys=True, ensure_ascii=False).encode("utf-8"))[:16]
    return {
        "overlay_id": overlay.get("id"), "plan_id": plan_id, "prefix": prefix,
        "manifest_readable": manifest_ok, "keep_living": bool(keep_living),
        "archive": archive, "keep": keep, "not_found": sorted(not_found),
        "settings": settings, "settings_local": local, "claude_md": claude_md,
        "nothing_to_do": nothing, "signature": signature, "active": bool(active),
    }


def _unique_archive_dir(ws_dir: Path, overlay_id: str) -> Path:
    """`.claude/.nebula-removed/<module>-<AAAAMMJJ-HHMMSS>` (suffixe `-2`,
    `-3`... si le nom existe) : une archive n'est jamais réutilisée."""
    import datetime as _dt
    base = ws_dir / REMOVED_DIR_REL
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    n = 1
    while True:
        cand = base / (f"{overlay_id}-{stamp}" if n == 1 else f"{overlay_id}-{stamp}-{n}")
        if not os.path.lexists(cand):
            return cand
        n += 1


def _public_removal(plan: dict, *, dry_run: bool, archive_dir: str | None = None,
                    settings_backup: str | None = None, claude_backup: str | None = None,
                    local_backup: str | None = None) -> dict:
    """Réponse de la route (sans les clés internes `_*` du plan)."""
    s, c, sl = plan["settings"], plan["claude_md"], plan["settings_local"]
    return {
        "ok": True, "overlay_id": plan["overlay_id"], "dry_run": dry_run,
        "plan_id": plan["plan_id"], "archive_dir": archive_dir,
        # Module inactif (signature absente) : seules les traces certaines
        # d'un retrait partiel sont traitées (cf. plan_overlay_removal).
        "inactive": not plan["active"],
        "archive": plan["archive"], "keep": plan["keep"], "not_found": plan["not_found"],
        "settings": {"present": s["present"], "archived": s["archive_whole"], "note": s["note"],
                     "entries_removed": s["entries_removed"],
                     "statusline_removed": s["statusline_removed"], "backup": settings_backup},
        "settings_local": {"present": sl["present"], "note": sl["note"],
                           "entries_removed": sl["entries_removed"],
                           "statusline_removed": sl["statusline_removed"],
                           "backup": local_backup},
        "claude_md": {"block_removed": c["block_present"], "whole_file": c["whole_file"],
                      "note": c["note"], "backup": claude_backup},
        "prefix": plan["prefix"], "keep_living": plan["keep_living"],
        "nothing_to_do": plan["nothing_to_do"], "restart_needed": True,
    }


def _archive_pycache(ws_dir: Path, ws_root: Path, moved: list[str], archive_dir: Path) -> list[str]:
    """Déplace dans l'archive le cache Python (`__pycache__/*.pyc|.pyo`) des
    seuls dossiers d'où un script `.py` du module vient d'être déplacé, pour
    les fichiers dont le source `<nom>.py` n'est plus dans ce dossier (un
    script du projet encore présent garde son cache). Jamais de rmtree,
    jamais un lien ou une jonction, jamais hors du workspace. Retourne les
    chemins déplacés (relatifs, posix) ; un échec est journalisé, pas bloquant."""
    out: list[str] = []
    dirs = sorted({(Path(ws_dir) / r).parent for r in moved if r.endswith(".py")})
    for d in dirs:
        cache = d / "__pycache__"
        try:
            if cache.is_symlink() or (hasattr(cache, "is_junction") and cache.is_junction()) \
                    or not cache.is_dir() or not _inside_workspace(ws_root, cache):
                continue
            entries = sorted(cache.iterdir())
        except OSError:
            continue
        for f in entries:
            if f.suffix not in (".pyc", ".pyo") or f.is_symlink() or not f.is_file():
                continue
            # `hook.cpython-313[.opt-1].pyc` -> source `hook.py`.
            base = re.sub(r"\.opt-\d+$", "", f.name[:-4])
            base = base.rsplit(".", 1)[0] if "." in base else base
            if (d / (base + ".py")).exists():
                continue
            rel = f.relative_to(ws_dir).as_posix()
            try:
                dst = archive_dir / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                _move(f, dst)
                out.append(rel)
            except OSError as e:
                log.warning("retrait : cache Python %s non déplacé : %s", rel, e)
    return out


def _rmdir_empty(ws_dir: Path, rels: list[str]) -> list[str]:
    """`os.rmdir` des dossiers devenus vides (parents des fichiers déplacés),
    du plus profond au moins profond, jamais la racine ni `.claude`, jamais
    un lien ou une jonction, jamais `rmtree`. Retourne les dossiers retirés."""
    stop = {Path(ws_dir), Path(ws_dir) / ".claude"}
    cands: set[Path] = set()
    for rel in rels:
        p = (Path(ws_dir) / rel).parent
        while p not in stop and Path(ws_dir) in p.parents:
            cands.add(p)
            p = p.parent
    removed: list[str] = []
    for d in sorted(cands, key=lambda x: len(x.parts), reverse=True):
        try:
            if d.is_symlink() or (hasattr(d, "is_junction") and d.is_junction()) or not d.is_dir():
                continue
            if any(d.iterdir()):
                continue
            os.rmdir(d)
            removed.append(d.relative_to(ws_dir).as_posix())
        except OSError:
            continue
    return removed


def remove_overlay(ws_id: str, overlay_id: str, vars: dict,
                   options: dict | None = None) -> tuple[int, dict]:
    """Retire le module `overlay_id` du workspace `ws_id` (cf. section).

    Options : `dry_run` (aperçu, aucune écriture), `plan_id` (obligatoire
    pour exécuter : celui de l'aperçu), `keep_living` (contenu vivant laissé
    en place), `force` (passer outre une session Claude en cours).

    Ordre figé sous _MUTATION_LOCK : garde dépendance inverse (409
    `dependents`) -> garde session (409 `active_session` ; seules les
    sessions lancées par Nebula sont vues) -> lecture stricte de
    settings.json et settings.local.json (409 + `file`, avant toute
    écriture) -> plan (module inactif : traces certaines seulement ; aperçu
    renvoyé ici ; `plan_id` absent ou différent -> 409) -> archive +
    removal.json EN PREMIER -> settings.json puis settings.local.json (.bak
    puis retrait) -> vérification relue des deux (une
    référence restante vers un script à déplacer : 500, scripts intacts) ->
    CLAUDE.md (bloc copié dans l'archive, .bak, retrait) -> déplacement des
    fichiers -> signature EN DERNIER (un retrait partiel laisse le module
    « actif », un nouvel appel le termine) -> rmdir des dossiers vides ->
    contrôle final `_missing_hook_refs`. Idempotent : rien à retirer ->
    `nothing_to_do: true`."""
    if not safe_id(ws_id):
        return 400, {"error": "ws_id invalide"}
    if not safe_id(overlay_id):
        return 400, {"error": "overlay_id invalide"}
    overlay = get_overlay(overlay_id)
    if not overlay:
        return 404, {"error": f"Module introuvable : {overlay_id}"}
    ws_dir = resolve_ws_dir(ws_id)
    if not ws_dir.exists():
        return 404, {"error": "workspace absent sur disque"}
    src_dir = TEMPLATES_DIR / overlay["dir_id"]
    if not src_dir.exists():
        return 404, {"error": f"Dossier du module introuvable : {overlay['dir_id']}"}
    opts = options or {}
    dry_run = bool(opts.get("dry_run"))
    keep_living = bool(opts.get("keep_living"))
    force = bool(opts.get("force"))
    want_plan = opts.get("plan_id")
    ov_id = overlay["id"]

    with _MUTATION_LOCK:
        marker = read_json(src_dir / OVERLAY_MARKER, {}) or {}
        all_overlays = list_overlays()
        # 1. Dépendance inverse : un module actif qui requiert celui-ci.
        dependents = [{"id": o["id"], "label": o["label"]} for o in all_overlays
                      if o["id"] != ov_id and ov_id in (o.get("requires") or [])
                      and overlay_is_active(ws_dir, o)]
        if dependents:
            labels = ", ".join(f"« {d['label']} »" for d in dependents)
            return 409, {"ok": False, "overlay_id": ov_id, "dependents": dependents,
                         "error": (f"{labels} requiert « {overlay['label']} » : retire "
                                   "d'abord ce module.")}
        # 2. Session Claude en cours : hooks et agents chargés, fichiers
        #    déplacés sous ses pieds.
        if not force:
            from dashcore import active_sessions
            sess = (active_sessions.list_active() or {}).get(ws_id)
            if isinstance(sess, dict) and sess.get("state", "running") == "running":
                return 409, {"ok": False, "overlay_id": ov_id, "active_session": True,
                             "error": ("Une session Claude tourne sur ce workspace : ferme-la "
                                       "(ou force le retrait), elle garde les hooks et agents "
                                       "du module chargés.")}
        # 3. settings.json lu strictement AVANT toute écriture.
        #    Même règle pour settings.local.json (ses hooks du module sont
        #    retirés aussi) : corrompu -> 409, rien écrit.
        parsed = {}
        for rel in (_SETTINGS_REL, _SETTINGS_LOCAL_REL):
            try:
                parsed[rel] = read_json_strict(ws_dir / rel, None)
            except CorruptJsonError as e:
                return 409, {"ok": False, "overlay_id": ov_id, "file": rel, "error": str(e)}
            if parsed[rel] is not None and not isinstance(parsed[rel], dict):
                return 409, {"ok": False, "overlay_id": ov_id, "file": rel,
                             "error": f"{rel} : objet JSON attendu"}
        # 4. Plan (fichiers aussi livrés par un autre module actif : gardés).
        #    Module inactif (signature absente) : plan restreint aux traces
        #    certaines d'un retrait partiel.
        shared: dict[str, str] = {}
        for o in all_overlays:
            if o["id"] != ov_id and overlay_is_active(ws_dir, o):
                for rel in o.get("files") or []:
                    shared.setdefault(rel, o["label"])
        plan = plan_overlay_removal(ws_dir, overlay, src_dir, marker, vars, ws_id=ws_id,
                                    keep_living=keep_living, settings_data=parsed[_SETTINGS_REL],
                                    shared=shared, local_data=parsed[_SETTINGS_LOCAL_REL],
                                    active=overlay_is_active(ws_dir, overlay))
        if plan["nothing_to_do"] or dry_run:
            return 200, _public_removal(plan, dry_run=dry_run)
        if not want_plan or want_plan != plan["plan_id"]:
            return 409, {**_public_removal(plan, dry_run=True), "ok": False,
                         "error": ("Aperçu absent ou périmé (un fichier a changé depuis) : "
                                   "relis l'aperçu puis confirme.")}
        missing_before = set(_missing_hook_refs(ws_dir, include_local=True))
        return _execute_removal(ws_id, ws_dir, overlay, plan, missing_before)


def _execute_removal(ws_id: str, ws_dir: Path, overlay: dict, plan: dict,
                     missing_before: set | None = None) -> tuple[int, dict]:
    """Exécution du plan (appelée sous _MUTATION_LOCK par remove_overlay)."""
    ov_id = overlay["id"]
    ws_root = Path(ws_dir).resolve()
    archive_dir = _unique_archive_dir(ws_dir, ov_id)
    archive_rel = archive_dir.relative_to(ws_dir).as_posix()
    s, c, sl = plan["settings"], plan["claude_md"], plan["settings_local"]
    errors: list[dict] = []
    settings_backup = claude_backup = local_backup = None

    def fail(status: int, msg: str) -> tuple[int, dict]:
        out = _public_removal(plan, dry_run=False, archive_dir=archive_rel,
                              settings_backup=settings_backup, claude_backup=claude_backup,
                              local_backup=local_backup)
        out.update(ok=False, error=msg, errors=errors)
        log.error("retrait %s sur %s : %s", ov_id, ws_id, msg)
        return status, out

    # 5. Archive + removal.json écrits EN PREMIER.
    import datetime as _dt
    public = _public_removal(plan, dry_run=False, archive_dir=archive_rel)
    record = {
        "overlay_id": ov_id, "label": overlay.get("label"), "workspace": ws_id,
        "date": _dt.datetime.now().isoformat(timespec="seconds"), "plan": public,
        "restore": [
            "Chaque fichier de ce dossier (hors removal.json, CLAUDE.*.block.md et "
            f"{LOCAL_BACKUP_NAME}) est à recopier au même chemin relatif depuis la racine "
            "du workspace.",
            "Bloc CLAUDE.md : recoller le contenu de CLAUDE." + ov_id + ".block.md dans "
            "CLAUDE.md, ou restaurer la sauvegarde .bak indiquée dans plan.claude_md.backup.",
            ".claude/settings.json : restaurer la sauvegarde .bak indiquée dans "
            "plan.settings.backup (ou le fichier archivé ici s'il l'a été entier).",
            ".claude/settings.local.json : restaurer la sauvegarde "
            f"{LOCAL_BACKUP_NAME} de ce dossier, indiquée dans la réponse du retrait "
            "(`settings_local.backup`), s'il y en a une ; ce fichier n'est jamais archivé.",
            "Ou ré-appliquer le module depuis Nebula, puis recopier le contenu vivant archivé "
            "(mémoire, registres, manifeste, évals, journal) pour retrouver celui du projet.",
        ],
    }
    try:
        archive_dir.mkdir(parents=True)
        (archive_dir / "removal.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as e:
        return fail(500, f"archive impossible ({archive_rel}) : {e} ; rien n'a été modifié")

    def archive_file(rel: str) -> bool:
        dst = archive_dir / rel
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            _move(ws_dir / rel, dst)
            return True
        except OSError as e:
            errors.append({"path": rel, "error": str(e)})
            return False

    moved: list[str] = []
    # 6. settings.json : archivé entier, ou .bak puis retrait ciblé.
    spath = ws_dir / _SETTINGS_REL
    if s["archive_whole"]:
        if not archive_file(_SETTINGS_REL):
            return fail(500, "settings.json non archivé : retrait interrompu avant les scripts")
        moved.append(_SETTINGS_REL)
    elif s["entries_removed"] or s["statusline_removed"]:
        backups: list[str] = []
        if not _write_backup(spath, ws_dir, backups):
            return fail(500, "sauvegarde .bak de settings.json impossible : retrait interrompu")
        settings_backup = backups[0]
        try:
            write_json(spath, s["_data"])
        except OSError as e:
            return fail(500, f"écriture de settings.json impossible : {e}")
    # 6b. settings.local.json : jamais archivé, .bak puis retrait ciblé.
    #     Le .bak va DANS l'archive du retrait (ignorée par le .gitignore
    #     livré), jamais à côté du fichier : réglages locaux (env, jetons)
    #     qu'une règle exacte `.claude/settings.local.json` ne couvrirait pas.
    lpath = ws_dir / _SETTINGS_LOCAL_REL
    if sl["entries_removed"] or sl["statusline_removed"]:
        import shutil
        lbak = archive_dir / LOCAL_BACKUP_NAME
        try:
            shutil.copy2(lpath, lbak)
        except OSError as e:
            log.warning("retrait : sauvegarde impossible %s -> %s : %s", lpath, lbak, e)
            return fail(500, "sauvegarde .bak de settings.local.json impossible : retrait interrompu")
        local_backup = lbak.relative_to(ws_dir).as_posix()
        try:
            write_json(lpath, sl["_data"])
        except OSError as e:
            return fail(500, f"écriture de settings.local.json impossible : {e}")
    # 7. Vérification relue (settings.json ET settings.local.json) : plus
    #    aucune référence vers un script à déplacer.
    to_move_scripts = {a["path"] for a in plan["archive"] if a["path"].endswith(".py")}
    for rel, path in ((_SETTINGS_REL, spath), (_SETTINGS_LOCAL_REL, lpath)):
        try:
            after = read_json_strict(path, None)
        except CorruptJsonError as e:
            return fail(500, f"{rel} illisible après retrait : {e}")
        left = sorted(_settings_script_refs(after, ws_root) & to_move_scripts)
        if left:
            return fail(500, f"{rel} référence encore " + ", ".join(left)
                        + " : scripts laissés en place, retrait interrompu")
    # 8. CLAUDE.md : bloc copié dans l'archive, .bak, retrait.
    if c["block_present"]:
        md_name = c["file"]
        md = ws_dir / md_name
        try:
            (archive_dir / f"CLAUDE.{ov_id}.block.md").write_text(c["_block"], encoding="utf-8")
            if c["whole_file"]:
                if archive_file(md_name):
                    moved.append(md_name)
            else:
                backups = []
                if _write_backup(md, ws_dir, backups):
                    claude_backup = backups[0]
                    md.write_text(c["_new_text"], encoding="utf-8")
                else:
                    errors.append({"path": md_name, "error": "sauvegarde .bak impossible, bloc laissé"})
        except OSError as e:
            errors.append({"path": md_name, "error": str(e)})
    # 9. Fichiers (scripts compris), signature EN DERNIER.
    sig = plan["signature"]
    for a in plan["archive"]:
        if a["path"] != sig and archive_file(a["path"]):
            moved.append(a["path"])
    sig_entry = next((a for a in plan["archive"] if a["path"] == sig), None)
    if sig_entry and not errors:
        if archive_file(sig):
            moved.append(sig)
    elif sig_entry:
        errors.append({"path": sig, "error": "signature laissée : retrait partiel, à relancer"})
    # 9b. Cache Python des scripts déplacés (sinon `.claude/hooks/__pycache__`
    #     empêche de retirer le dossier vidé). Best-effort, jamais bloquant.
    moved.extend(_archive_pycache(ws_dir, ws_root, moved, archive_dir))
    # 10. Dossiers du module devenus vides.
    _rmdir_empty(ws_dir, moved)
    # 11. Contrôle final : aucun hook référencé absent.
    # (une référence déjà cassée avant le retrait n'est pas de son fait).
    missing = [m for m in _missing_hook_refs(ws_dir, include_local=True)
               if m not in (missing_before or set())]
    if missing:
        return fail(500, "settings.json ou settings.local.json référence des hooks absents : "
                    + ", ".join(missing))
    if errors:
        return fail(500, "retrait partiel : relancer le retrait pour terminer")
    log.info("module %s retiré de %s : %d fichier(s) archivé(s) dans %s",
             ov_id, ws_id, len(moved), archive_rel)
    out = _public_removal(plan, dry_run=False, archive_dir=archive_rel,
                          settings_backup=settings_backup, claude_backup=claude_backup,
                          local_backup=local_backup)
    out["moved"] = moved
    return 200, out

