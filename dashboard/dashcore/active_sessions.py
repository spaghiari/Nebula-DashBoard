"""Registre des sessions Claude Code lancées depuis Nebula.

Persiste { ws_id -> { pid, launched_at, label, created } } dans
`dashboard/data/active_sessions.json`. Utilisé pour :
- afficher un indicateur "session en cours" sur la card workspace
- proposer un bouton "Stop" qui kill l'arbre de processus

Stratégie de tracking :
- `launch_script` et `launch_resume` lancent `cmd /k ...` dans une console
  neuve (CREATE_NEW_CONSOLE) ; Popen.pid = PID du cmd.exe.
- Au lancement : enregistrer { ws_id, pid, launched_at, created } où
  `created` = date de création du process (FILETIME, GetProcessTimes).
- Au stop : `taskkill /PID <pid> /T /F` kill l'arbre (cmd + claude enfant).

Liveness (Windows) -- UN SEUL snapshot Toolhelp32 pour toutes les sessions :
- PID absent du snapshot                     -> mort (pruné)
- date de création différente de `created`   -> PID recyclé -> mort (pruné)
  (entrée ancienne sans `created` : tolérée)
- cmd vivant + descendant claude.exe/node.exe -> state "running"
- cmd vivant sans descendant claude           -> state "idle"
  (terminal ouvert mais Claude fermé : `cmd /k` survit à la sortie de Claude)

Hors Windows : os.kill(pid, 0), state toujours "running" (pas d'arbre).

Stdlib only. json read/write atomique via tmp+replace.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time

from dashcore.config import ACTIVE_SESSIONS_FILE, log

_REGISTRY_PATH = ACTIVE_SESSIONS_FILE
_LOCK = threading.Lock()

# Exécutables considérés comme "Claude en cours" dans l'arbre du cmd.
# claude.exe = installeur natif ; node.exe = install npm (claude.cmd -> node).
_CLAUDE_EXES = ("claude.exe", "node.exe")


def _load() -> dict:
    if not _REGISTRY_PATH.exists():
        return {}
    try:
        data = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}


def _save(data: dict) -> None:
    _REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _REGISTRY_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, _REGISTRY_PATH)


# --- Windows : Toolhelp32 + GetProcessTimes via ctypes ----------------------

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)

    _TH32CS_SNAPPROCESS = 0x00000002
    _PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    _INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    class _PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    _k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    _k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    _k32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]
    _k32.Process32FirstW.restype = wintypes.BOOL
    _k32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]
    _k32.Process32NextW.restype = wintypes.BOOL
    _k32.CloseHandle.argtypes = [wintypes.HANDLE]
    _k32.CloseHandle.restype = wintypes.BOOL
    _k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _k32.OpenProcess.restype = wintypes.HANDLE
    _k32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    _k32.GetProcessTimes.restype = wintypes.BOOL


def _process_snapshot() -> dict[int, tuple[int, str]] | None:
    """pid -> (ppid, exe_lower) pour tous les process, en un seul appel.

    None si le snapshot échoue (ou hors Windows) : l'appelant retombe alors
    sur un check unitaire.
    """
    if sys.platform != "win32":
        return None
    snap = _k32.CreateToolhelp32Snapshot(_TH32CS_SNAPPROCESS, 0)
    if not snap or snap == _INVALID_HANDLE_VALUE:
        return None
    procs: dict[int, tuple[int, str]] = {}
    try:
        entry = _PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
        ok = _k32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            procs[int(entry.th32ProcessID)] = (
                int(entry.th32ParentProcessID), entry.szExeFile.lower())
            ok = _k32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        _k32.CloseHandle(snap)
    return procs


def process_creation_time(pid: int) -> int | None:
    """Date de création du process (FILETIME 100 ns, int) ou None.

    Sert d'identité stable : un PID recyclé a une date de création différente.
    """
    if not pid or sys.platform != "win32":
        return None
    h = _k32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not h:
        return None
    try:
        c, e, k, u = (wintypes.FILETIME() for _ in range(4))
        if not _k32.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(e),
                                    ctypes.byref(k), ctypes.byref(u)):
            return None
        return (c.dwHighDateTime << 32) | c.dwLowDateTime
    finally:
        _k32.CloseHandle(h)


def _has_claude_descendant(root: int, procs: dict[int, tuple[int, str]]) -> bool:
    """True si un descendant de `root` est claude.exe / node.exe.

    Parcours en largeur à partir de l'index ppid -> enfants. Garde contre les
    cycles (un ppid peut pointer vers un PID recyclé).
    """
    children: dict[int, list[int]] = {}
    for pid, (ppid, _exe) in procs.items():
        if pid != ppid:
            children.setdefault(ppid, []).append(pid)
    seen = {root}
    stack = list(children.get(root, ()))
    while stack:
        pid = stack.pop()
        if pid in seen:
            continue
        seen.add(pid)
        if procs.get(pid, (0, ""))[1] in _CLAUDE_EXES:
            return True
        stack.extend(children.get(pid, ()))
    return False


def is_pid_alive(pid: int) -> bool:
    """True si le PID existe encore (check unitaire, sans test de recyclage)."""
    if not pid:
        return False
    if sys.platform == "win32":
        procs = _process_snapshot()
        if procs is not None:
            return int(pid) in procs
        try:
            r = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True, timeout=3,
            )
            return str(pid) in r.stdout
        except (subprocess.TimeoutExpired, OSError):
            return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _session_state(info: dict, procs: dict[int, tuple[int, str]] | None) -> str | None:
    """'running' / 'idle' / None (mort ou PID recyclé)."""
    pid = int(info.get("pid") or 0)
    if not pid:
        return None
    if procs is None:
        # Fallback (non-Windows ou snapshot KO) : pas d'arbre -> running.
        return "running" if is_pid_alive(pid) else None
    if pid not in procs:
        return None
    created = info.get("created")
    if created:
        now_created = process_creation_time(pid)
        # now_created None = accès refusé : on ne conclut pas au recyclage.
        if now_created is not None and now_created != created:
            return None
    return "running" if _has_claude_descendant(pid, procs) else "idle"


def register(ws_id: str, pid: int, label: str | None = None) -> None:
    """Enregistre une session active dans le registre."""
    entry = {
        "pid": pid,
        "launched_at": int(time.time()),
        "label": label or ws_id,
    }
    created = process_creation_time(pid)
    if created is not None:
        entry["created"] = created
    with _LOCK:
        data = _load()
        data[ws_id] = entry
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
    """Liste les sessions actives, enrichies d'un champ `state`.

    `state` ∈ {"running", "idle"} (cf. docstring module). Si prune_dead,
    les entrées mortes / à PID recyclé sont retirées du registre. Le champ
    `state` n'est jamais persisté (calculé à chaque appel).
    """
    with _LOCK:
        data = _load()
        if not prune_dead:
            return data
        procs = _process_snapshot() if data else None
        cleaned: dict = {}
        result: dict = {}
        for ws_id, info in data.items():
            if not isinstance(info, dict):
                continue
            state = _session_state(info, procs)
            if state is None:
                log.info("active session pruned (dead/recycled pid): ws=%s pid=%s",
                         ws_id, info.get("pid"))
                continue
            cleaned[ws_id] = info
            result[ws_id] = {**info, "state": state}
        if len(cleaned) != len(data):
            _save(cleaned)
        return result


def kill(ws_id: str) -> tuple[bool, str]:
    """Kill l'arbre de processus de la session ws_id.

    Retourne (success, message). taskkill /T tue les enfants (cmd + claude).
    Refuse de tuer un PID recyclé (date de création différente).
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
    procs = _process_snapshot()
    if _session_state(info, procs) is None:
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
        import signal
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
            unregister(ws_id)
            return True, f"Session arrêtée (PID {pid})"
        except (OSError, ProcessLookupError) as e:
            return False, f"Erreur kill : {e}"
