"""Bac à sable commun des tests : à importer AVANT tout module `dashcore`.

Les chemins de `dashcore/config.py` sont résolus une fois à l'import, à
partir de `ATELIER_ROOT` (racine) et du dossier utilisateur (`USERPROFILE`
sous Windows, `HOME` ailleurs). Ce module les fait pointer vers un dossier
temporaire AVANT d'importer `dashcore`, puis vérifie que c'est bien le cas :
aucun test ne peut lire ni écrire les vraies données du poste.

Chaque classe de test appelle `reset_sandbox()` dans son `setUp` pour
repartir d'un état connu (registres vides, un template `blank`).
"""
from __future__ import annotations

import atexit
import http.client
import json
import logging
import os
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

DASHBOARD_DIR = Path(__file__).resolve().parents[1]

if any(m == "dashcore" or m.startswith("dashcore.") for m in sys.modules):
    raise RuntimeError("dashcore importé avant tests/_support.py : bac à sable impossible")

# Environnement d'origine (avant bac à sable) : pour les outils externes
# comme le navigateur des tests UI, qui ont besoin du vrai profil Windows.
ORIGINAL_ENV = dict(os.environ)

SANDBOX = Path(tempfile.mkdtemp(prefix="nebula-tests-")).resolve()
ROOT = SANDBOX / "root"
HOME = SANDBOX / "home"
ROOT.mkdir()
HOME.mkdir()

for _k in ("NEBULA_DATA_DIR", "NEBULA_HOST", "NEBULA_PORT", "NEBULA_ALLOWED_HOSTS"):
    os.environ.pop(_k, None)
os.environ["ATELIER_ROOT"] = str(ROOT)
os.environ["USERPROFILE"] = str(HOME)
os.environ["HOME"] = str(HOME)
# Git : identité et config isolées (les stash/commit des tests en ont besoin).
_gitcfg = SANDBOX / "gitconfig"
_gitcfg.write_text("[user]\n\tname = nebula-tests\n\temail = tests@nebula.invalid\n"
                   "[init]\n\tdefaultBranch = main\n[core]\n\tautocrlf = false\n",
                   encoding="utf-8")
os.environ["GIT_CONFIG_GLOBAL"] = str(_gitcfg)
os.environ["GIT_CONFIG_NOSYSTEM"] = "1"
# Aucun serveur de test ne démarre le planificateur de la boucle
# d'amélioration (il pourrait lancer de vrais jobs en arrière-plan).
os.environ["NEBULA_DISABLE_SCHEDULER"] = "1"
os.environ.pop("GIT_DIR", None)
os.environ.pop("GIT_WORK_TREE", None)

if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))

# Ordre imposé : helpers avant workspace_io (import circulaire, cf. performance.md).
import dashcore.helpers  # noqa: E402,F401
from dashcore import config  # noqa: E402

if config.ROOT != ROOT or not config.CLAUDE_HOME.is_relative_to(HOME):
    raise RuntimeError(f"bac à sable non appliqué : ROOT={config.ROOT}, CLAUDE_HOME={config.CLAUDE_HOME}")

# Les warnings du logger applicatif n'ont pas leur place dans la sortie des tests.
_log = logging.getLogger("dashboard")
_log.addHandler(logging.NullHandler())
_log.propagate = False


def _force_writable(func, path, *_):
    """Les objets git sont en lecture seule : Windows refuse de les supprimer."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def rmtree(path: Path) -> None:
    """`shutil.rmtree` qui passe sur les fichiers en lecture seule (sans suivre les liens)."""
    if not os.path.lexists(path):
        return
    if os.path.islink(path):
        os.unlink(path)
        return
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_force_writable)
    else:
        shutil.rmtree(path, onerror=_force_writable)


def rmtree_retry(path: Path, attempts: int = 20, delay: float = 0.25) -> bool:
    """`rmtree` avec nouvelles tentatives : sous Windows, un process qui vient
    d'être arrêté (navigateur des tests UI) garde ses fichiers verrouillés
    quelques instants. Retourne False si le dossier n'a pas pu être supprimé."""
    for _ in range(attempts):
        try:
            rmtree(path)
            return True
        except OSError:
            time.sleep(delay)
    return False


def _cleanup():
    if not rmtree_retry(SANDBOX):
        print(f"[tests] bac à sable non supprimé : {SANDBOX}", file=sys.stderr)


atexit.register(_cleanup)


def _rmtree_contents(d: Path) -> None:
    if not d.exists():
        return
    for child in d.iterdir():
        if child.is_symlink() or child.is_file():
            child.unlink()
        else:
            rmtree(child)


def reset_sandbox() -> None:
    """Remet ROOT et HOME dans un état minimal connu, vide les caches."""
    _rmtree_contents(ROOT)
    _rmtree_contents(HOME)
    (ROOT / "dashboard" / "data").mkdir(parents=True)
    (ROOT / "mcp").mkdir()
    write_json_file(ROOT / "mcp" / "registry.json", {"version": "1.0", "mcps": []})
    (ROOT / "scripts").mkdir()
    (ROOT / "workspaces").mkdir()
    (ROOT / "templates" / "blank").mkdir(parents=True)
    (ROOT / "templates" / "blank" / "CLAUDE.md").write_text("# {{label}}\n", encoding="utf-8")
    (HOME / ".claude" / "projects").mkdir(parents=True)
    write_json_file(HOME / ".claude" / "settings.json", {})
    from dashcore import workspace_io
    with workspace_io._STATS_CACHE_LOCK:
        workspace_io._STATS_CACHE.clear()


def write_json_file(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json_file(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def register_workspaces(entries: list[dict]) -> None:
    write_json_file(config.WORKSPACES_JSON, {"version": "1.0", "workspaces": entries})


def make_workspace(ws_id: str, path: Path | None = None, register: bool = True) -> Path:
    """Crée le dossier d'un workspace (sous workspaces/ par défaut) et l'enregistre."""
    d = path or (ROOT / "workspaces" / ws_id)
    (d / ".claude").mkdir(parents=True, exist_ok=True)
    (d / "CLAUDE.md").write_text(f"# {ws_id}\n", encoding="utf-8")
    if register:
        data = (read_json_file(config.WORKSPACES_JSON) if config.WORKSPACES_JSON.exists()
                else {"version": "1.0", "workspaces": []})
        data["workspaces"].append({"id": ws_id, "label": ws_id, "path": str(d)})
        write_json_file(config.WORKSPACES_JSON, data)
    return d


# --- Serveur HTTP en sous-process ------------------------------------------

def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class ServerProcess:
    """`server.py` lancé dans un bac à sable dédié (racine + home propres).

    Sortie redirigée vers un fichier (jamais un PIPE non lu, cf. pitfalls).
    Arrêt par le handle du process lancé (jamais par nom d'image).
    """

    def __init__(self, base: Path, extra_env: dict | None = None, host: str = "127.0.0.1",
                 real_front: bool = False):
        self.base = base
        self.root = base / "root"
        self.home = base / "home"
        self.host = host
        self.port = free_port()
        self.proc = None
        self.log_path = base / "server.log"
        self.extra_env = extra_env or {}
        self.real_front = real_front

    def build(self) -> None:
        dash = self.root / "dashboard"
        (dash / "data").mkdir(parents=True)
        if self.real_front:
            # Front réel (servi depuis ROOT/dashboard) pour les tests navigateur.
            for name in ("index.html", "app.js", "app.css"):
                shutil.copy2(DASHBOARD_DIR / name, dash / name)
            for name in ("js", "css", "assets"):
                if (DASHBOARD_DIR / name).is_dir():
                    shutil.copytree(DASHBOARD_DIR / name, dash / name)
        else:
            (dash / "app.css").write_text("body{}\n", encoding="utf-8")
            (dash / "index.html").write_text("<!doctype html><title>t</title>\n", encoding="utf-8")
        write_json_file(self.root / "mcp" / "registry.json", {"version": "1.0", "mcps": []})
        (self.root / "scripts").mkdir()
        ws = self.root / "workspaces" / "ws1"
        (ws / ".claude").mkdir(parents=True)
        (ws / "CLAUDE.md").write_text("# ws1\n", encoding="utf-8")
        write_json_file(dash / "data" / "workspaces.json", {
            "version": "1.0", "workspaces": [{"id": "ws1", "label": "ws1", "path": str(ws)}]})
        (self.home / ".claude" / "projects").mkdir(parents=True)
        write_json_file(self.home / ".claude" / "settings.json", {})

    def start(self) -> None:
        self.build()
        env = dict(os.environ)
        env.update({"ATELIER_ROOT": str(self.root), "USERPROFILE": str(self.home),
                    "HOME": str(self.home), "PYTHONIOENCODING": "utf-8"})
        env.update(self.extra_env)
        self._log = open(self.log_path, "w", encoding="utf-8")
        self.proc = subprocess.Popen(
            [sys.executable, "server.py", "--port", str(self.port), "--no-browser"],
            cwd=str(DASHBOARD_DIR), env=env, stdout=self._log, stderr=subprocess.STDOUT)
        deadline = time.time() + 15
        # Attendre la ligne de log émise APRÈS le bind : sous Windows, une
        # connexion refusée coûte ~2 s (retransmissions SYN), donc on évite
        # de sonder le port avant qu'il soit ouvert. Sonde via http.client
        # (pas urllib, qui consulte le proxy système pour 127.0.0.2 : ~5 s).
        while time.time() < deadline and self.proc.poll() is None:
            if "Ctrl+C" in self.log_text():
                break
            time.sleep(0.05)
        while time.time() < deadline:
            if self.proc.poll() is not None:
                break
            conn = http.client.HTTPConnection(self.host, self.port, timeout=2)
            try:
                conn.request("GET", "/api/overview")
                conn.getresponse().read()
                return  # le serveur répond (quel que soit le statut) : il est prêt
            except OSError:
                time.sleep(0.1)
            finally:
                conn.close()
        self.stop()
        raise RuntimeError("serveur non démarré :\n" + self.log_text()[-2000:])

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=5)
        if getattr(self, "_log", None):
            self._log.close()
            self._log = None

    def log_text(self) -> str:
        try:
            return self.log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
