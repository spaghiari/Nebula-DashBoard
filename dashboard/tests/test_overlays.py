"""api_overlays : liste, application idempotente, exclusion des artefacts de build.

Overlay synthétique construit dans le bac à sable, plus un test sur une
copie de l'overlay réel `templates/claude-self-improving` (ignoré s'il est
absent de l'installation).
"""
from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path

from _support import DASHBOARD_DIR, make_workspace, reset_sandbox, write_json_file
from dashcore import api_overlays as ov
from dashcore.config import TEMPLATES_DIR

REAL_OVERLAY = DASHBOARD_DIR.parent / "templates" / "claude-self-improving"


def _write(p: Path, content: str | bytes) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        p.write_bytes(content)
    else:
        p.write_text(content, encoding="utf-8")


def _build_overlay(marker_extra: dict | None = None) -> Path:
    d = TEMPLATES_DIR / "ov1"
    marker = {"id": "ov1", "label": "Overlay test", "description": "d",
              "signature_file": ".claude/sig.md"}
    marker.update(marker_extra or {})
    write_json_file(d / ov.OVERLAY_MARKER, marker)
    _write(d / "CLAUDE.md", "# {{label}} complet\n")
    _write(d / "CLAUDE.self-improving.md",
           "<!-- BEGIN claude-self-improving -->\nfragment {{label}}\n"
           "<!-- END claude-self-improving -->\n")
    _write(d / ".claude" / "sig.md", "signature\n")
    _write(d / ".claude" / "hooks" / "h.py", "print('{{label}}')\n")
    _write(d / ".claude" / "data.bin", b"\x00\x01binaire")
    _write(d / ".claude" / "equipe.md", "réservé équipe\n")
    _write(d / ".claude" / "seeds" / "ex.md", "EXEMPLE seed\n")
    # Artefacts de build : ni listés ni copiés.
    _write(d / ".claude" / "hooks" / "__pycache__" / "h.cpython-313.pyc", b"\x00pyc")
    _write(d / ".claude" / "hooks" / "__pycache__" / "notes.txt", "dans pycache\n")
    _write(d / "orphelin.pyc", b"\x00pyc")
    _write(d / "module.pyo", b"\x00pyo")
    return d


class IsJunkTests(unittest.TestCase):
    def test_cas(self):
        self.assertTrue(ov._is_junk(Path("a/__pycache__/x.pyc")))
        self.assertTrue(ov._is_junk(Path("__pycache__/notes.txt")))
        self.assertTrue(ov._is_junk(Path("x.pyc")))
        self.assertTrue(ov._is_junk(Path("x.pyo")))
        self.assertFalse(ov._is_junk(Path("a/b.py")))
        self.assertFalse(ov._is_junk(Path("pycache/x.py")))
        self.assertFalse(ov._is_junk(Path("x.pyc.md")))


class ListOverlaysTests(unittest.TestCase):
    def setUp(self):
        reset_sandbox()
        _build_overlay()

    def test_template_normal_ignore(self):
        ids = [o["id"] for o in ov.list_overlays()]
        self.assertEqual(ids, ["ov1"])  # `blank` (template normal) exclu

    def test_fichiers_sans_artefacts(self):
        o = ov.list_overlays()[0]
        self.assertEqual(sorted(o["files"]), sorted([
            "CLAUDE.md", "CLAUDE.self-improving.md", ".claude/sig.md",
            ".claude/hooks/h.py", ".claude/data.bin", ".claude/equipe.md",
            ".claude/seeds/ex.md",
        ]))
        self.assertEqual(o["file_count"], 7)
        self.assertFalse(any("__pycache__" in f or f.endswith((".pyc", ".pyo")) for f in o["files"]))
        self.assertEqual(o["signature_file"], ".claude/sig.md")

    def test_get_overlay(self):
        self.assertEqual(ov.get_overlay("ov1")["dir_id"], "ov1")
        self.assertIsNone(ov.get_overlay("absent"))
        self.assertIsNone(ov.get_overlay("../x"))


class ApplyOverlayTests(unittest.TestCase):
    def setUp(self):
        reset_sandbox()
        _build_overlay({
            "mode_gated": [{"path": ".claude/equipe.md", "modes": ["equipe"]}],
            "depth": {"minimal_keep": ["CLAUDE.md", ".claude/sig.md"]},
            "seeds": [{"seed": ".claude/seeds/ex.md", "target": ".claude/sig.md"}],
        })
        self.ws = make_workspace("w1")
        (self.ws / "CLAUDE.md").unlink()

    def _apply(self, **opts):
        return ov.apply_overlay("w1", "ov1", {"label": "Mon WS"}, opts or {"depth": "complete"})

    def test_ids_invalides(self):
        self.assertEqual(ov.apply_overlay("../x", "ov1", {})[0], 400)
        self.assertEqual(ov.apply_overlay("w1", "../x", {})[0], 400)
        self.assertEqual(ov.apply_overlay("w1", "absent", {})[0], 404)

    def test_complet_copie_sans_artefacts(self):
        status, p = self._apply()
        self.assertEqual(status, 200, p)
        self.assertFalse((self.ws / ".claude" / "hooks" / "__pycache__").exists())
        self.assertFalse((self.ws / "orphelin.pyc").exists())
        self.assertFalse((self.ws / "module.pyo").exists())
        self.assertTrue(all("__pycache__" not in c and not c.endswith((".pyc", ".pyo"))
                            for c in p["copied"]))
        # Placeholders rendus (texte), binaire copié tel quel.
        self.assertEqual((self.ws / "CLAUDE.md").read_text(encoding="utf-8"), "# Mon WS complet\n")
        self.assertEqual((self.ws / ".claude" / "hooks" / "h.py").read_text(encoding="utf-8"),
                         "print('Mon WS')\n")
        self.assertEqual((self.ws / ".claude" / "data.bin").read_bytes(), b"\x00\x01binaire")
        # Fragment et seeds jamais copiés comme fichiers autonomes.
        self.assertFalse((self.ws / "CLAUDE.self-improving.md").exists())
        self.assertFalse((self.ws / ".claude" / "seeds").exists())
        # Seed appendé au registre cible (profondeur complète).
        self.assertIn("EXEMPLE seed", (self.ws / ".claude" / "sig.md").read_text(encoding="utf-8"))
        # Mode solo : fichier réservé à l'équipe exclu.
        self.assertFalse((self.ws / ".claude" / "equipe.md").exists())
        self.assertIn({"path": ".claude/equipe.md", "reason": "mode-gated (hors mode solo)"},
                      p["skipped"])
        # settings.local.json posé (solo -> validate_author false).
        self.assertEqual(json.loads((self.ws / ".claude" / "settings.local.json")
                                    .read_text(encoding="utf-8")), {"validate_author": False})
        self.assertTrue(ov.overlay_is_active(self.ws, ov.get_overlay("ov1")))

    def test_idempotent(self):
        self._apply()
        sig = (self.ws / ".claude" / "sig.md").read_text(encoding="utf-8")
        status, p = self._apply()
        self.assertEqual(status, 200, p)
        self.assertEqual(p["copied"], [])
        self.assertEqual(p["seeded"], [])
        self.assertEqual((self.ws / ".claude" / "sig.md").read_text(encoding="utf-8"), sig)
        reasons = {s["path"]: s["reason"] for s in p["skipped"]}
        self.assertEqual(reasons[".claude/hooks/h.py"], "already present")

    def test_fichier_utilisateur_jamais_ecrase(self):
        (self.ws / ".claude" / "hooks").mkdir(parents=True)
        (self.ws / ".claude" / "hooks" / "h.py").write_text("à moi\n", encoding="utf-8")
        self._apply()
        self.assertEqual((self.ws / ".claude" / "hooks" / "h.py").read_text(encoding="utf-8"),
                         "à moi\n")

    def test_claude_md_existant_recoit_le_fragment_une_seule_fois(self):
        (self.ws / "CLAUDE.md").write_text("# perso\n", encoding="utf-8")
        status, p = self._apply()
        self.assertEqual(p["appended"], ["CLAUDE.md"])
        text = (self.ws / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# perso\n"))
        self.assertIn("fragment Mon WS", text)
        status, p = self._apply()
        self.assertEqual(p["appended"], [])
        self.assertEqual((self.ws / "CLAUDE.md").read_text(encoding="utf-8").count("BEGIN"), 1)

    def test_profondeur_minimale(self):
        status, p = self._apply(mode="solo")  # solo -> minimal par défaut
        self.assertEqual(status, 200, p)
        self.assertEqual(p["options"]["depth"], "minimal")
        self.assertTrue((self.ws / ".claude" / "sig.md").exists())
        self.assertFalse((self.ws / ".claude" / "hooks" / "h.py").exists())
        self.assertNotIn("EXEMPLE seed", (self.ws / ".claude" / "sig.md").read_text(encoding="utf-8"))

    def test_hook_reference_absent_refuse(self):
        _write(TEMPLATES_DIR / "ov1" / ".claude" / "settings.json",
               json.dumps({"hooks": {"x": 'python "${CLAUDE_PROJECT_DIR}/.claude/hooks/absent.py"'}}))
        status, p = self._apply()
        self.assertEqual(status, 500)
        self.assertEqual(p["missing_hooks"], [".claude/hooks/absent.py"])


HOOK_CMD = 'python "${CLAUDE_PROJECT_DIR}/.claude/hooks/h2.py"'
OTHER_CMD = 'python "${CLAUDE_PROJECT_DIR}/.claude/hooks/other.py"'


def _build_dependent(marker_extra: dict | None = None) -> Path:
    """Second overlay `ov2` qui requiert `ov1`, avec settings_patch + generators."""
    d = TEMPLATES_DIR / "ov2"
    marker = {
        "id": "ov2", "label": "Dépendant", "signature_file": ".claude/sig2.md",
        "requires": ["ov1"],
        "features": [{"icon": "cpu", "title": "F1", "text": "t1"}, "pas un dict"],
        "after_apply": "Ensuite...",
        "settings_patch": {
            "hooks": {"PreToolUse": [{"matcher": "Edit|Write", "hooks": [
                {"type": "command", "command": HOOK_CMD, "timeout": 5}]}]},
            "permissions": {"allow": ["Bash(echo:*)"]},
            "newKey": "posée",
        },
        "generators": ["inconnu"],
    }
    marker.update(marker_extra or {})
    write_json_file(d / ov.OVERLAY_MARKER, marker)
    _write(d / ".claude" / "sig2.md", "sig2\n")
    _write(d / ".claude" / "hooks" / "h2.py", "print('h2')\n")
    return d


class RequiresAndPatchTests(unittest.TestCase):
    def setUp(self):
        reset_sandbox()
        # ov1 exploite les options de bootstrap (profondeur déclarée) : il
        # pose settings.local.json ; ov2 (sans) ne doit pas le réécrire.
        _build_overlay({"depth": {"minimal_keep": ["CLAUDE.md", ".claude/sig.md"]}})
        _build_dependent()
        self.ws = make_workspace("w1")
        self.vars = {"name": "w1", "label": "W"}

    def test_liste_expose_le_declaratif(self):
        o2 = ov.get_overlay("ov2")
        self.assertEqual(o2["requires"], ["ov1"])
        self.assertEqual(o2["features"], [{"icon": "cpu", "title": "F1", "text": "t1"}])
        self.assertEqual(o2["after_apply"], "Ensuite...")
        self.assertEqual(o2["generators"], ["inconnu"])
        self.assertTrue(o2["has_settings_patch"])
        self.assertFalse(o2["bootstrap_options"])
        o1 = ov.get_overlay("ov1")
        self.assertEqual(o1["requires"], [])
        self.assertEqual(o1["features"], [])
        self.assertFalse(o1["has_settings_patch"])

    def test_prerequis_inactif_409_sans_ecriture(self):
        status, p = ov.apply_overlay("w1", "ov2", self.vars)
        self.assertEqual(status, 409)
        self.assertIn("Overlay test", p["error"])
        self.assertEqual(p["missing_requires"], [{"id": "ov1", "label": "Overlay test"}])
        self.assertFalse((self.ws / ".claude" / "sig2.md").exists())
        self.assertFalse((self.ws / ".claude" / "settings.json").exists())

    def test_settings_patch_fusion_idempotente(self):
        ov.apply_overlay("w1", "ov1", self.vars, {"depth": "complete"})
        settings = self.ws / ".claude" / "settings.json"
        write_json_file(settings, {
            "permissions": {"allow": ["Bash(git status)"], "deny": ["Bash(rm -rf:*)"]},
            "hooks": {"PreToolUse": [{"matcher": "Edit|Write", "hooks": [
                {"type": "command", "command": OTHER_CMD}]},
                {"matcher": "Bash", "hooks": []}]},
            "newKey": "à moi",
        })
        _write(self.ws / ".claude" / "hooks" / "other.py", "")
        status, p = ov.apply_overlay("w1", "ov2", self.vars)
        self.assertEqual(status, 200, p.get("error"))
        self.assertEqual(p["settings_patched"], [".claude/settings.json"])
        self.assertIn({"path": "generator:inconnu", "reason": "générateur inconnu"}, p["skipped"])
        data = json.loads(settings.read_text(encoding="utf-8"))
        edit = next(e for e in data["hooks"]["PreToolUse"] if e["matcher"] == "Edit|Write")
        self.assertEqual([h["command"] for h in edit["hooks"]], [OTHER_CMD, HOOK_CMD])
        self.assertEqual(data["permissions"]["allow"], ["Bash(git status)", "Bash(echo:*)"])
        self.assertEqual(data["permissions"]["deny"], ["Bash(rm -rf:*)"])
        self.assertEqual(data["newKey"], "à moi")  # scalaire utilisateur jamais écrasé
        self.assertTrue(any(e["matcher"] == "Bash" for e in data["hooks"]["PreToolUse"]))
        # Deuxième application : aucune écriture, aucun doublon.
        before = settings.read_text(encoding="utf-8")
        status, p = ov.apply_overlay("w1", "ov2", self.vars)
        self.assertEqual(p["settings_patched"], [])
        self.assertEqual(settings.read_text(encoding="utf-8"), before)
        data = json.loads(before)
        edit = next(e for e in data["hooks"]["PreToolUse"] if e["matcher"] == "Edit|Write")
        self.assertEqual(len(edit["hooks"]), 2)

    def test_settings_patch_cree_si_absent(self):
        ov.apply_overlay("w1", "ov1", self.vars, {"depth": "complete"})
        self.assertFalse((self.ws / ".claude" / "settings.json").exists())
        status, p = ov.apply_overlay("w1", "ov2", self.vars)
        self.assertEqual(status, 200, p.get("error"))
        data = json.loads((self.ws / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(data["hooks"]["PreToolUse"][0]["hooks"][0]["command"], HOOK_CMD)
        self.assertEqual(data["newKey"], "posée")
        self.assertEqual(ov._missing_hook_refs(self.ws), [])

    def test_fusion_groupe_sans_matcher(self):
        """Un événement sans `matcher` (UserPromptSubmit) : la clé absente,
        `null` et `""` désignent le même groupe ; aucun doublon à la
        ré-application, les hooks utilisateur du groupe sont gardés."""
        patch = [{"hooks": [{"type": "command", "command": HOOK_CMD, "timeout": 5}]}]
        existing = [{"matcher": "", "hooks": [{"type": "command", "command": OTHER_CMD}]}]
        self.assertTrue(ov._merge_hook_lists(existing, patch))
        self.assertEqual(len(existing), 1)
        self.assertEqual([h["command"] for h in existing[0]["hooks"]], [OTHER_CMD, HOOK_CMD])
        self.assertFalse(ov._merge_hook_lists(existing, patch))  # idempotent
        self.assertEqual(len(existing[0]["hooks"]), 2)
        existing = [{"matcher": None, "hooks": []}]
        self.assertTrue(ov._merge_hook_lists(existing, patch))
        self.assertEqual(len(existing), 1)
        self.assertFalse(ov._merge_hook_lists(existing, patch))
        # Liste vide : le groupe est copié tel quel (sans clé matcher).
        existing = []
        self.assertTrue(ov._merge_hook_lists(existing, patch))
        self.assertEqual(existing, patch)
        self.assertFalse(ov._merge_hook_lists(existing, patch))
        # Un groupe AVEC matcher reste distinct du groupe sans matcher.
        existing = [{"matcher": "Bash", "hooks": [{"type": "command", "command": HOOK_CMD}]}]
        self.assertTrue(ov._merge_hook_lists(existing, patch))
        self.assertEqual(len(existing), 2)
        # Bout en bout : settings_patch avec UserPromptSubmit, deux applications.
        _build_dependent({"settings_patch": {"hooks": {"UserPromptSubmit": patch}}})
        ov.apply_overlay("w1", "ov1", self.vars, {"depth": "complete"})
        settings = self.ws / ".claude" / "settings.json"
        write_json_file(settings, {"hooks": {"UserPromptSubmit": [{"hooks": [{"type": "command", "command": OTHER_CMD}]}]}})
        _write(self.ws / ".claude" / "hooks" / "other.py", "")
        status, p = ov.apply_overlay("w1", "ov2", self.vars)
        self.assertEqual(status, 200, p.get("error"))
        self.assertEqual(p["settings_patched"], [".claude/settings.json"])
        data = json.loads(settings.read_text(encoding="utf-8"))
        self.assertEqual(len(data["hooks"]["UserPromptSubmit"]), 1)
        self.assertEqual([h["command"] for h in data["hooks"]["UserPromptSubmit"][0]["hooks"]], [OTHER_CMD, HOOK_CMD])
        before = settings.read_text(encoding="utf-8")
        status, p = ov.apply_overlay("w1", "ov2", self.vars)
        self.assertEqual(p["settings_patched"], [])
        self.assertEqual(settings.read_text(encoding="utf-8"), before)

    def test_settings_json_corrompu_409_jamais_ecrase(self):
        ov.apply_overlay("w1", "ov1", self.vars, {"depth": "complete"})
        settings = self.ws / ".claude" / "settings.json"
        settings.write_text("{corrompu", encoding="utf-8")
        status, p = ov.apply_overlay("w1", "ov2", self.vars)
        self.assertEqual(status, 409)
        self.assertIn("illisible", p["error"])
        self.assertEqual(settings.read_text(encoding="utf-8"), "{corrompu")

    def test_second_overlay_ne_reecrit_pas_le_mode(self):
        ov.apply_overlay("w1", "ov1", self.vars, {"mode": "equipe", "depth": "complete"})
        local = self.ws / ".claude" / "settings.local.json"
        self.assertEqual(json.loads(local.read_text(encoding="utf-8")), {"validate_author": True})
        ov.apply_overlay("w1", "ov2", self.vars, {})  # mode solo par défaut
        self.assertEqual(json.loads(local.read_text(encoding="utf-8")), {"validate_author": True})

    def test_sans_profondeur_declaree_rien_exclu(self):
        ov.apply_overlay("w1", "ov1", self.vars, {"depth": "complete"})
        status, p = ov.apply_overlay("w1", "ov2", self.vars, {"depth": "minimal"})
        self.assertEqual(status, 200, p.get("error"))
        self.assertIn(".claude/hooks/h2.py", p["copied"])

    def test_no_copy(self):
        """Un chemin `no_copy` n'est ni liste, ni compte, ni copie."""
        d = TEMPLATES_DIR / "ov1"
        marker = json.loads((d / ov.OVERLAY_MARKER).read_text(encoding="utf-8"))
        marker["no_copy"] = ["DOC.md"]
        write_json_file(d / ov.OVERLAY_MARKER, marker)
        _write(d / "DOC.md", "doc du module\n")
        listed = ov.get_overlay("ov1")
        self.assertNotIn("DOC.md", listed["files"])
        status, p = ov.apply_overlay("w1", "ov1", self.vars, {"depth": "complete"})
        self.assertEqual(status, 200, p.get("error"))
        self.assertNotIn("DOC.md", p["copied"])
        self.assertFalse((self.ws / "DOC.md").exists())
        self.assertNotIn("DOC.md", [s["path"] for s in p["skipped"]])

    def test_usage_et_ordre(self):
        make_workspace("w2")
        ov.apply_overlay("w1", "ov1", self.vars, {"depth": "complete"})
        ov.apply_overlay("w1", "ov2", self.vars)
        ov.apply_overlay("w2", "ov1", {"name": "w2", "label": "W2"}, {"depth": "complete"})
        self.assertEqual(ov.overlays_usage(), {"ov1": ["w1", "w2"], "ov2": ["w1"]})
        self.assertEqual(ov.order_by_requires(["ov2", "ov1"]), (["ov1", "ov2"], {}))
        ordered, errors = ov.order_by_requires(["ov2"])
        self.assertEqual(ordered, [])
        self.assertIn("Overlay test", errors["ov2"])
        self.assertEqual(ov.order_by_requires(["inconnu", "ov1"]), (["inconnu", "ov1"], {}))


@unittest.skipUnless((REAL_OVERLAY / ov.OVERLAY_MARKER).is_file(), "overlay réel absent")
class RealOverlayTests(unittest.TestCase):
    """L'overlay livré, avec un `__pycache__` comme après exécution de ses hooks."""

    def setUp(self):
        reset_sandbox()
        self.dst = TEMPLATES_DIR / "claude-self-improving"
        shutil.copytree(REAL_OVERLAY, self.dst,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))
        self.expected = sorted(p.relative_to(self.dst).as_posix() for p in self.dst.rglob("*")
                               if p.is_file() and p.name != ov.OVERLAY_MARKER)
        _write(self.dst / ".claude" / "hooks" / "__pycache__" / "x.cpython-313.pyc", b"\x00")
        self.ws = make_workspace("w1")

    def test_compte_hors_pycache(self):
        o = ov.get_overlay("claude-self-improving")
        self.assertEqual(sorted(o["files"]), self.expected)

    def test_application_complete_et_minimale_coherentes(self):
        for depth in ("complete", "minimal"):
            with self.subTest(depth=depth):
                reset_sandbox()
                shutil.copytree(REAL_OVERLAY, self.dst,
                                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))
                _write(self.dst / ".claude" / "hooks" / "__pycache__" / "x.pyc", b"\x00")
                ws = make_workspace("w1")
                (ws / "CLAUDE.md").unlink()
                status, p = ov.apply_overlay("w1", "claude-self-improving",
                                             {"label": "W", "name": "w1"}, {"depth": depth})
                self.assertEqual(status, 200, p.get("error"))
                self.assertFalse(list(ws.rglob("__pycache__")))


if __name__ == "__main__":
    unittest.main()
