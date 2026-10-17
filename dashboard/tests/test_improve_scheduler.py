"""improve_scheduler : décisions du mode automatique (horloge et dépendances
injectées, aucun job réel, aucun appel à claude)."""
from __future__ import annotations

import datetime as dt
import unittest
from pathlib import Path
from unittest import mock

from _support import reset_sandbox
from dashcore import api_team, config
from dashcore import improve_jobs as ij
from dashcore import improve_scheduler as sch

NOW = dt.datetime(2026, 10, 17, 10, 0, 0)


def make_state(today=0, streak=0, pending=None, max_it=10, stop=3, journal=None):
    return {"pending": pending, "journal": journal or [],
            "stats": {"iterations": len(journal or []), "today_iterations": today,
                      "consecutive_rejects": streak},
            "loop": {"max_iterations": max_it, "stop_after_consecutive_rejects": stop}}


class SchedulerTest(unittest.TestCase):
    def setUp(self):
        reset_sandbox()
        sch.stop()
        config.IMPROVE_AUTO_FILE.unlink(missing_ok=True)
        self.states = {}
        self.jobs = {}
        self.spent = 0.0
        self.busy = False
        self.calls = []
        self.running = False
        for p in (
            mock.patch.object(ij, "get_job", lambda ws: self.jobs.get(ws)),
            mock.patch.object(ij, "spent_today", lambda day=None: self.spent),
            mock.patch.object(ij, "is_running", lambda ws_id=None: self.running),
            mock.patch.object(ij, "session_busy", self._busy),
            mock.patch("dashcore.workspace_io.resolve_ws_dir", lambda ws: Path("/x") / ws),
            mock.patch.object(api_team, "improvement_state", self._state),
        ):
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(sch.stop)

    def _busy(self, ws_id, ws_dir, exclude_session_ids=()):
        self.excluded = exclude_session_ids
        return self.busy, "session"

    def _state(self, ws_id):
        return 200, self.states.get(ws_id, make_state())

    def _start(self, ws_id, ws_dir, kind, **kw):
        self.calls.append((ws_id, kind, kw))
        return 202, {"ok": True}

    def tick(self, now=NOW):
        return sch.tick(now, start_job=self._start, state_fn=self._state)

    def enable(self, ws="a", **kw):
        sch.set_auto(ws, enabled=True, **kw)

    def test_disabled_by_default(self):
        self.assertFalse(sch.get_auto("a")["enabled"])
        self.assertEqual(self.tick(), [])
        self.assertEqual(self.calls, [])

    def test_iteration_launched_with_cap(self):
        self.enable()
        self.assertEqual(self.tick(), [{"ws_id": "a", "action": "iteration", "status": 202}])
        self.assertEqual(self.calls[0][2], {"max_usd": config.IMPROVE_MAX_USD_PER_ITERATION})

    def test_daily_budget(self):
        self.enable()
        self.states["a"] = make_state(today=3)
        self.assertEqual(self.tick(), [])
        self.states["a"] = make_state(today=2)
        self.assertEqual(len(self.tick()), 1)

    def test_cost_cap_pauses_until_midnight(self):
        self.enable()
        self.spent = config.IMPROVE_MAX_USD_PER_DAY
        self.assertEqual(self.tick(), [])
        auto = sch.get_auto("a")
        self.assertEqual(auto["pause_reason"], "budget")
        self.assertEqual(auto["paused_until"], "2026-10-18T00:00:00")
        self.spent = 0.0
        self.assertEqual(self.tick(NOW + dt.timedelta(hours=5)), [])
        self.assertEqual(len(self.tick(dt.datetime(2026, 10, 18, 0, 1))), 1)

    def test_quota_pause_until_reset_then_resume(self):
        self.enable()
        self.jobs["a"] = {"job_id": "j1", "status": "quota", "quota_reset": "2026-10-17T15:30:00"}
        self.assertEqual(self.tick(), [])
        auto = sch.get_auto("a")
        self.assertEqual((auto["pause_reason"], auto["paused_until"]), ("quota", "2026-10-17T15:30:00"))
        self.assertEqual(self.tick(dt.datetime(2026, 10, 17, 15, 0)), [])
        self.assertEqual(len(self.tick(dt.datetime(2026, 10, 17, 15, 31))), 1)
        self.assertIsNone(sch.get_auto("a")["paused_until"])
        # le même job quota ne repose pas de pause
        self.assertEqual(len(self.tick(dt.datetime(2026, 10, 17, 15, 32))), 1)

    def test_quota_job_bout_en_bout_heure_du_message(self):
        from dashcore import claude_runner as cr
        self.enable()
        reset = cr.parse_reset("3:45pm", NOW)
        self.jobs["a"] = {"job_id": "j1", "status": "quota", "quota_reset": reset}
        self.tick()
        self.assertEqual(sch.get_auto("a")["paused_until"], "2026-10-17T15:45:00")

    def test_sessions_des_jobs_recents_transmises_a_start_job(self):
        self.enable()
        self.jobs["a"] = {"job_id": "j2", "status": "succeeded", "session_ids": ["s2"],
                          "ended_at": "2026-10-17T09:55:00"}
        old = {"job_id": "j1", "session_ids": ["s1"], "ended_at": "2026-10-17T09:58:00"}
        ancien = {"job_id": "j0", "session_ids": ["s0"], "ended_at": "2026-10-17T08:00:00"}
        with mock.patch.object(ij, "list_history", lambda ws, limit=20: [old, ancien]):
            self.tick()
        self.assertEqual(self.excluded, ("s2", "s1"))
        self.assertEqual(self.calls[0][2]["exclude_session_ids"], ("s2", "s1"))

    def test_quota_without_time_adds_one_hour(self):
        self.enable()
        self.jobs["a"] = {"job_id": "j1", "status": "quota", "quota_reset": None}
        self.tick()
        self.assertEqual(sch.get_auto("a")["paused_until"], "2026-10-17T11:00:00")

    def test_stop_after_rejects_then_resume(self):
        self.enable()
        self.states["a"] = make_state(streak=3)
        self.assertEqual(self.tick(), [])
        status, view = sch.set_auto("a", resume=True)
        self.assertEqual(status, 200)
        self.assertEqual(sch.get_auto("a")["ack_rejects_at"], 3)
        self.assertEqual(len(self.tick()), 1)
        self.states["a"] = make_state(streak=6)
        self.assertEqual(self.tick(), [])

    def test_campaign_reset_on_reactivation(self):
        j = [{"iteration": i} for i in range(1, 6)]
        self.states["a"] = make_state(max_it=3, journal=j)
        self.enable()
        self.assertEqual(sch.get_auto("a")["campaign_start_iteration"], 6)
        self.assertEqual(len(self.tick()), 1)
        self.states["a"] = make_state(max_it=3, journal=j + [{"iteration": i} for i in (6, 7, 8)])
        self.assertEqual(self.tick(), [])
        sch.set_auto("a", enabled=False)
        self.enable()
        self.assertEqual(sch.get_auto("a")["campaign_start_iteration"], 9)
        self.assertEqual(len(self.tick()), 1)

    def test_plafond_borne_par_reste_du_jour(self):
        self.enable()
        self.spent = config.IMPROVE_MAX_USD_PER_DAY - 1.5
        self.tick()
        self.assertEqual(self.calls[0][2]["max_usd"], 1.5)

    def test_resolve_non_tranche_pause_undecidable_puis_resume(self):
        self.enable()
        self.states["a"] = make_state(pending={"iteration": 2})
        self.jobs["a"] = {"job_id": "r1", "kind": "resolve", "status": "succeeded",
                          "verdict": "pending", "ended_at": "2026-10-17T09:59:00"}
        self.assertEqual(self.tick(), [])
        auto = sch.get_auto("a")
        self.assertEqual((auto["pause_reason"], auto["handled_job"]), ("undecidable", "r1"))
        # pas de relance, même bien plus tard
        self.assertEqual(self.tick(NOW + dt.timedelta(days=30)), [])
        self.assertEqual(self.calls, [])
        sch.set_auto("a", resume=True)
        self.assertIsNone(sch.get_auto("a")["paused_until"])
        self.assertEqual(self.tick()[0]["action"], "resolve")

    def test_config_non_commitee_pause_dirty_config(self):
        self.enable()
        self.jobs["a"] = {"job_id": "d1", "kind": "iteration", "status": "succeeded",
                          "verdict": "refused", "dirty_paths": [".claude/team.json"]}
        self.assertEqual(self.tick(), [])
        auto = sch.get_auto("a")
        self.assertEqual((auto["pause_reason"], auto["handled_job"]), ("dirty_config", "d1"))
        self.assertEqual(self.tick(NOW + dt.timedelta(days=30)), [])
        self.assertEqual(self.calls, [])
        sch.set_auto("a", resume=True)
        self.assertEqual(self.tick()[0]["action"], "iteration")

    def test_resolve_tranche_ne_met_pas_en_pause(self):
        self.enable()
        self.states["a"] = make_state(pending={"iteration": 2})
        self.jobs["a"] = {"job_id": "r1", "kind": "resolve", "status": "succeeded",
                          "verdict": "rejected"}
        self.assertEqual(self.tick()[0]["action"], "resolve")

    def test_pending_resolves_first(self):
        self.enable()
        self.states["a"] = make_state(pending={"iteration": 2})
        self.assertEqual(self.tick()[0]["action"], "resolve")

    def test_open_session(self):
        self.enable()
        self.busy = True
        self.jobs["a"] = {"job_id": "j", "status": "succeeded", "session_ids": ["s1"]}
        self.assertEqual(self.tick(), [])
        self.assertEqual(tuple(self.excluded), ("s1",))

    def test_running_job_blocks(self):
        self.enable()
        self.running = True
        self.assertEqual(self.tick(), [])

    def test_single_job_for_two_workspaces(self):
        self.enable("a")
        self.enable("b")
        res = self.tick()
        self.assertEqual(len(res), 1)
        self.assertEqual(len(self.calls), 1)

    def test_invalid_daily_budget(self):
        for bad in (0, 11, "3", True):
            self.assertEqual(sch.set_auto("a", daily_budget=bad)[0], 400)
        status, view = sch.set_auto("a", daily_budget=5)
        self.assertEqual((status, view["daily_budget"], view["daily_limit"]), (200, 5, 5))

    def test_view_keys(self):
        view = sch.auto_view("a", make_state(today=3))
        for k in ("enabled", "paused_until", "campaign_start_iteration", "daily_limit",
                  "budget_reached", "pause_reason", "daily_budget", "spent_today",
                  "ack_rejects_at"):
            self.assertIn(k, view)
        self.assertTrue(view["budget_reached"])

    def test_corrupted_file(self):
        config.IMPROVE_AUTO_FILE.parent.mkdir(parents=True, exist_ok=True)
        config.IMPROVE_AUTO_FILE.write_text("{pas du json", encoding="utf-8")
        auto = sch.get_auto("a")
        self.assertFalse(auto["enabled"])
        self.assertEqual(auto["daily_budget"], config.IMPROVE_AUTO_ITERATIONS_PER_DAY)
        self.assertEqual(self.tick(), [])

    def test_start_idempotent_and_stop(self):
        with mock.patch.object(sch, "tick", return_value=[]):
            sch.start(1)
            first = sch._THREAD
            sch.start(1)
            self.assertIs(sch._THREAD, first)
            self.assertTrue(first.is_alive())
            sch.stop()
            self.assertFalse(first.is_alive())
            self.assertIsNone(sch._THREAD)


if __name__ == "__main__":
    unittest.main()
