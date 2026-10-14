"""active_sessions : purge des PID morts / recyclés, état running/idle."""
from __future__ import annotations

import os
import sys
import unittest

from _support import read_json_file, reset_sandbox, write_json_file
from dashcore import active_sessions
from dashcore.config import ACTIVE_SESSIONS_FILE

# PID qui ne peut exister nulle part : > pid_max Linux (4 194 304) et non
# multiple de 4 (les PID Windows le sont toujours).
DEAD_PID = 2_147_483_646


class ActiveSessionsTests(unittest.TestCase):
    def setUp(self):
        reset_sandbox()

    def _write(self, data):
        write_json_file(ACTIVE_SESSIONS_FILE, data)

    def test_pid_inexistant_purge(self):
        self._write({"mort": {"pid": DEAD_PID, "launched_at": 1, "label": "mort"}})
        self.assertEqual(active_sessions.list_active(), {})
        self.assertEqual(read_json_file(ACTIVE_SESSIONS_FILE), {})

    def test_pid_vivant_conserve(self):
        self._write({"vivant": {"pid": os.getpid(), "launched_at": 1, "label": "v"},
                     "mort": {"pid": DEAD_PID, "launched_at": 1, "label": "m"}})
        res = active_sessions.list_active()
        self.assertEqual(list(res), ["vivant"])
        # Windows : le process de test n'a pas de descendant claude/node -> idle.
        # Ailleurs : pas d'arbre de process -> running (PID vivant).
        expected = "idle" if sys.platform == "win32" else "running"
        self.assertEqual(res["vivant"]["state"], expected)
        self.assertNotIn("state", read_json_file(ACTIVE_SESSIONS_FILE)["vivant"])

    def test_sans_purge_rien_ne_change(self):
        data = {"mort": {"pid": DEAD_PID, "launched_at": 1, "label": "mort"}}
        self._write(data)
        self.assertEqual(active_sessions.list_active(prune_dead=False), data)
        self.assertEqual(read_json_file(ACTIVE_SESSIONS_FILE), data)

    def test_registre_illisible_traite_comme_vide(self):
        ACTIVE_SESSIONS_FILE.write_text("{corrompu", encoding="utf-8")
        self.assertEqual(active_sessions.list_active(), {})

    def test_kill_pid_mort_nettoie_sans_tuer(self):
        self._write({"mort": {"pid": DEAD_PID, "launched_at": 1, "label": "mort"}})
        ok, msg = active_sessions.kill("mort")
        self.assertFalse(ok)
        self.assertIn("déjà terminé", msg)
        self.assertEqual(read_json_file(ACTIVE_SESSIONS_FILE), {})

    def test_kill_sans_session(self):
        ok, _ = active_sessions.kill("inconnu")
        self.assertFalse(ok)

    @unittest.skipUnless(sys.platform == "win32", "date de création de process : Windows uniquement")
    def test_pid_recycle_purge(self):
        created = active_sessions.process_creation_time(os.getpid())
        self.assertIsNotNone(created)
        self._write({"recycle": {"pid": os.getpid(), "launched_at": 1, "label": "r",
                                 "created": created + 1}})
        self.assertEqual(active_sessions.list_active(), {})

class DescendantPureTests(unittest.TestCase):
    """`_has_claude_descendant` est pur : testable sur toutes les plateformes."""

    def test_descendant_claude_detecte(self):
        procs = {10: (1, "cmd.exe"), 11: (10, "conhost.exe"), 12: (11, "node.exe"),
                 20: (1, "cmd.exe")}
        self.assertTrue(active_sessions._has_claude_descendant(10, procs))
        self.assertFalse(active_sessions._has_claude_descendant(20, procs))

    def test_cycle_de_ppid_sans_boucle_infinie(self):
        procs = {5: (6, "cmd.exe"), 6: (5, "cmd.exe")}
        self.assertFalse(active_sessions._has_claude_descendant(5, procs))

    def test_descendant_profond(self):
        procs = {1: (0, "cmd.exe"), 2: (1, "x.exe"), 3: (2, "y.exe"), 4: (3, "claude.exe")}
        self.assertTrue(active_sessions._has_claude_descendant(1, procs))


if __name__ == "__main__":
    unittest.main()
