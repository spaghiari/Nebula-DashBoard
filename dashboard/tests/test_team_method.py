"""Méthode de délégation sobre : présente dans les trois fichiers du module
claude-team, propagée aux projets existants par « Ré-appliquer »."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

TEAM = Path(__file__).resolve().parent.parent.parent / "templates" / "claude-team"
CLAUDE_MD = TEAM / "CLAUDE.claude-team.md"
ORCH = TEAM / ".claude" / "team" / "agents" / "orchestrator.md"
CMD = TEAM / ".claude" / "commands" / "team.md"
OVERLAY = TEAM / ".nebula-overlay.json"

BEGIN = "<!-- BEGIN claude-team -->"
END = "<!-- END claude-team -->"
TITLE = "Méthode de délégation sobre"
KEYWORDS = ("fichiers", "parallèle", "contrats", "executor",
            "tests ciblés", "suite complète", "temporaire")
EM_DASH = "—"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


class TeamMethodTests(unittest.TestCase):
    def test_section_et_mots_cles(self):
        for p in (CLAUDE_MD, ORCH, CMD):
            txt = _read(p)
            self.assertIn(TITLE, txt, p.name)
            section = txt[txt.index(TITLE):]
            for kw in KEYWORDS:
                self.assertIn(kw, section, f"{p.name}: {kw}")

    def test_section_entre_marqueurs(self):
        txt = _read(CLAUDE_MD)
        self.assertEqual(txt.count(BEGIN), 1)
        self.assertEqual(txt.count(END), 1)
        b, e, s = txt.index(BEGIN), txt.index(END), txt.index(TITLE)
        self.assertTrue(b < s < e)
        for kw in KEYWORDS:
            self.assertIn(kw, txt[b:e], kw)

    def test_pas_de_tiret_cadratin(self):
        for p in (CLAUDE_MD, ORCH, CMD):
            self.assertNotIn(EM_DASH, _read(p), p.name)

    def test_overlay_propage_la_methode(self):
        data = json.loads(_read(OVERLAY))
        self.assertIs(data["claude_md"]["refresh_block"], True)
        self.assertIn(".claude/commands/team.md", data["managed"])


if __name__ == "__main__":
    unittest.main()
