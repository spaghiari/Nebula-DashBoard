"""api_files : fichiers à secrets (`.env*`, `.mcp.json`) dans l'explorateur.

Contrat VOULU (décision 2026-10-14, cf. le commentaire du contrôle dans
`dashcore/api_files.py` `write_file`) : création d'un fichier absent
autorisée avec contenu réel, écrasement d'un fichier existant refusé (403)
car l'explorateur n'en affiche qu'une version masquée.
"""
from __future__ import annotations

import json
import unittest

from _support import make_workspace, reset_sandbox
from dashcore import api_files

SECRET_ENV = "TOKEN=vrai-secret\n"
SECRET_MCP = json.dumps({"mcpServers": {"x": {"command": "c", "env": {"TOKEN": "vrai-secret"}}}})


class SensitiveFilesTests(unittest.TestCase):
    def setUp(self):
        reset_sandbox()
        self.ws = make_workspace("w1")

    def test_creation_autorisee_avec_contenu_reel(self):
        for rel, content in ((".env", SECRET_ENV), (".env.local", SECRET_ENV),
                             ("sous/.env.prod", SECRET_ENV), (".mcp.json", SECRET_MCP)):
            with self.subTest(fichier=rel):
                status, p = api_files.write_file("w1", rel, content)
                self.assertEqual(status, 200, p)
                self.assertEqual((self.ws / rel).read_text(encoding="utf-8"), content)

    def test_ecrasement_refuse_contenu_intact(self):
        for rel, content in ((".env", SECRET_ENV), (".ENV.local", SECRET_ENV),
                             (".mcp.json", SECRET_MCP)):
            with self.subTest(fichier=rel):
                (self.ws / rel).write_text(content, encoding="utf-8")
                status, p = api_files.write_file("w1", rel, "TOKEN=••••••\n")
                self.assertEqual(status, 403, p)
                self.assertIn("secrets", p["error"])
                self.assertEqual((self.ws / rel).read_text(encoding="utf-8"), content)
                self.assertFalse((self.ws / (rel + ".bak")).exists())

    def test_lecture_masquee_apres_creation(self):
        api_files.write_file("w1", ".env", SECRET_ENV)
        status, p = api_files.read_file("w1", ".env")
        self.assertEqual(status, 200)
        self.assertTrue(p["masked"] and p["readonly"])
        self.assertNotIn("vrai-secret", p["content"])

    def test_fichier_ordinaire_ecrasable(self):
        (self.ws / "notes.md").write_text("v1\n", encoding="utf-8")
        status, _ = api_files.write_file("w1", "notes.md", "v2\n")
        self.assertEqual(status, 200)
        self.assertEqual((self.ws / "notes.md").read_text(encoding="utf-8"), "v2\n")
        self.assertEqual((self.ws / "notes.md.bak").read_text(encoding="utf-8"), "v1\n")


if __name__ == "__main__":
    unittest.main()
