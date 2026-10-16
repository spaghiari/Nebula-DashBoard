"""Sélecteur de dossier natif (`dashcore/folder_picker.py`), subprocess mocké :
commande construite, chemin choisi, annulation, délai, 501 hors plateforme
supportée, un seul dialogue à la fois. Aucun vrai dialogue n'est ouvert."""
from __future__ import annotations

import base64
import os
import subprocess
import unittest
from unittest import mock

from _support import SANDBOX, rmtree
from dashcore import folder_picker
from dashcore.config import FOLDER_PICKER_TIMEOUT
from dashcore.folder_picker import pick_folder, picker_capability


def _done(cmd, rc=0, out="", err=""):
    return subprocess.CompletedProcess(cmd, rc, stdout=out, stderr=err)


class _Base(unittest.TestCase):
    platform = "win32"
    which = {"powershell.exe": r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"}
    display = True

    def setUp(self):
        self.start = SANDBOX / "picker" / "dossier d'essai"
        self.start.mkdir(parents=True, exist_ok=True)
        patches = [
            mock.patch.object(folder_picker, "_platform", return_value=self.platform),
            mock.patch.object(folder_picker.shutil, "which", side_effect=lambda n: self.which.get(n)),
            mock.patch.object(folder_picker, "_has_display", return_value=self.display),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        rmtree(SANDBOX / "picker")

    def run_pick(self, result=None, side_effect=None, payload=None):
        with mock.patch.object(folder_picker.subprocess, "run",
                               return_value=result, side_effect=side_effect) as run:
            status, body = pick_folder(payload or {})
        return status, body, run


class WindowsPickerTests(_Base):
    def test_commande_powershell_sta_sans_shell(self):
        b64 = base64.b64encode("C:\\dev\\é projet".encode("utf-8")).decode("ascii")
        status, body, run = self.run_pick(
            _done([], out=f"\ufeffOK64:{b64}\r\n"), payload={"initial": str(self.start)})
        self.assertEqual((status, body), (200, {"ok": True, "path": "C:\\dev\\é projet"}))
        cmd = run.call_args.args[0]
        kw = run.call_args.kwargs
        self.assertIsInstance(cmd, list)
        self.assertTrue(cmd[0].endswith("powershell.exe"))
        self.assertIn("-NoProfile", cmd)
        self.assertIn("-STA", cmd)
        self.assertFalse(kw["shell"])
        self.assertEqual(kw["timeout"], FOLDER_PICKER_TIMEOUT)
        self.assertEqual(kw["encoding"], "utf-8")
        # Dossier de départ transmis par l'env, jamais dans la commande.
        self.assertEqual(kw["env"]["NEBULA_PICK_INITIAL"], str(self.start))
        self.assertFalse(any("essai" in a for a in cmd))
        script = base64.b64decode(cmd[cmd.index("-EncodedCommand") + 1]).decode("utf-16-le")
        self.assertIn("FolderBrowserDialog", script)
        self.assertIn("TopMost = $true", script)
        self.assertIn("OutputEncoding = [System.Text.Encoding]::UTF8", script)

    def test_dossier_de_depart_absent_ignore(self):
        _, _, run = self.run_pick(_done([], out="CANCEL\n"), payload={"initial": str(self.start / "nope")})
        self.assertEqual(run.call_args.kwargs["env"]["NEBULA_PICK_INITIAL"], "")

    def test_annulation(self):
        status, body, _ = self.run_pick(_done([], out="CANCEL\r\n"))
        self.assertEqual((status, body), (200, {"ok": False, "cancelled": True}))

    def test_delai_depasse_504(self):
        status, body, _ = self.run_pick(side_effect=subprocess.TimeoutExpired("ps", FOLDER_PICKER_TIMEOUT))
        self.assertEqual(status, 504)
        self.assertIn("error", body)

    def test_echec_powershell_500(self):
        status, body, _ = self.run_pick(_done([], rc=1, err="Add-Type : échec"))
        self.assertEqual(status, 500)
        self.assertIn("échec", body["error"])

    def test_un_seul_dialogue_a_la_fois(self):
        self.assertTrue(folder_picker._PICK_LOCK.acquire(blocking=False))
        try:
            status, body, run = self.run_pick(_done([], out="CANCEL"))
        finally:
            folder_picker._PICK_LOCK.release()
        self.assertEqual(status, 409)
        run.assert_not_called()

    def test_capacite(self):
        self.assertEqual(picker_capability(), (200, {"supported": True, "backend": "powershell"}))


class LinuxPickerTests(_Base):
    platform = "linux"
    which = {"zenity": "/usr/bin/zenity"}

    def test_zenity_chemin_et_annulation(self):
        status, body, run = self.run_pick(_done([], out="/home/a/projet\n"))
        self.assertEqual((status, body), (200, {"ok": True, "path": "/home/a/projet"}))
        cmd = run.call_args.args[0]
        self.assertEqual(cmd[:3], ["/usr/bin/zenity", "--file-selection", "--directory"])
        status, body, _ = self.run_pick(_done([], rc=1))
        self.assertEqual(body, {"ok": False, "cancelled": True})


class LinuxSansSelecteurTests(_Base):
    platform = "linux"
    which = {}

    def test_501(self):
        status, body, run = self.run_pick(_done([]))
        self.assertEqual(status, 501)
        self.assertIn("colle le chemin", body["error"])
        run.assert_not_called()
        self.assertEqual(picker_capability(), (200, {"supported": False, "backend": None}))


class LinuxSansEcranTests(_Base):
    platform = "linux"
    which = {"zenity": "/usr/bin/zenity"}
    display = False

    def test_501_sans_session_graphique(self):
        self.assertEqual(self.run_pick(_done([]))[0], 501)


class MacPickerTests(_Base):
    platform = "darwin"
    which = {"osascript": "/usr/bin/osascript"}

    def test_osascript_argv_et_annulation(self):
        status, body, run = self.run_pick(_done([], out="/Users/a/projet/\n"),
                                          payload={"initial": str(self.start)})
        self.assertEqual(body, {"ok": True, "path": "/Users/a/projet"})
        cmd = run.call_args.args[0]
        self.assertEqual(cmd[-1], str(self.start))           # en argv, pas dans le script
        self.assertFalse(any("essai" in a for a in cmd[:-1]))
        status, body, _ = self.run_pick(_done([], rc=1, err="execution error: User canceled. (-128)"))
        self.assertEqual(body, {"ok": False, "cancelled": True})

    def test_pas_d_option_glissee_en_argv(self):
        # Titre et dossier de départ vont en argv positionnel : un « - » de tête
        # serait lu comme une option par osascript / kdialog.
        dash_dir = self.start / "-e"
        dash_dir.mkdir(exist_ok=True)
        cwd = os.getcwd()
        os.chdir(self.start)  # « -e » relatif : résolu depuis le dossier courant
        try:
            _, _, run = self.run_pick(_done([], out="/x/\n"),
                                      payload={"title": "-e do shell script", "initial": "-e"})
        finally:
            os.chdir(cwd)  # avant tearDown, qui supprime ce dossier
        cmd = run.call_args.args[0]
        script_end = max(i for i, a in enumerate(cmd) if a == "-e") + 1
        for arg in cmd[script_end + 1:]:
            self.assertFalse(arg.startswith("-"), cmd)
        self.assertEqual(cmd[script_end + 1], "e do shell script")
        self.assertEqual(cmd[-1], str(dash_dir.resolve()))
        # Contournements d'un strip en deux temps : tirets et blancs alternés.
        for title in (" - -e x", "- -e x", " -\t-x", "---", " - "):
            _, _, run = self.run_pick(_done([], out="/x/\n"), payload={"title": title})
            arg = run.call_args.args[0][-1]
            self.assertFalse(arg.lstrip().startswith("-"), (title, arg))


if __name__ == "__main__":
    unittest.main()
