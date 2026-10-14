"""workspace_io : encodage des dossiers projet Claude, cache des stats."""
from __future__ import annotations

import json
import unittest

from _support import HOME, ROOT, SANDBOX, make_workspace, reset_sandbox
from dashcore import workspace_io
from dashcore.workspace_io import all_stats, project_dir_for_path


def _encode(path) -> str:
    """Règle Claude Code, écrite indépendamment de l'implémentation :
    tout caractère hors [A-Za-z0-9] ASCII devient '-'."""
    s = str(path.resolve())
    return "".join(c if (c.isascii() and c.isalnum()) else "-" for c in s)


PROJECTS = HOME / ".claude" / "projects"


class ProjectDirTests(unittest.TestCase):
    def setUp(self):
        reset_sandbox()

    def test_points_soulignes_espaces_accents(self):
        p = SANDBOX / "mon_projet.v2 (copie) é"
        enc = _encode(p)
        for ch in "._ ()é":
            self.assertNotIn(ch, enc)
        (PROJECTS / enc).mkdir()
        self.assertEqual(project_dir_for_path(p), PROJECTS / enc)

    def test_correspondance_insensible_a_la_casse(self):
        p = SANDBOX / "Projet"
        (PROJECTS / _encode(p).upper()).mkdir()
        found = project_dir_for_path(p)
        self.assertIsNotNone(found)
        self.assertTrue(found.is_dir())
        self.assertEqual(found.name.lower(), _encode(p).lower())

    def test_absent(self):
        self.assertIsNone(project_dir_for_path(SANDBOX / "inconnu"))


def _line(kind="assistant", inp=0, out=0, text=None):
    entry = {"type": kind, "message": {"usage": {"input_tokens": inp, "output_tokens": out}}}
    if text is not None:
        entry["message"]["content"] = text
    return json.dumps(entry) + "\n"


class StatsCacheTests(unittest.TestCase):
    def setUp(self):
        reset_sandbox()
        ws_dir = make_workspace("w1")
        self.pdir = PROJECTS / _encode(ws_dir)
        self.pdir.mkdir()
        self.s1 = self.pdir / "s1.jsonl"
        self.s1.write_text(_line("user", text="bonjour") + _line(inp=10, out=5), encoding="utf-8")

    def test_ajout_de_ligne_pris_en_compte(self):
        st = all_stats()["w1"]
        self.assertEqual((st["sessions"], st["messages"], st["input_tokens"]), (1, 2, 10))
        with self.s1.open("a", encoding="utf-8") as f:
            f.write(_line(inp=7, out=1))
        st = all_stats()["w1"]
        self.assertEqual((st["messages"], st["input_tokens"], st["output_tokens"]), (3, 17, 6))

    def test_nouveau_fichier_puis_suppression(self):
        all_stats()
        s2 = self.pdir / "s2.jsonl"
        s2.write_text(_line(inp=100), encoding="utf-8")
        st = all_stats()["w1"]
        self.assertEqual((st["sessions"], st["input_tokens"]), (2, 110))
        self.assertIn(str(s2), workspace_io._STATS_CACHE)
        s2.unlink()
        st = all_stats()["w1"]
        self.assertEqual((st["sessions"], st["input_tokens"]), (1, 10))
        # Entrée purgée du cache au balayage complet.
        self.assertNotIn(str(s2), workspace_io._STATS_CACHE)

    def test_cache_reutilise_si_fichier_inchange(self):
        all_stats()
        calls = []
        orig = workspace_io._scan_session_file
        workspace_io._scan_session_file = lambda p: calls.append(p) or orig(p)
        try:
            all_stats()
        finally:
            workspace_io._scan_session_file = orig
        self.assertEqual(calls, [])

    def test_workspace_sans_dossier_projet(self):
        make_workspace("w2", path=ROOT / "ailleurs" / "w2")
        st = all_stats()["w2"]
        self.assertEqual(st["sessions"], 0)


class OverviewOverlaysTests(unittest.TestCase):
    """`/api/overview` expose l'état des overlays (badge « Auto-amélioration »)."""

    def setUp(self):
        reset_sandbox()
        ov = ROOT / "templates" / "claude-self-improving"
        (ov / ".claude").mkdir(parents=True)
        (ov / ".nebula-overlay.json").write_text(json.dumps({
            "id": "claude-self-improving", "label": "Auto-amélioration de Claude",
            "signature_file": ".claude/improvements.md"}), encoding="utf-8")
        (ov / ".claude" / "improvements.md").write_text("# improvements\n", encoding="utf-8")
        self.on = make_workspace("actif")
        (self.on / ".claude" / "improvements.md").write_text("# x\n", encoding="utf-8")
        make_workspace("inactif")
        # Workspace enregistré dont le dossier n'existe pas : ignoré sans erreur.
        data = json.loads(workspace_io.WORKSPACES_JSON.read_text(encoding="utf-8"))
        data["workspaces"].append({"id": "absent", "label": "absent", "path": str(ROOT / "nulle-part" / "x")})
        workspace_io.WORKSPACES_JSON.write_text(json.dumps(data), encoding="utf-8")

    def test_overlays_actifs_par_workspace(self):
        ov = workspace_io.workspaces_overview()["overlays_active"]
        self.assertEqual(ov, {"actif": ["claude-self-improving"]})

    def test_sans_overlay_disponible(self):
        import shutil
        shutil.rmtree(ROOT / "templates" / "claude-self-improving")
        self.assertEqual(workspace_io.workspaces_overview()["overlays_active"], {})


if __name__ == "__main__":
    unittest.main()
