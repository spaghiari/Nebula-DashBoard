"""api_team : agents générés depuis le manifeste, état de la boucle d'amélioration,
hook evals-lock.py ; scénario réel self-improving + claude-team en bac à sable.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from _support import DASHBOARD_DIR, make_workspace, reset_sandbox, write_json_file
from dashcore import api_overlays as ov
from dashcore import api_team as team
from dashcore.api_workspaces import create_workspace
from dashcore.config import TEAM_GENERATED_MARKER, TEMPLATES_DIR

REAL_SI = DASHBOARD_DIR.parent / "templates" / "claude-self-improving"
REAL_TEAM = DASHBOARD_DIR.parent / "templates" / "claude-team"
HOOK = REAL_TEAM / ".claude" / "hooks" / "evals-lock.py"
EVAL_CMD = REAL_TEAM / ".claude" / "commands" / "eval.md"
VALID_GRADERS = ("test", "regex", "exact", "rubric")

MANIFEST = {
    "team": {"name": "t", "version": "1.0.0", "entrypoint": "orchestrator", "language": "fr"},
    "models": {"sonnet": {"id": "s", "usage": "rapide"}, "opus": {"id": "o", "usage": "profond"},
               "default": "sonnet"},
    "agents": [
        {"id": "orchestrator", "file": "team/agents/orchestrator.md", "role": "Chef",
         "description": "Coordonne.", "model": "opus", "capabilities": ["filesystem"],
         "can_delegate_to": ["researcher", "executor"], "max_turns": 40},
        {"id": "researcher", "file": "team/agents/researcher.md", "role": "Chercheur",
         "description": "Cherche.", "model": "sonnet",
         "capabilities": ["web_search", "knowledge", "filesystem"], "read_only": True},
        {"id": "executor", "file": "team/agents/executor.md", "role": "Exécutant",
         "description": "Exécute.", "capabilities": ["filesystem", "code_exec", "repo"],
         "escalate_to": "opus"},
        {"id": "reviewer", "file": "team/agents/reviewer.md", "role": "Relecteur",
         "description": "Relit.", "model": "opus", "capabilities": ["filesystem", "repo"],
         "read_only": True, "isolation": "blind"},
        {"id": "evaluator", "file": "team/agents/evaluator.md", "role": "Évaluateur",
         "description": "Mesure.", "model": "sonnet", "capabilities": ["eval_runner", "code_exec"],
         "read_only": True, "temperature": 0},
        {"id": "critic", "file": "team/agents/critic.md", "description": "Critique.",
         "model": "opus", "capabilities": ["filesystem"], "read_only": True,
         "scope": "improvement_loop_only"},
        {"id": "bad id", "file": "x.md", "model": "opus", "capabilities": []},
    ],
    "improvement_loop": {"eval_set": "evals/eval-set.jsonl", "holdout_set": "evals/holdout.jsonl",
                         "eval_set_locked": True, "journal": "journal/changes.jsonl",
                         "accept_if": {"min_score_gain": 0.02, "max_regressions": 0}},
}


def _write(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _frontmatter(text: str) -> dict:
    """Frontmatter YAML plat (clé: valeur) d'un agent généré."""
    assert text.startswith("---\n"), text[:40]
    head = text.split("---\n", 2)[1]
    out = {}
    for line in head.splitlines():
        k, _, v = line.partition(":")
        out[k.strip()] = v.strip()
    return out


class GenerateAgentsTests(unittest.TestCase):
    def setUp(self):
        reset_sandbox()
        self.ws = make_workspace("w1")
        write_json_file(self.ws / ".claude" / "team.json", MANIFEST)
        for a in MANIFEST["agents"]:
            if a["id"] != "bad id":
                _write(self.ws / ".claude" / a["file"], f"# Rôle {a['id']} de {{{{label}}}}\n")
        self.vars = {"name": "w1", "label": "Mon WS"}

    def _agent(self, aid: str) -> str:
        return (self.ws / ".claude" / "agents" / f"w1-{aid}.md").read_text(encoding="utf-8")

    def test_generation_complete(self):
        r = team.generate_agents(self.ws, self.vars)
        self.assertEqual(sorted(r["generated"]), sorted(
            f".claude/agents/w1-{a}.md" for a in
            ("orchestrator", "researcher", "executor", "reviewer", "evaluator", "critic")))
        self.assertEqual(r["skipped"], [])  # l'agent à id invalide est ignoré sans bruit
        fm = _frontmatter(self._agent("orchestrator"))
        self.assertEqual(fm["name"], "w1-orchestrator")
        self.assertEqual(fm["model"], "opus")
        self.assertEqual(fm["tools"], "Read, Glob, Grep, Edit, Write, Agent")
        self.assertIn("Rôle : Chef", fm["description"])
        self.assertIn("profond", fm["description"])
        body = self._agent("orchestrator")
        self.assertIn(TEAM_GENERATED_MARKER, body)
        self.assertIn("`w1-researcher`, `w1-executor`", body)
        self.assertIn("environ 40 tours", body)
        self.assertIn("# Rôle orchestrator de Mon WS", body)  # placeholders rendus

    def test_outils_derives_et_read_only(self):
        team.generate_agents(self.ws, self.vars)
        self.assertEqual(_frontmatter(self._agent("researcher"))["tools"],
                         "WebSearch, WebFetch, Read, Grep, Glob")
        self.assertEqual(_frontmatter(self._agent("executor"))["tools"],
                         "Read, Glob, Grep, Edit, Write, Bash")
        self.assertEqual(_frontmatter(self._agent("evaluator"))["tools"], "Bash, Read")
        self.assertIn("Lecture seule", self._agent("researcher"))
        self.assertNotIn("Lecture seule", self._agent("executor"))
        self.assertIn("Isolation « blind »", self._agent("reviewer"))
        self.assertIn("modèle\n`opus`", self._agent("executor").replace("le modèle `opus`", "modèle\n`opus`"))
        self.assertIn("Reproductibilité", self._agent("evaluator"))
        self.assertIn("/improve", self._agent("critic"))

    def test_modele_par_defaut_et_overrides(self):
        team.generate_agents(self.ws, self.vars, {
            "models": {"researcher": "opus", "critic": "haiku", "executor": "nope", "../x": "opus"},
            "default_model": "opus",
        })
        self.assertEqual(_frontmatter(self._agent("researcher"))["model"], "opus")
        self.assertEqual(_frontmatter(self._agent("critic"))["model"], "haiku")
        # executor sans `model` : default_model du payload avant models.default.
        self.assertEqual(_frontmatter(self._agent("executor"))["model"], "opus")
        # evaluator déclare `sonnet` : default_model ne l'écrase jamais (rendu
        # ni manifeste).
        self.assertEqual(_frontmatter(self._agent("evaluator"))["model"], "sonnet")
        by_id = {a["id"]: a for a in json.loads(
            (self.ws / ".claude" / "team.json").read_text(encoding="utf-8"))["agents"]}
        self.assertEqual(by_id["evaluator"]["model"], "sonnet")
        self.assertEqual(by_id["executor"]["model"], "opus")
        reset_sandbox()
        self.setUp()
        team.generate_agents(self.ws, self.vars)
        self.assertEqual(_frontmatter(self._agent("executor"))["model"], "sonnet")

    def test_idempotent_et_regenerate(self):
        team.generate_agents(self.ws, self.vars)
        r = team.generate_agents(self.ws, self.vars)
        self.assertEqual(r["generated"], [])
        self.assertEqual({s["reason"] for s in r["skipped"]}, {"already present"})
        # Agent édité à la main (marqueur retiré) : jamais réécrit, même avec regenerate.
        manual = self.ws / ".claude" / "agents" / "w1-critic.md"
        manual.write_text("---\nname: w1-critic\n---\nà moi\n", encoding="utf-8")
        _write(self.ws / ".claude" / "team" / "agents" / "researcher.md", "# v2\n")
        r = team.generate_agents(self.ws, self.vars, {"regenerate": True})
        self.assertIn(".claude/agents/w1-researcher.md", r["generated"])
        self.assertNotIn(".claude/agents/w1-critic.md", r["generated"])
        self.assertEqual(manual.read_text(encoding="utf-8"), "---\nname: w1-critic\n---\nà moi\n")
        self.assertIn("# v2", self._agent("researcher"))
        self.assertTrue(any(s["path"].endswith("w1-critic.md") and "marqueur" in s["reason"]
                            for s in r["skipped"]))

    def test_corps_source_absent(self):
        (self.ws / ".claude" / "team" / "agents" / "critic.md").unlink()
        r = team.generate_agents(self.ws, self.vars)
        self.assertFalse((self.ws / ".claude" / "agents" / "w1-critic.md").exists())
        self.assertTrue(any("corps source absent" in s["reason"] for s in r["skipped"]))

    def test_sans_manifeste(self):
        (self.ws / ".claude" / "team.json").unlink()
        r = team.generate_agents(self.ws, self.vars)
        self.assertEqual(r["generated"], [])
        self.assertEqual(len(r["skipped"]), 1)

    def _manifest(self) -> dict:
        return json.loads((self.ws / ".claude" / "team.json").read_text(encoding="utf-8"))

    def test_corps_hors_de_claude_refuse(self):
        # Manifeste piégé (dépôt tiers adopté) : un `file` en ../ ou absolu ne
        # doit jamais être lu ni recopié dans .claude/agents/.
        secret = self.ws.parent / "secret-hors-workspace.md"
        _write(secret, "SECRET\n")
        m = json.loads(json.dumps(MANIFEST))
        for a in m["agents"]:
            if a["id"] == "orchestrator":
                a["file"] = "../../secret-hors-workspace.md"
            elif a["id"] == "researcher":
                a["file"] = str(secret)
        write_json_file(self.ws / ".claude" / "team.json", m)
        r = team.generate_agents(self.ws, self.vars)
        refused = {s["path"] for s in r["skipped"] if "hors de .claude" in s["reason"]}
        self.assertEqual(refused, {".claude/agents/w1-orchestrator.md",
                                   ".claude/agents/w1-researcher.md"})
        for aid in ("orchestrator", "researcher"):
            self.assertFalse((self.ws / ".claude" / "agents" / f"w1-{aid}.md").exists())
        self.assertIn(".claude/agents/w1-executor.md", r["generated"])

    def test_prefix_defaut_persiste(self):
        r = team.generate_agents(self.ws, self.vars)
        self.assertEqual(r["prefix"], "w1")
        # Le préfixe effectif (ici le défaut = id du workspace) est écrit dans
        # la copie workspace du manifeste ; la section `team` est conservée.
        m = self._manifest()
        self.assertEqual(m["team"]["prefix"], "w1")
        self.assertEqual(m["team"]["name"], "t")
        self.assertEqual(team.team_state("w1")[1]["prefix"], "w1")

    def test_prefix_override_et_regeneration(self):
        r = team.generate_agents(self.ws, self.vars, {"prefix": " dash "})
        self.assertEqual(r["prefix"], "dash")
        self.assertEqual(sorted(r["generated"])[0], ".claude/agents/dash-critic.md")
        self.assertFalse((self.ws / ".claude" / "agents" / "w1-orchestrator.md").exists())
        orch = (self.ws / ".claude" / "agents" / "dash-orchestrator.md").read_text(encoding="utf-8")
        self.assertIn("name: dash-orchestrator", orch)
        # {{name}} des corps rendus = préfixe (règle de délégation incluse).
        self.assertIn("`dash-researcher`, `dash-executor`", orch)
        self.assertEqual(self._manifest()["team"]["prefix"], "dash")
        stamp = (self.ws / ".claude" / "team.json").stat().st_mtime_ns
        # Ré-application sans prefix : le préfixe persisté est relu, rien ne change.
        r = team.generate_agents(self.ws, self.vars)
        self.assertEqual(r["prefix"], "dash")
        self.assertEqual(r["generated"], [])
        self.assertEqual({s["reason"] for s in r["skipped"]}, {"already present"})
        self.assertEqual((self.ws / ".claude" / "team.json").stat().st_mtime_ns, stamp)
        # Régénération sans prefix : toujours dash-*.
        r = team.generate_agents(self.ws, self.vars, {"regenerate": True})
        self.assertEqual(len(r["generated"]), 6)
        self.assertTrue(all(g.startswith(".claude/agents/dash-") for g in r["generated"]))
        # Préfixe invalide : ignoré (persisté relu).
        self.assertEqual(team.normalize_team_options({"prefix": "a b"})["prefix"], None)
        self.assertEqual(team.normalize_team_options({"prefix": 12})["prefix"], None)
        self.assertEqual(team.generate_agents(self.ws, self.vars, {"prefix": "../x"})["prefix"], "dash")
        st = team.team_state("w1")[1]
        self.assertEqual(st["prefix"], "dash")
        self.assertEqual({a["name"] for a in st["agents"]},
                         {f"dash-{a}" for a in ("orchestrator", "researcher", "executor",
                                                 "reviewer", "evaluator", "critic")})
        self.assertTrue(all(a["generated"] for a in st["agents"]))

    def test_prefix_manifeste_corrompu_jamais_ecrase(self):
        team.generate_agents(self.ws, self.vars)
        path = self.ws / ".claude" / "team.json"
        path.write_text("{corrompu", encoding="utf-8")
        r = team.generate_agents(self.ws, self.vars, {"prefix": "dash", "regenerate": True})
        # Manifeste illisible : rien n'est généré, rien n'est écrit.
        self.assertEqual(r["generated"], [])
        self.assertEqual(path.read_text(encoding="utf-8"), "{corrompu")

    def test_config_hash_stable_et_sensible(self):
        team.generate_agents(self.ws, self.vars)
        h1 = team.team_config_hash(self.ws, "w1")
        self.assertRegex(h1, r"^[0-9a-f]{12}$")
        self.assertEqual(team.team_config_hash(self.ws, "w1"), h1)
        self.assertEqual(team.team_state("w1")[1]["config_hash"], h1)
        # Un corps source modifié change l'empreinte, même sans régénération.
        _write(self.ws / ".claude" / "team" / "agents" / "researcher.md", "# v2\n")
        h2 = team.team_config_hash(self.ws, "w1")
        self.assertNotEqual(h1, h2)
        # Un agent généré réécrit aussi ; un agent hors préfixe, non.
        team.generate_agents(self.ws, self.vars, {"regenerate": True})
        h3 = team.team_config_hash(self.ws, "w1")
        self.assertNotEqual(h2, h3)
        _write(self.ws / ".claude" / "agents" / "autre-agent.md", "---\nname: autre-agent\n---\n")
        self.assertEqual(team.team_config_hash(self.ws, "w1"), h3)

    @unittest.skipUnless(EVAL_CMD.is_file(), "commande eval.md absente")
    def test_config_hash_egal_au_one_liner(self):
        team.generate_agents(self.ws, self.vars, {"prefix": "dash"})
        _write(self.ws / ".claude" / "agents" / "w1-orchestrator.md", "---\nname: w1-orchestrator\n---\nhors préfixe\n")
        text = EVAL_CMD.read_text(encoding="utf-8")
        m = re.search(r"^python -c \".*\"$", text, re.M)
        self.assertIsNotNone(m, "one-liner introuvable dans eval.md")
        oneliner = m.group(0)
        # Le one-liner de la commande et la constante du module sont la même chaîne.
        self.assertEqual(oneliner, team.CONFIG_HASH_ONELINER)
        rendered = oneliner.replace("{{name}}", "w1")
        # argv[0] = l'interpréteur courant : là où seul `python3` existe
        # (macOS, beaucoup de Linux), le littéral `python` est introuvable.
        argv = [sys.executable, *shlex.split(rendered, posix=True)[1:]]
        r = subprocess.run(argv, capture_output=True, text=True, cwd=str(self.ws), timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), team.team_config_hash(self.ws, "w1"))
        # Sans team.prefix persisté, le fallback {{name}} du one-liner = ws id.
        m2 = self._manifest()
        del m2["team"]["prefix"]
        write_json_file(self.ws / ".claude" / "team.json", m2)
        r = subprocess.run(argv, capture_output=True, text=True, cwd=str(self.ws), timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), team.team_config_hash(self.ws, "w1"))

    def test_team_state(self):
        team.generate_agents(self.ws, self.vars, {"models": {"researcher": "opus"}})
        (self.ws / ".claude" / "agents" / "w1-critic.md").unlink()
        status, p = team.team_state("w1")
        self.assertEqual(status, 200)
        self.assertTrue(p["active"])
        self.assertTrue(p["evals_locked"])
        self.assertFalse(p["evals_unlocked"])
        by_id = {a["id"]: a for a in p["agents"]}
        self.assertEqual(len(by_id), 6)
        self.assertTrue(by_id["researcher"]["generated"])
        self.assertTrue(by_id["researcher"]["generated_by_nebula"])
        self.assertFalse(by_id["critic"]["generated"])
        # Le choix d'activation est persisté dans le manifeste : team_state le voit.
        self.assertEqual(by_id["researcher"]["effective_model"], "opus")
        self.assertEqual(by_id["researcher"]["model"], "opus")
        self.assertEqual(by_id["executor"]["model"], "sonnet")
        write_json_file(self.ws / ".claude" / "settings.local.json", {"evals_unlocked": True})
        self.assertTrue(team.team_state("w1")[1]["evals_unlocked"])
        self.assertEqual(team.team_state("../x")[0], 400)
        self.assertEqual(team.team_state("absent")[0], 404)


class ImprovementStateTests(unittest.TestCase):
    def setUp(self):
        reset_sandbox()
        self.ws = make_workspace("w1")
        write_json_file(self.ws / ".claude" / "team.json", MANIFEST)

    def test_journal_vide_et_absent(self):
        status, p = team.improvement_state("w1")
        self.assertEqual(status, 200)
        base = {"iterations": 0, "accepted": 0, "rejected": 0, "pending": 0,
                "last_score": None, "scores": [], "consecutive_rejects": 0}
        self.assertEqual({k: p["stats"][k] for k in base}, base)
        self.assertEqual(p["evals"]["cases"], 0)
        self.assertTrue(p["evals"]["locked"])
        _write(self.ws / ".claude" / "journal" / "changes.jsonl", "")
        self.assertEqual(team.improvement_state("w1")[1]["journal"], [])

    def test_chemins_hors_de_claude_ignores(self):
        outside = self.ws.parent / "hors.jsonl"
        _write(outside, json.dumps({"iteration": 1, "status": "accepted"}) + "\n")
        m = json.loads(json.dumps(MANIFEST))
        m.setdefault("improvement_loop", {}).update(
            {"journal": "../../hors.jsonl", "eval_set": str(outside), "holdout_set": "../../hors.jsonl"})
        write_json_file(self.ws / ".claude" / "team.json", m)
        status, p = team.improvement_state("w1")
        self.assertEqual(status, 200)
        self.assertEqual(p["journal"], [])
        self.assertEqual(p["evals"]["cases"], 0)
        self.assertEqual(p["evals"]["holdout_cases"], 0)

    def test_journal_stats_et_lignes_invalides(self):
        lines = [
            json.dumps({"iteration": 1, "date": "2026-10-01", "target": "a.md", "hypothesis": "h1",
                        "score_before": 0.80, "score_after": 0.84, "regressions": [],
                        "status": "accepted", "commit": "abc1234"}),
            "pas du json",
            "[1, 2]",
            json.dumps({"iteration": 2, "date": "2026-10-02", "target": "b.md", "hypothesis": "h2",
                        "score_before": 0.84, "score_after": 0.85, "regressions": ["case-003"],
                        "status": "rejeté", "commit": None}),
            json.dumps({"date": "2026-10-03", "score_before": "0.84", "score_after": 0.9,
                        "regressions": None, "status": "accepté"}),
            json.dumps({"iteration": 4, "status": "rejected", "score_before": 0.9, "score_after": 0.88}),
            "",
        ]
        _write(self.ws / ".claude" / "journal" / "changes.jsonl", "\n".join(lines) + "\n")
        _write(self.ws / ".claude" / "evals" / "eval-set.jsonl", '{"id":"case-001"}\n\n{"id":"case-002"}\n')
        _write(self.ws / ".claude" / "evals" / "holdout.jsonl", '{"id":"hold-001"}\n')
        _write(self.ws / ".claude" / "improvements.md",
               "- **[TODO] a** (P1)\n- **[DONE 2026-10-01] b**\n- **[ABANDONED] c**\n- **[TODO] d**\n")
        _write(self.ws / ".claude" / "backlog.md", "- **[IN PROGRESS] x**\n- **[VALIDATED] y**\n")
        status, p = team.improvement_state("w1")
        self.assertEqual(status, 200)
        self.assertEqual(p["invalid_lines"], 2)
        self.assertEqual(p["stats"]["iterations"], 4)
        self.assertEqual(p["stats"]["accepted"], 2)
        self.assertEqual(p["stats"]["rejected"], 2)
        self.assertEqual(p["stats"]["scores"], [0.80, 0.84, 0.9])
        self.assertEqual(p["stats"]["last_score"], 0.9)
        self.assertEqual(p["stats"]["consecutive_rejects"], 1)
        j = p["journal"]
        self.assertEqual([e["status"] for e in j], ["accepted", "rejected", "accepted", "rejected"])
        self.assertEqual(j[1]["regressions"], ["case-003"])
        self.assertEqual(j[2]["iteration"], 3)  # itération absente -> rang
        self.assertEqual(j[2]["score_before"], 0.84)
        self.assertIsNone(j[1]["commit"])
        self.assertEqual(p["evals"], {"locked": True, "unlocked": False, "cases": 2, "holdout_cases": 1})
        self.assertEqual(p["registers"]["improvements"]["TODO"], 2)
        self.assertEqual(p["registers"]["improvements"]["DONE"], 1)
        self.assertEqual(p["registers"]["improvements"]["ABANDONED"], 1)
        self.assertEqual(p["registers"]["backlog"]["IN PROGRESS"], 1)
        self.assertEqual(p["registers"]["backlog"]["VALIDATED"], 1)
        self.assertEqual(p["registers"]["ideas"]["IDEAS"], 0)
        self.assertEqual(p["loop"]["accept_if"], {"min_score_gain": 0.02, "max_regressions": 0})

    def test_sans_manifeste(self):
        (self.ws / ".claude" / "team.json").unlink()
        status, p = team.improvement_state("w1")
        self.assertEqual(status, 200)
        self.assertFalse(p["active"])
        self.assertIsNone(p["config_hash"])
        self.assertFalse(p["baseline_current"])

    def test_baseline_a_jour_ou_perimee(self):
        for a in MANIFEST["agents"]:
            if a["id"] != "bad id":
                _write(self.ws / ".claude" / a["file"], f"# {a['id']}\n")
        team.generate_agents(self.ws, {"name": "w1", "label": "W"})
        h = team.team_config_hash(self.ws, "w1")
        journal = self.ws / ".claude" / "journal" / "changes.jsonl"
        # Journal vide : pas de baseline.
        p = team.improvement_state("w1")[1]
        self.assertEqual(p["config_hash"], h)
        self.assertFalse(p["baseline_current"])
        self.assertIsNone(p["baseline_version"])
        # Dernière ligne = empreinte courante, sans cas inexécutable : à jour.
        line = {"iteration": 1, "date": "2026-10-14", "target": "a.md", "hypothesis": "h",
                "score_before": 0.5, "score_after": 0.6, "regressions": [], "status": "accepted",
                "commit": "abc", "config_version": h, "unrunnable": 0}
        _write(journal, json.dumps(line) + "\n")
        p = team.improvement_state("w1")[1]
        self.assertTrue(p["baseline_current"])
        self.assertEqual(p["baseline_version"], h)
        self.assertEqual(p["journal"][0]["config_version"], h)
        self.assertEqual(p["journal"][0]["unrunnable"], 0)
        # Cas inexécutables : baseline non réutilisable.
        _write(journal, json.dumps({**line, "unrunnable": 2}) + "\n")
        self.assertFalse(team.improvement_state("w1")[1]["baseline_current"])
        # Seule la DERNIÈRE ligne compte ; une ligne sans config_version = périmée.
        _write(journal, json.dumps(line) + "\n" + json.dumps({**line, "iteration": 2, "config_version": "ancien"}) + "\n")
        p = team.improvement_state("w1")[1]
        self.assertFalse(p["baseline_current"])
        self.assertEqual(p["baseline_version"], "ancien")
        _write(journal, json.dumps({k: v for k, v in line.items() if k != "config_version"}) + "\n")
        p = team.improvement_state("w1")[1]
        self.assertFalse(p["baseline_current"])
        self.assertIsNone(p["baseline_version"])
        # Un corps modifié périme la baseline.
        _write(journal, json.dumps(line) + "\n")
        self.assertTrue(team.improvement_state("w1")[1]["baseline_current"])
        _write(self.ws / ".claude" / "team" / "agents" / "critic.md", "# v2\n")
        self.assertFalse(team.improvement_state("w1")[1]["baseline_current"])

    def test_candidat_pending_deux_phases(self):
        """Phase 1 de /improve : ligne `pending` (candidat en place, empreinte =
        config_version) ; phase 2 : ligne de résolution de la même itération.
        La dernière ligne d'une itération fait foi ; un pending n'est ni
        accepté ni rejeté et ne sert pas de baseline."""
        for a in MANIFEST["agents"]:
            if a["id"] != "bad id":
                _write(self.ws / ".claude" / a["file"], f"# {a['id']}\n")
        team.generate_agents(self.ws, {"name": "w1", "label": "W"})
        h = team.team_config_hash(self.ws, "w1")
        journal = self.ws / ".claude" / "journal" / "changes.jsonl"
        pending = {"iteration": 1, "date": "2026-10-14", "target": ".claude/team/agents/researcher.md",
                   "hypothesis": "h", "score_before": 0.75, "failures_before": ["case-008"],
                   "status": "pending", "baseline_version": "aaaa", "config_version": h,
                   "unrunnable": 0, "untracked": True}
        _write(journal, json.dumps(pending) + "\n")
        p = team.improvement_state("w1")[1]
        self.assertEqual(p["stats"], {**p["stats"], "iterations": 1, "accepted": 0, "rejected": 0, "pending": 1})
        self.assertFalse(p["baseline_current"])
        self.assertIsNone(p["baseline_version"])
        self.assertEqual(p["pending"]["iteration"], 1)
        self.assertTrue(p["pending"]["in_place"])
        self.assertEqual(p["pending"]["baseline_version"], "aaaa")
        self.assertEqual(p["journal"][0]["status"], "pending")
        self.assertTrue(p["journal"][0]["untracked"])
        # Candidat altéré entre les deux sessions : plus en place.
        _write(self.ws / ".claude" / "team" / "agents" / "critic.md", "# v3\n")
        self.assertFalse(team.improvement_state("w1")[1]["pending"]["in_place"])
        h2 = team.team_config_hash(self.ws, "w1")
        # Résolution (phase 2) : même itération, dernière ligne fait foi.
        done = {**pending, "status": "accepted", "score_after": 0.83, "regressions": [],
                "commit": None, "config_version": h2}
        _write(journal, json.dumps(pending) + "\n" + json.dumps(done) + "\n")
        p = team.improvement_state("w1")[1]
        self.assertIsNone(p["pending"])
        self.assertEqual(p["stats"]["iterations"], 1)
        self.assertEqual(p["stats"]["accepted"], 1)
        self.assertEqual(p["stats"]["pending"], 0)
        self.assertEqual(p["stats"]["scores"], [0.75, 0.83])
        self.assertTrue(p["baseline_current"])
        self.assertEqual(len(p["journal"]), 2)


@unittest.skipUnless(HOOK.is_file(), "hook evals-lock.py absent")
class EvalsLockHookTests(unittest.TestCase):
    """Le hook en sous-process, comme Claude Code l'invoque (stdin JSON UTF-8)."""

    def setUp(self):
        reset_sandbox()
        self.ws = make_workspace("w1")
        write_json_file(self.ws / ".claude" / "team.json", MANIFEST)

    def _run(self, file_path: str, cwd: Path | None = None, env_root: Path | None = None) -> tuple[int, str]:
        env = dict(os.environ)
        env.pop("CLAUDE_PROJECT_DIR", None)
        if env_root is not None:
            env["CLAUDE_PROJECT_DIR"] = str(env_root)
        payload = json.dumps({"tool_name": "Write", "tool_input": {"file_path": file_path, "content": "é"}})
        r = subprocess.run([sys.executable, str(HOOK)], input=payload.encode("utf-8"),
                           capture_output=True, cwd=str(cwd or self.ws), env=env, timeout=30)
        return r.returncode, r.stderr.decode("utf-8", errors="replace")

    def test_refus_sous_evals(self):
        code, err = self._run(str(self.ws / ".claude" / "evals" / "eval-set.jsonl"))
        self.assertEqual(code, 2)
        self.assertIn("verrouillé", err)
        self.assertIn("evals_unlocked", err)
        # Chemin relatif et séparateurs inverses : même verdict.
        self.assertEqual(self._run(".claude/evals/holdout.jsonl")[0], 2)
        self.assertEqual(self._run(".claude\\evals\\sub\\x.jsonl")[0], 2)
        # Via CLAUDE_PROJECT_DIR (cwd ailleurs).
        self.assertEqual(self._run(str(self.ws / ".claude" / "evals" / "a.jsonl"),
                                   cwd=self.ws.parent, env_root=self.ws)[0], 2)

    def test_autorise_ailleurs(self):
        self.assertEqual(self._run(str(self.ws / ".claude" / "journal" / "changes.jsonl"))[0], 0)
        self.assertEqual(self._run(str(self.ws / ".claude" / "evals-notes.md"))[0], 0)
        self.assertEqual(self._run(str(self.ws / "CLAUDE.md"))[0], 0)
        self.assertEqual(self._run("")[0], 0)

    def test_deverrouillage_explicite(self):
        write_json_file(self.ws / ".claude" / "settings.local.json", {"evals_unlocked": True})
        self.assertEqual(self._run(str(self.ws / ".claude" / "evals" / "eval-set.jsonl"))[0], 0)
        write_json_file(self.ws / ".claude" / "settings.local.json", {"evals_unlocked": "oui"})
        self.assertEqual(self._run(str(self.ws / ".claude" / "evals" / "eval-set.jsonl"))[0], 2)

    def _run_bash(self, command: str) -> int:
        env = dict(os.environ)
        env["CLAUDE_PROJECT_DIR"] = str(self.ws)
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
        r = subprocess.run([sys.executable, str(HOOK)], input=payload.encode("utf-8"),
                           capture_output=True, cwd=str(self.ws), env=env, timeout=30)
        return r.returncode

    def test_bash_ecriture_sous_evals_refusee(self):
        for cmd in ("echo x >> .claude/evals/eval-set.jsonl",
                    "cp tmp/a.jsonl .claude/evals/holdout.jsonl",
                    "sed -i 's/a/b/' .claude/evals/eval-set.jsonl",
                    "rm -rf .claude\\evals\\checks",
                    "Set-Content .claude/evals/x.jsonl 'y'",
                    "python -c \"open('.claude/evals/x', 'w').write('1')\""):
            self.assertEqual(self._run_bash(cmd), 2, cmd)

    def test_bash_lecture_autorisee(self):
        for cmd in ("cat .claude/evals/eval-set.jsonl",
                    "python .claude/evals/checks/case-001.py",
                    "python .claude/evals/checks/case-004.py; echo \"case-004 -> exit $?\"",
                    "python -c \"print(1>0)\" && cat .claude/evals/holdout.jsonl > /dev/null",
                    "grep -c id .claude/evals/holdout.jsonl",
                    "echo x >> .claude/journal/changes.jsonl",
                    "cp a b", ""):
            self.assertEqual(self._run_bash(cmd), 0, cmd)
        write_json_file(self.ws / ".claude" / "settings.local.json", {"evals_unlocked": True})
        self.assertEqual(self._run_bash("echo x >> .claude/evals/eval-set.jsonl"), 0)

    def test_sans_verrou_ou_sans_manifeste(self):
        m = dict(MANIFEST)
        m["improvement_loop"] = {"eval_set_locked": False}
        write_json_file(self.ws / ".claude" / "team.json", m)
        self.assertEqual(self._run(str(self.ws / ".claude" / "evals" / "x.jsonl"))[0], 0)
        (self.ws / ".claude" / "team.json").write_text("{corrompu", encoding="utf-8")
        self.assertEqual(self._run(str(self.ws / ".claude" / "evals" / "x.jsonl"))[0], 0)
        (self.ws / ".claude" / "team.json").unlink()
        self.assertEqual(self._run(str(self.ws / ".claude" / "evals" / "x.jsonl"))[0], 0)


@unittest.skipUnless((REAL_SI / ov.OVERLAY_MARKER).is_file() and (REAL_TEAM / ov.OVERLAY_MARKER).is_file(),
                     "overlays réels absents")
class RealTeamOverlayTests(unittest.TestCase):
    """Scénario réel : blank + claude-self-improving, puis claude-team."""

    def setUp(self):
        reset_sandbox()
        for src in (REAL_SI, REAL_TEAM):
            shutil.copytree(src, TEMPLATES_DIR / src.name,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))

    def test_jeu_de_demarrage_coherent(self):
        """Chaque ligne du jeu livré : JSON valide, agent du manifeste, grader
        et target valides, regex compilable, scope sur les cas diff, ids uniques,
        pas de web exigé, pas de {{name}} figé."""
        manifest = json.loads((REAL_TEAM / ".claude" / "team.json").read_text(encoding="utf-8"))
        agent_ids = {a["id"] for a in manifest["agents"]}
        seen_ids: set[str] = set()
        seen_agents: set[str] = set()
        for name, prefix in (("eval-set.jsonl", "case-"), ("holdout.jsonl", "hold-")):
            lines = [ln for ln in (REAL_TEAM / ".claude" / "evals" / name).read_text(encoding="utf-8").splitlines() if ln.strip()]
            self.assertGreaterEqual(len(lines), 2, name)
            for ln in lines:
                c = json.loads(ln)
                self.assertIsInstance(c, dict)
                self.assertTrue(c["id"].startswith(prefix), c["id"])
                self.assertNotIn(c["id"], seen_ids)
                seen_ids.add(c["id"])
                self.assertIn(c["agent"], agent_ids, c["id"])
                seen_agents.add(c["agent"])
                self.assertIn(c["grader"], VALID_GRADERS, c["id"])
                self.assertTrue(c["target"] == "output" or c["target"] == "diff"
                                or c["target"].startswith("file:"), c["id"])
                self.assertIsInstance(c["input"], str)
                self.assertTrue(c["input"].strip() and c["expected"].strip(), c["id"])
                self.assertNotIn("{{name}}", ln)
                self.assertNotIn("web", c["input"].lower().replace("pas de web", "").replace("jamais le web", ""))
                if c["grader"] in ("regex", "test"):
                    self.assertTrue(c.get("check"), c["id"])
                if c["grader"] == "regex":
                    re.compile(c["check"], re.M)
                if c["grader"] == "test":
                    self.assertTrue(c["check"].startswith("python "), c["id"])
                    self.assertIn('"{output}"', c["check"])
                    # Portabilité bash / PowerShell / cmd : jamais de backtick.
                    self.assertNotIn("`", c["check"], c["id"])
                if c["target"] == "diff":
                    self.assertTrue(c.get("scope"), c["id"])
                    self.assertNotIn("/", c["scope"].strip("/"), c["id"])
                self.assertEqual(c.get("runs", 1), 1 if c["grader"] != "rubric" else c.get("runs"))
                self.assertTrue(c.get("tags"), c["id"])
        self.assertEqual(len([i for i in seen_ids if i.startswith("case-")]), 6)
        self.assertEqual(len([i for i in seen_ids if i.startswith("hold-")]), 2)
        # Les 7 rôles sont mesurés au moins une fois (jeu + holdout).
        self.assertEqual(seen_agents, agent_ids)

    def test_liste_expose_le_declaratif(self):
        t = ov.get_overlay("claude-team")
        self.assertEqual(t["requires"], ["claude-self-improving"])
        self.assertEqual(t["generators"], ["team_agents"])
        self.assertTrue(t["has_settings_patch"])
        self.assertFalse(t["bootstrap_options"])
        self.assertEqual(len(t["features"]), 5)
        self.assertTrue(any(f["title"] == "Routage automatique" for f in t["features"]))
        self.assertTrue(t["after_apply"])
        self.assertEqual([a["id"] for a in t["agents"]],
                         ["orchestrator", "researcher", "architect", "executor", "reviewer",
                          "evaluator", "critic"])
        self.assertEqual(t["agents"][0]["model"], "opus")
        si = ov.get_overlay("claude-self-improving")
        self.assertTrue(si["bootstrap_options"])
        self.assertEqual(len(si["features"]), 4)
        self.assertEqual(si["agents"], [])

    def test_reappliquer_met_a_jour_les_fichiers_geres(self):
        """Ancien team-router.py installé, puis template mis à jour : la
        ré-application livre la nouvelle version (ancienne en .bak) ; le
        contenu du projet (manifeste, corps d'agents, mémoire, registres,
        évals) reste intact ; une seconde ré-application ne change rien."""
        ws = make_workspace("w1")
        vars = {"name": "w1", "label": "W"}
        self.assertEqual(ov.apply_overlay("w1", "claude-self-improving", vars)[0], 200)
        self.assertEqual(ov.apply_overlay("w1", "claude-team", vars)[0], 200)
        router = ws / ".claude" / "hooks" / "team-router.py"
        router.write_text("# ancienne version du routeur\n", encoding="utf-8")
        tpl_router = TEMPLATES_DIR / "claude-team" / ".claude" / "hooks" / "team-router.py"
        tpl_router.write_text(tpl_router.read_text(encoding="utf-8") + "# correctif v2\n",
                              encoding="utf-8")
        frag = TEMPLATES_DIR / "claude-team" / "CLAUDE.claude-team.md"
        frag.write_text(frag.read_text(encoding="utf-8").replace(
            "## Équipe d'agents (always-on)",
            "## Équipe d'agents (always-on)\n\nRègle v2."), encoding="utf-8")
        user_files = {
            ws / ".claude" / "team.json": None,
            ws / ".claude" / "team" / "agents" / "executor.md": "corps édité par /improve\n",
            ws / ".claude" / "memory" / "pitfalls.md": "mes pièges\n",
            ws / ".claude" / "improvements.md": "mes items\n",
            ws / ".claude" / "evals" / "eval-set.jsonl": None,
            ws / ".claude" / "commands" / "check-all.md": "check-all du projet\n",
        }
        for path, content in user_files.items():
            if content is not None:
                path.write_text(content, encoding="utf-8")
        snapshot = {p: p.read_bytes() for p in user_files}
        md = ws / "CLAUDE.md"
        md.write_text(md.read_text(encoding="utf-8") + "\nNote perso hors bloc.\n", encoding="utf-8")
        status, p = ov.apply_overlay("w1", "claude-team", vars)
        self.assertEqual(status, 200, p.get("error"))
        self.assertEqual(sorted(p["updated"]),
                         sorted([".claude/hooks/team-router.py", "CLAUDE.md (bloc claude-team)"]))
        self.assertEqual(len(p["backups"]), 2)
        self.assertEqual(router.read_text(encoding="utf-8"),
                         tpl_router.read_text(encoding="utf-8"))
        bak = next(ws / b for b in p["backups"] if "team-router" in b)
        self.assertEqual(bak.read_text(encoding="utf-8"), "# ancienne version du routeur\n")
        text = md.read_text(encoding="utf-8")
        self.assertIn("Règle v2.", text)
        self.assertIn("Note perso hors bloc.", text)
        self.assertEqual(text.count("<!-- BEGIN claude-team -->"), 1)
        self.assertEqual(text.count("<!-- BEGIN claude-self-improving -->"), 1)
        for path, before in snapshot.items():
            self.assertEqual(path.read_bytes(), before, path)
        self.assertEqual(ov._missing_hook_refs(ws), [])
        # Seconde ré-application (les deux modules) : rien ne change.
        for ov_id in ("claude-team", "claude-self-improving"):
            status, p = ov.apply_overlay("w1", ov_id, vars)
            self.assertEqual(status, 200, p.get("error"))
            self.assertEqual((p["updated"], p["backups"]), ([], []), ov_id)

    def test_team_seul_refuse_409(self):
        make_workspace("w1")
        status, p = ov.apply_overlay("w1", "claude-team", {"name": "w1", "label": "W"})
        self.assertEqual(status, 409)
        self.assertIn("Auto-amélioration", p["error"])
        self.assertEqual(p["missing_requires"][0]["id"], "claude-self-improving")
        self.assertFalse((TEMPLATES_DIR.parent / "workspaces" / "w1" / ".claude" / "team.json").exists())

    def test_hooks_en_python3_si_python_absent(self):
        # macOS / Linux sans alias `python` : tous les hooks des deux modules
        # passent en python3, et une ré-application ne les double pas.
        from unittest import mock
        ws = make_workspace("w1")
        vars = {"name": "w1", "label": "W"}
        with mock.patch.object(ov, "_hook_interpreter", return_value="python3"):
            self.assertEqual(ov.apply_overlay("w1", "claude-self-improving", vars)[0], 200)
            self.assertEqual(ov.apply_overlay("w1", "claude-team", vars)[0], 200)
            path = ws / ".claude" / "settings.json"
            first = path.read_text(encoding="utf-8")
            self.assertEqual(ov.apply_overlay("w1", "claude-team", vars, {"regenerate": True})[0], 200)
            again = path.read_text(encoding="utf-8")
        self.assertNotIn('"python \\"', first)
        for hook in ("evals-lock.py", "team-router.py", "protect-local-files.py"):
            self.assertIn(f'python3 \\"${{CLAUDE_PROJECT_DIR}}/.claude/hooks/{hook}', first)
        self.assertEqual(json.loads(again), json.loads(first))

    def test_interpreteur_des_hooks(self):
        from unittest import mock
        found = {"python": None, "python3": "/usr/bin/python3"}
        with mock.patch("os.name", "posix"), \
                mock.patch("shutil.which", side_effect=found.get):
            self.assertEqual(ov._hook_interpreter(), "python3")
        with mock.patch("os.name", "posix"), \
                mock.patch("shutil.which", side_effect={"python": "/usr/bin/python"}.get):
            self.assertEqual(ov._hook_interpreter(), "python")
        with mock.patch("os.name", "nt"), mock.patch("shutil.which", return_value=None):
            self.assertEqual(ov._hook_interpreter(), "python")

    def test_scenario_complet(self):
        ws = make_workspace("w1")
        (ws / "CLAUDE.md").unlink()
        vars = {"name": "w1", "label": "W"}
        status, p = ov.apply_overlay("w1", "claude-self-improving", vars, {"depth": "complete"})
        self.assertEqual(status, 200, p.get("error"))
        status, p = ov.apply_overlay("w1", "claude-team", vars, {"models": {"executor": "opus"}})
        self.assertEqual(status, 200, p.get("error"))
        self.assertEqual(p["appended"], ["CLAUDE.md"])
        self.assertEqual(p["settings_patched"], [".claude/settings.json"])
        self.assertEqual(len(p["generated"]), 7)
        agents_dir = ws / ".claude" / "agents"
        for aid in ("orchestrator", "researcher", "architect", "executor", "reviewer", "evaluator", "critic"):
            self.assertTrue((agents_dir / f"w1-{aid}.md").is_file(), aid)
        exe = (agents_dir / "w1-executor.md").read_text(encoding="utf-8")
        self.assertEqual(_frontmatter(exe)["model"], "opus")
        self.assertIn("name: w1-executor", exe)
        orch = (agents_dir / "w1-orchestrator.md").read_text(encoding="utf-8")
        self.assertIn("`w1-researcher`", orch)
        self.assertNotIn("{{", orch)
        # settings.json fusionné : hook ajouté au matcher Edit|Write|MultiEdit, rien perdu.
        settings = json.loads((ws / ".claude" / "settings.json").read_text(encoding="utf-8"))
        pre = settings["hooks"]["PreToolUse"]
        edit = next(e for e in pre if e["matcher"] == "Edit|Write|MultiEdit")
        cmds = [h["command"] for h in edit["hooks"]]
        self.assertEqual(len(cmds), 2)
        self.assertTrue(any("evals-lock.py" in c for c in cmds))
        self.assertTrue(any("protect-local-files.py" in c for c in cmds))
        self.assertTrue(any(e["matcher"] == "Bash" for e in pre))
        self.assertIn("statusLine", settings)
        self.assertEqual(ov._missing_hook_refs(ws), [])
        # CLAUDE.md : les deux fragments, une fois chacun.
        md = (ws / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertEqual(md.count("<!-- BEGIN claude-self-improving -->"), 1)
        self.assertEqual(md.count("<!-- BEGIN claude-team -->"), 1)
        self.assertNotIn("{{", md)
        # Le mode posé par self-improving (solo -> validate_author false) n'est pas réécrit.
        local = json.loads((ws / ".claude" / "settings.local.json").read_text(encoding="utf-8"))
        self.assertEqual(local, {"validate_author": False})
        self.assertFalse(list(ws.rglob("__pycache__")))
        self.assertTrue(ov.overlay_is_active(ws, ov.get_overlay("claude-team")))
        self.assertEqual(ov.overlays_usage(), {"claude-self-improving": ["w1"], "claude-team": ["w1"]})

        # Ré-application : rien ne bouge (ni agents, ni settings, ni fragment).
        before = {p2.relative_to(ws).as_posix(): p2.read_bytes() for p2 in ws.rglob("*") if p2.is_file()}
        status, p = ov.apply_overlay("w1", "claude-team", vars, {})
        self.assertEqual(status, 200, p.get("error"))
        self.assertEqual(p["copied"], [])
        self.assertEqual(p["appended"], [])
        self.assertEqual(p["generated"], [])
        self.assertEqual(p["settings_patched"], [])
        after = {p2.relative_to(ws).as_posix(): p2.read_bytes() for p2 in ws.rglob("*") if p2.is_file()}
        self.assertEqual(before, after)

        # Régénération : les 7 agents générés sont réécrits (marqueur présent).
        # default_model ne touche pas un modèle déclaré (tous le sont ici) :
        # manifeste inchangé à l'octet, critic reste opus.
        manifest_before = (ws / ".claude" / "team.json").read_bytes()
        status, p = ov.apply_overlay("w1", "claude-team", vars, {"regenerate": True, "default_model": "haiku"})
        self.assertEqual(len(p["generated"]), 7)
        self.assertEqual(p["prefix"], "w1")
        self.assertEqual(_frontmatter((agents_dir / "w1-critic.md").read_text(encoding="utf-8"))["model"], "opus")
        self.assertEqual((ws / ".claude" / "team.json").read_bytes(), manifest_before)

        # États exposés aux routes.
        self.assertTrue(team.team_state("w1")[1]["active"])
        st = team.improvement_state("w1")[1]
        self.assertEqual(st["evals"]["cases"], 6)
        self.assertEqual(st["evals"]["holdout_cases"], 2)
        self.assertEqual(st["stats"]["iterations"], 0)
        self.assertFalse(st["baseline_current"])
        self.assertRegex(st["config_hash"], r"^[0-9a-f]{12}$")
        # Les fichiers copiés ne gardent aucun placeholder, et parlent des
        # agents par <préfixe>, jamais par un nom figé sur l'id du workspace.
        for rel in ("CLAUDE.md", ".claude/commands/eval.md", ".claude/commands/team.md",
                    ".claude/commands/improve.md", ".claude/evals/README.md",
                    ".claude/team/agents/orchestrator.md", ".claude/team/agents/evaluator.md"):
            txt = (ws / rel).read_text(encoding="utf-8")
            self.assertNotIn("{{", txt, rel)
            self.assertNotIn("w1-orchestrator", txt, rel)
            self.assertNotIn("w1-evaluator", txt, rel)

    def test_scenario_prefix_dash(self):
        """Activation avec prefix dash -> 7 agents dash-*, team.prefix écrit ;
        ré-application sans prefix -> rien ne change ; regenerate -> dash-*."""
        ws = make_workspace("w1")
        (ws / "CLAUDE.md").unlink()
        vars = {"name": "w1", "label": "W"}
        status, p = ov.apply_overlay("w1", "claude-self-improving", vars, {"depth": "minimal"})
        self.assertEqual(status, 200, p.get("error"))
        status, p = ov.apply_overlay("w1", "claude-team", vars, {"prefix": "dash"})
        self.assertEqual(status, 200, p.get("error"))
        self.assertEqual(p["prefix"], "dash")
        self.assertEqual(sorted(p["generated"]), sorted(
            f".claude/agents/dash-{a}.md" for a in
            ("orchestrator", "researcher", "architect", "executor", "reviewer", "evaluator", "critic")))
        self.assertFalse(list((ws / ".claude" / "agents").glob("w1-*.md")))
        manifest = json.loads((ws / ".claude" / "team.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["team"]["prefix"], "dash")
        orch = (ws / ".claude" / "agents" / "dash-orchestrator.md").read_text(encoding="utf-8")
        self.assertIn("name: dash-orchestrator", orch)
        self.assertIn("`dash-researcher`", orch)
        self.assertIn("*-expert", orch)  # règle de cohabitation
        # Les fichiers copiés (commandes, fragment) ont {{name}} = id du workspace.
        self.assertIn("or 'w1'", (ws / ".claude" / "commands" / "eval.md").read_text(encoding="utf-8"))
        # Ré-application sans prefix : rien ne bouge.
        before = {p2.relative_to(ws).as_posix(): p2.read_bytes() for p2 in ws.rglob("*") if p2.is_file()}
        status, p = ov.apply_overlay("w1", "claude-team", vars, {})
        self.assertEqual(status, 200, p.get("error"))
        self.assertEqual(p["generated"], [])
        self.assertEqual(p["prefix"], "dash")
        after = {p2.relative_to(ws).as_posix(): p2.read_bytes() for p2 in ws.rglob("*") if p2.is_file()}
        self.assertEqual(before, after)
        # Régénération sans prefix : toujours dash-*.
        status, p = ov.apply_overlay("w1", "claude-team", vars, {"regenerate": True})
        self.assertEqual(len(p["generated"]), 7)
        self.assertTrue(all(g.startswith(".claude/agents/dash-") for g in p["generated"]))
        st = team.team_state("w1")[1]
        self.assertEqual(st["prefix"], "dash")
        self.assertTrue(all(a["generated"] and a["name"].startswith("dash-") for a in st["agents"]))
        # L'empreinte couvre bien les agents dash-* (changer un agent généré la change).
        h = st["config_hash"]
        (ws / ".claude" / "agents" / "dash-critic.md").write_text(
            (ws / ".claude" / "agents" / "dash-critic.md").read_text(encoding="utf-8") + "\n# x\n", encoding="utf-8")
        self.assertNotEqual(team.team_state("w1")[1]["config_hash"], h)

    def test_creation_workspace_ordre_et_refus(self):
        # claude-team coché avant son prérequis : l'ordre est corrigé.
        status, p = create_workspace({"id": "w2", "label": "W2", "template": "blank",
                                      "overlays": ["claude-team", "claude-self-improving"]})
        self.assertEqual(status, 201, p)
        self.assertEqual([o["id"] for o in p["overlays"]], ["claude-self-improving", "claude-team"])
        self.assertTrue(all(o["ok"] for o in p["overlays"]), p["overlays"])
        ws = TEMPLATES_DIR.parent / "workspaces" / "w2"
        self.assertTrue((ws / ".claude" / "agents" / "w2-orchestrator.md").is_file())
        # claude-team sans son prérequis : refus explicite, workspace créé quand même.
        status, p = create_workspace({"id": "w3", "label": "W3", "template": "blank",
                                      "overlays": ["claude-team"]})
        self.assertEqual(status, 201, p)
        self.assertEqual(len(p["overlays"]), 1)
        self.assertFalse(p["overlays"][0]["ok"])
        self.assertIn("requiert", p["overlays"][0]["error"])
        self.assertFalse((TEMPLATES_DIR.parent / "workspaces" / "w3" / ".claude" / "team.json").exists())

    def test_routage_dans_les_agents_generes(self):
        """Jeu réel : 5 agents « À utiliser automatiquement », critic et
        evaluator « Jamais en routage automatique », hook UserPromptSubmit
        câblé, team_state.routing déclaré en auto."""
        ws = make_workspace("w1")
        vars = {"name": "w1", "label": "W"}
        self.assertEqual(ov.apply_overlay("w1", "claude-self-improving", vars, {"depth": "complete"})[0], 200)
        status, p = ov.apply_overlay("w1", "claude-team", vars, {"prefix": "dash"})
        self.assertEqual(status, 200, p.get("error"))
        agents_dir = ws / ".claude" / "agents"
        for aid in ("orchestrator", "researcher", "architect", "executor", "reviewer"):
            txt = (agents_dir / f"dash-{aid}.md").read_text(encoding="utf-8")
            fm = _frontmatter(txt)
            self.assertIn("À utiliser automatiquement quand :", fm["description"], aid)
            self.assertNotIn("Jamais en routage automatique", fm["description"], aid)
            self.assertIn("**Routage** : automatique", txt, aid)
        for aid in ("critic", "evaluator"):
            txt = (agents_dir / f"dash-{aid}.md").read_text(encoding="utf-8")
            self.assertIn("Jamais en routage automatique : réservé à /eval et /improve.",
                          _frontmatter(txt)["description"], aid)
            self.assertIn("**Routage** : manuel uniquement", txt, aid)
        self.assertIn("où est implémenté", _frontmatter((agents_dir / "dash-researcher.md").read_text(encoding="utf-8"))["description"])
        # settings.json : le hook de routage sur UserPromptSubmit (groupe sans matcher), une fois.
        settings = json.loads((ws / ".claude" / "settings.json").read_text(encoding="utf-8"))
        ups = settings["hooks"]["UserPromptSubmit"]
        self.assertEqual(len(ups), 1)
        self.assertNotIn("matcher", ups[0])
        self.assertEqual([h["command"] for h in ups[0]["hooks"]],
                         ['python "${CLAUDE_PROJECT_DIR}/.claude/hooks/team-router.py"'])
        self.assertTrue((ws / ".claude" / "hooks" / "team-router.py").is_file())
        self.assertEqual(ov._missing_hook_refs(ws), [])
        status, p = ov.apply_overlay("w1", "claude-team", vars, {})
        self.assertEqual(p["settings_patched"], [])
        settings = json.loads((ws / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(len(settings["hooks"]["UserPromptSubmit"]), 1)
        self.assertEqual(len(settings["hooks"]["UserPromptSubmit"][0]["hooks"]), 1)
        # CLAUDE.md : la table de routage est là, une fois.
        md = (ws / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertEqual(md.count("### Routage automatique (always-on)"), 1)
        self.assertIn("`<p>-reviewer`", md)
        st = team.team_state("w1")[1]
        self.assertEqual(st["routing"]["mode"], "assiste")
        self.assertEqual(st["routing"]["review_gate"], "from_3_files")
        self.assertTrue(st["routing"]["declared"])
        by_id = {a["id"]: a for a in st["agents"]}
        self.assertTrue(by_id["researcher"]["auto"])
        self.assertFalse(by_id["critic"]["auto"])
        self.assertEqual(by_id["critic"]["triggers"], [])
        self.assertGreaterEqual(len(by_id["executor"]["triggers"]), 4)
        # Le hook réel, sur le workspace réel : une ligne de routage.
        env = dict(os.environ, CLAUDE_PROJECT_DIR=str(ws))
        r = subprocess.run([sys.executable, str(ws / ".claude" / "hooks" / "team-router.py")],
                           input=json.dumps({"prompt": "où est implémenté X ?"}).encode("utf-8"),
                           capture_output=True, env=env, cwd=str(ws), timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        ctx = json.loads(r.stdout.decode("utf-8"))["hookSpecificOutput"]["additionalContext"]
        self.assertIn("dash-researcher", ctx)
        self.assertIn("dash-reviewer", ctx)
        # Mode manuel depuis l'API : plus rien.
        self.assertEqual(team.set_routing(ws, mode="manuel")[0], 200)
        r = subprocess.run([sys.executable, str(ws / ".claude" / "hooks" / "team-router.py")],
                           input=json.dumps({"prompt": "où est implémenté X ?"}).encode("utf-8"),
                           capture_output=True, env=env, cwd=str(ws), timeout=30)
        self.assertEqual((r.returncode, r.stdout), (0, b""))


ROUTER_HOOK = REAL_TEAM / ".claude" / "hooks" / "team-router.py"


class RoutingTests(unittest.TestCase):
    """Couche 2 : description générée avec déclencheurs, team_state.routing,
    set_routing (validation, corruption, section absente, idempotence)."""

    def setUp(self):
        reset_sandbox()
        self.ws = make_workspace("w1")
        m = json.loads(json.dumps(MANIFEST))
        m["routing"] = {"mode": "auto", "modes": ["manuel", "assiste", "auto"], "review_gate": "always",
                        "review_gate_values": ["always", "from_3_files", "never"], "budget": "sonnet-first"}
        for a in m["agents"]:
            if a["id"] == "researcher":
                a["auto"] = True
                a["triggers"] = ["où est implémenté", "explique", "", 3]
            elif a["id"] == "critic":
                a["auto"] = False
            elif a["id"] == "executor":
                a["auto"] = True  # sans déclencheurs
        self.manifest = m
        write_json_file(self.ws / ".claude" / "team.json", m)
        for a in m["agents"]:
            if a["id"] != "bad id":
                _write(self.ws / ".claude" / a["file"], f"# Rôle {a['id']}\n")
        self.vars = {"name": "w1", "label": "W"}

    def _manifest(self) -> dict:
        return json.loads((self.ws / ".claude" / "team.json").read_text(encoding="utf-8"))

    def test_description_et_contraintes(self):
        team.generate_agents(self.ws, self.vars)
        agents = self.ws / ".claude" / "agents"
        res = (agents / "w1-researcher.md").read_text(encoding="utf-8")
        fm = _frontmatter(res)
        self.assertTrue(fm["description"].endswith(
            "[Rôle : Chercheur ; Modèle sonnet (rapide)] À utiliser automatiquement quand : où est implémenté, explique.\""))
        self.assertIn("- **Routage** : automatique (déclencheurs : où est implémenté, explique)", res)
        exe = (agents / "w1-executor.md").read_text(encoding="utf-8")
        self.assertIn("À utiliser automatiquement en routage auto.", _frontmatter(exe)["description"])
        self.assertIn("déclencheurs : selon la table du CLAUDE.md", exe)
        crit = (agents / "w1-critic.md").read_text(encoding="utf-8")
        self.assertIn("Jamais en routage automatique : réservé à /eval et /improve.", _frontmatter(crit)["description"])
        self.assertIn("- **Routage** : manuel uniquement", crit)
        # Agent sans `auto` (manifeste d'avant) : description et contraintes inchangées.
        rev = (agents / "w1-reviewer.md").read_text(encoding="utf-8")
        self.assertNotIn("routage", _frontmatter(rev)["description"].lower())
        self.assertNotIn("**Routage**", rev)

    def test_team_state_routing(self):
        st = team.team_state("w1")[1]
        self.assertEqual(st["routing"], {
            "declared": True, "mode": "auto", "modes": ["manuel", "assiste", "auto"],
            "review_gate": "always", "review_gate_values": ["always", "from_3_files", "never"],
            "budget": "sonnet-first"})
        by_id = {a["id"]: a for a in st["agents"]}
        self.assertEqual((by_id["researcher"]["auto"], by_id["researcher"]["triggers"]),
                         (True, ["où est implémenté", "explique"]))
        self.assertEqual((by_id["critic"]["auto"], by_id["critic"]["triggers"]), (False, []))
        self.assertEqual((by_id["reviewer"]["auto"], by_id["reviewer"]["triggers"]), (None, []))
        # Rétro-compatibilité : sans section routing -> manuel, non déclaré.
        m = self._manifest()
        del m["routing"]
        write_json_file(self.ws / ".claude" / "team.json", m)
        r = team.team_state("w1")[1]["routing"]
        self.assertFalse(r["declared"])
        self.assertEqual((r["mode"], r["review_gate"]), ("manuel", "from_3_files"))
        # Valeur hors liste -> manuel.
        m["routing"] = {"mode": "turbo"}
        write_json_file(self.ws / ".claude" / "team.json", m)
        self.assertEqual(team.team_state("w1")[1]["routing"]["mode"], "manuel")

    def test_set_routing(self):
        path = self.ws / ".claude" / "team.json"
        # Inchangé : aucune écriture (contenu octet à octet identique).
        before = path.read_bytes()
        status, p = team.set_routing(self.ws, mode="auto")
        self.assertEqual((status, p["written"], p["routing"]["mode"]), (200, False, "auto"))
        self.assertEqual(path.read_bytes(), before)
        # Changement de mode + de gate.
        status, p = team.set_routing(self.ws, mode="assiste", review_gate="from_3_files")
        self.assertEqual(status, 200)
        self.assertTrue(p["written"])
        self.assertEqual((p["routing"]["mode"], p["routing"]["review_gate"]), ("assiste", "from_3_files"))
        m = self._manifest()
        self.assertEqual((m["routing"]["mode"], m["routing"]["review_gate"]), ("assiste", "from_3_files"))
        self.assertEqual(m["agents"], self.manifest["agents"])  # rien d'autre ne bouge
        # Invalide -> 400, rien n'est écrit.
        before = path.read_bytes()
        self.assertEqual(team.set_routing(self.ws, mode="turbo")[0], 400)
        self.assertEqual(team.set_routing(self.ws, review_gate="parfois")[0], 400)
        self.assertEqual(team.set_routing(self.ws, mode=3)[0], 400)
        self.assertEqual(path.read_bytes(), before)

    def test_manifeste_existant_sans_routing_inchange(self):
        # Sans section routing : mode effectif manuel, defaut ecrit inchange (auto/always).
        self.assertEqual((team.ROUTING_DEFAULT["mode"], team.ROUTING_DEFAULT["review_gate"]), ("assiste", "from_3_files"))
        st = team.routing_state({"agents": []})
        self.assertEqual((st["declared"], st["mode"], st["review_gate"]), (False, "manuel", "from_3_files"))
        # Manifeste declarant deja son routage : intact.
        st = team.routing_state({"routing": {"mode": "auto", "review_gate": "always"}})
        self.assertEqual((st["mode"], st["review_gate"]), ("auto", "always"))

    def test_set_routing_section_absente_et_corrompu(self):
        path = self.ws / ".claude" / "team.json"
        m = self._manifest()
        del m["routing"]
        write_json_file(path, m)
        status, p = team.set_routing(self.ws, mode="auto")
        self.assertEqual(status, 200)
        self.assertTrue(p["written"])
        self.assertTrue(p["routing"]["declared"])
        self.assertEqual(self._manifest()["routing"], {**team.ROUTING_DEFAULT, "mode": "auto"})
        # Section absente, mode manuel demandé : défaut écrit puis mode appliqué.
        m = self._manifest()
        del m["routing"]
        write_json_file(path, m)
        self.assertEqual(team.set_routing(self.ws, mode="manuel")[1]["routing"]["mode"], "manuel")
        self.assertEqual(self._manifest()["routing"]["review_gate_values"], ["always", "from_3_files", "never"])
        # Corrompu -> 409, jamais écrasé.
        path.write_text("{corrompu", encoding="utf-8")
        status, p = team.set_routing(self.ws, mode="auto")
        self.assertEqual(status, 409)
        self.assertEqual(path.read_text(encoding="utf-8"), "{corrompu")
        # Manifeste absent -> 404.
        path.unlink()
        self.assertEqual(team.set_routing(self.ws, mode="auto")[0], 404)


class TeamRouterHookTests(unittest.TestCase):
    """Couche 3 : le hook team-router.py en sous-process (stdin JSON UTF-8),
    comme Claude Code l'invoque sur UserPromptSubmit."""

    def setUp(self):
        reset_sandbox()
        self.ws = make_workspace("w1")
        m = json.loads(json.dumps(MANIFEST))
        m["team"]["prefix"] = "dash"
        m["routing"] = {"mode": "auto", "modes": ["manuel", "assiste", "auto"], "review_gate": "always",
                        "review_gate_values": ["always", "from_3_files", "never"]}
        m["agents"].append({"id": "architect", "file": "team/agents/architect.md", "role": "Architecte",
                            "description": "Conçoit.", "model": "opus", "capabilities": ["filesystem"],
                            "read_only": True})
        for a in m["agents"]:
            a["auto"] = a["id"] not in ("critic", "evaluator")
        self.manifest = m
        write_json_file(self.ws / ".claude" / "team.json", m)

    def _run(self, prompt, *, env_root=None, cwd=None, raw=None) -> tuple[int, str, str]:
        env = dict(os.environ)
        env.pop("CLAUDE_PROJECT_DIR", None)
        if env_root is not None:
            env["CLAUDE_PROJECT_DIR"] = str(env_root)
        payload = raw if raw is not None else json.dumps({"prompt": prompt, "hook_event_name": "UserPromptSubmit"}).encode("utf-8")
        r = subprocess.run([sys.executable, str(ROUTER_HOOK)], input=payload, capture_output=True,
                           cwd=str(cwd or self.ws), env=env, timeout=30)
        return r.returncode, r.stdout.decode("utf-8", errors="replace"), r.stderr.decode("utf-8", errors="replace")

    def _ctx(self, prompt, **kw) -> str:
        code, out, err = self._run(prompt, **kw)
        self.assertEqual(code, 0, err)
        self.assertEqual(err, "")
        data = json.loads(out)
        self.assertEqual(data["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")
        ctx = data["hookSpecificOutput"]["additionalContext"]
        self.assertLessEqual(ctx.count("\n"), 1)  # jamais plus de 2 lignes
        return ctx

    def _silent(self, prompt, **kw):
        self.assertEqual(self._run(prompt, **kw), (0, "", ""), prompt)

    def test_classification(self):
        cases = {
            "question": ["où est implémenté le verrou ?", "Pourquoi ce comportement", "liste les routes",
                         "explique le hook", "c'est quoi config_hash", "le serveur tourne sur 4777 non ?",
                         "what does this do",
                         # Un interrogatif en tête l'emporte sur un verbe d'action plus loin
                         # (participe sans accent, forme interrogative inversée).
                         "ou est implemente project_dir_for_path ?", "Pourquoi le hook supprime la ligne ?",
                         "comment ajoute-t-on un hook ?", "où ajoute-t-on la route ?"],
            "conception": ["comment on ferait pour ajouter un onglet ?", "propose un plan", "quelle option",
                           "conçois l'architecture du cache", "comment on ferait pour corriger ce bug"],
            "implémentation": ["implémente la route POST", "ajoute un test", "corrige le bug : pourquoi ça plante ?",
                               "écris le fichier", "supprime la vue", "fix the prefix",
                               # Le premier verbe décide ; « vérifie que » n'est pas une relecture ;
                               # `/check-all` (jeton slash) ne compte pas.
                               "implémente la route puis vérifie que les tests passent",
                               "ajoute un test et lance /check-all",
                               "corrige le bug puis relis le diff"],
            "relecture": ["relis ce diff", "review app.js", "vérifie ce diff avant de livrer", "valide le code",
                          "relis ce diff puis corrige ce qui bloque"],
        }
        agent = {"question": "dash-researcher", "conception": "dash-architect",
                 "implémentation": "dash-executor", "relecture": "dash-reviewer"}
        for kind, prompts in cases.items():
            for p in prompts:
                ctx = self._ctx(p)
                self.assertTrue(ctx.startswith("[équipe claude-team] routage auto : " + kind), (p, ctx))
                self.assertIn(agent[kind], ctx, p)
        # Inconnu : seulement la gate reviewer (« je valide, go » n'est pas une relecture).
        for p in ("bonjour", "je valide, go pour le commit"):
            self.assertIn("demande non classée", self._ctx(p), p)
        ctx = self._ctx("bonjour")
        self.assertIn("relecture dash-reviewer obligatoire", ctx)
        # En auto, déléguer est le défaut : une demande non classée n'autorise
        # le travail en solo que sans travail (salutation, validation).
        self.assertIn("déléguer par défaut", ctx)
        self.assertIn("/team ou dash-executor", ctx)
        self.assertNotIn("répondre seul si une lecture suffit", ctx)
        self.manifest["routing"]["mode"] = "assiste"
        write_json_file(self.ws / ".claude" / "team.json", self.manifest)
        self.assertIn("répondre seul si une lecture suffit", self._ctx("bonjour"))
        self.manifest["routing"]["mode"] = "auto"
        write_json_file(self.ws / ".claude" / "team.json", self.manifest)
        # Relecture : pas de rappel de gate (c'est déjà le reviewer).
        self.assertNotIn("obligatoire", self._ctx("relis ce diff"))

    def test_chantier_et_verbes_de_remaniement(self):
        # Retour terrain : « retravaille ce projet » tombait en « inconnu » (aucune
        # délégation) et « peux-tu ... l'améliorer ? » partait au researcher.
        chantier = ["Retravaille ce projet avec l'auto-amélioration et les agents",
                    "retravaille le projet", "Nettoie et réorganise le projet",
                    "Peux-tu reprendre ce projet et l'améliorer ?", "modernise l'application",
                    "Utilise les agents pour ajouter l'export CSV",
                    "propose un plan pour refondre toute l'application", "rework the whole codebase"]
        for p in chantier:
            ctx = self._ctx(p)
            self.assertTrue(ctx.startswith("[équipe claude-team] routage auto : chantier"), (p, ctx))
            self.assertIn("/team", ctx, p)
            self.assertIn("dash-architect", ctx, p)
            self.assertIn("relecture dash-reviewer obligatoire", ctx, p)
        # Remaniement ciblé (pas le projet entier) ou infinitif : implémentation.
        for p in ("Améliore le code du module de paiement", "Optimise les performances",
                  "Refais l'interface", "Peux-tu corriger le bug ?", "simplifie cette fonction",
                  "ajoute un test au projet",
                  # Faux chantiers relevés en revue : portée hors du complément du
                  # verbe, quantificateur vague, équipe objet de la tâche.
                  "nettoie tous les imports inutiles de foo.py", "optimise la requête SQL de l'app",
                  "simplifie la fonction parse du projet", "corrige le hook claude-team",
                  "ajoute un bouton sur la page de l'équipe"):
            ctx = self._ctx(p)
            self.assertTrue(ctx.startswith("[équipe claude-team] routage auto : implémentation"), (p, ctx))
            self.assertIn("dash-executor", ctx, p)
        # Sans architecte dans le manifeste : le plan reste demandé, sans agent fantôme.
        self.manifest["agents"] = [a for a in self.manifest["agents"] if a["id"] != "architect"]
        write_json_file(self.ws / ".claude" / "team.json", self.manifest)
        ctx = self._ctx("retravaille le projet")
        self.assertIn("plan en étapes vérifiables", ctx)
        self.assertNotIn("dash-architect", ctx)

    def test_modes_et_silences(self):
        self.assertTrue(self._ctx("où est X ?").startswith("[équipe claude-team] routage auto"))
        self.manifest["routing"]["mode"] = "assiste"
        write_json_file(self.ws / ".claude" / "team.json", self.manifest)
        self.assertTrue(self._ctx("où est X ?").startswith("[équipe claude-team] suggestion : question"))
        self.manifest["routing"]["mode"] = "manuel"
        write_json_file(self.ws / ".claude" / "team.json", self.manifest)
        self._silent("où est X ?")
        # Section absente (manifeste d'avant le routage), slash command, prompt vide.
        del self.manifest["routing"]
        write_json_file(self.ws / ".claude" / "team.json", self.manifest)
        self._silent("où est X ?")
        self.manifest["routing"] = {"mode": "auto"}
        write_json_file(self.ws / ".claude" / "team.json", self.manifest)
        self._silent("/team objectif")
        self._silent("  /eval --tag x")
        self._silent("")
        self._silent("", raw=b"")
        self._silent("", raw=b"{pas du json")
        self._silent("", raw=json.dumps({"tool_name": "Write"}).encode("utf-8"))
        # Gate « never » : plus de rappel de relecture ; « from_3_files » : libellé.
        self.manifest["routing"]["review_gate"] = "never"
        write_json_file(self.ws / ".claude" / "team.json", self.manifest)
        self.assertNotIn("reviewer", self._ctx("ajoute un test"))
        self.manifest["routing"]["review_gate"] = "from_3_files"
        write_json_file(self.ws / ".claude" / "team.json", self.manifest)
        self.assertIn("dès 3 fichiers", self._ctx("ajoute un test"))

    def test_utf8_cwd_et_team_absent(self):
        # Accents dans le prompt et dans la sortie, via CLAUDE_PROJECT_DIR (cwd ailleurs).
        ctx = self._ctx("Où est implémenté l'écran « Amélioration » ?", env_root=self.ws, cwd=self.ws.parent)
        self.assertIn("réponse avec sources fichier:ligne", ctx)
        self.assertIn("« équipe : ... »", ctx)
        # Sans préfixe persisté : nom du dossier du projet.
        del self.manifest["team"]["prefix"]
        write_json_file(self.ws / ".claude" / "team.json", self.manifest)
        self.assertIn("w1-researcher", self._ctx("où est X ?"))
        # team.json corrompu ou absent : exit 0 silencieux.
        (self.ws / ".claude" / "team.json").write_text("{corrompu", encoding="utf-8")
        self._silent("où est X ?")
        (self.ws / ".claude" / "team.json").unlink()
        self._silent("où est X ?")
        self._silent("où est X ?", cwd=self.ws.parent)


class AgentModelEffortTests(unittest.TestCase):
    """Effort par agent, modèles persistés, propositions, route agents-config."""

    def setUp(self):
        reset_sandbox()
        self.ws = make_workspace("w1")
        write_json_file(self.ws / ".claude" / "team.json", MANIFEST)
        for a in MANIFEST["agents"]:
            if a["id"] != "bad id":
                _write(self.ws / ".claude" / a["file"], f"# Rôle {a['id']}\n")
        self.vars = {"name": "w1", "label": "w1"}

    def _manifest(self) -> dict:
        return json.loads((self.ws / ".claude" / "team.json").read_text(encoding="utf-8"))

    def _agent(self, aid: str) -> str:
        return (self.ws / ".claude" / "agents" / f"w1-{aid}.md").read_text(encoding="utf-8")

    def _journal(self, *lines) -> None:
        _write(self.ws / ".claude" / "journal" / "changes.jsonl",
               "".join(json.dumps(x) + "\n" for x in lines))

    def test_rendu_sans_effort_identique_a_l_octet(self):
        agent = dict(MANIFEST["agents"][3])  # reviewer, sans effort
        without = team.render_agent(agent, MANIFEST, self.vars, "corps")
        self.assertNotIn("effort:", without)
        with_effort = team.render_agent({**agent, "effort": "high"}, MANIFEST, self.vars, "corps")
        # Seule différence : la ligne `effort:` juste après `model:`.
        self.assertEqual(with_effort.replace("effort: high\n", "", 1), without)
        head = with_effort.split("---\n")[1].splitlines()
        self.assertEqual(head[head.index("model: opus") + 1], "effort: high")
        # Effort hors liste : ignoré (aucune ligne), rendu inchangé.
        self.assertEqual(team.render_agent({**agent, "effort": "turbo"}, MANIFEST, self.vars, "corps"),
                         without)
        # Empreinte inchangée pour un manifeste sans effort (rendu identique).
        team.generate_agents(self.ws, self.vars)
        h = team.team_config_hash(self.ws, "w1")
        team.generate_agents(self.ws, self.vars, {"regenerate": True})
        self.assertEqual(team.team_config_hash(self.ws, "w1"), h)

    def test_fable_inherit_sans_usage(self):
        for model in ("fable", "inherit"):
            fm = team.agent_frontmatter({**MANIFEST["agents"][1], "model": model},
                                        {**MANIFEST, "models": {**MANIFEST["models"],
                                                                model: {"usage": "XUSAGE"}}},
                                        self.vars)
            self.assertEqual(fm["model"], model)
            self.assertNotIn("XUSAGE", fm["description"])
            self.assertNotIn("Modèle", fm["description"])

    def test_modeles_d_activation_persistes(self):
        team.generate_agents(self.ws, self.vars, {"models": {"researcher": "fable"}})
        by_id = {a["id"]: a for a in self._manifest()["agents"]}
        self.assertEqual(by_id["researcher"]["model"], "fable")
        self.assertEqual(by_id["reviewer"]["model"], "opus")
        self.assertNotIn("model", by_id["executor"])
        # « Régénérer » sans payload : le choix d'activation est retrouvé.
        team.generate_agents(self.ws, self.vars, {"regenerate": True})
        self.assertEqual(_frontmatter(self._agent("researcher"))["model"], "fable")
        self.assertEqual(self._manifest()["improvement_loop"], MANIFEST["improvement_loop"])

    def test_modeles_d_activation_manifeste_corrompu_409(self):
        path = self.ws / ".claude" / "team.json"
        path.write_text("{corrompu", encoding="utf-8")
        from dashcore.helpers import CorruptJsonError
        with self.assertRaises(CorruptJsonError):
            team.generate_agents(self.ws, self.vars, {"models": {"researcher": "opus"}})
        self.assertEqual(path.read_text(encoding="utf-8"), "{corrompu")
        # Sans choix de modèle : comportement historique (rien, sans erreur).
        self.assertEqual(team.generate_agents(self.ws, self.vars)["generated"], [])

    @staticmethod
    def _with(**changes) -> dict:
        """Copie de MANIFEST avec `changes[id] = {clé: valeur | None (retirée)}`."""
        m = json.loads(json.dumps(MANIFEST))
        for a in m["agents"]:
            for k, v in (changes.get(a["id"]) or {}).items():
                if v is None:
                    a.pop(k, None)
                else:
                    a[k] = v
        return m

    @classmethod
    def _full(cls, **changes) -> dict:
        """Comme `_with`, avec l'architecte (absent du manifeste de test)."""
        m = cls._with(**changes)
        m["agents"].append({"id": "architect", "file": "team/agents/architect.md",
                            "role": "Architecte", "description": "Conçoit.", "model": "opus",
                            "capabilities": ["filesystem"], "read_only": True,
                            **(changes.get("architect") or {})})
        return m

    def test_propositions_regles(self):
        # Manifeste livré : modèles déclarés, aucun effort (= défaut de session,
        # `medium` sur les modèles 5.5) -> `high` proposé aux rôles à `high`,
        # rien aux rôles déjà à `medium`.
        props = {s["agent"]: s for s in team.suggest_agent_config(self._full())}
        self.assertEqual(set(props), {"architect", "reviewer", "evaluator", "critic"})
        for aid, s in props.items():
            with self.subTest(agent=aid):
                self.assertEqual(s["proposed"]["effort"], "high")
                self.assertIsNone(s["current"]["effort"])
                self.assertEqual(s["source"], "rule")
        # Un agent réglé à xhigh ne reçoit aucune proposition de règle.
        m = self._full(**{a: {"effort": "xhigh"} for a in ("architect", "reviewer", "evaluator", "critic")})
        self.assertEqual(team.suggest_agent_config(m), [])
        # Effort déclaré SOUS la règle : relevé à la valeur de la règle.
        m = self._full(orchestrator={"effort": "low"}, evaluator={"effort": "medium"})
        props = {s["agent"]: s for s in team.suggest_agent_config(m)}
        self.assertEqual(props["orchestrator"]["proposed"], {"model": "opus", "effort": "medium"})
        self.assertEqual(props["orchestrator"]["current"], {"model": "opus", "effort": "low"})
        self.assertEqual(props["orchestrator"]["source"], "rule")
        self.assertIn("sur-réfléchit", props["orchestrator"]["reasons"][0])
        self.assertEqual(props["evaluator"]["proposed"], {"model": "sonnet", "effort": "high"})
        self.assertEqual(set(props), {"orchestrator", "evaluator", "architect", "reviewer", "critic"})

    def test_propositions_jamais_de_baisse_ni_de_modele_declare_change(self):
        # Effort au-dessus de la règle : jamais de proposition à la baisse.
        m = self._with(**{a["id"]: {"effort": "xhigh"} for a in MANIFEST["agents"]})
        for a in m["agents"]:
            a["effort"] = {"orchestrator": "high", "reviewer": "max"}.get(a["id"], "xhigh")
        self.assertEqual(team.suggest_agent_config(m), [])
        # Modèle déclaré différent de la règle : jamais remis en cause.
        m = self._with(reviewer={"model": "sonnet", "effort": "high"},
                       researcher={"model": "opus", "effort": "low"})
        props = {s["agent"]: s for s in team.suggest_agent_config(m)}
        self.assertNotIn("reviewer", props)
        self.assertEqual(props["researcher"]["proposed"], {"model": "opus", "effort": "medium"})
        # Modèle venu du seul défaut : la règle du rôle peut le proposer.
        m = self._with(reviewer={"model": None, "effort": "high"})
        props = {s["agent"]: s for s in team.suggest_agent_config(m)}
        self.assertEqual(props["reviewer"]["current"], {"model": "sonnet", "effort": "high"})
        self.assertEqual(props["reviewer"]["proposed"], {"model": "opus", "effort": "high"})
        # Aucune proposition n'abaisse l'effort, quel que soit le réglage.
        for eff in ("low", "medium", "high", "xhigh", "max"):
            m = self._with(**{a["id"]: {"effort": eff} for a in MANIFEST["agents"]})
            for s in team.suggest_agent_config(m):
                with self.subTest(effort=eff, agent=s["agent"]):
                    self.assertGreater(team._effort_rank(s["proposed"]["effort"]),
                                       team._effort_rank(eff))

    def test_propositions_signal_mesure(self):
        cases = [{"id": f"case-{i}", "agent": "reviewer"} for i in (1, 2, 3)]
        cases.append({"id": "case-4", "agent": "researcher"})
        _write(self.ws / ".claude" / "evals" / "eval-set.jsonl",
               "".join(json.dumps(c) + "\n" for c in cases))
        self._journal({"iteration": 1, "date": "2026-10-10", "status": "pending",
                       "failures_before": ["case-1", "case-2", "case-4"]})
        st = team.team_state("w1")[1]
        self.assertEqual(st["suggestions_basis"], {"measured": True, "date": "2026-10-10",
                                                   "iteration": 1})
        props = {s["agent"]: s for s in st["suggestions"]}
        # reviewer sans effort (défaut de session = medium), 1/3 réussi : la
        # règle propose high, puis le signal +1 cran (xhigh), modèle inchangé.
        self.assertEqual(props["reviewer"]["proposed"], {"model": "opus", "effort": "xhigh"})
        self.assertEqual(props["reviewer"]["source"], "rule+measure")
        self.assertIn("1/3 cas réussis à la mesure du 2026-10-10", props["reviewer"]["reasons"][-1])
        # researcher : un seul cas, pas de signal ; règle sans objet (medium).
        self.assertNotIn("researcher", props)
        # Règle + signal : effort low -> règle high, puis +1 cran.
        m = self._with(reviewer={"effort": "low"})
        sig = team.measure_signals(self.ws, m)
        props = {s["agent"]: s for s in team.suggest_agent_config(m, sig)}
        self.assertEqual(props["reviewer"]["proposed"]["effort"], "xhigh")
        self.assertEqual(props["reviewer"]["source"], "rule+measure")
        # Effort déjà max : ni le signal ni la règle ne proposent quoi que ce
        # soit (avant : la règle proposait `high`, une baisse).
        m = self._with(reviewer={"effort": "max"})
        props = {s["agent"]: s for s in team.suggest_agent_config(m, sig)}
        self.assertNotIn("reviewer", props)
        # Effort xhigh en échec : max.
        m = self._with(reviewer={"effort": "xhigh"})
        props = {s["agent"]: s for s in team.suggest_agent_config(m, sig)}
        self.assertEqual(props["reviewer"]["proposed"]["effort"], "max")

    def test_propositions_journal_vide(self):
        write_json_file(self.ws / ".claude" / "team.json", self._full(researcher={"effort": "low"}))
        st = team.team_state("w1")[1]
        self.assertFalse(st["suggestions_basis"]["measured"])
        self.assertEqual({s["agent"] for s in st["suggestions"]},
                         {"researcher", "architect", "reviewer", "evaluator", "critic"})
        self.assertTrue(all(s["source"] == "rule" for s in st["suggestions"]))
        self.assertIn("fable", st["model_aliases"])
        self.assertEqual(st["effort_levels"][-1], "max")
        self.assertIsNone(st["agents"][0]["effective_effort"])

    def test_set_agents_config(self):
        team.generate_agents(self.ws, self.vars)
        manual = self.ws / ".claude" / "agents" / "w1-critic.md"
        manual.write_text("---\nname: w1-critic\n---\nà moi\n", encoding="utf-8")
        h0 = team.team_config_hash(self.ws, "w1")
        self._journal({"iteration": 1, "date": "2026-10-10", "status": "accepted",
                       "score_before": 0.5, "score_after": 0.6, "config_version": h0,
                       "unrunnable": 0})
        self.assertTrue(team.improvement_state("w1")[1]["baseline_current"])
        status, p = team.set_agents_config("w1", {"reviewer": {"effort": "high"},
                                                  "critic": {"model": "sonnet"}}, self.vars)
        self.assertEqual(status, 200, p)
        self.assertTrue(p["written"])
        self.assertEqual(p["generated"], [".claude/agents/w1-reviewer.md"])
        self.assertEqual(manual.read_text(encoding="utf-8"), "---\nname: w1-critic\n---\nà moi\n")
        self.assertTrue(any(s["path"].endswith("w1-critic.md") for s in p["skipped"]))
        self.assertEqual(_frontmatter(self._agent("reviewer"))["effort"], "high")
        self.assertEqual(p["config_hash_before"], h0)
        self.assertNotEqual(p["config_hash_after"], h0)
        self.assertTrue(p["baseline_stale"])
        self.assertEqual(self._manifest()["improvement_loop"], MANIFEST["improvement_loop"])
        # Même valeur : rien écrit, rien régénéré.
        stamp = (self.ws / ".claude" / "team.json").stat().st_mtime_ns
        status, p = team.set_agents_config("w1", {"reviewer": {"effort": "high"}}, self.vars)
        self.assertEqual((status, p["written"], p["generated"]), (200, False, []))
        self.assertEqual((self.ws / ".claude" / "team.json").stat().st_mtime_ns, stamp)
        # effort null : retiré du manifeste et de l'agent généré.
        status, p = team.set_agents_config("w1", {"reviewer": {"effort": None}}, self.vars)
        self.assertEqual(status, 200)
        self.assertNotIn("effort", {a["id"]: a for a in self._manifest()["agents"]}["reviewer"])
        self.assertNotIn("effort:", self._agent("reviewer"))

    def test_stale_agents_et_regeneration_seule(self):
        team.generate_agents(self.ws, self.vars)
        self.assertEqual(team.team_state("w1", self.vars)[1]["stale_agents"], [])
        # Corps modifié : l'agent généré correspondant est périmé.
        _write(self.ws / ".claude" / "team" / "agents" / "reviewer.md", "# Nouveau corps\n")
        st = team.team_state("w1", self.vars)[1]
        self.assertEqual(st["stale_agents"], ["reviewer"])
        # Un agent édité à la main (sans marqueur) n'est jamais signalé.
        tgt = self.ws / ".claude" / "agents" / "w1-reviewer.md"
        tgt.write_text("édité à la main\n", encoding="utf-8")
        self.assertEqual(team.team_state("w1", self.vars)[1]["stale_agents"], [])

    def test_agents_config_vide_regenere_les_perimes(self):
        team.generate_agents(self.ws, self.vars)
        before = (self.ws / ".claude" / "team.json").read_bytes()
        _write(self.ws / ".claude" / "team" / "agents" / "executor.md", "# Autre corps\n")
        self.assertEqual(team.team_state("w1", self.vars)[1]["stale_agents"], ["executor"])
        status, p = team.set_agents_config("w1", {}, self.vars)
        self.assertEqual(status, 200)
        self.assertFalse(p["written"])
        self.assertEqual(p["generated"], [".claude/agents/w1-executor.md"])
        self.assertIn("Autre corps", self._agent("executor"))
        self.assertEqual((self.ws / ".claude" / "team.json").read_bytes(), before)
        self.assertEqual(team.team_state("w1", self.vars)[1]["stale_agents"], [])
        # Rien de périmé : rien n'est régénéré.
        self.assertEqual(team.set_agents_config("w1", {}, self.vars)[1]["generated"], [])

    def test_set_agents_config_erreurs(self):
        for body in ({"inconnu": {"model": "opus"}}, {"reviewer": {"model": "gpt"}},
                     {"reviewer": {"effort": "turbo"}}, {"reviewer": "opus"}, None):
            with self.subTest(body=body):
                self.assertEqual(team.set_agents_config("w1", body)[0], 400)
        self.assertEqual(team.set_agents_config("absent", {"reviewer": {"model": "opus"}})[0], 404)
        # Itération /improve en attente : 409 sans écriture.
        before = (self.ws / ".claude" / "team.json").read_bytes()
        self._journal({"iteration": 2, "status": "pending", "config_version": "abc"})
        status, p = team.set_agents_config("w1", {"reviewer": {"model": "sonnet"}})
        self.assertEqual(status, 409)
        self.assertIn("en attente", p["error"])
        self.assertEqual((self.ws / ".claude" / "team.json").read_bytes(), before)
        (self.ws / ".claude" / "team.json").write_text("{corrompu", encoding="utf-8")
        self.assertEqual(team.set_agents_config("w1", {"reviewer": {"model": "opus"}})[0], 409)
        (self.ws / ".claude" / "team.json").unlink()
        self.assertEqual(team.set_agents_config("w1", {"reviewer": {"model": "opus"}})[0], 404)

    def test_set_agents_config_en_attente_sans_changement_passe(self):
        team.generate_agents(self.ws, self.vars)
        self._journal({"iteration": 2, "status": "pending", "config_version": "abc"})
        before = (self.ws / ".claude" / "team.json").read_bytes()
        # Valeurs actuelles (executor : modèle implicite `sonnet`) : 200, rien écrit.
        status, p = team.set_agents_config("w1", {"reviewer": {"model": "opus"},
                                                  "executor": {"model": "sonnet", "effort": None}})
        self.assertEqual((status, p.get("written")), (200, False), p)
        self.assertEqual((self.ws / ".claude" / "team.json").read_bytes(), before)

    def test_reappliquer_sans_changement_reel_n_ecrit_rien(self):
        # Modale d'activation : tous les modèles renvoyés, égaux à l'effectif
        # (executor : implicite via models.default). Aucun champ implicite
        # rendu explicite, manifeste inchangé à l'octet, empreinte stable.
        team.generate_agents(self.ws, self.vars)
        before = (self.ws / ".claude" / "team.json").read_bytes()
        h = team.team_config_hash(self.ws, "w1")
        current = {a["id"]: a["model"] for a in team.team_state("w1")[1]["agents"]}
        self.assertEqual(current["executor"], "sonnet")
        self.assertFalse(team._persist_models(self.ws, current, None))
        team.generate_agents(self.ws, self.vars, {"models": current, "regenerate": True})
        self.assertEqual((self.ws / ".claude" / "team.json").read_bytes(), before)
        self.assertNotIn("model", {a["id"]: a for a in self._manifest()["agents"]}["executor"])
        self.assertEqual(team.team_config_hash(self.ws, "w1"), h)

    def test_default_model_seulement_sans_modele_declare(self):
        self.assertTrue(team._persist_models(self.ws, {"critic": "haiku"}, "fable"))
        by_id = {a["id"]: a for a in self._manifest()["agents"]}
        self.assertEqual(by_id["critic"]["model"], "haiku")      # choix explicite par agent
        self.assertEqual(by_id["executor"]["model"], "fable")    # sans modèle déclaré
        self.assertEqual(by_id["reviewer"]["model"], "opus")     # déclaré : intact
        self.assertEqual(by_id["evaluator"]["model"], "sonnet")  # déclaré : intact

    def test_modeles_d_activation_iteration_en_attente(self):
        team.generate_agents(self.ws, self.vars)
        self._journal({"iteration": 3, "status": "pending", "config_version": "abc"})
        before = (self.ws / ".claude" / "team.json").read_bytes()
        with self.assertRaises(team.PendingIterationError) as cm:
            team.generate_agents(self.ws, self.vars, {"models": {"reviewer": "sonnet"}})
        self.assertEqual(cm.exception.pending["iteration"], 3)
        self.assertIn("en attente", str(cm.exception))
        self.assertEqual((self.ws / ".claude" / "team.json").read_bytes(), before)
        self.assertEqual(team.models_change_pending(self.ws, {"reviewer": "sonnet"}, None),
                         {"iteration": 3})
        # Sans changement réel : passe.
        self.assertIsNone(team.models_change_pending(self.ws, {"reviewer": "opus"}, None))
        team.generate_agents(self.ws, self.vars, {"models": {"reviewer": "opus"}})
        # Itération tranchée (dernière ligne de l'itération) : plus de verrou.
        self._journal({"iteration": 3, "status": "pending"}, {"iteration": 3, "status": "rejected"})
        self.assertIsNone(team.models_change_pending(self.ws, {"reviewer": "sonnet"}, None))

    def test_team_state_expose_iteration_en_attente(self):
        # La modale d'activation verrouille modèles et efforts sur cette clé.
        team.generate_agents(self.ws, self.vars)
        self.assertIsNone(team.team_state("w1")[1]["pending"])
        self._journal({"iteration": 5, "status": "pending", "config_version": "abc"})
        self.assertEqual(team.team_state("w1")[1]["pending"], {"iteration": 5})

    def test_regeneration_iteration_en_attente_seulement_si_reecriture_reelle(self):
        team.generate_agents(self.ws, self.vars)
        self._journal({"iteration": 6, "status": "pending", "config_version": "abc"})
        regen = {"regenerate": True}
        # Rien ne changerait : pas de verrou (ni sans « Régénérer »).
        self.assertIsNone(team.agents_rewrite_pending(self.ws, self.vars, regen))
        self.assertIsNone(team.agents_rewrite_pending(self.ws, self.vars, {}))
        # Corps modifié à la main depuis la phase 1 : la régénération réécrirait.
        body = self.ws / ".claude" / "team" / "agents" / "critic.md"
        body.write_text(body.read_text(encoding="utf-8") + "\nAjout.\n", encoding="utf-8")
        self.assertEqual(team.agents_rewrite_pending(self.ws, self.vars, regen), {"iteration": 6})
        self.assertIsNone(team.agents_rewrite_pending(self.ws, self.vars, {}))
        # Agent généré absent : régénéré même sans « Régénérer ».
        (self.ws / ".claude" / "agents" / "w1-critic.md").unlink()
        self.assertEqual(team.agents_rewrite_pending(self.ws, self.vars, {}), {"iteration": 6})
        # Itération tranchée : plus de verrou.
        self._journal({"iteration": 6, "status": "pending"}, {"iteration": 6, "status": "accepted"})
        self.assertIsNone(team.agents_rewrite_pending(self.ws, self.vars, regen))


class LegacyAgentFileModelTests(unittest.TestCase):
    """Ami en 2.4.x : modèle choisi à l'activation écrit SEULEMENT dans l'agent
    généré (`model:` du frontmatter), jamais dans team.json."""

    def setUp(self):
        reset_sandbox()
        self.ws = make_workspace("w1")
        write_json_file(self.ws / ".claude" / "team.json", MANIFEST)
        for a in MANIFEST["agents"]:
            if a["id"] != "bad id":
                _write(self.ws / ".claude" / a["file"], f"# Rôle {a['id']}\n")
        self.vars = {"name": "w1", "label": "w1"}
        team.generate_agents(self.ws, self.vars)
        self.manifest_path = self.ws / ".claude" / "team.json"

    def _path(self, aid: str) -> Path:
        return self.ws / ".claude" / "agents" / f"w1-{aid}.md"

    def _manifest_agent(self, aid: str) -> dict:
        data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        return {a["id"]: a for a in data["agents"]}[aid]

    def _legacy_executor_opus(self) -> None:
        # Rendu exact de la 2.4.1 : override d'activation, rien dans team.json.
        agent = {a["id"]: a for a in MANIFEST["agents"]}["executor"]
        body = (self.ws / ".claude" / agent["file"]).read_text(encoding="utf-8")
        self._path("executor").write_text(
            team.render_agent(agent, MANIFEST, self.vars, body, {"models": {"executor": "opus"}}),
            encoding="utf-8")
        self.assertNotIn("model", self._manifest_agent("executor"))

    def _journal(self, *lines) -> None:
        _write(self.ws / ".claude" / "journal" / "changes.jsonl",
               "".join(json.dumps(x) + "\n" for x in lines))

    def test_get_team_montre_le_modele_du_fichier(self):
        self._legacy_executor_opus()
        before = self.manifest_path.read_bytes()
        st = team.team_state("w1")[1]
        ex = {a["id"]: a for a in st["agents"]}["executor"]
        self.assertEqual((ex["model"], ex["effective_model"], ex["model_source"]),
                         ("opus", "opus", "agent_file"))
        by = {a["id"]: a for a in st["agents"]}
        self.assertEqual(by["reviewer"]["model_source"], "manifest")
        # Choix de l'utilisateur : la règle du rôle ne propose pas d'en changer.
        self.assertFalse(any(s["agent"] == "executor" and s["proposed"]["model"] != "opus"
                             for s in st["suggestions"]))
        self.assertEqual(self.manifest_path.read_bytes(), before)  # affichage seul

    def test_regler_l_effort_du_reviewer_garde_l_executor_en_opus(self):
        self._legacy_executor_opus()
        status, p = team.set_agents_config("w1", {"reviewer": {"effort": "high"}}, self.vars)
        self.assertEqual(status, 200, p)
        self.assertTrue(p["written"])
        self.assertEqual(p["adopted_models"], {"executor": "opus"})
        self.assertEqual(_frontmatter(self._path("executor").read_text(encoding="utf-8"))["model"],
                         "opus")
        self.assertEqual(self._manifest_agent("executor")["model"], "opus")
        st = team.team_state("w1")[1]
        self.assertEqual({a["id"]: a for a in st["agents"]}["executor"]["model_source"], "manifest")

    def test_regenerer_reprend_le_modele_du_fichier(self):
        self._legacy_executor_opus()
        team.generate_agents(self.ws, self.vars, {"regenerate": True})
        self.assertEqual(self._manifest_agent("executor")["model"], "opus")
        self.assertEqual(_frontmatter(self._path("executor").read_text(encoding="utf-8"))["model"],
                         "opus")

    def test_modale_qui_renvoie_le_modele_du_fichier(self):
        # Pré-remplie par GET /team, la modale renvoie opus : persisté, conservé.
        self._legacy_executor_opus()
        current = {a["id"]: a["model"] for a in team.team_state("w1")[1]["agents"]}
        self.assertEqual(current["executor"], "opus")
        team.generate_agents(self.ws, self.vars, {"models": current, "regenerate": True})
        self.assertEqual(self._manifest_agent("executor")["model"], "opus")
        self.assertEqual(_frontmatter(self._path("executor").read_text(encoding="utf-8"))["model"],
                         "opus")

    def test_iteration_en_attente_affiche_sans_ecrire(self):
        self._legacy_executor_opus()
        self._journal({"iteration": 4, "status": "pending", "config_version": "abc"})
        before = self.manifest_path.read_bytes()
        agent_before = self._path("executor").read_bytes()
        ex = {a["id"]: a for a in team.team_state("w1")[1]["agents"]}["executor"]
        self.assertEqual((ex["model"], ex["model_source"]), ("opus", "agent_file"))
        # La modale renvoie opus : pas un changement, pas de 409.
        self.assertIsNone(team.models_change_pending(self.ws, {"executor": "opus"}, None, self.vars))
        self.assertIsNone(team.agents_rewrite_pending(self.ws, self.vars, {"regenerate": True}))
        status, p = team.set_agents_config("w1", {"executor": {"model": "opus"}}, self.vars)
        self.assertEqual((status, p["written"]), (200, False), p)
        team.generate_agents(self.ws, self.vars, {"models": {"executor": "opus"}, "regenerate": True})
        self.assertEqual(self.manifest_path.read_bytes(), before)
        self.assertEqual(self._path("executor").read_bytes(), agent_before)
        # Un vrai changement reste refusé.
        self.assertEqual(team.set_agents_config("w1", {"executor": {"model": "sonnet"}})[0], 409)

    def test_agent_edite_a_la_main_ignore(self):
        p = self._path("executor")
        p.write_text("---\nname: w1-executor\nmodel: opus\n---\nà moi\n", encoding="utf-8")
        self.assertEqual(team.agent_file_models(self.ws, MANIFEST, "w1"), {})
        ex = {a["id"]: a for a in team.team_state("w1")[1]["agents"]}["executor"]
        self.assertEqual((ex["model"], ex["model_source"]), ("sonnet", "default"))

    def test_sans_ecart_rien_ne_change_a_l_octet(self):
        files = [self.manifest_path, *sorted((self.ws / ".claude" / "agents").glob("w1-*.md"))]
        before = {f: f.read_bytes() for f in files}
        h = team.team_config_hash(self.ws, "w1")
        self.assertEqual(team.agent_file_models(self.ws, MANIFEST, "w1"), {})
        st = team.team_state("w1")[1]
        self.assertNotIn("agent_file", {a["model_source"] for a in st["agents"]})
        team.generate_agents(self.ws, self.vars, {"regenerate": True})
        current = {a["id"]: a["model"] for a in st["agents"]}
        team.generate_agents(self.ws, self.vars, {"models": current, "regenerate": True})
        status, p = team.set_agents_config("w1", {"executor": {"model": "sonnet"}}, self.vars)
        self.assertEqual((status, p["written"], p["adopted_models"]), (200, False, {}))
        self.assertEqual({f: f.read_bytes() for f in files}, before)
        self.assertEqual(team.team_config_hash(self.ws, "w1"), h)
        # Rendu identique à celui de la 2.4.1 (sans override) pour chaque agent.
        for a in team.manifest_agents(MANIFEST):
            body = (self.ws / ".claude" / a["file"]).read_text(encoding="utf-8")
            self.assertEqual(self._path(a["id"]).read_text(encoding="utf-8"),
                             team.render_agent(a, MANIFEST, self.vars, body))


class ImprovementMetricsTests(unittest.TestCase):
    def setUp(self):
        reset_sandbox()
        self.ws = make_workspace("w1")
        write_json_file(self.ws / ".claude" / "team.json", MANIFEST)

    def _journal(self, *rows) -> None:
        _write(self.ws / ".claude" / "journal" / "changes.jsonl",
               "\n".join(json.dumps(r) for r in rows) + "\n")

    def test_journal_ancien_couts_null(self):
        self._journal({"iteration": 1, "date": "2026-01-01", "status": "accepted",
                       "score_before": 0.5, "score_after": 0.6})
        _, p = team.improvement_state("w1")
        j = p["journal"][0]
        self.assertIsNone(j["cost_usd"])
        self.assertIsNone(j["tokens"])
        self.assertIsNone(j["duration_ms"])
        self.assertIsNone(j["calls"])
        self.assertIsNone(j["reason"])
        self.assertIsNone(j["diff_archive"])
        self.assertIsNone(j["failures_after"])
        self.assertIsNone(p["stats"]["avg_cost_usd"])
        self.assertIsNone(p["stats"]["avg_tokens"])

    def _mixed(self):
        today = __import__("datetime").date.today().isoformat()
        self._journal(
            {"iteration": 1, "date": "2026-01-01", "status": "accepted",
             "score_before": 0.5, "score_after": 0.6},
            {"iteration": 2, "date": today, "status": "pending", "runner": "nebula", "job_id": "j1",
             "cost_usd": 0.25, "duration_ms": 1000, "calls": 2,
             "tokens": {"input": 10, "output": 5, "cache_read": 100, "cache_creation": 1}},
            {"iteration": 2, "date": today, "status": "accepted", "runner": "nebula",
             "score_before": 0.6, "score_after": 0.7, "cost_usd": 0.75, "duration_ms": 500, "calls": 3,
             "tokens": {"input": 20, "output": 15, "cache_read": 0, "cache_creation": 9},
             "failures_after": ["c1", "c2"], "reason": "gain suffisant", "diff_archive": "a.diff"},
            {"iteration": 3, "date": today, "status": "rejected", "runner": "nebula",
             "score_before": 0.7, "score_after": 0.7, "cost_usd": 1.0})

    def test_journal_mixte_sommes(self):
        self._mixed()
        _, p = team.improvement_state("w1")
        by = {}
        for j in p["journal"]:
            by[j["iteration"]] = j
        self.assertEqual(by[2]["cost_usd"], 1.0)
        self.assertEqual(by[2]["tokens"], {"input": 30, "output": 20, "cache_read": 100,
                                           "cache_creation": 10})
        self.assertEqual(by[2]["duration_ms"], 1500)
        self.assertEqual(by[2]["calls"], 5)
        self.assertEqual(by[2]["reason"], "gain suffisant")
        self.assertEqual(by[2]["diff_archive"], "a.diff")
        self.assertEqual(by[2]["failures_after"], 2)
        self.assertIsNone(by[1]["cost_usd"])
        self.assertEqual(by[3]["cost_usd"], 1.0)
        self.assertIsNone(by[3]["tokens"])
        # la dernière ligne fait toujours foi pour le statut
        self.assertEqual(p["stats"]["accepted"], 2)

    def test_stats_nouveaux(self):
        self._mixed()
        s = team.improvement_state("w1")[1]["stats"]
        self.assertEqual(s["acceptance_rate"], round(2 / 3, 4))
        self.assertEqual(s["cumulative_gain"], 0.2)
        self.assertEqual(s["avg_cost_usd"], 1.0)
        self.assertEqual(s["avg_tokens"], {"input": 30.0, "output": 20.0, "cache_read": 100.0,
                                           "cache_creation": 10.0})

    def test_acceptance_rate_null_sans_resolue(self):
        self._journal({"iteration": 1, "status": "pending"})
        s = team.improvement_state("w1")[1]["stats"]
        self.assertIsNone(s["acceptance_rate"])
        self.assertEqual(s["cumulative_gain"], 0)

    def test_todo_items(self):
        _write(self.ws / ".claude" / "improvements.md",
               "- **[TODO] a** (P1, ajouté 2026-10-01 par nebula)\n  détail\n"
               "- **[DONE 2026-10-01] b**\n- **[TODO] d**\n")
        items = team.improvement_state("w1")[1]["todo_items"]
        self.assertEqual(items, [{"title": "a", "priority": "P1", "date": "2026-10-01"},
                                 {"title": "d", "priority": None, "date": None}])

    def test_cases(self):
        _write(self.ws / ".claude" / "evals" / "eval-set.jsonl",
               '{"id":"c1","agent":"w1-executor","grader":"test"}\n'
               '{"id":"c2","agent":"w1-reviewer","grader":"rubric"}\n'
               '{"id":"c3","agent":"w1-reviewer","grader":"regex"}\n')
        cases = team.improvement_state("w1")[1]["cases"]
        self.assertEqual([c["last_result"] for c in cases], [None, None, None])
        self.assertEqual(cases[0]["grader"], "test")
        self._journal({"iteration": 1, "status": "accepted", "failures_after": ["c2"],
                       "unrunnable_ids": ["c3"]})
        cases = team.improvement_state("w1")[1]["cases"]
        self.assertEqual([c["last_result"] for c in cases], ["pass", "fail", "unrunnable"])
        self.assertEqual(cases[1]["agent"], "w1-reviewer")


if __name__ == "__main__":
    unittest.main()
