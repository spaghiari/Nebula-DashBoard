"""Faux binaire `claude` pour les tests : rejoue un flux stream-json scripté.

Lancé par `dashcore.claude_runner` via `NEBULA_CLAUDE_CMD=<ce fichier>`
(ou l'argument `cmd`). Lit le prompt sur STDIN, choisit la première règle
du script JSON (`FAKE_CLAUDE_SCRIPT`) qui correspond, et écrit les
événements sur stdout, une ligne JSON par événement (UTF-8). Chaque appel
est consigné (argv, stdin, cwd) dans le fichier `log` du script : les tests
vérifient ainsi la ligne de commande et ce que reçoit chaque appel.

Règle (toutes les clés optionnelles) :
  match        motif re.search (DOTALL) sur le stdin
  if_file      {"path", "contains"} : fichier (relatif au cwd) qui doit contenir le texte
  unless_file  {"path", "contains"} : idem, condition inverse
  agent        subagent_type délégué (défaut : lu dans le stdin, « subagent_type: x »)
  output       sortie de l'agent (tool_result du tool_use Agent)
  handback     préfixe « [Subagent hand-back] » (défaut : vrai)
  no_delegation  aucun tool_use Agent
  write_files  {chemin relatif: contenu} écrits par le « sous-agent »
  tool_errors  nombre de tool_result en erreur (outil retiré)
  denials      nombre d'entrées dans result.permission_denials
  background   sous-agent lancé en arrière-plan (launch « Async agent launched »,
               puis selon le mode) : "children" (messages enfants directs + notification),
               "notif_only" (notification seule, `summary`), "never" (aucune réponse),
               "failed" (notification status=failed), "nested" (enfants directs + un
               agent imbriqué dont les messages ne doivent pas être pris)
  summary      `summary` de la notification (défaut : output)
  result_costs liste de total_cost_usd : un événement result par valeur (un par tour)
  sleep        secondes d'attente avant le résultat (tests de délai)
  result       champs du `result` final à surcharger (subtype, is_error, ...)
  no_result    aucun événement result
  final_text   texte du `result` (défaut : FIN)
  api_retry    nombre d'événements system/api_retry rate_limit
  agents       liste des agents de system/init (défaut : .claude/agents/*.md du cwd)
  exit         code de sortie (défaut 0)
  stderr       texte écrit sur stderr

Stdlib only ; aucune dépendance au paquet dashcore.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path


def _emit(ev: dict) -> None:
    sys.stdout.write(json.dumps(ev, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _file_has(spec: dict) -> bool:
    try:
        return spec.get("contains", "") in Path(spec["path"]).read_text(encoding="utf-8")
    except OSError:
        return False


def _pick(rules: list, stdin: str) -> dict | None:
    for rule in rules:
        if rule.get("match") and not re.search(rule["match"], stdin, re.S):
            continue
        if rule.get("if_file") and not _file_has(rule["if_file"]):
            continue
        if rule.get("unless_file") and _file_has(rule["unless_file"]):
            continue
        return rule
    return None


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    stdin = sys.stdin.buffer.read().decode("utf-8")
    script_path = os.environ.get("FAKE_CLAUDE_SCRIPT")
    script = json.loads(Path(script_path).read_text(encoding="utf-8")) if script_path else {}
    if script.get("log"):
        with open(script["log"], "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"argv": sys.argv[1:], "stdin": stdin, "cwd": os.getcwd()},
                                ensure_ascii=False) + "\n")
    rule = _pick(script.get("rules") or [], stdin) or {
        "no_delegation": True, "final_text": "aucune règle", "result": {"is_error": True,
                                                                        "subtype": "error_during_execution"}}
    if rule.get("stderr"):
        sys.stderr.write(rule["stderr"])
        sys.stderr.flush()
    agents = rule.get("agents")
    if agents is None:
        agents = sorted(p.stem for p in Path(".claude/agents").glob("*.md"))
    init = {"type": "system", "subtype": "init", "session_id": "fake-session",
            "model": "claude-sonnet-5-5", "tools": ["Agent", "Read"]}
    if agents != "absent":
        init["agents"] = agents
    _emit(init)
    for _ in range(int(rule.get("api_retry") or 0)):
        _emit({"type": "system", "subtype": "api_retry", "attempt": 1, "error": "rate_limit"})
    if not rule.get("no_delegation"):
        m = re.search(r"subagent_type\s*[:=]\s*\"?([A-Za-z0-9_-]+)", stdin)
        agent = rule.get("agent") or (m.group(1) if m else "inconnu")
        _emit({"type": "assistant", "parent_tool_use_id": None, "message": {"content": [
            {"type": "tool_use", "id": "toolu_agent", "name": "Agent",
             "input": {"subagent_type": agent, "prompt": "..."}}]}})
        for i, (rel, content) in enumerate((rule.get("write_files") or {}).items()):
            target = Path(rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            _emit({"type": "assistant", "parent_tool_use_id": "toolu_agent", "message": {
                "content": [{"type": "tool_use", "id": f"toolu_w{i}", "name": "Write",
                             "input": {"file_path": rel}}]}})
            _emit({"type": "user", "parent_tool_use_id": "toolu_agent", "message": {
                "content": [{"type": "tool_result", "tool_use_id": f"toolu_w{i}",
                             "content": "File created successfully"}]}})
        for i in range(int(rule.get("tool_errors") or 0)):
            _emit({"type": "user", "parent_tool_use_id": "toolu_agent", "message": {
                "content": [{"type": "tool_result", "tool_use_id": f"toolu_e{i}", "is_error": True,
                             "content": "<tool_use_error>Error: No such tool available: Bash"
                                        "</tool_use_error>"}]}})
        out = rule.get("output", "")
        bg = rule.get("background")
        if bg:
            _emit({"type": "system", "subtype": "task_started", "task_id": "a1",
                   "tool_use_id": "toolu_agent", "is_backgrounded": True})
            _emit({"type": "user", "parent_tool_use_id": None, "message": {"content": [
                {"type": "tool_result", "tool_use_id": "toolu_agent", "content": [
                    {"type": "text", "text": "Async agent launched successfully.\nagentId: a1"}]}]}})
            if bg in ("children", "nested"):
                _emit({"type": "assistant", "parent_tool_use_id": "toolu_agent", "message": {
                    "content": [{"type": "text", "text": "intermédiaire"}]}})
                _emit({"type": "assistant", "parent_tool_use_id": "toolu_agent", "message": {
                    "content": [{"type": "text", "text": out}]}})
                _emit({"type": "assistant", "parent_tool_use_id": "toolu_agent", "message": {
                    "content": [{"type": "tool_use", "id": "toolu_t", "name": "Read",
                                 "input": {}}]}})
            if bg == "nested":
                _emit({"type": "assistant", "parent_tool_use_id": "toolu_agent", "message": {
                    "content": [{"type": "tool_use", "id": "toolu_inner", "name": "Agent",
                                 "input": {"subagent_type": "p-evaluator"}}]}})
                _emit({"type": "assistant", "parent_tool_use_id": "toolu_inner", "message": {
                    "content": [{"type": "text", "text": "NE PAS PRENDRE (imbriqué)"}]}})
                _emit({"type": "user", "parent_tool_use_id": "toolu_agent", "message": {
                    "content": [{"type": "tool_result", "tool_use_id": "toolu_inner",
                                 "content": "NE PAS PRENDRE (résultat imbriqué)"}]}})
            if bg != "never":
                _emit({"type": "system", "subtype": "task_notification",
                       "task_id": "a1", "tool_use_id": "toolu_agent",
                       "status": "failed" if bg == "failed" else "completed",
                       "summary": rule.get("summary", out), "output_file": "x", "usage": "{}"})
            out = None
        text = ("[Subagent hand-back] " + (out or "")) if rule.get("handback", True) else out
        if out is not None:
            _emit({"type": "user", "parent_tool_use_id": None, "message": {"content": [
                {"type": "tool_result", "tool_use_id": "toolu_agent",
                 "content": [{"type": "text", "text": text},
                             {"type": "text", "text": "agentId: a123 (for resuming)"}]}]}})
    if rule.get("sleep"):
        time.sleep(float(rule["sleep"]))
    final = rule.get("final_text", "FIN")
    _emit({"type": "assistant", "parent_tool_use_id": None,
           "message": {"content": [{"type": "text", "text": final}]}})
    if not rule.get("no_result"):
        res = {"type": "result", "subtype": "success", "is_error": False, "result": final,
               "total_cost_usd": 0.12, "num_turns": 2, "duration_ms": 1500,
               "session_id": "fake-session",
               "permission_denials": [{"tool_name": "Write", "tool_use_id": f"d{i}",
                                       "tool_input": {}} for i in range(int(rule.get("denials") or 0))],
               "modelUsage": {"claude-sonnet-5-5": {
                   "costUSD": 0.12, "inputTokens": 10, "outputTokens": 20,
                   "cacheReadInputTokens": 300, "cacheCreationInputTokens": 40}}}
        res.update(rule.get("result") or {})
        for cost in rule.get("result_costs") or [None]:
            if cost is not None:
                res["total_cost_usd"] = cost
            _emit(res)
    return int(rule.get("exit") or 0)


if __name__ == "__main__":
    sys.exit(main())
