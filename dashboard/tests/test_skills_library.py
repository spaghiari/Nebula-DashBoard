"""api_skills_library : list_library, distribution, cache de `_hash_dir`.

Le cache (clé : signature mtime_ns + taille des fichiers) doit rendre un
hash STRICTEMENT identique à l'algorithme d'origine, recopié ici comme
référence, et s'invalider à toute modification du dossier.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import unittest
from pathlib import Path
from unittest import mock

from _support import HOME, make_workspace, reset_sandbox
from dashcore import api_skills_library as lib
from dashcore.config import SKILLS_LIBRARY_DIR


def _hash_dir_reference(d: Path) -> str:
    """Algorithme d'origine (sans cache), référence des comparaisons."""
    h = hashlib.sha256()
    if not d.exists():
        return ""
    for f in sorted(d.rglob("*")):
        if not f.is_file():
            continue
        if f.name == ".nebula-origin.json":
            continue
        try:
            h.update(f.relative_to(d).as_posix().encode("utf-8"))
            h.update(b"\0")
            h.update(f.read_bytes())
            h.update(b"\0")
        except OSError:
            continue
    return h.hexdigest()


def _make_skill(parent: Path, name: str, desc: str = "desc", extra: dict | None = None) -> Path:
    d = parent / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: \"{desc}\"\n---\n\n# {name}\n", encoding="utf-8")
    for rel, content in (extra or {}).items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return d


def _bump_mtime(p: Path) -> None:
    """Décale le mtime de 2 s : contenu réécrit à taille égale détectable
    même sur un système de fichiers à résolution grossière."""
    st = p.stat()
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + 2_000_000_000))


class HashDirCacheTests(unittest.TestCase):
    def setUp(self):
        reset_sandbox()
        lib._HASH_CACHE.clear()
        self.skill = _make_skill(SKILLS_LIBRARY_DIR, "alpha", extra={
            "README.md": "lisez-moi\n",
            "references/b.md": "bbb\n",
            "references/A.md": "AAA\n",
            "examples/deep/x.txt": "x\n",
        })

    def test_dossier_absent(self):
        self.assertEqual(lib._hash_dir(SKILLS_LIBRARY_DIR / "absent"), "")

    def test_identique_a_la_reference_avec_et_sans_cache(self):
        ref = _hash_dir_reference(self.skill)
        self.assertEqual(lib._hash_dir(self.skill), ref)
        self.assertEqual(lib._hash_dir(self.skill), ref)  # 2e appel : cache

    def test_origin_ignore(self):
        before = lib._hash_dir(self.skill)
        (self.skill / ".nebula-origin.json").write_text(json.dumps({"repo": "a/b"}), encoding="utf-8")
        self.assertEqual(lib._hash_dir(self.skill), before)
        self.assertEqual(lib._hash_dir(self.skill), _hash_dir_reference(self.skill))

    def test_cache_evite_la_relecture(self):
        lib._hash_dir(self.skill)
        with mock.patch.object(Path, "read_bytes", side_effect=AssertionError("relu")):
            lib._hash_dir(self.skill)

    def test_invalidation_contenu_meme_taille(self):
        before = lib._hash_dir(self.skill)
        f = self.skill / "references" / "b.md"
        f.write_text("ccc\n", encoding="utf-8")  # même taille
        _bump_mtime(f)
        after = lib._hash_dir(self.skill)
        self.assertNotEqual(after, before)
        self.assertEqual(after, _hash_dir_reference(self.skill))

    def test_invalidation_ajout_suppression_renommage(self):
        h0 = lib._hash_dir(self.skill)
        (self.skill / "nouveau.md").write_text("n\n", encoding="utf-8")
        h1 = lib._hash_dir(self.skill)
        self.assertNotEqual(h1, h0)
        self.assertEqual(h1, _hash_dir_reference(self.skill))
        (self.skill / "nouveau.md").rename(self.skill / "renomme.md")
        h2 = lib._hash_dir(self.skill)
        self.assertNotEqual(h2, h1)
        self.assertEqual(h2, _hash_dir_reference(self.skill))
        (self.skill / "renomme.md").unlink()
        self.assertEqual(lib._hash_dir(self.skill), h0)

    def test_dossier_vide_et_sous_dossier_vide(self):
        (self.skill / "vide").mkdir()
        self.assertEqual(lib._hash_dir(self.skill), _hash_dir_reference(self.skill))
        empty = SKILLS_LIBRARY_DIR / "vide"
        empty.mkdir()
        self.assertEqual(lib._hash_dir(empty), _hash_dir_reference(empty))

    def test_copie_identique_meme_hash(self):
        copy = HOME / "copie" / "alpha"
        shutil.copytree(self.skill, copy)
        self.assertEqual(lib._hash_dir(copy), lib._hash_dir(self.skill))


class ListLibraryTests(unittest.TestCase):
    def setUp(self):
        reset_sandbox()
        lib._HASH_CACHE.clear()
        self.src = _make_skill(SKILLS_LIBRARY_DIR, "alpha", "Premier skill")
        _make_skill(SKILLS_LIBRARY_DIR, "beta")
        (SKILLS_LIBRARY_DIR / "sans-skill-md").mkdir()
        (SKILLS_LIBRARY_DIR / "fichier.txt").write_text("x", encoding="utf-8")
        self.ws = make_workspace("w1")

    def _by_id(self):
        return {s["id"]: s for s in lib.list_library()}

    def test_liste_et_meta(self):
        items = self._by_id()
        self.assertEqual(sorted(items), ["alpha", "beta"])
        self.assertEqual(items["alpha"]["name"], "alpha")
        self.assertEqual(items["alpha"]["description"], "Premier skill")
        self.assertEqual(items["alpha"]["distributed_to"], [])
        self.assertIsNone(items["alpha"]["origin"])

    def test_origin_github(self):
        (self.src / ".nebula-origin.json").write_text(
            json.dumps({"repo": "o/r", "commit": "abc"}), encoding="utf-8")
        self.assertEqual(self._by_id()["alpha"]["origin"], {"repo": "o/r", "commit": "abc"})

    def test_distribution_et_desynchronisation(self):
        status, payload = lib.distribute("alpha", ["global", "workspace:w1"])
        self.assertEqual(status, 200, payload)
        item = self._by_id()["alpha"]
        self.assertEqual(sorted(item["distributed_to"]), ["global", "workspace:w1"])
        self.assertEqual(item["outdated_count"], 0)

        # Édition de la source : les deux copies deviennent désynchronisées
        # (le cache ne doit pas masquer la modification).
        md = self.src / "SKILL.md"
        md.write_text(md.read_text(encoding="utf-8") + "ajout\n", encoding="utf-8")
        self.assertEqual(self._by_id()["alpha"]["outdated_count"], 2)

        # Resync explicite : de nouveau à jour.
        lib.distribute("alpha", ["global", "workspace:w1"])
        self.assertEqual(self._by_id()["alpha"]["outdated_count"], 0)

        # Retrait d'une cible.
        lib.distribute("alpha", ["global"])
        self.assertEqual(self._by_id()["alpha"]["distributed_to"], ["global"])
        self.assertFalse((self.ws / ".claude" / "skills" / "alpha").exists())

    def test_copie_sans_skill_md_ignoree(self):
        (HOME / ".claude" / "skills" / "alpha").mkdir(parents=True)
        self.assertEqual(self._by_id()["alpha"]["distributed_to"], [])

    def test_get_distribution_coherente_avec_la_liste(self):
        lib.distribute("alpha", ["workspace:w1"])
        status, payload = lib.get_distribution("alpha")
        self.assertEqual(status, 200)
        self.assertEqual(payload["library_hash"], _hash_dir_reference(self.src))
        self.assertEqual([t["target"] for t in payload["targets"]], ["workspace:w1"])
        self.assertEqual(self._by_id()["alpha"]["distributed_to"], ["workspace:w1"])

    def test_noms_invalides(self):
        self.assertEqual(lib.get_distribution("../x")[0], 400)
        self.assertEqual(lib.get_distribution("absent")[0], 404)


if __name__ == "__main__":
    unittest.main()
