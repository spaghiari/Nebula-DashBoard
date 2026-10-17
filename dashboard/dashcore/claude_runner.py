"""Appel de Claude Code en mode headless (`claude -p`) pour la boucle
d'amélioration pilotée par Nebula (cf. dashcore/improve_engine.py).

Claude ne fait ici qu'une chose par appel, en permissions restreintes :
jouer un agent sur un cas d'éval, noter une sortie `rubric` en aveugle ou
produire le JSON du critique. Le fil principal de chaque appel est un
simple relais qui délègue l'entrée TELLE QUELLE à `<p>-<agent>` (outil
Agent) puis répond FIN ; Nebula lit la sortie de l'agent dans le
`tool_result` du `tool_use` Agent.

Garde-fous (vérifiés par tests/test_claude_runner.py) :
  - jamais `--bare`, `bypassPermissions` ni `--dangerously-skip-permissions`
    (IMPROVE_FORBIDDEN_ARGS) : `build_args` lève ValueError ;
  - `--permission-mode dontAsk` + `--allowedTools` explicite +
    `--disallowedTools Bash ...` (y compris dans les sous-agents) ;
  - prompt sur STDIN (`--allowedTools` est variadique) ;
  - flux stream-json lu ligne à ligne en UTF-8, stderr dans un fichier
    temporaire (jamais un PIPE non lu, cf. pitfalls) ;
  - pas de timeout natif côté Claude : délai géré ici, arbre de processus
    tué (`taskkill /PID <pid> /T /F` sous Windows, groupe de processus
    ailleurs) ; annulation par drapeau (`threading.Event`) ;
  - `system/init` doit lister des agents `<p>-*` (sinon `agents_missing`,
    appel interrompu) : protège contre un futur `--bare` par défaut.

Statuts d'un appel (`CallResult.status`) : `ok`, `error` (sous-type du
`result`, ex. `error_max_turns`, ou sortie sans `result`), `timeout`,
`cancelled`, `quota` (limite d'abonnement, `quota_reset` = heure extraite
du message ou None), `delegation_missing` (aucun `tool_result` du
`tool_use` Agent attendu), `agents_missing`, `spawn_error`.

Stdlib only.
"""
from __future__ import annotations

import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from dashcore import config
from dashcore.config import (
    IMPROVE_CALL_TIMEOUT, IMPROVE_DISALLOWED_TOOLS, IMPROVE_FORBIDDEN_ARGS,
    IMPROVE_RELAY_EFFORT, IMPROVE_RELAY_MAX_TURNS, IMPROVE_RELAY_MODEL, log,
)

# Noms de l'outil de délégation (Agent ; Task dans les anciennes versions).
_AGENT_TOOL_NAMES = ("Agent", "Task")
# Limite d'abonnement : « You've hit your session limit · resets 3:45pm »,
# « weekly limit », « Opus limit », « usage limit ».
_QUOTA_RE = re.compile(
    r"hit your (?:session |weekly |opus |usage )?limit|(?:session|weekly|opus|usage) limit",
    re.I)
_RESET_RE = re.compile(
    r"resets?\s+(?:at\s+)?((?:(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*\.?,?\s+(?:at\s+)?)?"
    r"\d{1,2}(?::\d{2})?\s*(?:[ap]\.?m\.?)?)", re.I)
_RESET_PARTS_RE = re.compile(
    r"\A(?:(mon|tue|wed|thu|fri|sat|sun)[a-z]*\.?,?\s+(?:at\s+)?)?"
    r"(\d{1,2})(?::(\d{2}))?\s*([ap])?\.?(?:m\.?)?\Z", re.I)
_WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
# En-tête ajouté par Claude Code au `tool_result` d'un sous-agent.
_HANDBACK_RE = re.compile(r"\A\s*\[Subagent hand-back\][ \t]*:?[ \t]*(?:\r?\n)?")
# Bloc de métadonnées ajouté après la sortie d'un sous-agent (reprise).
_ASYNC_LAUNCH_RE = re.compile(r"\A\s*Async agent launched", re.I)
_AGENT_META_RE = re.compile(r"\A\s*agentId:\s*\S+")
_POLL = 0.2  # s : réactivité au délai et à l'annulation


class ClaudeNotFound(RuntimeError):
    """Binaire `claude` introuvable (ni NEBULA_CLAUDE_CMD, ni PATH)."""


@dataclass
class CallResult:
    """Résultat d'un appel `claude -p` (cf. statuts dans la docstring du module)."""

    status: str = "error"
    subtype: str | None = None
    is_error: bool = True
    text: str = ""                      # `result` final du fil principal
    agent_output: str | None = None     # tool_result du tool_use Agent attendu
    delegated_to: list[str] = field(default_factory=list)
    agents_loaded: list[str] | None = None
    cost_usd: float = 0.0
    cost_known: bool = False            # False : pas de `result` (timeout, kill)
    tokens: dict = field(default_factory=lambda: _zero_tokens())
    model_usage: dict = field(default_factory=dict)
    duration_ms: int = 0
    num_turns: int = 0
    permission_denials: int = 0         # `result.permission_denials`
    tool_errors: int = 0                # tool_result avec is_error (outil retiré...)
    rate_limit_retries: int = 0
    quota_reset: str | None = None
    session_id: str | None = None
    exit_code: int | None = None
    error: str = ""
    stderr_tail: str = ""

    @property
    def refusals(self) -> int:
        """Refus comptés : refus de permission + tool_result en erreur."""
        return self.permission_denials + self.tool_errors

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__} | {"refusals": self.refusals}


def _zero_tokens() -> dict:
    return {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}


# --- Ligne de commande -------------------------------------------------------

def claude_command(override: str | None = None) -> list[str]:
    """Commande de base : `override`, puis NEBULA_CLAUDE_CMD, puis `claude`
    du PATH. Un chemin `.py` est lancé avec l'interpréteur courant."""
    raw = override or config.NEBULA_CLAUDE_CMD
    if raw:
        if raw.lower().endswith(".py"):
            return [sys.executable, raw]
        return [raw]
    found = shutil.which("claude")
    if not found:
        raise ClaudeNotFound("binaire `claude` introuvable dans le PATH "
                             "(installer Claude Code ou définir NEBULA_CLAUDE_CMD)")
    return [found]


def build_args(allowed_tools, *, max_budget_usd: float, max_turns: int = IMPROVE_RELAY_MAX_TURNS,
               model: str = IMPROVE_RELAY_MODEL, effort: str = IMPROVE_RELAY_EFFORT,
               disallowed_tools=IMPROVE_DISALLOWED_TOOLS) -> list[str]:
    """Arguments de `claude -p` (sans le binaire). Le prompt n'y figure
    jamais : il passe par STDIN. ValueError si un argument interdit
    (IMPROVE_FORBIDDEN_ARGS) apparaît, ou si un outil est à la fois
    autorisé et retiré."""
    allowed = [str(t) for t in allowed_tools if str(t).strip()]
    disallowed = [str(t) for t in disallowed_tools if str(t).strip()]
    if not allowed:
        raise ValueError("liste d'outils autorisés vide")
    clash = {t.split("(")[0] for t in allowed} & set(disallowed)
    if clash:
        raise ValueError(f"outil à la fois autorisé et retiré : {', '.join(sorted(clash))}")
    args = [
        "-p",
        "--output-format", "stream-json", "--verbose",
        "--permission-mode", "dontAsk", "--permission-prompts", "none",
        "--model", model, "--effort", effort,
        "--max-turns", str(int(max_turns)),
        "--max-budget-usd", f"{max(0.01, float(max_budget_usd)):.2f}",
        "--disallowedTools", *disallowed,
        # Variadique en dernier : rien ne doit suivre (le prompt est sur stdin).
        "--allowedTools", *allowed,
    ]
    for a in args:
        for bad in IMPROVE_FORBIDDEN_ARGS:
            if bad.lower() in a.lower():
                raise ValueError(f"argument interdit dans la ligne de commande : {bad}")
    return args


# --- Arrêt de l'arbre de processus ------------------------------------------

def kill_tree(proc: subprocess.Popen) -> None:
    """Tue le processus et ses descendants (même motif qu'active_sessions.kill :
    `taskkill /T /F` sous Windows, groupe de processus ailleurs)."""
    if proc.poll() is not None:
        return
    if sys.platform == "win32":
        try:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           capture_output=True, text=True, timeout=10)
        except (subprocess.TimeoutExpired, OSError) as e:
            log.warning("taskkill %s : %s", proc.pid, e)
    else:
        import signal
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass
    if proc.poll() is None:
        try:
            proc.kill()
        except OSError:
            pass
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        log.warning("processus %s toujours vivant après kill", proc.pid)


# --- Lecture du flux ---------------------------------------------------------

def _text_of(content) -> str:
    """Texte d'un `content` de tool_result (chaîne ou liste de blocs)."""
    if isinstance(content, str):
        return content
    parts: list[str] = []
    if isinstance(content, list):
        for b in content:
            if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str):
                if parts and _AGENT_META_RE.match(b["text"]):
                    continue  # métadonnées de reprise après la sortie
                parts.append(b["text"])
            elif isinstance(b, str):
                parts.append(b)
    return "\n".join(parts)


def clean_agent_output(text: str) -> str:
    """Sortie d'un sous-agent sans l'en-tête « [Subagent hand-back] »."""
    return _HANDBACK_RE.sub("", text or "", count=1)


class _StreamState:
    def __init__(self, expect_agent: str | None, agents_prefix: str | None):
        self.expect_agent = expect_agent
        self.agents_prefix = agents_prefix
        self.agent_tool_ids: dict[str, str] = {}   # tool_use_id -> subagent_type
        self.r = CallResult()
        self.result_seen = False
        self.init_seen = False
        self.agents_problem = ""
        self.texts: list[str] = []
        # Sous-agent lancé en arrière-plan : le tool_result n'est que le message
        # de lancement, la réponse vient des messages enfants / de la notification.
        self.bg_ids: set[str] = set()
        self.children_text: dict[str, str] = {}     # tool_use_id -> dernier texte non vide
        self.notifications: dict[str, dict] = {}    # tool_use_id -> task_notification
        self.bg_status = ""                         # "" | "error" | "missing"
        self.bg_error = ""

    def feed(self, ev: dict) -> None:
        t = ev.get("type")
        r = self.r
        if t == "system":
            sub = ev.get("subtype")
            if sub == "init":
                self.init_seen = True
                r.session_id = ev.get("session_id") or r.session_id
                raw = ev.get("agents")
                names = None
                if isinstance(raw, list):
                    names = [a if isinstance(a, str) else str((a or {}).get("name") or "")
                             for a in raw]
                r.agents_loaded = names
                if self.agents_prefix:
                    if names is None:
                        self.agents_problem = ("system/init sans liste d'agents : format du flux "
                                               "inattendu, sous-agents non vérifiables")
                    elif not any(n.startswith(self.agents_prefix + "-") for n in names):
                        self.agents_problem = (
                            f"aucun agent « {self.agents_prefix}-* » chargé par Claude Code "
                            "(mode --bare par défaut ? agents non générés ?)")
            elif sub == "api_retry":
                if "rate_limit" in str(ev.get("error") or "").lower():
                    r.rate_limit_retries += 1
            elif sub == "task_started":
                if ev.get("is_backgrounded") and ev.get("tool_use_id"):
                    self.bg_ids.add(str(ev["tool_use_id"]))
            elif sub == "task_notification":
                if ev.get("tool_use_id"):
                    self.notifications[str(ev["tool_use_id"])] = ev
        elif t == "assistant":
            msg = ev.get("message") or {}
            parent = ev.get("parent_tool_use_id")
            if parent:
                # Enfant DIRECT seulement : un agent imbriqué a son propre parent.
                for b in msg.get("content") or []:
                    if (isinstance(b, dict) and b.get("type") == "text"
                            and isinstance(b.get("text"), str) and b["text"].strip()):
                        self.children_text[str(parent)] = b["text"]
            for b in msg.get("content") or []:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_use" and b.get("name") in _AGENT_TOOL_NAMES \
                        and not ev.get("parent_tool_use_id"):
                    st = str((b.get("input") or {}).get("subagent_type") or "")
                    self.agent_tool_ids[str(b.get("id"))] = st
                    r.delegated_to.append(st)
                elif (b.get("type") == "text" and isinstance(b.get("text"), str)
                      and not ev.get("parent_tool_use_id")):
                    self.texts.append(b["text"])
        elif t == "user":
            msg = ev.get("message") or {}
            content = msg.get("content")
            for b in content if isinstance(content, list) else []:
                if not isinstance(b, dict) or b.get("type") != "tool_result":
                    continue
                if b.get("is_error"):
                    r.tool_errors += 1
                tid = str(b.get("tool_use_id"))
                if tid in self.agent_tool_ids and not b.get("is_error") \
                        and self.agent_tool_ids[tid] == self.expect_agent:
                    txt = _text_of(b.get("content"))
                    if _ASYNC_LAUNCH_RE.match(txt):
                        self.bg_ids.add(tid)
                    else:
                        r.agent_output = clean_agent_output(txt)
        elif t == "result":
            self.result_seen = True
            r.subtype = ev.get("subtype")
            r.is_error = bool(ev.get("is_error"))
            r.text = str(ev.get("result") or "")
            try:
                # Un `result` par tour : cumulatifs, on garde le plus élevé.
                r.cost_usd = max(r.cost_usd, float(ev.get("total_cost_usd") or 0.0))
                r.cost_known = True
            except (TypeError, ValueError):
                pass
            r.num_turns = int(ev.get("num_turns") or 0)
            r.duration_ms = int(ev.get("duration_ms") or 0)
            r.session_id = ev.get("session_id") or r.session_id
            denials = ev.get("permission_denials")
            r.permission_denials = len(denials) if isinstance(denials, list) else 0
            mu = ev.get("modelUsage")
            if isinstance(mu, dict):
                r.model_usage = mu
                tok = _zero_tokens()
                for u in mu.values():
                    if not isinstance(u, dict):
                        continue
                    tok["input"] += int(u.get("inputTokens") or 0)
                    tok["output"] += int(u.get("outputTokens") or 0)
                    tok["cache_read"] += int(u.get("cacheReadInputTokens") or 0)
                    tok["cache_creation"] += int(u.get("cacheCreationInputTokens") or 0)
                r.tokens = tok


    def resolve_background(self) -> None:
        """Sortie du sous-agent attendu lancé en arrière-plan (sans toucher
        au premier plan). Ne renvoie jamais le message de lancement."""
        r = self.r
        if r.agent_output is not None or not self.expect_agent:
            return
        tids = [t for t in self.bg_ids if self.agent_tool_ids.get(t) == self.expect_agent]
        if not tids:
            return
        for tid in tids:
            note = self.notifications.get(tid)
            status = str((note or {}).get("status") or "")
            if note and status != "completed":
                self.bg_status = "error"
                self.bg_error = f"sous-agent en arrière-plan terminé en « {status or 'inconnu'} »"
                return
        for tid in tids:
            reply = self.children_text.get(tid)
            if reply is None:
                note = self.notifications.get(tid)
                summary = str((note or {}).get("summary") or "")
                if summary.strip():
                    lines = summary.lstrip().split(chr(10), 1)
                    if lines[0].lstrip().startswith("[harness:"):
                        summary = lines[1] if len(lines) > 1 else ""
                    reply = summary.strip() or None
            if reply is not None:
                r.agent_output = clean_agent_output(reply)
                return
        self.bg_status = "missing"
        self.bg_error = "sous-agent en arrière-plan sans réponse"


def detect_quota(*texts: str) -> tuple[bool, str | None]:
    """(limite d'abonnement atteinte, heure de réinitialisation ou None)."""
    for t in texts:
        if t and _QUOTA_RE.search(t):
            m = _RESET_RE.search(t)
            return True, (m.group(1).strip() if m else None)
    return False, None


def parse_reset(text: str | None, now: datetime | None = None) -> str | None:
    """Convertit l'heure de réinitialisation du message (`3:45pm`, `11pm`,
    `15:45`, `Mon 12:00am`) en ISO local (secondes) de la PROCHAINE occurrence
    strictement postérieure à `now` : heure seule -> aujourd'hui ou demain ;
    jour + heure -> prochain jour de la semaine. `None` si illisible."""
    m = _RESET_PARTS_RE.match(str(text or "").strip())
    if not m:
        return None
    day, hh, mm, ampm = m.groups()
    hour, minute = int(hh), int(mm) if mm else 0
    if ampm:
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if ampm.lower() == "p" else 0)
    elif mm is None:
        return None  # « 15 » seul : ni am/pm ni minutes, ambigu
    if hour > 23 or minute > 59:
        return None
    now = now or datetime.now()
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if day:
        target += timedelta(days=(_WEEKDAYS.index(day.lower()) - now.weekday()) % 7)
        if target <= now:
            target += timedelta(days=7)
    elif target <= now:
        target += timedelta(days=1)
    return target.isoformat(timespec="seconds")


# --- Appel -------------------------------------------------------------------

def run_claude(prompt: str, cwd: Path, *, allowed_tools, max_budget_usd: float,
               expect_agent: str | None = None, agents_prefix: str | None = None,
               timeout: float = IMPROVE_CALL_TIMEOUT, cancel: threading.Event | None = None,
               max_turns: int = IMPROVE_RELAY_MAX_TURNS, log_path: Path | None = None,
               cmd: str | None = None,
               on_spawn: Callable[[subprocess.Popen], None] | None = None) -> CallResult:
    """Lance `claude -p` dans `cwd`, prompt sur stdin, et lit le flux.

    `expect_agent` : nom généré `<p>-<agent>` dont on veut la sortie
    (absente -> `delegation_missing`). `agents_prefix` : préfixe `<p>`
    exigé dans `system/init` (sinon `agents_missing`, appel interrompu).
    `log_path` : copie brute du flux (une ligne JSON par événement), vidée
    ligne à ligne (suivi en direct possible). `on_spawn` : rappel appelé avec
    le `Popen` juste après sa création, avant la lecture du flux ; une
    exception y est journalisée et n'interrompt pas l'appel."""
    t0 = time.monotonic()
    try:
        argv = claude_command(cmd) + build_args(allowed_tools, max_budget_usd=max_budget_usd,
                                                max_turns=max_turns)
    except (ClaudeNotFound, ValueError) as e:
        return CallResult(status="spawn_error", error=str(e))
    env = dict(os.environ)
    # Lancé depuis une session Claude Code : l'appel headless reste autonome.
    env.pop("CLAUDECODE", None)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = (getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                                   | getattr(subprocess, "CREATE_NO_WINDOW", 0))
    else:
        kwargs["start_new_session"] = True
    state = _StreamState(expect_agent, agents_prefix)
    r = state.r
    err_file = tempfile.TemporaryFile()
    log_fh = None
    if log_path is not None:
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_fh = open(log_path, "w", encoding="utf-8")
        except OSError as e:
            log.warning("journal brut %s : %s", log_path, e)
    try:
        try:
            proc = subprocess.Popen(argv, cwd=str(cwd), env=env, stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, stderr=err_file, **kwargs)
        except OSError as e:
            r.status, r.error = "spawn_error", f"lancement de claude impossible : {e}"
            return r
        if on_spawn is not None:
            try:
                on_spawn(proc)
            except Exception as e:  # noqa: BLE001 - le suivi ne casse jamais l'appel
                log.warning("rappel on_spawn : %s", e)

        def _feed_stdin():
            try:
                proc.stdin.write(prompt.encode("utf-8"))
            except OSError:
                pass
            finally:
                try:
                    proc.stdin.close()
                except OSError:
                    pass

        lines: queue.Queue = queue.Queue()

        def _read_stdout():
            try:
                for raw in iter(proc.stdout.readline, b""):
                    lines.put(raw)
            except (OSError, ValueError):
                pass  # flux fermé après un kill
            finally:
                lines.put(None)

        threading.Thread(target=_feed_stdin, daemon=True).start()
        reader = threading.Thread(target=_read_stdout, daemon=True)
        reader.start()
        deadline = t0 + timeout
        outcome = None
        while True:
            if cancel is not None and cancel.is_set():
                outcome = "cancelled"
                break
            if time.monotonic() > deadline:
                outcome = "timeout"
                break
            try:
                raw = lines.get(timeout=_POLL)
            except queue.Empty:
                continue
            if raw is None:
                break
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            if log_fh:
                try:
                    log_fh.write(line + "\n")
                    log_fh.flush()  # suivi en direct pendant l'appel
                except (OSError, ValueError) as e:
                    log.warning("journal brut %s : %s", log_path, e)
                    log_fh.close()
                    log_fh = None
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if isinstance(ev, dict):
                state.feed(ev)
            if state.agents_problem:
                outcome = "agents_missing"
                break
        if outcome:
            kill_tree(proc)
        else:
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                kill_tree(proc)
        r.exit_code = proc.returncode
        if reader.is_alive():
            reader.join(timeout=5)
        try:
            proc.stdout.close()
        except OSError:
            pass
    finally:
        if log_fh:
            log_fh.close()
        try:
            err_file.seek(0)
            r.stderr_tail = err_file.read()[-4000:].decode("utf-8", errors="replace")
        except OSError:
            pass
        err_file.close()
    if not r.duration_ms:
        r.duration_ms = int((time.monotonic() - t0) * 1000)
    return _finalize(state, outcome)


def _finalize(state: _StreamState, outcome: str | None) -> CallResult:
    r = state.r
    state.resolve_background()
    quota, reset = detect_quota(r.text, *state.texts[-3:], r.stderr_tail)
    if outcome == "cancelled":
        r.status, r.error = "cancelled", "appel annulé"
    elif outcome == "timeout":
        r.status, r.error = "timeout", "délai dépassé : arbre de processus tué"
    elif outcome == "agents_missing":
        r.status, r.error = "agents_missing", state.agents_problem
    elif quota and (not state.result_seen or r.is_error or r.subtype != "success"):
        r.status, r.quota_reset = "quota", parse_reset(reset)
        r.error = "limite d'utilisation de l'abonnement atteinte" + (
            f" (réinitialisation : {reset})" if reset else "")
    elif r.rate_limit_retries and not state.result_seen:
        r.status, r.error = "quota", "limite de débit (api_retry rate_limit) sans résultat"
    elif not state.result_seen:
        r.status = "error"
        r.error = (f"flux sans événement result (code de sortie {r.exit_code})"
                   + (f" : {r.stderr_tail.strip()[-300:]}" if r.stderr_tail.strip() else ""))
    elif r.is_error or r.subtype != "success":
        r.status, r.error = "error", f"appel en échec : {r.subtype or 'is_error'}"
    elif state.bg_status == "error":
        r.status, r.error = "error", state.bg_error
    elif state.bg_status == "missing":
        r.status, r.error = "delegation_missing", state.bg_error
    elif state.expect_agent and r.agent_output is None:
        r.status = "delegation_missing"
        r.error = (f"aucune sortie de l'agent {state.expect_agent} (délégations vues : "
                   f"{', '.join(r.delegated_to) or 'aucune'})")
    else:
        r.status = "ok"
    return r
