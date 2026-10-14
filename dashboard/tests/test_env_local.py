"""env_local : store illisible -> refus d'écriture (aucun écrasement du coffre)."""
from __future__ import annotations

import sys
import unittest

from _support import reset_sandbox
from dashcore import env_local
from dashcore.config import ENV_ENC_FILE, ENV_FILE
from dashcore.env_crypto import ENC_HEADER
from dashcore.env_local import (
    EnvStoreUnreadable, delete_env_var, load_env_local, load_env_local_strict, set_env_var,
)


class PlainStoreTests(unittest.TestCase):
    def setUp(self):
        reset_sandbox()

    def test_set_puis_delete_en_clair(self):
        self.assertEqual(set_env_var("TOKEN_A", "v1")[0], 200)
        self.assertEqual(set_env_var("TOKEN_B", "v2")[0], 200)
        self.assertEqual(load_env_local_strict(), {"TOKEN_A": "v1", "TOKEN_B": "v2"})
        self.assertEqual(delete_env_var("TOKEN_A")[0], 200)
        self.assertEqual(load_env_local(), {"TOKEN_B": "v2"})

    def test_preserve_commentaires(self):
        ENV_FILE.write_text("# secret\nA=1\n", encoding="utf-8")
        set_env_var("A", "2")
        self.assertIn("# secret", ENV_FILE.read_text(encoding="utf-8"))

    def test_caracteres_invisibles_retires(self):
        set_env_var("CHEMIN", "\u202aC:\\outil\\x.exe")
        self.assertEqual(load_env_local()["CHEMIN"], "C:\\outil\\x.exe")

    def test_cle_ou_valeur_invalide(self):
        self.assertEqual(set_env_var("1ABC", "x")[0], 400)
        self.assertEqual(set_env_var("ABC", "a\nb")[0], 400)

    def test_store_clair_illisible_leve_en_strict(self):
        ENV_FILE.write_bytes(b"A=\xff\xfe\n")
        with self.assertRaises(EnvStoreUnreadable):
            load_env_local_strict()


class EncryptedStoreUnreadableTests(unittest.TestCase):
    """Coffre chiffré illisible : header invalide -> pas besoin de DPAPI."""

    def setUp(self):
        reset_sandbox()
        self.garbage = b"PAS-UN-COFFRE-NEBULA"
        ENV_ENC_FILE.write_bytes(self.garbage)

    def test_lecture_stricte_leve(self):
        with self.assertRaises(EnvStoreUnreadable):
            load_env_local_strict()

    def test_lecture_tolerante_vide_sans_retomber_sur_le_clair(self):
        ENV_FILE.write_text("A=clair\n", encoding="utf-8")
        self.assertEqual(load_env_local(), {})

    def test_set_refuse_et_coffre_intact(self):
        status, payload = set_env_var("NOUVELLE", "x")
        self.assertEqual(status, 409)
        self.assertIn("illisible", payload["error"])
        self.assertEqual(ENV_ENC_FILE.read_bytes(), self.garbage)

    def test_delete_refuse_et_coffre_intact(self):
        self.assertEqual(delete_env_var("A")[0], 409)
        self.assertEqual(ENV_ENC_FILE.read_bytes(), self.garbage)


@unittest.skipUnless(sys.platform == "win32", "DPAPI : Windows uniquement")
class DpapiTests(unittest.TestCase):
    def setUp(self):
        reset_sandbox()

    def test_chiffrement_puis_blob_abime_refuse(self):
        set_env_var("A", "1")
        status, payload = env_local.enable_encryption()
        self.assertEqual(status, 200, payload)
        self.assertTrue(ENV_ENC_FILE.exists())
        self.assertEqual(set_env_var("B", "2")[0], 200)
        self.assertEqual(load_env_local_strict(), {"A": "1", "B": "2"})
        # Header valide mais blob DPAPI abîmé : déchiffrement impossible.
        ENV_ENC_FILE.write_bytes(ENC_HEADER + b"\x00" * 64)
        self.assertEqual(set_env_var("C", "3")[0], 409)
        self.assertEqual(ENV_ENC_FILE.read_bytes(), ENC_HEADER + b"\x00" * 64)


if __name__ == "__main__":
    unittest.main()
