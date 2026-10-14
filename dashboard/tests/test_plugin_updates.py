"""Plugins « à jour » (dashcore/plugin_updates.py) : comparaison de versions,
installé vs clone local du marketplace, rafraîchissement via la CLI."""
from __future__ import annotations

import json
import unittest
from unittest import mock

from _support import HOME, reset_sandbox, write_json_file
from dashcore import plugin_updates as pu

PLUGINS = HOME / ".claude" / "plugins"
MKT = PLUGINS / "marketplaces" / "mkt"
REV_NEW, REV_OLD = "a" * 40, "b" * 40


def _plugin(d, name, version=None, body="x\n"):
    meta = {"name": name}
    if version:
        meta["version"] = version
    write_json_file(d / ".claude-plugin" / "plugin.json", meta)
    (d / "README.md").write_text(body, encoding="utf-8")


class VersionTests(unittest.TestCase):
    def test_comparaisons(self):
        c = pu.compare_versions
        self.assertEqual(c("1.0.0", "1.2.0"), -1)
        self.assertEqual(c("1.10.0", "1.9.3"), 1)
        self.assertEqual(c("2.0", "2.0.0"), 0)
        self.assertEqual(c("v1.2.3", "1.2.3"), 0)
        self.assertEqual(c("1.2.0-beta", "1.2.0"), -1)
        self.assertEqual(c("1.2.0+build5", "1.2.0"), 0)
        self.assertEqual(c("abc", "abc"), 0)
        self.assertIsNone(c("8bd00f08f0b0", "1.0.0"))
        self.assertIsNone(c("", "1.0.0"))


class CompareTests(unittest.TestCase):
    def setUp(self):
        reset_sandbox()
        (MKT / ".gcs-sha").parent.mkdir(parents=True, exist_ok=True)
        (MKT / ".gcs-sha").write_text(REV_NEW, encoding="utf-8")
        specs = []
        for name, version, body in (("rev", None, "v2\n"), ("pareil", None, "same\n"), ("change", None, "neuf\n"),
                                    ("semver", "1.2.0", "s\n"), ("semver-ok", "2.0.0", "t\n")):
            _plugin(MKT / "plugins" / name, name, version, body)
            specs.append({"name": name, "source": f"./plugins/{name}"})
        specs += [
            {"name": "ext-sha", "source": {"source": "url", "url": "https://h/x.git", "sha": "c" * 40}},
            {"name": "ext-ver", "source": {"source": "url", "url": "https://h/y.git", "sha": "c" * 40}},
            {"name": "ext-branche", "source": {"source": "github", "repo": "o/r"}},
            {"name": "evasion", "source": "../../../ailleurs"},
            {"name": "explicite", "version": "3.1.0", "source": {"source": "github", "repo": "o/e"}},
            {"name": "inst-inconnu", "version": "2.0.0", "source": {"source": "github", "repo": "o/i"}},
            {"name": "sha-vers-version", "version": "2.0.0", "source": {"source": "github", "repo": "o/s"}},
        ]
        write_json_file(MKT / ".claude-plugin" / "marketplace.json", {"name": "mkt", "plugins": specs})
        write_json_file(PLUGINS / "known_marketplaces.json", {"mkt": {
            "installLocation": str(MKT), "lastUpdated": "2026-10-12T08:15:00.000Z"}})
        inst = {}

        def install(name, version, sha=None, body="x\n", meta_version=None, scope="user"):
            d = PLUGINS / "cache" / "mkt" / name / version[:12]
            _plugin(d, name, meta_version, body)
            (d / ".in_use").write_text("", encoding="utf-8")
            e = {"scope": scope, "installPath": str(d), "version": version}
            if sha:
                e["gitCommitSha"] = sha
            inst.setdefault(f"{name}@mkt", []).append(e)

        install("rev", REV_NEW[:12], REV_NEW, "v2\n")
        install("pareil", REV_OLD[:12], REV_OLD, "same\n")
        install("change", REV_OLD[:12], REV_OLD, "ancien\n")
        install("semver", "1.0.0", REV_OLD, "s\n", "1.0.0")
        install("semver-ok", "2.0.0", REV_OLD, "t\n", "2.0.0")
        install("ext-sha", ("d" * 40)[:12], "d" * 40)
        install("ext-ver", "1.1.1", "d" * 40)
        install("ext-branche", "0.3.0", "e" * 40)
        install("evasion", ("f" * 40)[:12], "f" * 40)
        install("explicite", "3.1.0")
        install("disparu", "1.0.0")
        install("inst-inconnu", "unknown")
        install("sha-vers-version", ("9f" * 20)[:12], "9f" * 20)
        write_json_file(PLUGINS / "installed_plugins.json", {"version": 2, "plugins": inst})
        self.res = pu.plugin_updates()

    def state(self, name):
        return self.res["plugins"][f"{name}@mkt"]["state"]

    def test_etats_par_cas(self):
        attendu = {
            "rev": pu.UP_TO_DATE,            # même révision du marketplace
            "pareil": pu.UP_TO_DATE,         # autre révision, contenu identique (.in_use ignoré)
            "change": pu.OUTDATED,           # contenu modifié dans le marketplace
            "semver": pu.OUTDATED,           # 1.0.0 < 1.2.0
            "semver-ok": pu.UP_TO_DATE,
            "ext-sha": pu.OUTDATED,          # révision installée != révision épinglée
            "ext-ver": pu.UNKNOWN,           # version déclarée dans un dépôt non cloné
            "ext-branche": pu.UNKNOWN,       # source non épinglée
            "evasion": pu.UNKNOWN,           # source relative hors du clone : refusée
            "explicite": pu.UP_TO_DATE,      # version explicite du marketplace
            "disparu": pu.UNKNOWN,           # plus listé
            "inst-inconnu": pu.UNKNOWN,      # version installée « unknown » : jamais « mise à jour »
            "sha-vers-version": pu.OUTDATED,  # installé par révision, marketplace désormais versionné
        }
        for name, st in attendu.items():
            with self.subTest(plugin=name):
                self.assertEqual(self.state(name), st, self.res["plugins"][f"{name}@mkt"]["reason"])

    def test_empreinte_fichier_trop_gros_inconnue(self):
        d = MKT / "plugins" / "rev"
        self.assertIsNotNone(pu._content_digest(d))
        with mock.patch.object(pu, "_CONTENT_MAX_BYTES", 1):
            self.assertIsNone(pu._content_digest(d))

    def test_synthese(self):
        self.assertEqual(self.res["counts"], {"up_to_date": 4, "outdated": 4, "unknown": 5})
        self.assertEqual(self.res["total"], 13)
        self.assertEqual(self.res["checked_at"], "2026-10-12T08:15:00.000Z")
        r = self.res["plugins"]["semver@mkt"]
        self.assertEqual((r["installed"], r["available"], r["basis"]), ("1.0.0", "1.2.0", "version"))
        self.assertEqual(self.res["plugins"]["change@mkt"]["available"], REV_NEW[:12])

    def test_scope_user_prioritaire(self):
        inst = json.loads((PLUGINS / "installed_plugins.json").read_text(encoding="utf-8"))
        old = dict(inst["plugins"]["semver@mkt"][0], scope="project", version="1.2.0")
        inst["plugins"]["semver@mkt"].insert(0, old)
        write_json_file(PLUGINS / "installed_plugins.json", inst)
        self.assertEqual(pu.plugin_updates()["plugins"]["semver@mkt"]["state"], pu.OUTDATED)

    def test_marketplace_absent_ou_illisible(self):
        (MKT / ".claude-plugin" / "marketplace.json").write_text("{cassé", encoding="utf-8")
        res = pu.plugin_updates()
        self.assertEqual(res["counts"]["unknown"], res["total"])
        import shutil
        shutil.rmtree(MKT)
        self.assertTrue(all(r["state"] == pu.UNKNOWN for r in pu.plugin_updates()["plugins"].values()))

    def test_revision_git_lue_sur_disque(self):
        repo = PLUGINS / "marketplaces" / "gitmkt"
        (repo / ".git" / "refs" / "heads").mkdir(parents=True)
        (repo / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
        (repo / ".git" / "packed-refs").write_text(f"# pack\n{'1' * 40} refs/heads/main\n", encoding="utf-8")
        self.assertEqual(pu._marketplace_revision(repo), "1" * 40)
        (repo / ".git" / "refs" / "heads" / "main").write_text("2" * 40 + "\n", encoding="utf-8")
        self.assertEqual(pu._marketplace_revision(repo), "2" * 40)

    def test_aucun_plugin(self):
        (PLUGINS / "installed_plugins.json").unlink()
        res = pu.plugin_updates()
        self.assertEqual((res["total"], res["checked_at"]), (0, None))


class RefreshTests(unittest.TestCase):
    def setUp(self):
        reset_sandbox()

    def test_nom_invalide(self):
        self.assertEqual(pu.refresh_marketplaces("../x")[0], 400)

    def test_echec_cli_remonte_en_http_non_ok(self):
        fake = (200, {"ok": False, "returncode": 1, "stdout": "", "stderr": "network unreachable"})
        with mock.patch("dashcore.api_plugins.claude_plugin_cli", return_value=fake) as cli:
            status, out = pu.refresh_marketplaces()
        self.assertEqual(status, 502)
        self.assertIn("network unreachable", out["error"])
        cli.assert_called_once_with(["marketplace", "update"], timeout=pu.REFRESH_TIMEOUT_S)
        with mock.patch("dashcore.api_plugins.claude_plugin_cli",
                        return_value=(500, {"ok": False, "error": "timeout (180s)"})):
            self.assertEqual(pu.refresh_marketplaces("mkt"), (502, {"error": "timeout (180s)"}))

    def test_succes_renvoie_la_nouvelle_synthese(self):
        with mock.patch("dashcore.api_plugins.claude_plugin_cli",
                        return_value=(200, {"ok": True, "returncode": 0, "stdout": "ok", "stderr": ""})) as cli:
            status, out = pu.refresh_marketplaces("mkt")
        self.assertEqual(status, 200)
        self.assertTrue(out["ok"])
        self.assertIn("counts", out["updates"])
        cli.assert_called_once_with(["marketplace", "update", "mkt"], timeout=pu.REFRESH_TIMEOUT_S)

    def test_un_seul_rafraichissement_a_la_fois(self):
        pu._REFRESH_LOCK.acquire()
        try:
            self.assertEqual(pu.refresh_marketplaces()[0], 409)
        finally:
            pu._REFRESH_LOCK.release()


if __name__ == "__main__":
    unittest.main()
