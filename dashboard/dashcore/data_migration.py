"""Migration assistée des données vers `NEBULA_DATA_DIR`.

Quand l'utilisateur déplace ses données (variable d'env `NEBULA_DATA_DIR`),
le dossier par défaut `<ROOT>/dashboard/data` contient encore ses
workspaces, sa bibliothèque de skills, etc. Sans migration, Nebula
démarrerait « vide » sur le nouveau dossier.

Principe : COPIER puis basculer (la bascule = la variable d'env elle-même).
- Seules les données utilisateur connues sont concernées (`MIGRATABLE`) ; le
  catalogue livré (`mcp_recipes.json`) et `hook_errors.log` (chemin fixe des
  hooks) restent dans le dépôt.
- JAMAIS d'écrasement : un fichier déjà présent à la destination est laissé
  tel quel (identique -> ignoré, différent -> signalé en conflit). Chaque
  copie est créée en mode exclusif (`open(..., "xb")`).
- La source n'est jamais modifiée ni supprimée : retour arrière possible en
  retirant la variable d'env. Sa suppression reste un geste de l'utilisateur.
- Au démarrage, la migration automatique ne s'applique que si la
  destination ne contient encore AUCUNE donnée migrable (premier lancement
  sur le nouveau dossier). Sinon (dossier déjà utilisé, partagé...), on se
  contente d'avertir : `python server.py --migrate-data` fusionne alors les
  seuls fichiers manquants, toujours sans écraser.
- Un marqueur `.nebula-migration.json` est écrit dans la destination : la
  migration automatique ne repasse pas (un fichier supprimé volontairement
  dans le nouveau dossier ne réapparaît pas au démarrage suivant).
"""
from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

from dashcore.config import DASHBOARD_DIR, DATA_DIR, DATA_DIR_IS_CUSTOM, log

# Dossier de données par défaut (source de la migration).
DEFAULT_DATA_DIR = DASHBOARD_DIR / "data"

# Entrées de premier niveau migrées (fichiers JSON + leur `.bak`, dossiers).
# Cf. dashcore/config.py § « Données utilisateur / runtime ».
MIGRATABLE_FILES = (
    "workspaces.json",
    "ui_state.json",
    "mcp_sync_state.json",
    "active_sessions.json",
    "mcp_recipes.local.json",
    "stats_history.json",
)
MIGRATABLE_DIRS = ("skills-library",)
MARKER_NAME = ".nebula-migration.json"


def _migratable_entries(src: Path) -> list[Path]:
    """Fichiers (chemins relatifs à `src`) concernés par la migration."""
    rels: list[Path] = []
    for name in MIGRATABLE_FILES:
        for candidate in (name, name + ".bak"):
            if (src / candidate).is_file():
                rels.append(Path(candidate))
    for name in MIGRATABLE_DIRS:
        root = src / name
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames.sort()
            for fn in sorted(filenames):
                rels.append((Path(dirpath) / fn).relative_to(src))
    return rels


def _same_content(a: Path, b: Path) -> bool:
    try:
        if a.stat().st_size != b.stat().st_size:
            return False
        return a.read_bytes() == b.read_bytes()
    except OSError:
        return False


def _has_user_data(d: Path) -> bool:
    """True si `d` contient déjà au moins une donnée migrable."""
    if any((d / n).exists() for n in MIGRATABLE_FILES):
        return True
    for n in MIGRATABLE_DIRS:
        p = d / n
        try:
            if p.is_dir() and any(p.iterdir()):
                return True
        except OSError:
            return True  # illisible : prudence, on considère « occupé »
    return False


def plan_migration(src: Path, dst: Path) -> dict:
    """Ce que ferait la migration, sans rien écrire.

    Retour : {"copy": [...], "identical": [...], "conflicts": [...]}
    (chemins relatifs, séparateur `/`).
    """
    plan = {"copy": [], "identical": [], "conflicts": []}
    if not src.is_dir():
        return plan
    for rel in _migratable_entries(src):
        target = dst / rel
        key = rel.as_posix()
        if not os.path.lexists(target):
            plan["copy"].append(key)
        elif target.is_file() and _same_content(src / rel, target):
            plan["identical"].append(key)
        else:
            plan["conflicts"].append(key)
    return plan


def _copy_exclusive(source: Path, target: Path) -> None:
    """Copie `source` vers `target` sans jamais écraser (FileExistsError sinon).

    Une copie interrompue est effacée : jamais de fichier tronqué laissé à
    la destination (il bloquerait la reprise en passant pour un conflit).
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(source, "rb") as fin, open(target, "xb") as fout:
        try:
            shutil.copyfileobj(fin, fout)
        except BaseException:
            fout.close()
            try:
                target.unlink()
            except OSError:
                pass
            raise
    try:
        shutil.copystat(source, target)
    except OSError:
        pass  # dates non conservées : sans conséquence


def migrate_data_dir(src: Path, dst: Path) -> dict:
    """Copie vers `dst` les données de `src` absentes de `dst` (jamais d'écrasement).

    Retour : plan exécuté + {"copied": [...], "errors": [{"path", "error"}],
    "ok": bool}. Écrit le marqueur `MARKER_NAME` dans `dst` si aucune
    erreur (sinon la migration automatique sera retentée au prochain démarrage).
    """
    src = Path(src)
    dst = Path(dst)
    if src.resolve() == dst.resolve():
        return {"ok": True, "copy": [], "identical": [], "conflicts": [],
                "copied": [], "errors": [], "skipped": "source = destination"}
    plan = plan_migration(src, dst)
    copied: list[str] = []
    errors: list[dict] = []
    for key in plan["copy"]:
        try:
            _copy_exclusive(src / key, dst / key)
            copied.append(key)
        except FileExistsError:
            # Apparu entre le plan et la copie : on ne l'écrase pas.
            plan["conflicts"].append(key)
        except OSError as e:
            errors.append({"path": key, "error": str(e)})
    report = {**plan, "copied": copied, "errors": errors, "ok": not errors}
    if not errors:
        try:
            dst.mkdir(parents=True, exist_ok=True)
            (dst / MARKER_NAME).write_text(json.dumps({
                "source": str(src),
                "date": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "copied": len(copied),
                "conflicts": plan["conflicts"],
            }, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as e:
            log.warning("Migration des données : marqueur non écrit (%s)", e)
    return report


def _log_report(report: dict, src: Path, dst: Path) -> None:
    log.info("Migration des données %s -> %s : %d fichier(s) copié(s), "
             "%d identique(s), %d conflit(s)", src, dst, len(report["copied"]),
             len(report["identical"]), len(report["conflicts"]))
    for key in report["conflicts"]:
        log.warning("  conflit (destination conservée, source ignorée) : %s", key)
    for err in report["errors"]:
        log.warning("  échec de copie %s : %s", err["path"], err["error"])
    if report["copied"]:
        log.info("  l'ancien dossier %s est conservé intact : supprime-le "
                 "toi-même une fois la bascule vérifiée.", src)


def startup_migration(force: bool = False, src: Path | None = None,
                      dst: Path | None = None) -> dict | None:
    """Point d'entrée du démarrage serveur (`server.py`).

    - Sans `NEBULA_DATA_DIR` : rien (None).
    - `force=False` (démarrage normal) : migre seulement si la destination
      n'a encore aucune donnée et pas de marqueur ; sinon, si la source
      contient des fichiers absents de la destination, simple avertissement.
    - `force=True` (`--migrate-data`) : fusionne les fichiers manquants,
      marqueur ou pas (toujours sans écraser).
    `src` / `dst` : surcharge pour les tests.
    """
    if src is None or dst is None:
        if not DATA_DIR_IS_CUSTOM:
            if force:
                log.warning("--migrate-data ignoré : NEBULA_DATA_DIR n'est pas défini.")
            return None
        src = src or DEFAULT_DATA_DIR
        dst = dst or DATA_DIR
    if not src.is_dir() or src.resolve() == dst.resolve():
        return None
    if not force:
        if (dst / MARKER_NAME).exists():
            return None
        if _has_user_data(dst):
            pending = plan_migration(src, dst)["copy"]
            if pending:
                log.warning("Données : %d fichier(s) de %s absents de %s "
                            "(NEBULA_DATA_DIR déjà utilisé, pas de migration "
                            "automatique). Pour les recopier sans rien écraser : "
                            "python server.py --migrate-data", len(pending), src, dst)
            return None
    report = migrate_data_dir(src, dst)
    _log_report(report, src, dst)
    return report
