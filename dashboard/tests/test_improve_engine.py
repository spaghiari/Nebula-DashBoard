"""improve_engine : notation, verdict, liste blanche du critique, registre
improvements.md, mesure (dépôt git temporaire + faux binaire), phases
candidat et verdict, abandon. Aucun appel réel à `claude`."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from _support import DASHBOARD_DIR, SANDBOX, make_workspace, reset_sandbox, rmtree, write_json_file
from dashcore import api_team as team
from dashcore import improve_engine as ie

FAKE = DASHBOARD_DIR / "tests" / "fake_claude.py"
PY = sys.executable

MANIFEST = {
    "team": {"name": "t", "version": "1.0.0", "entrypoint": "orchestrator", "language": "fr"},
    "models": {"sonnet": {"id": "s", "usage": "rapide"}, "opus": {"id": "o", "usage": "profond"},
               "default": "sonnet"},
    "agents": [
        {"id": "orchestrator", "file": "team/agents/orchestrator.md", "model": "opus",
         "capabilities": ["filesystem"], "can_delegate_to": ["researcher"]},
        {"id": "researcher", "file": "team/agents/researcher.md", "model": "sonnet",
         "capabilities": ["filesystem"], "read_only": True},
        {"id": "executor", "file": "team/agents/executor.md", "capabilities": ["filesystem"]},
        {"id": "evaluator", "file": "team/agents/evaluator.md", "capabilities": ["knowledge"],
         "read_only": True},
        {"id": "critic", "file": "team/agents/critic.md", "model": "opus",
         "capabilities": ["filesystem"], "read_only": True},
    ],
    "improvement_loop": {"eval_set": "evals/eval-set.jsonl", "eval_set_locked": True,
                         "runs_per_eval": 2, "journal": "journal/changes.jsonl",
                         "accept_if": {"min_score_gain": 0.02, "max_regressions": 0}},
}
RESEARCHER_BODY = "# Rôle\nTu cherches.\n\n# Sortie\nTrois sections.\n"
SECRET_INPUT = "ENTREE-SECRETE-DU-CAS-C4"
CASES = [
    {"id": "c1", "agent": "researcher", "input": "Question ?", "grader": "regex",
     "check": r"\A## Conclusions", "target": "output", "tags": ["format"]},
    {"id": "c2", "agent": "executor", "input": "Écris tmp-eval/x.txt", "grader": "exact",
     "expected": "ok", "target": "file:tmp-eval/x.txt", "scope": "tmp-eval", "tags": ["scope"]},
    {"id": "c3", "agent": "executor", "input": "Écris tmp-eval/x.txt", "grader": "regex",
     "check": r"tmp-eval/x\.txt", "target": "diff", "scope": "tmp-eval", "tags": ["scope"]},
    {"id": "c4", "agent": "orchestrator", "input": SECRET_INPUT, "grader": "rubric",
     "expected": "un mot", "rubric": "1 si ok", "tags": ["format"]},
    {"id": "c5", "agent": "orchestrator", "input": "Dis ok", "grader": "test",
     "check": f"\"{PY}\" -c \"import sys;t=open(sys.argv[1],encoding='utf-8').read();"
              "sys.exit(0 if 'ok' in t else 1)\" \"{output}\"", "tags": ["code"]},
]
IMPROVEMENTS = ("# Registre\n\n- **[TODO] Le chercheur oublie le format** (P2, ajouté 2026-10-17 par nebula)\n"
                "  - Cible : `.claude/team/agents/researcher.md`\n\n"
                "- **[TODO] Autre item** (P2, ajouté 2026-10-17 par nebula)\n  - Cible : x\n")
GOOD_DIFF = ("--- a/.claude/team/agents/researcher.md\n+++ b/.claude/team/agents/researcher.md\n"
             "@@ -1,2 +1,3 @@\n # Rôle\n Tu cherches.\n+MARQUEUR : commence par ## Conclusions.\n")
NEUTRAL_DIFF = GOOD_DIFF.replace("MARQUEUR : commence", "Sois précis, commence")


def git(ws: Path, *args) -> str:
    p = subprocess.run(["git", *args], cwd=str(ws), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise AssertionError(f"git {args} : {p.stderr}")
    return p.stdout


def critic_output(diff=GOOD_DIFF, target=".claude/team/agents/researcher.md",
                  hypothesis="Le chercheur " + chr(0x2014) + " oublie le format", item="Le chercheur oublie le format"):
    return json.dumps({"hypothesis": hypothesis, "improvement_item": item, "target": target,
                       "kind": "prompt", "diff": diff, "expected_fixes": ["c1"], "risk": "faible"},
                      ensure_ascii=False)


def make_team_ws(ws_id="w1", with_git=True) -> Path:
    ws = make_workspace(ws_id)
    write_json_file(ws / ".claude" / "team.json", MANIFEST)
    bodies = ws / ".claude" / "team" / "agents"
    bodies.mkdir(parents=True, exist_ok=True)
    for a in MANIFEST["agents"]:
        (bodies / f"{a['id']}.md").write_text(
            RESEARCHER_BODY if a["id"] == "researcher" else f"# Rôle\nAgent {a['id']}.\n",
            encoding="utf-8")
    team.generate_agents(ws, {"name": ws_id, "label": ws_id}, {"prefix": "p"})
    ev = ws / ".claude" / "evals" / "eval-set.jsonl"
    ev.parent.mkdir(parents=True, exist_ok=True)
    ev.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in CASES), encoding="utf-8")
    (ws / ".claude" / "journal").mkdir(parents=True, exist_ok=True)
    (ws / ".claude" / "journal" / "changes.jsonl").write_text("", encoding="utf-8")
    (ws / ".claude" / "improvements.md").write_text(IMPROVEMENTS, encoding="utf-8")
    (ws / "other").mkdir(exist_ok=True)
    (ws / "other" / "keep.txt").write_text("v1\n", encoding="utf-8")
    if with_git:
        git(ws, "init", "-q")
        git(ws, "add", "-A")
        git(ws, "commit", "-q", "-m", "init")
    return ws


class EngineMixin:
    def setUp(self):
        reset_sandbox()
        self.ws = make_team_ws(with_git=getattr(self, "WITH_GIT", True))
        # Script, journal des appels et journaux bruts propres à chaque test.
        tag = self.id().rsplit(".", 2)[-2] + "-" + self.id().rsplit(".", 1)[-1]
        self.tmp = SANDBOX / "engine" / tag
        rmtree(self.tmp)
        self.tmp.mkdir(parents=True)
        self.script = self.tmp / "script.json"
        self.calls_log = self.tmp / "calls.jsonl"
        if self.calls_log.exists():
            self.calls_log.unlink()
        env = mock.patch.dict(os.environ, {"FAKE_CLAUDE_SCRIPT": str(self.script)})
        env.start()
        self.addCleanup(env.stop)
        self.rules()

    def rules(self, critic=None, good_marker="MARQUEUR", extra=()):
        rules = list(extra) + [
            {"match": "subagent_type: p-critic", "output": critic or critic_output()},
            {"match": "subagent_type: p-evaluator",
             "output": '{"id": "c4", "pass": true, "score": 0.8, "reason": "ok"}'},
            {"match": "subagent_type: p-researcher",
             "if_file": {"path": ".claude/agents/p-researcher.md", "contains": good_marker},
             "output": "## Conclusions\n- fait [CLAUDE.md]"},
            {"match": "subagent_type: p-researcher", "output": "pas de format"},
            {"match": "subagent_type: p-executor", "write_files": {"tmp-eval/x.txt": "ok"},
             "output": "fait"},
            {"match": "subagent_type: p-orchestrator", "output": "ok"},
        ]
        self.script.write_text(json.dumps({"log": str(self.calls_log), "rules": rules}),
                               encoding="utf-8")

    def ctx(self, **kw) -> ie.EngineContext:
        kw.setdefault("cmd", str(FAKE))
        kw.setdefault("log_dir", self.tmp / "logs")
        kw.setdefault("call_timeout", 60)
        return ie.EngineContext(self.ws, "w1", job_id="job-1", **kw)

    def calls(self) -> list[dict]:
        if not self.calls_log.exists():
            return []
        return [json.loads(x) for x in self.calls_log.read_text(encoding="utf-8").splitlines()]

    def journal(self) -> list[dict]:
        text = (self.ws / ".claude" / "journal" / "changes.jsonl").read_text(encoding="utf-8")
        return [json.loads(x) for x in text.splitlines() if x.strip()]


# --- Briques pures --------------------------------------------------------------------

class GradingTests(unittest.TestCase):
    def test_exact_et_regex(self):
        self.assertTrue(ie.grade_exact("  ok\n", "ok")["pass"])
        self.assertFalse(ie.grade_exact("ok!", "ok")["pass"])
        self.assertTrue(ie.grade_regex(r"^b$", "a\nb\nc")["pass"])  # re.M
        self.assertFalse(ie.grade_regex(r"\Ab", "a\nb")["pass"])
        bad = ie.grade_regex("(", "x")
        self.assertEqual((bad["pass"], bad["unrunnable"]), (False, True))

    def test_test_sortie_et_workspace(self):
        d = SANDBOX / "grade-ws"
        d.mkdir(exist_ok=True)
        (d / "marque.txt").write_text("m", encoding="utf-8")
        check = (f"\"{PY}\" -c \"import sys,os;t=open(sys.argv[1],encoding='utf-8').read();"
                 "assert t=='é ok';assert os.path.isfile(os.path.join(sys.argv[2],'marque.txt'));"
                 "assert os.path.isfile('marque.txt')\" \"{output}\" \"{workspace}\"")
        self.assertTrue(ie.grade_test(check, "é ok", d)["pass"])
        g = ie.grade_test(check, "autre", d)
        self.assertEqual((g["pass"], g["unrunnable"]), (False, False))

    def test_test_commande_introuvable(self):
        g = ie.grade_test("commande-inexistante-xyz --version", "x", SANDBOX)
        self.assertEqual((g["pass"], g["unrunnable"]), (False, True))

    def test_decide_verdict(self):
        v = ie.decide_verdict(0.8, ["c1", "c2"], 0.9, ["c2"], {"min_score_gain": 0.02, "max_regressions": 0})
        self.assertTrue(v["accepted"])
        self.assertEqual(v["regressions"], [])
        # Gain insuffisant.
        self.assertFalse(ie.decide_verdict(0.8, ["c1"], 0.81, [], None)["accepted"])
        # Gain exactement au seuil (flottants) : accepté.
        self.assertTrue(ie.decide_verdict(0.75, ["a"], 0.77, [], {"min_score_gain": 0.02})["accepted"])
        # Régression : rejet quel que soit le gain.
        v = ie.decide_verdict(0.5, ["c1", "c2"], 0.9, ["c3"], {})
        self.assertFalse(v["accepted"])
        self.assertEqual(v["regressions"], ["c3"])
        # max_regressions lu dans accept_if.
        self.assertTrue(ie.decide_verdict(0.5, ["c1", "c2"], 0.9, ["c3"], {"max_regressions": 1})["accepted"])

    def test_aggregate_exclut_les_inexecutables(self):
        def res(cid, ok, unrun=False):
            return {"id": cid, "agent": "a", "tags": ["t"], "pass": ok, "score": float(ok),
                    "unrunnable": unrun, "reason": "", "got": "", "expected": ""}
        r = ie.aggregate([res("a", True), res("b", False), res("c", False, unrun=True),
                          res("d", True)], "v")
        self.assertEqual(r["score"], 0.6667)  # 2 réussis sur 3 exécutables
        self.assertEqual((r["passed"], r["failed"], r["unrunnable"], r["total"]), (2, 1, 1, 4))
        self.assertEqual([f["id"] for f in r["failures"]], ["b"])
        self.assertEqual(r["unrunnable_ids"], ["c"])
        self.assertEqual(r["by_tag"]["t"], 0.6667)

    def test_comparaison_sur_les_cas_executables_des_deux_mesures(self):
        ids = ["c1", "c2", "c3", "c4", "c5"]
        # Inexécutable à la référence, réussi au candidat : aucun gain.
        c = ie.compare_on_runnable(ids, [], ["c1"], [], [])
        self.assertEqual((c["score_before"], c["score_after"], c["excluded"]), (1.0, 1.0, ["c1"]))
        # Inexécutable au candidat seulement : pas de régression.
        c = ie.compare_on_runnable(ids, ["c1"], [], [], ["c5"])
        self.assertEqual(ie.decide_verdict(c["score_before"], c["failures_before"], c["score_after"],
                                           c["failures_after"], None)["regressions"], [])
        self.assertEqual((c["score_before"], c["score_after"]), (0.75, 1.0))
        # Plus de la moitié des cas exclus (union) : non tranché.
        self.assertTrue(ie.compare_on_runnable(ids, [], ["c1", "c2"], [], ["c3"])["undecidable"])
        self.assertFalse(ie.compare_on_runnable(ids, [], ["c1"], [], ["c2"])["undecidable"])
        self.assertTrue(ie.compare_on_runnable([], [], [], [], [])["undecidable"])


class CandidateValidationTests(unittest.TestCase):
    def setUp(self):
        reset_sandbox()
        self.ws = make_team_ws("w1", with_git=False)
        (self.ws / ".claude" / "memory" / "conventions").mkdir(parents=True)
        (self.ws / ".claude" / "memory" / "conventions" / "x.md").write_text("a\n", encoding="utf-8")

    def test_chemins_refuses_et_acceptes(self):
        for rel in (".claude/memory/../team/agents/critic.md",
                    ".claude/memory/../evals/eval-set.jsonl",
                    ".claude/memory/../../outside.md", ".claude/memory/./x.md",
                    str(self.ws / ".claude" / "memory" / "x.md"), "/abs/x.md",
                    ".claude\\memory\\x.md", ".claude/team/agents/critic.md",
                    ".claude/evals/eval-set.jsonl", ".claude/agents/p-researcher.md",
                    ".claude/settings.json", "CLAUDE.md"):
            with self.subTest(rel=rel):
                self.assertFalse(ie.target_allowed(self.ws, rel, MANIFEST)[0])
        for rel in (".claude/memory/conventions/x.md", ".claude/team/agents/researcher.md",
                    ".claude/team.json", ".claude/commands/pipeline.md"):
            self.assertTrue(ie.target_allowed(self.ws, rel, MANIFEST)[0], rel)

    def test_casse_differente_du_chemin_reel_refusee(self):
        # Sous Windows, `Critic.md` désigne `critic.md` : chemin réel exigé à
        # l'identique ; ailleurs, la liste noire insensible à la casse refuse.
        for rel in (".claude/team/agents/Critic.md", ".claude/team/agents/CRITIC.MD",
                    ".Claude/team/agents/critic.md", ".claude/Evals/eval-set.jsonl"):
            with self.subTest(rel=rel):
                ok, why = ie.target_allowed(self.ws, rel, MANIFEST)
                self.assertFalse(ok)
                self.assertTrue(why)
        critic = self.ws / ".claude" / "team" / "agents" / "critic.md"
        original = critic.read_bytes()
        v = ie.validate_candidate({"target": ".claude/team/agents/Critic.md", "diff":
                                   "--- a/.claude/team/agents/Critic.md\n+++ b/.claude/team/agents/Critic.md\n"
                                   "@@ -1,2 +1,2 @@\n # Rôle\n-Agent critic.\n+Agent complaisant.\n"},
                                  self.ws, MANIFEST)
        self.assertFalse(v["ok"])
        self.assertEqual(critic.read_bytes(), original)

    def test_liste_noire_insensible_a_la_casse(self):
        for rel in (".claude/team/agents/CRITIC.md", ".CLAUDE/EVALS/eval-set.jsonl",
                    ".claude/Evals", ".claude/commands/Improve.md"):
            self.assertTrue(ie.is_forbidden_target(rel, MANIFEST), rel)
            self.assertTrue(ie.is_forbidden_target(rel, None), rel)
        m = json.loads(json.dumps(MANIFEST))
        m["agents"][-1]["file"] = "team/agents/juge.md"
        m["improvement_loop"]["eval_set"] = "jeux/eval-set.jsonl"
        self.assertTrue(ie.is_forbidden_target(".claude/team/agents/JUGE.md", m))
        self.assertTrue(ie.is_forbidden_target(".claude/Jeux/eval-set.jsonl", m))
        self.assertFalse(ie.is_forbidden_target(".claude/team/agents/researcher.md", MANIFEST))

    def test_commandes_de_la_boucle_refusees(self):
        for name in ("improve", "eval", "eval-add", "team"):
            with self.subTest(name=name):
                self.assertFalse(ie.target_allowed(self.ws, f".claude/commands/{name}.md", MANIFEST)[0])
        self.assertTrue(ie.target_allowed(self.ws, ".claude/commands/pipeline.md", MANIFEST)[0])
        self.assertTrue(ie.target_allowed(self.ws, ".claude/commands/evaluate.md", MANIFEST)[0])

    def test_scope_sous_claude_ou_git_insensible_a_la_casse(self):
        for scope in (".Claude/x", ".CLAUDE", ".Git/hooks", ".claude/memory"):
            with self.subTest(scope=scope):
                got, why = ie._scope_of(self.ws, {"scope": scope})
                self.assertIsNone(got)
                self.assertIn("refusé", why)
        self.assertEqual(ie._scope_of(self.ws, {"scope": "tmp-eval/"}), ("tmp-eval", ""))
        # Casse différente d'un dossier existant : refusée (chemin réel exigé).
        if sys.platform == "win32":
            got, why = ie._scope_of(self.ws, {"scope": "Other"})
            self.assertIsNone(got)
            self.assertIn("casse", why)

    def test_lien_ou_jonction_hors_projet_refuse(self):
        outside = SANDBOX / "dehors-engine"
        rmtree(outside)
        outside.mkdir()
        (outside / "x.md").write_text("a\n", encoding="utf-8")
        link = self.ws / ".claude" / "memory" / "lien"
        if sys.platform == "win32":
            r = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)],
                               capture_output=True, text=True)
            if r.returncode != 0:
                self.skipTest("jonction impossible")
        else:
            os.symlink(outside, link)
        try:
            self.assertFalse(ie.target_allowed(self.ws, ".claude/memory/lien/x.md", MANIFEST)[0])
            v = ie.validate_candidate({"target": ".claude/memory/lien/x.md", "diff":
                                       "--- a/.claude/memory/lien/x.md\n+++ b/.claude/memory/lien/x.md\n"
                                       "@@ -1 +1 @@\n-a\n+b\n"}, self.ws, MANIFEST)
            self.assertFalse(v["ok"])
            self.assertEqual((outside / "x.md").read_text(encoding="utf-8"), "a\n")
        finally:
            os.rmdir(link) if sys.platform == "win32" else link.unlink()

    def test_liste_noire_sans_manifeste(self):
        # Liste noire de config.py appliquée même sans manifeste (défense en profondeur).
        self.assertFalse(ie.target_allowed(self.ws, ".claude/team/agents/critic.md", None)[0])

    def test_corps_du_critique_declare_ailleurs_refuse(self):
        m = json.loads(json.dumps(MANIFEST))
        m["agents"][-1]["file"] = "team/agents/juge.md"
        self.assertFalse(ie.target_allowed(self.ws, ".claude/team/agents/juge.md", m)[0])

    def _team_diff(self, old: str, new: str) -> str:
        text = (self.ws / ".claude" / "team.json").read_text(encoding="utf-8")
        lines = text.split("\n")
        i = next(k for k, line in enumerate(lines) if line == old)
        return ("--- a/.claude/team.json\n+++ b/.claude/team.json\n"
                f"@@ -{i + 1},1 +{i + 1},1 @@\n-{old}\n+{new}\n")

    def test_team_json_section_agents_seulement(self):
        text = (self.ws / ".claude" / "team.json").read_text(encoding="utf-8")
        model_line = next(x for x in text.split("\n") if '"model": "sonnet"' in x and x.startswith("      "))
        ok = ie.validate_candidate({"target": ".claude/team.json",
                                    "diff": self._team_diff(model_line, model_line.replace("sonnet", "opus"))},
                                   self.ws, MANIFEST)
        self.assertTrue(ok["ok"], ok["reason"])
        bad = ie.validate_candidate({"target": ".claude/team.json",
                                     "diff": self._team_diff(model_line, model_line.replace("sonnet", "gpt"))},
                                    self.ws, MANIFEST)
        self.assertIn("modèle invalide", bad["reason"])
        loop_line = next(x for x in text.split("\n") if '"runs_per_eval"' in x)
        bad = ie.validate_candidate({"target": ".claude/team.json",
                                     "diff": self._team_diff(loop_line, loop_line.replace("2", "1"))},
                                    self.ws, MANIFEST)
        self.assertIn("improvement_loop", bad["reason"])
        # Rien n'a été écrit (validation sans effet).
        self.assertEqual((self.ws / ".claude" / "team.json").read_text(encoding="utf-8"), text)

    def test_diff_multi_cible_ou_incoherent(self):
        v = ie.validate_candidate({"target": ".claude/team/agents/researcher.md, .claude/team.json",
                                   "diff": GOOD_DIFF}, self.ws, MANIFEST)
        self.assertFalse(v["ok"])
        v = ie.validate_candidate({"target": ".claude/team/agents/executor.md", "diff": GOOD_DIFF},
                                  self.ws, MANIFEST)
        self.assertIn("cible annoncée", v["reason"])

    def test_sortie_du_critique(self):
        d = ie.parse_critic_output("voici :\n```json\n" + critic_output() + "\n```")
        self.assertEqual(d["target"], ".claude/team/agents/researcher.md")
        with self.assertRaises(ie.EngineError):
            ie.parse_critic_output('{"target": "x"}')


class ImprovementsRegisterTests(unittest.TestCase):
    def test_items_todo_et_mise_a_jour(self):
        p = SANDBOX / "improvements-test.md"
        p.write_text(IMPROVEMENTS, encoding="utf-8")
        self.assertEqual([t["title"] for t in ie.extract_todo_items(IMPROVEMENTS)],
                         ["Le chercheur oublie le format", "Autre item"])
        self.assertTrue(ie.update_improvement_item(p, "Le chercheur oublie le format", "DONE 2026-10-17",
                                                   "Mesure : score 0.8 -> 1.0"))
        text = p.read_text(encoding="utf-8")
        self.assertIn("- **[DONE 2026-10-17] Le chercheur oublie le format**", text)
        self.assertIn("  - Cible : `.claude/team/agents/researcher.md`\n  - Mesure : score 0.8 -> 1.0\n", text)
        self.assertIn("- **[TODO] Autre item**", text)
        self.assertEqual(p.with_name(p.name + ".bak").read_text(encoding="utf-8"), IMPROVEMENTS)
        self.assertFalse(ie.update_improvement_item(p, "Inconnu", "ABANDONED", "x"))


# --- Mesure ------------------------------------------------------------------------------

class OnSpawnTests(EngineMixin, unittest.TestCase):
    def test_call_transmet_on_spawn(self):
        seen = []
        c = self.ctx(on_spawn=seen.append)
        c.call("subagent_type: p-researcher\nQ ?", expect_agent="p-researcher",
               allowed_tools=["Agent", "Read"], label="spawn")
        self.assertEqual(len(seen), 1)
        self.assertGreater(seen[0].pid, 0)

    def test_on_spawn_defaut_none(self):
        self.assertIsNone(self.ctx().on_spawn)


class MeasureTests(EngineMixin, unittest.TestCase):
    def test_format_et_hors_scope_intact(self):
        # Modifications de l'utilisateur hors scope : jamais touchées.
        (self.ws / "other" / "keep.txt").write_text("v2 utilisateur\n", encoding="utf-8")
        (self.ws / "notes.txt").write_text("brouillon\n", encoding="utf-8")
        r = ie.measure(self.ctx())
        for k in ("config_version", "score", "passed", "failed", "total", "unrunnable", "by_tag",
                  "by_agent", "failures"):
            self.assertIn(k, r)
        self.assertEqual(r["config_version"], team.team_config_hash(self.ws, "w1"))
        self.assertEqual((r["total"], r["passed"], r["failed"], r["unrunnable"]), (5, 4, 1, 0))
        self.assertEqual(r["unrunnable_ids"], [])
        self.assertEqual(r["score"], 0.8)
        self.assertEqual([f["id"] for f in r["failures"]], ["c1"])
        self.assertEqual(r["by_agent"], {"executor": 1.0, "orchestrator": 1.0, "researcher": 0.0})
        self.assertEqual(r["by_tag"]["format"], 0.5)
        self.assertEqual(r["failures"][0]["got"], "pas de format")
        self.assertEqual((self.ws / "other" / "keep.txt").read_text(encoding="utf-8"), "v2 utilisateur\n")
        self.assertEqual((self.ws / "notes.txt").read_text(encoding="utf-8"), "brouillon\n")
        self.assertFalse((self.ws / "tmp-eval").exists())  # scope restauré
        self.assertEqual(r["spend"]["calls"], 7)  # 5 relais + 2 passes rubric
        self.assertAlmostEqual(r["spend"]["cost_usd"], 0.84)

    def test_rubric_en_aveugle_sans_input(self):
        ie.measure(self.ctx())
        evals = [c for c in self.calls() if "subagent_type: p-evaluator" in c["stdin"]]
        self.assertEqual(len(evals), 2)  # runs_per_eval
        for c in evals:
            self.assertNotIn(SECRET_INPUT, c["stdin"])
            self.assertIn("ID: c4\nSORTIE: ok", c["stdin"])
            self.assertIn("ATTENDU: un mot", c["stdin"])
            self.assertIn("GRILLE: 1 si ok", c["stdin"])
        # Le relais du cas reçoit bien son entrée, et des outils d'écriture
        # limités au scope pour les cas à scope seulement.
        relay = next(c for c in self.calls() if SECRET_INPUT in c["stdin"])
        self.assertFalse(any(a.startswith("Write") for a in relay["argv"]))
        ex = next(c for c in self.calls() if "subagent_type: p-executor" in c["stdin"])
        self.assertIn("Write(./tmp-eval/**)", ex["argv"])
        for c in self.calls():
            self.assertNotIn("--bare", c["argv"])
            self.assertIn("Bash", c["argv"][c["argv"].index("--disallowedTools") + 1:])

    def test_scope_non_propre_inexecutable(self):
        (self.ws / "tmp-eval").mkdir()
        (self.ws / "tmp-eval" / "a-moi.txt").write_text("à garder\n", encoding="utf-8")
        r = ie.measure(self.ctx())
        bad = {c["id"]: c for c in r["cases"]}
        self.assertTrue(bad["c2"]["unrunnable"])
        self.assertIn("non propre", bad["c2"]["reason"])
        self.assertEqual((self.ws / "tmp-eval" / "a-moi.txt").read_text(encoding="utf-8"), "à garder\n")

    def test_quota_arrete_la_mesure_et_restaure(self):
        self.rules(extra=[{"match": "subagent_type: p-executor", "write_files": {"tmp-eval/x.txt": "ok"},
                           "final_text": "You've hit your session limit · resets 3:45pm",
                           "result": {"is_error": True}}])
        with self.assertRaises(ie.QuotaReached) as cm:
            ie.measure(self.ctx())
        # Heure brute ou ISO selon `claude_runner.parse_reset` (corrigé en parallèle).
        # Le lanceur convertit l'heure du message en ISO local (parse_reset).
        self.assertRegex(cm.exception.reset or "", r"^\d{4}-\d{2}-\d{2}T15:45:00$")
        self.assertFalse((self.ws / "tmp-eval").exists())

    def test_agents_absents_et_budget(self):
        self.rules(extra=[{"agents": [], "output": "x"}])
        with self.assertRaises(ie.AgentsMissing):
            ie.measure(self.ctx())
        self.rules()
        with self.assertRaises(ie.BudgetExceeded):
            ie.measure(self.ctx(max_usd=0.2))

    def test_annulation(self):
        c = self.ctx()
        c.cancel.set()
        with self.assertRaises(ie.Cancelled):
            ie.measure(c)


class NoGitMeasureTests(EngineMixin, unittest.TestCase):
    WITH_GIT = False

    def test_cas_a_scope_inexecutables_sans_git(self):
        r = ie.measure(self.ctx())
        cases = {c["id"]: c for c in r["cases"]}
        for cid in ("c2", "c3"):
            self.assertTrue(cases[cid]["unrunnable"])
            self.assertIn("sans dépôt git", cases[cid]["reason"])
        self.assertEqual(r["unrunnable"], 2)
        self.assertEqual(r["unrunnable_ids"], ["c2", "c3"])

    def test_ligne_pending_porte_unrunnable_ids(self):
        res = ie.candidate_phase(self.ctx())
        line = self.journal()[-1]
        self.assertEqual(line["unrunnable"], 2)
        self.assertEqual(line["unrunnable_ids"], ["c2", "c3"], res["status"])


# --- Phases --------------------------------------------------------------------------------

class BaselineFileTests(EngineMixin, unittest.TestCase):
    def bpath(self):
        return self.ws / ".claude" / "journal" / "baseline.json"

    def test_measure_ecrit_baseline_json_sans_toucher_au_journal(self):
        jp = self.ws / ".claude" / "journal" / "changes.jsonl"
        jb = jp.read_bytes() if jp.exists() else None
        r = ie.measure(self.ctx())
        b = json.loads(self.bpath().read_text(encoding="utf-8"))
        self.assertEqual(b["config_version"], r["config_version"])
        self.assertEqual((b["score"], b["failures"], b["unrunnable"], b["cases"], b["runner"]),
                         (0.8, ["c1"], 0, 5, "nebula"))
        self.assertTrue(b["measured_at"])
        self.assertEqual(jp.read_bytes() if jp.exists() else None, jb)
        st = team.improvement_state("w1")[1]
        self.assertTrue(st["baseline_current"])
        self.assertEqual(st["stats"]["last_score"], 0.8)
        lm = st["last_measure"]
        self.assertEqual((lm["score"], lm["unrunnable"], lm["current"]), (0.8, 0, True))
        self.assertNotEqual(st["next_step"]["state"], "no_baseline")

    def test_iteration_reutilise_baseline_json(self):
        ie.measure(self.ctx())
        n = len(self.calls())
        res = ie.candidate_phase(self.ctx())
        self.assertTrue(res["baseline"]["reused"])
        self.assertEqual(res["baseline"]["score"], 0.8)
        self.assertEqual(len(self.calls()), n + 1)  # critique seul, pas de re-mesure

    def test_ignoree_si_empreinte_differente_ou_inexecutable(self):
        ie.measure(self.ctx())
        b = json.loads(self.bpath().read_text(encoding="utf-8"))
        h = team.team_config_hash(self.ws, "w1")
        self.assertIsNotNone(ie._baseline_from_file(self.ws, h))
        self.assertIsNone(ie._baseline_from_file(self.ws, "autre"))
        b["unrunnable"] = 1
        self.bpath().write_text(json.dumps(b), encoding="utf-8")
        self.assertIsNone(ie._baseline_from_file(self.ws, h))

    def test_le_plus_recent_gagne(self):
        ie.measure(self.ctx())
        h = team.team_config_hash(self.ws, "w1")
        line = {"iteration": 1, "status": "rejected", "date": "2000-01-01", "config_version": h,
                "score_before": 0.5, "failures_before": ["c1", "c2"], "unrunnable": 0}
        ie.append_journal(self.ws, None, line)
        entries = ie.read_journal(self.ws, None)
        self.assertEqual(ie._baseline_reusable(self.ws, entries, h)["score"], 0.8)
        entries[0]["date"] = "2999-01-01"
        self.assertEqual(ie._baseline_reusable(self.ws, entries, h)["score"], 0.5)
        entries[0]["date"] = ""
        self.assertEqual(ie._baseline_reusable(self.ws, entries, h)["score"], 0.5)

    def test_relais_demande_run_in_background_false(self):
        self.assertIn("run_in_background: false", ie.relay_prompt("p-critic", "x"))


class PhaseTests(EngineMixin, unittest.TestCase):
    def test_candidat_pending_vu_par_improvement_state(self):
        base_hash = team.team_config_hash(self.ws, "w1")
        res = ie.candidate_phase(self.ctx())
        self.assertEqual(res["status"], "pending")
        n = res["iteration"]
        self.assertEqual(n, 1)
        before = self.ws / ".claude" / "journal" / "pending" / "1" / "researcher.md.before"
        self.assertEqual(before.read_text(encoding="utf-8"), RESEARCHER_BODY)
        self.assertIn("MARQUEUR", (self.ws / ".claude" / "agents" / "p-researcher.md").read_text(encoding="utf-8"))
        line = self.journal()[-1]
        self.assertEqual((line["status"], line["runner"], line["job_id"], line["branch"]),
                         ("pending", "nebula", "job-1", None))
        self.assertEqual(line["baseline_version"], base_hash)
        self.assertEqual(line["failures_before"], ["c1"])
        self.assertEqual(line["score_before"], 0.8)
        self.assertEqual((line["unrunnable"], line["unrunnable_ids"]), (0, []))
        self.assertGreater(line["cost_usd"], 0)
        self.assertEqual(set(line["tokens"]), {"input", "output", "cache_read", "cache_creation"})
        _, st = team.improvement_state("w1")
        self.assertEqual(st["pending"]["iteration"], 1)
        self.assertTrue(st["pending"]["in_place"])
        # Critique : entrée avec les échecs, les items [TODO] et les cibles.
        crit = next(c for c in self.calls() if "subagent_type: p-critic" in c["stdin"])
        self.assertIn("c1", crit["stdin"])
        self.assertIn("Le chercheur oublie le format", crit["stdin"])
        self.assertIn(".claude/memory/**/*.md", crit["stdin"])
        # Une seule itération en attente à la fois.
        with self.assertRaises(ie.ConflictError):
            ie.candidate_phase(self.ctx())

    def test_diff_invalide_rejete_sans_mesure(self):
        bad = critic_output(diff=GOOD_DIFF.replace("researcher.md", "../evals/eval-set.jsonl"),
                            target=".claude/evals/eval-set.jsonl")
        self.rules(critic=bad)
        evals_before = (self.ws / ".claude" / "evals" / "eval-set.jsonl").read_bytes()
        res = ie.candidate_phase(self.ctx())
        self.assertEqual(res["status"], "rejected")
        line = self.journal()[-1]
        self.assertEqual(line["status"], "rejected")
        self.assertTrue(line["reason"])
        self.assertFalse((self.ws / ".claude" / "journal" / "pending" / "1").exists())
        self.assertEqual((self.ws / ".claude" / "evals" / "eval-set.jsonl").read_bytes(), evals_before)
        # Baseline (7 appels) + critique, aucune mesure du candidat.
        self.assertEqual(len(self.calls()), 8)
        # La ligne rejetée sert de baseline à l'itération suivante (rien remesuré).
        self.rules()
        res2 = ie.candidate_phase(self.ctx())
        self.assertTrue(res2["baseline"]["reused"])
        self.assertEqual(res2["iteration"], 2)
        self.assertEqual(len(self.calls()), 9)

    def test_iteration_acceptee_et_commit(self):
        res = ie.run_iteration(self.ctx())
        v = res["verdict"]
        self.assertEqual(v["status"], "accepted", v["entry"].get("reason"))
        self.assertTrue(v["commit"])
        msg = git(self.ws, "log", "-1", "--format=%B")
        self.assertTrue(msg.startswith("update(p): improve/1 - Le chercheur - oublie le format"), msg)
        self.assertNotIn(chr(0x2014), msg)
        self.assertNotIn(chr(0x2013), msg)
        self.assertNotIn("Co-Authored-By", msg)
        files = [x for x in git(self.ws, "show", "--name-only", "--format=", "HEAD").splitlines() if x]
        self.assertEqual(sorted(files), [".claude/agents/p-researcher.md",
                                         ".claude/team/agents/researcher.md"])
        line = self.journal()[-1]
        self.assertEqual((line["status"], line["score_after"], line["regressions"]), ("accepted", 1.0, []))
        self.assertEqual(line["failures_after"], [])
        self.assertEqual(line["commit"], v["commit"])
        self.assertEqual((line["unrunnable"], line["unrunnable_ids"]), (0, []))
        self.assertEqual(line["config_version"], team.team_config_hash(self.ws, "w1"))
        self.assertFalse((self.ws / ".claude" / "journal" / "pending" / "1").exists())
        imp = (self.ws / ".claude" / "improvements.md").read_text(encoding="utf-8")
        self.assertRegex(imp, r"\[DONE \d{4}-\d{2}-\d{2}\] Le chercheur oublie le format")
        self.assertIn("Mesure : score 0.8 -> 1.0 (gain +0.20, 0 régression), commit", imp)
        _, st = team.improvement_state("w1")
        self.assertIsNone(st["pending"])
        self.assertTrue(st["baseline_current"])

    def test_iteration_rejetee_restaure_la_baseline(self):
        self.rules(critic=critic_output(diff=NEUTRAL_DIFF))
        head = git(self.ws, "rev-parse", "HEAD")
        res = ie.run_iteration(self.ctx())
        v = res["verdict"]
        self.assertEqual(v["status"], "rejected")
        pend = self.journal()[-2]
        self.assertEqual(pend["status"], "pending")
        # Empreinte après rejet == baseline mesurée.
        self.assertEqual(team.team_config_hash(self.ws, "w1"), pend["baseline_version"])
        self.assertEqual((self.ws / ".claude" / "team" / "agents" / "researcher.md").read_text(encoding="utf-8"),
                         RESEARCHER_BODY)
        line = self.journal()[-1]
        self.assertEqual(line["config_version"], pend["baseline_version"])
        self.assertEqual(line["diff_archive"], ".claude/journal/rejected/1/candidate.diff")
        self.assertIn("Sois précis", (self.ws / line["diff_archive"]).read_text(encoding="utf-8"))
        self.assertFalse((self.ws / ".claude" / "journal" / "pending" / "1").exists())
        self.assertEqual(git(self.ws, "rev-parse", "HEAD"), head)  # aucun commit
        imp = (self.ws / ".claude" / "improvements.md").read_text(encoding="utf-8")
        self.assertIn("[ABANDONED] Le chercheur oublie le format", imp)
        self.assertIn("Mesure : score 0.8 -> 0.8 (gain +0.00, régressions : aucune), itération 1", imp)

    def test_candidat_altere_rejete(self):
        ie.candidate_phase(self.ctx())
        body = self.ws / ".claude" / "team" / "agents" / "executor.md"
        body.write_text("# Rôle\nmodifié entre les sessions\n", encoding="utf-8")
        team.generate_agents(self.ws, {"name": "w1"}, {"regenerate": True})
        n_calls = len(self.calls())
        res = ie.verdict_phase(self.ctx())
        self.assertEqual((res["status"], res["reason"]), ("rejected", "candidat altéré"))
        self.assertEqual(len(self.calls()), n_calls)  # aucune mesure
        self.assertEqual((self.ws / ".claude" / "team" / "agents" / "researcher.md").read_text(encoding="utf-8"),
                         RESEARCHER_BODY)

    def test_abandon_pending_nebula_et_manuelle(self):
        ie.candidate_phase(self.ctx())
        pend = self.journal()[-1]
        res = ie.abandon_pending(self.ctx())
        self.assertEqual(res["restored_from"], "before")
        self.assertEqual(team.team_config_hash(self.ws, "w1"), pend["baseline_version"])
        self.assertEqual(self.journal()[-1]["reason"], "abandonné")
        with self.assertRaises(ie.ConflictError):
            ie.abandon_pending(self.ctx())
        # Pending posée par /improve manuel (sans runner), avec sa sauvegarde.
        target = self.ws / ".claude" / "team" / "agents" / "executor.md"
        original = target.read_text(encoding="utf-8")
        bdir = self.ws / ".claude" / "journal" / "pending" / "3"
        bdir.mkdir(parents=True)
        (bdir / "executor.md.before").write_text(original, encoding="utf-8")
        target.write_text(original + "ajout manuel\n", encoding="utf-8")
        ie.append_journal(self.ws, MANIFEST, {"iteration": 3, "target": ".claude/team/agents/executor.md",
                                              "status": "pending", "config_version": "x"})
        ie.abandon_pending(self.ctx())
        self.assertEqual(target.read_text(encoding="utf-8"), original)

    # Relais en échec (aucune délégation) selon que le candidat est en place.
    CAND = {"path": ".claude/agents/p-researcher.md", "contains": "MARQUEUR"}

    def test_inexecutable_a_la_reference_puis_reussi_pas_de_gain(self):
        self.rules(extra=[{"match": "subagent_type: p-researcher", "unless_file": self.CAND,
                           "no_delegation": True}])
        v = ie.run_iteration(self.ctx())["verdict"]
        # Sans exclusion : 0,8 -> 1,0 et faux gain accepté.
        self.assertEqual(v["status"], "rejected", v["entry"].get("reason"))
        self.assertEqual(v["verdict"]["gain"], 0.0)
        self.assertEqual(v["verdict"]["comparison"]["excluded"], ["c1"])
        line = self.journal()[-1]
        self.assertEqual(line["excluded_unrunnable"], ["c1"])
        self.assertEqual((line["score_before_compared"], line["score_after_compared"]), (1.0, 1.0))

    def test_relais_en_echec_au_candidat_sur_cas_reussi_est_une_regression(self):
        self.rules(extra=[{"match": "Dis ok", "if_file": self.CAND, "no_delegation": True}])
        v = ie.run_iteration(self.ctx())["verdict"]
        # c5 réussissait à la référence : échec au candidat, donc régression.
        self.assertEqual(v["status"], "rejected", v["entry"].get("reason"))
        self.assertEqual(v["verdict"]["regressions"], ["c5"])
        self.assertEqual(v["verdict"]["comparison"]["excluded"], [])

    def test_majorite_inexecutable_reste_pending(self):
        self.rules(extra=[{"match": "subagent_type: p-(executor|orchestrator)",
                           "no_delegation": True}])
        head = git(self.ws, "rev-parse", "HEAD")
        v = ie.run_iteration(self.ctx())["verdict"]
        self.assertEqual(v["status"], "pending")
        self.assertIn("non tranché", v["reason"])
        self.assertEqual(self.journal()[-1]["status"], "pending")
        self.assertIn("MARQUEUR", (self.ws / ".claude" / "team" / "agents" / "researcher.md")
                      .read_text(encoding="utf-8"))
        self.assertTrue((self.ws / ".claude" / "journal" / "pending" / "1").is_dir())
        self.assertEqual(git(self.ws, "rev-parse", "HEAD"), head)

    def test_configuration_non_commitee_refusee_sans_rien_ecrire(self):
        agent = self.ws / ".claude" / "agents" / "p-executor.md"
        edited = agent.read_text(encoding="utf-8") + "\nretouche manuelle\n"
        agent.write_text(edited, encoding="utf-8")
        researcher = self.ws / ".claude" / "team" / "agents" / "researcher.md"
        res = ie.candidate_phase(self.ctx())
        self.assertEqual(res["status"], "rejected")
        self.assertEqual(res["reason"], ie.DIRTY_TEAM_REASON)
        self.assertIn("commite-les ou annule-les", res["reason"])
        self.assertEqual(self.calls(), [])  # ni mesure ni critique
        self.assertEqual(agent.read_text(encoding="utf-8"), edited)  # pas régénéré
        self.assertEqual(researcher.read_text(encoding="utf-8"), RESEARCHER_BODY)
        self.assertFalse((self.ws / ".claude" / "journal" / "pending").exists())
        self.assertEqual(self.journal(), [])  # aucune ligne, aucun numéro consommé
        self.assertIsNone(res["entry"])
        self.assertEqual(res["dirty_paths"], [".claude/agents/p-executor.md"])
        # Manifeste modifié et non commité : même refus.
        git(self.ws, "checkout", "--", ".claude/agents/p-executor.md")
        manifest = self.ws / ".claude" / "team.json"
        manifest.write_text(manifest.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        res = ie.candidate_phase(self.ctx())
        self.assertEqual((res["status"], res["dirty_paths"]), ("rejected", [".claude/team.json"]))

    def test_commit_limite_aux_chemins_changes_par_l_iteration(self):
        ie.candidate_phase(self.ctx())
        cap = self.ws / ".claude" / "journal" / "pending" / "1" / "capture.json"
        self.assertEqual(json.loads(cap.read_text(encoding="utf-8"))["dirty"], [])
        # Agent généré déjà modifié avant l'itération (capture) : jamais commité.
        cap.write_text(json.dumps({"dirty": [".claude/agents/p-researcher.md"], "untracked": []}),
                       encoding="utf-8")
        v = ie.verdict_phase(self.ctx())
        self.assertEqual(v["status"], "accepted", v["entry"].get("reason"))
        files = [x for x in git(self.ws, "show", "--name-only", "--format=", "HEAD").splitlines() if x]
        self.assertEqual(files, [".claude/team/agents/researcher.md"])

    def test_pending_manuelle_sur_branche_refusee(self):
        ie.append_journal(self.ws, MANIFEST, {"iteration": 1, "target": ".claude/team/agents/executor.md",
                                              "status": "pending", "config_version": "x",
                                              "branch": "improve/1"})
        journal = (self.ws / ".claude" / "journal" / "changes.jsonl").read_bytes()
        for fn in (ie.verdict_phase, ie.abandon_pending):
            with self.subTest(fn=fn.__name__):
                with self.assertRaises(ie.ConflictError) as cm:
                    fn(self.ctx())
                self.assertEqual(cm.exception.status, 409)
                self.assertIn("ouverte à la main sur la branche improve/1", str(cm.exception))
                self.assertIn("/improve dans une nouvelle session", str(cm.exception))
        self.assertEqual((self.ws / ".claude" / "journal" / "changes.jsonl").read_bytes(), journal)
        self.assertEqual(self.calls(), [])
        # Même pending mais posée par Nebula : tranchée normalement.
        ie.append_journal(self.ws, MANIFEST, {"iteration": 1, "target": ".claude/team/agents/executor.md",
                                              "status": "pending", "config_version": "x",
                                              "branch": "improve/1", "runner": "nebula"})
        self.assertEqual(ie.abandon_pending(self.ctx())["status"], "rejected")

    def test_verdict_sans_pending_409(self):
        with self.assertRaises(ie.ConflictError) as cm:
            ie.verdict_phase(self.ctx())
        self.assertEqual(cm.exception.status, 409)

    def test_iteration_concurrente_refusee(self):
        lock = ie._ws_lock(self.ws)
        lock.acquire()
        try:
            with self.assertRaises(ie.ConflictError):
                ie.run_iteration(self.ctx())
        finally:
            lock.release()


class NoGitPhaseTests(EngineMixin, unittest.TestCase):
    WITH_GIT = False

    def test_acceptee_non_suivie_par_git(self):
        res = ie.run_iteration(self.ctx())
        v = res["verdict"]
        # Sans git : c2 / c3 inexécutables dans les deux mesures, c1 corrigé.
        self.assertEqual(v["status"], "accepted")
        self.assertIsNone(v["commit"])
        self.assertTrue(v["untracked"])
        self.assertTrue(self.journal()[-1]["untracked"])

    def test_abandon_sans_before_ni_git_409(self):
        ie.append_journal(self.ws, MANIFEST, {"iteration": 1, "target": ".claude/team/agents/executor.md",
                                              "status": "pending", "config_version": "x"})
        with self.assertRaises(ie.ConflictError) as cm:
            ie.abandon_pending(self.ctx())
        self.assertEqual(cm.exception.status, 409)
        with self.assertRaises(ie.ConflictError):
            ie.verdict_phase(self.ctx())



# --- Relecture : garde-fous du critique, capture, restauration --------------------------

class ReviewFixesTests(EngineMixin, unittest.TestCase):
    def test_corps_evaluateur_interdit_au_critique(self):
        self.assertFalse(ie.target_allowed(self.ws, ".claude/team/agents/evaluator.md", MANIFEST)[0])
        self.assertTrue(ie.is_forbidden_target(".claude/team/agents/Evaluator.md", MANIFEST))
        # Fichier corps déclaré ailleurs dans le manifeste : suivi aussi.
        m = json.loads(json.dumps(MANIFEST))
        for a in m["agents"]:
            if a["id"] == "evaluator":
                a["file"] = "team/agents/juge.md"
        self.assertTrue(ie.is_forbidden_target(".claude/team/agents/JUGE.md", m))
        self.assertFalse(ie.is_forbidden_target(".claude/team/agents/researcher.md", m))

    def test_team_json_evaluateur_critique_et_cles_autres_que_model_effort(self):
        before = json.dumps(MANIFEST)

        def check(fn):
            m = json.loads(before)
            fn(m)
            return ie._check_team_json(before, json.dumps(m))
        ag = lambda m, i: next(a for a in m["agents"] if a["id"] == i)  # noqa: E731
        self.assertEqual(check(lambda m: ag(m, "researcher").update(model="opus", effort="high")), "")
        for who in ("evaluator", "critic"):
            self.assertTrue(check(lambda m, who=who: ag(m, who).update(model="haiku")), who)
        self.assertTrue(check(lambda m: ag(m, "evaluator").update(effort="low")))
        self.assertTrue(check(lambda m: ag(m, "researcher").update(read_only=False)))
        self.assertTrue(check(lambda m: ag(m, "researcher").pop("read_only")))
        self.assertTrue(check(lambda m: ag(m, "orchestrator").update(can_delegate_to=["executor"])))
        self.assertTrue(check(lambda m: ag(m, "executor").update(capabilities=["shell"])))
        self.assertTrue(check(lambda m: m["agents"].pop()))
        self.assertTrue(check(lambda m: m["agents"].append({"id": "x", "file": "x.md"})))

    def test_capture_inclut_les_corps_d_agents(self):
        ctx = self.ctx()
        self.assertEqual(ie.team_git_capture(ctx), {"dirty": [], "untracked": []})
        body = self.ws / ".claude" / "team" / "agents" / "researcher.md"
        body.write_text(RESEARCHER_BODY + "retouche\n", encoding="utf-8")
        self.assertEqual(ie.team_git_capture(ctx)["dirty"], [".claude/team/agents/researcher.md"])
        res = ie.candidate_phase(ctx)
        self.assertEqual(res["status"], "rejected")
        self.assertEqual(res["reason"], ie.DIRTY_TEAM_REASON)
        self.assertEqual(self.calls(), [])

    def test_refus_config_modifiee_sans_ligne_de_journal(self):
        (self.ws / ".claude" / "team" / "agents" / "executor.md").write_text("autre\n", encoding="utf-8")
        res = ie.candidate_phase(self.ctx())
        self.assertEqual((res["status"], res["iteration"], res["entry"]), ("rejected", None, None))
        jl = self.ws / ".claude" / "journal" / "changes.jsonl"
        self.assertTrue(not jl.exists() or not jl.read_text(encoding="utf-8").strip())

    def test_restore_scope_nettoie_les_ignores_du_scope_seulement(self):
        (self.ws / ".gitignore").write_text("*.log\n", encoding="utf-8")
        git(self.ws, "add", ".gitignore")
        git(self.ws, "commit", "-q", "-m", "ignore")
        (self.ws / "tmp-eval").mkdir(exist_ok=True)
        (self.ws / "tmp-eval" / "a.log").write_text("x", encoding="utf-8")
        (self.ws / "other" / "keep.log").write_text("y", encoding="utf-8")
        self.assertEqual(ie._restore_scope(self.ws, "tmp-eval"), "")
        self.assertFalse((self.ws / "tmp-eval" / "a.log").exists())
        self.assertTrue((self.ws / "other" / "keep.log").exists())

    def test_message_de_commit_sans_tirets_typographiques(self):
        h = "a" + "".join(chr(c) for c in (0x2014, 0x2013, 0x2012, 0x2015, 0x2212)) + "b"
        msg = ie._commit_message("p", 3, h)
        self.assertEqual(msg, "update(p): improve/3 - a-----b")
        self.assertTrue(all(ord(c) < 0x2010 or ord(c) > 0x2212 for c in msg))


if __name__ == "__main__":
    unittest.main()
