"""Retrouver ses projets : scan des projets sans session (transcripts purgés),
inspection d'un dossier parent et adoption groupée."""
from __future__ import annotations

import json
import os
import re
import time
import unittest
from pathlib import Path
from unittest import mock

from _support import (
    ROOT, SANDBOX, read_json_file, register_workspaces, reset_sandbox, rmtree,
    write_json_file,
)
from dashcore import api_mcps, api_workspaces
from dashcore.api_mcps import scan_claude_config
from dashcore.api_workspaces import adopt_workspaces_bulk, inspect_parent_folder
from dashcore.config import CLAUDE_HOME, CLAUDE_JSON, CLAUDE_PROJECTS, WORKSPACES_JSON


def _encode(path: Path) -> str:
    """Même règle que Claude Code : tout caractère non alphanumérique -> `-`."""
    return re.sub(r"[^A-Za-z0-9]", "-", str(path))


def _project_dir(name: str, *, cwd: str | None = None) -> Path:
    d = CLAUDE_PROJECTS / name
    (d / "memory").mkdir(parents=True, exist_ok=True)
    if cwd is not None:
        (d / "s1.jsonl").write_text(json.dumps({"type": "user", "cwd": cwd}) + "\n",
                                    encoding="utf-8")
    return d


def _projects_by_path() -> dict[str, dict]:
    status, payload = scan_claude_config()
    assert status == 200
    return {p["path"].lower(): p for p in payload["projects"]}


class ScanExpiredSessionsTests(unittest.TestCase):
    def setUp(self):
        reset_sandbox()
        self.base = SANDBOX / "scan-projets"
        rmtree(self.base)
        self.base.mkdir()

    def tearDown(self):
        rmtree(self.base)

    def test_projet_sans_session_garde_si_chemin_existe(self):
        real = self.base / "projet_expire"
        real.mkdir()
        d = _project_dir(_encode(real))
        old = time.time() - 3 * 86400
        os.utime(d, (old, old))
        write_json_file(CLAUDE_JSON, {"projects": {real.as_posix(): {}}})
        p = _projects_by_path().get(str(real).lower())
        self.assertIsNotNone(p, "un projet aux transcripts purgés doit rester proposé")
        self.assertEqual(p["sessions"], 0)
        self.assertTrue(p["sessions_expired"])
        self.assertTrue(p["path_exists"])
        self.assertEqual(p["path_source"], "claude_json")
        self.assertAlmostEqual(p["last_modified"], old, delta=2)

    def test_projet_sans_session_chemin_decode(self):
        real = self.base / "decode"
        real.mkdir()
        name = _encode(real)
        _project_dir(name)
        fake = {name: (str(real), True)}
        with mock.patch.object(api_mcps, "_decode_project_path",
                               side_effect=lambda n: fake.get(n, ("", False))):
            p = _projects_by_path().get(str(real).lower())
        self.assertIsNotNone(p)
        self.assertEqual((p["path_source"], p["sessions_expired"]), ("decoded", True))

    def test_projet_sans_session_exclu_si_chemin_absent(self):
        _project_dir("C--chemin-qui-n-existe-nulle-part-xyz")
        status, payload = scan_claude_config()
        self.assertEqual(status, 200)
        self.assertEqual(payload["projects"], [])

    def test_projet_avec_session_inchange(self):
        real = self.base / "actif"
        real.mkdir()
        _project_dir(_encode(real), cwd=str(real))
        p = _projects_by_path()[str(real).lower()]
        self.assertEqual((p["sessions"], p["sessions_expired"], p["path_source"]), (1, False, "session"))

    def test_racine_nebula_et_claude_home_exclues(self):
        # Racine Nebula, sans session (via ~/.claude.json) puis avec session.
        _project_dir(_encode(ROOT))
        write_json_file(CLAUDE_JSON, {"projects": {ROOT.as_posix(): {}}})
        self.assertNotIn(str(ROOT).lower(), _projects_by_path())
        rmtree(CLAUDE_PROJECTS / _encode(ROOT))
        _project_dir("racine-avec-session", cwd=str(ROOT))
        sous_home = CLAUDE_HOME / "plugins"
        sous_home.mkdir(parents=True, exist_ok=True)
        _project_dir("sous-claude-home", cwd=str(sous_home))
        found = _projects_by_path()
        self.assertNotIn(str(ROOT).lower(), found)
        self.assertNotIn(str(sous_home).lower(), found)


class InspectParentTests(unittest.TestCase):
    def setUp(self):
        reset_sandbox()
        self.parent = SANDBOX / "parent-projets"
        rmtree(self.parent)
        p = self.parent
        (p / "Alpha Proj").mkdir(parents=True)
        (p / "Alpha Proj" / "CLAUDE.md").write_text("# a\n", encoding="utf-8")
        (p / "alpha-proj").mkdir()
        (p / "alpha-proj" / "package.json").write_text("{}", encoding="utf-8")
        (p / "taken" / ".git").mkdir(parents=True)
        (p / "adopte").mkdir()
        (p / "adopte" / "pyproject.toml").write_text("", encoding="utf-8")
        (p / "dotnet").mkdir()
        (p / "dotnet" / "App.sln").write_text("", encoding="utf-8")
        (p / "node_modules" / "lib").mkdir(parents=True)
        (p / "node_modules" / "package.json").write_text("{}", encoding="utf-8")
        (p / ".cache").mkdir()
        (p / ".cache" / "CLAUDE.md").write_text("", encoding="utf-8")
        (p / "__pycache__").mkdir()
        (p / "__pycache__" / "setup.py").write_text("", encoding="utf-8")
        (p / "vide").mkdir()
        (p / "plain" / "inner").mkdir(parents=True)
        (p / "plain" / "inner" / "go.mod").write_text("", encoding="utf-8")
        register_workspaces([
            {"id": "taken", "label": "t", "path": str(SANDBOX / "ailleurs")},
            {"id": "deja", "label": "d", "path": str(p / "adopte")},
        ])

    def tearDown(self):
        rmtree(self.parent)

    def _inspect(self, **kw):
        status, payload = inspect_parent_folder({"path": str(self.parent), **kw})
        self.assertEqual(status, 200, payload)
        return payload, {c["name"]: c for c in payload["candidates"]}

    def test_signaux_ids_et_dossiers_ignores(self):
        payload, by_name = self._inspect()
        self.assertEqual(sorted(by_name), ["Alpha Proj", "adopte", "alpha-proj", "dotnet", "taken"])
        self.assertFalse(payload["truncated"])
        self.assertEqual(by_name["Alpha Proj"]["signals"], ["CLAUDE.md"])
        self.assertTrue(by_name["Alpha Proj"]["claude"])
        self.assertFalse(by_name["alpha-proj"]["claude"])
        self.assertEqual(by_name["dotnet"]["signals"], ["App.sln"])
        self.assertEqual(by_name["taken"]["signals"], [".git"])
        # Dédoublonné entre candidats puis contre le registre.
        self.assertEqual(by_name["Alpha Proj"]["suggested_id"], "alpha-proj")
        self.assertEqual(by_name["alpha-proj"]["suggested_id"], "alpha-proj-2")
        self.assertEqual(by_name["taken"]["suggested_id"], "taken-2")
        # Déjà adopté : id existant, pas de nouvel id.
        self.assertTrue(by_name["adopte"]["already_adopted"])
        self.assertEqual(by_name["adopte"]["adopted_id"], "deja")
        self.assertFalse(by_name["taken"]["already_adopted"])

    def test_profondeur_2(self):
        _, by_name = self._inspect(depth=2)
        self.assertIn("inner", by_name)
        self.assertEqual(Path(by_name["inner"]["relative"]), Path("plain") / "inner")
        self.assertNotIn("lib", by_name)  # node_modules jamais parcouru

    def test_plafond_tronque(self):
        with mock.patch.object(api_workspaces, "PARENT_SCAN_MAX_CANDIDATES", 2):
            payload, _ = self._inspect()
        self.assertEqual(len(payload["candidates"]), 2)
        self.assertTrue(payload["truncated"])
        self.assertEqual(payload["max"], 2)

    def test_erreurs(self):
        self.assertEqual(inspect_parent_folder({"path": "relatif"})[0], 400)
        self.assertEqual(inspect_parent_folder({"path": str(self.parent / "absent")})[0], 404)
        self.assertEqual(inspect_parent_folder({"path": str(CLAUDE_HOME)})[0], 403)

    def test_lecture_seule(self):
        before = WORKSPACES_JSON.read_bytes()
        self._inspect(depth=2)
        self.assertEqual(WORKSPACES_JSON.read_bytes(), before)
        self.assertFalse((self.parent / "Alpha Proj" / ".claude").exists())


class AdoptBulkTests(unittest.TestCase):
    def setUp(self):
        reset_sandbox()
        self.base = SANDBOX / "bulk"
        rmtree(self.base)
        for name in ("un", "deux", "trois"):
            (self.base / name).mkdir(parents=True)
        register_workspaces([{"id": "existant", "label": "e", "path": str(self.base / "deux")}])

    def tearDown(self):
        rmtree(self.base)

    def test_succes_partiel(self):
        status, payload = adopt_workspaces_bulk({"items": [
            {"path": str(self.base / "un"), "id": "un"},
            {"path": str(self.base / "deux"), "id": "deux"},           # chemin déjà adopté
            {"path": str(self.base / "absent"), "id": "absent"},       # introuvable
            {"path": str(self.base / "trois"), "id": "pas valide !"},  # id invalide
            {"path": str(self.base / "trois"), "id": "un"},            # id pris dans le lot
            "pas un objet",
        ]})
        self.assertEqual(status, 200, payload)
        self.assertEqual((payload["adopted"], payload["failed"]), (1, 5))
        statuses = [r["status"] for r in payload["results"]]
        self.assertEqual(statuses, [201, 409, 404, 400, 409, 400])
        self.assertTrue(payload["results"][0]["ok"])
        self.assertTrue(all(r.get("error") for r in payload["results"][1:]))
        ids = [w["id"] for w in read_json_file(WORKSPACES_JSON)["workspaces"]]
        self.assertEqual(ids, ["existant", "un"])

    def test_tout_en_echec_400(self):
        status, payload = adopt_workspaces_bulk({"items": [
            {"path": str(self.base / "deux"), "id": "deux"}]})
        self.assertEqual(status, 400)
        self.assertIn("Aucun projet adopté", payload["error"])
        self.assertEqual(len(payload["results"]), 1)

    def test_entree_invalide(self):
        self.assertEqual(adopt_workspaces_bulk({})[0], 400)
        self.assertEqual(adopt_workspaces_bulk({"items": []})[0], 400)
        with mock.patch.object(api_workspaces, "PARENT_SCAN_MAX_CANDIDATES", 1):
            self.assertEqual(adopt_workspaces_bulk({"items": [{}, {}]})[0], 400)

    def test_registre_corrompu_rien_ecrit(self):
        WORKSPACES_JSON.write_text("{cassé", encoding="utf-8")
        status, payload = adopt_workspaces_bulk({"items": [
            {"path": str(self.base / "un"), "id": "un"}]})
        self.assertEqual(status, 400)
        self.assertEqual(payload["results"][0]["status"], 409)
        self.assertEqual(WORKSPACES_JSON.read_text(encoding="utf-8"), "{cassé")


if __name__ == "__main__":
    unittest.main()
