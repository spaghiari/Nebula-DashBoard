"""claude_runner : ligne de commande headless, lecture du flux stream-json,
délai, annulation, quota, délégation, refus, agents chargés (faux binaire
tests/fake_claude.py, aucun appel réel à `claude`)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from _support import DASHBOARD_DIR, SANDBOX, rmtree
from dashcore import claude_runner as cr
from dashcore.config import IMPROVE_FORBIDDEN_ARGS

FAKE = DASHBOARD_DIR / "tests" / "fake_claude.py"
TOOLS = ("Agent", "Read", "Grep", "Glob")


class FakeClaudeMixin:
    """Bac à sable d'un appel : dossier de travail avec deux agents `p-*`,
    script du faux binaire, journal des appels."""

    def setUp(self):
        self.dir = Path(SANDBOX / "runner" / self.id().rsplit(".", 1)[-1])
        rmtree(self.dir)
        (self.dir / ".claude" / "agents").mkdir(parents=True, exist_ok=True)
        for name in ("p-researcher", "p-evaluator"):
            (self.dir / ".claude" / "agents" / f"{name}.md").write_text("x", encoding="utf-8")
        self.script = self.dir / "script.json"
        self.calls_log = self.dir / "calls.jsonl"
        if self.calls_log.exists():
            self.calls_log.unlink()
        env = mock.patch.dict(os.environ, {"FAKE_CLAUDE_SCRIPT": str(self.script)})
        env.start()
        self.addCleanup(env.stop)

    def rules(self, *rules):
        self.script.write_text(json.dumps({"log": str(self.calls_log), "rules": list(rules)}),
                               encoding="utf-8")

    def run_fake(self, prompt="subagent_type: p-researcher\nQuestion ?", **kw):
        kw.setdefault("allowed_tools", TOOLS)
        kw.setdefault("max_budget_usd", 1.0)
        kw.setdefault("expect_agent", "p-researcher")
        kw.setdefault("agents_prefix", "p")
        return cr.run_claude(prompt, self.dir, cmd=str(FAKE), **kw)

    def calls(self) -> list[dict]:
        return [json.loads(x) for x in self.calls_log.read_text(encoding="utf-8").splitlines()]


class BuildArgsTests(unittest.TestCase):
    def test_options_communes_sans_argument_interdit(self):
        args = cr.build_args(TOOLS, max_budget_usd=0.5)
        joined = " ".join(args).lower()
        for bad in IMPROVE_FORBIDDEN_ARGS:
            self.assertNotIn(bad.lower(), joined)
        for opt in ("-p", "--verbose", "--permission-prompts"):
            self.assertIn(opt, args)
        self.assertEqual(args[args.index("--output-format") + 1], "stream-json")
        self.assertEqual(args[args.index("--permission-mode") + 1], "dontAsk")
        self.assertEqual(args[args.index("--max-budget-usd") + 1], "0.50")
        # Variadique en dernier : rien après les outils (prompt sur stdin).
        self.assertEqual(args[-len(TOOLS):], list(TOOLS))
        dis = args.index("--disallowedTools")
        self.assertIn("Bash", args[dis + 1:args.index("--allowedTools")])

    def test_argument_interdit_refuse(self):
        for bad in ("--bare", "--dangerously-skip-permissions", "bypassPermissions"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                cr.build_args(["Agent", bad], max_budget_usd=1)

    def test_outil_autorise_et_retire_refuse(self):
        with self.assertRaises(ValueError):
            cr.build_args(["Agent", "Bash(ls)"], max_budget_usd=1)

    def test_commande_python_lancee_avec_l_interpreteur(self):
        cmd = cr.claude_command("C:/x/fake.py")
        self.assertEqual(cmd[0], sys.executable)
        self.assertEqual(cmd[1], "C:/x/fake.py")
        with mock.patch.object(cr.config, "NEBULA_CLAUDE_CMD", None), \
             mock.patch.object(cr.shutil, "which", return_value=None):
            with self.assertRaises(cr.ClaudeNotFound):
                cr.claude_command()

    def test_parse_reset(self):
        from datetime import datetime
        now = datetime(2026, 10, 17, 10, 0, 0)  # samedi
        cases = {
            "3:45pm": "2026-10-17T15:45:00",       # plus tard aujourd'hui
            "9:30am": "2026-10-18T09:30:00",       # déjà passée : demain
            "11pm": "2026-10-17T23:00:00",
            "12am": "2026-10-18T00:00:00",
            "3:45 p.m.": "2026-10-17T15:45:00",
            "15:45": "2026-10-17T15:45:00",
            "Mon 12:00am": "2026-10-19T00:00:00",
            "Saturday 9am": "2026-10-24T09:00:00",  # même jour, heure passée
            "Sat 3pm": "2026-10-17T15:00:00",
            "13:00pm": None, "15": None, "25:00": None, "bientôt": None, "": None, None: None,
        }
        for text, want in cases.items():
            self.assertEqual(cr.parse_reset(text, now), want, text)
        self.assertEqual(cr.detect_quota("session limit · resets Mon 12:00am"),
                         (True, "Mon 12:00am"))

    def test_detection_du_quota(self):
        self.assertEqual(cr.detect_quota("You've hit your session limit · resets 3:45pm"),
                         (True, "3:45pm"))
        self.assertEqual(cr.detect_quota("You've hit your weekly limit"), (True, None))
        self.assertEqual(cr.detect_quota("Opus limit reached · resets 11pm"), (True, "11pm"))
        self.assertEqual(cr.detect_quota("tout va bien", ""), (False, None))


class RunClaudeTests(FakeClaudeMixin, unittest.TestCase):
    def test_reussite(self):
        self.rules({"output": "## Conclusions\n- Évaluation ✓ [CLAUDE.md]"})
        r = self.run_fake()
        self.assertEqual(r.status, "ok", r.error)
        self.assertEqual(r.agent_output, "## Conclusions\n- Évaluation ✓ [CLAUDE.md]")
        self.assertEqual(r.delegated_to, ["p-researcher"])
        self.assertEqual((r.cost_usd, r.cost_known, r.num_turns, r.duration_ms), (0.12, True, 2, 1500))
        self.assertEqual(r.tokens, {"input": 10, "output": 20, "cache_read": 300, "cache_creation": 40})
        self.assertIn("claude-sonnet-5-5", r.model_usage)
        self.assertEqual(r.refusals, 0)
        call = self.calls()[0]
        # Prompt sur stdin, jamais dans la ligne de commande.
        self.assertEqual(call["stdin"], "subagent_type: p-researcher\nQuestion ?")
        self.assertNotIn("Question ?", " ".join(call["argv"]))
        for bad in IMPROVE_FORBIDDEN_ARGS:
            self.assertNotIn(bad.lower(), " ".join(call["argv"]).lower())
        self.assertEqual(Path(call["cwd"]).resolve(), self.dir.resolve())

    def test_journal_brut_du_flux(self):
        self.rules({"output": "ok"})
        log_path = self.dir / "logs" / "call.jsonl"
        self.run_fake(log_path=log_path)
        types = [json.loads(x)["type"] for x in log_path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(types[0], "system")
        self.assertEqual(types[-1], "result")

    def test_on_spawn_recoit_le_popen(self):
        self.rules({"output": "ok"})
        seen = []
        r = self.run_fake(on_spawn=seen.append)
        self.assertEqual(r.status, "ok", r.error)
        self.assertEqual(len(seen), 1)
        self.assertIsInstance(seen[0], subprocess.Popen)
        self.assertIsNotNone(seen[0].returncode)
        # PID réel du faux binaire : celui consigné n'est pas exposé, mais le Popen est celui de l'enfant.
        self.assertGreater(seen[0].pid, 0)
        self.assertNotEqual(seen[0].pid, os.getpid())

    def test_on_spawn_pid_vivant_pendant_appel(self):
        self.rules({"output": "ok", "sleep": 1.5})
        box = {}

        def cb(proc):
            box["pid"] = proc.pid
            box["alive"] = proc.poll() is None

        self.run_fake(on_spawn=cb)
        self.assertTrue(box["alive"])

    def test_on_spawn_exception_n_interrompt_pas(self):
        self.rules({"output": "ok"})

        def boom(proc):
            raise RuntimeError("rappel cassé")

        with self.assertLogs("dashboard", level="WARNING"):
            r = self.run_fake(on_spawn=boom)
        self.assertEqual(r.status, "ok", r.error)
        self.assertEqual(r.agent_output, "ok")

    def test_journal_brut_lisible_avant_la_fin(self):
        self.rules({"output": "ok", "sleep": 4})
        log_path = self.dir / "logs" / "live.jsonl"
        box = {}
        t = threading.Thread(target=lambda: box.update(r=self.run_fake(log_path=log_path)))
        t.start()
        try:
            deadline = time.monotonic() + 3
            lines = []
            while time.monotonic() < deadline and not lines:
                time.sleep(0.05)
                if log_path.exists():
                    lines = log_path.read_text(encoding="utf-8").splitlines()
            self.assertTrue(t.is_alive(), "l'appel devait encore être en cours")
            self.assertTrue(lines, "aucune ligne dans le journal avant la fin de l'appel")
            self.assertEqual(json.loads(lines[0])["type"], "system")
        finally:
            t.join(timeout=30)
        self.assertEqual(box["r"].status, "ok")

    def test_error_max_turns(self):
        self.rules({"output": "partiel", "result": {"subtype": "error_max_turns", "is_error": True}})
        r = self.run_fake()
        self.assertEqual((r.status, r.subtype), ("error", "error_max_turns"))
        # La sortie de l'agent reste lisible : l'appelant décide d'en tenir compte.
        self.assertEqual(r.agent_output, "partiel")

    def test_timeout_tue_l_arbre(self):
        self.rules({"output": "x", "sleep": 30})
        t0 = time.monotonic()
        r = self.run_fake(timeout=2)
        self.assertLess(time.monotonic() - t0, 20)
        self.assertEqual(r.status, "timeout")
        self.assertFalse(r.cost_known)

    def test_annulation_par_drapeau(self):
        self.rules({"output": "x", "sleep": 30})
        cancel = threading.Event()
        threading.Timer(1.0, cancel.set).start()
        t0 = time.monotonic()
        r = self.run_fake(cancel=cancel)
        self.assertEqual(r.status, "cancelled")
        self.assertLess(time.monotonic() - t0, 20)

    def test_quota_avec_heure(self):
        self.rules({"no_delegation": True,
                    "final_text": "You've hit your session limit · resets 3:45pm",
                    "result": {"is_error": True, "subtype": "success"}})
        r = self.run_fake()
        self.assertEqual(r.status, "quota")
        self.assertEqual(r.quota_reset, cr.parse_reset("3:45pm"))
        self.assertRegex(r.quota_reset, r"^\d{4}-\d\d-\d\dT15:45:00$")

    def test_quota_sans_heure_et_rate_limit(self):
        self.rules({"no_delegation": True, "final_text": "weekly limit reached",
                    "result": {"is_error": True}})
        r = self.run_fake()
        self.assertEqual((r.status, r.quota_reset), ("quota", None))
        self.rules({"no_delegation": True, "api_retry": 3, "no_result": True, "exit": 1})
        self.assertEqual(self.run_fake().status, "quota")

    def test_delegation_absente(self):
        self.rules({"no_delegation": True})
        r = self.run_fake()
        self.assertEqual(r.status, "delegation_missing")
        # Délégation vers un autre agent que celui attendu : même verdict.
        self.rules({"agent": "p-evaluator", "output": "x"})
        r = self.run_fake()
        self.assertEqual(r.status, "delegation_missing")
        self.assertIsNone(r.agent_output)
        self.assertIn("p-evaluator", r.error)

    def test_arriere_plan_enfants_directs(self):
        self.rules({"background": "children", "output": "Réponse finale",
                    "summary": "[harness: x neutralized]\nautre"})
        r = self.run_fake()
        self.assertEqual(r.status, "ok", r.error)
        self.assertEqual(r.agent_output, "Réponse finale")

    def test_arriere_plan_notification_seule_prefixe_retire(self):
        self.rules({"background": "notif_only",
                    "summary": "[harness: contenu neutralized]\nRéponse du résumé"})
        r = self.run_fake()
        self.assertEqual(r.status, "ok", r.error)
        self.assertEqual(r.agent_output, "Réponse du résumé")
        self.rules({"background": "notif_only", "summary": "Sans préfixe"})
        self.assertEqual(self.run_fake().agent_output, "Sans préfixe")

    def test_arriere_plan_imbrique_enfants_directs_seulement(self):
        self.rules({"background": "nested", "output": "Réponse directe"})
        r = self.run_fake()
        self.assertEqual(r.status, "ok", r.error)
        self.assertEqual(r.agent_output, "Réponse directe")
        self.assertEqual(r.delegated_to, ["p-researcher"])

    def test_arriere_plan_jamais_termine(self):
        self.rules({"background": "never"})
        r = self.run_fake()
        self.assertEqual(r.status, "delegation_missing")
        self.assertIsNone(r.agent_output)
        self.assertIn("arrière-plan", r.error)

    def test_arriere_plan_notification_failed(self):
        self.rules({"background": "failed", "output": "x"})
        r = self.run_fake()
        self.assertEqual(r.status, "error")
        self.assertIn("failed", r.error)
        self.assertIsNone(r.agent_output)

    def test_premier_plan_inchange_si_pas_de_lancement_async(self):
        self.rules({"output": "Texte normal"})
        r = self.run_fake()
        self.assertEqual((r.status, r.agent_output), ("ok", "Texte normal"))

    def test_cout_sur_plusieurs_result(self):
        self.rules({"output": "ok", "result_costs": [0.05, 0.12, 0.12]})
        r = self.run_fake()
        self.assertEqual(r.cost_usd, 0.12)
        self.rules({"output": "ok", "result_costs": [0.30, 0.10]})
        self.assertEqual(self.run_fake().cost_usd, 0.30)

    def test_refus_comptes(self):
        self.rules({"output": "x", "denials": 2, "tool_errors": 1})
        r = self.run_fake()
        self.assertEqual((r.permission_denials, r.tool_errors, r.refusals), (2, 1, 3))

    def test_agents_absents_de_init(self):
        for agents in ([], ["autre-researcher"], "absent"):
            with self.subTest(agents=agents):
                self.rules({"output": "x", "agents": agents, "sleep": 30})
                t0 = time.monotonic()
                r = self.run_fake()
                self.assertEqual(r.status, "agents_missing")
                self.assertIn("agent", r.error)
                # Appel interrompu dès system/init, sans attendre la fin.
                self.assertLess(time.monotonic() - t0, 20)

    def test_flux_sans_result(self):
        self.rules({"output": "x", "no_result": True, "exit": 3, "stderr": "boum"})
        r = self.run_fake()
        self.assertEqual(r.status, "error")
        self.assertEqual(r.exit_code, 3)
        self.assertIn("boum", r.error)

    def test_binaire_introuvable(self):
        r = cr.run_claude("x", self.dir, allowed_tools=TOOLS, max_budget_usd=1,
                          cmd=str(self.dir / "absent.exe"))
        self.assertEqual(r.status, "spawn_error")


if __name__ == "__main__":
    unittest.main()
