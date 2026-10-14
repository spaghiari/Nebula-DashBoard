"""api_mcps : sync .mcp.json non destructive, refus des valeurs masquées."""
from __future__ import annotations

import unittest

from _support import make_workspace, read_json_file, reset_sandbox, write_json_file
from dashcore.api_mcps import add_or_update_mcp, clean_mcp_payload, sync_workspace_mcps
from dashcore.config import ENV_ENC_FILE, MCP_REGISTRY


def _mcp(mid, **kw):
    m = {"id": mid, "name": mid, "transport": "stdio", "command": "echo",
         "args": [], "workspaces": ["w1"], "status": "disponible"}
    m.update(kw)
    return m


class SyncTests(unittest.TestCase):
    def setUp(self):
        reset_sandbox()
        self.ws = make_workspace("w1")
        self.out = self.ws / ".mcp.json"
        write_json_file(MCP_REGISTRY, {"version": "1.0", "mcps": [_mcp("neb")]})

    def _servers(self):
        return read_json_file(self.out)["mcpServers"]

    def test_generation_simple(self):
        status, payload = sync_workspace_mcps("w1")
        self.assertEqual(status, 200, payload)
        self.assertEqual(list(self._servers()), ["neb"])

    def test_serveurs_etrangers_preserves(self):
        write_json_file(self.out, {"mcpServers": {"perso": {"command": "x"}}})
        status, payload = sync_workspace_mcps("w1")
        self.assertEqual(status, 200)
        self.assertEqual(payload.get("preserved"), ["perso"])
        self.assertEqual(set(self._servers()), {"perso", "neb"})
        self.assertEqual(self._servers()["perso"], {"command": "x"})

    def test_mcp_retire_du_registre_supprime_mais_etranger_garde(self):
        sync_workspace_mcps("w1")
        data = read_json_file(self.out)
        data["mcpServers"]["perso"] = {"command": "y"}
        write_json_file(self.out, data)
        write_json_file(MCP_REGISTRY, {"version": "1.0", "mcps": []})
        self.assertEqual(sync_workspace_mcps("w1")[0], 200)
        self.assertEqual(self._servers(), {"perso": {"command": "y"}})

    def test_plus_aucun_serveur_fichier_supprime(self):
        sync_workspace_mcps("w1")
        write_json_file(MCP_REGISTRY, {"version": "1.0", "mcps": []})
        self.assertEqual(sync_workspace_mcps("w1")[0], 200)
        self.assertFalse(self.out.exists())

    def test_fichier_illisible_erreur_sans_ecrasement(self):
        self.out.write_text("{pas du json", encoding="utf-8")
        status, payload = sync_workspace_mcps("w1")
        self.assertEqual(status, 409)
        self.assertIn("illisible", payload["error"])
        self.assertEqual(self.out.read_text(encoding="utf-8"), "{pas du json")

    def test_store_env_illisible_sync_annulee(self):
        write_json_file(self.out, {"mcpServers": {"neb": {"command": "secret-resolu"}}})
        before = self.out.read_bytes()
        ENV_ENC_FILE.write_bytes(b"illisible")
        self.assertEqual(sync_workspace_mcps("w1")[0], 409)
        self.assertEqual(self.out.read_bytes(), before)


class MaskedValuesTests(unittest.TestCase):
    def setUp(self):
        reset_sandbox()
        make_workspace("w1")

    def test_valeurs_masquees_refusees(self):
        cases = [
            {"env": {"TOKEN": "••••••"}},
            {"env": {"TOKEN": "***"}},
            {"transport": "http", "command": "", "url": "https://x.example/mcp",
             "headers": {"Authorization": "••••••"}},
            {"transport": "http", "command": "", "url": "https://x.example/mcp?…"},
        ]
        for extra in cases:
            with self.subTest(extra=extra):
                clean, err = clean_mcp_payload(_mcp("m", **extra))
                self.assertIsNotNone(err)
                self.assertIn("masquée", err)

    def test_reference_variable_acceptee(self):
        clean, err = clean_mcp_payload(_mcp("m", env={"TOKEN": "${MON_TOKEN}"}))
        self.assertIsNone(err)
        self.assertEqual(clean["env"], {"TOKEN": "${MON_TOKEN}"})

    def test_ajout_avec_valeur_masquee_registre_inchange(self):
        before = MCP_REGISTRY.read_bytes()
        status, payload = add_or_update_mcp(_mcp("m", env={"TOKEN": "••••••"}))
        self.assertEqual(status, 400, payload)
        self.assertEqual(MCP_REGISTRY.read_bytes(), before)
        self.assertEqual(read_json_file(MCP_REGISTRY)["mcps"], [])


if __name__ == "__main__":
    unittest.main()
