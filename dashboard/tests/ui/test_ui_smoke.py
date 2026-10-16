"""Smoke test front : Edge/Chrome headless piloté par CDP (client stdlib).

FACULTATIF : ne tourne que si `NEBULA_UI_TESTS=1` ET qu'un navigateur
Chromium est trouvé (`NEBULA_BROWSER`, emplacements Edge/Chrome usuels, PATH).
Sinon : skip explicite. Serveur et profil navigateur en bac à sable, arrêt
des process par leur handle/PID (jamais par nom d'image).

    NEBULA_UI_TESTS=1 python -m unittest discover -s dashboard/tests
"""
from __future__ import annotations

import http.client
import json
import os
import shutil
import subprocess
import sys
import time
import unittest
from pathlib import Path

from _support import ORIGINAL_ENV, SANDBOX, ServerProcess, free_port, rmtree, rmtree_retry
from ui.cdp import CDP, page_ws

_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]
_NAMES = ("msedge", "microsoft-edge", "google-chrome", "chromium", "chromium-browser", "chrome")


def find_browser() -> str | None:
    env = os.environ.get("NEBULA_BROWSER")
    if env and Path(env).is_file():
        return env
    for c in _CANDIDATES:
        if Path(c).is_file():
            return c
    for n in _NAMES:
        found = shutil.which(n)
        if found:
            return found
    return None


BROWSER = find_browser() if os.environ.get("NEBULA_UI_TESTS") == "1" else None

# Journal des fetch + panne simulée de /api/overview (pilotée par sessionStorage).
INSTR = r"""
window.__fetchLog = [];
window.__fetchErrors = [];
const _f = window.fetch.bind(window);
window.fetch = async (url, opts) => {
  const u = String(url);
  window.__fetchLog.push(u);
  if (sessionStorage.getItem('failOverview') === '1' && u.startsWith('/api/overview'))
    throw new TypeError('Failed to fetch');
  const r = await _f(url, opts);
  if (r.status >= 500) window.__fetchErrors.push(r.status + ' ' + u);
  return r;
};
"""

WAIT = """(async (sel, ms) => { const t0 = Date.now(); while (Date.now() - t0 < ms) {
  if (document.querySelector(sel)) return true; await new Promise(r => setTimeout(r, 50)); }
  return false; })"""

# Page rendue : #content non vide, ni squelette ni boîte d'erreur, hash conservé.
RENDERED = """(async (hash, ms) => { const t0 = Date.now(); while (Date.now() - t0 < ms) {
  const c = document.querySelector('#content');
  const txt = c ? c.innerText.trim() : '';
  if (txt.length > 20 && !c.querySelector('.skeleton, [aria-busy="true"]'))
    return {ok: true, hash: location.hash,
            error: !!c.querySelector('.error-box, .load-error'), text: txt.slice(0, 200)};
  await new Promise(r => setTimeout(r, 50)); }
  return {ok: false, hash: location.hash, error: false, text: ''}; })"""

# Routes de premier niveau du routeur (js/router.js) + page d'un workspace.
ROUTES = ("#/", "#/mcps", "#/plugins", "#/skills", "#/templates", "#/tools",
          "#/aide", "#/workspace/ws1")


@unittest.skipUnless(os.environ.get("NEBULA_UI_TESTS") == "1",
                     "tests navigateur facultatifs : définir NEBULA_UI_TESTS=1")
@unittest.skipUnless(BROWSER, "aucun navigateur Chromium (Edge/Chrome) trouvé")
class UiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = SANDBOX / "ui"
        rmtree(cls.base)
        cls.srv = ServerProcess(cls.base, real_front=True)
        cls.srv.start()
        ws = cls.srv.root / "workspaces" / "ws1"
        (ws / ".mcp.json").write_text(json.dumps({"mcpServers": {"srv1": {}}}), encoding="utf-8")
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
                # Arbre du navigateur lancé, ciblé par SON PID.
                subprocess.run(["taskkill", "/PID", str(b.pid), "/T", "/F"], capture_output=True)
            else:
                b.terminate()
            try:
                b.wait(timeout=10)
            except subprocess.TimeoutExpired:
                b.kill()
        cls.srv.stop()
        # Le navigateur relâche son profil quelques instants après l'arrêt.
        rmtree_retry(cls.base)

    @classmethod
    def tearDownClass(cls):
        cls._stop_all()

    def nav(self, url):
        # Passage par about:blank : même URL à ancre = pas de rechargement.
        self.c.call("Page.navigate", url="about:blank")
        time.sleep(0.2)
        self.c.call("Page.navigate", url=url)
        time.sleep(0.4)

    def wait(self, sel, ms=8000):
        return self.c.js(f"{WAIT}({json.dumps(sel)}, {ms})")

    def test_1_accueil_et_requete_agregee(self):
        self.nav(self.url + "/#/")
        self.assertTrue(self.wait('[data-ws-card="ws1"]'), "carte du workspace absente")
        log = self.c.js("window.__fetchLog")
        self.assertEqual(log.count("/api/overview"), 1, log)
        self.assertFalse([u for u in log if "/api/workspaces/" in u and "/mcps" in u], log)
        self.assertEqual(self.c.js("JSON.stringify(STATE.wsMcps.ws1)"),
                         '{"active":["srv1"],"has_file":true}')

    def test_2_erreur_reseau_distincte_de_l_etat_vide(self):
        self.c.js("sessionStorage.setItem('failOverview','1')")
        try:
            self.nav(self.url + "/#/")
            self.assertTrue(self.wait(".load-error"), "boîte d'erreur absente")
            txt = self.c.js("document.querySelector('#content').innerText")
            self.assertNotIn("Pas encore de workspace", txt)
        finally:
            self.c.js("sessionStorage.removeItem('failOverview')")
        self.nav(self.url + "/#/")
        self.assertTrue(self.wait('[data-ws-card="ws1"]'))

    def test_3_toutes_les_pages_se_rendent(self):
        """Chaque route rend une page (sans erreur affichée ni 5xx d'API) et
        n'est pas redirigée vers l'accueil (route inconnue du routeur)."""
        for hash in ROUTES:
            with self.subTest(route=hash):
                before = len(self._exceptions())
                self.nav(self.url + "/" + hash)
                res = self.c.js(f"{RENDERED}({json.dumps(hash)}, 8000)")
                self.assertTrue(res["ok"], f"{hash} : page vide")
                # Un workspace sans onglet est complété par l'onglet par défaut.
                self.assertTrue(res["hash"] == hash or res["hash"].startswith(hash + "/"),
                                f"{hash} redirigé vers {res['hash']}")
                self.assertFalse(res["error"], f"{hash} : {res['text']}")
                self.assertEqual(self.c.js("window.__fetchErrors"), [], hash)
                new = self._exceptions()[before:]
                self.assertFalse(new, json.dumps(new)[:600])

    def test_4_adoption_groupee_depuis_un_dossier_parent(self):
        """Modale Adopter, mode « Plusieurs projets d'un dossier » : liste, déjà
        adopté grisé, adoption de la sélection, registre mis à jour. Le bouton
        Parcourir n'est jamais cliqué (il ouvrirait un vrai dialogue)."""
        parent = self.srv.root / "workspaces"
        (parent / "nouveau-projet").mkdir(exist_ok=True)
        (parent / "nouveau-projet" / "package.json").write_text("{}", encoding="utf-8")
        before = len(self._exceptions())
        self.nav(self.url + "/#/")
        self.assertTrue(self.wait('[data-ws-card="ws1"]'))
        self.c.js("modalRegisterExisting({ mode: 'parent' })")
        self.assertTrue(self.wait('.adopt-pane-parent [data-inspect-parent]'))
        self.assertEqual(self.c.js("getComputedStyle(document.querySelector('.adopt-pane-single')).display"), "none")
        self.c.js(f"document.querySelector('[name=parent_path]').value = {json.dumps(str(parent))};"
                  "document.querySelector('[data-inspect-parent]').click()")
        self.assertTrue(self.wait('.adopt-pane-parent .wizard-item'))
        rows = self.c.js("""[...document.querySelectorAll('.adopt-pane-parent .wizard-item')].map(r => ({
            name: r.querySelector('.mono').textContent, registered: r.classList.contains('is-registered'),
            checked: r.querySelector('input[data-cand]').checked,
            id: r.querySelector('.wizard-id-input').value }))""")
        by = {r["name"]: r for r in rows}
        self.assertTrue(by["ws1"]["registered"])
        self.assertFalse(by["ws1"]["checked"])
        self.assertTrue(by["nouveau-projet"]["checked"])
        self.assertEqual(by["nouveau-projet"]["id"], "nouveau-projet")
        footer = "document.querySelector('.modal-footer .btn-primary')"
        self.assertIn("(1)", self.c.js(f"{footer}.textContent"))
        self.c.js(f"{footer}.click()")
        ok = self.c.js("""(async () => { const t0 = Date.now(); while (Date.now() - t0 < 8000) {
            if (!document.querySelector('.adopt-pane-parent')) return true;
            await new Promise(r => setTimeout(r, 50)); } return false; })()""")
        self.assertTrue(ok, "la modale aurait dû se fermer après l'adoption")
        reg = json.loads((self.srv.root / "dashboard" / "data" / "workspaces.json").read_text(encoding="utf-8"))
        self.assertIn("nouveau-projet", [w["id"] for w in reg["workspaces"]])
        new = self._exceptions()[before:]
        self.assertFalse(new, json.dumps(new)[:600])

    def _exceptions(self):
        return [e for e in self.c.events if e.get("method") == "Runtime.exceptionThrown"]

    def test_9_aucune_exception_js(self):
        errs = [e for e in self.c.events if e.get("method") == "Runtime.exceptionThrown"]
        self.assertFalse(errs, json.dumps(errs)[:600])


if __name__ == "__main__":
    unittest.main()
