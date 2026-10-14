"""Verdict mémorisé de « Diagnostiquer » (dashcore/mcp_probe.py) : persistance,
signature de config, fenêtre de fraîcheur, branchement dans api_mcps."""
from __future__ import annotations

import json
import unittest

from _support import reset_sandbox, write_json_file
from dashcore import api_mcps, config, data_migration, mcp_probe

NOW = 1_800_000_000


def _mcp(**kw):
    m = {"id": "srv", "name": "Serveur", "transport": "stdio", "command": "npx",
         "args": ["-y", "@x/srv"], "env": {"TOKEN": "${TOKEN}"}, "workspaces": ["a"]}
    m.update(kw)
    return m


class SignatureTests(unittest.TestCase):
    def test_champs_non_techniques_sans_effet(self):
        base = mcp_probe.mcp_signature(_mcp())
        for k, v in (("name", "Autre"), ("description", "texte"), ("workspaces", ["b"]),
                     ("status", "désactivé"), ("notes", "n")):
            with self.subTest(champ=k):
                self.assertEqual(mcp_probe.mcp_signature(_mcp(**{k: v})), base)

    def test_champs_techniques_changent_la_signature(self):
        base = mcp_probe.mcp_signature(_mcp())
        for k, v in (("command", "uvx"), ("args", ["-y", "@x/srv2"]), ("env", {"TOKEN": "x"}),
                     ("cwd", "C:/x"), ("url", "http://h/mcp"), ("headers", {"A": "1"}),
                     ("transport", "http")):
            with self.subTest(champ=k):
                self.assertNotEqual(mcp_probe.mcp_signature(_mcp(**{k: v})), base)

    def test_normalisation_aller_retour_edition(self):
        # Vide / absent / espaces : même signature (le formulaire renvoie des "" et des []).
        a = _mcp(cwd="", headers={}, url="")
        b = _mcp(command=" npx ")
        b.pop("url", None)
        self.assertEqual(mcp_probe.mcp_signature(a), mcp_probe.mcp_signature(b))
        self.assertEqual(mcp_probe.mcp_signature({"id": "x"}), mcp_probe.mcp_signature({"id": "x", "transport": "stdio"}))


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        reset_sandbox()
        mcp_probe.probe_state_path().unlink(missing_ok=True)

    def test_fichier_dans_le_dossier_de_donnees(self):
        self.assertEqual(mcp_probe.probe_state_path().parent, config.DATA_DIR)
        self.assertIn(mcp_probe.PROBE_STATE_NAME, data_migration.MIGRATABLE_FILES)

    def test_ecriture_relecture(self):
        e = mcp_probe.record_probe(_mcp(), "ok", now=NOW)
        self.assertEqual(e["verdict"], "ok")
        self.assertEqual(mcp_probe.read_probe_entries(), {"srv": e})
        # Atomique : pas de .tmp résiduel.
        self.assertFalse(mcp_probe.probe_state_path().with_suffix(".json.tmp").exists())

    def test_verdict_inconnu_refuse(self):
        with self.assertRaises(ValueError):
            mcp_probe.record_probe(_mcp(), "vert", now=NOW)
        self.assertFalse(mcp_probe.probe_state_path().exists())

    def test_elagage_des_mcps_disparus(self):
        mcp_probe.record_probe(_mcp(id="vieux"), "ok", now=NOW)
        mcp_probe.record_probe(_mcp(id="autre"), "err", now=NOW)
        mcp_probe.record_probe(_mcp(), "ok", known_ids=["srv", "autre"], now=NOW)
        self.assertEqual(sorted(mcp_probe.read_probe_entries()), ["autre", "srv"])

    def test_fichier_corrompu_repris_de_zero(self):
        path = mcp_probe.probe_state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{pas du json", encoding="utf-8")
        self.assertEqual(mcp_probe.read_probe_entries(), {})
        mcp_probe.record_probe(_mcp(), "warn", now=NOW)
        self.assertEqual(mcp_probe.read_probe_entries()["srv"]["verdict"], "warn")
        self.assertTrue(list(path.parent.glob(path.name + ".corrupt-*")))

    def test_entrees_invalides_ignorees(self):
        write_json_file(mcp_probe.probe_state_path(), {"mcps": {
            "a": {"verdict": "ok", "at": NOW, "sig": "x"}, "b": {"verdict": "vert", "at": NOW, "sig": "x"},
            "c": {"verdict": "ok", "at": "hier", "sig": "x"}, "d": "ok"}})
        self.assertEqual(list(mcp_probe.read_probe_entries()), ["a"])


class SummaryTests(unittest.TestCase):
    def _entry(self, verdict="ok", age=3600, mcp=None):
        return {"verdict": verdict, "at": NOW - age, "sig": mcp_probe.mcp_signature(mcp or _mcp())}

    def test_etats(self):
        s = mcp_probe.probe_summary
        self.assertIsNone(s(_mcp(), None, now=NOW))
        for v in ("ok", "warn", "err"):
            self.assertEqual(s(_mcp(), self._entry(v), now=NOW)["state"], v)
        self.assertEqual(s(_mcp(command="uvx"), self._entry(), now=NOW)["state"], "changed")
        self.assertEqual(s(_mcp(), self._entry(age=mcp_probe.PROBE_FRESH_S + 1), now=NOW)["state"], "expired")
        self.assertEqual(s(_mcp(), self._entry(age=mcp_probe.PROBE_FRESH_S - 1), now=NOW)["state"], "ok")
        # Horodatage dans le futur (horloge corrigée) : expiré, pas « vérifié ».
        self.assertEqual(s(_mcp(), self._entry(age=-3600), now=NOW)["state"], "expired")
        out = s(_mcp(), self._entry("err"), now=NOW)
        self.assertEqual((out["verdict"], out["at"], out["fresh_days"]), ("err", NOW - 3600, mcp_probe.PROBE_FRESH_DAYS))


class ApiIntegrationTests(unittest.TestCase):
    def setUp(self):
        reset_sandbox()
        mcp_probe.probe_state_path().unlink(missing_ok=True)

    def _registry(self, mcps):
        write_json_file(config.MCP_REGISTRY, {"version": "1.0", "mcps": mcps})

    def test_diagnostic_memorise_le_verdict(self):
        # Commande vide : verdict « err » sans lancer de process.
        self._registry([_mcp(command="", env={})])
        status, out = api_mcps.diagnose_mcp("srv")
        self.assertEqual(status, 200)
        self.assertEqual(out["verdict"], "err")
        self.assertEqual(out["last_probe"]["state"], "err")
        self.assertEqual(mcp_probe.read_probe_entries()["srv"]["verdict"], "err")

    def test_diagnostic_echoue_rien_memorise(self):
        self._registry([])
        self.assertEqual(api_mcps.diagnose_mcp("srv")[0], 404)
        self.assertFalse(mcp_probe.probe_state_path().exists())

    def test_liste_expose_last_probe_sans_le_persister(self):
        m = _mcp(command="", env={})
        self._registry([m, _mcp(id="jamais")])
        mcp_probe.record_probe(m, "ok")
        mcps = {x["id"]: x for x in api_mcps.list_mcps_with_computed_status()["mcps"]}
        self.assertEqual(mcps["srv"]["last_probe"]["state"], "ok")
        self.assertNotIn("last_probe", mcps["jamais"])
        on_disk = json.loads(config.MCP_REGISTRY.read_text(encoding="utf-8"))
        self.assertNotIn("last_probe", on_disk["mcps"][0])
        clean, err = api_mcps.clean_mcp_payload(dict(mcps["srv"], status="disponible"))
        self.assertIsNone(err)
        self.assertNotIn("last_probe", clean)


if __name__ == "__main__":
    unittest.main()
