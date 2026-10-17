"""Visite guidée principale (`TOURS.main`, app.js).

Deux niveaux :
- test statique (toujours exécuté, sans navigateur) : la visite couvre les
  modules, l'équipe d'agents, l'onglet Amélioration et les mises à jour, et
  son nombre d'étapes est cohérent avec help.js et le README ;
- test navigateur (facultatif, `NEBULA_UI_TESTS=1`, Edge/Chrome headless via
  CDP) : sur une installation vierge (aucun workspace), chaque étape atteint
  sa page, sa cible existe (ou l'étape est volontairement sans cible) et
  aucune exception JS n'apparaît.

    NEBULA_UI_TESTS=1 python -m unittest discover -s dashboard/tests -p test_tour.py
"""
from __future__ import annotations

import http.client
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unittest
from pathlib import Path

from _support import DASHBOARD_DIR, ORIGINAL_ENV, SANDBOX, ServerProcess, free_port, rmtree, rmtree_retry, write_json_file
from ui.cdp import CDP, page_ws
from ui.test_ui_smoke import BROWSER, INSTR

APP_JS = DASHBOARD_DIR / "app.js"
HELP_JS = DASHBOARD_DIR / "js" / "pages" / "help.js"
README = DASHBOARD_DIR.parent / "README.md"


def _tour_source() -> str:
    src = APP_JS.read_text(encoding="utf-8")
    a = src.index("const TOURS = {")
    b = src.index("function _tourResolveTarget")
    return src[a:b]


def _steps() -> list[str]:
    """Texte de chaque étape de TOURS.main (découpé sur les `title:`)."""
    block = _tour_source()
    parts = re.split(r"^\s{6}title:", block, flags=re.M)[1:]
    return parts


class TourStaticTests(unittest.TestCase):
    def test_etapes_attendues(self):
        steps = _steps()
        self.assertGreaterEqual(len(steps), 12)
        low = [s.lower() for s in steps]
        for label, words in {
            "modules": ("section <strong>modules</strong>", "ré-appliquer", "retirer"),
            "équipe": ("7 agents", "/team", "opus"),
            "amélioration": ("amélioration", "mesurée", "régression"),
            "mises à jour": ("mises à jour", "maj", "notes de version"),
        }.items():
            with self.subTest(etape=label):
                self.assertTrue(any(all(w in s for w in words) for s in low),
                                f"aucune étape ne couvre {label} ({words})")

    def test_pas_de_tiret_cadratin(self):
        self.assertNotIn("—", _tour_source())

    def test_nombre_d_etapes_coherent(self):
        n = len(_steps())
        help_src = HELP_JS.read_text(encoding="utf-8")
        readme = README.read_text(encoding="utf-8")
        self.assertIn(f"en {n} étapes", help_src)
        self.assertIn(f"({n} étapes, ~", help_src)
        self.assertIn(f"({n} étapes, spotlight", readme)
        self.assertIn(f"En {n} étapes", _tour_source())
        for src in (help_src, readme):
            for m in re.finditer(r"(\d+) étapes", src):
                if "visite" in src[max(0, m.start() - 200):m.end() + 60].lower() or "tour" in src[max(0, m.start() - 80):m.end()].lower():
                    self.assertEqual(int(m.group(1)), n, m.group(0))


class _FreshServer(ServerProcess):
    """Installation vierge : aucun workspace, un template et les deux modules présents."""

    def build(self) -> None:
        super().build()
        write_json_file(self.root / "dashboard" / "data" / "workspaces.json",
                        {"version": "1.0", "workspaces": []})
        for name in ("blank", "claude-self-improving", "claude-team"):
            src = DASHBOARD_DIR.parent / "templates" / name
            if src.is_dir():
                shutil.copytree(src, self.root / "templates" / name)


# Mémorise la cible réellement résolue par la visite à chaque étape.
HOOK = r"""
window.__tourTargets = [];
const _pos = _positionTourBubble;
_positionTourBubble = function (el) {
  const step = STATE.tour && STATE.tour.definition[STATE.tour.step];
  window.__tourTargets.push({
    step: STATE.tour ? STATE.tour.step : -1,
    found: !!el,
    tag: el ? el.tagName + (el.id ? '#' + el.id : '') + (el.className && el.className.baseVal === undefined ? '.' + String(el.className).split(' ')[0] : '') : null,
    primary: !!(el && step && step.target && el.matches(step.target.split(',')[0].trim())),
    hasLabel: !!(step && step.targetLabel),
  });
  return _pos(el);
};
true
"""


@unittest.skipUnless(os.environ.get("NEBULA_UI_TESTS") == "1",
                     "tests navigateur facultatifs : définir NEBULA_UI_TESTS=1")
@unittest.skipUnless(BROWSER, "aucun navigateur Chromium (Edge/Chrome) trouvé")
class TourUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = SANDBOX / "ui-tour"
        rmtree(cls.base)
        cls.srv = _FreshServer(cls.base, real_front=True)
        cls.srv.start()
        cls._post("/api/ui-state", {"onboarded": True})
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
    def _post(cls, path, body):
        conn = http.client.HTTPConnection("127.0.0.1", cls.srv.port, timeout=10)
        try:
            conn.request("POST", path, body=json.dumps(body),
                         headers={"Content-Type": "application/json", "X-Nebula-XHR": "1"})
            conn.getresponse().read()
        finally:
            conn.close()

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

    def _exceptions(self):
        return [e for e in self.c.events if e.get("method") == "Runtime.exceptionThrown"]

    def test_chaque_etape_atteint_sa_page_et_sa_cible(self):
        self.c.call("Page.navigate", url=self.url + "/#/")
        time.sleep(1.0)
        self.assertTrue(self.c.js(HOOK))
        defs = self.c.js("JSON.stringify(TOURS.main.map(s => ({title: s.title, navigate: s.navigate || null, target: s.target || null})))")
        steps = json.loads(defs)
        self.assertGreaterEqual(len(steps), 12)
        before = len(self._exceptions())
        current_hash = "#/"
        for i, st in enumerate(steps):
            with self.subTest(etape=i + 1, titre=st["title"]):
                self.c.js("window.__tourTargets = []; if (STATE.tour) endTour(); startTour('main', %d); true" % i)
                res = self.c.js("""(async (i, n) => { const t0 = Date.now();
                  while (Date.now() - t0 < 8000) {
                    const o = document.getElementById('tour-overlay');
                    const s = o && o.querySelector('.tour-bubble-step');
                    if (o && o.classList.contains('is-active') && s && s.textContent === (i + 1) + ' / ' + n
                        && window.__tourTargets.some(t => t.step === i))
                      return {ok: true, hash: location.hash, title: o.querySelector('.tour-bubble-title').textContent,
                              tgt: window.__tourTargets.filter(t => t.step === i).pop(),
                              body: o.querySelector('.tour-bubble-body').innerText.length,
                              err: !!document.querySelector('#content .error-box, #content .load-error')};
                    await new Promise(r => setTimeout(r, 50)); }
                  return {ok: false, hash: location.hash}; })(%d, %d)""" % (i, len(steps)))
                self.assertTrue(res["ok"], f"étape {i + 1} jamais affichée (hash {res['hash']})")
                if st["navigate"]:
                    current_hash = st["navigate"]
                self.assertEqual(res["hash"], current_hash, "page visée non atteinte")
                self.assertFalse(res["err"], "boîte d'erreur affichée sur la page visée")
                self.assertGreater(res["body"], 40)
                if st["target"] is None:
                    self.assertFalse(res["tgt"]["found"])  # étape volontairement sans cible
                else:
                    self.assertTrue(res["tgt"]["found"], f"cible introuvable : {st['target']}")
                    if "[data-overlay" in st["target"]:
                        self.assertTrue(res["tgt"]["primary"],
                                        f"carte du module absente, repli sur {res['tgt']['tag']}")
        self.c.js("if (STATE.tour) endTour(); true")
        new = self._exceptions()[before:]
        self.assertFalse(new, json.dumps(new)[:600])
        self.assertEqual(self.c.js("window.__fetchErrors"), [])


if __name__ == "__main__":
    unittest.main()
