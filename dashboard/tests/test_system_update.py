"""system_update : stash NOMMÉ et vérifié, jamais de pop du stash utilisateur.

Dépôts git temporaires (remote nu + clone). Ignoré si git est absent.
"""
from __future__ import annotations

import shutil
import subprocess
import unittest
from unittest import mock

from _support import SANDBOX, rmtree
from dashcore import system_update

GIT = shutil.which("git")


def git(cwd, *args, check=True):
    r = subprocess.run([GIT, *args], cwd=str(cwd), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} : {r.stderr or r.stdout}")
    return r.stdout.strip()


@unittest.skipUnless(GIT, "git introuvable dans le PATH")
class StashSafetyTests(unittest.TestCase):
    def setUp(self):
        self.base = SANDBOX / "git"
        rmtree(self.base)
        self.remote = self.base / "remote.git"
        self.seed = self.base / "seed"
        self.work = self.base / "work"
        self.base.mkdir()
        git(self.base, "init", "-q", "--bare", "-b", "main", str(self.remote))
        git(self.base, "init", "-q", "-b", "main", str(self.seed))
        (self.seed / "a.txt").write_text("v1\n", encoding="utf-8")
        git(self.seed, "add", "a.txt")
        git(self.seed, "commit", "-q", "-m", "init")
        git(self.seed, "remote", "add", "origin", str(self.remote))
        git(self.seed, "push", "-q", "origin", "main")
        git(self.base, "clone", "-q", str(self.remote), str(self.work))
        # Stash PRÉEXISTANT de l'utilisateur : ne doit jamais être dépilé.
        (self.work / "a.txt").write_text("travail utilisateur\n", encoding="utf-8")
        git(self.work, "stash", "push", "-q", "-m", "stash-utilisateur")
        self._patch = mock.patch.object(system_update, "ROOT", self.work)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        rmtree(self.base)

    def _stashes(self):
        return git(self.work, "stash", "list", "--format=%gs").splitlines()

    def _upstream_commit(self):
        (self.seed / "b.txt").write_text("nouveau\n", encoding="utf-8")
        git(self.seed, "add", "b.txt")
        git(self.seed, "commit", "-q", "-m", "amont")
        git(self.seed, "push", "-q", "origin", "main")

    def test_stash_sans_rien_a_sauver_signale_l_echec(self):
        ok, msg = system_update._stash_push_verified("nebula-test-1", include_untracked=True)
        self.assertFalse(ok)
        self.assertTrue(msg)
        self.assertEqual(len(self._stashes()), 1)
        self.assertTrue(self._stashes()[0].endswith("stash-utilisateur"))

    def test_stash_verifie_retrouve_par_son_label(self):
        (self.work / "a.txt").write_text("modif\n", encoding="utf-8")
        ok, _ = system_update._stash_push_verified("nebula-test-2", include_untracked=False)
        self.assertTrue(ok)
        self.assertEqual(system_update._find_stash_ref_by_label("nebula-test-2"), "stash@{0}")
        self.assertEqual(system_update._find_stash_ref_by_label("stash-utilisateur"), "stash@{1}")
        self.assertIsNone(system_update._find_stash_ref_by_label("absent"))

    def test_update_avec_modifs_locales_restaure_et_garde_le_stash_utilisateur(self):
        self._upstream_commit()
        (self.work / "a.txt").write_text("modif locale\n", encoding="utf-8")
        (self.work / "nouveau-local.txt").write_text("x\n", encoding="utf-8")
        status, payload = system_update.system_apply_update()
        self.assertEqual(status, 200, payload)
        self.assertTrue(payload["ok"], payload)
        self.assertTrue(payload["applied"])
        self.assertTrue(payload["stash_applied"])
        self.assertIsNone(payload["stash_pop_warning"])
        self.assertTrue((self.work / "b.txt").exists())
        self.assertEqual((self.work / "a.txt").read_text(encoding="utf-8"), "modif locale\n")
        self.assertTrue((self.work / "nouveau-local.txt").exists())
        self.assertEqual(len(self._stashes()), 1)
        self.assertTrue(self._stashes()[0].endswith("stash-utilisateur"))

    def test_update_arbre_propre_ne_touche_pas_au_stash_utilisateur(self):
        self._upstream_commit()
        status, payload = system_update.system_apply_update()
        self.assertEqual(status, 200, payload)
        self.assertTrue(payload["applied"])
        self.assertFalse(payload["stash_applied"])
        self.assertEqual((self.work / "a.txt").read_text(encoding="utf-8"), "v1\n")
        self.assertEqual(len(self._stashes()), 1)

    def test_status_paths_porcelain_v2(self):
        (self.work / "a.txt").write_text("m\n", encoding="utf-8")
        (self.work / "nouveau fichier.txt").write_text("n\n", encoding="utf-8")
        paths = system_update._status_paths()
        self.assertEqual(paths.get("a.txt"), ".M")
        self.assertEqual(paths.get("nouveau fichier.txt"), "??")


class NormalizeGitUrlTests(unittest.TestCase):
    def test_variantes_de_l_ancien_depot(self):
        ref = system_update._normalize_git_url(system_update.LEGACY_ORIGIN_URL)
        self.assertEqual(ref, "git.exemple.lan/erti/claude-dashboard")
        for url in (
            "https://git.exemple.lan/erti/claude-dashboard.git",
            "https://git.exemple.lan/erti/claude-dashboard",
            "https://git.exemple.lan/erti/claude-dashboard/",
            "http://git.exemple.lan/erti/claude-dashboard.git",
            "https://user:jeton@git.exemple.lan/erti/claude-dashboard.git",
            "https://git.exemple.lan:443/erti/claude-dashboard.git",
            "git@git.exemple.lan:erti/claude-dashboard.git",
            "git@git.exemple.lan:erti/claude-dashboard",
            "ssh://git@git.exemple.lan/erti/claude-dashboard.git",
            "ssh://git@git.exemple.lan:2222/erti/claude-dashboard",
            "  HTTPS://git.exemple.lan/ERTI/Claude-Dashboard.git  ",
        ):
            with self.subTest(url=url):
                self.assertEqual(system_update._normalize_git_url(url), ref)

    def test_autres_depots_distincts(self):
        ref = system_update._normalize_git_url(system_update.LEGACY_ORIGIN_URL)
        for url in (
            system_update.ORIGIN_URL,
            "https://git.exemple.lan/autre/claude-dashboard.git",
            "https://git.exemple.lan/erti/claude-dashboard-fork.git",
            "git@github.com:erti/claude-dashboard.git",
            "C:/depots/claude-dashboard.git",
            "",
        ):
            with self.subTest(url=url):
                self.assertNotEqual(system_update._normalize_git_url(url), ref)


@unittest.skipUnless(GIT, "git introuvable dans le PATH")
class OriginMigrationTests(unittest.TestCase):
    """Bascule GitLab -> Forgejo : dépôt bac à sable, jamais le vrai dépôt.

    La « nouvelle » URL est remplacée par un dépôt nu local pour que le pull
    qui suit la bascule fonctionne hors réseau.
    """

    def setUp(self):
        self.base = SANDBOX / "git-origin"
        rmtree(self.base)
        self.remote = self.base / "remote.git"
        self.seed = self.base / "seed"
        self.work = self.base / "work"
        self.base.mkdir()
        git(self.base, "init", "-q", "--bare", "-b", "main", str(self.remote))
        git(self.base, "init", "-q", "-b", "main", str(self.seed))
        (self.seed / "a.txt").write_text("v1\n", encoding="utf-8")
        git(self.seed, "add", "a.txt")
        git(self.seed, "commit", "-q", "-m", "init")
        git(self.seed, "remote", "add", "origin", str(self.remote))
        git(self.seed, "push", "-q", "origin", "main")
        git(self.base, "clone", "-q", str(self.remote), str(self.work))
        self._patches = [mock.patch.object(system_update, "ROOT", self.work),
                         mock.patch.object(system_update, "ORIGIN_URL", str(self.remote))]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in reversed(self._patches):
            p.stop()
        rmtree(self.base)

    def _origin(self):
        return git(self.work, "remote", "get-url", "origin")

    def test_bascule_puis_update(self):
        git(self.work, "remote", "set-url", "origin",
            "git@git.exemple.lan:erti/claude-dashboard.git")
        (self.seed / "b.txt").write_text("nouveau\n", encoding="utf-8")
        git(self.seed, "add", "b.txt")
        git(self.seed, "commit", "-q", "-m", "amont")
        git(self.seed, "push", "-q", "origin", "main")
        status, payload = system_update.system_apply_update()
        self.assertEqual(status, 200, payload)
        self.assertEqual(self._origin(), str(self.remote))
        self.assertTrue((self.work / "b.txt").exists())

    def test_idempotent(self):
        git(self.work, "remote", "set-url", "origin", system_update.LEGACY_ORIGIN_URL)
        self.assertTrue(system_update._migrate_origin_remote())
        self.assertFalse(system_update._migrate_origin_remote())
        self.assertEqual(self._origin(), str(self.remote))

    def test_fork_ou_autre_remote_intouche(self):
        fork = "https://git.exemple.lan/quelquun/claude-dashboard.git"
        git(self.work, "remote", "set-url", "origin", fork)
        git(self.work, "remote", "add", "gitlab", system_update.LEGACY_ORIGIN_URL)
        self.assertFalse(system_update._migrate_origin_remote())
        self.assertEqual(self._origin(), fork)
        self.assertEqual(git(self.work, "remote", "get-url", "gitlab"),
                         system_update.LEGACY_ORIGIN_URL)

    def test_cible_injoignable_pas_de_bascule(self):
        git(self.work, "remote", "set-url", "origin", system_update.LEGACY_ORIGIN_URL)
        absent = str(self.work.parent / "depot-inexistant.git")
        with mock.patch.object(system_update, "ORIGIN_URL", absent):
            self.assertFalse(system_update._migrate_origin_remote())
        self.assertEqual(self._origin(), system_update.LEGACY_ORIGIN_URL)

    def test_sans_origin(self):
        git(self.work, "remote", "remove", "origin")
        self.assertFalse(system_update._migrate_origin_remote())


if __name__ == "__main__":
    unittest.main()
