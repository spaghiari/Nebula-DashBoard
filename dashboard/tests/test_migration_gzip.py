"""Compression gzip parallèle de l'export (`dashcore/migration_gzip.py`).

Couvre : relecture par `gzip.GzipFile` (format inchangé pour l'import), flux
de plusieurs membres, ordre conservé, flux vide, fermeture idempotente, `out`
laissé ouvert, écriture après fermeture refusée, erreur d'écriture propagée
sans laisser de threads, et aller-retour tar complet.
"""
from __future__ import annotations

import gzip
import io
import os
import tarfile
import threading
import unittest

from dashcore.migration_gzip import ParallelGzipWriter, default_workers

BLOCK = 4096            # petit bloc : plusieurs membres avec peu de données


def _compress(data: bytes, **kw) -> bytes:
    out = io.BytesIO()
    w = ParallelGzipWriter(out, block_size=BLOCK, workers=3, **kw)
    # Écritures de tailles variées, comme le fait tarfile.
    i = 0
    for step in (1, 17, 500, 4096, 10000):
        while i < len(data):
            w.write(data[i:i + step])
            i += step
            if i % 7 == 0:
                break
        if i >= len(data):
            break
    w.write(data[i:])
    w.close()
    return out.getvalue()


def _members(raw: bytes) -> int:
    """Nombre de membres gzip : occurrences de l'en-tête 1f 8b 08 00 00000000."""
    return raw.count(b"\x1f\x8b\x08\x00\x00\x00\x00\x00")


class ParallelGzipTests(unittest.TestCase):
    def test_relu_par_gzipfile_octet_pour_octet(self):
        data = os.urandom(3 * BLOCK + 123) + b"abc" * 5000
        raw = _compress(data, level=1)
        self.assertEqual(gzip.GzipFile(fileobj=io.BytesIO(raw), mode="rb").read(), data)
        self.assertEqual(gzip.decompress(raw), data)

    def test_plusieurs_membres_ordre_conserve(self):
        # Contenu numéroté : tout bloc permuté changerait la relecture.
        data = b"".join(b"%08d\n" % i for i in range(20000))
        raw = _compress(data, level=3)
        self.assertGreater(_members(raw), 3)
        self.assertEqual(gzip.decompress(raw), data)

    def test_flux_vide_reste_un_gzip_valide(self):
        out = io.BytesIO()
        ParallelGzipWriter(out, block_size=BLOCK, workers=2).close()
        self.assertEqual(gzip.decompress(out.getvalue()), b"")

    def test_taille_exacte_multiple_du_bloc(self):
        data = os.urandom(BLOCK * 3)
        self.assertEqual(gzip.decompress(_compress(data, level=1)), data)

    def test_sortie_deterministe(self):
        # mtime=0 : deux compressions du même flux donnent les mêmes octets,
        # quel que soit l'ordre d'exécution des threads.
        data = b"nebula" * 9000
        self.assertEqual(_compress(data, level=1), _compress(data, level=1))

    def test_close_idempotent_et_out_reste_ouvert(self):
        out = io.BytesIO()
        w = ParallelGzipWriter(out, block_size=BLOCK, workers=2)
        w.write(b"x" * 10000)
        w.close()
        w.close()
        self.assertFalse(out.closed)
        self.assertEqual(gzip.decompress(out.getvalue()), b"x" * 10000)

    def test_ecriture_apres_fermeture_refusee(self):
        w = ParallelGzipWriter(io.BytesIO(), block_size=BLOCK, workers=2)
        w.close()
        with self.assertRaises(ValueError):
            w.write(b"x")

    def test_erreur_d_ecriture_propagee_sans_thread_residuel(self):
        class Boom(io.RawIOBase):
            def write(self, b):
                raise OSError("disque plein")

        before = {t for t in threading.enumerate() if t.name.startswith("nebmig-gz")}
        w = ParallelGzipWriter(Boom(), block_size=BLOCK, workers=2)
        with self.assertRaises(OSError):
            for _ in range(50):
                w.write(os.urandom(BLOCK))
            w.close()
        try:
            w.close()
        except OSError:
            pass
        after = {t for t in threading.enumerate() if t.name.startswith("nebmig-gz")}
        self.assertEqual(after - before, set())

    def test_tar_aller_retour_comme_l_export(self):
        files = {f"d/f{i}.bin": os.urandom(300 + i * 997) for i in range(40)}
        out = io.BytesIO()
        gz = ParallelGzipWriter(out, block_size=BLOCK, workers=4)
        tf = tarfile.open(fileobj=gz, mode="w|", format=tarfile.PAX_FORMAT)
        for name, content in files.items():
            ti = tarfile.TarInfo(name)
            ti.size = len(content)
            tf.addfile(ti, io.BytesIO(content))
        tf.close()
        gz.close()
        out.seek(0)
        with tarfile.open(fileobj=gzip.GzipFile(fileobj=out, mode="rb"), mode="r|") as rd:
            got = {m.name: rd.extractfile(m).read() for m in rd}
        self.assertEqual(got, files)

    def test_nombre_de_workers_borne(self):
        self.assertGreaterEqual(default_workers(), 2)
        self.assertLessEqual(default_workers(), 12)


if __name__ == "__main__":
    unittest.main()
