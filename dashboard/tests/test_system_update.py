"""system_update : stash NOMMÉ et vérifié, jamais de pop du stash utilisateur.

Dépôts git temporaires (remote nu + clone). Ignoré si git est absent.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import threading
import time
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


class RepoWebUrlTests(unittest.TestCase):
    """Dérivation de l'URL web du dépôt : jamais d'identifiants, http(s) seulement."""

    def test_formes_reconnues(self):
        web = "https://github.com/spaghiari/Nebula-DashBoard"
        for url in (
            "https://github.com/spaghiari/Nebula-DashBoard.git",
            "https://github.com/spaghiari/Nebula-DashBoard",
            "https://github.com/spaghiari/Nebula-DashBoard/",
            "git@github.com:spaghiari/Nebula-DashBoard.git",
            "git@github.com:spaghiari/Nebula-DashBoard",
            "ssh://git@github.com/spaghiari/Nebula-DashBoard.git",
            "ssh://git@github.com:22/spaghiari/Nebula-DashBoard",
            "https://github.com:443/spaghiari/Nebula-DashBoard.git",
            "  https://GitHub.com/spaghiari/Nebula-DashBoard.git  ",
        ):
            with self.subTest(url=url):
                self.assertEqual(system_update._repo_web_url(url), web)

    def test_identifiants_retires(self):
        for url in (
            "https://ghp_JETONSECRET@github.com/o/r.git",
            "https://user:motdepasse@github.com/o/r.git",
            "https://user:motdepasse@github.com/o/r.git?jeton=JETONSECRET#frag",
            "ssh://user:motdepasse@github.com/o/r.git",
        ):
            with self.subTest(url=url):
                web = system_update._repo_web_url(url)
                self.assertEqual(web, "https://github.com/o/r")
                for secret in ("JETONSECRET", "motdepasse", "user", "@"):
                    self.assertNotIn(secret, web)

    def test_http_et_port_web_conserves(self):
        self.assertEqual(system_update._repo_web_url("http://forge.lan:3000/a/b.git"),
                         "http://forge.lan:3000/a/b")
        self.assertEqual(system_update._repo_web_url("https://git.example.org/equipe/Projet.git"),
                         "https://git.example.org/equipe/Projet")

    def test_aucune_url_pour_chemin_local_ou_schema_inconnu(self):
        for url in (
            "C:/depots/nebula.git",
            "C:\\depots\\nebula.git",
            "/srv/git/nebula.git",
            "../nebula.git",
            "file:///C:/depots/nebula.git",
            "git://github.com/o/r.git",
            "ftp://github.com/o/r.git",
            "javascript://github.com/o/r",
            "https://github.com/seul-segment",
            "https://github.com/o/../r",
            "https://bad host/o/r",
            "",
        ):
            with self.subTest(url=url):
                self.assertEqual(system_update._repo_web_url(url), "")
                self.assertEqual(system_update._repo_links(url)["repo_web_url"], "")

    def test_liens_et_libelle(self):
        links = system_update._repo_links("git@github.com:o/r.git")
        self.assertEqual(links, {
            "repo_web_url": "https://github.com/o/r",
            "repo_host_label": "GitHub",
            "repo_issues_url": "https://github.com/o/r/issues",
            "repo_commit_url": "https://github.com/o/r/commit/",
        })
        autre = system_update._repo_links("https://git.example.org/a/b.git")
        self.assertEqual(autre["repo_host_label"], "git.example.org")
        self.assertEqual(autre["repo_commit_url"], "https://git.example.org/a/b/commit/")
        gitlab = system_update._repo_links("https://gitlab.com/g/sous/r.git")
        self.assertEqual(gitlab["repo_host_label"], "GitLab")
        self.assertEqual(gitlab["repo_issues_url"], "https://gitlab.com/g/sous/r/-/issues")

    def test_redaction_des_erreurs(self):
        err = "fatal: unable to access 'https://ghp_JETON:x@github.com/o/r.git/': 403"
        red = system_update._redact_credentials(err)
        self.assertNotIn("ghp_JETON", red)
        self.assertIn("https://github.com/o/r.git/", red)

    def test_diagnostic_auth_avant_connexion(self):
        hint = system_update._diagnose_remote_failure(
            "git@github.com: Permission denied (publickey).\n"
            "fatal: Could not read from remote repository.")
        self.assertIn("Accès au dépôt refusé", hint)
        hint = system_update._diagnose_remote_failure(
            "fatal: could not read Username for 'https://github.com': terminal prompts disabled")
        self.assertIn("privé", hint)
        hint = system_update._diagnose_remote_failure("fatal: Could not resolve host: github.com")
        self.assertIn("Connexion", hint)


@unittest.skipUnless(GIT, "git introuvable dans le PATH")
class VersionInfoTests(unittest.TestCase):
    """Champs de /api/system/version : liens dépôt, état de vérification, fetch unique."""

    def setUp(self):
        self.base = SANDBOX / "git-version"
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
        system_update._FETCH_STATE.clear()
        self._patch = mock.patch.object(system_update, "ROOT", self.work)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        system_update._FETCH_STATE.clear()
        rmtree(self.base)

    def _upstream_commit(self, msg="feature(ui): nouvel écran"):
        (self.seed / "b.txt").write_text("nouveau\n", encoding="utf-8")
        git(self.seed, "add", "b.txt")
        git(self.seed, "commit", "-q", "-m", msg)
        git(self.seed, "push", "-q", "origin", "main")

    def test_remote_avec_jeton_aucun_identifiant_dans_la_reponse(self):
        git(self.work, "remote", "set-url", "origin",
            "https://ghp_JETONSECRET:x-oauth@github.com/spaghiari/Nebula-DashBoard.git")
        info = system_update.system_version_info(check_remote=False)
        self.assertEqual(info["repo_web_url"], "https://github.com/spaghiari/Nebula-DashBoard")
        self.assertEqual(info["repo_host_label"], "GitHub")
        self.assertEqual(info["repo_issues_url"], "https://github.com/spaghiari/Nebula-DashBoard/issues")
        self.assertEqual(info["repo_commit_url"], "https://github.com/spaghiari/Nebula-DashBoard/commit/")
        dump = json.dumps(info)
        self.assertNotIn("JETONSECRET", dump)
        self.assertNotIn("x-oauth", dump)

    def test_remote_local_liens_vers_depot_public_et_fetch_horodate(self):
        # Les liens de l'interface pointent toujours vers le dépôt public
        # (GitHub), jamais vers le remote local (dépôt de travail interne).
        self._upstream_commit()
        info = system_update.system_version_info(check_remote=True)
        self.assertTrue(info["fetched"])
        self.assertEqual(info["repo_web_url"], system_update.PUBLIC_REPO_URL)
        self.assertEqual(info["repo_issues_url"], system_update.PUBLIC_REPO_URL + "/issues")
        self.assertEqual(info["repo_host_label"], "GitHub")
        self.assertIsNotNone(info["checked_at"])
        self.assertIsNone(info["check_error"])
        self.assertEqual(info["behind"], 1)
        c = info["commits"][0]
        self.assertEqual(c["subject"], "feature(ui): nouvel écran")
        self.assertEqual(len(c["sha_full"]), 40)
        self.assertTrue(c["sha_full"].startswith(c["sha"]))
        self.assertRegex(c["date"], r"^\d{4}-\d\d-\d\dT")

    def test_fetch_en_echec_explique_sans_identifiants(self):
        orig = system_update._git

        def fake(*args, **kw):
            if args[:1] == ("fetch",):
                return 128, "", ("fatal: unable to access 'https://ghp_JETONSECRET@github.com/o/r.git/': "
                                 "Could not resolve host: github.com")
            return orig(*args, **kw)

        with mock.patch.object(system_update, "_git", side_effect=fake):
            info = system_update.system_version_info(check_remote=True)
        self.assertFalse(info["fetched"])
        self.assertIn("Could not resolve host", info["fetch_error"])
        self.assertEqual(info["check_error"], info["fetch_error"])
        self.assertIn("Connexion", info["check_hint"])
        self.assertNotIn("JETONSECRET", json.dumps(info))
        # La réponse reste complète (retard calculé sur la dernière ref connue).
        self.assertEqual(info["behind"], 0)
        self.assertIn("diverged", info)
        # Lecture simple suivante : l'échec reste visible.
        again = system_update.system_version_info(check_remote=False)
        self.assertEqual(again["check_error"], info["check_error"])

    def test_fetch_non_interactif(self):
        orig = system_update._git
        seen = []

        def spy(*args, **kw):
            if args[:1] == ("fetch",):
                seen.append(kw.get("env") or {})
            return orig(*args, **kw)

        with mock.patch.object(system_update, "_git", side_effect=spy):
            system_update.system_version_info(check_remote=True)
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0].get("GIT_TERMINAL_PROMPT"), "0")
        self.assertEqual(seen[0].get("GCM_INTERACTIVE"), "never")

    def test_deux_verifications_concurrentes_un_seul_fetch(self):
        orig = system_update._git
        fetches = []

        def slow(*args, **kw):
            if args[:1] == ("fetch",):
                fetches.append(threading.get_ident())
                time.sleep(0.4)
            return orig(*args, **kw)

        results = []
        with mock.patch.object(system_update, "_git", side_effect=slow):
            threads = [threading.Thread(target=lambda: results.append(
                system_update.system_version_info(check_remote=True))) for _ in range(2)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(30)
        self.assertEqual(len(fetches), 1)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r["fetched"] for r in results))

    def test_fetch_ancien_refait(self):
        system_update.system_version_info(check_remote=True)
        state = system_update._FETCH_STATE[str(self.work)]
        state["attempt_at"] -= system_update.FETCH_REUSE_SECONDS + 1
        self._upstream_commit()
        info = system_update.system_version_info(check_remote=True)
        self.assertEqual(info["behind"], 1)



class NonInteractiveSshTests(unittest.TestCase):
    """Fetch d'arrière-plan : OpenSSH en BatchMode (aucune passphrase ni
    confirmation de clé d'hôte attendue dans la console du serveur), sans
    jamais écraser une commande SSH choisie par l'utilisateur."""

    def _env(self, environ, ssh_command=""):
        with mock.patch.dict(system_update.os.environ, environ, clear=True),                 mock.patch.object(system_update, "_git",
                                  return_value=(0 if ssh_command else 1, ssh_command, "")) as git:
            return system_update._noninteractive_env(), git

    def test_batchmode_par_defaut(self):
        env, _ = self._env({})
        self.assertEqual(env["GIT_SSH_COMMAND"], "ssh -o BatchMode=yes")
        self.assertEqual(env["GIT_TERMINAL_PROMPT"], "0")
        self.assertEqual(env["GCM_INTERACTIVE"], "never")

    def test_commande_ssh_utilisateur_respectee(self):
        env, git = self._env({"GIT_SSH_COMMAND": "plink -batch"})
        self.assertNotIn("GIT_SSH_COMMAND", env)  # _git complète l'environnement existant
        git.assert_not_called()
        env, _ = self._env({}, ssh_command="plink -batch")
        self.assertNotIn("GIT_SSH_COMMAND", env)



class LocalGitErrorTests(unittest.TestCase):
    """Retour terrain : git échouait dans le processus du dashboard (« v2.4.0 ? »,
    « Jamais vérifié », « Vérifier maintenant » sans effet) sans aucun message."""

    def _info(self, git_side_effect, upstream="", check=True):
        patches = (
            mock.patch.object(system_update, "_is_git_repo", return_value=True),
            mock.patch.object(system_update, "_current_branch", return_value="main"),
            mock.patch.object(system_update, "_tracking_branch", return_value=upstream),
            mock.patch.object(system_update, "_tracked_remote_url", return_value=""),
            mock.patch.object(system_update, "_fetch_remote", return_value=(True, "")),
            mock.patch.object(system_update, "_git", side_effect=git_side_effect),
        )
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        return system_update.system_version_info(check)

    def test_dubious_ownership_remontee_avec_solution(self):
        err = ("fatal: detected dubious ownership in repository at 'C:/claude-workspace'\n"
               "To add an exception for this directory, call: git config --global --add safe.directory")
        info = self._info(lambda *a, **k: (128, "", err))
        self.assertEqual(info["head"], "?")
        self.assertIn("dubious ownership", info["git_error"])
        self.assertIn("dubious ownership", info["check_error"])
        self.assertIn("safe.directory", info["check_hint"])
        self.assertIn("administrateur", info["check_hint"])

    def test_git_hors_path_trouve_dans_program_files(self):
        # Git for Windows « Git Bash seulement » : absent du PATH d'un dashboard
        # lancé par double-clic sur start-dashboard.bat.
        from dashcore import helpers
        with mock.patch.object(helpers.shutil, "which", return_value=None), \
                mock.patch.object(helpers.os, "name", "nt"), \
                mock.patch.dict(helpers.os.environ, {"ProgramW6432": "C:\\PF"}, clear=True), \
                mock.patch.object(helpers.os.path, "isfile",
                                  side_effect=lambda p: p.replace("/", "\\") == "C:\\PF\\Git\\cmd\\git.exe"):
            self.assertEqual(helpers.git_cli().replace("/", "\\"), "C:\\PF\\Git\\cmd\\git.exe")
        with mock.patch.object(helpers.shutil, "which", return_value=None), \
                mock.patch.object(helpers.os, "name", "nt"), \
                mock.patch.dict(helpers.os.environ, {}, clear=True):
            self.assertEqual(helpers.git_cli(), "git")
        with mock.patch.object(helpers.shutil, "which", return_value="/usr/bin/git"):
            self.assertEqual(helpers.git_cli(), "/usr/bin/git")

    def test_sans_branche_suivie_explique(self):
        info = self._info(lambda *a, **k: (0, "abc1234", ""))
        self.assertNotIn("git_error", info)
        self.assertEqual(info["check_error"], "Aucune branche distante suivie.")
        self.assertIn("--set-upstream-to=origin/main", info["check_hint"])
        # Sans vérification demandée : pas d'erreur affichée au chargement.
        info = self._info(lambda *a, **k: (0, "abc1234", ""), check=False)
        self.assertIsNone(info["check_error"])


if __name__ == "__main__":
    unittest.main()
