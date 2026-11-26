"""Titre d'onglet des terminaux lancés par Nebula : nom du projet, pas de la conversation.

Couvre : nettoyage du libellé, repli sur l'id, plafond de longueur, script de
titre intermédiaire (écrit une fois, réécrit s'il diffère, lancement sans titre
s'il ne s'écrit pas), ligne `cmd /k` transmise à `Popen` pour le lancement et la
reprise, variables d'environnement (libellé, désactivation du titre de Claude
Code), et, sous Windows, le TITRE RÉEL d'une console lue depuis l'intérieur :
`cmd` réécrit sinon le titre en « <titre>  - <commande> » (régression 2.8.0).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

from _support import SANDBOX, make_workspace, reset_sandbox
from dashcore import api_workspaces, workspace_io
from dashcore.config import (
    DATA_DIR, SCRIPTS_DIR, TERMINAL_TITLE_ENV, TERMINAL_TITLE_MAX, TERMINAL_TITLE_VAR,
    TERMINAL_TITLE_WRAPPER,
)


class TerminalTitleTests(unittest.TestCase):
    def test_libelle_simple_conserve(self):
        self.assertEqual(workspace_io.terminal_title("Home Assistant"), "Home Assistant")

    def test_caracteres_dangereux_retires(self):
        t = workspace_io.terminal_title('a & b | c < d > e ^ f " g % h\r\n')
        for ch in '&|<>^"%\r\n':
            self.assertNotIn(ch, t)
        self.assertIn("a", t)
        self.assertIn("h", t)

    def test_repli_sur_l_id_si_libelle_vide_ou_nettoye_a_vide(self):
        self.assertEqual(workspace_io.terminal_title(None, "ws-1"), "ws-1")
        self.assertEqual(workspace_io.terminal_title("", "ws-1"), "ws-1")
        self.assertEqual(workspace_io.terminal_title("&|<>", "ws-1"), "ws-1")

    def test_titre_vide_sans_libelle_ni_id(self):
        self.assertEqual(workspace_io.terminal_title(None, None), "")

    def test_longueur_plafonnee(self):
        self.assertEqual(len(workspace_io.terminal_title("x" * 500)), TERMINAL_TITLE_MAX)

    def test_accents_et_unicode_conserves(self):
        self.assertEqual(workspace_io.terminal_title("Projet été"), "Projet été")


class WrapperAndEnvTests(unittest.TestCase):
    def setUp(self):
        reset_sandbox()

    def test_commande_avec_script_de_titre(self):
        w = Path("C:/data dir/nebula-title.cmd")
        cmd = workspace_io.terminal_command('call "C:\\s\\a.bat"', w)
        self.assertEqual(cmd, f'cmd /k ""{w}" call "C:\\s\\a.bat""')

    def test_commande_sans_script(self):
        self.assertEqual(workspace_io.terminal_command("claude -c"), 'cmd /k "claude -c"')

    def test_le_libelle_n_est_jamais_dans_la_ligne_de_commande(self):
        cmd = workspace_io.terminal_command("claude -c", Path("C:/d/w.cmd"))
        self.assertNotIn("Mon projet", cmd)

    def test_env_porte_le_libelle_et_desactive_le_titre_auto(self):
        with mock.patch.dict(os.environ, {"NEBULA_TEST_VAR": "garde"}):
            env = workspace_io.terminal_env("Mon projet")
        self.assertEqual(env[TERMINAL_TITLE_ENV], "1")
        self.assertEqual(env[TERMINAL_TITLE_VAR], "Mon projet")
        self.assertEqual(env["NEBULA_TEST_VAR"], "garde")
        self.assertNotEqual(os.environ.get(TERMINAL_TITLE_ENV), "1")
        self.assertNotIn(TERMINAL_TITLE_VAR, os.environ)

    def test_env_sans_titre_retire_une_variable_heritee(self):
        with mock.patch.dict(os.environ, {TERMINAL_TITLE_VAR: "herite"}):
            env = workspace_io.terminal_env("")
        self.assertNotIn(TERMINAL_TITLE_VAR, env)

    def test_script_ecrit_dans_data_dir_et_reecrit_s_il_differe(self):
        p = workspace_io.ensure_title_wrapper()
        self.assertEqual(p, DATA_DIR / TERMINAL_TITLE_WRAPPER)
        body = p.read_bytes()
        self.assertIn(b"title %" + TERMINAL_TITLE_VAR.encode() + b"%", body)
        self.assertTrue(body.rstrip().endswith(b"%*"))
        p.write_bytes(b"@echo off\r\necho modifie\r\n")
        workspace_io.ensure_title_wrapper()
        self.assertEqual(p.read_bytes(), body)

    def test_ecriture_impossible_lancement_sans_titre(self):
        with mock.patch.object(Path, "write_bytes", side_effect=OSError("lecture seule")), \
             mock.patch.object(Path, "read_bytes", side_effect=OSError("absent")):
            self.assertIsNone(workspace_io.ensure_title_wrapper())


class LaunchCommandTests(unittest.TestCase):
    """La ligne de commande transmise à Popen (sans lancer de vrai terminal)."""

    def setUp(self):
        reset_sandbox()
        SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
        self.bat = SCRIPTS_DIR / "launch-w1.bat"
        self.bat.write_text("@echo off\n", encoding="utf-8")
        self.ws_dir = make_workspace("w1")
        self.wrapper = DATA_DIR / TERMINAL_TITLE_WRAPPER

    def _launch(self, label):
        proc = mock.Mock(pid=4242)
        with mock.patch.object(workspace_io, "IS_WINDOWS", True), \
             mock.patch.object(workspace_io.subprocess, "Popen", return_value=proc) as popen, \
             mock.patch("dashcore.active_sessions.register"):
            status, payload = workspace_io.launch_script(
                "launch-w1.bat", ws_id="w1", ws_label=label, ws_path=str(self.ws_dir))
        return status, payload, popen

    def test_lancement_passe_par_le_script_de_titre(self):
        status, payload, popen = self._launch("Home Assistant")
        self.assertEqual(status, 200, payload)
        args, kwargs = popen.call_args
        self.assertEqual(args[0], f'cmd /k ""{self.wrapper}" call "{self.bat}""')
        self.assertEqual(kwargs["env"][TERMINAL_TITLE_VAR], "Home Assistant")
        self.assertEqual(kwargs["env"][TERMINAL_TITLE_ENV], "1")
        self.assertFalse(kwargs["shell"])
        self.assertTrue(self.wrapper.is_file())

    def test_libelle_piege_nettoye_et_hors_ligne_de_commande(self):
        status, payload, popen = self._launch('x & calc.exe | "y" %PATH%')
        self.assertEqual(status, 200, payload)
        args, kwargs = popen.call_args
        for ch in '&|<>^%':
            self.assertNotIn(ch, kwargs["env"][TERMINAL_TITLE_VAR])
        self.assertNotIn("calc", args[0])

    def test_libelle_absent_repli_sur_l_id(self):
        status, _payload, popen = self._launch(None)
        self.assertEqual(status, 200)
        self.assertEqual(popen.call_args.kwargs["env"][TERMINAL_TITLE_VAR], "w1")

    def test_reprise_passe_aussi_par_le_script_de_titre(self):
        proc = mock.Mock(pid=4243)
        with mock.patch.object(api_workspaces, "IS_WINDOWS", True), \
             mock.patch.object(api_workspaces.subprocess, "Popen", return_value=proc) as popen, \
             mock.patch("dashcore.active_sessions.register"):
            status, payload = api_workspaces.launch_resume("w1")
        self.assertEqual(status, 200, payload)
        args, kwargs = popen.call_args
        self.assertEqual(args[0], f'cmd /k ""{self.wrapper}" claude -c"')
        self.assertTrue(kwargs["env"][TERMINAL_TITLE_VAR])
        self.assertEqual(kwargs["env"][TERMINAL_TITLE_ENV], "1")
        self.assertEqual(kwargs["cwd"], str(self.ws_dir))


@unittest.skipUnless(sys.platform == "win32" and shutil.which("powershell"),
                     "titre de console réel : Windows + PowerShell")
class RealConsoleTitleTests(unittest.TestCase):
    """Lit le titre d'une VRAIE console depuis l'intérieur (console cachée).

    Régression : avec `cmd /k "title X && call bat"`, `cmd` réécrivait le titre en
    « X  - call "…\\bat" », visible dans l'onglet.
    """

    def setUp(self):
        reset_sandbox()
        # Chemin avec espaces ET parenthèses : cas réel des dossiers utilisateur.
        self.dir = SANDBOX / "dossier avec espaces (test)"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.out = self.dir / "titre.txt"
        read = f'powershell -NoProfile -Command "[Console]::Title" > "{self.out}"'
        # Lanceur existant : AUCUNE commande `title` (comme les .bat déjà générés).
        self.bat = self.dir / "launch-x.bat"
        self.bat.write_text(f"@echo off\r\necho.\r\n{read}\r\nexit\r\n", encoding="utf-8")
        self.fake_claude = self.dir / "fakeclaude.cmd"
        self.fake_claude.write_text(f"@echo off\r\n{read}\r\nexit\r\n", encoding="utf-8")

    def _title_seen(self, inner: str, title: str) -> str:
        if self.out.exists():
            self.out.unlink()
        wrapper = workspace_io.ensure_title_wrapper()
        self.assertIsNotNone(wrapper)
        p = subprocess.Popen(
            workspace_io.terminal_command(inner, wrapper), env=workspace_io.terminal_env(title),
            cwd=str(self.dir), creationflags=subprocess.CREATE_NO_WINDOW, shell=False)
        try:
            deadline = time.time() + 40
            while time.time() < deadline:
                if p.poll() is not None and self.out.exists() and self.out.stat().st_size:
                    break
                time.sleep(0.25)
        finally:
            if p.poll() is None:
                p.kill()
        self.assertTrue(self.out.exists(), "le script n'a pas écrit le titre lu")
        return self.out.read_text(encoding="cp850", errors="replace").strip()

    def test_lancement_titre_exact_sans_suffixe_de_commande(self):
        seen = self._title_seen(f'call "{self.bat}"', "Home Assistant")
        self.assertEqual(seen, "Home Assistant")
        self.assertNotIn("call", seen)

    def test_reprise_titre_exact(self):
        self.assertEqual(self._title_seen(f'call "{self.fake_claude}"', "Mon Projet"), "Mon Projet")

    def test_libelle_avec_parentheses(self):
        self.assertEqual(self._title_seen(f'call "{self.bat}"', "Projet (v2) test"),
                         "Projet (v2) test")

    def test_libelle_piege_n_execute_rien(self):
        title = workspace_io.terminal_title('piege & echo INJECTE | "x" %PATH%', "x")
        seen = self._title_seen(f'call "{self.bat}"', title)
        self.assertEqual(seen, title)


if __name__ == "__main__":
    unittest.main()
