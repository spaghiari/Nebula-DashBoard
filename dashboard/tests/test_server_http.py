"""Serveur HTTP réel en sous-process : Host, Origin, corps, statique, export.

Bac à sable dédié (ATELIER_ROOT + home propres), port libre, arrêt par le
handle du process lancé.
"""
from __future__ import annotations

import http.client
import json
import sys
import unittest

from _support import SANDBOX, ServerProcess, rmtree


def request(port, method, path, *, host=None, headers=None, body=None, raw_body=None):
    """Requête brute (en-tête Host maîtrisé). Retourne (status, headers, octets)."""
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        conn.putheader("Host", host or f"127.0.0.1:{port}")
        data = raw_body if raw_body is not None else (
            json.dumps(body).encode("utf-8") if body is not None else None)
        hdrs = dict(headers or {})
        if data is not None:
            hdrs.setdefault("Content-Type", "application/json")
            hdrs["Content-Length"] = str(len(data))
        for k, v in hdrs.items():
            conn.putheader(k, v)
        conn.endheaders(data)
        resp = conn.getresponse()
        return resp.status, dict(resp.getheaders()), resp.read()
    finally:
        conn.close()


XHR = {"X-Nebula-XHR": "1"}


class ServerSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = SANDBOX / "http"
        rmtree(cls.base)
        cls.srv = ServerProcess(cls.base)
        cls.srv.start()
        cls.port = cls.srv.port

    @classmethod
    def tearDownClass(cls):
        cls.srv.stop()
        rmtree(cls.base)

    def req(self, *a, **kw):
        return request(self.port, *a, **kw)

    def test_overview_200(self):
        status, _, data = self.req("GET", "/api/overview")
        self.assertEqual(status, 200)
        payload = json.loads(data)
        self.assertEqual([w["id"] for w in payload["workspaces"]], ["ws1"])
        self.assertIn("ws1", payload["ws_mcps"])
        self.assertEqual(payload["team_routing"], {})  # aucun module claude-team actif

    def test_route_team_routing(self):
        """POST /api/workspaces/<id>/team/routing : garde XHR, 404 sans manifeste,
        écriture de la section par défaut puis du mode, 400 si invalide."""
        self.assertEqual(self.req("POST", "/api/workspaces/ws1/team/routing", body={"mode": "auto"})[0], 403)
        status, _, data = self.req("POST", "/api/workspaces/ws1/team/routing", body={"mode": "auto"}, headers=XHR)
        self.assertEqual(status, 404)
        self.assertIn("inactif", json.loads(data)["error"])
        self.assertEqual(self.req("POST", "/api/workspaces/absent/team/routing", body={}, headers=XHR)[0], 404)
        manifest = self.srv.root / "workspaces" / "ws1" / ".claude" / "team.json"
        manifest.write_text(json.dumps({"team": {"name": "t", "prefix": "ws1"}, "agents": []}), encoding="utf-8")
        try:
            status, _, data = self.req("POST", "/api/workspaces/ws1/team/routing", body={"mode": "assiste"}, headers=XHR)
            self.assertEqual(status, 200, data)
            payload = json.loads(data)
            self.assertTrue(payload["written"])
            self.assertEqual((payload["routing"]["mode"], payload["routing"]["declared"]), ("assiste", True))
            saved = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(saved["routing"]["mode"], "assiste")
            self.assertEqual(saved["routing"]["modes"], ["manuel", "assiste", "auto"])
            status, _, data = self.req("POST", "/api/workspaces/ws1/team/routing", body={"review_gate": "parfois"}, headers=XHR)
            self.assertEqual(status, 400)
            self.assertIn("relecture", json.loads(data)["error"])
            status, _, data = self.req("GET", "/api/workspaces/ws1/team")
            self.assertEqual(json.loads(data)["routing"]["mode"], "assiste")
        finally:
            manifest.unlink()

    def test_overlays_avec_usage(self):
        status, _, data = self.req("GET", "/api/overlays")
        self.assertEqual(status, 200)
        payload = json.loads(data)
        self.assertIn("overlays", payload)
        self.assertIsInstance(payload["usage"], dict)

    def test_routes_claude_team(self):
        # Workspace sans manifeste : routes 200, module inactif ; id inconnu : 404.
        status, _, data = self.req("GET", "/api/workspaces/ws1/team")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data), {"active": False, "agents": [], "manifest": None})
        status, _, data = self.req("GET", "/api/workspaces/ws1/improvement")
        self.assertEqual(status, 200)
        payload = json.loads(data)
        self.assertFalse(payload["active"])
        self.assertEqual(payload["stats"]["iterations"], 0)
        self.assertIn("registers", payload)
        self.assertEqual(self.req("GET", "/api/workspaces/absent/team")[0], 404)
        self.assertEqual(self.req("GET", "/api/workspaces/absent/improvement")[0], 404)

    def test_localhost_accepte(self):
        self.assertEqual(self.req("GET", "/api/overview", host=f"localhost:{self.port}")[0], 200)

    def test_host_etranger_403(self):
        for host in ("evil.example", f"evil.example:{self.port}", f"127.0.0.1:{self.port + 1}"):
            with self.subTest(host=host):
                self.assertEqual(self.req("GET", "/api/overview", host=host)[0], 403)

    def test_origin_etrangere_sur_post_403(self):
        status, _, data = self.req("POST", "/api/ui-state", body={"theme": "nebula"},
                                   headers={**XHR, "Origin": "http://evil.example"})
        self.assertEqual(status, 403)
        self.assertIn("Origine", json.loads(data)["error"])

    def test_origin_locale_sur_post_200(self):
        status, _, _ = self.req("POST", "/api/ui-state", body={"theme": "nebula"},
                                headers={**XHR, "Origin": f"http://127.0.0.1:{self.port}"})
        self.assertEqual(status, 200)

    def test_post_sans_header_xhr_403(self):
        self.assertEqual(self.req("POST", "/api/ui-state", body={"theme": "nebula"})[0], 403)

    def test_corps_non_objet_400(self):
        for raw in (b"[1, 2]", b'"texte"', b"42", b"{pas du json"):
            with self.subTest(raw=raw):
                status, _, data = self.req("POST", "/api/ui-state", raw_body=raw, headers=XHR)
                self.assertEqual(status, 400)
                self.assertIn("error", json.loads(data))

    def test_statique_liste_blanche(self):
        self.assertEqual(self.req("GET", "/app.css")[0], 200)
        self.assertEqual(self.req("GET", "/")[0], 200)
        for path in ("/server.py", "/dashcore/config.py", "/data/workspaces.json",
                     "/tools/preflight.py", "/js/../server.py", "/js/.hidden.js",
                     "/%2e%2e/server.py", "/js\\..\\server.py"):
            with self.subTest(path=path):
                self.assertEqual(self.req("GET", path)[0], 404)

    def test_export_refuse_en_get(self):
        status, headers, _ = self.req("GET", "/api/workspaces/ws1/export")
        self.assertNotEqual(status, 200)
        self.assertNotIn("zip", headers.get("Content-Type", ""))

    def test_export_en_post_avec_xhr(self):
        status, headers, data = self.req("POST", "/api/workspaces/ws1/export", headers=XHR)
        self.assertEqual(status, 200)
        self.assertIn("zip", headers.get("Content-Type", ""))
        self.assertTrue(data.startswith(b"PK"))

    @unittest.skipIf(sys.platform == "win32",
                     "sous Windows la route ouvrirait une vraie console : non testé ici")
    def test_lancement_hors_windows_erreur_claire(self):
        status, _, data = self.req("POST", "/api/launch-resume/ws1", headers=XHR)
        self.assertEqual(status, 501)
        self.assertIn("Windows", json.loads(data)["error"])


@unittest.skipIf(sys.platform == "darwin", "127.0.0.2 n'est pas configuré par défaut sous macOS")
class ConfiguredHostTests(unittest.TestCase):
    """NEBULA_HOST + NEBULA_ALLOWED_HOSTS : l'hôte configuré est accepté dans Host."""

    @classmethod
    def setUpClass(cls):
        cls.base = SANDBOX / "http-host"
        rmtree(cls.base)
        cls.srv = ServerProcess(cls.base, host="127.0.0.2",
                                extra_env={"NEBULA_HOST": "127.0.0.2",
                                           "NEBULA_ALLOWED_HOSTS": "nebula.lan"})
        cls.srv.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.stop()
        rmtree(cls.base)

    def _get(self, host):
        conn = http.client.HTTPConnection("127.0.0.2", self.srv.port, timeout=10)
        try:
            conn.putrequest("GET", "/api/overview", skip_host=True)
            conn.putheader("Host", host)
            conn.endheaders()
            return conn.getresponse().status
        finally:
            conn.close()

    def test_hotes_acceptes_et_refuses(self):
        p = self.srv.port
        self.assertEqual(self._get(f"127.0.0.2:{p}"), 200)
        self.assertEqual(self._get(f"nebula.lan:{p}"), 200)
        self.assertEqual(self._get(f"localhost:{p}"), 200)
        self.assertEqual(self._get(f"evil.example:{p}"), 403)


if __name__ == "__main__":
    unittest.main()
