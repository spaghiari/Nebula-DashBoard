"""Sélecteur de dossier natif (bouton « Parcourir… » de la modale Adopter).

Le navigateur ne peut pas renvoyer le chemin absolu d'un dossier choisi :
c'est le serveur local qui ouvre le dialogue natif du système et renvoie le
chemin sélectionné.

- Windows : PowerShell `-NoProfile -STA` + `System.Windows.Forms.FolderBrowserDialog`,
  avec une fenêtre propriétaire `TopMost` pour que le dialogue passe au
  premier plan (sinon il s'ouvre souvent derrière le navigateur).
- Linux : `zenity` puis `kdialog` (session graphique requise).
- macOS : `osascript` (`choose folder`).
- Sinon : 501 avec un message clair.

Sécurité : arguments passés en liste (`shell=False`) ; le dossier de départ
et le titre transitent par variables d'environnement (Windows) ou argv
(osascript), jamais concaténés dans un script. Un seul dialogue à la fois.
"""
from __future__ import annotations

import base64
import os
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path

from dashcore.config import FOLDER_PICKER_TIMEOUT, log

UNSUPPORTED_MSG = ("Sélecteur de dossier indisponible sur ce système (Windows, "
                   "zenity, kdialog ou macOS requis) : colle le chemin à la main.")

_PICK_LOCK = threading.Lock()
_LEADING_DASHES_RE = re.compile(r"^[\s\-]+")

_DEFAULT_TITLE = "Choisis un dossier"

# Script PowerShell figé : les seules données variables passent par l'env.
_PS_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Windows.Forms
$owner = New-Object System.Windows.Forms.Form
$owner.TopMost = $true
$owner.ShowInTaskbar = $false
$dlg = New-Object System.Windows.Forms.FolderBrowserDialog
$dlg.Description = $env:NEBULA_PICK_TITLE
$dlg.ShowNewFolderButton = $true
$init = $env:NEBULA_PICK_INITIAL
if ($init -and (Test-Path -LiteralPath $init -PathType Container)) { $dlg.SelectedPath = $init }
$res = $dlg.ShowDialog($owner)
$owner.Dispose()
if ($res -eq [System.Windows.Forms.DialogResult]::OK) {
  Write-Output ('OK64:' + [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($dlg.SelectedPath)))
} else { Write-Output 'CANCEL' }
"""


def _platform() -> str:
    """Isolé pour les tests (patché)."""
    return sys.platform


def _has_display() -> bool:
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _backend() -> tuple[str, str] | None:
    """(nom, exécutable) du sélecteur utilisable, ou None."""
    plat = _platform()
    if plat == "win32":
        exe = shutil.which("powershell.exe") or shutil.which("powershell")
        if not exe:
            root = os.environ.get("SystemRoot") or r"C:\Windows"
            cand = Path(root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
            exe = str(cand) if cand.exists() else None
        return ("powershell", exe) if exe else None
    if plat == "darwin":
        exe = shutil.which("osascript")
        return ("osascript", exe) if exe else None
    if not _has_display():
        return None
    for name in ("zenity", "kdialog"):
        exe = shutil.which(name)
        if exe:
            return (name, exe)
    return None


def picker_capability() -> tuple[int, dict]:
    """GET : le bouton « Parcourir… » est-il utilisable sur ce poste ?"""
    b = _backend()
    return 200, {"supported": b is not None, "backend": b[0] if b else None}


def _build_command(name: str, exe: str, initial: str, title: str) -> tuple[list[str], dict | None]:
    """Commande (liste d'args) et environnement éventuel du sélecteur."""
    if name == "powershell":
        encoded = base64.b64encode(_PS_SCRIPT.encode("utf-16-le")).decode("ascii")
        env = dict(os.environ)
        env["NEBULA_PICK_INITIAL"] = initial
        env["NEBULA_PICK_TITLE"] = title
        return [exe, "-NoProfile", "-STA", "-NonInteractive", "-EncodedCommand", encoded], env
    if name == "zenity":
        cmd = [exe, "--file-selection", "--directory", f"--title={title}"]
        if initial:
            cmd.append("--filename=" + initial.rstrip("/") + "/")
        return cmd, None
    if name == "kdialog":
        return [exe, "--title", title, "--getexistingdirectory", initial or str(Path.home())], None
    # osascript : données en argv, jamais dans le texte du script.
    lines = ["on run argv"]
    if initial:
        lines.append("set p to choose folder with prompt (item 1 of argv) "
                     "default location (POSIX file (item 2 of argv))")
    else:
        lines.append("set p to choose folder with prompt (item 1 of argv)")
    lines += ["return POSIX path of p", "end run"]
    cmd = [exe]
    for line in lines:
        cmd += ["-e", line]
    cmd.append(title)
    if initial:
        cmd.append(initial)
    return cmd, None


def _parse_output(name: str, returncode: int, stdout: str, stderr: str) -> tuple[int, dict]:
    out = (stdout or "").replace("\ufeff", "").strip()
    if name == "powershell":
        last = out.splitlines()[-1].strip() if out else ""
        # Chemin renvoyé en base64 de l'UTF-8 : sortie 100 % ASCII, donc
        # insensible à la page de code de la console (accents préservés même
        # quand [Console]::OutputEncoding n'est pas pris en compte en sortie
        # redirigée, constaté sous Windows PowerShell 5.1).
        if returncode == 0 and last.startswith("OK64:"):
            try:
                path = base64.b64decode(last[5:].strip(), validate=True).decode("utf-8").strip()
            except (ValueError, UnicodeDecodeError):
                path = ""
            if path:
                return 200, {"ok": True, "path": path}
        if returncode == 0 and last == "CANCEL":
            return 200, {"ok": False, "cancelled": True}
    else:
        if returncode == 0 and out:
            path = out.splitlines()[-1].strip()
            if name == "osascript" and len(path) > 1:
                path = path.rstrip("/")
            return 200, {"ok": True, "path": path}
        # zenity / kdialog : 1 = annulé ; osascript : -128 « User canceled ».
        if returncode == 1 and (name != "osascript" or "-128" in (stderr or "")):
            return 200, {"ok": False, "cancelled": True}
    detail = ((stderr or "").strip() or out)[-300:]
    log.warning("sélecteur de dossier (%s) : code %s, %s", name, returncode, detail)
    return 500, {"error": f"Le sélecteur de dossier a échoué (code {returncode})"
                          + (f" : {detail}" if detail else "")}


def pick_folder(payload: dict) -> tuple[int, dict]:
    """POST : ouvre le dialogue natif, renvoie {"ok": true, "path"} ou
    {"ok": false, "cancelled": true}. 501 si aucun sélecteur, 409 si un
    dialogue est déjà ouvert, 504 au-delà de FOLDER_PICKER_TIMEOUT."""
    b = _backend()
    if b is None:
        return 501, {"ok": False, "error": UNSUPPORTED_MSG}
    name, exe = b
    # Valeurs du client passées en argv positionnel à kdialog / osascript :
    # jamais de tiret en tête (sinon lues comme options). Le dossier de départ
    # est résolu en chemin absolu (ne commence donc jamais par « - »), le
    # titre perd ses tirets de tête.
    initial = str(payload.get("initial") or "").strip()
    try:
        initial = str(Path(initial).resolve()) if initial and Path(initial).is_dir() else ""
    except (OSError, ValueError):
        initial = ""
    # Tirets ET blancs de tête retirés d'un seul tenant (« - -e » ne doit
    # pas redevenir « -e » après un strip en deux temps).
    title = _LEADING_DASHES_RE.sub("", str(payload.get("title") or "")[:120]).strip() or _DEFAULT_TITLE
    if not _PICK_LOCK.acquire(blocking=False):
        return 409, {"error": "Un sélecteur de dossier est déjà ouvert"}
    try:
        cmd, env = _build_command(name, exe, initial, title)
        kwargs: dict = {}
        if name == "powershell" and hasattr(subprocess, "CREATE_NO_WINDOW"):
            # Pas de console qui clignote : le dialogue WinForms reste visible.
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        try:
            r = subprocess.run(
                cmd, shell=False, env=env, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=FOLDER_PICKER_TIMEOUT,
                stdin=subprocess.DEVNULL, **kwargs,
            )
        except subprocess.TimeoutExpired:
            return 504, {"error": f"Aucun dossier choisi après {FOLDER_PICKER_TIMEOUT} s : "
                                  "sélecteur abandonné"}
        except OSError as e:
            return 500, {"error": f"Impossible d'ouvrir le sélecteur de dossier : {e}"}
        return _parse_output(name, r.returncode, r.stdout, r.stderr)
    finally:
        _PICK_LOCK.release()
