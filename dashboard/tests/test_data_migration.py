"""Migration assistée vers `NEBULA_DATA_DIR` : copie sans jamais écraser.

Fonctions testées avec des dossiers source/destination explicites (le
bac à sable n'a pas de `NEBULA_DATA_DIR`), plus un démarrage réel du serveur
avec la variable définie.
"""
from __future__ import annotations

import http.client
import json
import unittest

from _support import SANDBOX, ServerProcess, read_json_file, rmtree, write_json_file
from dashcore import data_migration as dm


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.base = SANDBOX / "migration"
        rmtree(self.base)
        self.src = self.base / "ancien"
        self.dst = self.base / "nouveau"
        write_json_file(self.src / "workspaces.json", {"version": "1.0", "workspaces": [{"id": "a"}]})
        write_json_file(self.src / "workspaces.json.bak", {"version": "1.0", "workspaces": []})
        write_json_file(self.src / "ui_state.json", {"theme": "sobre"})
        write_json_file(self.src / "mcp_recipes.local.json", {"version": 1, "recipes": []})
        skill = self.src / "skills-library" / "s1"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: s1\n---\n", encoding="utf-8")
        (skill / "references").mkdir()
        (skill / "references" / "r.md").write_text("r\n", encoding="utf-8")
        # Hors périmètre : catalogue livré, log des hooks, fichier inconnu.
        write_json_file(self.src / "mcp_recipes.json", {"version": 1, "recipes": []})
        (self.src / "hook_errors.log").write_text("x\n", encoding="utf-8")
        (self.src / "divers.txt").write_text("x\n", encoding="utf-8")

    def tearDown(self):
        rmtree(self.base)

    def _src_snapshot(self):
        return {p.relative_to(self.src).as_posix(): p.read_bytes()
                for p in self.src.rglob("*") if p.is_file()}

    def test_destination_vide_tout_copie_source_intacte(self):
        before = self._src_snapshot()
        report = dm.startup_migration(src=self.src, dst=self.dst)
        self.assertTrue(report["ok"])
        self.assertEqual(sorted(report["copied"]), sorted([
            "workspaces.json", "workspaces.json.bak", "ui_state.json",
            "mcp_recipes.local.json", "skills-library/s1/SKILL.md",
            "skills-library/s1/references/r.md"]))
        self.assertEqual(read_json_file(self.dst / "ui_state.json"), {"theme": "sobre"})
        for name in ("mcp_recipes.json", "hook_errors.log", "divers.txt"):
            self.assertFalse((self.dst / name).exists(), name)
        self.assertEqual(self._src_snapshot(), before)
        self.assertTrue((self.dst / dm.MARKER_NAME).is_file())

    def test_jamais_d_ecrasement(self):
        write_json_file(self.dst / "ui_state.json", {"theme": "pop"})
        write_json_file(self.dst / "workspaces.json", {"version": "1.0", "workspaces": [{"id": "a"}]})
        report = dm.migrate_data_dir(self.src, self.dst)
        self.assertEqual(read_json_file(self.dst / "ui_state.json"), {"theme": "pop"})
        self.assertIn("ui_state.json", report["conflicts"])
        self.assertIn("workspaces.json", report["identical"])
        self.assertNotIn("ui_state.json", report["copied"])
        self.assertTrue((self.dst / "skills-library" / "s1" / "SKILL.md").exists())

    def test_copie_exclusive(self):
        target = self.dst / "x.json"
        target.parent.mkdir(parents=True)
        target.write_text("présent", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            dm._copy_exclusive(self.src / "ui_state.json", target)
        self.assertEqual(target.read_text(encoding="utf-8"), "présent")

    def test_destination_deja_utilisee_pas_de_migration_auto(self):
        write_json_file(self.dst / "workspaces.json", {"version": "1.0", "workspaces": []})
        self.assertIsNone(dm.startup_migration(src=self.src, dst=self.dst))
        self.assertFalse((self.dst / "ui_state.json").exists())
        # --migrate-data : fusion des seuls fichiers manquants.
        report = dm.startup_migration(force=True, src=self.src, dst=self.dst)
        self.assertIn("ui_state.json", report["copied"])
        self.assertIn("workspaces.json", report["conflicts"])
        self.assertEqual(read_json_file(self.dst / "workspaces.json")["workspaces"], [])

    def test_marqueur_empeche_la_resurrection(self):
        dm.startup_migration(src=self.src, dst=self.dst)
        (self.dst / "ui_state.json").unlink()  # suppression volontaire
        self.assertIsNone(dm.startup_migration(src=self.src, dst=self.dst))
        self.assertFalse((self.dst / "ui_state.json").exists())

    def test_meme_dossier_ou_source_absente(self):
        self.assertIsNone(dm.startup_migration(src=self.src, dst=self.src))
        self.assertIsNone(dm.startup_migration(src=self.base / "absent", dst=self.dst))
        self.assertFalse(self.dst.exists())

    def test_sans_variable_d_env_rien(self):
        # Bac à sable : NEBULA_DATA_DIR non défini.
        self.assertIsNone(dm.startup_migration())
        self.assertIsNone(dm.startup_migration(force=True))


class ServerStartupMigrationTests(unittest.TestCase):
    """Démarrage réel avec NEBULA_DATA_DIR vers un dossier vide."""

    def setUp(self):
        self.base = SANDBOX / "srv-migration"
        rmtree(self.base)
        self.data2 = self.base / "data2"
        self.srv = ServerProcess(self.base, extra_env={"NEBULA_DATA_DIR": str(self.data2)})
        self.srv.start()

    def tearDown(self):
        self.srv.stop()
        rmtree(self.base)

    def test_workspaces_retrouves(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.srv.port, timeout=5)
        try:
            conn.request("GET", "/api/workspaces")
            body = json.loads(conn.getresponse().read())
        finally:
            conn.close()
        ids = [w["id"] for w in (body.get("workspaces", body) if isinstance(body, dict) else body)]
        self.assertEqual(ids, ["ws1"])
        self.assertTrue((self.data2 / "workspaces.json").is_file())
        self.assertTrue((self.srv.root / "dashboard" / "data" / "workspaces.json").is_file())
        self.assertIn("Migration des données", self.srv.log_text())


if __name__ == "__main__":
    unittest.main()
