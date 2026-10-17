"""Retrait d'un module (overlay) d'un workspace : plan, retrait ciblé des hooks,
exécution archivée (jamais de suppression), route HTTP aperçu + exécution.

Scénario réel : claude-self-improving + claude-team appliqués en bac à sable,
retrait de claude-team puis de claude-self-improving, workspace restant
utilisable (aucun hook référencé absent).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from _support import (
    DASHBOARD_DIR, SANDBOX, ServerProcess, make_workspace, reset_sandbox, rmtree,
    write_json_file,
)
from dashcore import api_overlays as ov
from dashcore.config import TEMPLATES_DIR

REAL_SI = DASHBOARD_DIR.parent / "templates" / "claude-self-improving"
REAL_TEAM = DASHBOARD_DIR.parent / "templates" / "claude-team"
HAVE_REAL = (REAL_SI / ov.OVERLAY_MARKER).is_file() and (REAL_TEAM / ov.OVERLAY_MARKER).is_file()
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo")
VARS = {"name": "w1", "label": "w1"}


def _copy_real_templates(dst_root: Path) -> None:
    for src in (REAL_SI, REAL_TEAM):
        shutil.copytree(src, dst_root / src.name, ignore=IGNORE)


def _tree(root: Path) -> dict:
    """Arborescence complète (chemin relatif -> octets, None pour un dossier)."""
    out = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        out[rel] = None if p.is_dir() else p.read_bytes()
    return out


def _settings(ws: Path) -> dict:
    return json.loads((ws / ".claude" / "settings.json").read_text(encoding="utf-8"))


def _remove(ws_id: str, ov_id: str, **opts):
    """Aperçu puis exécution avec le plan_id de l'aperçu."""
    status, prev = ov.remove_overlay(ws_id, ov_id, VARS, {**opts, "dry_run": True})
    if status != 200 or prev.get("nothing_to_do"):
        return status, prev
    return ov.remove_overlay(ws_id, ov_id, VARS, {**opts, "plan_id": prev["plan_id"]})


@unittest.skipUnless(HAVE_REAL, "overlays réels absents")
class RemovalMarkerTests(unittest.TestCase):
    """Section `removal` des marqueurs livrés."""

    def test_globs_vivants_et_signature(self):
        for src in (REAL_SI, REAL_TEAM):
            with self.subTest(module=src.name):
                marker = json.loads((src / ov.OVERLAY_MARKER).read_text(encoding="utf-8"))
                self.assertIsInstance(marker.get("removal"), dict)
                cfg = ov._removal_config(marker)
                self.assertTrue(cfg["living"])
                files = [rel for rel, _ in ov._module_files(src, marker)]
                for g in cfg["living"]:
                    self.assertTrue(any(ov._matches_any(f, [g]) for f in files),
                                    f"{g} ne correspond à aucun fichier du module")
                for g in cfg["keep_if_modified"]:
                    self.assertTrue(any(ov._matches_any(f, [g]) for f in files), g)
                sig = marker["signature_file"]
                self.assertIn(sig, files)
                self.assertFalse(ov._matches_any(sig, cfg["keep_if_modified"]))


class StripHooksTests(unittest.TestCase):
    """Retrait ciblé des hooks et de la statusLine du module dans settings.json."""

    ROOT = Path(SANDBOX / "strip-ws").resolve()

    def _settings(self, interp: str = "python") -> dict:
        def cmd(name):
            return f'{interp} "${{CLAUDE_PROJECT_DIR}}/.claude/hooks/{name}"'
        return {
            "permissions": {"allow": ["Bash(git status)"], "deny": ["Bash(rm -rf:*)"]},
            "hooks": {
                "PreToolUse": [
                    {"matcher": "Edit|Write|MultiEdit", "hooks": [
                        {"type": "command", "command": cmd("protect-local-files.py")},
                        {"type": "command", "command": cmd("evals-lock.py")}]},
                    {"matcher": "Bash", "hooks": [
                        {"type": "command", "command": cmd("em-dash-precommit.py")},
                        {"type": "command", "command": cmd("evals-lock.py")},
                        {"type": "command", "command": "python mon-hook.py"}]},
                ],
                "UserPromptSubmit": [{"hooks": [{"type": "command", "command": cmd("team-router.py")}]}],
                "Stop": [{"hooks": [{"type": "command", "command": cmd("remind-check-all.py")}]}],
            },
            "statusLine": {"type": "command", "command": cmd("statusline.py")},
        }

    def test_settings_fusionne_team_retire(self):
        data = self._settings()
        scripts = {".claude/hooks/evals-lock.py", ".claude/hooks/team-router.py"}
        removed, sl = ov._strip_module_hooks(data, scripts, self.ROOT)
        self.assertFalse(sl)
        self.assertEqual(sorted((r["event"], r["matcher"]) for r in removed),
                         [("PreToolUse", "Bash"), ("PreToolUse", "Edit|Write|MultiEdit"),
                          ("UserPromptSubmit", "")])
        self.assertNotIn("UserPromptSubmit", data["hooks"])  # événement vide retiré
        bash = data["hooks"]["PreToolUse"][1]["hooks"]
        # Hook utilisateur du même matcher conservé.
        self.assertEqual([h["command"] for h in bash][-1], "python mon-hook.py")
        self.assertEqual(len(bash), 2)
        self.assertEqual(data["permissions"], self._settings()["permissions"])
        self.assertIn("statusLine", data)

    def test_python3_et_statusline(self):
        data = self._settings("python3")
        scripts = {".claude/hooks/protect-local-files.py", ".claude/hooks/em-dash-precommit.py",
                   ".claude/hooks/remind-check-all.py", ".claude/hooks/statusline.py"}
        removed, sl = ov._strip_module_hooks(data, scripts, self.ROOT)
        self.assertTrue(sl)
        self.assertNotIn("statusLine", data)
        self.assertNotIn("Stop", data["hooks"])
        self.assertEqual(len(removed), 3)
        self.assertIn("permissions", data)

    def test_tout_retire_supprime_hooks(self):
        data = {"hooks": {"Stop": [{"hooks": [{"type": "command",
                                               "command": 'python ".claude\\hooks\\x.py"'}]}]}}
        removed, _ = ov._strip_module_hooks(data, {".claude/hooks/x.py"}, self.ROOT)
        self.assertEqual(len(removed), 1)
        self.assertEqual(data, {})

    def test_reference_par_chemin(self):
        refs = ov._script_refs('python3 "${CLAUDE_PROJECT_DIR}\\.claude\\hooks\\a.py" --x', self.ROOT)
        self.assertEqual(refs, {".claude/hooks/a.py"})
        refs = ov._script_refs(f'py -3 "{self.ROOT / ".claude" / "hooks" / "b.py"}"', self.ROOT)
        self.assertEqual(refs, {".claude/hooks/b.py"})


@unittest.skipUnless(HAVE_REAL, "overlays réels absents")
class RemovalBase(unittest.TestCase):
    def setUp(self):
        reset_sandbox()
        _copy_real_templates(TEMPLATES_DIR)
        self.ws = make_workspace("w1")
        # Profondeur complète : agents, mémoire et registres au complet.
        status, p = ov.apply_overlay("w1", "claude-self-improving", VARS, {"depth": "complete"})
        self.assertEqual(status, 200, p.get("error"))

    def _team(self):
        status, p = ov.apply_overlay("w1", "claude-team", VARS)
        self.assertEqual(status, 200, p.get("error"))

    def _plan(self, ov_id: str, **opts):
        status, p = ov.remove_overlay("w1", ov_id, VARS, {**opts, "dry_run": True})
        self.assertEqual(status, 200, p.get("error"))
        return p

    @staticmethod
    def _reasons(items):
        return {i["path"]: i["reason"] for i in items}


class PlanTests(RemovalBase):
    def test_identique_modifie_renomme_absent(self):
        hook = self.ws / ".claude" / "hooks" / "em-dash-precommit.py"
        hook.write_text(hook.read_text(encoding="utf-8") + "# perso\n", encoding="utf-8")
        (self.ws / "README.md").write_text("# README du projet\n", encoding="utf-8")
        agents = self.ws / ".claude" / "agents"
        (agents / "slug-expert.md").rename(agents / "w1-expert.md")
        (self.ws / ".claude" / "hooks" / "README.md").unlink()
        p = self._plan("claude-self-improving")
        arch, keep = self._reasons(p["archive"]), self._reasons(p["keep"])
        self.assertEqual(arch[".claude/hooks/protect-local-files.py"], "identique au rendu")
        self.assertEqual(arch[".claude/hooks/em-dash-precommit.py"], "modifié")
        self.assertEqual(arch[".claude/memory/pitfalls.md"], "contenu vivant")
        self.assertEqual(arch[".claude/improvements.md"], "signature du module")
        self.assertEqual(keep["README.md"], "modifié : conservé")
        self.assertIn(".claude/agents/slug-expert.md", p["not_found"])
        self.assertIn(".claude/hooks/README.md", p["not_found"])
        self.assertNotIn(".claude/settings.json", arch)  # section settings dédiée
        self.assertTrue(p["settings"]["archived"])  # identique au rendu
        self.assertTrue(p["claude_md"]["block_removed"])
        self.assertTrue(p["dry_run"] and p["restart_needed"])

    def test_keep_living_garde_le_contenu_sauf_signature(self):
        p = self._plan("claude-self-improving", keep_living=True)
        arch, keep = self._reasons(p["archive"]), self._reasons(p["keep"])
        self.assertEqual(keep[".claude/memory/pitfalls.md"], "contenu vivant conservé (keep_living)")
        self.assertEqual(arch[".claude/improvements.md"], "signature du module")
        self.assertNotEqual(p["plan_id"], self._plan("claude-self-improving")["plan_id"])

    def test_plan_id_stable_puis_change(self):
        a = self._plan("claude-self-improving")["plan_id"]
        self.assertEqual(a, self._plan("claude-self-improving")["plan_id"])
        mem = self.ws / ".claude" / "memory" / "domain.md"
        mem.write_text(mem.read_text(encoding="utf-8") + "\nnote\n", encoding="utf-8")
        self.assertNotEqual(a, self._plan("claude-self-improving")["plan_id"])

    def test_agent_sans_marqueur_garde(self):
        self._team()
        agent = self.ws / ".claude" / "agents" / "w1-reviewer.md"
        agent.write_text("---\nname: w1-reviewer\n---\nÉdité à la main.\n", encoding="utf-8")
        p = self._plan("claude-team")
        self.assertEqual(p["prefix"], "w1")
        arch, keep = self._reasons(p["archive"]), self._reasons(p["keep"])
        self.assertEqual(keep[".claude/agents/w1-reviewer.md"],
                         "agent édité à la main (marqueur généré absent)")
        self.assertEqual(arch[".claude/agents/w1-critic.md"], "agent généré")
        self.assertEqual(arch[".claude/team.json"], "signature du module")
        self.assertFalse(p["settings"]["archived"])
        self.assertEqual(len(p["settings"]["entries_removed"]), 3)

    def test_team_json_illisible_agents_marques_seulement(self):
        self._team()
        (self.ws / ".claude" / "team.json").write_text("{cassé", encoding="utf-8")
        (self.ws / ".claude" / "agents" / "autre-critic.md").write_text("perso\n", encoding="utf-8")
        p = self._plan("claude-team")
        arch = self._reasons(p["archive"])
        self.assertIsNone(p["prefix"])
        self.assertEqual(arch[".claude/agents/w1-critic.md"], "agent généré")
        self.assertNotIn(".claude/agents/autre-critic.md", arch)
        self.assertNotIn(".claude/agents/autre-critic.md", self._reasons(p["keep"]))

    @unittest.skipUnless(os.name == "nt", "jonction NTFS (Windows)")
    def test_jonction_gardee(self):
        skills = self.ws / ".claude" / "skills"
        outside = self.ws.parent / "skills-externes"
        shutil.copytree(skills, outside)
        rmtree(skills)
        r = subprocess.run(["cmd", "/c", "mklink", "/J", str(skills), str(outside)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            self.skipTest(f"mklink /J indisponible : {r.stdout} {r.stderr}")
        try:
            p = self._plan("claude-self-improving")
            self.assertEqual(self._reasons(p["keep"])[".claude/skills/review/SKILL.md"],
                             "lien ou jonction : laissé en place")
            status, r2 = _remove("w1", "claude-self-improving")
            self.assertEqual(status, 200, r2.get("error"))
            self.assertTrue((outside / "review" / "SKILL.md").is_file())
        finally:
            os.rmdir(skills)  # retire la jonction, pas sa cible


class RemoveOverlayTests(RemovalBase):
    def test_retrait_complet_archive_et_idempotent(self):
        (self.ws / "CLAUDE.md").write_text(
            (self.ws / "CLAUDE.md").read_text(encoding="utf-8") + "\nNote perso après le bloc.\n",
            encoding="utf-8")
        before = _tree(self.ws)
        status, p = _remove("w1", "claude-self-improving")
        self.assertEqual(status, 200, p.get("error"))
        self.assertFalse(p["dry_run"])
        arch = self.ws / p["archive_dir"]
        self.assertTrue(p["archive_dir"].startswith(".claude/.nebula-removed/claude-self-improving-"))
        for item in p["archive"]:
            with self.subTest(path=item["path"]):
                self.assertFalse((self.ws / item["path"]).exists())
                self.assertEqual((arch / item["path"]).read_bytes(), before[item["path"]])
        # settings.json identique au rendu : archivé entier.
        self.assertTrue(p["settings"]["archived"])
        self.assertTrue((arch / ".claude" / "settings.json").is_file())
        self.assertFalse((self.ws / ".claude" / "settings.json").exists())
        record = json.loads((arch / "removal.json").read_text(encoding="utf-8"))
        self.assertEqual(record["overlay_id"], "claude-self-improving")
        self.assertTrue(record["restore"])
        # CLAUDE.md : seul le bloc est parti (copié dans l'archive, .bak posé).
        md = (self.ws / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertNotIn("BEGIN claude-self-improving", md)
        self.assertIn("# w1", md)
        self.assertIn("Note perso après le bloc.", md)
        self.assertIn("BEGIN claude-self-improving",
                      (arch / "CLAUDE.claude-self-improving.block.md").read_text(encoding="utf-8"))
        self.assertTrue((self.ws / p["claude_md"]["backup"]).is_file())
        self.assertFalse(ov.overlay_is_active(self.ws, ov.get_overlay("claude-self-improving")))
        self.assertFalse((self.ws / ".claude" / "memory").exists())  # dossier vidé puis retiré
        self.assertTrue((self.ws / ".claude").is_dir())
        self.assertEqual(ov._missing_hook_refs(self.ws), [])
        # Second appel : rien à faire.
        status, p2 = ov.remove_overlay("w1", "claude-self-improving", VARS, {})
        self.assertEqual(status, 200)
        self.assertTrue(p2["nothing_to_do"])

    def test_dependants_409(self):
        self._team()
        before = _tree(self.ws)
        status, p = ov.remove_overlay("w1", "claude-self-improving", VARS, {"dry_run": True})
        self.assertEqual(status, 409)
        self.assertEqual(p["dependents"][0]["id"], "claude-team")
        self.assertEqual(_tree(self.ws), before)

    def test_settings_corrompu_409_sans_aucune_ecriture(self):
        (self.ws / ".claude" / "settings.json").write_text("{cassé", encoding="utf-8")
        status, prev = ov.remove_overlay("w1", "claude-self-improving", VARS, {"dry_run": True})
        self.assertEqual(status, 409)
        before = _tree(self.ws)
        status, p = ov.remove_overlay("w1", "claude-self-improving", VARS, {"plan_id": "x"})
        self.assertEqual(status, 409)
        self.assertEqual(_tree(self.ws), before)

    def test_session_active_409_sauf_force(self):
        from dashcore import active_sessions
        with mock.patch.object(active_sessions, "list_active",
                               return_value={"w1": {"pid": 1, "state": "running"}}):
            status, p = ov.remove_overlay("w1", "claude-self-improving", VARS, {"dry_run": True})
            self.assertEqual(status, 409)
            self.assertTrue(p["active_session"])
            status, p = ov.remove_overlay("w1", "claude-self-improving", VARS,
                                          {"dry_run": True, "force": True})
            self.assertEqual(status, 200)
        with mock.patch.object(active_sessions, "list_active",
                               return_value={"w1": {"pid": 1, "state": "idle"}}):
            self.assertEqual(ov.remove_overlay("w1", "claude-self-improving", VARS,
                                               {"dry_run": True})[0], 200)

    def test_plan_id_absent_ou_perime_409(self):
        status, p = ov.remove_overlay("w1", "claude-self-improving", VARS, {})
        self.assertEqual(status, 409)
        self.assertTrue(p["plan_id"])
        before = _tree(self.ws)
        status, _ = ov.remove_overlay("w1", "claude-self-improving", VARS, {"plan_id": "0" * 16})
        self.assertEqual(status, 409)
        self.assertEqual(_tree(self.ws), before)

    def test_echec_deplacement_hook_settings_sans_reference(self):
        self._team()
        real_move = ov._move

        def flaky(src, dst):
            if Path(src).name == "team-router.py":
                raise OSError("fichier verrouillé")
            return real_move(src, dst)

        with mock.patch.object(ov, "_move", side_effect=flaky):
            status, p = _remove("w1", "claude-team")
        self.assertEqual(status, 500)
        self.assertEqual(p["errors"][0]["path"], ".claude/hooks/team-router.py")
        text = (self.ws / ".claude" / "settings.json").read_text(encoding="utf-8")
        self.assertNotIn("team-router.py", text)
        self.assertNotIn("evals-lock.py", text)
        self.assertTrue((self.ws / ".claude" / "hooks" / "team-router.py").is_file())
        # Signature laissée : module encore « actif », un nouvel appel termine.
        self.assertTrue((self.ws / ".claude" / "team.json").is_file())
        self.assertEqual(ov._missing_hook_refs(self.ws), [])
        status, p = _remove("w1", "claude-team")
        self.assertEqual(status, 200, p.get("error"))
        self.assertEqual([a["path"] for a in p["archive"]], [".claude/hooks/team-router.py",
                                                             ".claude/team.json"])
        self.assertFalse(ov.overlay_is_active(self.ws, ov.get_overlay("claude-team")))

    def test_verification_settings_arrete_avant_les_scripts(self):
        self._team()
        # Retrait des hooks simulé inopérant : la référence reste dans settings.json.
        with mock.patch.object(ov, "_strip_module_hooks", return_value=([{"event": "x", "matcher": "",
                                                                          "command": "x"}], False)):
            status, prev = ov.remove_overlay("w1", "claude-team", VARS, {"dry_run": True})
            status, p = ov.remove_overlay("w1", "claude-team", VARS, {"plan_id": prev["plan_id"]})
        self.assertEqual(status, 500)
        self.assertIn("référence encore", p["error"])
        self.assertTrue((self.ws / ".claude" / "hooks" / "team-router.py").is_file())
        self.assertTrue((self.ws / ".claude" / "hooks" / "evals-lock.py").is_file())
        self.assertEqual(ov._missing_hook_refs(self.ws), [])

    def test_scenario_reel_team_puis_self_improving(self):
        self._team()
        settings = self.ws / ".claude" / "settings.json"
        user = _settings(self.ws)
        user["permissions"]["allow"].append("Bash(npm test)")
        write_json_file(settings, user)
        status, p = _remove("w1", "claude-team")
        self.assertEqual(status, 200, p.get("error"))
        self.assertEqual(ov._missing_hook_refs(self.ws), [])
        self.assertEqual(len(p["settings"]["entries_removed"]), 3)
        self.assertTrue((self.ws / p["settings"]["backup"]).is_file())
        data = _settings(self.ws)
        self.assertNotIn("UserPromptSubmit", data["hooks"])
        self.assertIn("Bash(npm test)", data["permissions"]["allow"])
        self.assertFalse(list((self.ws / ".claude" / "agents").glob("w1-*.md")))
        self.assertFalse((self.ws / ".claude" / "team").exists())
        self.assertFalse((self.ws / ".claude" / "evals").exists())
        md = (self.ws / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertNotIn("claude-team -->", md)
        self.assertIn("BEGIN claude-self-improving", md)
        self.assertTrue(ov.overlay_is_active(self.ws, ov.get_overlay("claude-self-improving")))
        # Puis claude-self-improving : settings.json modifié (permission en plus)
        # -> retrait ciblé, permissions conservées.
        status, p = _remove("w1", "claude-self-improving")
        self.assertEqual(status, 200, p.get("error"))
        self.assertFalse(p["settings"]["archived"])
        self.assertTrue(p["settings"]["statusline_removed"])
        data = _settings(self.ws)
        self.assertNotIn("hooks", data)
        self.assertNotIn("statusLine", data)
        self.assertIn("Bash(npm test)", data["permissions"]["allow"])
        self.assertEqual(ov._missing_hook_refs(self.ws), [])
        self.assertTrue((self.ws / ".claude" / "settings.local.json").is_file())
        self.assertEqual((self.ws / "CLAUDE.md").read_text(encoding="utf-8").strip(), "# w1")
        removed = sorted(p.name for p in (self.ws / ".claude" / ".nebula-removed").iterdir())
        self.assertEqual(len(removed), 2)
        # Ré-activation possible ensuite (rien ne la bloque).
        self.assertEqual(ov.apply_overlay("w1", "claude-self-improving", VARS)[0], 200)


class InactiveModuleTests(RemovalBase):
    """Module inactif (signature absente) : jamais de fichier homonyme déplacé."""

    def test_module_jamais_applique_rien_a_faire(self):
        # Projet qui a, par hasard, les mêmes chemins que claude-team et un
        # hook de même nom : rien n'est à lui retirer.
        self.ws = make_workspace("w2")
        hooks = self.ws / ".claude" / "hooks"
        hooks.mkdir(parents=True, exist_ok=True)
        (hooks / "evals-lock.py").write_text("# hook du projet\n", encoding="utf-8")
        (self.ws / "README.md").write_text("# Projet\n", encoding="utf-8")
        (self.ws / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
        mem = self.ws / ".claude" / "memory"
        mem.mkdir(parents=True, exist_ok=True)
        (mem / "overview.md").write_text("# Ma mémoire\n", encoding="utf-8")
        write_json_file(self.ws / ".claude" / "settings.json", {"hooks": {"PreToolUse": [
            {"matcher": "Bash", "hooks": [{"type": "command",
                                           "command": 'python "${CLAUDE_PROJECT_DIR}/.claude/hooks/evals-lock.py"'}]}]}})
        before = _tree(self.ws)
        for ov_id in ("claude-team", "claude-self-improving"):
            with self.subTest(module=ov_id):
                status, p = ov.remove_overlay("w2", ov_id, VARS, {"dry_run": True})
                self.assertEqual(status, 200, p.get("error"))
                self.assertEqual(p["archive"], [])
                self.assertEqual(p["settings"]["entries_removed"], [])
                self.assertTrue(p["nothing_to_do"], p)
                self.assertTrue(p["inactive"])
                status, r = ov.remove_overlay("w2", ov_id, VARS, {"plan_id": p["plan_id"]})
                self.assertEqual(status, 200)
                self.assertTrue(r["nothing_to_do"])
        self.assertEqual(_tree(self.ws), before)

    def test_signature_absente_seules_les_traces_certaines(self):
        self._team()
        # Retrait « à la main » partiel de l'équipe : manifeste et un script
        # supprimés ; le reste (autres hooks, bloc CLAUDE.md, agents générés,
        # mémoire) est encore là.
        (self.ws / ".claude" / "team.json").unlink()
        (self.ws / ".claude" / "hooks" / "team-router.py").unlink()
        p = self._plan("claude-team")
        arch = self._reasons(p["archive"])
        # Agents portant le marqueur généré : spécifiques au module.
        self.assertEqual(arch[".claude/agents/w1-critic.md"], "agent généré")
        # Aucun autre fichier, même présent et identique au rendu.
        self.assertEqual(set(arch.values()), {"agent généré"})
        self.assertNotIn(".claude/hooks/evals-lock.py", arch)
        self.assertNotIn(".claude/memory/overview.md", arch)
        # Hook cassé (script absent) retiré ; evals-lock.py (présent) gardé.
        cmds = [e["command"] for e in p["settings"]["entries_removed"]]
        self.assertEqual(len(cmds), 1)
        self.assertIn("team-router.py", cmds[0])
        self.assertTrue(p["claude_md"]["block_removed"])
        self.assertTrue(p["inactive"])
        status, r = ov.remove_overlay("w1", "claude-team", VARS, {"plan_id": p["plan_id"]})
        self.assertEqual(status, 200, r.get("error"))
        self.assertTrue((self.ws / ".claude" / "hooks" / "evals-lock.py").is_file())
        self.assertIn("evals-lock.py", (self.ws / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertNotIn("team-router.py", (self.ws / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertTrue((self.ws / ".claude" / "memory" / "overview.md").is_file())
        self.assertEqual(ov._missing_hook_refs(self.ws, include_local=True), [])

    def test_self_improving_inactif_readme_gitignore_overview_intacts(self):
        (self.ws / ".claude" / "improvements.md").unlink()
        keep = {rel: (self.ws / rel).read_bytes()
                for rel in ("README.md", ".gitignore", ".claude/memory/overview.md",
                            ".claude/settings.json")}
        status, r = _remove("w1", "claude-self-improving")
        self.assertEqual(status, 200, r.get("error"))
        for rel, data in keep.items():
            with self.subTest(path=rel):
                self.assertTrue((self.ws / rel).is_file(), rel)
                self.assertEqual((self.ws / rel).read_bytes(), data)
        self.assertEqual(r["archive"], [])
        self.assertTrue(r["claude_md"]["block_removed"])  # bloc à marqueurs du module
        self.assertTrue(r["inactive"])


class LocalSettingsAndGitignoreTests(RemovalBase):
    def test_settings_local_hooks_du_module_retires(self):
        self._team()
        local = self.ws / ".claude" / "settings.local.json"
        data = json.loads(local.read_text(encoding="utf-8"))
        data["permissions"] = {"allow": ["Bash(npm test)"]}
        data["hooks"] = {"PreToolUse": [{"matcher": "Bash", "hooks": [
            {"type": "command", "command": 'python "${CLAUDE_PROJECT_DIR}/.claude/hooks/evals-lock.py"'},
            {"type": "command", "command": "python mon-hook-local.py"}]}]}
        write_json_file(local, data)
        local_names = sorted(p.name for p in (self.ws / ".claude").glob("settings.local.json*"))
        status, r = _remove("w1", "claude-team")
        self.assertEqual(status, 200, r.get("error"))
        after = json.loads(local.read_text(encoding="utf-8"))
        self.assertNotIn("evals-lock.py", local.read_text(encoding="utf-8"))
        self.assertEqual(len(r["settings_local"]["entries_removed"]), 1)
        self.assertEqual(after["permissions"], {"allow": ["Bash(npm test)"]})
        self.assertEqual(after["validate_author"], data["validate_author"])
        self.assertEqual([h["command"] for h in after["hooks"]["PreToolUse"][0]["hooks"]],
                         ["python mon-hook-local.py"])
        self.assertTrue((self.ws / r["settings_local"]["backup"]).is_file())
        self.assertEqual(ov._missing_hook_refs(self.ws, include_local=True), [])
        # Sauvegarde rangée DANS l'archive du retrait (ignorée par git),
        # jamais à côté de settings.local.json (env, jetons commitables).
        self.assertEqual(r["settings_local"]["backup"],
                         f"{r['archive_dir']}/{ov.LOCAL_BACKUP_NAME}")
        self.assertEqual(json.loads((self.ws / r["settings_local"]["backup"])
                                    .read_text(encoding="utf-8")), data)
        # Seule reste à côté la rotation `.bak` de write_json (toute écriture
        # de settings.local.json la produit), couverte par la règle
        # `.claude/settings.local.json*` du .gitignore livré.
        self.assertEqual(sorted(p.name for p in (self.ws / ".claude").glob("settings.local.json*")
                                if p.name != "settings.local.json.bak"), local_names)
        self.assertEqual(list((self.ws / ".claude").glob("settings.local.json.*-*.bak")), [])
        rec = json.loads((self.ws / r["archive_dir"] / "removal.json").read_text(encoding="utf-8"))
        self.assertTrue(any(ov.LOCAL_BACKUP_NAME in step for step in rec["restore"]))

    def test_gitignore_livre_couvre_les_sauvegardes_locales(self):
        # Règle élargie : `.claude/settings.local.json*` (sauvegardes .bak comprises).
        gi = REAL_SI / ".gitignore"
        lines = [ln.strip() for ln in gi.read_text(encoding="utf-8").splitlines()]
        self.assertIn(".claude/settings.local.json*", lines)
        self.assertIn(".claude/.nebula-removed/", lines)

    def test_settings_local_controle_final(self):
        # Le contrôle final voit settings.local.json (avant : seul settings.json).
        local = self.ws / ".claude" / "settings.local.json"
        write_json_file(local, {"statusLine": {"type": "command",
                                               "command": 'python "${CLAUDE_PROJECT_DIR}/.claude/hooks/absent.py"'}})
        self.assertEqual(ov._missing_hook_refs(self.ws), [])
        self.assertEqual(ov._missing_hook_refs(self.ws, include_local=True), [".claude/hooks/absent.py"])

    def test_settings_local_corrompu_409(self):
        local = self.ws / ".claude" / "settings.local.json"
        local.write_text("{cassé", encoding="utf-8")
        before = _tree(self.ws)
        status, p = ov.remove_overlay("w1", "claude-self-improving", VARS, {"dry_run": True})
        self.assertEqual(status, 409)
        self.assertEqual(p["file"], ".claude/settings.local.json")
        self.assertEqual(_tree(self.ws), before)

    def test_gitignore_identique_toujours_garde(self):
        gi = self.ws / ".gitignore"
        self.assertIn(".claude/.nebula-removed/", gi.read_text(encoding="utf-8"))
        p = self._plan("claude-self-improving")
        self.assertIn(".gitignore", self._reasons(p["keep"]))
        self.assertNotIn(".gitignore", self._reasons(p["archive"]))
        status, r = _remove("w1", "claude-self-improving")
        self.assertEqual(status, 200, r.get("error"))
        self.assertIn(".claude/.nebula-removed/", gi.read_text(encoding="utf-8"))
        self.assertFalse((self.ws / r["archive_dir"] / ".gitignore").exists())


class ActivationModelsTests(RemovalBase):
    def test_reappliquer_modeles_iteration_en_attente_409(self):
        self._team()
        journal = self.ws / ".claude" / "journal" / "changes.jsonl"
        journal.parent.mkdir(parents=True, exist_ok=True)
        journal.write_text(json.dumps({"iteration": 4, "status": "pending"}) + "\n", encoding="utf-8")
        before = _tree(self.ws)
        # Changement réel d'un modèle : 409 avant toute écriture.
        status, p = ov.apply_overlay("w1", "claude-team", VARS, {"models": {"critic": "sonnet"}})
        self.assertEqual(status, 409)
        self.assertEqual(p["pending"], {"iteration": 4})
        self.assertIn("en attente", p["error"])
        self.assertEqual(_tree(self.ws), before)
        # Modale qui renvoie les modèles actuels : la ré-application passe,
        # sans rien changer.
        from dashcore import api_team as team
        current = {a["id"]: a["model"] for a in team.team_state("w1")[1]["agents"]}
        status, p = ov.apply_overlay("w1", "claude-team", VARS, {"models": current})
        self.assertEqual(status, 200, p.get("error"))
        self.assertEqual(_tree(self.ws), before)

    def test_reactivation_modeles_manifeste_corrompu_409(self):
        self._team()
        path = self.ws / ".claude" / "team.json"
        path.write_text("{corrompu", encoding="utf-8")
        # Hook géré modifié : une application partielle le remettrait à jour.
        self._touch_managed_hook()
        before = _tree(self.ws)
        for opts in ({"models": {"critic": "sonnet"}}, {"regenerate": True}):
            with self.subTest(opts=opts):
                status, p = ov.apply_overlay("w1", "claude-team", VARS, opts)
                self.assertEqual(status, 409)
                self.assertIn("manifeste corrompu", p["error"])
                # 409 avant toute écriture : arborescence intacte.
                self.assertEqual(_tree(self.ws), before)

    def _touch_managed_hook(self):
        hook = self.ws / ".claude" / "hooks" / "team-router.py"
        hook.write_text(hook.read_text(encoding="utf-8") + "# ancienne version\n", encoding="utf-8")

    def _pending(self, n: int = 7):
        journal = self.ws / ".claude" / "journal" / "changes.jsonl"
        journal.parent.mkdir(parents=True, exist_ok=True)
        journal.write_text(json.dumps({"iteration": n, "status": "pending"}) + "\n", encoding="utf-8")

    def test_regenerer_iteration_en_attente_409_si_reecriture_reelle(self):
        self._team()
        self._pending()
        # Sans réécriture réelle d'un agent : « Régénérer » passe.
        before = _tree(self.ws)
        status, p = ov.apply_overlay("w1", "claude-team", VARS, {"regenerate": True})
        self.assertEqual(status, 200, p.get("error"))
        self.assertEqual(_tree(self.ws), before)
        # Corps modifié depuis la phase 1 : la régénération réécrirait l'agent.
        body = self.ws / ".claude" / "team" / "agents" / "critic.md"
        body.write_text(body.read_text(encoding="utf-8") + "\nAjout.\n", encoding="utf-8")
        self._touch_managed_hook()
        before = _tree(self.ws)
        status, p = ov.apply_overlay("w1", "claude-team", VARS, {"regenerate": True})
        self.assertEqual(status, 409)
        self.assertEqual(p["pending"], {"iteration": 7})
        self.assertIn("agents générés", p["error"])
        self.assertEqual(_tree(self.ws), before)
        # Sans « Régénérer », l'agent présent n'est pas réécrit : passe.
        status, p = ov.apply_overlay("w1", "claude-team", VARS, {})
        self.assertEqual(status, 200, p.get("error"))
        self.assertEqual(p["generated"], [])


class RemovalCacheAndAgentsTests(RemovalBase):
    def _pyc(self, rel: str) -> Path:
        p = self.ws / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"\x00pyc")
        return p

    def test_pycache_des_hooks_archive_dossier_retire(self):
        cache = ".claude/hooks/__pycache__/"
        self._pyc(cache + "em-dash-precommit.cpython-313.pyc")
        self._pyc(cache + "statusline.cpython-313.opt-1.pyc")
        # Cache hors des dossiers de hooks du module : jamais touché.
        other = self._pyc(".claude/outils/__pycache__/x.cpython-313.pyc")
        status, p = _remove("w1", "claude-self-improving")
        self.assertEqual(status, 200, p.get("error"))
        arch = self.ws / p["archive_dir"]
        self.assertFalse((self.ws / ".claude" / "hooks").exists())
        self.assertTrue((arch / cache / "em-dash-precommit.cpython-313.pyc").is_file())
        self.assertTrue((arch / cache / "statusline.cpython-313.opt-1.pyc").is_file())
        self.assertIn(cache + "em-dash-precommit.cpython-313.pyc", p["moved"])
        self.assertTrue(other.is_file())

    def test_pycache_d_un_script_du_projet_garde(self):
        hooks = self.ws / ".claude" / "hooks"
        (hooks / "perso.py").write_text("# hook du projet\n", encoding="utf-8")
        mine = self._pyc(".claude/hooks/__pycache__/perso.cpython-313.pyc")
        self._pyc(".claude/hooks/__pycache__/em-dash-precommit.cpython-313.pyc")
        status, p = _remove("w1", "claude-self-improving")
        self.assertEqual(status, 200, p.get("error"))
        self.assertTrue(mine.is_file())
        self.assertTrue((hooks / "perso.py").is_file())
        self.assertFalse((hooks / "__pycache__" / "em-dash-precommit.cpython-313.pyc").exists())

    def test_agent_auto_amelioration_modifie_laisse_en_place(self):
        agent = self.ws / ".claude" / "agents" / "slug-expert.md"
        agent.write_text(agent.read_text(encoding="utf-8") + "\nRègle du projet.\n", encoding="utf-8")
        p = self._plan("claude-self-improving")
        keep, arch = self._reasons(p["keep"]), self._reasons(p["archive"])
        self.assertEqual(keep[".claude/agents/slug-expert.md"], "modifié : conservé")
        self.assertNotIn(".claude/agents/slug-expert.md", arch)
        self.assertEqual(arch[".claude/agents/slug-impl-validator.md"], "identique au rendu")
        status, r = _remove("w1", "claude-self-improving")
        self.assertEqual(status, 200, r.get("error"))
        self.assertIn("Règle du projet.", agent.read_text(encoding="utf-8"))
        self.assertFalse((self.ws / ".claude" / "agents" / "slug-impl-validator.md").exists())


@unittest.skipUnless(HAVE_REAL, "overlays réels absents")
class OverlayHttpRouteTests(unittest.TestCase):
    """Routes de retrait et agents-config sur un serveur réel."""

    @classmethod
    def setUpClass(cls):
        from test_server_http import XHR, request
        cls.XHR, cls.request = XHR, staticmethod(request)
        cls.base = SANDBOX / "http-removal"
        rmtree(cls.base)
        cls.srv = ServerProcess(cls.base)
        cls.srv.start()
        _copy_real_templates(cls.srv.root / "templates")
        cls.ws = cls.srv.root / "workspaces" / "ws1"

    @classmethod
    def tearDownClass(cls):
        cls.srv.stop()
        rmtree(cls.base)

    def post(self, path, body, xhr=True):
        status, _, data = self.request(self.srv.port, "POST", path, body=body,
                                       headers=self.XHR if xhr else None)
        return status, json.loads(data or b"{}")

    def test_agents_config(self):
        """POST .../team/agents-config : garde XHR, 400, 200 + régénération,
        409 itération en attente ; le module est retiré en fin de test."""
        base = "/api/workspaces/ws1/overlays/"
        self.assertEqual(self.post(base + "claude-self-improving", {})[0], 200)
        self.assertEqual(self.post(base + "claude-team", {})[0], 200)
        url = "/api/workspaces/ws1/team/agents-config"
        body = {"agents": {"reviewer": {"model": "opus", "effort": "high"}}}
        self.assertEqual(self.post(url, body, xhr=False)[0], 403)
        self.assertEqual(self.post(url, {"agents": {"reviewer": {"effort": "turbo"}}})[0], 400)
        self.assertEqual(self.post("/api/workspaces/absent/team/agents-config", body)[0], 404)
        status, p = self.post(url, body)
        self.assertEqual(status, 200, p)
        self.assertEqual(p["generated"], [".claude/agents/ws1-reviewer.md"])
        self.assertIn("effort: high", (self.ws / ".claude" / "agents" / "ws1-reviewer.md")
                      .read_text(encoding="utf-8"))
        status, _, data = self.request(self.srv.port, "GET", "/api/workspaces/ws1/team")
        st = json.loads(data)
        self.assertEqual({a["id"]: a for a in st["agents"]}["reviewer"]["effective_effort"], "high")
        self.assertIn("suggestions", st)
        journal = self.ws / ".claude" / "journal" / "changes.jsonl"
        journal.write_text(json.dumps({"iteration": 1, "status": "pending"}) + "\n", encoding="utf-8")
        self.assertEqual(self.post(url, {"agents": {"reviewer": {"effort": "low"}}})[0], 409)
        status, prev = self.post(base + "claude-team/remove", {"dry_run": True})
        self.assertEqual(status, 200, prev)
        status, p = self.post(base + "claude-team/remove", {"plan_id": prev["plan_id"]})
        self.assertEqual(status, 200, p)
        status, prev = self.post(base + "claude-self-improving/remove", {"dry_run": True})
        status, p = self.post(base + "claude-self-improving/remove", {"plan_id": prev["plan_id"]})
        self.assertEqual(status, 200, p)

    def test_apercu_puis_execution(self):
        url = "/api/workspaces/ws1/overlays/claude-self-improving"
        self.assertEqual(self.post(url, {})[0], 200)
        self.assertEqual(self.post(url + "/remove", {"dry_run": True}, xhr=False)[0], 403)
        before = _tree(self.ws)
        status, prev = self.post(url + "/remove", {"dry_run": True})
        self.assertEqual(status, 200, prev)
        self.assertEqual(_tree(self.ws), before)  # aperçu : aucune écriture
        # Un fichier change entre l'aperçu et l'exécution : 409, rien touché.
        mem = self.ws / ".claude" / "memory" / "conventions.md"
        mem.write_text(mem.read_text(encoding="utf-8") + "\nnote\n", encoding="utf-8")
        before = _tree(self.ws)
        status, p = self.post(url + "/remove", {"plan_id": prev["plan_id"]})
        self.assertEqual(status, 409, p)
        self.assertEqual(_tree(self.ws), before)
        status, p = self.post(url + "/remove", {"plan_id": p["plan_id"]})
        self.assertEqual(status, 200, p)
        self.assertTrue(p["restart_needed"])
        self.assertFalse((self.ws / ".claude" / "improvements.md").exists())
        self.assertEqual(self.post("/api/workspaces/ws1/overlays/inconnu/remove",
                                   {"dry_run": True})[0], 404)
        self.assertEqual(self.post("/api/workspaces/absent/overlays/claude-team/remove",
                                   {"dry_run": True})[0], 404)


if __name__ == "__main__":
    unittest.main()
