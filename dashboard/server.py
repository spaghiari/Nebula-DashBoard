"""
Dashboard Claude Workspace — point d'entrée.

- Bind 127.0.0.1 uniquement (aucune exposition réseau).
- Sert dashboard/index.html et expose /api/* pour piloter le workspace.
- Aucune dépendance externe (stdlib only).

Lancement :
    python server.py                # port 4777 par défaut
    python server.py --port 4800    # port custom
    python server.py --debug        # logs DEBUG
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from dashcore.config import (
    HOST, DEFAULT_PORT, DASHBOARD_DIR, WORKSPACES_JSON, MCP_REGISTRY,
    ENV_FILE, BACKUPS_DIR, SNIPPETS_DIR, LOGS_DIR, STATIC_TYPES, log,
)
from dashcore.helpers import (
    setup_logging, read_json, safe_id, load_env_local, port_free, find_port,
    set_env_var, delete_env_var, launch_script, open_target,
    backup_claude_config, list_backups, read_journal, append_journal, clear_journal,
    all_stats, sanity_check, global_search, cleanup_orphan_bats,
)
from dashcore.api_workspaces import (
    list_templates, duplicate_template, delete_template,
    create_workspace, update_workspace, delete_workspace, duplicate_workspace,
    read_workspace_config, write_workspace_file, export_workspace, launch_resume,
    list_sessions_for_workspace, read_session_messages,
    get_workspace_settings, save_workspace_settings, patch_workspace_settings,
    get_global_hooks, set_global_hooks,
)
from dashcore.api_mcps import (
    add_or_update_mcp, delete_mcp, sync_workspace_mcps, sync_all_workspaces,
    workspace_mcp_status, mcp_live_check, test_mcp,
)
from dashcore.api_plugins import (
    list_plugins, list_marketplace_plugins, read_plugin_readme,
    list_installed_plugins, uninstall_plugin,
    install_plugin_cli, enable_plugin_cli, disable_plugin_cli, uninstall_plugin_cli,
    get_workspace_plugins, set_workspace_plugin,
    list_skills_global, list_skills_for_workspace,
    create_skill, delete_skill, get_skill_content, save_skill_content,
    copy_skill_to_workspace,
    list_agents, list_commands,
    create_fileitem, delete_fileitem, get_fileitem_content, save_fileitem_content,
)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        log.info("%s %s", self.address_string(), fmt % args)

    def handle_one_request(self):
        try:
            super().handle_one_request()
        except Exception:
            log.exception("Unhandled exception in request handler")
            try:
                self._send_json(500, {"error": "internal server error"})
            except Exception:
                pass

    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path):
        if not path.exists() or not path.is_file():
            self._send_json(404, {"error": "not found"})
            return
        try:
            path.resolve().relative_to(DASHBOARD_DIR.resolve())
        except ValueError:
            self._send_json(403, {"error": "forbidden"})
            return
        ct = STATIC_TYPES.get(path.suffix.lower(), "application/octet-stream")
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    def do_GET(self):
        p = urlparse(self.path).path

        if p in ("/", "/index.html"):
            self._send_file(DASHBOARD_DIR / "index.html"); return

        if p == "/api/workspaces":
            self._send_json(200, read_json(WORKSPACES_JSON, {"version":"1.0","workspaces":[]})); return
        if p == "/api/mcps":
            self._send_json(200, read_json(MCP_REGISTRY, {"version":"1.0","mcps":[]})); return
        if p == "/api/env":
            env = load_env_local()
            self._send_json(200, {"keys": sorted(env.keys()), "file": str(ENV_FILE), "exists": ENV_FILE.exists()}); return
        if p == "/api/env/values":
            env = load_env_local()
            self._send_json(200, {"values": env, "file": str(ENV_FILE), "exists": ENV_FILE.exists()}); return
        if p == "/api/snippets":
            out = {}
            if SNIPPETS_DIR.exists():
                for f in SNIPPETS_DIR.glob("*.md"):
                    out[f.stem] = f.read_text(encoding="utf-8")
            self._send_json(200, out); return
        if p.startswith("/api/workspaces/") and p.endswith("/mcps"):
            ws_id = p.split("/")[3]
            status, payload = workspace_mcp_status(ws_id)
            self._send_json(status, payload); return

        if p.startswith("/api/workspaces/") and p.endswith("/config"):
            ws_id = p.split("/")[3]
            status, payload = read_workspace_config(ws_id)
            self._send_json(status, payload); return

        if p == "/api/stats":
            self._send_json(200, all_stats()); return

        if p == "/api/sanity-check":
            self._send_json(200, sanity_check()); return

        if p == "/api/backups":
            self._send_json(200, {"dir": str(BACKUPS_DIR), "items": list_backups()}); return

        if p == "/api/journal":
            self._send_json(200, {"entries": read_journal()[-100:]}); return

        if p == "/api/templates":
            self._send_json(200, {"templates": list_templates()}); return

        if p == "/api/plugins":
            self._send_json(200, list_plugins()); return

        if p == "/api/plugins/installed":
            self._send_json(200, list_installed_plugins()); return

        m = re.match(r"^/api/plugins/marketplace/([a-zA-Z0-9_-]+)$", p)
        if m:
            self._send_json(200, list_marketplace_plugins(m.group(1))); return

        m = re.match(r"^/api/plugins/marketplace/([a-zA-Z0-9_-]+)/(plugins|external_plugins)/([a-zA-Z0-9_-]+)/readme$", p)
        if m:
            s, r = read_plugin_readme(m.group(1), m.group(2), m.group(3))
            self._send_json(s, r); return

        if p == "/api/skills":
            self._send_json(200, {"global": list_skills_global()}); return

        if p.startswith("/api/workspaces/") and p.endswith("/skills"):
            ws_id = p.split("/")[3]
            if not safe_id(ws_id):
                self._send_json(400, {"error":"id invalide"}); return
            self._send_json(200, list_skills_for_workspace(ws_id)); return

        if p.startswith("/api/workspaces/") and p.endswith("/plugins"):
            ws_id = p.split("/")[3]
            if not safe_id(ws_id):
                self._send_json(400, {"error":"id invalide"}); return
            self._send_json(200, {"plugins": get_workspace_plugins(ws_id)}); return

        m = re.match(r"^/api/skills/(global|workspace:[a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+)/content$", p)
        if m:
            s, r = get_skill_content(m.group(1), m.group(2))
            self._send_json(s, r); return

        m = re.match(r"^/api/(agents|commands)(?:/workspace/([a-zA-Z0-9_-]+))?$", p)
        if m:
            kind = m.group(1)
            ws = m.group(2)
            data = list_agents(ws) if kind == "agents" else list_commands(ws)
            self._send_json(200, data); return

        m = re.match(r"^/api/(agents|commands)/(global|workspace:[a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+)/content$", p)
        if m:
            s, r = get_fileitem_content(m.group(1), m.group(2), m.group(3))
            self._send_json(s, r); return

        if p.startswith("/api/workspaces/") and p.endswith("/settings"):
            ws_id = p.split("/")[3]
            s, r = get_workspace_settings(ws_id)
            self._send_json(s, r); return

        if p.startswith("/api/workspaces/") and p.endswith("/sessions"):
            ws_id = p.split("/")[3]
            self._send_json(200, {"sessions": list_sessions_for_workspace(ws_id)}); return

        m = re.match(r"^/api/workspaces/([a-zA-Z0-9_-]+)/sessions/([^/]+)$", p)
        if m:
            s, r = read_session_messages(m.group(1), m.group(2))
            self._send_json(s, r); return

        if p == "/api/hooks/global":
            self._send_json(200, {"hooks": get_global_hooks()}); return

        if p.startswith("/api/search"):
            qs = parse_qs(urlparse(self.path).query)
            q = (qs.get("q", [""])[0])
            self._send_json(200, global_search(q)); return

        m = re.match(r"^/api/workspaces/([a-zA-Z0-9_-]+)/export$", p)
        if m:
            status, data = export_workspace(m.group(1))
            if status != 200:
                self._send_json(status, data); return
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", f'attachment; filename="{m.group(1)}.zip"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        m = re.match(r"^/api/workspaces/([a-zA-Z0-9_-]+)/mcp-check$", p)
        if m:
            s, r = mcp_live_check(m.group(1))
            self._send_json(s, r); return

        safe = p.lstrip("/").replace("..", "")
        self._send_file(DASHBOARD_DIR / safe)

    def do_POST(self):
        p = urlparse(self.path).path
        body = self._read_json_body()
        if body is None:
            self._send_json(400, {"error":"JSON invalide"}); return

        if p.startswith("/api/launch/"):
            ws_id = p[len("/api/launch/"):]
            if not safe_id(ws_id):
                self._send_json(400, {"error":"id invalide"}); return
            ok, msg = launch_script(f"launch-{ws_id}.bat")
            self._send_json(200 if ok else 500, {"ok": ok, "message": msg}); return

        if p == "/api/env":
            s, r = set_env_var((body or {}).get("key", ""), (body or {}).get("value", ""))
            self._send_json(s, r); return

        if p == "/api/workspaces":
            s, r = create_workspace(body); self._send_json(s, r); return

        if p.startswith("/api/workspaces/") and p.endswith("/update"):
            ws_id = p.split("/")[3]
            s, r = update_workspace(ws_id, body or {})
            self._send_json(s, r); return

        if p == "/api/mcps":
            s, r = add_or_update_mcp(body); self._send_json(s, r); return

        if p == "/api/mcps/import":
            results = []
            ws_override = body.get("workspaces", [])

            # Format registre direct : objet avec "id" ou tableau d'objets
            if "id" in body:
                entries = [body]
            elif isinstance(body.get("mcps"), list):
                entries = body["mcps"]
            else:
                entries = None

            if entries is not None:
                for cfg in entries:
                    mcp_id = cfg.get("id", "")
                    if not safe_id(mcp_id):
                        results.append({"id": mcp_id, "ok": False, "error": "id invalide"}); continue
                    mcp = dict(cfg)
                    if ws_override:
                        mcp["workspaces"] = ws_override
                    mcp.setdefault("status", "disponible")
                    s, r = add_or_update_mcp(mcp)
                    results.append({"id": mcp_id, "ok": s < 400, **r})
                self._send_json(200, {"ok": True, "results": results}); return

            # Format Claude : {"mcpServers": {"name": {...}}}
            servers = body.get("mcpServers") or body.get("servers") or {}
            if not isinstance(servers, dict):
                self._send_json(400, {"error": "Format non reconnu. Coller soit un objet MCP direct (avec \"id\"), soit {\"mcpServers\":{...}}"}); return
            for name, cfg in servers.items():
                if not safe_id(name):
                    results.append({"id": name, "ok": False, "error": "id invalide"}); continue
                mcp = {
                    "id": name,
                    "name": cfg.get("name", name),
                    "transport": cfg.get("transport") or cfg.get("type") or ("http" if cfg.get("url") else "stdio"),
                    "command": cfg.get("command", ""),
                    "args": cfg.get("args", []),
                    "env": cfg.get("env", {}),
                    "url": cfg.get("url", ""),
                    "workspaces": ws_override or cfg.get("workspaces", []),
                    "status": "disponible",
                }
                s, r = add_or_update_mcp(mcp)
                results.append({"id": name, "ok": s < 400, **r})
            self._send_json(200, {"ok": True, "results": results}); return

        if p.startswith("/api/mcps/") and p.endswith("/test"):
            mcp_id = p.split("/")[3]
            s, r = test_mcp(mcp_id); self._send_json(s, r); return

        if p.startswith("/api/workspaces/") and p.endswith("/sync-mcps"):
            ws_id = p.split("/")[3]
            s, r = sync_workspace_mcps(ws_id); self._send_json(s, r); return

        if p == "/api/sync-all":
            s, r = sync_all_workspaces(); self._send_json(s, r); return

        if p == "/api/open":
            key = (body or {}).get("target", "")
            ok, msg = open_target(key)
            self._send_json(200 if ok else 400, {"ok": ok, "message": msg}); return

        if p == "/api/backup":
            ok, msg = backup_claude_config()
            self._send_json(200 if ok else 400, {"ok": ok, "message": msg}); return

        if p == "/api/journal":
            text = (body or {}).get("text", "").strip()
            if not text:
                self._send_json(400, {"error": "texte vide"}); return
            append_journal(text)
            self._send_json(200, {"ok": True}); return

        if p == "/api/templates/duplicate":
            s, r = duplicate_template(body or {})
            self._send_json(s, r); return

        if p == "/api/skills":
            s, r = create_skill(body or {})
            self._send_json(s, r); return

        if p == "/api/skills/copy":
            s, r = copy_skill_to_workspace(body or {})
            self._send_json(s, r); return

        m = re.match(r"^/api/skills/(global|workspace:[a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+)/content$", p)
        if m:
            s, r = save_skill_content(m.group(1), m.group(2), (body or {}).get("content", ""))
            self._send_json(s, r); return

        if p.startswith("/api/workspaces/") and p.endswith("/plugins"):
            ws_id = p.split("/")[3]
            s, r = set_workspace_plugin(
                ws_id,
                (body or {}).get("plugin_id", ""),
                (body or {}).get("enabled"),
            )
            self._send_json(s, r); return

        if p.startswith("/api/launch-resume/"):
            ws_id = p[len("/api/launch-resume/"):]
            ok, msg = launch_resume(ws_id)
            self._send_json(200 if ok else 500, {"ok": ok, "message": msg}); return

        if p == "/api/workspaces/duplicate":
            s, r = duplicate_workspace(body or {})
            self._send_json(s, r); return

        if p == "/api/agents":
            s, r = create_fileitem("agents", body or {})
            self._send_json(s, r); return
        if p == "/api/commands":
            s, r = create_fileitem("commands", body or {})
            self._send_json(s, r); return

        m = re.match(r"^/api/(agents|commands)/(global|workspace:[a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+)/content$", p)
        if m:
            s, r = save_fileitem_content(m.group(1), m.group(2), m.group(3), (body or {}).get("content", ""))
            self._send_json(s, r); return

        if p.startswith("/api/workspaces/") and p.endswith("/settings"):
            ws_id = p.split("/")[3]
            s, r = save_workspace_settings(ws_id, (body or {}).get("content", "{}"))
            self._send_json(s, r); return

        m = re.match(r"^/api/workspaces/([a-zA-Z0-9_-]+)/file$", p)
        if m:
            s, r = write_workspace_file(m.group(1), (body or {}).get("filename", ""), (body or {}).get("content", ""))
            self._send_json(s, r); return

        m = re.match(r"^/api/workspaces/([a-zA-Z0-9_-]+)/settings/([a-zA-Z]+)$", p)
        if m:
            s, r = patch_workspace_settings(m.group(1), m.group(2), (body or {}).get("value"))
            self._send_json(s, r); return

        if p == "/api/hooks/global":
            hooks = (body or {}).get("hooks") or {}
            s, r = set_global_hooks(hooks)
            self._send_json(s, r); return

        if p == "/api/plugins/uninstall-soft":
            pid = (body or {}).get("plugin_id", "")
            rm = bool((body or {}).get("remove_files"))
            s, r = uninstall_plugin(pid, remove_files=rm)
            self._send_json(s, r); return

        if p == "/api/plugins/install":
            spec = (body or {}).get("spec", "")
            s, r = install_plugin_cli(spec)
            self._send_json(s, r); return

        if p == "/api/plugins/enable":
            pid = (body or {}).get("plugin_id", "")
            s, r = enable_plugin_cli(pid)
            self._send_json(s, r); return

        if p == "/api/plugins/disable":
            pid = (body or {}).get("plugin_id", "")
            s, r = disable_plugin_cli(pid)
            self._send_json(s, r); return

        if p == "/api/plugins/uninstall":
            pid = (body or {}).get("plugin_id", "")
            s, r = uninstall_plugin_cli(pid)
            self._send_json(s, r); return

        if p == "/api/cleanup/orphan-bats":
            self._send_json(200, cleanup_orphan_bats()); return

        self._send_json(404, {"error":"route inconnue"})

    def do_DELETE(self):
        u = urlparse(self.path)
        p = u.path
        qs = {k: v[0] for k, v in parse_qs(u.query).items()}
        if p.startswith("/api/workspaces/"):
            ws_id = p[len("/api/workspaces/"):]
            purge = qs.get("purge", "").lower() in ("1", "true", "yes")
            s, r = delete_workspace(ws_id, purge=purge); self._send_json(s, r); return
        if p.startswith("/api/mcps/"):
            mcp_id = p[len("/api/mcps/"):]
            s, r = delete_mcp(mcp_id); self._send_json(s, r); return
        if p.startswith("/api/env/"):
            key = p[len("/api/env/"):]
            s, r = delete_env_var(key); self._send_json(s, r); return
        if p == "/api/journal":
            clear_journal()
            self._send_json(200, {"ok": True}); return
        if p.startswith("/api/templates/"):
            tpl_id = p[len("/api/templates/"):]
            s, r = delete_template(tpl_id); self._send_json(s, r); return
        if p.startswith("/api/skills/"):
            rest = p[len("/api/skills/"):]
            m = re.match(r"^(global|workspace:[a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+)$", rest)
            if not m:
                self._send_json(400, {"error": "format : /api/skills/<scope>/<name>"}); return
            s, r = delete_skill(m.group(1), m.group(2))
            self._send_json(s, r); return
        m = re.match(r"^/api/(agents|commands)/(global|workspace:[a-zA-Z0-9_-]+)/([a-zA-Z0-9_-]+)$", p)
        if m:
            s, r = delete_fileitem(m.group(1), m.group(2), m.group(3))
            self._send_json(s, r); return
        self._send_json(404, {"error":"route inconnue"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--debug", action="store_true", help="Active le niveau DEBUG")
    args = ap.parse_args()

    setup_logging(logging.DEBUG if args.debug else logging.INFO)

    port = args.port
    if not port_free(HOST, port):
        new = find_port(HOST, port + 1)
        log.warning("Port %d occupé → fallback sur %d", port, new)
        port = new

    server = ThreadingHTTPServer((HOST, port), Handler)
    url = f"http://{HOST}:{port}/"
    log.info("Dashboard Claude Workspace — %s", url)
    log.info("  registry : %s", MCP_REGISTRY)
    log.info("  .env.local : %s  (%s)", ENV_FILE, "présent" if ENV_FILE.exists() else "absent")
    log.info("  logs : %s", LOGS_DIR / "dashboard.log")
    log.info("Ctrl+C pour arrêter.")
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Arrêt demandé (Ctrl+C).")
        server.shutdown()


if __name__ == "__main__":
    main()
