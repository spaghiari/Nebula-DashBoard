"""Chiffrement des archives de migration `.nebmig` (schéma maison, stdlib seule).

ATTENTION : la bibliothèque standard n'a pas d'AES. Ce schéma est une
construction maison, simple et classique (dérivation de clé + flux de clé +
chiffrer-puis-authentifier), à FAIRE VALIDER avant de lui confier autre chose
que des données déjà protégées par ailleurs. Modèle de menace et limites :
`.claude/memory/subsystems/migration.md`.

Format (tout en grand-boutiste) :

    en-tête (80 octets)
        0   8   magic            b"NEBULAMG"
        8   2   version du format (1)
        10  1   id KDF           1 = PBKDF2-HMAC-SHA256
        11  1   id chiffrement   1 = flux SHAKE-256 (XOR) + HMAC-SHA256
        12  4   itérations PBKDF2
        16  32  sel aléatoire
        48  24  nonce aléatoire
        72  4   taille de bloc du flux de clé
        76  4   réservé (zéros)
    flux chiffré (taille quelconque)
    étiquette (32 octets) = HMAC-SHA256(mac_key, en-tête || flux chiffré)

Clés : `master = PBKDF2-HMAC-SHA256(NFC(phrase), sel, itérations, 32 octets)`,
puis `enc_key = HMAC(master, "nebula-migration/enc/v1")` et
`mac_key = HMAC(master, "nebula-migration/mac/v1")`.

Flux de clé : pour le bloc `i` (taille `C`) du texte clair,
`SHAKE-256("NEBMIG-KS1" || enc_key || nonce || i sur 8 octets)` tiré sur la
longueur du bloc, XOR avec le clair. Un couple (clé, nonce) n'est jamais
réutilisé : sel et nonce sont tirés à chaque archive.

Authentification : encrypt-then-MAC. L'étiquette est vérifiée en entier
(première passe, `compare_digest`) AVANT de déchiffrer le moindre octet, puis
recalculée pendant le déchiffrement (seconde passe) et revérifiée en fin de
flux : un fichier modifié entre les deux passes est refusé avant toute
application. Une mauvaise phrase de passe et une archive altérée sont
indiscernables par construction (même message).
"""
from __future__ import annotations

import hashlib
import hmac
import io
import os
import struct
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from dashcore.config import (
    MIGRATION_CHUNK_SIZE, MIGRATION_FORMAT_VERSION, MIGRATION_KDF_ITERATIONS,
    MIGRATION_KDF_MAX_ITERATIONS, MIGRATION_KDF_MIN_ITERATIONS, MIGRATION_MAGIC,
)

_HEADER = struct.Struct(">8sHBBI32s24sI4s")
HEADER_LEN = _HEADER.size            # 80
TAG_LEN = 32
KDF_PBKDF2_SHA256 = 1
CIPHER_SHAKE256_HMAC = 1
_CHUNK_MIN, _CHUNK_MAX = 4096, 64 << 20
_KS_LABEL = b"NEBMIG-KS1"
_READ_BLOCK = 1 << 20

Progress = Callable[[int, int], None]


class MigrationError(Exception):
    """Erreur de migration à message affichable (jamais de secret dedans)."""
    code = "migration"


class MigrationFormatError(MigrationError):
    code = "bad_format"


class MigrationVersionError(MigrationError):
    code = "unsupported_version"


class MigrationAuthError(MigrationError):
    code = "bad_passphrase_or_corrupt"

    def __init__(self, msg: str | None = None):
        super().__init__(msg or "Phrase de passe incorrecte, ou archive altérée ou tronquée.")


class MigrationCancelled(MigrationError):
    code = "cancelled"

    def __init__(self):
        super().__init__("Opération annulée.")


@dataclass(frozen=True)
class Header:
    version: int
    kdf_id: int
    cipher_id: int
    iterations: int
    salt: bytes
    nonce: bytes
    chunk_size: int
    raw: bytes


@dataclass(frozen=True)
class Keys:
    enc: bytes
    mac: bytes


def parse_header(raw: bytes) -> Header:
    """Valide et décode l'en-tête (sans phrase de passe)."""
    if len(raw) != HEADER_LEN:
        raise MigrationFormatError("Archive tronquée : en-tête incomplet.")
    (magic, version, kdf_id, cipher_id, iterations, salt, nonce,
     chunk, reserved) = _HEADER.unpack(raw)
    if magic != MIGRATION_MAGIC:
        raise MigrationFormatError("Ce fichier n'est pas une archive de migration Nebula.")
    if version > MIGRATION_FORMAT_VERSION:
        raise MigrationVersionError(
            f"Archive de format {version}, plus récente que cette version de Nebula "
            f"(format {MIGRATION_FORMAT_VERSION}) : mets Nebula à jour avant d'importer.")
    if version < 1:
        raise MigrationFormatError("Version de format invalide.")
    if kdf_id != KDF_PBKDF2_SHA256 or cipher_id != CIPHER_SHAKE256_HMAC:
        raise MigrationFormatError("Algorithme de chiffrement inconnu.")
    if not (MIGRATION_KDF_MIN_ITERATIONS <= iterations <= MIGRATION_KDF_MAX_ITERATIONS):
        raise MigrationFormatError("Paramètres de dérivation de clé hors limites.")
    if not (_CHUNK_MIN <= chunk <= _CHUNK_MAX):
        raise MigrationFormatError("Taille de bloc invalide.")
    if reserved != b"\0\0\0\0":
        raise MigrationFormatError("Champ réservé non nul.")
    return Header(version, kdf_id, cipher_id, iterations, salt, nonce, chunk, bytes(raw))


def derive_keys(passphrase: str, header: Header) -> Keys:
    secret = unicodedata.normalize("NFC", passphrase or "").encode("utf-8")
    if not secret:
        raise MigrationAuthError("Phrase de passe vide.")
    master = hashlib.pbkdf2_hmac("sha256", secret, header.salt, header.iterations, 32)
    return Keys(
        enc=hmac.new(master, b"nebula-migration/enc/v1", "sha256").digest(),
        mac=hmac.new(master, b"nebula-migration/mac/v1", "sha256").digest(),
    )


def _keystream(keys: Keys, nonce: bytes, index: int, length: int) -> bytes:
    return hashlib.shake_256(
        _KS_LABEL + keys.enc + nonce + index.to_bytes(8, "big")).digest(length)


def _xor(a: bytes, b: bytes) -> bytes:
    n = len(a)
    if n == 0:
        return b""
    return (int.from_bytes(a, "little") ^ int.from_bytes(b, "little")).to_bytes(n, "little")


class EncryptingWriter:
    """Fichier en écriture seule : tout ce qui est écrit sort chiffré dans `raw`.

    `close()` écrit l'étiquette finale et synchronise le fichier ; il ferme
    aussi `raw`. Les données sont chiffrées par blocs de `chunk_size`.
    """

    def __init__(self, raw, passphrase: str, iterations: int = MIGRATION_KDF_ITERATIONS):
        salt, nonce = os.urandom(32), os.urandom(24)
        header_raw = _HEADER.pack(
            MIGRATION_MAGIC, MIGRATION_FORMAT_VERSION, KDF_PBKDF2_SHA256,
            CIPHER_SHAKE256_HMAC, iterations, salt, nonce, MIGRATION_CHUNK_SIZE, b"\0\0\0\0")
        self.header = parse_header(header_raw)
        self._keys = derive_keys(passphrase, self.header)
        self._raw = raw
        self._mac = hmac.new(self._keys.mac, digestmod="sha256")
        self._mac.update(header_raw)
        raw.write(header_raw)
        self._buf = bytearray()
        self._index = 0
        self._closed = False
        self.bytes_in = 0

    def writable(self) -> bool:
        return True

    def _emit(self, plain: bytes) -> None:
        ct = _xor(plain, _keystream(self._keys, self.header.nonce, self._index, len(plain)))
        self._index += 1
        self._mac.update(ct)
        self._raw.write(ct)

    def write(self, data) -> int:
        if self._closed:
            raise ValueError("écriture sur une archive fermée")
        n = len(data)
        self.bytes_in += n
        self._buf += data
        c = self.header.chunk_size
        while len(self._buf) >= c:
            chunk = bytes(self._buf[:c])
            del self._buf[:c]
            self._emit(chunk)
        return n

    def flush(self) -> None:
        pass

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._buf:
            self._emit(bytes(self._buf))
            self._buf.clear()
        self._raw.write(self._mac.digest())
        self._raw.flush()
        try:
            os.fsync(self._raw.fileno())
        except (OSError, AttributeError, ValueError):
            pass
        self._raw.close()


def read_header_and_tag(path: Path) -> tuple[Header, bytes, int]:
    """(en-tête validé, étiquette finale, taille du fichier), sans phrase de passe."""
    size = os.path.getsize(path)
    if size < HEADER_LEN + TAG_LEN:
        raise MigrationFormatError("Archive tronquée ou vide.")
    with open(path, "rb") as f:
        header = parse_header(f.read(HEADER_LEN))
        f.seek(size - TAG_LEN)
        tag = f.read(TAG_LEN)
    return header, tag, size


def _check_cancel(cancel) -> None:
    if cancel is not None and cancel():
        raise MigrationCancelled()


def verify_mac(f, header: Header, keys: Keys, size: int,
               progress: Progress | None = None, cancel=None) -> bytes:
    """Première passe : HMAC de tout le fichier hors étiquette, comparé à
    l'étiquette en temps constant. Retourne l'étiquette. Aucun déchiffrement."""
    mac = hmac.new(keys.mac, digestmod="sha256")
    mac.update(header.raw)
    total = size - HEADER_LEN - TAG_LEN
    f.seek(HEADER_LEN)
    left = total
    done = 0
    while left > 0:
        _check_cancel(cancel)
        block = f.read(min(_READ_BLOCK, left))
        if not block:
            raise MigrationAuthError()
        mac.update(block)
        left -= len(block)
        done += len(block)
        if progress:
            progress(done, total)
    tag = f.read(TAG_LEN)
    if not hmac.compare_digest(mac.digest(), tag):
        raise MigrationAuthError()
    return tag


class _DecryptRaw(io.RawIOBase):
    """Lecture déchiffrée, à n'utiliser qu'après `verify_mac`. Recalcule le
    HMAC au fil de la lecture et le compare à l'étiquette au dernier octet."""

    def __init__(self, f, header: Header, keys: Keys, total: int, tag: bytes, cancel=None):
        self._f = f
        self._h = header
        self._keys = keys
        self._left = total
        self._tag = tag
        self._cancel = cancel
        self._mac = hmac.new(keys.mac, digestmod="sha256")
        self._mac.update(header.raw)
        self._index = 0
        self._plain = b""
        self._pos = 0
        self._eof = False
        f.seek(HEADER_LEN)

    def readable(self) -> bool:
        return True

    def _fill(self) -> None:
        _check_cancel(self._cancel)
        if self._left <= 0:
            if not self._eof:
                self._eof = True
                if not hmac.compare_digest(self._mac.digest(), self._tag):
                    raise MigrationAuthError(
                        "L'archive a été modifiée pendant la lecture : rien n'a été appliqué.")
            self._plain, self._pos = b"", 0
            return
        ct = self._f.read(min(self._h.chunk_size, self._left))
        if not ct:
            raise MigrationAuthError()
        self._left -= len(ct)
        self._mac.update(ct)
        self._plain = _xor(ct, _keystream(self._keys, self._h.nonce, self._index, len(ct)))
        self._index += 1
        self._pos = 0

    def readinto(self, b) -> int:
        if self._pos >= len(self._plain):
            if self._eof:
                return 0
            self._fill()
            if not self._plain:
                return 0
        n = min(len(b), len(self._plain) - self._pos)
        b[:n] = self._plain[self._pos:self._pos + n]
        self._pos += n
        return n

    def finish(self) -> None:
        """Lit jusqu'au bout pour déclencher la vérification finale de l'étiquette."""
        while not self._eof:
            self._fill()
            self._pos = len(self._plain)


class OpenedArchive:
    """Archive ouverte et vérifiée : `.reader` donne le texte clair (flux)."""

    def __init__(self, f, header: Header, raw: _DecryptRaw, tag: bytes):
        self._f = f
        self._raw = raw
        self.header = header
        self.tag = tag
        self.reader = io.BufferedReader(raw, buffer_size=_READ_BLOCK)

    def finish(self) -> None:
        # Vide le tampon du lecteur tamponné puis force la vérification finale.
        while self.reader.read(_READ_BLOCK):
            pass
        self._raw.finish()

    def close(self) -> None:
        try:
            self.reader.close()
        finally:
            self._f.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def open_archive(path: Path, passphrase: str, progress: Progress | None = None,
                 cancel=None) -> OpenedArchive:
    """Ouvre `path`, dérive la clé, VÉRIFIE l'étiquette (première passe) puis
    prépare le déchiffrement en flux. Lève `MigrationAuthError` si la phrase de
    passe est fausse ou l'archive altérée : aucun octet n'est alors déchiffré."""
    header, _tag, size = read_header_and_tag(path)
    keys = derive_keys(passphrase, header)
    f = open(path, "rb")
    try:
        tag = verify_mac(f, header, keys, size, progress, cancel)
        raw = _DecryptRaw(f, header, keys, size - HEADER_LEN - TAG_LEN, tag, cancel)
        return OpenedArchive(f, header, raw, tag)
    except BaseException:
        f.close()
        raise
