"""config : variables d'environnement (NEBULA_*), hôtes autorisés, plateforme."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import unittest
from unittest import mock

from _support import DASHBOARD_DIR, SANDBOX
from dashcore import config
from dashcore import helpers, workspace_io

_PROBE = (
    "import json; from dashcore import config as c; print(json.dumps({"
    "'data': str(c.DATA_DIR), 'ws': str(c.WORKSPACES_JSON), 'ui': str(c.UI_STATE_FILE),"
    "'lib': str(c.SKILLS_LIBRARY_DIR), 'recipes': str(c.MCP_RECIPES_FILE),"
    "'host': c.HOST, 'port': c.DEFAULT_PORT, 'extra': list(c.EXTRA_ALLOWED_HOSTS),"
    "'warn': c.CONFIG_WARNINGS, 'custom': c.DATA_DIR_IS_CUSTOM}))"
)


def probe(**env) -> dict:
    """Valeurs de config résolues dans un interpréteur neuf avec `env`."""
    full = dict(os.environ)
    for k in ("NEBULA_DATA_DIR", "NEBULA_HOST", "NEBULA_PORT", "NEBULA_ALLOWED_HOSTS"):
        full.pop(k, None)
    full.update(env)
    out = subprocess.run([sys.executable, "-c", _PROBE], cwd=str(DASHBOARD_DIR), env=full,
                         capture_output=True, text=True, timeout=30)
    if out.returncode != 0:
        raise AssertionError(out.stderr)
    return json.loads(out.stdout)


class EnvConfigTests(unittest.TestCase):
    def test_defauts_retrocompatibles(self):
        c = probe()
        root = os.environ["ATELIER_ROOT"]
        self.assertEqual(c["data"], os.path.join(root, "dashboard", "data"))
        self.assertEqual(c["ws"], os.path.join(root, "dashboard", "data", "workspaces.json"))
        self.assertEqual((c["host"], c["port"], c["extra"], c["warn"], c["custom"]),
                         ("127.0.0.1", 4777, [], [], False))

    def test_nebula_data_dir(self):
        target = SANDBOX / "donnees-ailleurs"
        c = probe(NEBULA_DATA_DIR=str(target))
        self.assertTrue(c["custom"])
        self.assertEqual(c["data"], str(target.resolve()))
        self.assertEqual(c["ws"], str(target.resolve() / "workspaces.json"))
        self.assertEqual(c["ui"], str(target.resolve() / "ui_state.json"))
        self.assertEqual(c["lib"], str(target.resolve() / "skills-library"))
        # Le catalogue livré avec le code ne bouge pas.
        self.assertTrue(c["recipes"].endswith(os.path.join("dashboard", "data", "mcp_recipes.json")))

    def test_port_hote_et_hotes_supplementaires(self):
        c = probe(NEBULA_PORT="4800", NEBULA_HOST="0.0.0.0", NEBULA_ALLOWED_HOSTS=" Nas.lan , ,x ")
        self.assertEqual((c["port"], c["host"], c["extra"]), (4800, "0.0.0.0", ["nas.lan", "x"]))

    def test_port_invalide_avertit_et_garde_le_defaut(self):
        for bad in ("abc", "0", "70000"):
            with self.subTest(bad=bad):
                c = probe(NEBULA_PORT=bad)
                self.assertEqual(c["port"], 4777)
                self.assertEqual(len(c["warn"]), 1)
                self.assertIn("NEBULA_PORT", c["warn"][0])


    def test_hote_autorise_avec_port_signale(self):
        c = probe(NEBULA_ALLOWED_HOSTS="nas.lan:4777,ok.lan,fe80::1")
        self.assertEqual(len(c["warn"]), 1)
        self.assertIn("nas.lan:4777", c["warn"][0])


class HostHelpersTests(unittest.TestCase):
    def test_port_free_ipv4_et_ipv6(self):
        self.assertIsInstance(helpers.port_free("127.0.0.1", 0), bool)
        if not socket.has_ipv6:
            self.skipTest("IPv6 indisponible")
        try:
            with socket.socket(socket.AF_INET6) as s:
                s.bind(("::1", 0))
                busy = s.getsockname()[1]
                s.listen()
                self.assertFalse(helpers.port_free("::1", busy))
        except OSError as e:
            self.skipTest(f"boucle IPv6 indisponible : {e}")

    def test_is_loopback_host(self):
        for h in ("127.0.0.1", "127.0.0.2", "localhost", "LOCALHOST", "::1", "[::1]"):
            self.assertTrue(config.is_loopback_host(h), h)
        for h in ("0.0.0.0", "::", "192.168.1.10", "nas.lan", ""):
            self.assertFalse(config.is_loopback_host(h), h)

    def test_allowed_host_headers(self):
        import server
        base = {"127.0.0.1:80", "localhost:80", "[::1]:80"}
        self.assertEqual(server.allowed_host_headers("127.0.0.1", 80), base)
        self.assertEqual(server.allowed_host_headers("0.0.0.0", 80), base)
        self.assertEqual(server.allowed_host_headers("::", 80), base)
        self.assertEqual(server.allowed_host_headers("192.168.1.10", 80, ("nas.lan",)),
                         base | {"192.168.1.10:80", "nas.lan:80"})
        self.assertIn("[fe80::1]:80", server.allowed_host_headers("fe80::1", 80))


class PlatformGuardTests(unittest.TestCase):
    """Fonctions Windows-only : erreur claire (501), jamais de crash."""

    def test_lancement_de_script_hors_windows(self):
        with mock.patch.object(workspace_io, "IS_WINDOWS", False):
            status, payload = workspace_io.launch_script("launch-x.bat")
        self.assertEqual(status, 501)
        self.assertIn("Windows", payload["error"])

    def test_reprise_de_session_hors_windows(self):
        from dashcore import api_workspaces
        with mock.patch.object(api_workspaces, "IS_WINDOWS", False):
            status, payload = api_workspaces.launch_resume("w1")
        self.assertEqual(status, 501)

    def test_ouverture_sans_ouvreur_hors_windows(self):
        target = SANDBOX / "a-ouvrir.txt"
        target.write_text("x", encoding="utf-8")
        with mock.patch.object(helpers, "IS_WINDOWS", False), \
             mock.patch.dict(helpers.OPEN_TARGETS, {"test-cible": target}), \
             mock.patch.object(helpers.shutil, "which", return_value=None):
            status, payload = helpers.open_target("test-cible")
        self.assertEqual(status, 501)
        self.assertIn("introuvable", payload["error"])

    def test_import_du_serveur_sans_effet_de_bord_windows(self):
        """server.py et tout dashcore s'importent avec sys.platform simulé
        en 'linux' (attrape un import Windows-only non gardé au niveau module)."""
        code = ("import sys; sys.platform = 'linux'; import server; "
                "from dashcore import active_sessions, env_crypto; "
                "assert active_sessions._process_snapshot() is None; "
                "assert env_crypto.IS_WINDOWS is False; print('ok')")
        out = subprocess.run([sys.executable, "-c", code], cwd=str(DASHBOARD_DIR),
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip(), "ok")


class TeamConstantsTests(unittest.TestCase):
    """Constantes du module claude-team : alias, efforts, règles par rôle."""

    def test_alias_et_efforts(self):
        self.assertEqual(config.TEAM_MODEL_ALIASES, ("sonnet", "opus", "haiku", "fable", "inherit"))
        self.assertEqual(config.TEAM_EFFORT_LEVELS, ("low", "medium", "high", "xhigh", "max"))

    def test_regles_par_role(self):
        roles = {"orchestrator", "researcher", "architect", "executor", "reviewer",
                 "evaluator", "critic"}
        self.assertEqual(set(config.TEAM_ROLE_DEFAULTS), roles)
        allowed = config.TEAM_EFFORT_LEVELS[:config.TEAM_EFFORT_LEVELS.index("high") + 1]
        for role, rule in config.TEAM_ROLE_DEFAULTS.items():
            with self.subTest(role=role):
                self.assertIn(rule["model"], config.TEAM_MODEL_ALIASES)
                # Une règle ne propose jamais au-delà de `high`.
                self.assertIn(rule["effort"], allowed)
                self.assertTrue(rule["why"].strip())
                self.assertNotIn(chr(0x2014), rule["why"])  # pas de tiret cadratin
        self.assertEqual(config.TEAM_ROLE_DEFAULTS["orchestrator"]["effort"], "medium")
        self.assertEqual(config.TEAM_ROLE_DEFAULTS["reviewer"], {
            **config.TEAM_ROLE_DEFAULTS["reviewer"], "model": "opus", "effort": "high"})


if __name__ == "__main__":
    unittest.main()
