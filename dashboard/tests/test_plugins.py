"""api_plugins.uninstall_plugin : ids refusés, correspondance exacte, confinement."""
from __future__ import annotations

import os
import unittest

from _support import HOME, SANDBOX, read_json_file, reset_sandbox, write_json_file
from dashcore.api_plugins import uninstall_plugin
from dashcore.config import CLAUDE_SETTINGS
from dashcore.helpers import CorruptJsonError

PLUGINS = HOME / ".claude" / "plugins"


class UninstallPluginTests(unittest.TestCase):
    def setUp(self):
        reset_sandbox()
        for rel in ("foo", "foobar", "foo-old", "cache/mkt/foo", "cache/mkt/foobar",
                    "cache/autre/foo", "marketplaces/mkt"):
            (PLUGINS / rel).mkdir(parents=True)
            (PLUGINS / rel / "plugin.json").write_text("{}", encoding="utf-8")
        write_json_file(CLAUDE_SETTINGS, {"enabledPlugins": {"foo@mkt": True, "bar@mkt": True},
                                          "autre": 1})

    def test_ids_invalides_refuses(self):
        for bad in ("../x", "..", "a/b", "a\\b", "C:x", "foo@mkt/../..", "x..y", "",
                    "@mkt", "foo@", ".cache"):
            with self.subTest(bad=bad):
                self.assertEqual(uninstall_plugin(bad, remove_files=True)[0], 400)
        self.assertEqual(uninstall_plugin(None)[0], 400)

    def test_retire_de_la_config_sans_toucher_le_reste(self):
        status, payload = uninstall_plugin("foo@mkt")
        self.assertEqual(status, 200)
        self.assertTrue(payload["removed_from_config"])
        settings = read_json_file(CLAUDE_SETTINGS)
        self.assertEqual(settings["enabledPlugins"], {"bar@mkt": True})
        self.assertEqual(settings["autre"], 1)
        self.assertTrue((PLUGINS / "cache" / "mkt" / "foo").exists())   # remove_files=False

    def test_correspondance_exacte_layout_cache(self):
        status, payload = uninstall_plugin("foo@mkt", remove_files=True)
        self.assertEqual(status, 200)
        self.assertEqual(payload["removed_dir"], str(PLUGINS / "cache" / "mkt" / "foo"))
        self.assertFalse((PLUGINS / "cache" / "mkt" / "foo").exists())
        for kept in ("cache/mkt/foobar", "cache/autre/foo", "foo", "foobar", "foo-old"):
            self.assertTrue((PLUGINS / kept).exists(), kept)

    def test_correspondance_exacte_layout_legacy(self):
        _, payload = uninstall_plugin("foo", remove_files=True)
        self.assertEqual(payload["removed_dir"], str(PLUGINS / "foo"))
        for kept in ("foobar", "foo-old", "cache/mkt/foo"):
            self.assertTrue((PLUGINS / kept).exists(), kept)

    def test_entrees_reservees_jamais_supprimees(self):
        for reserved in ("cache", "marketplaces", "data"):
            with self.subTest(reserved=reserved):
                _, payload = uninstall_plugin(reserved, remove_files=True)
                self.assertIsNone(payload["removed_dir"])
        self.assertTrue((PLUGINS / "cache" / "mkt" / "foo").exists())
        self.assertTrue((PLUGINS / "marketplaces" / "mkt").exists())

    def test_lien_vers_l_exterieur_seul_le_lien_est_retire(self):
        outside = SANDBOX / "hors-plugins"
        outside.mkdir(exist_ok=True)
        (outside / "precieux.txt").write_text("x", encoding="utf-8")
        link = PLUGINS / "lien"
        try:
            os.symlink(outside, link, target_is_directory=True)
        except (OSError, NotImplementedError) as e:
            self.skipTest(f"création de lien symbolique impossible ici : {e}")
        _, payload = uninstall_plugin("lien", remove_files=True)
        self.assertEqual(payload["removed_dir"], str(link))
        self.assertFalse(os.path.lexists(link))
        self.assertTrue((outside / "precieux.txt").exists())

    def test_settings_corrompu_refuse_sans_ecrasement(self):
        CLAUDE_SETTINGS.write_text("{corrompu", encoding="utf-8")
        bak = CLAUDE_SETTINGS.with_suffix(".json.bak")
        bak.write_text('{"sain": true}', encoding="utf-8")
        with self.assertRaises(CorruptJsonError):
            uninstall_plugin("foo@mkt", remove_files=True)
        self.assertEqual(CLAUDE_SETTINGS.read_text(encoding="utf-8"), "{corrompu")
        self.assertEqual(bak.read_text(encoding="utf-8"), '{"sain": true}')
        self.assertTrue((PLUGINS / "cache" / "mkt" / "foo").exists())


if __name__ == "__main__":
    unittest.main()
