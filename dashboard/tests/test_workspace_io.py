"""workspace_io : encodage des dossiers projet Claude, cache des stats."""
from __future__ import annotations

import json
import unittest
from unittest import mock

from _support import HOME, ROOT, SANDBOX, make_workspace, reset_sandbox, rmtree, write_json_file
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


class StatsHistoryTests(unittest.TestCase):
    """Historique quotidien des totaux (sparklines de l'Accueil)."""

    def setUp(self):
        reset_sandbox()
        workspace_io.stats_history_path().unlink(missing_ok=True)

    @staticmethod
    def _stats(sessions, messages):
        return {"a": {"sessions": sessions, "messages": messages, "input_tokens": 10, "output_tokens": 5},
                "b": {"sessions": 1, "messages": 2, "input_tokens": 0, "output_tokens": 0}}

    def test_un_point_par_jour_et_ecriture_seulement_si_change(self):
        import datetime as dt
        d1, d2 = dt.date(2026, 10, 1), dt.date(2026, 10, 2)
        self.assertTrue(workspace_io.record_stats_history(self._stats(3, 10), d1))
        self.assertFalse(workspace_io.record_stats_history(self._stats(3, 10), d1))
        self.assertTrue(workspace_io.record_stats_history(self._stats(4, 12), d1))
        self.assertTrue(workspace_io.record_stats_history(self._stats(5, 20), d2))
        pts = workspace_io.stats_history()["points"]
        self.assertEqual([p["date"] for p in pts], ["2026-10-01", "2026-10-02"])
        self.assertEqual(pts[0], {"date": "2026-10-01", "workspaces": 2, "sessions": 5, "messages": 14, "tokens": 15})
        self.assertEqual(pts[1]["messages"], 22)
        # Fichier dans le dossier de données (NEBULA_DATA_DIR respecté).
        self.assertEqual(workspace_io.stats_history_path().parent, workspace_io._config.DATA_DIR)

    def test_retention_bornee(self):
        import datetime as dt
        start = dt.date(2026, 1, 1)
        for i in range(workspace_io.STATS_HISTORY_DAYS + 5):
            workspace_io.record_stats_history(self._stats(i, i), start + dt.timedelta(days=i))
        pts = workspace_io.stats_history()["points"]
        self.assertEqual(len(pts), workspace_io.STATS_HISTORY_DAYS)
        self.assertEqual(pts[0]["date"], (start + dt.timedelta(days=5)).isoformat())

    def test_fichier_corrompu_repris_sans_erreur(self):
        path = workspace_io.stats_history_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{pas du json", encoding="utf-8")
        self.assertEqual(workspace_io.stats_history()["points"], [])
        self.assertTrue(workspace_io.record_stats_history(self._stats(1, 1)))
        self.assertEqual(len(workspace_io.stats_history()["points"]), 1)


class SanityMigrationTests(unittest.TestCase):
    """Indicateur « données à migrer » du sanity-check (bloc Santé)."""

    def setUp(self):
        reset_sandbox()
        self.base = SANDBOX / "sanity-migration"
        rmtree(self.base)
        self.src = self.base / "defaut"
        self.dst = self.base / "perso"
        write_json_file(self.src / "workspaces.json", {"version": "1.0", "workspaces": []})
        write_json_file(self.src / "ui_state.json", {"theme": "sobre"})
        (self.src / "skills-library" / "s1").mkdir(parents=True)
        (self.src / "skills-library" / "s1" / "SKILL.md").write_text("x\n", encoding="utf-8")
        self.dst.mkdir(parents=True)

    def tearDown(self):
        rmtree(self.base)

    def _patch(self, custom=True, src=None, dst=None):
        return (
            mock.patch.object(workspace_io._config, "DATA_DIR_IS_CUSTOM", custom),
            mock.patch.object(workspace_io._config, "DATA_DIR", dst or self.dst),
            mock.patch.object(workspace_io._data_migration, "DEFAULT_DATA_DIR", src or self.src),
        )

    def _pending(self, **kw):
        a, b, c = self._patch(**kw)
        with a, b, c:
            return workspace_io.pending_data_migration()

    def test_fichiers_a_copier_signales(self):
        # Un fichier déjà identique et un en conflit : seuls les manquants comptent.
        write_json_file(self.dst / "workspaces.json", {"version": "1.0", "workspaces": []})
        write_json_file(self.dst / "ui_state.json", {"theme": "pop"})
        before = sorted(p.name for p in self.dst.rglob("*"))
        mig = self._pending()
        self.assertEqual(mig["to_copy"], 1)
        self.assertEqual(mig["conflicts"], 1)
        self.assertEqual(mig["sample"], ["skills-library/s1/SKILL.md"])
        self.assertEqual(mig["command"], "python server.py --migrate-data")
        self.assertEqual(mig["data_dir"], str(self.dst))
        # Lecture seule : rien n'est copié.
        self.assertEqual(sorted(p.name for p in self.dst.rglob("*")), before)

    def test_dossier_par_defaut_aucun_signal(self):
        self.assertIsNone(self._pending(custom=False))

    def test_tout_deja_migre_aucun_signal(self):
        write_json_file(self.dst / "workspaces.json", {"version": "1.0", "workspaces": []})
        write_json_file(self.dst / "ui_state.json", {"theme": "pop"})
        (self.dst / "skills-library" / "s1").mkdir(parents=True)
        (self.dst / "skills-library" / "s1" / "SKILL.md").write_text("x\n", encoding="utf-8")
        self.assertIsNone(self._pending())

    def test_variable_pointant_sur_le_defaut_aucun_signal(self):
        self.assertIsNone(self._pending(dst=self.src))

    def test_source_absente_aucun_signal(self):
        self.assertIsNone(self._pending(src=self.base / "inexistant"))

    def test_sanity_check_expose_la_cle(self):
        a, b, c = self._patch()
        with a, b, c:
            r = workspace_io.sanity_check()
        self.assertEqual(r["data_migration"]["to_copy"], 3)
        # Bac à sable sans NEBULA_DATA_DIR : clé présente, valeur nulle.
        self.assertIsNone(workspace_io.sanity_check()["data_migration"])


if __name__ == "__main__":
    unittest.main()
