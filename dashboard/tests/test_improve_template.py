"""Gabarit /improve : /improve manuel uniquement (plus de runner Nebula)."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

TPL = Path(__file__).resolve().parents[2] / "templates" / "claude-team"
IMPROVE = TPL / ".claude" / "commands" / "improve.md"
LOOP = TPL / ".claude" / "memory" / "conventions" / "improvement-loop.md"
MARKER = TPL / ".nebula-overlay.json"


class ImproveTemplateTests(unittest.TestCase):
    def test_mentions(self):
        for f in (IMPROVE, LOOP):
            text = f.read_text(encoding="utf-8")
            self.assertIn("failures_after", text, f.name)
            self.assertNotIn("runner: nebula", text, f.name)
            self.assertNotIn('runner: "nebula"', text, f.name)

    def test_pas_de_tiret_cadratin(self):
        for f in (IMPROVE, LOOP):
            self.assertNotIn("—", f.read_text(encoding="utf-8"), f.name)

    def test_marker_liste_improve(self):
        data = json.loads(MARKER.read_text(encoding="utf-8"))
        self.assertIn(".claude/commands/improve.md", data["managed"])


if __name__ == "__main__":
    unittest.main()
