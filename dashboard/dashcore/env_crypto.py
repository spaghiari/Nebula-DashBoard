"""Chiffrement DPAPI (Windows) pour .env.local + ACL stricte via icacls.

DPAPI CurrentUser : le blob ne peut être déchiffré que par le même compte
utilisateur Windows sur la même machine. Pas de mot de passe à mémoriser.

Limites :
- Ne protège PAS contre un malware qui tourne sous le compte de l'utilisateur
  (il peut appeler CryptUnprotectData lui-même).
- Profil corrompu / reinstall Windows = secrets perdus → toujours exporter
  en clair pour backup hors-poste.
- Windows uniquement. Sur autre OS, les fonctions lèvent NotImplementedError.

Format du fichier .env.local.enc :
  HEADER (8 octets, ASCII)  | BLOB DPAPI
  "NEBULA1\\n"               | bytes retournés par CryptProtectData

Le header permet de distinguer un fichier chiffré d'un fichier corrompu et
de prévoir une migration de format future sans casser la compat.
"""
from __future__ import annotations

import ctypes
import getpass
import os
import subprocess
import sys
import tempfile
from ctypes import wintypes
from pathlib import Path

from dashcore.config import log

# Header de version du blob chiffré. 8 octets fixes pour faciliter le sniff.
ENC_HEADER = b"NEBULA1\n"

IS_WINDOWS = sys.platform == "win32"


class CryptoError(Exception):
    """Erreur côté chiffrement (DPAPI échec, plateforme non supportée, etc.)."""


# ─────────────────────────────────────────────────────────────────────────────
# DPAPI via ctypes (crypt32.dll)
# ─────────────────────────────────────────────────────────────────────────────

class _DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _load_crypt32():
    if not IS_WINDOWS:
        raise CryptoError("DPAPI n'est disponible que sur Windows")
    try:
        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32
    except (AttributeError, OSError) as e:
        raise CryptoError(f"impossible de charger crypt32/kernel32 : {e}") from e

    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_DATA_BLOB),  # pDataIn
        wintypes.LPCWSTR,            # szDataDescr (peut être NULL)
        ctypes.POINTER(_DATA_BLOB),  # pOptionalEntropy (peut être NULL)
        ctypes.c_void_p,             # pvReserved
        ctypes.c_void_p,             # pPromptStruct
        wintypes.DWORD,              # dwFlags
        ctypes.POINTER(_DATA_BLOB),  # pDataOut
    ]
    crypt32.CryptProtectData.restype = wintypes.BOOL

    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DATA_BLOB),
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(_DATA_BLOB),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DATA_BLOB),
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL

    kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
    kernel32.LocalFree.restype = wintypes.HLOCAL

    return crypt32, kernel32


def _blob_in(data: bytes) -> _DATA_BLOB:
    """Construit un DATA_BLOB en entrée à partir de bytes Python.

    Important : le buffer est ré-attaché à la struct via from_buffer_copy pour
    qu'il reste vivant tant que la struct est utilisée. On garde une référence
    sur la struct côté appelant ; le buffer reste manipulé par CryptoAPI en
    lecture seule pendant l'appel.
    """
    raw = (ctypes.c_ubyte * len(data)).from_buffer_copy(data) if data else (ctypes.c_ubyte * 0)()
    blob = _DATA_BLOB()
    blob.cbData = len(data)
    blob.pbData = ctypes.cast(raw, ctypes.POINTER(ctypes.c_ubyte))
    # Garder une réf au buffer pour qu'il ne soit pas GC pendant l'appel
    blob._raw_keepalive = raw  # type: ignore[attr-defined]
    return blob


def _blob_out_to_bytes(blob: _DATA_BLOB, kernel32) -> bytes:
    """Copie le contenu d'un DATA_BLOB sortant vers bytes, puis LocalFree."""
    try:
        if not blob.pbData or blob.cbData == 0:
            return b""
        out = ctypes.string_at(blob.pbData, blob.cbData)
        return out
    finally:
        if blob.pbData:
            kernel32.LocalFree(blob.pbData)


def dpapi_encrypt(plaintext: bytes) -> bytes:
    """Chiffre `plaintext` via DPAPI CurrentUser. Retourne le blob brut.

    Lève CryptoError sur échec (plateforme, API Windows).
    """
    if not isinstance(plaintext, (bytes, bytearray)):
        raise TypeError("plaintext doit être bytes")
    crypt32, kernel32 = _load_crypt32()

    blob_in = _blob_in(bytes(plaintext))
    blob_out = _DATA_BLOB()

    ok = crypt32.CryptProtectData(
        ctypes.byref(blob_in),
        None,           # szDataDescr — pas de description (apparaît dans certains outils)
        None,           # pas d'entropy secondaire (clé = compte utilisateur)
        None,
        None,
        0,              # flags : CurrentUser scope par défaut
        ctypes.byref(blob_out),
    )
    if not ok:
        err = ctypes.GetLastError()
        raise CryptoError(f"CryptProtectData a échoué (code {err})")

    return _blob_out_to_bytes(blob_out, kernel32)


def dpapi_decrypt(blob_bytes: bytes) -> bytes:
    """Déchiffre un blob DPAPI. Lève CryptoError si le compte/machine ne match pas."""
    if not isinstance(blob_bytes, (bytes, bytearray)):
        raise TypeError("blob_bytes doit être bytes")
    if not blob_bytes:
        raise CryptoError("blob vide")
    crypt32, kernel32 = _load_crypt32()

    blob_in = _blob_in(bytes(blob_bytes))
    blob_out = _DATA_BLOB()

    ok = crypt32.CryptUnprotectData(
        ctypes.byref(blob_in),
        None,           # pas besoin du szDataDescr en sortie
        None,
        None,
        None,
        0,
        ctypes.byref(blob_out),
    )
    if not ok:
        err = ctypes.GetLastError()
        raise CryptoError(f"CryptUnprotectData a échoué (code {err})")

    return _blob_out_to_bytes(blob_out, kernel32)


def dpapi_self_test() -> bool:
    """Round-trip de validation : chiffre puis déchiffre un canary. Lève si KO."""
    canary = b"nebula-dpapi-canary-" + os.urandom(16)
    blob = dpapi_encrypt(canary)
    out = dpapi_decrypt(blob)
    if out != canary:
        raise CryptoError("self-test DPAPI : round-trip mismatch")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Lecture / écriture du fichier chiffré (avec header)
# ─────────────────────────────────────────────────────────────────────────────

def write_encrypted_file(path: Path, plaintext: bytes) -> None:
    """Chiffre `plaintext` et écrit `path` de manière atomique, puis ACL stricte.

    Atomique : écrit dans un .tmp dans le même dossier puis os.replace().
    """
    blob = dpapi_encrypt(plaintext)
    data = ENC_HEADER + blob
    path.parent.mkdir(parents=True, exist_ok=True)
    # NamedTemporaryFile avec delete=False puis rename : garantit l'atomicité
    fd, tmp_name = tempfile.mkstemp(
        prefix=".env.local.enc.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass  # fsync peut échouer sur certains FS Windows, non bloquant
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    try:
        restrict_acl_user_only(path)
    except Exception as e:
        log.warning("ACL stricte sur %s impossible : %s", path, e)


def read_encrypted_file(path: Path) -> bytes:
    """Lit `path`, valide le header, déchiffre. Retourne le plaintext brut."""
    if not path.exists():
        raise CryptoError(f"fichier chiffré introuvable : {path}")
    raw = path.read_bytes()
    if not raw.startswith(ENC_HEADER):
        raise CryptoError("header de fichier chiffré invalide ou corrompu")
    return dpapi_decrypt(raw[len(ENC_HEADER):])


# ─────────────────────────────────────────────────────────────────────────────
# ACL stricte (Windows uniquement) via icacls
# ─────────────────────────────────────────────────────────────────────────────

def restrict_acl_user_only(path: Path) -> None:
    """Réduit les ACL du fichier à l'utilisateur courant + SYSTEM uniquement.

    Utilise icacls.exe (présent sur tout Windows ≥ Vista). No-op sur autre OS.
    Lève RuntimeError si icacls échoue.
    """
    if not IS_WINDOWS:
        return
    if not path.exists():
        raise FileNotFoundError(path)

    user = getpass.getuser()
    if not user or any(c in user for c in '"\\/\r\n'):
        # Très improbable, mais on refuse tout nom suspect plutôt que de l'injecter
        raise RuntimeError(f"nom d'utilisateur inattendu : {user!r}")

    # icacls : /inheritance:r désactive l'héritage et purge les ACL existantes.
    # /grant:r remplace toute ACL existante pour le principal donné.
    # On utilise subprocess avec liste d'args (pas de shell), donc pas
    # d'injection possible même si user contenait des caractères spéciaux
    # (mais on a déjà filtré).
    cmd = [
        "icacls", str(path),
        "/inheritance:r",
        "/grant:r", f"{user}:(F)",
        "/grant:r", "SYSTEM:(F)",
    ]
    try:
        # CREATE_NO_WINDOW pour ne pas faire flasher une console
        creationflags = 0x08000000 if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10,
            creationflags=creationflags,
        )
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        raise RuntimeError(f"icacls indisponible : {e}") from e
    if r.returncode != 0:
        raise RuntimeError(f"icacls a échoué (code {r.returncode}) : {r.stderr.strip() or r.stdout.strip()}")
