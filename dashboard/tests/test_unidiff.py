"""unidiff : applicateur de diff unifié strict, un seul fichier, chemin confiné,
fichier intact en cas d'échec."""
from __future__ import annotations

import os
import subprocess
import sys
import unittest

from _support import SANDBOX, rmtree
from dashcore import unidiff as ud

BODY = "# Rôle\nTu cherches.\n\n# Sortie\n## Conclusions\n- fait [src]\n"
GOOD = ("--- a/.claude/team/agents/researcher.md\n+++ b/.claude/team/agents/researcher.md\n"
        "@@ -1,3 +1,4 @@\n # Rôle\n Tu cherches.\n+Cite toujours la source.\n \n")


def _diff(rel: str, old: str = " Tu cherches.", new: str = "+ajout") -> str:
    return f"--- a/{rel}\n+++ b/{rel}\n@@ -2,1 +2,2 @@\n{old}\n{new}\n"


class UnidiffTests(unittest.TestCase):
    def setUp(self):
        self.root = SANDBOX / "unidiff"
        rmtree(self.root)
        self.target = self.root / ".claude" / "team" / "agents" / "researcher.md"
        self.target.parent.mkdir(parents=True)
        self.target.write_bytes(BODY.encode("utf-8"))

    def test_application_reussie(self):
        r = ud.apply_diff(GOOD, self.root)
        self.assertEqual(r["path"], ".claude/team/agents/researcher.md")
        self.assertEqual(self.target.read_text(encoding="utf-8"),
                         "# Rôle\nTu cherches.\nCite toujours la source.\n\n# Sortie\n"
                         "## Conclusions\n- fait [src]\n")

    def test_crlf_et_bom_conserves(self):
        self.target.write_bytes(b"\xef\xbb\xbf" + BODY.replace("\n", "\r\n").encode("utf-8"))
        ud.apply_diff(GOOD, self.root)
        raw = self.target.read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        self.assertIn("Tu cherches.\r\nCite toujours la source.\r\n".encode("utf-8"), raw)
        self.assertNotIn(b"\n\n", raw.replace(b"\r\n", b"X"))

    def test_numero_de_ligne_decale_mais_contexte_unique(self):
        shifted = GOOD.replace("@@ -1,3 +1,4 @@", "@@ -7,3 +7,4 @@")
        ud.apply_diff(shifted, self.root)
        self.assertIn("Cite toujours", self.target.read_text(encoding="utf-8"))

    def _refused(self, diff: str, **kw) -> str:
        before = self.target.read_bytes()
        with self.assertRaises(ud.DiffError) as cm:
            ud.apply_diff(diff, self.root, **kw)
        self.assertEqual(self.target.read_bytes(), before)  # jamais modifié
        return str(cm.exception)

    def test_contexte_inexact_refuse(self):
        self._refused(GOOD.replace(" Tu cherches.", " Tu cherches !"))

    def test_contexte_ambigu_refuse(self):
        self.target.write_text("a\nb\na\nb\n", encoding="utf-8")
        self._refused("--- a/.claude/team/agents/researcher.md\n+++ b/.claude/team/agents/researcher.md\n"
                      "@@ -9,2 +9,2 @@\n a\n-b\n+c\n")

    def test_echec_au_second_hunk_rien_ecrit(self):
        diff = GOOD + "@@ -5,1 +6,1 @@\n-## Absent\n+## X\n"
        self._refused(diff)

    def test_multi_fichiers_refuse(self):
        other = GOOD.replace("researcher.md", "executor.md")
        self.assertIn("un seul fichier", self._refused(GOOD + other))

    def test_creation_et_suppression_refusees(self):
        self._refused("--- /dev/null\n+++ b/.claude/team/agents/researcher.md\n@@ -0,0 +1 @@\n+x\n")
        self._refused("--- a/.claude/team/agents/researcher.md\n+++ /dev/null\n@@ -1 +0,0 @@\n-# Rôle\n")

    def test_chemin_hors_cible_refuse(self):
        msg = self._refused(GOOD, allowed=lambda rel: rel.startswith(".claude/memory/"))
        self.assertIn("non autorisée", msg)
        self.assertIn("cible annoncée", self._refused(GOOD, expected_path=".claude/team.json"))

    def test_strict_case_exige_le_chemin_reel(self):
        (self.root / ".claude" / "team" / "agents" / "critic.md").write_text("x\n", encoding="utf-8")
        ok = ".claude/team/agents/critic.md"
        self.assertEqual(ud.check_rel_path(self.root, ok, strict_case=True),
                         (self.root / ok).resolve())
        # Fichier absent : sa casse demandée est conservée, accepté.
        self.assertTrue(ud.check_rel_path(self.root, ".claude/team/agents/Nouveau.md", strict_case=True))
        if sys.platform != "win32":
            self.skipTest("système de fichiers sensible à la casse")
        for rel in (".claude/team/agents/Critic.md", ".claude/team/agents/CRITIC.MD",
                    ".Claude/team/agents/critic.md"):
            with self.subTest(rel=rel):
                # Comportement historique (non strict) : accepté sous Windows.
                ud.check_rel_path(self.root, rel)
                with self.assertRaises(ud.DiffError) as cm:
                    ud.check_rel_path(self.root, rel, strict_case=True)
                self.assertIn("casse", str(cm.exception))

    def test_chemins_dangereux_refuses(self):
        mem = self.root / ".claude" / "memory"
        mem.mkdir(parents=True)
        (self.root / ".claude" / "team" / "agents" / "critic.md").write_text("x\n", encoding="utf-8")
        for rel in (".claude/memory/../team/agents/critic.md",
                    ".claude/memory/../evals/eval-set.jsonl",
                    ".claude/memory/../../outside.md", ".claude/memory/./x.md",
                    "/etc/passwd", "C:/Windows/x.md", ".claude\\memory\\x.md",
                    ".claude//memory/x.md", ""):
            with self.subTest(rel=rel), self.assertRaises(ud.DiffError):
                ud.check_rel_path(self.root, rel)
        # Refus par la règle de segment elle-même (avant toute résolution).
        for rel in (".claude/memory/./x.md", ".claude/memory/a/../x.md"):
            with self.assertRaises(ud.DiffError) as cm:
                ud.check_rel_path(self.root, rel)
            self.assertIn("segment", str(cm.exception))
        self.assertEqual(ud.check_rel_path(self.root, ".claude/memory/conventions/x.md"),
                         (mem / "conventions" / "x.md").resolve())

    def test_lien_ou_jonction_qui_sort_refuse(self):
        outside = SANDBOX / "unidiff-dehors"
        rmtree(outside)
        outside.mkdir()
        (outside / "x.md").write_text("a\n", encoding="utf-8")
        mem = self.root / ".claude" / "memory"
        mem.mkdir(parents=True)
        link = mem / "lien"
        if sys.platform == "win32":
            r = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)],
                               capture_output=True, text=True)
            if r.returncode != 0:
                self.skipTest(f"jonction impossible : {r.stdout} {r.stderr}")
        else:
            os.symlink(outside, link)
        try:
            with self.assertRaises(ud.DiffError):
                ud.check_rel_path(self.root, ".claude/memory/lien/x.md")
            diff = "--- a/.claude/memory/lien/x.md\n+++ b/.claude/memory/lien/x.md\n@@ -1 +1 @@\n-a\n+b\n"
            with self.assertRaises(ud.DiffError):
                ud.apply_diff(diff, self.root)
            self.assertEqual((outside / "x.md").read_text(encoding="utf-8"), "a\n")
        finally:
            if sys.platform == "win32":
                os.rmdir(link)
            else:
                link.unlink()

    def test_lien_interne_vers_une_zone_interdite_refuse(self):
        """Un lien qui reste dans le workspace mais mène ailleurs (ex. vers
        `.claude/evals`) est refusé : le chemin résolu doit être le chemin demandé."""
        evals = self.root / ".claude" / "evals"
        evals.mkdir(parents=True)
        (evals / "x.md").write_text("a\n", encoding="utf-8")
        mem = self.root / ".claude" / "memory"
        mem.mkdir(parents=True)
        link = mem / "raccourci"
        if sys.platform == "win32":
            r = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(evals)],
                               capture_output=True, text=True)
            if r.returncode != 0:
                self.skipTest("jonction impossible")
        else:
            os.symlink(evals, link)
        try:
            with self.assertRaises(ud.DiffError) as cm:
                ud.check_rel_path(self.root, ".claude/memory/raccourci/x.md")
            self.assertIn("lien", str(cm.exception))
        finally:
            os.rmdir(link) if sys.platform == "win32" else link.unlink()

    def test_fichier_absent_et_diff_vide(self):
        self._refused(_diff(".claude/team/agents/absent.md"))
        self._refused("")
        self._refused("--- a/x.md\n+++ b/x.md\n@@ -1 +1 @@\n a\n")  # sans modification

    def test_ecriture_atomique_sans_residu(self):
        ud.apply_diff(GOOD, self.root)
        leftovers = [p.name for p in self.target.parent.iterdir() if p.name.endswith(".tmp")]
        self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
