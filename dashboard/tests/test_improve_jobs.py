"""improve_jobs : tâches de fond de la boucle d'amélioration.

Moteur simulé par `mock` (aucun appel réel à `claude`) ; l'annulation lance
le faux binaire `tests/fake_claude.py` via `claude_runner.run_claude`."""
from __future__ import annotations

import datetime as dt
import importlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from _support import DASHBOARD_DIR, HOME, SANDBOX, make_workspace, reset_sandbox, write_json_file
from dashcore import active_sessions
from dashcore import claude_runner as cr
from dashcore import config
from dashcore import improve_engine as ie
from dashcore import improve_jobs as ij

FAKE = DASHBOARD_DIR / "tests" / "fake_claude.py"
RECORD_KEYS = {"job_id", "ws_id", "kind", "status", "step", "cases_done", "cases_total",
               "started_at", "ended_at", "pid", "pid_ctime", "cost_usd", "tokens", "calls",
               "iteration", "verdict", "score", "quota_reset", "error", "session_ids"}


def wait_idle(timeout: float = 30.0) -> None:
    end = time.monotonic() + timeout
    while ij.is_running() and time.monotonic() < end:
        time.sleep(0.05)
    if ij.is_running():
        raise AssertionError("job toujours en cours")


def wait_for(pred, timeout: float = 20.0) -> None:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return
        time.sleep(0.05)
    raise AssertionError("condition non atteinte")


def sleeper() -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class Base(unittest.TestCase):
    def setUp(self):
        wait_idle()
        reset_sandbox()
        self.ws = make_workspace("w1")
        self.ws2 = make_workspace("w2")

    def tearDown(self):
        wait_idle()


class ConcurrenceTests(Base):
    def test_second_lancement_409_meme_ws_et_autre_ws(self):
        gate = threading.Event()

        def fake(ctx):
            gate.wait(10)
            return {"candidate": None, "verdict": {"status": "accepted", "iteration": 3}}

        with mock.patch.object(ie, "run_iteration", side_effect=fake):
            st, body = ij.start_job("w1", self.ws, "iteration")
            self.assertEqual(st, 202, body)
            self.assertEqual(body["job"]["status"], "running")
            self.assertTrue(ij.is_running("w1"))
            self.assertTrue(ij.is_running())
            self.assertFalse(ij.is_running("w2"))
            st, body = ij.start_job("w1", self.ws, "measure")
            self.assertEqual((st, body["reason"]), (409, "running"))
            st, body = ij.start_job("w2", self.ws2, "iteration", force=True)
            self.assertEqual((st, body["reason"]), (409, "running"))
            self.assertIn("w1", body["error"])
            gate.set()
            wait_idle()
        job = ij.get_job("w1")
        self.assertEqual(job["status"], "succeeded")
        self.assertEqual((job["iteration"], job["verdict"]), (3, "accepted"))
        with mock.patch.object(ie, "measure", return_value={"score": 0.75}):
            st, _ = ij.start_job("w2", self.ws2, "measure")
            self.assertEqual(st, 202)
            wait_idle()
        self.assertEqual(ij.get_job("w2")["score"], 0.75)

    def test_kind_et_parametres_invalides(self):
        self.assertEqual(ij.start_job("w1", self.ws, "autre")[0], 400)
        self.assertEqual(ij.start_job("../x", self.ws, "measure")[0], 400)
        self.assertEqual(ij.start_job("w1", self.ws, "measure", max_usd=0)[0], 400)
        self.assertEqual(ij.start_job("w1", self.ws, "measure", max_usd="abc")[0], 400)
        self.assertFalse(ij.is_running())

    def test_session_ouverte_409_sauf_force(self):
        running = {"w1": {"pid": 1, "launched_at": 0, "label": "w1", "state": "running"}}
        with mock.patch.object(active_sessions, "list_active", return_value=running), \
             mock.patch.object(ie, "measure", return_value={"score": 1.0}):
            st, body = ij.start_job("w1", self.ws, "measure")
            self.assertEqual((st, body["reason"]), (409, "session"))
            self.assertIn("Nebula", body["error"])
            st, _ = ij.start_job("w1", self.ws, "measure", force=True)
            self.assertEqual(st, 202)
            wait_idle()
        self.assertEqual(ij.get_job("w1")["status"], "succeeded")

    def test_resolve_et_abandon_appellent_le_moteur(self):
        with mock.patch.object(ie, "verdict_phase",
                               return_value={"status": "rejected", "iteration": 2,
                                             "report": {"score": 0.5}}) as vp:
            self.assertEqual(ij.start_job("w1", self.ws, "resolve")[0], 202)
            wait_idle()
        vp.assert_called_once()
        job = ij.get_job("w1")
        self.assertEqual((job["verdict"], job["iteration"], job["score"]), ("rejected", 2, 0.5))
        with mock.patch.object(ie, "abandon_pending",
                               return_value={"status": "rejected", "iteration": 2}) as ab:
            self.assertEqual(ij.start_job("w1", self.ws, "abandon")[0], 202)
            wait_idle()
        ab.assert_called_once()
        self.assertEqual(ij.get_job("w1")["kind"], "abandon")


class AnnulationTests(Base):
    def test_annulation_tue_enfant_et_donne_cancelled(self):
        script = SANDBOX / "fake-cancel.json"
        calls = SANDBOX / "fake-cancel-calls.jsonl"
        write_json_file(script, {"log": str(calls), "rules": [{"no_delegation": True, "sleep": 30}]})
        seen = {}

        def fake(ctx):
            # cancel=None : seul cancel_job peut arrêter l'enfant.
            r = cr.run_claude("prompt", ctx.ws_dir, allowed_tools=["Read"], max_budget_usd=1.0,
                              cancel=None, timeout=60, cmd=str(FAKE),
                              log_path=ctx.log_dir / "001-relay.jsonl", on_spawn=ctx.on_spawn)
            seen["status"] = r.status
            if ctx.cancel.is_set():
                raise ie.Cancelled("job annulé")
            return {}

        with mock.patch.dict(os.environ, {"FAKE_CLAUDE_SCRIPT": str(script)}), \
             mock.patch.object(ie, "measure", side_effect=fake):
            self.assertEqual(ij.start_job("w1", self.ws, "measure")[0], 202)
            wait_for(lambda: (ij.get_job("w1") or {}).get("pid"))
            pid = ij.get_job("w1")["pid"]
            self.assertTrue(active_sessions.is_pid_alive(pid))
            # Faux binaire démarré (journal d'appel écrit), puis le temps que
            # l'événement init (session_id) soit émis avant son attente.
            wait_for(calls.exists)
            time.sleep(0.5)
            t0 = time.monotonic()
            st, _ = ij.cancel_job("w1")
            self.assertEqual(st, 202)
            wait_idle()
        self.assertLess(time.monotonic() - t0, 20)
        job = ij.get_job("w1")
        self.assertEqual(job["status"], "cancelled")
        self.assertIsNone(job["pid"])
        self.assertEqual(job["session_ids"], ["fake-session"])
        self.assertFalse(active_sessions.is_pid_alive(pid))
        self.assertNotEqual(seen["status"], "ok")

    def test_annulation_sans_job_404(self):
        self.assertEqual(ij.cancel_job("w1")[0], 404)


class MappingTests(Base):
    def test_chaque_exception_du_moteur(self):
        cases = [
            (ie.QuotaReached("limite atteinte", reset="3:45pm"), "quota"),
            (ie.BudgetExceeded("plafond atteint"), "budget"),
            (ie.Cancelled("job annulé"), "cancelled"),
            (ie.JobTimeout("délai dépassé"), "timeout"),
            (ie.ConflictError("une itération attend"), "failed"),
            (ie.AgentsMissing("agents absents"), "failed"),
            (ie.EngineError("moteur", status=500), "failed"),
            (RuntimeError("boom\nligne 2\n" + "x" * 1000), "failed"),
        ]
        for exc, status in cases:
            with self.subTest(exc=type(exc).__name__), \
                 mock.patch.object(ie, "run_iteration", side_effect=exc):
                self.assertEqual(ij.start_job("w1", self.ws, "iteration")[0], 202)
                wait_idle()
                job = ij.get_job("w1")
                self.assertEqual(job["status"], status)
                self.assertTrue(job["error"])
                self.assertNotIn("\n", job["error"])
                self.assertNotIn("Traceback", job["error"])
                self.assertLessEqual(len(job["error"]), ij.ERROR_MAX)
                self.assertIsNotNone(job["ended_at"])
                if status == "quota":
                    self.assertEqual(job["quota_reset"], "3:45pm")
                else:
                    self.assertIsNone(job["quota_reset"])
        self.assertTrue(ij.list_history("w1")[-1]["error"].startswith("limite"))
        self.assertTrue(ij.get_job("w1")["error"].startswith("RuntimeError"))


class RefusConfigTests(Base):
    def test_refus_config_non_commitee_enregistre(self):
        res = {"candidate": {"phase": "candidate", "status": "rejected", "iteration": None,
                             "reason": "modifications non commitées", "dirty_paths": [".claude/team.json"],
                             "baseline": None, "entry": None}, "verdict": None, "spend": None}
        with mock.patch.object(ie, "run_iteration", return_value=res):
            self.assertEqual(ij.start_job("w1", self.ws, "iteration")[0], 202)
            wait_idle()
        job = ij.get_job("w1")
        self.assertEqual(job["status"], "succeeded")
        self.assertEqual(job["verdict"], "refused")
        self.assertEqual(job["dirty_paths"], [".claude/team.json"])
        self.assertIsNone(job.get("iteration"))


class PersistanceTests(Base):
    def test_progression_cout_et_relecture_apres_rechargement(self):
        global ij

        def fake(ctx):
            ctx.notify(event="case", id="c1")
            ctx.notify(event="case", id="c2")
            ctx.spend["cost_usd"] = 1.25
            ctx.spend["calls"] = 3
            ctx.spend["tokens"]["output"] = 42
            ctx.notify(event="call", label="critic", seq=3)
            ctx.notify(event="case", id="c1")   # 2e mesure : compteur remis à zéro
            return {"candidate": {"status": "pending", "iteration": 1},
                    "verdict": {"status": "accepted", "iteration": 1, "report": {"score": 0.9}}}

        with mock.patch.object(ie, "run_iteration", side_effect=fake):
            self.assertEqual(ij.start_job("w1", self.ws, "iteration", max_usd=2.5)[0], 202)
            wait_idle()
        job = ij.get_job("w1")
        self.assertEqual(job["status"], "succeeded")
        self.assertEqual((job["cost_usd"], job["calls"], job["tokens"]["output"]), (1.25, 3, 42))
        self.assertEqual(job["cases_done"], 1)
        self.assertEqual(job["score"], 0.9)
        events = (config.IMPROVE_LOGS_DIR / "w1" / f"{job['job_id']}.jsonl").read_text(
            encoding="utf-8").splitlines()
        self.assertEqual(json.loads(events[0])["event"], "start")
        self.assertEqual(json.loads(events[-1])["event"], "end")
        ij = importlib.reload(ij)
        self.assertFalse(ij.is_running())
        again = ij.get_job("w1")
        self.assertEqual(again, job)
        self.assertEqual([h["job_id"] for h in ij.list_history("w1")], [job["job_id"]])
        self.assertEqual(ij.list_history("w1", limit=0), [])

    def test_historique_borne_et_rotation_des_journaux(self):
        with mock.patch.object(ie, "measure", return_value={"score": 1.0}):
            for _ in range(ij.HISTORY_MAX + 3):
                self.assertEqual(ij.start_job("w1", self.ws, "measure")[0], 202)
                wait_idle()
        hist = ij.list_history("w1", limit=100)
        self.assertEqual(len(hist), ij.HISTORY_MAX)
        self.assertEqual(len({h["job_id"] for h in hist}), ij.HISTORY_MAX)
        logs = list((config.IMPROVE_LOGS_DIR / "w1").glob("*.jsonl"))
        self.assertLessEqual(len(logs), ij.LOGS_KEEP)

    def test_aucune_donnee_d_identification_dans_l_etat(self):
        def fake(ctx):
            ctx.notify(event="call", label="relay", seq=1, prompt="SECRET-PROMPT")
            return {"score": 1.0, "secret": "SECRET-RESULT"}

        with mock.patch.object(ie, "measure", side_effect=fake):
            ij.start_job("w1", self.ws, "measure")
            wait_idle()
        text = (config.IMPROVE_JOBS_DIR / "w1.json").read_text(encoding="utf-8")
        state = json.loads(text)
        self.assertEqual(set(state), {"current", "history"})
        self.assertIsNone(state["current"])
        self.assertEqual(set(state["history"][0]), RECORD_KEYS)
        for bad in ("SECRET-RESULT", "@", str(HOME), str(self.ws), "email", "oauth", "accessToken"):
            self.assertNotIn(bad, text)


class RecoverTests(Base):
    def _write_running(self, ws_id: str, pid=None, ctime=None) -> dict:
        rec = ij._new_record(f"20261017-000000-{ws_id}", ws_id, "iteration")
        rec.update(pid=pid, pid_ctime=ctime)
        write_json_file(config.IMPROVE_JOBS_DIR / f"{ws_id}.json", {"current": rec, "history": []})
        return rec

    def test_running_devient_interrupted_et_orphelin_tue(self):
        orphan, stranger = sleeper(), sleeper()
        try:
            ctime = active_sessions.process_creation_time(orphan.pid)
            sctime = active_sessions.process_creation_time(stranger.pid)
            self._write_running("w1", orphan.pid, ctime)
            # PID recyclé (date de création différente) : jamais tué.
            self._write_running("w2", stranger.pid, (sctime or 0) + 1)
            write_json_file(config.IMPROVE_JOBS_DIR / "w3.json",
                            {"current": None, "history": []})
            self.assertEqual(sorted(ij.recover_jobs()), ["w1", "w2"])
            for ws in ("w1", "w2"):
                job = ij.get_job(ws)
                self.assertEqual(job["status"], "interrupted")
                self.assertIsNone(job["pid"])
                self.assertTrue(job["ended_at"])
                self.assertIsNone(ij._load_state(ws)["current"])
            if ctime is not None:
                orphan.wait(timeout=15)
                self.assertIsNotNone(orphan.poll())
            self.assertIsNone(stranger.poll())
            self.assertEqual(ij.recover_jobs(), [])
        finally:
            for p in (orphan, stranger):
                if p.poll() is None:
                    p.kill()
                    p.wait(timeout=10)


class SpentTodayTests(Base):
    def test_somme_du_jour_tous_workspaces(self):
        today = dt.date.today()
        yesterday = today - dt.timedelta(days=1)

        def rec(job_id, day, cost):
            r = ij._new_record(job_id, "w", "iteration")
            r.update(started_at=dt.datetime.combine(day, dt.time(10, 0)).astimezone()
                     .isoformat(timespec="seconds"), cost_usd=cost, status="succeeded")
            return r

        a = rec("a", today, 1.5)
        write_json_file(config.IMPROVE_JOBS_DIR / "w1.json",
                        {"current": a, "history": [a, rec("b", today, 2.25), rec("c", yesterday, 9.0)]})
        write_json_file(config.IMPROVE_JOBS_DIR / "w2.json",
                        {"current": None, "history": [rec("d", today, 0.5), rec("e", yesterday, 1.0)]})
        self.assertAlmostEqual(ij.spent_today(), 4.25)
        self.assertAlmostEqual(ij.spent_today(yesterday), 10.0)
        self.assertEqual(ij.spent_today(today - dt.timedelta(days=5)), 0.0)

    def test_vide(self):
        self.assertEqual(ij.spent_today(), 0.0)


class SessionBusyTests(Base):
    def _transcript(self, name: str, age_s: float) -> Path:
        enc = re.sub(r"[^A-Za-z0-9]", "-", str(self.ws.resolve()))
        d = config.CLAUDE_PROJECTS / enc
        d.mkdir(parents=True, exist_ok=True)
        f = d / f"{name}.jsonl"
        f.write_text("{}\n", encoding="utf-8")
        t = time.time() - age_s
        os.utime(f, (t, t))
        return f

    def test_entree_active_sessions_running(self):
        with mock.patch.object(active_sessions, "list_active",
                               return_value={"w1": {"state": "running"}}):
            busy, why = ij.session_busy("w1", self.ws)
        self.assertTrue(busy)
        self.assertEqual(why, "session lancée par Nebula en cours")

    def test_entree_idle_ou_autre_ws_libre(self):
        with mock.patch.object(active_sessions, "list_active",
                               return_value={"w1": {"state": "idle"}, "w2": {"state": "running"}}):
            self.assertEqual(ij.session_busy("w1", self.ws), (False, ""))

    def test_transcript_etranger_recent_occupe(self):
        self._transcript("abc-123", 30)
        busy, why = ij.session_busy("w1", self.ws)
        self.assertTrue(busy)
        self.assertIn("activité récente", why)

    def test_transcript_du_job_exclu_libre(self):
        self._transcript("job-session", 30)
        self.assertEqual(ij.session_busy("w1", self.ws, exclude_session_ids=["job-session"]),
                         (False, ""))

    def test_transcript_ancien_libre(self):
        self._transcript("vieux", ij.RECENT_ACTIVITY_S + 60)
        self.assertEqual(ij.session_busy("w1", self.ws), (False, ""))

    def test_sans_dossier_projet_libre(self):
        self.assertEqual(ij.session_busy("w1", self.ws), (False, ""))

    def test_start_job_exclut_les_sessions_du_job_precedent(self):
        self._transcript("job-prec", 30)
        with mock.patch.object(ie, "measure", return_value={"score": 1.0}):
            st, body = ij.start_job("w1", self.ws, "measure")
            self.assertEqual((st, body["reason"]), (409, "session"))
            st, _ = ij.start_job("w1", self.ws, "measure", exclude_session_ids=["job-prec"])
            self.assertEqual(st, 202)
            wait_idle()
            # un transcript étranger récent bloque toujours
            self._transcript("etranger", 5)
            st, body = ij.start_job("w1", self.ws, "measure", exclude_session_ids=["job-prec"])
            self.assertEqual((st, body["reason"]), (409, "session"))

    def test_planificateur_enchaine_deux_jobs_auto_sans_409(self):
        from dashcore import improve_scheduler as sch
        config.IMPROVE_AUTO_FILE.unlink(missing_ok=True)
        st_fn = lambda ws: (200, {"pending": None, "journal": [], "loop": {},  # noqa: E731
                                  "stats": {"iterations": 0, "today_iterations": 0,
                                            "consecutive_rejects": 0}})
        sch.set_auto("w1", enabled=True, daily_budget=10)
        real = ij.session_busy
        with mock.patch("dashcore.workspace_io.resolve_ws_dir", lambda ws: self.ws),              mock.patch.object(ie, "run_iteration",
                               return_value={"candidate": None,
                                             "verdict": {"status": "accepted", "iteration": 1}}):
            out = sch.tick(dt.datetime.now(), state_fn=st_fn)
            self.assertEqual([r["status"] for r in out], [202])
            wait_idle()
            # le job a laissé son transcript `claude -p` (session connue du job)
            self._transcript("job-prec", 30)
            state = ij._load_state("w1")
            state["history"][0]["session_ids"] = ["job-prec"]
            ij._save_state("w1", state)
            self.assertTrue(real("w1", self.ws)[0])
            out = sch.tick(dt.datetime.now(), state_fn=st_fn)
            self.assertEqual([r["status"] for r in out], [202], out)
            wait_idle()
            # un transcript étranger récent bloque toujours (pas de lancement)
            self._transcript("etranger", 5)
            self.assertEqual(sch.tick(dt.datetime.now(), state_fn=st_fn), [])
        sch.stop()

    def test_start_job_refuse_sur_transcript_recent(self):
        self._transcript("abc", 10)
        st, body = ij.start_job("w1", self.ws, "measure")
        self.assertEqual((st, body["reason"]), (409, "session"))


class OnSpawnTests(unittest.TestCase):
    def test_plus_de_relais_popen(self):
        self.assertFalse(hasattr(ij, "_PopenTap"))
        self.assertFalse(hasattr(ij, "_install_tap"))
        self.assertIs(cr.subprocess, subprocess)


if __name__ == "__main__":
    unittest.main()
