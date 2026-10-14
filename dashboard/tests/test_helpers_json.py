"""helpers : lecture stricte, écriture atomique, rotation .bak sûre, BOM."""
from __future__ import annotations

import json
import unittest

import _support
from _support import ROOT, reset_sandbox
from dashcore.helpers import CorruptJsonError, read_json, read_json_strict, write_json


class ReadJsonTests(unittest.TestCase):
    def setUp(self):
        reset_sandbox()
        self.path = ROOT / "dashboard" / "data" / "x.json"

    def test_strict_absent_renvoie_le_defaut(self):
        self.assertEqual(read_json_strict(self.path, {"d": 1}), {"d": 1})

    def test_strict_corrompu_leve_avec_chemin(self):
        self.path.write_text("{pas du json", encoding="utf-8")
        with self.assertRaises(CorruptJsonError) as ctx:
            read_json_strict(self.path, {})
        self.assertEqual(ctx.exception.path, self.path)
        self.assertIn("x.json.bak", str(ctx.exception))

    def test_strict_non_utf8_leve(self):
        self.path.write_bytes(b'{"a": "\xff\xfe"}')
        with self.assertRaises(CorruptJsonError):
            read_json_strict(self.path, {})

    def test_tolerant_corrompu_renvoie_le_defaut(self):
        self.path.write_text("[1, 2", encoding="utf-8")
        self.assertEqual(read_json(self.path, {"d": 0}), {"d": 0})

    def test_bom_utf8_accepte(self):
        self.path.write_bytes(b"\xef\xbb\xbf" + json.dumps({"a": "é"}).encode("utf-8"))
        self.assertEqual(read_json_strict(self.path, {}), {"a": "é"})
        self.assertEqual(read_json(self.path, {}), {"a": "é"})


class WriteJsonTests(unittest.TestCase):
    def setUp(self):
        reset_sandbox()
        self.path = ROOT / "dashboard" / "data" / "w.json"
        self.bak = self.path.with_suffix(".json.bak")

    def test_ecriture_atomique_sans_tmp_residuel(self):
        write_json(self.path, {"a": [1, 2], "t": "é"})
        self.assertEqual(_support.read_json_file(self.path), {"a": [1, 2], "t": "é"})
        self.assertFalse(self.path.with_suffix(".json.tmp").exists())

    def test_cree_les_dossiers_parents(self):
        p = ROOT / "nouveau" / "sous" / "f.json"
        write_json(p, {"ok": True})
        self.assertTrue(p.exists())

    def test_bak_tourne_sur_fichier_valide(self):
        write_json(self.path, {"v": 1})
        write_json(self.path, {"v": 2})
        self.assertEqual(_support.read_json_file(self.bak), {"v": 1})
        self.assertEqual(_support.read_json_file(self.path), {"v": 2})

    def test_bak_preserve_si_fichier_courant_corrompu(self):
        write_json(self.path, {"v": 1})
        write_json(self.path, {"v": 2})          # .bak = {"v": 1}
        self.path.write_text("{corrompu", encoding="utf-8")
        write_json(self.path, {"v": 3})
        # Le .bak sain n'est PAS écrasé par le fichier corrompu...
        self.assertEqual(_support.read_json_file(self.bak), {"v": 1})
        # ... et le contenu corrompu est conservé à part.
        kept = list(self.path.parent.glob("w.json.corrupt-*"))
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].read_text(encoding="utf-8"), "{corrompu")
        self.assertEqual(_support.read_json_file(self.path), {"v": 3})


if __name__ == "__main__":
    unittest.main()
