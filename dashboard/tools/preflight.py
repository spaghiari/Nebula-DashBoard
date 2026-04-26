"""Preflight — vérification rapide avant push.

Usage : `python tools/preflight.py` (depuis dashboard/)

Étapes :
1. Importe tous les modules dashcore (détecte les SyntaxError, ImportError)
2. Démarre le serveur sur un port libre, en mémoire (sans navigateur)
3. Tape tous les endpoints GET sans paramètre + quelques GET workspace-scoped
4. Fait un round-trip POST/GET sur /api/ui-state
5. Vérifie que / sert bien index.html
6. Affiche un récap PASS/FAIL et exit code 0 si tout est vert

Le serveur est tué proprement à la fin. Aucun fichier modifié.
"""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DASHBOARD_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DASHBOARD_DIR))


# --1. Imports ───────────────────────────────────────────────────────────────
DASHCORE_MODULES = [
    "dashcore.config",
    "dashcore.helpers",
    "dashcore.api_workspaces",
    "dashcore.api_mcps",
    "dashcore.api_plugins",
    "dashcore.api_ui_state",
    "dashcore.system_update",
]


def check_imports() -> list[tuple[str, bool, str]]:
    results = []
    for mod in DASHCORE_MODULES:
        try:
            __import__(mod)
            results.append((f"import {mod}", True, ""))
        except Exception as e:
            results.append((f"import {mod}", False, f"{type(e).__name__}: {e}"))
    return results


# --2. Serveur ───────────────────────────────────────────────────────────────
def find_free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_server(url: str, timeout: float = 10.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except (urllib.error.URLError, ConnectionResetError, OSError):
            time.sleep(0.2)
    return False


# --3. Tests HTTP ────────────────────────────────────────────────────────────
def http_get(url: str) -> tuple[int, dict | str]:
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            body = r.read().decode("utf-8", errors="replace")
            try:
                return r.status, json.loads(body)
            except json.JSONDecodeError:
                return r.status, body
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:
        return -1, f"{type(e).__name__}: {e}"


def http_post(url: str, payload: dict) -> tuple[int, dict | str]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            body = r.read().decode("utf-8", errors="replace")
            try:
                return r.status, json.loads(body)
            except json.JSONDecodeError:
                return r.status, body
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:
        return -1, f"{type(e).__name__}: {e}"


# Endpoints GET sans paramètres — doivent tous renvoyer 200
GLOBAL_GET_ENDPOINTS = [
    "/",
    "/api/workspaces",
    "/api/mcps",
    "/api/mcps/conflicts",
    "/api/skills",
    "/api/plugins",
    "/api/plugins/installed",
    "/api/agents",
    "/api/commands",
    "/api/templates",
    "/api/snippets",
    "/api/stats",
    "/api/sanity-check",
    "/api/backups",
    "/api/journal",
    "/api/hooks/global",
    "/api/env",
    "/api/env/values",
    "/api/setup/scan",
    "/api/ui-state",
    "/api/system/version",
    "/api/search?q=test",
]


def run_http_tests(base: str) -> list[tuple[str, bool, str]]:
    results = []

    # GET globaux
    for ep in GLOBAL_GET_ENDPOINTS:
        status, body = http_get(base + ep)
        ok = status == 200
        msg = "" if ok else f"status={status} body={str(body)[:120]}"
        results.append((f"GET {ep}", ok, msg))

    # round-trip ui-state
    status0, state0 = http_get(base + "/api/ui-state")
    if status0 == 200 and isinstance(state0, dict):
        original_theme = state0.get("theme", "atelier")
        # POST nouveau thème
        s1, _ = http_post(base + "/api/ui-state", {"theme": "marine"})
        # GET vérif
        s2, state2 = http_get(base + "/api/ui-state")
        ok = (s1 == 200 and s2 == 200 and isinstance(state2, dict)
              and state2.get("theme") == "marine")
        # Restore
        http_post(base + "/api/ui-state", {"theme": original_theme})
        results.append(("ui-state round-trip POST/GET", ok,
                        "" if ok else f"s1={s1} s2={s2} state2={state2}"))
    else:
        results.append(("ui-state round-trip POST/GET", False, "GET initial KO"))

    # GET workspace-scoped sur le 1er workspace existant (si registre non vide)
    s, ws_list = http_get(base + "/api/workspaces")
    workspaces = ws_list.get("workspaces", []) if isinstance(ws_list, dict) else []
    if workspaces:
        wid = workspaces[0]["id"]
        for sub in ("config", "settings", "sessions", "plugins", "skills", "mcps"):
            ep = f"/api/workspaces/{wid}/{sub}"
            status, body = http_get(base + ep)
            ok = status == 200
            msg = "" if ok else f"status={status} body={str(body)[:120]}"
            results.append((f"GET {ep}", ok, msg))
    else:
        results.append(("workspace-scoped tests", True, "(skipped — registre vide)"))

    return results


# --4. Orchestration ─────────────────────────────────────────────────────────
def print_section(title: str, results: list[tuple[str, bool, str]]) -> int:
    print(f"\n--{title} " + "-" *(60 - len(title)))
    fails = 0
    for name, ok, msg in results:
        sym = "OK  " if ok else "FAIL"
        line = f"  [{sym}] {name}"
        if msg:
            line += f"  — {msg}"
        print(line)
        if not ok:
            fails += 1
    return fails


def main() -> int:
    print("Preflight dashboard -- verification avant push")
    print(f"  Repertoire : {DASHBOARD_DIR}")

    total_fails = 0

    # 1. Imports
    total_fails += print_section("Imports modules", check_imports())
    if total_fails:
        print("\n[FAIL] Imports KO -- on arrete la, fix ces erreurs d'abord.")
        return 1

    # 2. Démarrage serveur
    port = find_free_port()
    print(f"\n--Démarrage serveur (port {port}) " + "-" *30)
    proc = subprocess.Popen(
        [sys.executable, "server.py", "--port", str(port), "--no-browser"],
        cwd=str(DASHBOARD_DIR),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace",
    )
    base = f"http://127.0.0.1:{port}"

    try:
        if not wait_for_server(base + "/api/workspaces", timeout=10):
            try:
                _, err = proc.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                err = "(serveur ne répond pas et ne termine pas)"
            print(f"  [FAIL] serveur n'a pas démarré\n{err}")
            return 1
        print("  [OK  ] serveur démarré")

        # 3. HTTP tests
        total_fails += print_section("HTTP endpoints", run_http_tests(base))

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    # 4. Récap
    print("\n" + "=" * 64)
    if total_fails == 0:
        print("[PASS] Preflight OK -- safe to push")
        return 0
    print(f"[FAIL] Preflight KO -- {total_fails} erreur(s) a corriger avant push")
    return 1


if __name__ == "__main__":
    sys.exit(main())
