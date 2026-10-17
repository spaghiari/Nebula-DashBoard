"""Onglet « Amélioration » d'un workspace (js/pages/improvement.js) dans un
vrai navigateur headless (CDP, client stdlib).

FACULTATIF comme `test_ui_smoke` : `NEBULA_UI_TESTS=1` et un Chromium
(Edge/Chrome) trouvé, sinon skip. Serveur isolé (`ServerProcess`, front
réel, `NEBULA_DISABLE_SCHEDULER=1` posé par `_support`), workspace `ws1`
avec le module claude-team (marker minimal + `.claude/team.json`), jeu
d'évals et journal factices ; job factice écrit dans `IMPROVE_JOBS_DIR`
APRÈS le démarrage (la reprise du démarrage le passerait `interrupted`).
Aucun appel à Claude : aucun bouton qui lance un job n'est cliqué.

Couvre : rendu sans exception JS des états `no_baseline`, `pending`,
`job_running`, `rejects_stop` ; panneau du job ; fin de job (re-rendu +
toast du verdict) ; arrêt du polling quand l'onglet est masqué et au
démontage (navigation).

Les fonctions `write_fixture` / `write_job` servent aussi au script de
captures d'écran (outil local, hors dépôt).
"""
from __future__ import annotations

import datetime as dt
import http.client
import json
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

from _support import ORIGINAL_ENV, SANDBOX, ServerProcess, free_port, rmtree, rmtree_retry
from ui.cdp import CDP, page_ws
from ui.test_ui_smoke import INSTR, WAIT, find_browser

BROWSER = find_browser() if os.environ.get("NEBULA_UI_TESTS") == "1" else None

MANIFEST = {
    "team": {"name": "Équipe de test", "prefix": "ws1"},
    "agents": [
        {"id": "orchestrator", "role": "Chef d'équipe", "model": "opus"},
        {"id": "executor", "role": "Exécutant", "model": "sonnet", "effort": "high"},
        {"id": "reviewer", "role": "Relecteur", "model": "opus"},
    ],
    "improvement_loop": {
        "eval_set": "evals/eval-set.jsonl", "journal": "journal/changes.jsonl",
        "eval_set_locked": True, "runs_per_eval": 1, "max_iterations": 10,
        "stop_after_consecutive_rejects": 3, "accept_if": {"min_score_gain": 0.02},
    },
}
CASES = [
    {"id": "plan-simple", "agent": "orchestrator", "grader": "rubric", "input": "x", "expected": "y"},
    {"id": "fix-<b>xss</b>", "agent": "executor", "grader": "test", "input": "x", "check": "true"},
    {"id": "regex-ok", "agent": "executor", "grader": "regex", "input": "x", "expected": "y"},
    {"id": "relecture", "agent": "reviewer", "grader": "exact", "input": "x", "expected": "y"},
]
IMPROVEMENTS_MD = """# improvements

- **[TODO] Préciser le format de sortie de l'exécutant <script>** (P1, ajouté 2026-10-15 par nebula)
  Détail.
- **[TODO] Raccourcir les consignes du relecteur** (P2, ajouté 2026-10-16 par nebula)
- **[DONE] Ancienne piste** (P2, ajouté 2026-10-01 par nebula)
"""
TOK = {"input": 120000, "output": 30000, "cache_read": 400000, "cache_creation": 20000}


def _line(it, status, before, after, cfg, **kw):
    d = {"iteration": it, "date": dt.date.today().isoformat(), "target": "team/agents/executor.md",
         "hypothesis": f"Hypothèse {it} : demander un plan avant d'écrire <i>le code</i>",
         "score_before": before, "score_after": after, "regressions": [], "status": status,
         "commit": None, "config_version": cfg, "runner": "nebula", "tokens": TOK,
         "cost_usd": 0.42, "duration_ms": 540000, "calls": 14, "failures_after": ["relecture"]}
    d.update(kw)
    return d


def _req(port, method, path, body=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
    try:
        hdr = {"X-Nebula-XHR": "1"}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            hdr["Content-Type"] = "application/json"
        conn.request(method, path, body=data, headers=hdr)
        r = conn.getresponse()
        return r.status, json.loads(r.read() or b"null")
    finally:
        conn.close()


def write_fixture(root: Path, port: int, state: str) -> None:
    """Workspace ws1 + module claude-team + journal pour l'état `state`
    (`no_baseline`, `pending`, `job_running`, `rejects_stop`, `ready`)."""
    tpl = root / "templates" / "claude-team"
    tpl.mkdir(parents=True, exist_ok=True)
    (tpl / ".nebula-overlay.json").write_text(json.dumps(
        {"id": "claude-team", "label": "Équipe d'agents", "signature_file": ".claude/team.json"}),
        encoding="utf-8")
    cl = root / "workspaces" / "ws1" / ".claude"
    (cl / "evals").mkdir(parents=True, exist_ok=True)
    (cl / "journal").mkdir(parents=True, exist_ok=True)
    (cl / "team.json").write_text(json.dumps(MANIFEST, ensure_ascii=False, indent=2), encoding="utf-8")
    (cl / "evals" / "eval-set.jsonl").write_text(
        "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in CASES), encoding="utf-8")
    (cl / "improvements.md").write_text(IMPROVEMENTS_MD, encoding="utf-8")
    journal = cl / "journal" / "changes.jsonl"
    journal.write_text("", encoding="utf-8")
    jobs = root / "dashboard" / "data" / "improve-jobs" / "ws1.json"
    if jobs.exists():
        jobs.unlink()
    if state == "no_baseline":
        return
    _, st = _req(port, "GET", "/api/workspaces/ws1/improvement")
    cfg = st["config_hash"]
    lines = [_line(1, "accepted", 0.5, 0.62, "ancienne", commit="a1b2c3d", reason="gain 0,12, 0 régression")]
    if state == "pending":
        lines.append(_line(2, "pending", 0.62, None, cfg, tokens={"input": 50000, "output": 9000,
                                                                     "cache_read": 0, "cache_creation": 0}))
    elif state == "rejects_stop":
        for i in (2, 3, 4):
            lines.append(_line(i, "rejected", 0.62, 0.6, cfg, regressions=["regex-ok"],
                               reason="gain négatif, 1 régression"))
    else:  # job_running / ready : mesure de référence à jour
        lines.append(_line(2, "accepted", 0.62, 0.7, cfg, commit="d4e5f6a", runner="manual"))
    journal.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lines), encoding="utf-8")
    if state == "job_running":
        write_job(root, running=True)


def write_job(root: Path, running: bool, **extra) -> None:
    now = dt.datetime.now().astimezone()
    rec = {"job_id": "20261017-101500-abc123", "ws_id": "ws1", "kind": "iteration",
           "status": "running" if running else "succeeded",
           "step": "mesure candidat" if running else "terminé", "cases_done": 2, "cases_total": 4,
           "started_at": (now - dt.timedelta(minutes=4)).isoformat(timespec="seconds"),
           "ended_at": None if running else now.isoformat(timespec="seconds"),
           "pid": None, "pid_ctime": None, "cost_usd": 0.18,
           "tokens": {"input": 40000, "output": 8000, "cache_read": 90000, "cache_creation": 0},
           "calls": 7, "iteration": 3, "verdict": None if running else "accepted",
           "score": None if running else 0.75, "quota_reset": None, "error": None, "session_ids": []}
    rec.update(extra)
    p = root / "dashboard" / "data" / "improve-jobs" / "ws1.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    state = {"current": rec, "history": []} if running else {"current": None, "history": [rec]}
    p.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")


@unittest.skipUnless(os.environ.get("NEBULA_UI_TESTS") == "1",
                     "tests navigateur facultatifs : définir NEBULA_UI_TESTS=1")
@unittest.skipUnless(BROWSER, "aucun navigateur Chromium (Edge/Chrome) trouvé")
class ImprovementTabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = SANDBOX / "ui-impr"
        rmtree(cls.base)
        cls.srv = ServerProcess(cls.base, real_front=True)
        cls.srv.start()
        _req(cls.srv.port, "POST", "/api/ui-state", {"onboarded": True, "claude_plan": "pro"})
        # Détection de l'abonnement (CLI `claude auth status`, lente à froid) mise
        # en cache côté serveur avant les mesures de délai du polling.
        _req(cls.srv.port, "GET", "/api/claude/subscription")
        cls.url = f"http://127.0.0.1:{cls.srv.port}"
        dbg = free_port()
        cls.browser = subprocess.Popen(
            [BROWSER, "--headless=new", f"--remote-debugging-port={dbg}",
             f"--user-data-dir={cls.base / 'profil'}", "--no-first-run", "--disable-gpu",
             "--window-size=1400,1000", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=ORIGINAL_ENV)
        try:
            cls.c = CDP(page_ws(dbg))
            cls.c.call("Page.enable")
            cls.c.call("Runtime.enable")
            cls.c.call("Page.addScriptToEvaluateOnNewDocument", source=INSTR)
        except Exception:
            cls._stop_all()
            raise

    @classmethod
    def _stop_all(cls):
        c = getattr(cls, "c", None)
        if c:
            c.close()
        b = getattr(cls, "browser", None)
        if b and b.poll() is None:
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/PID", str(b.pid), "/T", "/F"], capture_output=True)
            else:
                b.terminate()
            try:
                b.wait(timeout=10)
            except subprocess.TimeoutExpired:
                b.kill()
        cls.srv.stop()
        rmtree_retry(cls.base)

    @classmethod
    def tearDownClass(cls):
        cls._stop_all()

    # -- utilitaires -------------------------------------------------------------
    def _exceptions(self):
        # Les extensions du navigateur (chrome-extension://) ne sont pas Nebula.
        return [e for e in self.c.events if e.get("method") == "Runtime.exceptionThrown"
                and not str(((e.get("params") or {}).get("exceptionDetails") or {}).get("url", ""))
                .startswith("chrome-extension://")]

    def wait(self, sel, ms=10000):
        return self.c.js(f"{WAIT}({json.dumps(sel)}, {ms})")

    def open_state(self, state):
        write_fixture(self.srv.root, self.srv.port, state)
        self.c.call("Page.navigate", url="about:blank")
        time.sleep(0.2)
        self.c.call("Page.navigate", url=self.url + "/#/workspace/ws1/amelioration")
        ok = self.wait(f'.impr-next[data-state="{state}"]')
        txt = self.c.js("(document.querySelector('#content') || document.body).innerText.slice(0, 400)")
        self.assertTrue(ok, f"bandeau {state} absent : {txt}")

    def count(self, part):
        return self.c.js(f"window.__fetchLog.filter(u => u.includes({json.dumps(part)})).length")

    def assert_no_raw_html(self):
        """Données hostiles (ids de cas, hypothèses, pistes) affichées en texte."""
        self.assertEqual(self.c.js("document.querySelectorAll('.impr b b, .impr script, .impr i i').length"), 0)

    # -- états -----------------------------------------------------------------------
    def test_1_no_baseline(self):
        before = len(self._exceptions())
        self.open_state("no_baseline")
        acts = self.c.js("[...document.querySelectorAll('.impr-next [data-impr-act]')].map(b => b.dataset.imprAct)")
        self.assertEqual(acts, ["measure"])
        self.assertTrue(self.wait(".impr-timeline-empty"))
        rows = self.c.js("document.querySelectorAll('.impr-case[role=row]:not(.h)').length")
        self.assertEqual(rows, len(CASES))
        self.assertIn("fix-<b>xss</b>", self.c.js("document.querySelector('.impr-cases').innerText"))
        self.assertEqual(self.c.js("document.querySelectorAll('.impr-todo li').length"), 2)
        self.assertFalse(self.c.js("document.querySelector('[data-impr-auto]').checked"))
        self.assertTrue(self.c.js("imprPollingActive('ws1')"))
        self.assert_no_raw_html()
        self.assertFalse(self._exceptions()[before:], json.dumps(self._exceptions()[before:])[:600])

    def test_2_pending(self):
        before = len(self._exceptions())
        self.open_state("pending")
        acts = self.c.js("[...document.querySelectorAll('.impr-next [data-impr-act]')].map(b => b.dataset.imprAct)")
        self.assertEqual(acts, ["resolve", "abandon"])
        self.assertTrue(self.wait(".impr-team"))
        # Carte Équipe : sélecteurs verrouillés, boutons Trancher / Abandonner.
        self.assertTrue(self.c.js("[...document.querySelectorAll('.impr-team select')].every(s => s.disabled)"))
        self.assertEqual(self.c.js("[...document.querySelectorAll('.impr-team [data-impr-act]')].map(b => b.dataset.imprAct)"),
                         ["resolve", "abandon"])
        # Frise : 2 pastilles, clic = détail.
        self.assertEqual(self.c.js("document.querySelectorAll('.impr-dots .impr-dot').length"), 2)
        self.c.js("document.querySelector('.impr-dots .impr-dot.ok').click()")
        detail = self.c.js("(() => { const d = document.querySelector('[data-impr-detail]'); return d.hidden ? '' : d.innerText; })()")
        self.assertIn("a1b2c3d", detail)
        self.assertIn("par Nebula", detail)
        # Avertissements d'abonnement (plan forcé à pro) dans la carte Équipe.
        self.assertTrue(self.wait(".impr-team .impr-warn.alert"), "avertissement pro absent")
        self.assert_no_raw_html()
        self.assertFalse(self._exceptions()[before:], json.dumps(self._exceptions()[before:])[:600])

    def test_3_rejects_stop(self):
        before = len(self._exceptions())
        self.open_state("rejects_stop")
        acts = self.c.js("[...document.querySelectorAll('.impr-next [data-impr-act]')].map(b => b.dataset.imprAct)")
        self.assertEqual(acts, ["resume"])
        self.assertEqual(self.c.js("document.querySelectorAll('.impr-dots .impr-dot.err').length"), 3)
        self.assertFalse(self._exceptions()[before:], json.dumps(self._exceptions()[before:])[:600])

    def test_4_job_running_polling_et_fin(self):
        before = len(self._exceptions())
        self.open_state("job_running")
        self.assertTrue(self.wait(".impr-job"))
        panel = self.c.js("document.querySelector('.impr-job').innerText")
        self.assertIn("Mesure de la modification à l'essai", panel)
        self.assertIn("2", panel)
        self.assertTrue(self.c.js("!!document.querySelector('.impr-job [data-impr-act=cancel]')"))
        self.assertTrue(self.c.js("!!document.querySelector('.impr-job-bar[aria-valuenow=\"2\"]')"))
        self.assertTrue(self.c.js("[...document.querySelectorAll('.impr-team select')].every(s => s.disabled)"))
        # Polling 3 s du job.
        n0 = self.count("/improvement/job")
        time.sleep(3.6)
        self.assertGreater(self.count("/improvement/job"), n0, "aucun poll du job")
        # Onglet masqué : plus de requête.
        self.c.js("wsSelectTab('memoire', true)")
        time.sleep(0.5)
        n1 = self.count("/improvement/job")
        time.sleep(3.6)
        self.assertEqual(self.count("/improvement/job"), n1, "polling actif onglet masqué")
        # Retour sur l'onglet, puis fin du job : re-rendu + toast du verdict.
        self.c.js("wsSelectTab('amelioration', true)")
        write_job(self.srv.root, running=False)
        ended = self.wait('.impr-next:not([data-state="job_running"])', 20000)
        self.assertTrue(ended, "fin de job non vue : " + json.dumps(self.c.js(
            "({live: Object.values(IMPR_LIVE).map(l => ({running: l.running, inflight: l.inflight,"
            " hidden: !!l.host.closest('[hidden]'), reg: STATE.pagePollers.includes(l.timer)})),"
            " hash: location.hash, vis: document.visibilityState, hidden: document.hidden, log: window.__fetchLog.slice(-6)})")))
        self.assertFalse(self.c.js("!!document.querySelector('.impr-job')"))
        self.assertTrue(self.wait(".toast"))
        self.assertIn("gardée", self.c.js("[...document.querySelectorAll('.toast')].map(t => t.innerText).join(' | ')"))
        self.assertFalse(self._exceptions()[before:], json.dumps(self._exceptions()[before:])[:600])

    def test_5_polling_arrete_au_demontage(self):
        self.open_state("job_running")
        self.assertTrue(self.c.js("imprPollingActive('ws1')"))
        self.c.js("location.hash = '#/'")
        self.assertTrue(self.wait('[data-ws-card="ws1"]'))
        self.assertFalse(self.c.js("imprPollingActive('ws1')"))
        n = self.count("/improvement")
        time.sleep(3.6)
        self.assertEqual(self.count("/improvement"), n, "requêtes de l'onglet après démontage")

    def test_6_job_fini_avant_le_premier_poll(self):
        before = len(self._exceptions())
        self.open_state("ready")
        # Le job est deja termine (refuse : fichiers non commites) quand le
        # client recoit le 202 : toast + ligne du bandeau, sans polling.
        write_job(self.srv.root, running=False, verdict="refused", score=None,
                  dirty_paths=["agents/a<b>.md", "team.json"])
        self.c.js("""(() => {
          const host = document.querySelector('.impr-next').parentElement;
          API.postStatus = async () => ({ ok: true, status: 202, data: { ok: true, job: { job_id: '20261017-101500-abc123', status: 'running' } } });
          imprLaunch('ws1', host, 'iteration', document.querySelector('.impr-next [data-impr-act]'));
        })()""")
        toasts = ""
        for _ in range(40):
            toasts = self.c.js("[...document.querySelectorAll('.toast')].map(t => t.innerText).join(' | ')")
            if "refusée" in toasts:
                break
            time.sleep(0.25)
        self.assertIn("refusée", toasts)
        self.assertTrue(self.wait(".impr-next-last"))
        last = self.c.js("document.querySelector('.impr-next-last').innerText")
        self.assertIn("Dernière tentative refusée", last)
        self.assertIn("a<b>.md", last)
        self.assertEqual(self.c.js("document.querySelectorAll('.impr-next-last b').length"), 0)
        self.assertEqual(self.c.js("[...document.querySelectorAll('.toast')].filter(t => t.innerText.includes('refusée')).length"), 1)
        self.assertFalse(self._exceptions()[before:], json.dumps(self._exceptions()[before:])[:600])

    def test_9_aucune_exception_js(self):
        self.assertFalse(self._exceptions(), json.dumps(self._exceptions())[:600])


if __name__ == "__main__":
    unittest.main()
