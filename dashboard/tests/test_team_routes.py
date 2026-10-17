"""Routes HTTP : abonnement Claude, état de l'équipe (stale_agents),
retrait des routes de jobs de la boucle d'amélioration."""
from __future__ import annotations

import http.client
import json
import threading
import unittest
from unittest import mock

from _support import HOME, make_workspace, reset_sandbox, write_json_file

from dashcore import api_team, claude_account

import server

XHR = {"X-Nebula-XHR": "1"}
MANIFEST = {"team": {"name": "t", "prefix": "ws1"},
            "agents": [{"id": "executor", "role": "Exécutant", "model": "opus", "effort": "high",
                        "file": "team/agents/executor.md"},
                       {"id": "researcher", "role": "Chercheur", "model": "sonnet",
                        "file": "team/agents/researcher.md"}]}


def request(port, method, path, *, headers=None, body=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
    try:
        hdrs = dict(headers or {})
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            hdrs["Content-Type"] = "application/json"
        elif method == "POST":
            data = b""
        conn.request(method, path, body=data, headers=hdrs)
        resp = conn.getresponse()
        return resp.status, resp.read()
    finally:
        conn.close()


class RoutesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = server._NebulaHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.httpd.nebula_host = "127.0.0.1"
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def setUp(self):
        reset_sandbox()
        self.ws = make_workspace("ws1")
        write_json_file(self.ws / ".claude" / "team.json", MANIFEST)
        for a in MANIFEST["agents"]:
            p = self.ws / ".claude" / a["file"]
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(f"# {a['id']}\n", encoding="utf-8")
        claude_account.clear_cache()

    def req(self, *a, **kw):
        return request(self.port, *a, **kw)

    def test_subscription_sans_secret(self):
        write_json_file(HOME / ".claude" / ".credentials.json", {"claudeAiOauth": {
            "accessToken": "SECRET-acces", "refreshToken": "SECRET-refresh",
            "subscriptionType": "pro", "rateLimitTier": "default_claude_pro"}})
        with mock.patch.object(claude_account, "_from_cli", return_value=None), \
                mock.patch.object(claude_account, "_cli_exists", return_value=False):
            st, raw = self.req("GET", "/api/claude/subscription?ws=ws1")
            self.assertEqual(st, 200, raw)
            self.assertNotIn(b"SECRET", raw)
            p = json.loads(raw)
            self.assertEqual(p["plan"], "pro")
            codes = {w["code"] for w in p["warnings"]}
            self.assertIn("pro_opus", codes)
            self.assertIn("pro_effort", codes)
            self.assertNotIn("pro_auto", {r["code"] for r in p["rules"]})
            st, raw = self.req("GET", "/api/claude/subscription")
            self.assertEqual(st, 200)
            self.assertEqual(json.loads(raw)["warnings"], [])
            self.assertEqual(self.req("GET", "/api/claude/subscription?ws=absent")[0], 404)
            self.assertEqual(self.req("GET", "/api/claude/subscription?ws=a%2Fb")[0], 400)

    def test_team_stale_agents_puis_agents_config_vide(self):
        api_team.generate_agents(self.ws, {"name": "ws1", "label": "ws1"})
        st, raw = self.req("GET", "/api/workspaces/ws1/team")
        self.assertEqual(st, 200, raw)
        self.assertEqual(json.loads(raw)["stale_agents"], [])
        (self.ws / ".claude" / "team" / "agents" / "researcher.md").write_text(
            "# autre\n", encoding="utf-8")
        self.assertEqual(json.loads(self.req("GET", "/api/workspaces/ws1/team")[1])["stale_agents"],
                         ["researcher"])
        st, raw = self.req("POST", "/api/workspaces/ws1/team/agents-config",
                           body={"agents": {}}, headers=XHR)
        self.assertEqual(st, 200, raw)
        p = json.loads(raw)
        self.assertFalse(p["written"])
        self.assertEqual(p["generated"], [".claude/agents/ws1-researcher.md"])
        self.assertEqual(json.loads(self.req("GET", "/api/workspaces/ws1/team")[1])["stale_agents"], [])

    def _pending(self):
        d = self.ws / ".claude" / "journal"
        d.mkdir(parents=True, exist_ok=True)
        (d / "changes.jsonl").write_text(json.dumps(
            {"iteration": 1, "status": "pending", "config_version": "abc"}) + "\n", encoding="utf-8")

    def test_agents_config_vide_sous_pending(self):
        api_team.generate_agents(self.ws, {"name": "ws1", "label": "ws1"})
        self._pending()
        url = "/api/workspaces/ws1/team/agents-config"
        manifest = self.ws / ".claude" / "team.json"
        before = manifest.read_bytes()
        # Rien ne changerait : 200, rien d'écrit.
        st, raw = self.req("POST", url, body={"agents": {}}, headers=XHR)
        self.assertEqual(st, 200, raw)
        p = json.loads(raw)
        self.assertFalse(p["written"])
        self.assertEqual(p["generated"], [])
        self.assertEqual(manifest.read_bytes(), before)
        # Un agent changerait : 409 pending, rien d'écrit.
        agent = self.ws / ".claude" / "agents" / "ws1-researcher.md"
        agent.write_text(agent.read_text(encoding="utf-8") + "\nmodif\n", encoding="utf-8")
        edited = agent.read_bytes()
        st, raw = self.req("POST", url, body={"agents": {}}, headers=XHR)
        self.assertEqual(st, 409, raw)
        self.assertEqual(json.loads(raw)["pending"]["iteration"], 1)
        self.assertEqual(agent.read_bytes(), edited)

    def test_stale_agent_fichier_disparu(self):
        api_team.generate_agents(self.ws, {"name": "ws1", "label": "ws1"})
        (self.ws / ".claude" / "agents" / "ws1-researcher.md").unlink()
        st, raw = self.req("GET", "/api/workspaces/ws1/team")
        self.assertIn("researcher", json.loads(raw)["stale_agents"])

    def test_routes_de_jobs_retirees(self):
        self.assertEqual(self.req("GET", "/api/workspaces/ws1/improvement/job")[0], 404)
        for name in ("run", "abandon", "stop", "auto"):
            st, _ = self.req("POST", f"/api/workspaces/ws1/improvement/{name}", body={}, headers=XHR)
            self.assertEqual(st, 404, name)
        st, raw = self.req("GET", "/api/workspaces/ws1/improvement")
        self.assertEqual(st, 200, raw)
        p = json.loads(raw)
        for gone in ("job", "auto", "next_step", "last_measure"):
            self.assertNotIn(gone, p)


if __name__ == "__main__":
    unittest.main()
