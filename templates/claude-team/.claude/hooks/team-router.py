#!/usr/bin/env python3
"""UserPromptSubmit hook : routage déterministe vers l'équipe claude-team.

Classe le prompt de l'utilisateur (question / conception / implementation /
relecture / inconnu) par expressions régulières (français d'abord, quelques
formes anglaises) et injecte UNE ligne de contexte qui rappelle au fil
principal vers quel agent router et la gate de relecture, selon
`routing.mode` de `.claude/team.json` :

  - `auto`    : « routage auto : <type> -> <prefix>-<agent> ... »
  - `assiste` : même ligne, préfixée « suggestion : »
  - `manuel`  : rien (exit 0 silencieux), comme une section `routing` absente.

Un prompt qui commence par `/` (slash command) ne reçoit rien non plus.

Format de sortie (doc Claude Code, https://code.claude.com/docs/en/hooks,
§ UserPromptSubmit) : à exit 0, Claude Code accepte deux canaux, le texte
brut sur stdout ou le JSON
`{"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
"additionalContext": "..."}}` ; les deux sont injectés comme contexte que
Claude lit, sans entrée visible dans le transcript. Ce hook utilise la
forme JSON (explicite, jamais confondue avec un autre objet JSON de
sortie). L'événement n'a pas de `matcher` ; `timeout` est en secondes.

Best-effort / fail-open : fichier manquant, JSON illisible, stdin vide ->
exit 0 sans sortie (un hook cassé ne doit jamais gêner la session). Python
stdlib, portable Windows/Unix ; stdin, stdout et stderr en UTF-8 explicite
(sous Windows, cp1252 ferait mojibake ou UnicodeEncodeError).
"""
from __future__ import annotations

import json
import os
import re
import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# Modes connus : toute autre valeur est traitée comme `manuel` (silence).
ACTIVE_MODES = ("auto", "assiste")
GATE_LABELS = {
    "always": "tout code livré",
    "from_3_files": "dès 3 fichiers touchés",
}

# Classification : parmi relecture / conception / implementation, c'est le
# verbe qui apparaît EN PREMIER dans le prompt qui décide (« implémente la
# route puis vérifie que les tests passent » = implementation, « relis ce
# diff puis corrige » = relecture) ; question ensuite (« comment on ferait »
# gagne sur « comment », « corrige ... pourquoi ? » sur le « ? » final).
# Les jetons `/...` (slash commands, chemins) sont retirés avant : `/check-all`
# n'est pas une demande de relecture. « vérifie » / « valide » ne comptent
# que suivis d'un objet (ce diff, le code...) : « vérifie que les tests
# passent » ou « je valide, go » ne sont pas des relectures.
_W = r"(?<![\w'])"  # début de mot (l'apostrophe compte comme séparateur)
_OBJ = r"\s+(ce|cet|cette|le|la|les|l'|mon|ma|mes|ton|ta|tes|un|une|diff|code|fichier|the|this|my|a)\b"
CLASSES = (
    ("relecture", re.compile(
        _W + r"(relis|relecture|review|revois|check|(v[ée]rifie|valide|validate|verify)" + _OBJ + r")\b",
        re.IGNORECASE)),
    ("conception", re.compile(
        r"(comment on ferait|comment faire pour|comment tu ferais|how would (we|you)|how should)"
        r"|" + _W + r"(plan|con[çc]ois|conception|architecture|option|options|propose|design|strat[ée]gie)\b",
        re.IGNORECASE)),
    ("implementation", re.compile(
        _W + r"(impl[ée]mente|ajoute|corrige|cr[ée]e|modifie|[ée]cris|refactor\w*|supprime|retire"
        r"|implement|add|create|write|fix|remove|rename|renomme|mets?\s+[àa]\s+jour|update)\b",
        re.IGNORECASE)),
)
_QUESTION_RE = re.compile(
    _W + r"(o[ùu] est|o[ùu] sont|o[ùu]|pourquoi|comment [çc]a|comment\b|quels?|quelles?|liste|explique"
    r"|c'est quoi|qu'est-ce|est-ce que|what|where|why|how does|how do|which|list|explain)\b",
    re.IGNORECASE)
_FINAL_QUESTION_RE = re.compile(r"\?\s*$")
_SLASH_TOKEN_RE = re.compile(r"(?<!\S)/\S+")
# Un prompt qui S'OUVRE par un mot interrogatif est une question, même s'il
# contient ensuite un participe qui ressemble à un verbe d'action (« où est
# implémenté X ? », « pourquoi ce fichier est-il supprimé ? »). Les tournures
# de conception (« comment on ferait ») sont testées avant, car elles
# commencent aussi par un interrogatif.
_OPENER_RE = re.compile(
    r"^(o[ùu]|pourquoi|comment|est-ce que|qu'est-ce|c'est quoi"
    r"|what|where|why|how)\b", re.IGNORECASE)
_CONCEPTION_PHRASE_RE = re.compile(
    r"(comment on ferait|comment faire pour|comment tu ferais|how would (we|you)|how should)",
    re.IGNORECASE)


def _read_json(path: str):
    """JSON du fichier, ou None s'il est absent / illisible."""
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _project_root() -> str:
    root = (os.environ.get("CLAUDE_PROJECT_DIR") or "").strip() or os.getcwd()
    return os.path.abspath(root)


def classify(prompt: str) -> str:
    """Type de demande : relecture / conception / implementation / question / inconnu."""
    text = " ".join(_SLASH_TOKEN_RE.sub(" ", prompt).split())
    if not text:
        return "inconnu"
    if _CONCEPTION_PHRASE_RE.search(text):
        return "conception"
    if _OPENER_RE.search(text):
        return "question"
    first: tuple[int, str] | None = None
    for name, rx in CLASSES:
        m = rx.search(text)
        if m and (first is None or m.start() < first[0]):
            first = (m.start(), name)
    if first is not None:
        return first[1]
    if _QUESTION_RE.search(text) or _FINAL_QUESTION_RE.search(text):
        return "question"
    return "inconnu"


def _agent_enabled(team: dict, agent_id: str) -> bool:
    """Vrai si l'agent existe dans le manifeste et n'est pas `auto: false`."""
    for a in team.get("agents") or []:
        if isinstance(a, dict) and a.get("id") == agent_id:
            return a.get("auto") is not False
    return False


def routing_line(team: dict, kind: str, prefix: str) -> str | None:
    """Ligne de contexte (au plus 2 lignes) pour le type de demande, ou None
    si le mode ne demande rien."""
    routing = team.get("routing")
    if not isinstance(routing, dict):
        return None
    mode = str(routing.get("mode") or "manuel")
    if mode not in ACTIVE_MODES:
        return None
    gate = str(routing.get("review_gate") or "always")
    gate_txt = GATE_LABELS.get(gate)
    reviewer = _agent_enabled(team, "reviewer")
    gate_part = (f"code livré -> relecture {prefix}-reviewer obligatoire ({gate_txt}) avant de présenter"
                 if gate_txt and reviewer else "")

    if kind == "question" and _agent_enabled(team, "researcher"):
        head = f"question -> {prefix}-researcher en silence (réponse avec sources fichier:ligne)"
    elif kind == "conception" and _agent_enabled(team, "architect"):
        head = f"conception -> {prefix}-architect (plan en étapes vérifiables, compromis)"
    elif kind == "implementation":
        exe = f"{prefix}-executor" if _agent_enabled(team, "executor") else "*-expert"
        head = f"implémentation -> {exe} (tâche S) ou *-expert (feature M+)"
    elif kind == "relecture" and reviewer:
        head = f"relecture -> {prefix}-reviewer (objectif + critères + diff, jamais le raisonnement)"
    else:
        head = "demande non classée : répondre seul si une lecture suffit, /team si multi-étapes"
    parts = [head]
    if gate_part and kind != "relecture":
        parts.append(gate_part)
    parts.append("pied de réponse « équipe : ... »")
    label = "suggestion : " if mode == "assiste" else "routage auto : "
    return "[équipe claude-team] " + label + " ; ".join(parts)


def main() -> int:
    raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    if not raw.strip():
        return 0
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return 0
    if not isinstance(data, dict):
        return 0
    prompt = data.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return 0
    if prompt.lstrip().startswith("/"):
        return 0  # slash command : la commande porte déjà son protocole

    root = _project_root()
    team = _read_json(os.path.join(root, ".claude", "team.json"))
    if not isinstance(team, dict):
        return 0
    team_section = team.get("team") if isinstance(team.get("team"), dict) else {}
    prefix = str(team_section.get("prefix") or "").strip() or os.path.basename(root.rstrip("\\/")) or "ws"

    line = routing_line(team, classify(prompt), prefix)
    if not line:
        return 0
    sys.stdout.write(json.dumps({
        "hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": line},
    }, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
