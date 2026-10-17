"""Moteur de la boucle d'amélioration pilotée par Nebula (module claude-team).

Nebula enchaîne en Python les deux phases de `/improve`
(templates/claude-team/.claude/commands/improve.md) dans un seul job :

  1. candidat : baseline (journal réutilisé si l'empreinte est inchangée,
     sinon mesure), critique, validation, sauvegarde `.before`, diff
     appliqué, agents régénérés, ligne `pending` au journal ;
  2. verdict : contrôle d'empreinte, mesure du candidat, `decide_verdict`,
     commit (gardé) ou restauration (écarté), ligne de résolution, item de
     `improvements.md` mis à jour.

Chaque appel `claude -p` (dashcore/claude_runner.py) est une NOUVELLE
session qui relit les agents régénérés : la mesure du candidat est donc
valide dans le même job. La ligne `pending` est quand même écrite entre les
deux phases, pour rester compatible avec `/improve` manuel (une itération
interrompue se tranche ensuite par Nebula ou par `/improve`).

Claude headless ne fait que trois choses, en permissions restreintes :
jouer un agent sur un cas (relais), noter un `rubric` en aveugle
(`<p>-evaluator`, sans l'`input` du cas) et produire le JSON du critique
(`<p>-critic`). TOUT ce qui écrit sous `.claude/` ou `.git` est fait ici.

Jamais d'écriture sous `.claude/evals/` (lecture seule du jeu), jamais de
modification de la section `improvement_loop` de `.claude/team.json`.

Stdlib only.
"""
from __future__ import annotations

import datetime as dt
import difflib
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from dashcore import claude_runner as cr
from dashcore import unidiff as ud
from dashcore.api_team import (
    _claude_path, _parse_journal, effective_prefix, generate_agents, load_manifest,
    manifest_agents, read_baseline_file, team_config_hash,
)
from dashcore.config import (
    IMPROVE_CALL_TIMEOUT, IMPROVE_CRITIC_FORBIDDEN, IMPROVE_CRITIC_LOOP_COMMANDS,
    IMPROVE_CRITIC_TARGETS,
    IMPROVE_JOB_TIMEOUT, IMPROVE_LOGS_DIR, IMPROVE_MAX_USD_PER_ITERATION,
    IMPROVE_RELAY_TOOLS, IMPROVE_TEST_TIMEOUT, TEAM_EFFORT_LEVELS, TEAM_MODEL_ALIASES,
    _MUTATION_LOCK, log,
)

VALID_GRADERS = ("test", "regex", "exact", "rubric")
CRITIC_KEYS = ("hypothesis", "improvement_item", "target", "kind", "diff",
               "expected_fixes", "risk")
MANIFEST_REL = ".claude/team.json"
PENDING_DIR_REL = Path(".claude") / "journal" / "pending"
REJECTED_DIR_REL = Path(".claude") / "journal" / "rejected"
IMPROVEMENTS_REL = Path(".claude") / "improvements.md"
GOT_MAX_LINES = 10
CAPTURE_FILE = "capture.json"
DIRTY_TEAM_REASON = ("modifications non commitées dans la configuration de l'équipe : "
                     "commite-les ou annule-les avant de lancer la boucle")
_WS_LOCKS: dict[str, threading.Lock] = {}
_WS_LOCKS_GUARD = threading.Lock()


# --- Erreurs -------------------------------------------------------------------

class EngineError(Exception):
    """Arrêt du moteur ; `status` = code HTTP suggéré pour la route."""

    status = 500

    def __init__(self, message: str, status: int | None = None, **extra):
        super().__init__(message)
        if status is not None:
            self.status = status
        self.extra = extra


class ConflictError(EngineError):
    status = 409


class QuotaReached(EngineError):
    """Limite d'abonnement : `reset` = heure annoncée par Claude ou None."""

    status = 429

    def __init__(self, message: str, reset: str | None = None):
        super().__init__(message, reset=reset)
        self.reset = reset


class BudgetExceeded(EngineError):
    status = 402


class Cancelled(EngineError):
    status = 499


class JobTimeout(EngineError):
    status = 504


class AgentsMissing(EngineError):
    status = 503


# --- Notation (fonctions pures) --------------------------------------------------

def _grade(passed: bool, reason: str = "", unrunnable: bool = False, score: float | None = None) -> dict:
    return {"pass": bool(passed), "score": float(score if score is not None else (1.0 if passed else 0.0)),
            "unrunnable": bool(unrunnable), "reason": reason}


def grade_exact(target: str, expected: str) -> dict:
    """`exact` : `target.strip() == expected.strip()`."""
    ok = (target or "").strip() == (expected or "").strip()
    return _grade(ok, "" if ok else "sortie différente de l'attendu exact")


def grade_regex(check: str, target: str) -> dict:
    """`regex` : `re.search(check, target, re.M)` ; motif invalide = inexécutable."""
    try:
        ok = re.search(check or "", target or "", re.M) is not None
    except re.error as e:
        return _grade(False, f"motif regex invalide : {e}", unrunnable=True)
    return _grade(ok, "" if ok else "motif non trouvé dans la cible")


_NOT_FOUND_RE = re.compile(r"not recognized as an internal or external command|n'est pas reconnu"
                           r"|command not found|No such file or directory", re.I)


def grade_test(check: str, target: str, ws_dir: Path, timeout: float = IMPROVE_TEST_TIMEOUT) -> dict:
    """`test` : `target` écrit dans un fichier temporaire, `{output}` = son
    chemin, `{workspace}` = racine ; commande lancée par le shell du poste
    depuis la racine ; exit 0 = succès. Commande introuvable = inexécutable."""
    fd, tmp = tempfile.mkstemp(prefix="nebula-eval-", suffix=".txt")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(target or "")
        cmd = (check or "").replace("{output}", tmp).replace("{workspace}", str(ws_dir))
        if not cmd.strip():
            return _grade(False, "commande `check` vide", unrunnable=True)
        try:
            p = subprocess.run(cmd, shell=True, cwd=str(ws_dir), capture_output=True,
                               timeout=timeout)
        except subprocess.TimeoutExpired:
            return _grade(False, f"commande `check` au-delà de {timeout:.0f} s")
        except OSError as e:
            return _grade(False, f"commande `check` inexécutable : {e}", unrunnable=True)
        err = (p.stderr or b"").decode("utf-8", errors="replace")
        out = (p.stdout or b"").decode("utf-8", errors="replace")
        if p.returncode in (127, 9009) or (p.returncode != 0 and _NOT_FOUND_RE.search(err)
                                           and p.returncode in (1, 127, 9009)):
            return _grade(False, f"commande introuvable : {err.strip()[-200:]}", unrunnable=True)
        if p.returncode == 0:
            return _grade(True)
        return _grade(False, f"exit {p.returncode} : {(err or out).strip()[-300:]}")
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def decide_verdict(score_before: float, failures_before, score_after: float, failures_after,
                   accept_if: dict | None) -> dict:
    """Règles de `improve.md` : gain = après - avant ; régressions = ids
    échoués maintenant et absents de `failures_before`. Accepté si gain >=
    `min_score_gain` ET régressions <= `max_regressions` (lus dans
    `improvement_loop.accept_if`, jamais modifiés ; défauts 0,02 et 0)."""
    a = accept_if if isinstance(accept_if, dict) else {}
    try:
        min_gain = float(a.get("min_score_gain", 0.02))
    except (TypeError, ValueError):
        min_gain = 0.02
    try:
        max_reg = int(a.get("max_regressions", 0))
    except (TypeError, ValueError):
        max_reg = 0
    gain = round(float(score_after) - float(score_before), 6)
    regressions = sorted(set(failures_after or ()) - set(failures_before or ()))
    accepted = gain >= min_gain - 1e-9 and len(regressions) <= max_reg
    if accepted:
        reason = f"gain {gain:+.4f} >= {min_gain}, {len(regressions)} régression(s)"
    elif gain < min_gain - 1e-9:
        reason = f"gain {gain:+.4f} < {min_gain}"
    else:
        reason = f"{len(regressions)} régression(s) > {max_reg} : {', '.join(regressions)}"
    return {"accepted": accepted, "gain": gain, "regressions": regressions,
            "min_score_gain": min_gain, "max_regressions": max_reg, "reason": reason}


def _id_list(v) -> list[str]:
    """Ids d'une liste du journal (chaînes ou objets `{"id"}`) ; [] sinon."""
    if not isinstance(v, list):
        return []
    return [x if isinstance(x, str) else str((x or {}).get("id")) for x in v
            if isinstance(x, str) or isinstance(x, dict)]


def compare_on_runnable(case_ids, failures_before, unrunnable_before, failures_after,
                        unrunnable_after) -> dict:
    """Référence et candidat comparés sur le MÊME ensemble de cas : ceux
    exécutables dans les deux mesures (l'union des inexécutables est exclue
    du score ET des régressions). `undecidable` si aucun cas n'est comparable
    ou si plus de la moitié des cas sont exclus (fonction pure)."""
    ids = list(dict.fromkeys(str(i) for i in case_ids or ()))
    union = set(unrunnable_before or ()) | set(unrunnable_after or ())
    excluded = [i for i in ids if i in union]
    common = [i for i in ids if i not in union]
    keep = set(common)
    fb = sorted(set(failures_before or ()) & keep)
    fa = sorted(set(failures_after or ()) & keep)
    n = len(common)
    return {"total": len(ids), "compared": common, "excluded": excluded,
            "failures_before": fb, "failures_after": fa,
            "score_before": round((n - len(fb)) / n, 4) if n else 0.0,
            "score_after": round((n - len(fa)) / n, 4) if n else 0.0,
            "undecidable": n == 0 or 2 * len(excluded) > len(ids)}


# --- Cibles du critique -------------------------------------------------------------

def _forbidden_by_manifest(rel: str, manifest: dict | None) -> bool:
    """Corps du critique ET de l'évaluateur (le critique ne modifie jamais le
    juge) déclarés dans le manifeste, et dossier du jeu d'évals
    (comparaison insensible à la casse)."""
    rel = rel.casefold()
    loop = (manifest or {}).get("improvement_loop") or {}
    eval_set = str(loop.get("eval_set") or "evals/eval-set.jsonl").replace("\\", "/")
    eval_dir = (".claude/" + eval_set.rsplit("/", 1)[0] if "/" in eval_set else ".claude").casefold()
    if eval_dir != ".claude" and (rel == eval_dir or rel.startswith(eval_dir + "/")):
        return True
    for a in manifest_agents(manifest or {"agents": []}):
        if a.get("id") in ("critic", "evaluator"):
            f = str(a.get("file") or f"team/agents/{a.get('id')}.md").replace("\\", "/")
            if rel == (".claude/" + f).casefold():
                return True
    return False


_LOOP_COMMANDS_RE = r"\.claude/commands/(?:" + "|".join(
    re.escape(c) for c in IMPROVE_CRITIC_LOOP_COMMANDS) + r")\.md"


def is_forbidden_target(rel: str, manifest: dict | None = None) -> bool:
    """Liste noire du critique, INSENSIBLE à la casse (défense en profondeur :
    sous Windows `Critic.md` désigne `critic.md`) : IMPROVE_CRITIC_FORBIDDEN,
    commandes de la boucle (IMPROVE_CRITIC_LOOP_COMMANDS), corps du critique
    et jeu d'évals déclarés par le manifeste."""
    low = rel.casefold()
    if any(re.fullmatch(p, low, re.I) for p in (*IMPROVE_CRITIC_FORBIDDEN, _LOOP_COMMANDS_RE)):
        return True
    return _forbidden_by_manifest(rel, manifest)


def target_allowed(ws_dir: Path, rel: str, manifest: dict | None = None) -> tuple[bool, str]:
    """Cible du critique autorisée ? Ordre (défense en profondeur) :
    1. chemin vérifié et résolu sous le workspace (`unidiff.check_rel_path`
       en `strict_case` : ni absolu, ni `\\`, ni `:`, ni segment vide / `.` /
       `..`, ni lien ou jonction sur le trajet, et chemin demandé IDENTIQUE,
       casse comprise, au chemin réel résolu) ;
    2. SEULEMENT ENSUITE, chemin réel (posix, relatif) comparé à la liste
       noire (`is_forbidden_target`, insensible à la casse) puis à la liste
       blanche (IMPROVE_CRITIC_TARGETS)."""
    try:
        real = ud.check_rel_path(ws_dir, rel, strict_case=True)
        real_rel = real.relative_to(Path(ws_dir).resolve()).as_posix()
    except (ud.DiffError, ValueError) as e:
        return False, str(e)
    if real_rel != rel:  # déjà garanti par strict_case ; jamais de comparaison sur `rel` seul
        return False, f"chemin refusé (chemin réel {real_rel}) : {rel}"
    if is_forbidden_target(rel, manifest) or is_forbidden_target(real_rel, manifest):
        return False, f"cible interdite : {rel}"
    if not any(re.fullmatch(p, real_rel) for p in IMPROVE_CRITIC_TARGETS):
        return False, f"cible hors liste blanche : {rel}"
    return True, ""


def _check_team_json(before: str, after: str) -> str:
    """'' si `after` ne change que la section `agents` (ids et `file`
    inchangés, modèle et effort dans les listes de config), sinon la raison."""
    try:
        old = json.loads(before)
        new = json.loads(after)
    except ValueError as e:
        return f"team.json invalide après application : {e}"
    if not isinstance(new, dict) or not isinstance(old, dict):
        return "team.json : objet JSON attendu"
    for k in set(old) | set(new):
        if k != "agents" and old.get(k) != new.get(k):
            return f"team.json : seule la section agents peut changer (section {k} modifiée)"
    oa, na = old.get("agents"), new.get("agents")
    if not isinstance(na, list) or not isinstance(oa, list) or len(na) != len(oa):
        return "team.json : la liste des agents doit garder les mêmes entrées"
    for o, n in zip(oa, na):
        if not isinstance(n, dict) or not isinstance(o, dict):
            return "team.json : agent non objet"
        if (o.get("id"), o.get("file")) != (n.get("id"), n.get("file")):
            return f"team.json : id ou file de l'agent {o.get('id')} modifié"
        if o.get("id") in ("evaluator", "critic"):
            if o != n:
                return f"team.json : l'agent {o.get('id')} ne peut pas être modifié par le critique"
            continue
        for k in (set(o) | set(n)) - {"model", "effort"}:
            if o.get(k) != n.get(k) or (k in o) != (k in n):
                return (f"team.json : seules les clés model et effort de l'agent "
                        f"{o.get('id')} peuvent changer (clé {k} modifiée)")
        if "model" in n and n["model"] not in TEAM_MODEL_ALIASES:
            return f"team.json : modèle invalide pour {n.get('id')} ({n['model']})"
        if "effort" in n and n["effort"] not in TEAM_EFFORT_LEVELS:
            return f"team.json : effort invalide pour {n.get('id')} ({n['effort']})"
    return ""


def parse_critic_output(text: str) -> dict:
    """Objet JSON du critique (texte du premier `{` au dernier `}`), clés de
    CRITIC_KEYS présentes. EngineError(400) sinon."""
    t = text or ""
    t = t[t.find("{"):t.rfind("}") + 1] if "{" in t and "}" in t else ""
    try:
        d = json.loads(t)
    except ValueError as e:
        raise EngineError(f"sortie du critique non JSON : {e}", status=400) from e
    if not isinstance(d, dict):
        raise EngineError("sortie du critique : objet JSON attendu", status=400)
    missing = [k for k in CRITIC_KEYS if k not in d]
    if missing:
        raise EngineError(f"sortie du critique incomplète (clés absentes : {', '.join(missing)})",
                          status=400)
    return d


def validate_candidate(proposal: dict, ws_dir: Path, manifest: dict | None) -> dict:
    """Validation du candidat du critique, sans rien écrire.

    Une seule cible (chaîne sur une ligne, sans virgule), autorisée
    (`target_allowed`), diff unifié d'UN fichier qui vise exactement cette
    cible et s'applique strictement ; pour `.claude/team.json`, rien d'autre
    que la section `agents` ne change. Retourne {"ok", "reason", "target",
    "before", "after"}."""
    target = proposal.get("target") if isinstance(proposal, dict) else None
    out = {"ok": False, "reason": "", "target": target if isinstance(target, str) else None,
           "before": None, "after": None}
    if not isinstance(target, str) or not target.strip() or "\n" in target or "," in target:
        out["reason"] = "une seule cible attendue (chaîne sur une ligne)"
        return out
    target = target.strip()
    out["target"] = target
    ok, why = target_allowed(ws_dir, target, manifest)
    if not ok:
        out["reason"] = why
        return out
    diff = proposal.get("diff")
    if not isinstance(diff, str) or not diff.strip():
        out["reason"] = "diff absent"
        return out
    try:
        r = ud.apply_diff(diff, ws_dir, allowed=lambda rel: target_allowed(ws_dir, rel, manifest)[0],
                          expected_path=target, write=False)
    except ud.DiffError as e:
        out["reason"] = f"diff invalide : {e}"
        return out
    if target == MANIFEST_REL:
        why = _check_team_json(r["before"], r["after"])
        if why:
            out["reason"] = why
            return out
    out.update(ok=True, before=r["before"], after=r["after"])
    return out


# --- improvements.md -----------------------------------------------------------------

_ITEM_RE = re.compile(r"^- \*\*\[(?P<status>[^\]]+)\]\s*(?P<title>.+?)\*\*")


def extract_todo_items(text: str) -> list[dict]:
    """Items `- **[TODO] <titre>** ...` : [{"title", "line" (0-based), "block"}]."""
    lines = (text or "").splitlines()
    out = []
    for i, line in enumerate(lines):
        m = _ITEM_RE.match(line)
        if not m or m.group("status").strip() != "TODO":
            continue
        j = i + 1
        while j < len(lines) and lines[j].startswith((" ", "\t")):
            j += 1
        out.append({"title": m.group("title").strip(), "line": i, "block": "\n".join(lines[i:j])})
    return out


def update_improvement_item(path: Path, title: str, status: str, measure: str) -> bool:
    """Passe l'item `[TODO] <titre>` en `[<status>]` (ex. `DONE 2026-10-17`,
    `ABANDONED`) et ajoute « Mesure : ... » à la fin de son bloc. `.bak`
    avant écriture, écriture atomique. False si l'item est introuvable."""
    with _MUTATION_LOCK:
        try:
            raw = path.read_bytes()
        except OSError:
            return False
        text = raw.decode("utf-8", errors="strict")
        newline = "\r\n" if "\r\n" in text else "\n"
        lines = text.replace("\r\n", "\n").split("\n")
        want = (title or "").strip()
        for i, line in enumerate(lines):
            m = _ITEM_RE.match(line)
            if not m or m.group("status").strip() != "TODO" or m.group("title").strip() != want:
                continue
            lines[i] = line.replace("[TODO]", f"[{status}]", 1)
            j = i + 1
            while j < len(lines) and lines[j].startswith((" ", "\t")):
                j += 1
            lines.insert(j, f"  - {measure}")
            shutil.copy2(path, path.with_name(path.name + ".bak"))
            ud.write_text_atomic(path, newline.join(lines))
            return True
    return False


# --- Journal -----------------------------------------------------------------------

def journal_path(ws_dir: Path, manifest: dict | None) -> Path:
    loop = (manifest or {}).get("improvement_loop") or {}
    p = _claude_path(ws_dir, str(loop.get("journal") or "journal/changes.jsonl"))
    if p is None:
        raise EngineError("journal hors de .claude refusé", status=400)
    return p


def read_journal(ws_dir: Path, manifest: dict | None) -> list[dict]:
    return _parse_journal(journal_path(ws_dir, manifest))[0]


def _iter_of(e: dict, i: int) -> int:
    return e["iteration"] if isinstance(e.get("iteration"), int) else i


def last_lines(entries: list[dict]) -> dict[int, dict]:
    """Dernière ligne de chaque itération (elle fait foi)."""
    out: dict[int, dict] = {}
    for i, e in enumerate(entries, 1):
        out[_iter_of(e, i)] = e
    return out


def pending_entry(entries: list[dict]) -> dict | None:
    pend = [e for e in last_lines(entries).values()
            if str(e.get("status") or "").lower().startswith(("pend", "attente"))]
    return pend[-1] if pend else None


def next_iteration(entries: list[dict]) -> int:
    its = list(last_lines(entries))
    return (max(its) if its else 0) + 1


def append_journal(ws_dir: Path, manifest: dict | None, entry: dict) -> None:
    """Ajoute UNE ligne JSON au journal (jamais verrouillé), sous _MUTATION_LOCK."""
    p = journal_path(ws_dir, manifest)
    with _MUTATION_LOCK:
        p.parent.mkdir(parents=True, exist_ok=True)
        prefix = ""
        try:
            data = p.read_bytes()
            if data and not data.endswith(b"\n"):
                prefix = "\n"
        except OSError:
            pass
        with open(p, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(prefix + json.dumps(entry, ensure_ascii=False) + "\n")


# --- Git ---------------------------------------------------------------------------

def _git(ws_dir: Path, *args: str, timeout: int = 60) -> tuple[int | None, str, str]:
    """(code, stdout, stderr) ; code None si git est absent. stdout NON strippé
    (cf. pitfalls : `status --porcelain` perd l'espace initial)."""
    try:
        p = subprocess.run(["git", *args], cwd=str(ws_dir), capture_output=True, timeout=timeout,
                           env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, "", str(e)
    return (p.returncode, p.stdout.decode("utf-8", errors="replace"),
            p.stderr.decode("utf-8", errors="replace"))


def git_worktree(ws_dir: Path) -> bool:
    code, out, _ = _git(ws_dir, "rev-parse", "--is-inside-work-tree")
    return code == 0 and out.strip() == "true"


def git_tracked(ws_dir: Path, rel: str) -> bool:
    code, _, _ = _git(ws_dir, "ls-files", "--error-unmatch", "--", rel)
    return code == 0


def git_ignored(ws_dir: Path, rel: str) -> bool:
    code, _, _ = _git(ws_dir, "check-ignore", "-q", "--", rel)
    return code == 0


def git_dirty(ws_dir: Path, rel: str, untracked_all: bool = False) -> str:
    args = ["status", "--porcelain"] + (["--untracked-files=all"] if untracked_all else []) + ["--", rel]
    code, out, err = _git(ws_dir, *args)
    if code != 0:
        raise EngineError(f"git status impossible : {err.strip()}")
    return out


def team_git_capture(ctx: "EngineContext") -> dict | None:
    """État git de la configuration de l'équipe (`.claude/team.json` et
    agents générés `.claude/agents/<préfixe>-*.md`) : {"dirty": chemins
    suivis modifiés / supprimés / indexés et non commités, corps `.claude/team/agents/*.md` compris, "untracked":
    chemins non suivis}. None hors dépôt git (rien à protéger)."""
    if not git_worktree(ctx.ws_dir):
        return None
    pattern = f".claude/agents/{ctx.prefix}-*.md"
    code, out, err = _git(ctx.ws_dir, "status", "--porcelain", "--untracked-files=all", "--",
                          MANIFEST_REL, pattern, ".claude/team/agents/*.md")
    if code != 0:
        raise EngineError(f"git status impossible : {err.strip()}")
    dirty, untracked = [], []
    for line in out.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].split(" -> ")[-1].strip().strip('"')
        (untracked if line.startswith("??") else dirty).append(path)
    return {"dirty": sorted(dirty), "untracked": sorted(untracked)}


def _commit_message(prefix: str, n: int, hypothesis: str) -> str:
    """`update(<p>): improve/<n> - <hypothèse courte>` : une ligne, sans
    tiret cadratin ni demi-cadratin, sans trailer."""
    h = re.sub(r"\s+", " ", str(hypothesis or "")).strip()
    for ch in (0x2014, 0x2013, 0x2012, 0x2015, 0x2212):  # cadratins, demi-cadratin, tiret figure, barre, moins
        h = h.replace(chr(ch), "-")
    if len(h) > 60:
        h = h[:59].rstrip() + "…"
    return f"update({prefix}): improve/{n} - {h or 'candidat accepté'}"


# --- Contexte d'exécution ------------------------------------------------------------

def _zero_spend() -> dict:
    return {"cost_usd": 0.0, "tokens": {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0},
            "duration_ms": 0, "calls": 0, "permission_denials": 0, "tool_errors": 0,
            "cost_unknown_calls": 0}


def _spend_delta(after: dict, before: dict) -> dict:
    d = _zero_spend()
    for k in ("cost_usd", "duration_ms", "calls", "permission_denials", "tool_errors",
              "cost_unknown_calls"):
        d[k] = after[k] - before[k]
    d["cost_usd"] = round(d["cost_usd"], 6)
    for k in d["tokens"]:
        d["tokens"][k] = after["tokens"][k] - before["tokens"][k]
    return d


@dataclass
class EngineContext:
    """Un job : workspace, budget, délais, annulation, journaux bruts."""

    ws_dir: Path
    ws_id: str
    job_id: str = "manual"
    max_usd: float = IMPROVE_MAX_USD_PER_ITERATION
    call_timeout: float = IMPROVE_CALL_TIMEOUT
    job_timeout: float = IMPROVE_JOB_TIMEOUT
    cancel: threading.Event = field(default_factory=threading.Event)
    cmd: str | None = None
    log_dir: Path | None = None
    progress: object = None             # callable(dict) optionnel
    on_spawn: object = None             # callable(Popen) optionnel, transmis à run_claude
    started: float = field(default_factory=time.monotonic)
    spend: dict = field(default_factory=_zero_spend)
    _seq: int = 0

    def __post_init__(self):
        self.ws_dir = Path(self.ws_dir)
        if self.log_dir is None:
            self.log_dir = IMPROVE_LOGS_DIR / self.ws_id / self.job_id

    @property
    def manifest(self) -> dict:
        m = load_manifest(self.ws_dir)
        if m is None:
            raise EngineError("module claude-team inactif (manifeste absent ou illisible)", status=404)
        return m

    @property
    def prefix(self) -> str:
        return effective_prefix(self.manifest, {"name": self.ws_id})

    def config_hash(self) -> str:
        return team_config_hash(self.ws_dir, self.ws_id)

    def notify(self, **info) -> None:
        if callable(self.progress):
            try:
                self.progress(info)
            except Exception as e:  # noqa: BLE001 - un rappel d'affichage ne casse pas le job
                log.warning("progression improve : %s", e)

    def check_alive(self) -> float:
        """Délai restant du job ; lève Cancelled / JobTimeout."""
        if self.cancel.is_set():
            raise Cancelled("job annulé")
        left = self.job_timeout - (time.monotonic() - self.started)
        if left <= 0:
            raise JobTimeout(f"délai du job dépassé ({self.job_timeout:.0f} s)")
        return left

    def call(self, prompt: str, *, expect_agent: str, allowed_tools, label: str) -> cr.CallResult:
        """Un appel `claude -p` sous budget et délai ; cumule coût, jetons,
        durée, refus. Lève QuotaReached, AgentsMissing, Cancelled, JobTimeout,
        BudgetExceeded, EngineError (binaire introuvable). Les autres statuts
        (`ok`, `error`, `timeout`, `delegation_missing`) sont rendus."""
        left = self.check_alive()
        remaining = round(self.max_usd - self.spend["cost_usd"], 4)
        if remaining < 0.01:
            raise BudgetExceeded(f"plafond de dépense de l'itération atteint ({self.max_usd:.2f} USD)")
        self._seq += 1
        safe_label = re.sub(r"[^A-Za-z0-9_.-]", "_", label)[:60]
        log_path = self.log_dir / f"{self._seq:03d}-{safe_label}.jsonl" if self.log_dir else None
        self.notify(event="call", label=label, seq=self._seq)
        r = cr.run_claude(prompt, self.ws_dir, allowed_tools=allowed_tools, max_budget_usd=remaining,
                          expect_agent=expect_agent, agents_prefix=self.prefix,
                          timeout=min(self.call_timeout, left), cancel=self.cancel,
                          log_path=log_path, cmd=self.cmd, on_spawn=self.on_spawn)
        s = self.spend
        s["calls"] += 1
        s["cost_usd"] = round(s["cost_usd"] + r.cost_usd, 6)
        if not r.cost_known:
            s["cost_unknown_calls"] += 1
        s["duration_ms"] += r.duration_ms
        s["permission_denials"] += r.permission_denials
        s["tool_errors"] += r.tool_errors
        for k in s["tokens"]:
            s["tokens"][k] += int(r.tokens.get(k) or 0)
        if r.status == "quota":
            raise QuotaReached(r.error, r.quota_reset)
        if r.status == "agents_missing":
            raise AgentsMissing(r.error)
        if r.status == "cancelled":
            raise Cancelled("job annulé")
        if r.status == "spawn_error":
            raise EngineError(r.error, status=503)
        if r.status == "timeout":
            self.check_alive()  # délai du job épuisé -> JobTimeout
        return r


# --- Prompts -----------------------------------------------------------------------

def relay_prompt(agent_name: str, text: str) -> str:
    """Prompt du fil principal : déléguer `text` TEL QUEL à `agent_name`,
    puis répondre FIN."""
    return (
        "Tu es un relais de mesure automatique (Nebula, boucle d'amélioration). Ta seule tâche :\n"
        f"1. Appelle l'outil Agent UNE seule fois avec subagent_type: {agent_name} et"
        "   run_in_background: false (attends sa réponse avant de répondre),\n"
        "   et, comme prompt, le texte situé entre les lignes <<<ENTREE>>> et <<<FIN ENTREE>>>,\n"
        "   recopié TEL QUEL (sans rien ajouter, retirer ni reformuler).\n"
        "2. Quand l'agent a répondu, réponds uniquement FIN. Ne commente pas, ne corrige pas,\n"
        "   n'exécute rien d'autre, ne lis aucun fichier.\n"
        "<<<ENTREE>>>\n" + (text or "") + "\n<<<FIN ENTREE>>>\n"
    )


def evaluator_payload(case_id: str, target: str, expected: str, rubric: str) -> str:
    """Entrée de l'évaluateur en aveugle : id, sortie, attendu, grille.
    JAMAIS l'`input` du cas (format du corps `evaluator.md`)."""
    return (f"ID: {case_id}\nSORTIE: {target}\nATTENDU: {expected}\nGRILLE: {rubric}\n"
            "Rends UNIQUEMENT ton objet JSON {\"id\", \"pass\", \"score\", \"reason\"}.")


def _got(text: str) -> str:
    return "\n".join((text or "").splitlines()[:GOT_MAX_LINES])


# --- Mesure ------------------------------------------------------------------------

def load_cases(ws_dir: Path, manifest: dict) -> list[dict]:
    """Cas de `eval-set.jsonl` (LECTURE seule ; jamais `holdout.jsonl`)."""
    loop = manifest.get("improvement_loop") or {}
    p = _claude_path(ws_dir, str(loop.get("eval_set") or "evals/eval-set.jsonl"))
    if p is None or not p.is_file():
        raise EngineError("jeu d'évals introuvable", status=404)
    cases, invalid = _parse_journal(p)
    if invalid:
        log.warning("eval-set : %d ligne(s) invalide(s) ignorée(s)", invalid)
    return [c for c in cases if isinstance(c.get("id"), str) and c["id"]]


def _scope_of(ws_dir: Path, case: dict) -> tuple[str | None, str]:
    """(scope normalisé, raison si invalide)."""
    raw = case.get("scope")
    if raw in (None, ""):
        return None, ""
    scope = str(raw).strip().rstrip("/")
    # Refus de `.claude` / `.git` insensible à la casse (`.Claude` désigne
    # `.claude` sous Windows), AVANT et APRÈS résolution (chemin réel exigé
    # identique au chemin demandé, casse comprise).
    if scope.split("/")[0].casefold() in (".claude", ".git"):
        return None, f"scope refusé (sous {scope.split('/')[0]}) : {scope}"
    try:
        ud.check_rel_path(ws_dir, scope, strict_case=True)
    except ud.DiffError as e:
        return None, f"scope invalide : {e}"
    return scope, ""


def _restore_scope(ws_dir: Path, scope: str) -> str:
    """`git checkout` + `git clean -fdx` (ignorés compris) LIMITÉS au scope ; '' ou la raison
    d'une restauration incomplète."""
    _git(ws_dir, "checkout", "--", scope)  # sans fichier suivi : erreur sans effet
    code, _, err = _git(ws_dir, "clean", "-fdx", "--", scope)
    if code != 0:
        return f"git clean a échoué : {err.strip()}"
    try:
        left = git_dirty(ws_dir, scope, untracked_all=True)
    except EngineError as e:
        return str(e)
    return f"scope non restauré : {left.strip()}" if left.strip() else ""


def _rubric_score(text: str) -> float | None:
    t = text or ""
    t = t[t.find("{"):t.rfind("}") + 1] if "{" in t and "}" in t else ""
    try:
        d = json.loads(t)
        s = float(d.get("score"))
    except (ValueError, TypeError, AttributeError):
        return None
    return min(max(s, 0.0), 1.0)


def run_case(ctx: EngineContext, case: dict, manifest: dict, prefix: str,
             strict_ids: set | None = None) -> dict:
    """Un cas : relais vers `<p>-<agent>`, cible, notation. Les exceptions
    d'arrêt (quota, budget, annulation, délai) remontent après restauration."""
    res = _run_case(ctx, case, manifest, prefix)
    if (res.pop("relay_failed", False) and res.get("unrunnable")
            and strict_ids is not None and res["id"] in strict_ids):
        # Cas réussi à la référence et relais en échec sur le candidat
        # (timeout, délégation absente, erreur) : échec, donc régression.
        res.update(unrunnable=False, **{"pass": False}, score=0.0)
        res["reason"] = "échec du relais sur le candidat : " + str(res.get("reason") or "")
    return res


def _run_case(ctx: EngineContext, case: dict, manifest: dict, prefix: str) -> dict:
    cid = case["id"]
    agent = str(case.get("agent") or "orchestrator")
    grader = case.get("grader")
    kind = str(case.get("target") or "output")
    res = {"id": cid, "agent": agent, "tags": [t for t in case.get("tags") or [] if isinstance(t, str)],
           "pass": False, "score": 0.0, "unrunnable": False, "reason": "", "got": "",
           "expected": str(case.get("expected") or "")}

    def unrunnable(reason: str) -> dict:
        res.update(unrunnable=True, reason=reason)
        return res

    if agent not in {a["id"] for a in manifest_agents(manifest)}:
        return unrunnable(f"agent inconnu du manifeste : {agent}")
    if grader not in VALID_GRADERS:
        return unrunnable(f"grader invalide : {grader}")
    scope, why = _scope_of(ctx.ws_dir, case)
    if why:
        return unrunnable(why)
    if kind == "diff" and not scope:
        return unrunnable("target: diff sans scope")
    if scope:
        if not git_worktree(ctx.ws_dir):
            return unrunnable("workspace sans dépôt git : cas à scope inexécutable")
        if git_ignored(ctx.ws_dir, scope):
            return unrunnable(f"scope ignoré par git (restauration impossible) : {scope}")
        if git_dirty(ctx.ws_dir, scope).strip():
            return unrunnable(f"scope non propre avant le cas (git status non vide) : {scope}")
    name = f"{prefix}-{agent}"
    tools = list(IMPROVE_RELAY_TOOLS)
    if scope:
        tools += [f"Write(./{scope}/**)", f"Edit(./{scope}/**)"]
    target_text = None
    try:
        r = ctx.call(relay_prompt(name, str(case.get("input") or "")), expect_agent=name,
                     allowed_tools=tools, label=f"case-{cid}")
        res["refusals"] = r.refusals
        if r.agent_output is None:
            res["relay_failed"] = True
            return unrunnable(f"relais en échec ({r.status}) : {r.error}")
        if kind == "output":
            target_text = r.agent_output
        elif kind == "diff":
            target_text = git_dirty(ctx.ws_dir, scope, untracked_all=True)
            code, out, err = _git(ctx.ws_dir, "diff", "--", scope)
            target_text += out
        elif kind.startswith("file:"):
            rel = kind[5:].strip()
            try:
                target_text = ud.check_rel_path(ctx.ws_dir, rel).read_text(encoding="utf-8")
            except (ud.DiffError, OSError, UnicodeDecodeError) as e:
                res["reason"] = f"fichier cible illisible ou absent : {rel} ({e})"
                return res
        else:
            return unrunnable(f"target invalide : {kind}")
    finally:
        if scope:
            bad = _restore_scope(ctx.ws_dir, scope)
            if bad:
                res["restore_error"] = bad
    res["got"] = _got(target_text)
    if grader == "exact":
        g = grade_exact(target_text, str(case.get("expected") or ""))
    elif grader == "regex":
        g = grade_regex(str(case.get("check") or ""), target_text)
    elif grader == "test":
        g = grade_test(str(case.get("check") or ""), target_text, ctx.ws_dir)
    else:
        g = _grade_rubric(ctx, case, target_text, manifest, prefix)
    res.update(g)
    return res


def _grade_rubric(ctx: EngineContext, case: dict, target: str, manifest: dict, prefix: str) -> dict:
    """`rubric` : `<p>-evaluator` en aveugle, `runs` passes (défaut
    `runs_per_eval`), moyenne ; pass = moyenne >= 0,5."""
    loop = manifest.get("improvement_loop") or {}
    runs = case.get("runs") if isinstance(case.get("runs"), int) and case["runs"] > 0 \
        else (loop.get("runs_per_eval") if isinstance(loop.get("runs_per_eval"), int) else 3)
    runs = max(1, min(int(runs), 10))
    name = f"{prefix}-evaluator"
    payload = evaluator_payload(case["id"], target, str(case.get("expected") or ""),
                                str(case.get("rubric") or ""))
    scores = []
    for k in range(runs):
        r = ctx.call(relay_prompt(name, payload), expect_agent=name,
                     allowed_tools=list(IMPROVE_RELAY_TOOLS), label=f"rubric-{case['id']}-{k + 1}")
        if r.agent_output is None:
            g = _grade(False, f"évaluateur en échec ({r.status}) : {r.error}", unrunnable=True)
            g["relay_failed"] = True
            return g
        s = _rubric_score(r.agent_output)
        if s is None:
            return _grade(False, "note de l'évaluateur illisible", unrunnable=True)
        scores.append(s)
    avg = round(sum(scores) / len(scores), 4)
    return _grade(avg >= 0.5, f"moyenne {avg} sur {runs} passe(s)", score=avg)


def aggregate(results: list[dict], config_version: str) -> dict:
    """Rapport au format de `/eval`. Un cas inexécutable n'est ni réussi ni
    échoué : il est exclu du score, des ratios et de `failures` (listé dans
    `unrunnable_ids`) ; `passed + failed + unrunnable == total`."""
    total = len(results)
    runnable = [r for r in results if not r["unrunnable"]]
    passed = sum(1 for r in runnable if r["pass"])

    def ratio(rs):
        rs = [r for r in rs if not r["unrunnable"]]
        return round(sum(1 for r in rs if r["pass"]) / len(rs), 4) if rs else 0.0
    tags = sorted({t for r in results for t in r["tags"]})
    agents = sorted({r["agent"] for r in results})
    return {
        "config_version": config_version,
        "score": round(passed / len(runnable), 4) if runnable else 0.0,
        "passed": passed, "failed": len(runnable) - passed, "total": total,
        "unrunnable": total - len(runnable),
        "unrunnable_ids": [r["id"] for r in results if r["unrunnable"]],
        "by_tag": {t: ratio([r for r in results if t in r["tags"]]) for t in tags},
        "by_agent": {a: ratio([r for r in results if r["agent"] == a]) for a in agents},
        "failures": [{"id": r["id"], "agent": r["agent"], "expected": r["expected"],
                      "got": r["got"], "reason": r["reason"]} for r in runnable if not r["pass"]],
        "cases": [{k: r.get(k) for k in ("id", "agent", "pass", "score", "unrunnable", "reason")}
                  for r in results],
    }


def measure(ctx: EngineContext, strict_ids=None) -> dict:
    """Mesure la configuration courante sur tout `eval-set.jsonl`.
    `strict_ids` : cas réussis à la référence ; un relais en échec sur l'un
    d'eux compte comme échec (et non comme inexécutable)."""
    strict = set(strict_ids) if strict_ids is not None else None
    manifest = ctx.manifest
    prefix = ctx.prefix
    version = ctx.config_hash()
    before = json.loads(json.dumps(ctx.spend))
    results = []
    for case in load_cases(ctx.ws_dir, manifest):
        ctx.notify(event="case", id=case["id"])
        results.append(run_case(ctx, case, manifest, prefix, strict))
    report = aggregate(results, version)
    report["spend"] = _spend_delta(ctx.spend, before)
    if strict_ids is None:
        write_baseline(ctx, report)
    return report


def write_baseline(ctx: EngineContext, report: dict) -> None:
    """Mesure de référence durable `.claude/journal/baseline.json` (écriture
    atomique). Pas de ligne au journal : son format est partagé avec /improve."""
    p = _claude_path(ctx.ws_dir, "journal/baseline.json")
    if p is None:
        return
    data = {"config_version": report["config_version"], "score": report["score"],
            "failures": [f["id"] for f in report.get("failures") or []],
            "unrunnable": report["unrunnable"],
            "unrunnable_ids": list(report.get("unrunnable_ids") or []),
            "measured_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "runner": "nebula", "cases": report["total"]}
    with _MUTATION_LOCK:
        p.parent.mkdir(parents=True, exist_ok=True)
        ud.write_text_atomic(p, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


# --- Régénération, sauvegarde, restauration --------------------------------------------

def _agent_files(ctx: EngineContext) -> list[Path]:
    return sorted((ctx.ws_dir / ".claude" / "agents").glob(f"{ctx.prefix}-*.md"))


def regenerate(ctx: EngineContext) -> list[str]:
    """`generate_agents(..., {"regenerate": True})` ; chemins (relatifs à la
    racine) des agents dont le contenu a réellement changé."""
    def snap():
        out = {}
        for p in _agent_files(ctx):
            try:
                out[p.relative_to(ctx.ws_dir).as_posix()] = p.read_bytes()
            except OSError:
                pass
        return out
    with _MUTATION_LOCK:
        before = snap()
        generate_agents(ctx.ws_dir, {"name": ctx.ws_id, "label": ctx.ws_id}, {"regenerate": True})
        after = snap()
    return sorted(rel for rel in after if before.get(rel) != after[rel])


def _pending_dir(ws_dir: Path, n: int) -> Path:
    return ws_dir / PENDING_DIR_REL / str(int(n))


def _before_file(ws_dir: Path, n: int, target: str) -> Path:
    return _pending_dir(ws_dir, n) / (Path(target).name + ".before")


def _archive_diff(ws_dir: Path, n: int, target: str, before: str | None) -> str | None:
    """Diff candidat (sauvegarde -> cible actuelle) archivé dans
    `.claude/journal/rejected/<n>/candidate.diff` ; chemin relatif ou None."""
    if before is None:
        return None
    try:
        current = (ws_dir / target).read_text(encoding="utf-8")
    except OSError:
        current = ""
    diff = "".join(difflib.unified_diff(before.splitlines(True), current.splitlines(True),
                                        fromfile=f"a/{target}", tofile=f"b/{target}"))
    d = ws_dir / REJECTED_DIR_REL / str(int(n))
    d.mkdir(parents=True, exist_ok=True)
    ud.write_text_atomic(d / "candidate.diff", diff)
    return (d / "candidate.diff").relative_to(ws_dir).as_posix()


def _restore_target(ctx: EngineContext, n: int, target: str) -> str:
    """Remet la cible depuis `.before` (sinon depuis git) ; 'before' | 'git'."""
    bf = _before_file(ctx.ws_dir, n, target)
    dest = ud.check_rel_path(ctx.ws_dir, target)
    with _MUTATION_LOCK:
        if bf.is_file():
            data = bf.read_bytes()
            fd, tmp = tempfile.mkstemp(dir=str(dest.parent), prefix=f".{dest.name}.", suffix=".tmp")
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            os.replace(tmp, dest)
            return "before"
        code, _, err = _git(ctx.ws_dir, "checkout", "--", target)
        if code != 0:
            raise ConflictError(f"restauration impossible : ni sauvegarde .before ni git ({err.strip()})")
        return "git"


def _cleanup_pending(ws_dir: Path, n: int) -> None:
    d = _pending_dir(ws_dir, n)
    if d.is_dir():
        shutil.rmtree(d)


def _read_before_text(ws_dir: Path, n: int, target: str) -> str | None:
    try:
        return _before_file(ws_dir, n, target).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


# --- Lignes de journal ------------------------------------------------------------------

def _today() -> str:
    return dt.date.today().isoformat()


def _spend_fields(spend: dict) -> dict:
    return {"cost_usd": spend["cost_usd"], "tokens": spend["tokens"],
            "duration_ms": spend["duration_ms"], "calls": spend["calls"],
            "permission_denials": spend["permission_denials"]}


def _baseline_from_file(ws_dir: Path, config_hash: str) -> tuple[dict, str] | None:
    b = read_baseline_file(ws_dir)
    if not b or b["config_version"] != config_hash or b.get("unrunnable"):
        return None
    ids = [f if isinstance(f, str) else str((f or {}).get("id")) for f in b["failures"]]
    return ({"config_version": config_hash, "score": float(b["score"]), "unrunnable": 0,
             "unrunnable_ids": [],
             "failures": [{"id": i, "agent": "", "expected": "", "got": "", "reason": "baseline"}
                          for i in ids], "reused": True, "spend": _zero_spend()},
            str(b.get("measured_at") or ""))


def _baseline_reusable(ws_dir: Path, entries: list[dict], config_hash: str) -> dict | None:
    """Journal et baseline.json : à empreinte égale, le plus récent. Sans date
    de journal exploitable, ou à égalité de jour, le journal l'emporte."""
    j = _baseline_from_journal(entries, config_hash)
    f = _baseline_from_file(ws_dir, config_hash)
    if f is None:
        return j
    if j is None:
        return f[0]
    resolved = [e for e in last_lines(entries).values()
                if str(e.get("status") or "").lower().startswith(("accept", "reject", "rejet"))]
    jdate = str(resolved[-1].get("date") or "")[:10]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", jdate) and f[1][:10] > jdate:
        return f[0]
    return j


def _baseline_from_journal(entries: list[dict], config_hash: str) -> dict | None:
    """Mesure réutilisable : dernière ligne résolue de même empreinte, sans
    cas inexécutable, avec la liste des échecs. None sinon."""
    resolved = [e for e in last_lines(entries).values()
                if str(e.get("status") or "").lower().startswith(("accept", "reject", "rejet"))]
    if not resolved:
        return None
    last = resolved[-1]
    if str(last.get("config_version") or "") != config_hash or last.get("unrunnable"):
        return None
    accepted = str(last.get("status")).lower().startswith("accept")
    score = last.get("score_after") if accepted else last.get("score_before")
    fails = last.get("failures_after") if accepted else last.get("failures_before")
    if not isinstance(score, (int, float)) or not isinstance(fails, list):
        return None
    ids = [f if isinstance(f, str) else str((f or {}).get("id")) for f in fails]
    return {"config_version": config_hash, "score": float(score), "unrunnable": 0,
            "unrunnable_ids": [],
            "failures": [{"id": i, "agent": "", "expected": "", "got": "", "reason": "journal"}
                         for i in ids], "reused": True,
            "spend": _zero_spend()}


# --- Phase 1 : candidat ---------------------------------------------------------------------

def _critic_prompt(n: int, baseline: dict, entries: list[dict], todos: list[dict],
                   manifest: dict) -> str:
    fails = baseline.get("failures") or []
    lines = [f"Contexte : boucle /improve pilotée par Nebula, itération {n} (tu es bien invoqué "
             "par la boucle).",
             f"Baseline : score {baseline.get('score')}, configuration {baseline.get('config_version')}.",
             "Échecs de la baseline :"]
    for f in fails:
        lines.append(f"- {f['id']} ({f.get('agent') or '?'}) : {f.get('reason') or 'échec'}"
                     + (f" ; attendu : {f['expected']}" if f.get("expected") else "")
                     + (f" ; obtenu : {f['got']}" if f.get("got") else ""))
    if not fails:
        lines.append("- aucun")
    unrun = [str(i) for i in baseline.get("unrunnable_ids") or []]
    if unrun:
        lines.append("Cas inexécutables à la baseline (exclus du score, pas des échecs d'agent) : "
                     + ", ".join(unrun))
    lines.append("Journal des itérations précédentes (`.claude/journal/changes.jsonl`) :")
    hist = list(last_lines(entries).items())
    for it, e in hist:
        lines.append(f"- itération {it} : {e.get('status')}, cible {e.get('target')}, hypothèse "
                     f"« {e.get('hypothesis')} », score {e.get('score_before')} -> "
                     f"{e.get('score_after')}" + (f", raison : {e['reason']}" if e.get("reason") else ""))
    if not hist:
        lines.append("- vide")
    rejected = [e.get("hypothesis") for _, e in hist
                if str(e.get("status")).lower().startswith("rej") and e.get("hypothesis")]
    if rejected:
        lines.append("Hypothèses déjà écartées (ne pas les reproposer) : "
                     + " | ".join(str(h) for h in rejected))
    lines.append("Items [TODO] de `.claude/improvements.md` :")
    lines += [f"- {t['title']}" for t in todos] or ["- aucun"]
    lines += [
        "Cibles autorisées (UNE seule, chemin relatif à la racine du workspace) :",
        "- .claude/team/agents/<id>.md (corps d'agent, sauf critic.md et evaluator.md)",
        "- .claude/team.json (section agents seulement ; model parmi "
        f"{', '.join(TEAM_MODEL_ALIASES)} ; effort parmi {', '.join(TEAM_EFFORT_LEVELS)})",
        "- .claude/commands/<nom>.md (sauf les commandes de la boucle : "
        + ", ".join(f"{c}.md" for c in IMPROVE_CRITIC_LOOP_COMMANDS) + ")",
        "- .claude/memory/**/*.md",
        "Jamais .claude/evals/, jamais la section improvement_loop.",
        "Le champ diff est un diff unifié d'UN seul fichier (en-têtes `--- a/<cible>` et "
        "`+++ b/<cible>`), contexte recopié À L'IDENTIQUE du fichier actuel (lis-le d'abord).",
        "Rends UNIQUEMENT ton objet JSON de sortie (7 clés : hypothesis, improvement_item, "
        "target, kind, diff, expected_fixes, risk), rien d'autre.",
    ]
    return "\n".join(lines)


def candidate_phase(ctx: EngineContext, baseline: dict | None = None) -> dict:
    """Phase 1 : baseline, critique, validation, candidat en place, ligne
    `pending` (ou `rejected` si le candidat est invalide, sans mesure)."""
    manifest = ctx.manifest
    entries = read_journal(ctx.ws_dir, manifest)
    if pending_entry(entries):
        raise ConflictError("une itération attend déjà son verdict")
    spend0 = json.loads(json.dumps(ctx.spend))
    # Capture git de la configuration de l'équipe AVANT toute régénération :
    # une modification non commitée (manifeste ou agent généré) serait
    # écrasée par la régénération ou partirait dans le commit de l'itération.
    capture = team_git_capture(ctx)
    if capture is not None and capture["dirty"]:
        # Refus sans écriture au journal : aucun numéro d'itération consommé.
        return {"phase": "candidate", "status": "rejected", "iteration": None,
                "reason": DIRTY_TEAM_REASON, "dirty_paths": capture["dirty"],
                "baseline": None, "entry": None}
    # Agents alignés sur leurs sources AVANT la baseline : sinon le candidat
    # embarquerait aussi une régénération en retard (gain non attribuable).
    regenerate(ctx)
    current = ctx.config_hash()
    if baseline is None:
        baseline = _baseline_reusable(ctx.ws_dir, entries, current)
    if baseline is None:
        baseline = measure(ctx)
        baseline["reused"] = False
    if baseline.get("config_version") != current:
        raise EngineError("la configuration a changé pendant la mesure de la baseline", status=409)
    n = next_iteration(entries)
    imp = ctx.ws_dir / IMPROVEMENTS_REL
    try:
        todos = extract_todo_items(imp.read_text(encoding="utf-8"))
    except OSError:
        todos = []
    critic = f"{ctx.prefix}-critic"
    r = ctx.call(relay_prompt(critic, _critic_prompt(n, baseline, entries, todos, manifest)),
                 expect_agent=critic, allowed_tools=list(IMPROVE_RELAY_TOOLS), label="critic")
    failures_before = [f["id"] for f in baseline.get("failures") or []]
    base_line = {"iteration": n, "date": _today(), "score_before": baseline.get("score"),
                 "failures_before": failures_before, "baseline_version": current,
                 "unrunnable": int(baseline.get("unrunnable") or 0),
                 "unrunnable_ids": [str(i) for i in baseline.get("unrunnable_ids") or []],
                 "runner": "nebula",
                 "job_id": ctx.job_id, "branch": None}

    def reject(reason: str, proposal: dict | None = None) -> dict:
        p = proposal or {}
        entry = {**base_line, "target": str(p.get("target") or ""),
                 "hypothesis": str(p.get("hypothesis") or ""), "status": "rejected",
                 "reason": reason, "score_after": None, "regressions": [],
                 "config_version": ctx.config_hash(), "commit": None,
                 **_spend_fields(_spend_delta(ctx.spend, spend0))}
        append_journal(ctx.ws_dir, manifest, entry)
        return {"phase": "candidate", "status": "rejected", "iteration": n, "reason": reason,
                "baseline": baseline, "entry": entry}

    if r.agent_output is None:
        return reject(f"critique en échec ({r.status}) : {r.error}")
    try:
        proposal = parse_critic_output(r.agent_output)
    except EngineError as e:
        return reject(str(e))
    v = validate_candidate(proposal, ctx.ws_dir, manifest)
    if not v["ok"]:
        return reject(v["reason"], proposal)
    target = v["target"]
    tracked = git_worktree(ctx.ws_dir) and git_tracked(ctx.ws_dir, target)
    if tracked and git_dirty(ctx.ws_dir, target).strip():
        return reject(f"cible modifiée et non commitée : {target}", proposal)
    with _MUTATION_LOCK:
        pdir = _pending_dir(ctx.ws_dir, n)
        pdir.mkdir(parents=True, exist_ok=True)
        dest = ud.check_rel_path(ctx.ws_dir, target)
        shutil.copy2(dest, _before_file(ctx.ws_dir, n, target))
        try:
            ud.apply_diff(proposal["diff"], ctx.ws_dir,
                          allowed=lambda rel: target_allowed(ctx.ws_dir, rel, manifest)[0],
                          expected_path=target)
        except ud.DiffError as e:
            _cleanup_pending(ctx.ws_dir, n)
            return reject(f"diff invalide : {e}", proposal)
        changed_agents = regenerate(ctx)
        ud.write_text_atomic(pdir / "regenerated.json", json.dumps(changed_agents))
        if capture is not None:
            ud.write_text_atomic(pdir / CAPTURE_FILE, json.dumps(capture))
        version = ctx.config_hash()
        entry = {**base_line, "target": target, "hypothesis": str(proposal.get("hypothesis") or ""),
                 "improvement_item": proposal.get("improvement_item"),
                 "kind": proposal.get("kind"), "risk": proposal.get("risk"),
                 "expected_fixes": [x for x in proposal.get("expected_fixes") or []
                                    if isinstance(x, str)],
                 "status": "pending", "config_version": version, "untracked": not tracked,
                 "baseline_reused": bool(baseline.get("reused")),
                 **_spend_fields(_spend_delta(ctx.spend, spend0))}
        append_journal(ctx.ws_dir, manifest, entry)
    return {"phase": "candidate", "status": "pending", "iteration": n, "target": target,
            "baseline": baseline, "regenerated": changed_agents, "entry": entry}


# --- Phase 2 : verdict ----------------------------------------------------------------------

def _resolution_line(pend: dict, ctx: EngineContext, spend0: dict, **fields) -> dict:
    base = {k: pend.get(k) for k in ("iteration", "target", "hypothesis", "score_before",
                                     "failures_before", "baseline_version", "improvement_item")}
    return {**base, "date": _today(), "runner": "nebula", "job_id": ctx.job_id,
            **_spend_fields(_spend_delta(ctx.spend, spend0)),
            "config_version": ctx.config_hash(), "unrunnable_ids": [], **fields}


def _refuse_manual_branch(pend: dict, n: int) -> None:
    """`pending` posée par `/improve` manuel sur une vraie branche (`branch`
    non nul, `runner` autre que `nebula`) : Nebula ne la tranche pas (ni
    verdict ni abandon), ConflictError (409) sans rien écrire."""
    branch = pend.get("branch")
    if branch and str(pend.get("runner") or "") != "nebula":
        raise ConflictError(f"itération ouverte à la main sur la branche improve/{n} : tranche-la "
                            "avec /improve dans une nouvelle session", branch=str(branch))


def _commit(ctx: EngineContext, n: int, pend: dict) -> tuple[str | None, bool, str]:
    """(hash court, untracked, raison d'échec) : commit limité à la cible et
    aux agents régénérés réellement changés, suivis par git, et jamais à un
    chemin déjà modifié avant l'itération (capture `capture.json` de la
    phase candidat) : seuls partent les chemins changés PAR l'itération."""
    target = str(pend.get("target") or "")
    if not git_worktree(ctx.ws_dir):
        return None, True, ""
    pdir = _pending_dir(ctx.ws_dir, n)
    try:
        regen = json.loads((pdir / "regenerated.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        regen = []
    try:
        cap = json.loads((pdir / CAPTURE_FILE).read_text(encoding="utf-8"))
        pre_dirty = {p for p in cap.get("dirty") or [] if isinstance(p, str)}
    except (OSError, ValueError, AttributeError):
        pre_dirty = set()
    paths = [p for p in dict.fromkeys([target, *[x for x in regen if isinstance(x, str)]])
             if p not in pre_dirty and git_tracked(ctx.ws_dir, p) and git_dirty(ctx.ws_dir, p).strip()]
    if not git_tracked(ctx.ws_dir, target):
        return None, True, ""
    if not paths:
        return None, False, "rien à commiter (cible identique au dépôt)"
    msg = _commit_message(ctx.prefix, n, str(pend.get("hypothesis") or ""))
    code, _, err = _git(ctx.ws_dir, "commit", "-m", msg, "--", *paths, timeout=120)
    if code != 0:
        return None, False, f"commit refusé : {err.strip()[-300:]}"
    code, out, _ = _git(ctx.ws_dir, "rev-parse", "--short", "HEAD")
    return (out.strip() or None), False, ""


def _measure_line(before, after, verdict: dict, commit: str | None, n: int) -> str:
    gain = verdict["gain"]
    if verdict["accepted"]:
        regs = len(verdict["regressions"])
        return (f"Mesure : score {before} -> {after} (gain {gain:+.2f}, {regs} régression), "
                f"commit {commit or 'aucun'}, itération {n}")
    regs = ", ".join(verdict["regressions"]) or "aucune"
    return f"Mesure : score {before} -> {after} (gain {gain:+.2f}, régressions : {regs}), itération {n}"


def verdict_phase(ctx: EngineContext) -> dict:
    """Phase 2 : contrôle d'empreinte, mesure, verdict, commit ou
    restauration, ligne de résolution, item de `improvements.md`."""
    manifest = ctx.manifest
    entries = read_journal(ctx.ws_dir, manifest)
    pend = pending_entry(entries)
    if not pend:
        raise ConflictError("aucune itération en attente de verdict")
    n = int(pend.get("iteration") or next_iteration(entries) - 1)
    _refuse_manual_branch(pend, n)
    target = str(pend.get("target") or "")
    try:
        ud.check_rel_path(ctx.ws_dir, target)
    except ud.DiffError as e:
        raise ConflictError(f"cible de l'itération en attente invalide : {e}") from e
    has_before = _before_file(ctx.ws_dir, n, target).is_file()
    if not has_before and not (git_worktree(ctx.ws_dir) and git_tracked(ctx.ws_dir, target)):
        raise ConflictError("itération en attente sans sauvegarde .before ni git : restauration "
                            "impossible, à trancher à la main")
    spend0 = json.loads(json.dumps(ctx.spend))
    before_text = _read_before_text(ctx.ws_dir, n, target)
    if ctx.config_hash() != str(pend.get("config_version") or ""):
        archive = _archive_diff(ctx.ws_dir, n, target, before_text)
        _restore_target(ctx, n, target)
        regenerate(ctx)
        _cleanup_pending(ctx.ws_dir, n)
        entry = _resolution_line(pend, ctx, spend0, status="rejected", reason="candidat altéré",
                                 score_after=None, regressions=[], commit=None,
                                 untracked=bool(pend.get("untracked")), unrunnable=0,
                                 diff_archive=archive)
        append_journal(ctx.ws_dir, manifest, entry)
        return {"phase": "verdict", "status": "rejected", "iteration": n, "reason": "candidat altéré",
                "entry": entry}
    ref_bad = set(_id_list(pend.get("failures_before"))) | set(_id_list(pend.get("unrunnable_ids")))
    strict = {str(c["id"]) for c in load_cases(ctx.ws_dir, manifest)} - ref_bad
    report = measure(ctx, strict_ids=strict)
    failures_after = [f["id"] for f in report["failures"]]
    cmp = compare_on_runnable([c["id"] for c in report["cases"]],
                              _id_list(pend.get("failures_before")), _id_list(pend.get("unrunnable_ids")),
                              failures_after, report["unrunnable_ids"])
    if cmp["undecidable"]:
        # Mesure non probante : rien n'est restauré ni commité, aucune ligne
        # de résolution ; l'itération reste `pending` (à retrancher plus tard).
        reason = (f"verdict non tranché : {len(cmp['excluded'])} cas inexécutable(s) sur "
                  f"{cmp['total']} (plus de la moitié) à la référence ou au candidat ; "
                  "l'itération reste en attente")
        return {"phase": "verdict", "status": "pending", "iteration": n, "reason": reason,
                "comparison": cmp, "report": report, "entry": None}
    verdict = decide_verdict(cmp["score_before"], cmp["failures_before"],
                             cmp["score_after"], cmp["failures_after"],
                             (manifest.get("improvement_loop") or {}).get("accept_if"))
    verdict["comparison"] = cmp
    commit, untracked, reason, archive = None, bool(pend.get("untracked")), verdict["reason"], None
    restore_ok = True
    if verdict["accepted"]:
        commit, untracked, commit_err = _commit(ctx, n, pend)
        if commit_err:
            reason += f" ; {commit_err}"
        _cleanup_pending(ctx.ws_dir, n)
    else:
        archive = _archive_diff(ctx.ws_dir, n, target, before_text)
        _restore_target(ctx, n, target)
        regenerate(ctx)
        restore_ok = ctx.config_hash() == str(pend.get("baseline_version") or "")
        if not restore_ok:
            reason += " ; empreinte après restauration différente de la baseline"
        _cleanup_pending(ctx.ws_dir, n)
    status = "accepted" if verdict["accepted"] else "rejected"
    entry = _resolution_line(pend, ctx, spend0, status=status, score_after=report["score"],
                             regressions=verdict["regressions"], commit=commit, untracked=untracked,
                             unrunnable=report["unrunnable"],
                             unrunnable_ids=report["unrunnable_ids"], failures_after=failures_after,
                             reason=reason, diff_archive=archive,
                             score_before_compared=cmp["score_before"],
                             score_after_compared=cmp["score_after"],
                             excluded_unrunnable=cmp["excluded"])
    if not restore_ok:
        entry["restore_mismatch"] = True
    append_journal(ctx.ws_dir, manifest, entry)
    item = pend.get("improvement_item")
    item_updated = False
    if isinstance(item, str) and item.strip():
        label = f"DONE {_today()}" if verdict["accepted"] else "ABANDONED"
        item_updated = update_improvement_item(
            ctx.ws_dir / IMPROVEMENTS_REL, item, label,
            _measure_line(cmp["score_before"], cmp["score_after"], verdict, commit, n))
    return {"phase": "verdict", "status": status, "iteration": n, "verdict": verdict,
            "report": report, "commit": commit, "untracked": untracked, "entry": entry,
            "improvement_item_updated": item_updated}


# --- Abandon, itération complète ---------------------------------------------------------------

def _ws_lock(ws_dir: Path) -> threading.Lock:
    key = str(Path(ws_dir).resolve()).lower()
    with _WS_LOCKS_GUARD:
        return _WS_LOCKS.setdefault(key, threading.Lock())


def abandon_pending(ctx: EngineContext, reason: str = "abandonné") -> dict:
    """Abandonne l'itération `pending` (posée par Nebula ou par `/improve`
    manuel) : diff archivé, cible restaurée (`.before`, sinon git), agents
    régénérés, ligne `rejected`. ConflictError (409) sans itération en
    attente, ou sans `.before` ni git."""
    lock = _ws_lock(ctx.ws_dir)
    if not lock.acquire(blocking=False):
        raise ConflictError("une itération est déjà en cours sur ce workspace")
    try:
        manifest = ctx.manifest
        entries = read_journal(ctx.ws_dir, manifest)
        pend = pending_entry(entries)
        if not pend:
            raise ConflictError("aucune itération en attente")
        n = int(pend.get("iteration") or 0)
        _refuse_manual_branch(pend, n)
        target = str(pend.get("target") or "")
        try:
            ud.check_rel_path(ctx.ws_dir, target)
        except ud.DiffError as e:
            raise ConflictError(f"cible invalide : {e}") from e
        if not _before_file(ctx.ws_dir, n, target).is_file() and not (
                git_worktree(ctx.ws_dir) and git_tracked(ctx.ws_dir, target)):
            raise ConflictError("ni sauvegarde .before ni git : restauration impossible")
        spend0 = json.loads(json.dumps(ctx.spend))
        archive = _archive_diff(ctx.ws_dir, n, target, _read_before_text(ctx.ws_dir, n, target))
        how = _restore_target(ctx, n, target)
        regenerate(ctx)
        _cleanup_pending(ctx.ws_dir, n)
        entry = _resolution_line(pend, ctx, spend0, status="rejected", reason=reason,
                                 score_after=None, regressions=[], commit=None,
                                 untracked=bool(pend.get("untracked")), unrunnable=0,
                                 diff_archive=archive, restored_from=how)
        append_journal(ctx.ws_dir, manifest, entry)
        return {"status": "rejected", "iteration": n, "restored_from": how, "entry": entry}
    finally:
        lock.release()


def run_iteration(ctx: EngineContext) -> dict:
    """Une itération complète dans un seul job : phase 2 seule si une ligne
    `pending` existe déjà (job interrompu, `/improve` manuel), sinon phase 1
    puis phase 2 (chaque appel `claude -p` relit les agents régénérés)."""
    lock = _ws_lock(ctx.ws_dir)
    if not lock.acquire(blocking=False):
        raise ConflictError("une itération est déjà en cours sur ce workspace")
    try:
        if pending_entry(read_journal(ctx.ws_dir, ctx.manifest)):
            return {"candidate": None, "verdict": verdict_phase(ctx), "spend": ctx.spend}
        cand = candidate_phase(ctx)
        if cand["status"] != "pending":
            return {"candidate": cand, "verdict": None, "spend": ctx.spend}
        return {"candidate": cand, "verdict": verdict_phase(ctx), "spend": ctx.spend}
    finally:
        lock.release()
