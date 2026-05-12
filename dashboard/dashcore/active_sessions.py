"""Registre des sessions Claude Code lancées depuis Nebula.

Persiste { ws_id -> { pid, launched_at, label } } dans
`dashboard/data/active_sessions.json`. Utilisé pour :
- afficher un indicateur "session en cours" sur la card workspace
- proposer un bouton "Stop" qui kill l'arbre de processus

Stratégie de tracking :
- Modifier `launch_script` et `launch_resume` (workspace_io / api_workspaces)
  pour utiliser `cmd /k` directement (au lieu de `cmd /c start`). Popen.pid
  reste alors valide tant que la fenêtre cmd est ouverte.
- Au lancement : enregistrer { ws_id, pid, launched_at }.
- Au stop : `taskkill /PID <pid> /T /F` kill l'arbre (cmd + claude enfant).
- Liveness check : `tasklist /FI "PID eq <pid>" /NH` — sortie vide = mort.

Stdlib only. Sécurité : json read/write atomique via tmp+replace.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

from dashcore.config import ROOT, log

_REGISTRY_PATH = ROOT / "dashboard" / "data" / "active_sessions.json"
_LOCK = threading.Lock()


def _load() -> dict:
    if not _REGISTRY_PATH.exists():
        return {}
    try:
        return json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save(data: dict) -> None:
    _REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _REGISTRY_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(_REGISTRY_PATH)


def is_pid_alive(pid: int) -> bool:
    """True si le PID existe encore. Windows : tasklist, autres : os.kill(0)."""
    if not pid:
        return False
    if sys.platform == "win32":
        try:
            r = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True, timeout=3,
            )
            return str(pid) in r.stdout
        except (subprocess.TimeoutExpired, OSError):
            return False
    else:
        import os
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


def register(ws_id: str, pid: int, label: str | None = None) -> None:
    """Enregistre une session active dans le registre."""
    with _LOCK:
        data = _load()
        data[ws_id] = {
            "pid": pid,
            "launched_at": int(time.time()),
            "label": label or ws_id,
        }
        _save(data)
    log.info("active session registered: ws=%s pid=%s", ws_id, pid)


def unregister(ws_id: str) -> None:
    """Retire une session du registre (appelé après stop ou cleanup)."""
    with _LOCK:
        data = _load()
        if ws_id in data:
            data.pop(ws_id)
            _save(data)


def list_active(*, prune_dead: bool = True) -> dict:
    """Liste les sessions actives. Si prune_dead, retire les entrées mortes."""
    with _LOCK:
        data = _load()
        if not prune_dead:
            return data
        cleaned = {}
        changed = False
        for ws_id, info in data.items():
            if is_pid_alive(info.get("pid", 0)):
                cleaned[ws_id] = info
            else:
                changed = True
                log.info("active session pruned (dead pid): ws=%s pid=%s",
                         ws_id, info.get("pid"))
        if changed:
            _save(cleaned)
        return cleaned


def kill(ws_id: str) -> tuple[bool, str]:
    """Kill l'arbre de processus de la session ws_id.

    Retourne (success, message). taskkill /T tue les enfants (cmd + claude).
    """
    with _LOCK:
        data = _load()
        info = data.get(ws_id)
    if not info:
        return False, "Pas de session active enregistrée pour ce workspace"
    pid = info.get("pid", 0)
    if not pid:
        unregister(ws_id)
        return False, "PID invalide dans le registre"
    if not is_pid_alive(pid):
        unregister(ws_id)
        return False, "Process déjà terminé (registre nettoyé)"
    if sys.platform == "win32":
        try:
            r = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True, text=True, timeout=10,
            )
            if r.returncode == 0:
                unregister(ws_id)
                log.info("active session killed: ws=%s pid=%s", ws_id, pid)
                return True, f"Session arrêtée (PID {pid} + enfants)"
            return False, f"taskkill échec : {r.stderr.strip() or r.stdout.strip()}"
        except (subprocess.TimeoutExpired, OSError) as e:
            return False, f"Erreur taskkill : {e}"
    else:
        import os
        import signal
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
            unregister(ws_id)
            return True, f"Session arrêtée (PID {pid})"
        except (OSError, ProcessLookupError) as e:
            return False, f"Erreur kill : {e}"
