"""Lecture de l'abonnement Claude : priorités, normalisation, secrets, cache."""
from __future__ import annotations

import json
import os
import subprocess
import unittest
from unittest import mock

from _support import HOME, reset_sandbox, write_json_file

from dashcore import claude_account as ca
from dashcore.api_ui_state import patch_ui_state

CREDS = HOME / ".claude" / ".credentials.json"
CLAUDE_JSON = HOME / ".claude.json"


def _cli_result(data, code=0):
    return subprocess.CompletedProcess(["claude"], code, stdout=json.dumps(data), stderr="")


def _write_files(org="claude_max", tier="default_claude_max_5x", sub="pro"):
    write_json_file(CLAUDE_JSON, {"oauthAccount": {
        "organizationType": org, "organizationRateLimitTier": tier}})
    write_json_file(CREDS, {"claudeAiOauth": {
        "accessToken": "SECRET-x", "refreshToken": "SECRET-y",
        "subscriptionType": sub, "rateLimitTier": "default_claude_pro"}})


class ClaudeAccountTest(unittest.TestCase):
    def setUp(self):
        reset_sandbox()
        ca.clear_cache()
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("ANTHROPIC_API_KEY", None)
        self.now = [1000.0]
        patcher = mock.patch.object(ca, "_clock", lambda: self.now[0])
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(ca.clear_cache)

    def _run(self, **kw):
        return mock.patch("dashcore.claude_account.subprocess.run", **kw)

    def test_mapping_claude_json(self):
        _write_files()
        with self._run(side_effect=FileNotFoundError):
            info = ca.subscription_info()
        self.assertEqual((info["plan"], info["tier"], info["source"]), ("max", "max_5x", "claude_json"))

    def test_credentials_seuls_sans_fuite(self):
        _write_files()
        CLAUDE_JSON.unlink()
        with self._run(side_effect=FileNotFoundError):
            info = ca.subscription_info()
        self.assertEqual((info["plan"], info["source"]), ("pro", "credentials"))
        self.assertNotIn("SECRET", json.dumps(info))

    def test_cli_seule_source_sans_fuite(self):
        out = {"loggedIn": True, "authMethod": "claude.ai", "subscriptionType": "pro",
               "email": "a@b.c"}
        with self._run(return_value=_cli_result(out)) as m:
            info = ca.subscription_info()
        self.assertEqual((info["plan"], info["source"], info["auth_method"]), ("pro", "cli", "claude.ai"))
        args, kwargs = m.call_args
        self.assertIsInstance(args[0], list)
        self.assertFalse(kwargs.get("shell"))
        self.assertEqual(kwargs.get("timeout"), 10)
        self.assertFalse(info["conflict"])
        self.assertNotIn("SECRET", json.dumps(info))

    def test_claude_json_prime_sur_cli_et_credentials_perimes(self):
        _write_files()  # claude.json max 5x ; credentials pro
        out = {"loggedIn": True, "authMethod": "claude.ai", "subscriptionType": "pro"}
        with self._run(return_value=_cli_result(out)):
            info = ca.subscription_info()
        self.assertEqual((info["plan"], info["tier"], info["source"]), ("max", "max_5x", "claude_json"))
        # ~/.claude.json fait foi : désaccord visible dans sources_seen, sans alerte.
        self.assertFalse(info["conflict"])
        self.assertEqual(info["sources_seen"],
                         {"cli": "pro", "claude_json": "max", "credentials": "pro"})
        self.assertEqual(info["auth_method"], "claude.ai")
        self.assertNotIn("SECRET", json.dumps(info))

    def test_conflit_sans_claude_json(self):
        _write_files(sub="pro")
        CLAUDE_JSON.unlink()
        out = {"loggedIn": True, "authMethod": "claude.ai", "subscriptionType": "max"}
        with self._run(return_value=_cli_result(out)):
            info = ca.subscription_info()
        self.assertTrue(info["conflict"])
        self.assertEqual(info["sources_seen"], {"cli": "max", "credentials": "pro"})

    def test_cli_sans_plan_garde_auth_method(self):
        _write_files(sub="max")
        out = {"loggedIn": True, "authMethod": "claude.ai", "subscriptionType": None}
        with self._run(return_value=_cli_result(out)):
            info = ca.subscription_info()
        self.assertEqual((info["plan"], info["source"], info["auth_method"]), ("max", "claude_json", "claude.ai"))
        self.assertFalse(info["conflict"])

    def test_cle_api_cli_prioritaire_sur_claude_json(self):
        _write_files()
        out = {"loggedIn": True, "authMethod": "api_key", "subscriptionType": None}
        with self._run(return_value=_cli_result(out)):
            info = ca.subscription_info()
        self.assertEqual((info["plan"], info["source"]), ("api", "cli"))
        self.assertTrue(info["api_key_present"])

    def test_cli_echec_ou_absente_retombe_sur_fichiers(self):
        _write_files()
        for kw in ({"return_value": _cli_result({"loggedIn": False}, 1)},
                   {"side_effect": FileNotFoundError},
                   {"side_effect": subprocess.TimeoutExpired("claude", 10)},
                   {"return_value": subprocess.CompletedProcess(["claude"], 0, stdout="pas du json", stderr="")}):
            ca.clear_cache()
            with self._run(**kw):
                info = ca.subscription_info()
            self.assertEqual((info["plan"], info["source"]), ("max", "claude_json"))

    def test_manuel_prioritaire(self):
        _write_files()
        patch_ui_state({"claude_plan": "api"})
        out = {"loggedIn": True, "authMethod": "claude.ai", "subscriptionType": "pro"}
        with self._run(return_value=_cli_result(out)):
            info = ca.subscription_info()
        self.assertEqual((info["plan"], info["source"]), ("api", "manual"))
        patch_ui_state({"claude_plan": "auto"})
        with self._run(return_value=_cli_result(out)):
            self.assertEqual(ca.subscription_info()["source"], "claude_json")

    def test_reglage_invalide_refuse(self):
        status, _ = patch_ui_state({"claude_plan": "enterprise"})
        self.assertEqual(status, 400)

    def test_fichiers_absents_unknown(self):
        with self._run(side_effect=FileNotFoundError):
            info = ca.subscription_info()
        self.assertEqual((info["plan"], info["tier"], info["source"]), ("unknown", None, "none"))
        self.assertFalse(info["api_key_present"])

    def test_variantes_de_noms(self):
        for raw, plan in (("claude_pro", "pro"), ("pro", "pro"), ("team", "team"),
                          ("enterprise", "team"), ("claude_max", "max"), ("zzz", None)):
            self.assertEqual(ca._norm_plan(raw), plan, raw)

    def test_cle_api(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-SECRET-env"
        with self._run(side_effect=FileNotFoundError):
            info = ca.subscription_info()
        self.assertEqual(info["plan"], "api")
        self.assertTrue(info["api_key_present"])
        self.assertNotIn("SECRET", json.dumps(info))
        ca.clear_cache()
        out = {"loggedIn": True, "authMethod": "api_key", "subscriptionType": None}
        os.environ.pop("ANTHROPIC_API_KEY")
        with self._run(return_value=_cli_result(out)):
            info = ca.subscription_info()
        self.assertEqual(info["plan"], "api")

    def test_cache_cinq_minutes(self):
        out = {"loggedIn": True, "authMethod": "claude.ai", "subscriptionType": "pro"}
        with self._run(return_value=_cli_result(out)) as m:
            ca.subscription_info()
            self.now[0] += 299
            ca.subscription_info()
            self.assertEqual(m.call_count, 1)
            self.now[0] += 2
            ca.subscription_info()
            self.assertEqual(m.call_count, 2)


class ConsumptionWarningsTests(unittest.TestCase):
    def _codes(self, plan, agents=(), **kw):
        return [w["code"] for w in ca.consumption_warnings(plan, list(agents), **kw)]

    def test_pro_opus(self):
        w = ca.consumption_warnings("pro", [
            {"id": "a", "model": "opus", "effort": None},
            {"id": "b", "model": "sonnet", "effort": None}])
        self.assertEqual([x["code"] for x in w], ["pro_opus"])
        self.assertEqual(w[0]["level"], "alert")
        self.assertEqual(w[0]["agents"], ["a"])

    def test_pro_effort_eleve(self):
        for e in ("high", "xhigh", "max"):
            w = ca.consumption_warnings("pro", [{"id": "a", "model": "sonnet", "effort": e}])
            self.assertEqual([x["code"] for x in w], ["pro_effort"])
            self.assertEqual(w[0]["level"], "alert")

    def test_pro_sonnet_medium_rien(self):
        self.assertEqual(self._codes("pro", [{"id": "a", "model": "sonnet", "effort": None}]), [])
        self.assertEqual(self._codes("pro", [{"id": "a", "model": "sonnet", "effort": "medium"}]), [])

    def test_max_opus_xhigh_info(self):
        w = ca.consumption_warnings("max", [{"id": "a", "model": "opus", "effort": "xhigh"}])
        self.assertEqual([x["code"] for x in w], ["max_opus_effort"])
        self.assertEqual(w[0]["level"], "info")
        self.assertIn("partagé", w[0]["message"])

    def test_max_opus_medium_rien(self):
        self.assertEqual(self._codes("max", [{"id": "a", "model": "opus", "effort": None}]), [])

    def test_api_unknown_conflict(self):
        self.assertEqual(self._codes("api"), ["api"])
        self.assertEqual(self._codes("unknown"), ["unknown"])
        self.assertEqual(self._codes("max", conflict=True), ["conflict"])

    def test_aucun_avertissement(self):
        self.assertEqual(self._codes("max"), [])
        self.assertEqual(self._codes("team", [{"id": "a", "model": "opus", "effort": "max"}]), [])
        self.assertEqual(self._codes("pro"), [])


if __name__ == "__main__":
    unittest.main()
