"""Routes HTTP de la boucle d'amélioration automatique (Nebula 2.6.0).

Deux bancs :
- `ServeurIsoleTests` : `server.py` réel en sous-process (bac à sable dédié,
  `NEBULA_DISABLE_SCHEDULER=1`, `NEBULA_CLAUDE_CMD` vers le faux binaire) :
  démarrage, garde CSRF, 400 / 404.
- `RoutesJobTests` : serveur HTTP réel lancé dans un thread du process de
  test, pour simuler le moteur par `mock` (aucun appel réel à `claude`) :
  lancement, 409, arrêt, mode automatique, enrichissement, abonnement.
"""
from __future__ import annotations

import http.client
import json
import os
import threading
import time
import unittest
from unittest import mock

from _support import (DASHBOARD_DIR, HOME, SANDBOX, ServerProcess, make_workspace,
                      reset_sandbox, rmtree, write_json_file)

os.environ["NEBULA_DISABLE_SCHEDULER"] = "1"

from dashcore import api_team, claude_account  # noqa: E402
from dashcore import improve_engine as ie  # noqa: E402
from dashcore import improve_jobs as ij  # noqa: E402

import server  # noqa: E402

FAKE = DASHBOARD_DIR / "tests" / "fake_claude.py"
XHR = {"X-Nebula-XHR": "1"}
MANIFEST = {"team": {"name": "t", "prefix": "ws1"},
            "agents": [{"id": "executor", "role": "Exécutant", "model": "opus", "effort": "high"},
                       {"id": "researcher", "role": "Chercheur", "model": "sonnet"}]}
POSTS = ("run", "abandon", "stop", "auto")


def request(port, method, path, *, headers=None, body=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
    try:
        hdrs = dict(headers or {})
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            hdrs["Content-Type"] = "application/json"
        elif method == "POST":
            data = b""
        conn.request(method, path, body=data, headers=hdrs)
        resp = conn.getresponse()
        raw = resp.read()
        return resp.status, raw
    finally:
        conn.close()


def activate(ws_dir, cases=1):
    write_json_file(ws_dir / ".claude" / "team.json", MANIFEST)
    lines = [json.dumps({"id": f"c{i}", "agent": "executor", "grader": "exact",
                         "input": "x", "expected": "y"}) for i in range(cases)]
    p = ws_dir / ".claude" / "evals" / "eval-set.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def wait_idle(timeout=20.0):
    end = time.monotonic() + timeout
    while ij.is_running() and time.monotonic() < end:
        time.sleep(0.05)
    if ij.is_running():
        raise AssertionError("job toujours en cours")


class ServeurIsoleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = SANDBOX / "http-improve"
        rmtree(cls.base)
        cls.srv = ServerProcess(cls.base, extra_env={"NEBULA_DISABLE_SCHEDULER": "1",
                                                     "NEBULA_CLAUDE_CMD": str(FAKE)})
        cls.srv.start()
        cls.port = cls.srv.port
        cls.ws = cls.srv.root / "workspaces" / "ws1"

    @classmethod
    def tearDownClass(cls):
        cls.srv.stop()
        rmtree(cls.base)

    def req(self, *a, **kw):
        return request(self.port, *a, **kw)

    def test_demarrage_reprise_sans_planificateur(self):
        log = self.srv.log_text()
        self.assertIn("NEBULA_DISABLE_SCHEDULER=1", log)
        self.assertNotIn("Traceback", log)

    def test_post_sans_xhr_403(self):
        for name in POSTS:
            with self.subTest(route=name):
                st, _ = self.req("POST", f"/api/workspaces/ws1/improvement/{name}",
                                 body={"kind": "iteration"})
                self.assertEqual(st, 403)

    def test_module_inactif_404_et_id_invalide_400(self):
        for name in POSTS:
            with self.subTest(route=name):
                st, raw = self.req("POST", f"/api/workspaces/ws1/improvement/{name}",
                                   body={"kind": "iteration"}, headers=XHR)
                self.assertEqual(st, 404, raw)
                self.assertIn("inactif", json.loads(raw)["error"])
                st, _ = self.req("POST", f"/api/workspaces/absent/improvement/{name}",
                                 body={"kind": "iteration"}, headers=XHR)
                self.assertEqual(st, 404)
                st, _ = self.req("POST", f"/api/workspaces/{'a' * 200}/improvement/{name}",
                                 body={"kind": "iteration"}, headers=XHR)
                self.assertEqual(st, 400)
        self.assertEqual(self.req("GET", f"/api/workspaces/{'a' * 200}/improvement/job")[0], 400)
        self.assertEqual(self.req("GET", "/api/workspaces/absent/improvement/job")[0], 404)

    def test_kind_invalide_400_et_get_enrichi(self):
        activate(self.ws)
        try:
            for body in ({"kind": "abandon"}, {"kind": "bidule"}, {}):
                with self.subTest(body=body):
                    st, raw = self.req("POST", "/api/workspaces/ws1/improvement/run",
                                       body=body, headers=XHR)
                    self.assertEqual(st, 400, raw)
                    self.assertNotIn("Traceback", raw.decode("utf-8"))
            st, raw = self.req("POST", "/api/workspaces/ws1/improvement/auto",
                               body={"daily_budget": 11}, headers=XHR)
            self.assertEqual(st, 400, raw)
            st, raw = self.req("GET", "/api/workspaces/ws1/improvement")
            self.assertEqual(st, 200, raw)
            p = json.loads(raw)
            self.assertTrue(p["active"])
            self.assertIn("registers", p)          # champs existants conservés
            self.assertIsNone(p["job"])
            self.assertFalse(p["auto"]["enabled"])
            self.assertEqual(p["next_step"]["state"], "no_baseline")
            st, raw = self.req("GET", "/api/workspaces/ws1/improvement/job")
            self.assertEqual(st, 200, raw)
            p = json.loads(raw)
            self.assertEqual(set(p), {"job", "history", "auto", "next_step"})
            self.assertEqual(p["history"], [])
        finally:
            rmtree(self.ws / ".claude" / "evals")
            (self.ws / ".claude" / "team.json").unlink()


class RoutesJobTests(unittest.TestCase):
    """Serveur HTTP réel dans un thread : le moteur est simulé par mock."""

    @classmethod
    def setUpClass(cls):
        cls.httpd = server._NebulaHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.httpd.nebula_host = "127.0.0.1"
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def setUp(self):
        wait_idle()
        reset_sandbox()
        self.ws = make_workspace("ws1")
        activate(self.ws)
        claude_account.clear_cache()
        self.gate = threading.Event()

    def tearDown(self):
        self.gate.set()
        ij.cancel_job("ws1")
        wait_idle()

    def req(self, *a, **kw):
        return request(self.port, *a, **kw)

    def _blocking_engine(self, ctx):
        # Attend la fin du test ou l'annulation (drapeau du job).
        while not self.gate.is_set():
            if ctx.cancel.is_set():
                raise ie.Cancelled("annulé")
            time.sleep(0.02)
        return {"candidate": None, "verdict": {"status": "accepted", "iteration": 1}}

    def _start_blocking(self):
        st, raw = self.req("POST", "/api/workspaces/ws1/improvement/run",
                           body={"kind": "iteration"}, headers=XHR)
        self.assertEqual(st, 202, raw)
        return json.loads(raw)

    def test_lancement_202_puis_409_et_agents_config_409(self):
        with mock.patch.object(ie, "run_iteration", side_effect=self._blocking_engine):
            p = self._start_blocking()
            self.assertEqual((p["job"]["kind"], p["job"]["status"]), ("iteration", "running"))
            st, raw = self.req("POST", "/api/workspaces/ws1/improvement/run",
                               body={"kind": "measure"}, headers=XHR)
            self.assertEqual(st, 409)
            self.assertEqual(json.loads(raw)["reason"], "running")
            # Réglages modèle / effort refusés pendant le job, rien d'écrit.
            before = (self.ws / ".claude" / "team.json").read_bytes()
            st, raw = self.req("POST", "/api/workspaces/ws1/team/agents-config",
                               body={"agents": {"executor": {"model": "sonnet"}}}, headers=XHR)
            self.assertEqual(st, 409, raw)
            self.assertEqual(json.loads(raw)["reason"], "job_running")
            self.assertEqual((self.ws / ".claude" / "team.json").read_bytes(), before)
            # Vue enrichie : job en cours => next_step job_running.
            st, raw = self.req("GET", "/api/workspaces/ws1/improvement")
            p = json.loads(raw)
            self.assertEqual(p["job"]["status"], "running")
            self.assertEqual(p["next_step"]["state"], "job_running")
            self.assertIn("enabled", p["auto"])
            self.gate.set()
            wait_idle()
        st, raw = self.req("GET", "/api/workspaces/ws1/improvement/job")
        p = json.loads(raw)
        self.assertEqual(p["job"]["status"], "succeeded")
        self.assertEqual(len(p["history"]), 1)
        self.assertNotEqual(p["next_step"]["state"], "job_running")

    def test_plafond_de_cout_du_jour_409_meme_force(self):
        full = server_config_day()
        with mock.patch.object(ij, "spent_today", return_value=full),              mock.patch.object(ij, "start_job",
                               return_value=(202, {"ok": True, "job": {}})) as sj:
            st, raw = self.req("POST", "/api/workspaces/ws1/improvement/run",
                               body={"kind": "iteration"}, headers=XHR)
            self.assertEqual(st, 409, raw)
            p = json.loads(raw)
            self.assertEqual(p["reason"], "daily_budget")
            self.assertIn("plafond de coût du jour atteint", p["error"])
            sj.assert_not_called()
            # Forcer la garde de session ne lève jamais le plafond du jour.
            for key in ("force", "force_session"):
                st, _ = self.req("POST", "/api/workspaces/ws1/improvement/run",
                                 body={"kind": "iteration", key: True}, headers=XHR)
                self.assertEqual(st, 409)
            sj.assert_not_called()

    def test_plafond_par_iteration_transmis(self):
        with mock.patch.object(ij, "start_job", return_value=(202, {"ok": True, "job": {}})) as sj:
            st, _ = self.req("POST", "/api/workspaces/ws1/improvement/run",
                             body={"kind": "resolve", "force": True}, headers=XHR)
        self.assertEqual(st, 202)
        args, kwargs = sj.call_args
        self.assertEqual(args[0], "ws1")
        self.assertEqual(args[2], "resolve")
        self.assertEqual(kwargs, {"max_usd": server_config_max(), "force": True,
                                  "exclude_session_ids": ()})

    def test_sessions_des_jobs_recents_transmises_run_et_abandon(self):
        from dashcore import improve_scheduler as sch
        with mock.patch.object(sch, "recent_job_session_ids", return_value=("s1", "s2")),                 mock.patch.object(ij, "start_job", return_value=(202, {"ok": True, "job": {}})) as sj:
            for path, body in (("run", {"kind": "iteration"}), ("abandon", {})):
                st, raw = self.req("POST", f"/api/workspaces/ws1/improvement/{path}",
                                   body=body, headers=XHR)
                self.assertEqual(st, 202, raw)
                self.assertEqual(sj.call_args.kwargs["exclude_session_ids"], ("s1", "s2"))

    def test_plafond_borne_par_reste_du_jour_meme_force(self):
        reste = 1.25
        with mock.patch.object(ij, "spent_today", return_value=server_config_day() - reste),                 mock.patch.object(ij, "start_job", return_value=(202, {"ok": True, "job": {}})) as sj:
            self.req("POST", "/api/workspaces/ws1/improvement/run",
                     body={"kind": "iteration"}, headers=XHR)
            self.assertEqual(sj.call_args.kwargs["max_usd"], reste)
            self.req("POST", "/api/workspaces/ws1/improvement/run",
                     body={"kind": "iteration", "force_session": True}, headers=XHR)
            self.assertEqual(sj.call_args.kwargs["max_usd"], reste)
            self.assertIs(sj.call_args.kwargs["force"], True)

    def test_stop_annule_et_desactive_auto(self):
        st, raw = self.req("POST", "/api/workspaces/ws1/improvement/auto",
                           body={"enabled": True, "daily_budget": 2}, headers=XHR)
        self.assertEqual(st, 200, raw)
        st, raw = self.req("GET", "/api/workspaces/ws1/improvement/job")
        self.assertTrue(json.loads(raw)["auto"]["enabled"])
        with mock.patch.object(ie, "run_iteration", side_effect=self._blocking_engine):
            self._start_blocking()
            st, raw = self.req("POST", "/api/workspaces/ws1/improvement/stop", headers=XHR)
            self.assertEqual(st, 200, raw)
            p = json.loads(raw)
            self.assertTrue(p["cancelled"])
            self.assertFalse(p["auto"]["enabled"])
            wait_idle()
        self.assertEqual(ij.get_job("ws1")["status"], "cancelled")
        # Rien ne tourne : 200, cancelled false.
        st, raw = self.req("POST", "/api/workspaces/ws1/improvement/stop", headers=XHR)
        self.assertEqual(st, 200, raw)
        self.assertFalse(json.loads(raw)["cancelled"])

    def test_auto_valeurs_invalides(self):
        for body in ({"enabled": "oui"}, {"daily_budget": 0}, {"daily_budget": "3"},
                     {"daily_budget": True}):
            with self.subTest(body=body):
                st, _ = self.req("POST", "/api/workspaces/ws1/improvement/auto",
                                 body=body, headers=XHR)
                self.assertEqual(st, 400)

    def test_abandon_202(self):
        with mock.patch.object(ie, "abandon_pending",
                               return_value={"status": "rejected", "iteration": 2}) as ab:
            st, raw = self.req("POST", "/api/workspaces/ws1/improvement/abandon", headers=XHR)
            self.assertEqual(st, 202, raw)
            self.assertEqual(json.loads(raw)["job"]["kind"], "abandon")
            wait_idle()
        self.assertTrue(ab.called)

    def test_get_improvement_un_seul_improvement_state(self):
        real = api_team.improvement_state
        counter = mock.Mock(side_effect=real)
        with mock.patch.object(server, "improvement_state", counter), \
                mock.patch.object(api_team, "improvement_state", counter):
            st, _ = self.req("GET", "/api/workspaces/ws1/improvement")
            self.assertEqual(st, 200)
            self.assertEqual(counter.call_count, 1)
            counter.reset_mock()
            st, _ = self.req("GET", "/api/workspaces/ws1/improvement/job")
            self.assertEqual(st, 200)
            self.assertEqual(counter.call_count, 1)

    def test_subscription_sans_secret(self):
        write_json_file(HOME / ".claude" / ".credentials.json", {"claudeAiOauth": {
            "accessToken": "SECRET-acces", "refreshToken": "SECRET-refresh",
            "subscriptionType": "pro", "rateLimitTier": "default_claude_pro"}})
        with mock.patch.object(claude_account, "_from_cli", return_value=None), \
                mock.patch.object(claude_account, "_cli_exists", return_value=False):
            st, raw = self.req("GET", "/api/claude/subscription?ws=ws1")
            self.assertEqual(st, 200, raw)
            self.assertNotIn(b"SECRET", raw)
            p = json.loads(raw)
            self.assertEqual(p["plan"], "pro")
            codes = {w["code"] for w in p["warnings"]}
            self.assertIn("pro_opus", codes)
            self.assertIn("pro_effort", codes)
            self.assertTrue(p["rules"])
            self.assertLessEqual(set(p) - {"warnings", "rules"},
                                 {"plan", "tier", "source", "auth_method", "api_key_present",
                                  "cli_available", "conflict", "sources_seen"})
            st, raw = self.req("GET", "/api/claude/subscription")
            self.assertEqual(st, 200)
            self.assertEqual(json.loads(raw)["warnings"], [])
            self.assertEqual(self.req("GET", "/api/claude/subscription?ws=absent")[0], 404)
            self.assertEqual(self.req("GET", "/api/claude/subscription?ws=a%2Fb")[0], 400)


def server_config_day():
    from dashcore.config import IMPROVE_MAX_USD_PER_DAY
    return IMPROVE_MAX_USD_PER_DAY


def server_config_max():
    from dashcore.config import IMPROVE_MAX_USD_PER_ITERATION
    return IMPROVE_MAX_USD_PER_ITERATION


if __name__ == "__main__":
    unittest.main()
