"""Compression gzip parallèle pour l'export de migration.

Un flux gzip classique se compresse sur un seul cœur, et c'est le goulot de
l'export (quelques dizaines de Mo/s) alors que disque, SHAKE256 et HMAC vont
bien plus vite. Ici le flux tar est découpé en blocs de `MIGRATION_GZIP_BLOCK`
octets ; chaque bloc devient un **membre gzip indépendant**, compressé dans un
pool de threads (zlib relâche le GIL).

Trois étages se recouvrent :
  1. le thread appelant lit les fichiers et fabrique le tar (`write`) ;
  2. le pool compresse les blocs ;
  3. un thread d'écriture récupère les membres **dans l'ordre** et les passe à
     `out` (chiffrement + disque). Sans lui, le chiffrement s'exécuterait dans
     le thread appelant et le pool resterait à l'arrêt pendant ce temps.

Format inchangé : des membres gzip concaténés forment un fichier gzip valide,
que `gzip.GzipFile` (lecture) enchaîne tout seul. L'import et la vérification
n'ont donc rien à savoir de ce découpage, et une archive écrite ainsi se relit
comme une archive à un seul membre.

Mémoire bornée : au plus `2 x workers` blocs sont en vol (entrée + sortie).
Une erreur d'écriture (disque plein...) est remontée à l'appelant au prochain
`write` ou à `close`.
"""
from __future__ import annotations

import gzip
import os
import queue
import threading
from concurrent.futures import Future, ThreadPoolExecutor

from dashcore.config import (
    MIGRATION_COMPRESS_LEVEL, MIGRATION_GZIP_BLOCK, MIGRATION_GZIP_MAX_WORKERS,
)

_STOP = object()


def default_workers() -> int:
    """Threads de compression : les cœurs moins deux (laisse de l'air au
    reste de la machine), au moins 2, plafonné pour borner la mémoire."""
    return max(2, min(MIGRATION_GZIP_MAX_WORKERS, (os.cpu_count() or 4) - 2))


class ParallelGzipWriter:
    """Fichier en écriture seule : ce qui est écrit sort compressé dans `out`.

    `close()` termine le dernier membre et vide la file d'attente, mais ne
    ferme PAS `out` (même contrat que `gzip.GzipFile(fileobj=...)`).
    """

    def __init__(self, out, level: int = MIGRATION_COMPRESS_LEVEL,
                 block_size: int = MIGRATION_GZIP_BLOCK, workers: int | None = None):
        self._out = out
        self._level = level
        self._block = max(1, block_size)
        n = workers if workers and workers > 0 else default_workers()
        self._pool = ThreadPoolExecutor(max_workers=n, thread_name_prefix="nebmig-gz")
        self._queue: queue.Queue = queue.Queue(maxsize=2 * n)
        # Morceaux reçus, joints UNE fois par bloc : mesuré ~40 % plus rapide
        # qu'un bytearray tranché (slice + bytes() + del = trois copies de
        # 4 Mio par bloc, et autant d'allocations à page-faulter).
        self._chunks: list[bytes] = []
        self._pending_bytes = 0
        self._wrote_member = False
        self._closed = False
        self._error: BaseException | None = None
        self._abort = threading.Event()
        self._writer = threading.Thread(
            target=self._drain, name="nebmig-gz-writer", daemon=True)
        self._writer.start()

    # -- thread d'écriture ------------------------------------------------

    def _drain(self) -> None:
        """Écrit les membres dans l'ordre de soumission. Après une erreur,
        continue de vider la file (sans écrire) pour ne jamais bloquer
        l'appelant sur une file pleine."""
        while True:
            fut = self._queue.get()
            if fut is _STOP:
                return
            if self._error is not None or self._abort.is_set():
                fut.cancel()
                continue
            try:
                self._out.write(fut.result())
            except BaseException as e:  # noqa: BLE001 : remonté à l'appelant
                self._error = e

    def _raise_if_failed(self) -> None:
        if self._error is not None:
            raise self._error

    def _enqueue(self, fut: Future) -> None:
        # `put` bloque quand 2 x workers membres attendent : contre-pression.
        # Timeout court pour réagir à une erreur du thread d'écriture.
        while True:
            self._raise_if_failed()
            try:
                self._queue.put(fut, timeout=0.2)
                return
            except queue.Full:
                continue

    # -- API fichier -------------------------------------------------------

    def writable(self) -> bool:
        return True

    def _submit(self, block: bytes) -> None:
        self._enqueue(self._pool.submit(gzip.compress, block, self._level, mtime=0))
        self._wrote_member = True

    def write(self, data) -> int:
        if self._closed:
            raise ValueError("écriture sur un flux fermé")
        self._raise_if_failed()
        n = len(data)
        if n:
            # `bytes(bytes)` renvoie le même objet : aucune copie pour tarfile.
            self._chunks.append(bytes(data))
            self._pending_bytes += n
            if self._pending_bytes >= self._block:
                self._flush_block()
        return n

    def _flush_block(self) -> None:
        block = b"".join(self._chunks)
        self._chunks = []
        self._pending_bytes = 0
        self._submit(block)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            if self._chunks or not self._wrote_member:
                # Dernier bloc partiel ; un flux vide reste un gzip valide.
                self._flush_block()
        except BaseException:
            self._abort.set()
            raise
        finally:
            self._queue.put(_STOP)
            self._writer.join()
            # Sur erreur : on abandonne ce qui n'a pas démarré.
            self._pool.shutdown(wait=True, cancel_futures=True)
        self._raise_if_failed()
