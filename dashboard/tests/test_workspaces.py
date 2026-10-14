"""api_workspaces : garde de purge, create/duplicate (409, rollback, registre strict)."""
from __future__ import annotations

import unittest
from unittest import mock

from _support import ROOT, SANDBOX, make_workspace, read_json_file, reset_sandbox
from dashcore import api_workspaces
from dashcore.api_workspaces import create_workspace, delete_workspace, duplicate_workspace
from dashcore.config import BACKUPS_DIR, SCRIPTS_DIR, WORKSPACES_DIR, WORKSPACES_JSON
from dashcore.helpers import CorruptJsonError


def _ids():
    if not WORKSPACES_JSON.exists():
        return []
    return [w["id"] for w in read_json_file(WORKSPACES_JSON)["workspaces"]]


class PurgeGuardTests(unittest.TestCase):
    def setUp(self):
        reset_sandbox()

    def test_purge_hors_dossier_workspaces_refusee(self):
        ext = make_workspace("adopte", path=SANDBOX / "externe" / "adopte")
        status, payload = delete_workspace("adopte", purge=True)
        self.assertEqual(status, 400)
        self.assertIn("Purge refusée", payload["error"])
        self.assertTrue(ext.is_dir())
        self.assertEqual(_ids(), ["adopte"])        # registre inchangé

    def test_purge_de_la_racine_refusee(self):
        make_workspace("racine", path=ROOT)
        self.assertEqual(delete_workspace("racine", purge=True)[0], 400)
        self.assertTrue((ROOT / "templates").is_dir())
        self.assertEqual(_ids(), ["racine"])

    def test_purge_du_dossier_workspaces_refusee(self):
        make_workspace("tous", path=WORKSPACES_DIR)
        self.assertEqual(delete_workspace("tous", purge=True)[0], 400)
        self.assertTrue(WORKSPACES_DIR.is_dir())

    def test_purge_nominale_avec_backup(self):
        d = make_workspace("w1")
        status, payload = delete_workspace("w1", purge=True)
        self.assertEqual(status, 200, payload)
        self.assertFalse(d.exists())
        self.assertEqual(_ids(), [])
        self.assertTrue(list(BACKUPS_DIR.glob("*w1*.zip")))

    def test_suppression_sans_purge_conserve_le_dossier(self):
        ext = make_workspace("adopte", path=SANDBOX / "externe2" / "adopte")
        self.assertEqual(delete_workspace("adopte")[0], 200)
        self.assertTrue(ext.is_dir())
        self.assertEqual(_ids(), [])

    def test_id_invalide(self):
        self.assertEqual(delete_workspace("../x", purge=True)[0], 400)


class CreateWorkspaceTests(unittest.TestCase):
    def setUp(self):
        reset_sandbox()

    def test_creation_nominale(self):
        status, payload = create_workspace({"id": "neuf", "label": "Neuf", "template": "blank"})
        self.assertIn(status, (200, 201), payload)
        self.assertTrue((WORKSPACES_DIR / "neuf" / "CLAUDE.md").exists())
        self.assertTrue((SCRIPTS_DIR / "launch-neuf.bat").exists())
        self.assertEqual(_ids(), ["neuf"])

    def test_409_id_deja_enregistre(self):
        make_workspace("pris", path=SANDBOX / "ailleurs" / "pris")
        status, payload = create_workspace({"id": "pris", "template": "blank"})
        self.assertEqual(status, 409)
        self.assertFalse((WORKSPACES_DIR / "pris").exists())

    def test_409_dossier_existant_non_enregistre(self):
        (WORKSPACES_DIR / "orphelin").mkdir()
        (WORKSPACES_DIR / "orphelin" / "garder.txt").write_text("x", encoding="utf-8")
        self.assertEqual(create_workspace({"id": "orphelin", "template": "blank"})[0], 409)
        self.assertTrue((WORKSPACES_DIR / "orphelin" / "garder.txt").exists())

    def test_rollback_si_echec_en_cours_de_creation(self):
        with mock.patch.object(api_workspaces, "write_launch_bat", side_effect=OSError("disque plein")):
            with self.assertRaises(OSError):
                create_workspace({"id": "rate", "template": "blank"})
        self.assertFalse((WORKSPACES_DIR / "rate").exists())
        self.assertFalse((SCRIPTS_DIR / "launch-rate.bat").exists())
        self.assertEqual(_ids(), [])

    def test_registre_corrompu_aucun_orphelin(self):
        WORKSPACES_JSON.write_text("{corrompu", encoding="utf-8")
        with self.assertRaises(CorruptJsonError):
            create_workspace({"id": "neuf", "template": "blank"})
        self.assertFalse((WORKSPACES_DIR / "neuf").exists())
        self.assertFalse((SCRIPTS_DIR / "launch-neuf.bat").exists())
        self.assertEqual(WORKSPACES_JSON.read_text(encoding="utf-8"), "{corrompu")


class DuplicateWorkspaceTests(unittest.TestCase):
    def setUp(self):
        reset_sandbox()
        self.src = make_workspace("src")
        (self.src / "notes.md").write_text("contenu", encoding="utf-8")

    def test_duplication_nominale(self):
        status, payload = duplicate_workspace({"source": "src", "id": "copie"})
        self.assertEqual(status, 201, payload)
        self.assertEqual((WORKSPACES_DIR / "copie" / "notes.md").read_text(encoding="utf-8"), "contenu")
        self.assertEqual(_ids(), ["src", "copie"])

    def test_duplication_d_un_workspace_adopte(self):
        make_workspace("ext", path=SANDBOX / "dehors" / "ext")
        self.assertEqual(duplicate_workspace({"source": "ext", "id": "ext2"})[0], 201)
        self.assertTrue((WORKSPACES_DIR / "ext2" / "CLAUDE.md").exists())

    def test_409_id_existant(self):
        make_workspace("autre", path=SANDBOX / "loin" / "autre")
        self.assertEqual(duplicate_workspace({"source": "src", "id": "autre"})[0], 409)
        self.assertFalse((WORKSPACES_DIR / "autre").exists())

    def test_409_destination_existante(self):
        (WORKSPACES_DIR / "occupe").mkdir()
        self.assertEqual(duplicate_workspace({"source": "src", "id": "occupe"})[0], 409)

    def test_source_ancetre_de_la_destination_refusee(self):
        make_workspace("racine", path=ROOT)
        self.assertEqual(duplicate_workspace({"source": "racine", "id": "boucle"})[0], 400)
        self.assertFalse((WORKSPACES_DIR / "boucle").exists())

    def test_rollback_si_echec(self):
        with mock.patch.object(api_workspaces, "write_launch_bat", side_effect=OSError("boom")):
            with self.assertRaises(OSError):
                duplicate_workspace({"source": "src", "id": "copie"})
        self.assertFalse((WORKSPACES_DIR / "copie").exists())
        self.assertEqual(_ids(), ["src"])


if __name__ == "__main__":
    unittest.main()
