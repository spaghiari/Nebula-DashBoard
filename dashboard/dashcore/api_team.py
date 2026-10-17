"""Module claude-team : agents générés depuis un manifeste + état de la boucle
d'amélioration mesurée.

Un workspace équipé de l'overlay `claude-team` porte :

    .claude/team.json                 manifeste (source de vérité, `team.prefix`)
    .claude/team/agents/<id>.md       corps des agents (sans frontmatter)
    .claude/agents/<prefix>-<id>.md   agents GÉNÉRÉS ici (frontmatter Claude Code)
    .claude/evals/*.jsonl             jeu d'évals (verrouillé par evals-lock.py)
    .claude/journal/changes.jsonl     journal des itérations (/improve)

Ce module :
  - `generate_agents` : générateur `team_agents` appelé par apply_overlay
    après la copie (mapping capacités -> outils, modèle par rôle, bloc de
    contraintes). Idempotent : un agent présent n'est pas écrasé, sauf
    option `regenerate` ET marqueur TEAM_GENERATED_MARKER en tête de corps.
    Le préfixe des agents générés (`team.prefix`, défaut = id du
    workspace) est persisté dans la copie workspace du manifeste.
  - `team_config_hash` : empreinte de la configuration mesurée par /eval
    (manifeste + corps + agents générés). Le même calcul est fait par le
    one-liner de `.claude/commands/eval.md` (CONFIG_HASH_ONELINER).
  - `team_state` / `improvement_state` : données des routes
    GET /api/workspaces/<id>/team et /improvement.

Stdlib only ; toute écriture sous _MUTATION_LOCK (réentrant).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from dashcore.config import (
    CAPABILITY_TOOLS, CAPABILITY_WRITE_TOOLS, REGISTER_STATUSES,
    TEAM_EFFORT_LEVELS, TEAM_GENERATED_MARKER, TEAM_MODEL_ALIASES,
    TEAM_ROLE_DEFAULTS, TEAM_SESSION_DEFAULT_EFFORT, _MUTATION_LOCK, log,
)
from dashcore.helpers import (
    CorruptJsonError, read_json, read_json_strict, render_placeholders,
    resolve_ws_dir, safe_id, write_json,
)

MANIFEST_REL = Path(".claude") / "team.json"
AGENTS_DIR_REL = Path(".claude") / "agents"
# Longueur du hash court de configuration (sha1 hex tronqué).
CONFIG_HASH_LEN = 12
# One-liner stdlib équivalent à `team_config_hash` (même algorithme, même
# ordre, même encodage), tel qu'il figure dans `.claude/commands/eval.md`
# de l'overlay ; `{{name}}` y est substitué par l'id du workspace à la copie.
# À exécuter depuis la racine du workspace. test_team.py vérifie l'égalité.
CONFIG_HASH_ONELINER = (
    "python -c \"import hashlib,json,pathlib;c=pathlib.Path('.claude');"
    "p=((json.loads(c.joinpath('team.json').read_text(encoding='utf-8-sig')).get('team') or {})"
    ".get('prefix') or '{{name}}');"
    "f=sorted([c/'team.json',*c.glob('team/agents/*.md'),*c.glob('agents/'+p+'-*.md')],"
    "key=lambda x:x.relative_to(c.parent).as_posix());h=hashlib.sha1();"
    "[h.update(x.relative_to(c.parent).as_posix().encode('utf-8')+bytes(1)+x.read_bytes()+bytes(1)) for x in f];"
    "print(h.hexdigest()[:12])\""
)
# Fichiers des registres self-improving comptés par statut.
REGISTER_FILES = ("ideas.md", "backlog.md", "improvements.md")
_STATUS_RE = re.compile(r"\*\*\[(" + "|".join(REGISTER_STATUSES) + r")[^\]]*\]")
# Frontmatter YAML en tête d'un agent généré (`---\n...\n---\n`).
_FRONTMATTER_RE = re.compile(r"\A---\r?\n.*?\r?\n---\r?\n", re.S)


# --- Manifeste ----------------------------------------------------------------

def load_manifest(ws_dir: Path) -> dict | None:
    """Manifeste `.claude/team.json` du workspace, ou None s'il est absent
    ou illisible (lecture seule : `read_json` tolérant suffit)."""
    data = read_json(ws_dir / MANIFEST_REL, None)
    if not isinstance(data, dict) or not isinstance(data.get("agents"), list):
        return None
    return data


def manifest_agents(manifest: dict) -> list[dict]:
    """Agents du manifeste avec un id sûr (les autres sont ignorés)."""
    out = []
    for a in manifest.get("agents") or []:
        if isinstance(a, dict) and safe_id(str(a.get("id") or "")):
            out.append(a)
    return out


def manifest_prefix(manifest: dict | None) -> str | None:
    """`team.prefix` du manifeste s'il est un id sûr, sinon None."""
    team = (manifest or {}).get("team")
    p = team.get("prefix") if isinstance(team, dict) else None
    return p if isinstance(p, str) and safe_id(p) else None


def effective_prefix(manifest: dict | None, vars: dict, requested: str | None = None) -> str:
    """Préfixe des agents générés : payload d'activation, puis `team.prefix`
    persisté dans le manifeste, puis id du workspace (`vars['name']`)."""
    if requested and safe_id(requested):
        return requested
    return manifest_prefix(manifest) or str(vars.get("name") or "ws")


def _persist_prefix(ws_dir: Path, prefix: str) -> bool:
    """Écrit `team.prefix` dans la copie workspace du manifeste si la valeur
    change (idempotent). Lecture stricte : un manifeste corrompu n'est jamais
    écrasé (CorruptJsonError remontée à l'appelant). Retourne True si écrit."""
    path = ws_dir / MANIFEST_REL
    with _MUTATION_LOCK:
        data = read_json_strict(path, None)
        if not isinstance(data, dict):
            return False
        team = data.get("team")
        if not isinstance(team, dict):
            team = {}
            data["team"] = team
        if team.get("prefix") == prefix:
            return False
        team["prefix"] = prefix
        write_json(path, data)
        return True


class PendingIterationError(Exception):
    """Changement de modèle refusé : une itération /improve attend son
    verdict (le candidat serait mesuré sur une autre configuration)."""

    def __init__(self, pending: dict):
        self.pending = pending
        super().__init__(pending_message(pending, "les modèles"))


def pending_message(pending: dict, what: str) -> str:
    """Message affiché quand une itération en attente bloque un changement."""
    return (f"itération /improve {pending.get('iteration')} en attente de verdict : la "
            f"trancher (nouvelle session puis /improve) avant de changer {what} ; rien "
            "n'a été modifié")


def pending_iteration(ws_dir: Path, manifest: dict | None) -> dict | None:
    """Itération /improve encore `pending` (dernière ligne de chaque itération
    du journal, même règle que improvement_state), ou None. Lecture seule."""
    loop = (manifest or {}).get("improvement_loop") or {}
    jp = _claude_path(ws_dir, str(loop.get("journal") or "journal/changes.jsonl"))
    entries, _ = _parse_journal(jp) if jp else ([], 0)
    last: dict = {}
    for i, e in enumerate(entries, 1):
        it = e.get("iteration") if isinstance(e.get("iteration"), int) else i
        last[it] = _norm_status(e.get("status"))
    pend = [it for it, s in last.items() if s == "pending"]
    return {"iteration": pend[-1]} if pend else None


def _declared_model(agent: dict) -> str | None:
    """`model` déclaré explicitement par l'agent dans le manifeste (alias
    valide), ou None (le modèle vient alors du défaut)."""
    v = agent.get("model")
    return v if isinstance(v, str) and v in TEAM_MODEL_ALIASES else None


_FM_MODEL_RE = re.compile(r"^model:[ \t]*(\S+)[ \t]*\r?$", re.M)


def agent_file_models(ws_dir: Path, manifest: dict | None, prefix: str | None) -> dict[str, str]:
    """Modèles choisis avant la 2.5.0 et restés seulement dans les agents
    générés : jusqu'en 2.4.1, les modèles de la modale d'activation
    n'étaient écrits que dans le frontmatter `model:` de
    `.claude/agents/<prefix>-<id>.md`, jamais dans `team.json`.

    Retourne {agent_id: alias} pour chaque agent SANS modèle déclaré dans le
    manifeste dont le fichier généré (porteur du marqueur) déclare un alias
    valide différent du modèle effectif du manifeste. Ce modèle est le choix
    de l'utilisateur : il est affiché, puis persisté avant toute
    régénération (cf. _persist_models, set_agents_config). Lecture seule ;
    {} sans écart (rendu identique à la 2.4.1)."""
    out: dict[str, str] = {}
    if not isinstance(manifest, dict) or not prefix:
        return out
    for a in manifest_agents(manifest):
        if _declared_model(a) is not None:
            continue
        target = ws_dir / AGENTS_DIR_REL / f"{prefix}-{a['id']}.md"
        try:
            content = target.read_text(encoding="utf-8")
        except OSError:
            continue
        if not _is_generated(content):
            continue
        fm = _FRONTMATTER_RE.match(content)
        m = _FM_MODEL_RE.search(fm.group(0)) if fm else None
        if not m:
            continue
        model = m.group(1)
        if model in TEAM_MODEL_ALIASES and model != _effective_model(a, manifest, None):
            out[a["id"]] = model
    return out


def _with_file_models(manifest: dict, file_models: dict[str, str]) -> dict:
    """Copie du manifeste où les modèles des agents générés (cf.
    agent_file_models) sont déclarés : vue pour l'affichage et le rendu,
    jamais écrite telle quelle. Le manifeste lui-même si aucun écart."""
    if not file_models:
        return manifest
    view = json.loads(json.dumps(manifest))
    for a in view.get("agents") or []:
        if isinstance(a, dict) and a.get("id") in file_models:
            a["model"] = file_models[a["id"]]
    return view


def _model_changes(data: dict, models: dict, default_model: str | None) -> list[tuple[dict, str]]:
    """Changements de modèle RÉELS demandés à l'activation : `models[id]`
    (choix explicite par agent), sinon `default_model` pour un agent SANS
    modèle déclaré seulement (un modèle déclaré n'est jamais écrasé par le
    défaut). Une valeur égale au modèle effectif actuel n'est pas un
    changement (pas de champ implicite rendu explicite)."""
    out: list[tuple[dict, str]] = []
    for a in data.get("agents") or []:
        if not isinstance(a, dict) or not safe_id(str(a.get("id") or "")):
            continue
        if a["id"] in models:
            want = models[a["id"]]
        elif default_model and _declared_model(a) is None:
            want = default_model
        else:
            continue
        if want != _effective_model(a, data, None):
            out.append((a, want))
    return out


def models_change_pending(ws_dir: Path, models: dict, default_model: str | None,
                          vars: dict | None = None) -> dict | None:
    """Itération en attente qui bloquerait les changements de modèle
    demandés (None : rien ne change, ou aucune itération en attente).
    Un modèle resté dans l'agent généré (cf. agent_file_models) compte
    comme modèle actuel : la modale qui le renvoie ne change rien.
    Lecture non stricte : un manifeste corrompu est traité plus loin (409)."""
    data = read_json(ws_dir / MANIFEST_REL, None)
    if not isinstance(data, dict) or not isinstance(data.get("agents"), list):
        return None
    prefix = effective_prefix(data, vars or {"name": ws_dir.name})
    view = _with_file_models(data, agent_file_models(ws_dir, data, prefix))
    if not _model_changes(view, models or {}, default_model):
        return None
    return pending_iteration(ws_dir, data)


def _persist_models(ws_dir: Path, models: dict, default_model: str | None,
                    prefix: str | None = None) -> bool:
    """Écrit les modèles choisis à l'activation dans `agents[i].model` de la
    copie workspace du manifeste (cf. _model_changes). Seuls `model` des
    agents changent (jamais `improvement_loop`). Lecture stricte ; écrit
    seulement si une valeur change réellement ; itération /improve en
    attente + changement réel -> PendingIterationError (rien écrit).

    `prefix` (préfixe des agents déjà générés) : les modèles restés
    seulement dans les agents générés (cf. agent_file_models) sont d'abord
    déclarés dans le manifeste, pour que la régénération les conserve. Sous
    itération en attente, cette reprise n'est pas écrite (elle changerait
    l'empreinte) : le rendu l'applique sans l'écrire (cf. generate_agents).
    Retourne True si écrit."""
    path = ws_dir / MANIFEST_REL
    with _MUTATION_LOCK:
        data = read_json_strict(path, None)
        if not isinstance(data, dict) or not isinstance(data.get("agents"), list):
            return False
        file_models = agent_file_models(ws_dir, data, prefix)
        view = _with_file_models(data, file_models)
        changes = _model_changes(view, models or {}, default_model)
        if not changes and not file_models:
            return False
        pend = pending_iteration(ws_dir, data)
        if pend:
            if changes:
                raise PendingIterationError(pend)
            return False
        by_id = {a.get("id"): a for a in data["agents"] if isinstance(a, dict)}
        for aid, model in file_models.items():
            by_id[aid]["model"] = model
        for a, want in changes:
            by_id[a["id"]]["model"] = want
        write_json(path, data)
        return True


# --- Routage always-on ------------------------------------------------------------

ROUTING_MODES = ("manuel", "assiste", "auto")
REVIEW_GATES = ("always", "from_3_files", "never")
# Section `routing` écrite par défaut dans un manifeste qui n'en a pas
# (workspace activé avant le routage) au premier `set_routing`.
ROUTING_DEFAULT = {
    "mode": "auto",
    "modes": list(ROUTING_MODES),
    "review_gate": "always",
    "review_gate_values": list(REVIEW_GATES),
    "budget": "sonnet-first",
}


def _str_list(raw, default: tuple) -> list[str]:
    vals = [v for v in (raw if isinstance(raw, list) else []) if isinstance(v, str) and v]
    return vals or list(default)


def routing_state(manifest: dict | None) -> dict:
    """Routage effectif du manifeste : `declared` (section présente), `mode`,
    `modes`, `review_gate`, `review_gate_values`, `budget`.

    Rétro-compatibilité : sans section `routing`, le mode effectif est
    `manuel` (le hook et le fragment ne font rien), `declared` est faux
    pour que l'UI propose d'activer le routage. Une valeur hors liste
    retombe sur `manuel` / `always`."""
    raw = (manifest or {}).get("routing")
    declared = isinstance(raw, dict)
    raw = raw if declared else {}
    modes = _str_list(raw.get("modes"), ROUTING_MODES)
    gates = _str_list(raw.get("review_gate_values"), REVIEW_GATES)
    mode = raw.get("mode") if declared else "manuel"
    if mode not in modes:
        mode = "manuel"
    gate = raw.get("review_gate") if declared else ROUTING_DEFAULT["review_gate"]
    if gate not in gates:
        gate = ROUTING_DEFAULT["review_gate"]
    budget = raw.get("budget")
    return {
        "declared": declared, "mode": mode, "modes": modes,
        "review_gate": gate, "review_gate_values": gates,
        "budget": budget if isinstance(budget, str) and budget else ROUTING_DEFAULT["budget"],
    }


def set_routing(ws_dir: Path, mode: str | None = None,
                review_gate: str | None = None) -> tuple[int, dict]:
    """Écrit `routing.mode` / `routing.review_gate` dans `.claude/team.json`.

    Validation contre `routing.modes` / `routing.review_gate_values` du
    manifeste (400 sinon) ; lecture stricte (manifeste corrompu -> 409,
    jamais écrasé) ; section `routing` absente -> section par défaut
    complète écrite d'abord ; écriture seulement si quelque chose change.
    Aucune régénération des agents : le hook et le fragment relisent
    `team.json`. Retourne (status, routing_state à jour)."""
    path = ws_dir / MANIFEST_REL
    with _MUTATION_LOCK:
        try:
            data = read_json_strict(path, None)
        except CorruptJsonError as e:
            return 409, {"error": f"manifeste corrompu : {e}"}
        if not isinstance(data, dict) or not isinstance(data.get("agents"), list):
            return 404, {"error": "module claude-team inactif (manifeste absent)"}
        changed = False
        routing = data.get("routing")
        if not isinstance(routing, dict):
            routing = json.loads(json.dumps(ROUTING_DEFAULT))
            data["routing"] = routing
            changed = True
        state = routing_state(data)
        if mode is not None:
            if not isinstance(mode, str) or mode not in state["modes"]:
                return 400, {"error": f"mode invalide (attendu : {', '.join(state['modes'])})"}
            if routing.get("mode") != mode:
                routing["mode"] = mode
                changed = True
        if review_gate is not None:
            if not isinstance(review_gate, str) or review_gate not in state["review_gate_values"]:
                return 400, {"error": "relecture invalide (attendu : "
                                      f"{', '.join(state['review_gate_values'])})"}
            if routing.get("review_gate") != review_gate:
                routing["review_gate"] = review_gate
                changed = True
        if changed:
            write_json(path, data)
        return 200, {"routing": routing_state(data), "written": changed}


# --- Empreinte de configuration -------------------------------------------------

def team_config_hash(ws_dir: Path, default_prefix: str | None = None) -> str:
    """sha1 court de la configuration mesurée par /eval : chemins relatifs
    (posix, triés) + contenus bruts de `.claude/team.json`,
    `.claude/team/agents/*.md` et des agents générés
    `.claude/agents/<prefix>-*.md`. Même algorithme que CONFIG_HASH_ONELINER
    (`{{name}}` du one-liner = `default_prefix`, défaut : nom du dossier)."""
    c = ws_dir / ".claude"
    manifest = read_json(c / "team.json", None)
    prefix = manifest_prefix(manifest if isinstance(manifest, dict) else None) \
        or default_prefix or ws_dir.name
    files = sorted([c / "team.json", *c.glob("team/agents/*.md"), *c.glob(f"agents/{prefix}-*.md")],
                   key=lambda x: x.relative_to(ws_dir).as_posix())
    h = hashlib.sha1()
    for f in files:
        try:
            content = f.read_bytes()
        except OSError:
            continue
        h.update(f.relative_to(ws_dir).as_posix().encode("utf-8") + bytes(1) + content + bytes(1))
    return h.hexdigest()[:CONFIG_HASH_LEN]


# --- Mapping manifeste -> frontmatter ------------------------------------------

def _effective_model(agent: dict, manifest: dict, overrides: dict | None) -> str:
    """Alias de modèle du frontmatter : override par agent, puis `model`
    déclaré par l'agent, puis `default_model` de l'override (agents sans
    modèle déclaré seulement), puis `models.default` du manifeste, puis
    `sonnet`."""
    overrides = overrides or {}
    per_agent = overrides.get("models") or {}
    for cand in (per_agent.get(agent.get("id")), agent.get("model"),
                 overrides.get("default_model"), (manifest.get("models") or {}).get("default")):
        if isinstance(cand, str) and cand in TEAM_MODEL_ALIASES:
            return cand
    return "sonnet"


def _effective_effort(agent: dict) -> str | None:
    """Niveau d'effort (`effort:` du frontmatter) déclaré par l'agent dans le
    manifeste, ou None (non déclaré ou hors TEAM_EFFORT_LEVELS) : rien n'est
    alors écrit, le rendu reste identique à celui d'avant l'effort."""
    v = agent.get("effort")
    return v if isinstance(v, str) and v in TEAM_EFFORT_LEVELS else None


# Modèles sans phrase d'« usage » dans la description générée : haiku
# (historique), fable et inherit (absents du catalogue `models` du manifeste).
_NO_USAGE_MODELS = ("haiku", "fable", "inherit")


def agent_tools(agent: dict, manifest: dict) -> list[str]:
    """Outils Claude Code dérivés des capacités (CAPABILITY_TOOLS), des
    outils d'écriture si non read_only, et `Agent` pour le point d'entrée.
    Dédupliqués, ordre stable."""
    tools: list[str] = []

    def add(names):
        for n in names:
            if n not in tools:
                tools.append(n)

    read_only = bool(agent.get("read_only"))
    for cap in agent.get("capabilities") or []:
        add(CAPABILITY_TOOLS.get(str(cap), ()))
        if not read_only:
            add(CAPABILITY_WRITE_TOOLS.get(str(cap), ()))
    entrypoint = (manifest.get("team") or {}).get("entrypoint")
    if agent.get("id") == entrypoint or agent.get("can_delegate_to"):
        add(("Agent",))
    return tools


def _agent_name(agent: dict, vars: dict) -> str:
    return f"{vars.get('name') or 'ws'}-{agent['id']}"


def agent_frontmatter(agent: dict, manifest: dict, vars: dict,
                      overrides: dict | None = None) -> dict:
    """Champs du frontmatter Claude Code pour `agent` : name, description,
    model, effort (None si non déclaré), tools (liste)."""
    desc = str(agent.get("description") or "").strip()
    role = str(agent.get("role") or "").strip()
    model = _effective_model(agent, manifest, overrides)
    usage = None
    if model not in _NO_USAGE_MODELS:
        usage = ((manifest.get("models") or {}).get(model) or {}).get("usage")
    extra = []
    if role:
        extra.append(f"Rôle : {role}")
    if usage:
        extra.append(f"Modèle {model} ({usage})")
    if extra:
        desc = (desc + " " if desc else "") + "[" + " ; ".join(extra) + "]"
    # Couche 2 du routage always-on : Claude Code lit la description pour
    # déléguer de lui-même ; les déclencheurs y figurent donc en clair.
    routing = _routing_phrase(agent)
    if routing:
        desc = (desc + " " if desc else "") + routing
    return {
        "name": _agent_name(agent, vars),
        "description": desc or f"Agent {agent['id']} de l'équipe {vars.get('label') or ''}".strip(),
        "model": model,
        "effort": _effective_effort(agent),
        "tools": agent_tools(agent, manifest),
    }


def agent_auto(agent: dict) -> bool | None:
    """`auto` de l'agent : True / False si déclaré (booléen), None sinon
    (manifeste d'avant le routage : description et contraintes inchangées)."""
    v = agent.get("auto")
    return v if isinstance(v, bool) else None


def agent_triggers(agent: dict) -> list[str]:
    """Déclencheurs déclarés (chaînes non vides, ordre préservé)."""
    return [t.strip() for t in (agent.get("triggers") or []) if isinstance(t, str) and t.strip()]


def _routing_phrase(agent: dict) -> str:
    """Phrase de routage ajoutée à la description générée, ou '' si l'agent
    ne déclare pas `auto`."""
    auto = agent_auto(agent)
    if auto is None:
        return ""
    if not auto:
        return "Jamais en routage automatique : réservé à /eval et /improve."
    triggers = agent_triggers(agent)
    if not triggers:
        return "À utiliser automatiquement en routage auto."
    return "À utiliser automatiquement quand : " + ", ".join(triggers) + "."


def _constraints_block(agent: dict, manifest: dict, vars: dict) -> str:
    """Bloc « Contraintes d'exécution » : les champs du manifeste sans
    équivalent natif dans Claude Code deviennent des règles explicites."""
    lines: list[str] = []
    if agent.get("max_turns"):
        lines.append(f"- **Budget** : environ {agent['max_turns']} tours au maximum "
                     "(indicatif). Au-delà, conclure et remonter ce qui reste.")
    if agent.get("read_only"):
        lines.append("- **Lecture seule** : tu ne modifies aucun fichier du workspace ; "
                     "tes outils d'écriture ne sont pas accordés.")
    if agent.get("isolation") == "blind":
        lines.append("- **Isolation « blind »** : tu ne reçois que l'objectif, les critères "
                     "de réussite et le livrable. Jamais le raisonnement ni le transcript de "
                     "l'agent qui a produit le livrable ; si on te les transmet, ignore-les.")
    if agent.get("escalate_to"):
        lines.append(f"- **Escalade** : si une étape échoue deux fois, arrête-toi et remonte "
                     f"le blocage à l'orchestrateur, qui relance l'étape avec le modèle "
                     f"`{agent['escalate_to']}`.")
    if agent.get("temperature") == 0:
        lines.append("- **Reproductibilité** : la température n'est pas pilotable dans "
                     "Claude Code ; applique une procédure strictement reproductible (même "
                     "ordre, mêmes commandes, résultats bruts notés) et indique le modèle utilisé.")
    if agent.get("scope") == "improvement_loop_only":
        lines.append("- **Périmètre** : tu n'es invoqué que par `/improve` (boucle "
                     "d'amélioration mesurée). Hors de cette boucle, refuse et renvoie vers "
                     "`/improve`.")
    deleg = agent.get("can_delegate_to") or []
    if deleg:
        names = ", ".join(f"`{_agent_name({'id': d}, vars)}`" for d in deleg if safe_id(str(d)))
        lines.append(f"- **Délégation** : tu délègues uniquement à {names} (outil Agent, "
                     "sous-agents de ce workspace). Chaque délégation suit le contrat ci-dessous.")
    auto = agent_auto(agent)
    if auto is True:
        triggers = agent_triggers(agent)
        lines.append("- **Routage** : automatique (déclencheurs : "
                     + (", ".join(triggers) if triggers else "selon la table du CLAUDE.md")
                     + ") ; le fil principal te mobilise sans appel explicite quand "
                     "`routing.mode` de `.claude/team.json` est `auto`.")
    elif auto is False:
        lines.append("- **Routage** : manuel uniquement (jamais en routage automatique ; "
                     "réservé à `/eval` et `/improve`).")
    if not lines:
        return ""
    return "# Contraintes d'exécution\n" + "\n".join(lines) + "\n\n"


def render_agent(agent: dict, manifest: dict, vars: dict, body: str,
                 overrides: dict | None = None) -> str:
    """Contenu complet d'un agent généré : frontmatter + marqueur + en-tête
    de provenance + contraintes + corps (placeholders substitués)."""
    fm = agent_frontmatter(agent, manifest, vars, overrides)
    desc = fm["description"].replace("\n", " ").replace('"', "'")
    # `effort:` seulement s'il est déclaré : un manifeste sans effort rend
    # exactement le même fichier qu'avant (empreinte /eval inchangée).
    effort_line = f"effort: {fm['effort']}\n" if fm["effort"] else ""
    head = (
        "---\n"
        f"name: {fm['name']}\n"
        f"description: \"{desc}\"\n"
        f"model: {fm['model']}\n"
        f"{effort_line}"
        f"tools: {', '.join(fm['tools'])}\n"
        "---\n"
    )
    src_rel = str(agent.get("file") or f"team/agents/{agent['id']}.md").replace("\\", "/")
    provenance = (
        f"{TEAM_GENERATED_MARKER}\n"
        f"<!-- Généré par Nebula depuis .claude/team.json et .claude/{src_rel}. "
        "Ne pas éditer ici : modifier le corps source puis ré-appliquer le module "
        "avec « Régénérer ». -->\n\n"
    )
    body = render_placeholders(body, vars).strip() + "\n"
    return head + provenance + _constraints_block(agent, manifest, vars) + body


def _is_generated(content: str) -> bool:
    """Vrai si le corps (après frontmatter) commence par le marqueur généré."""
    rest = _FRONTMATTER_RE.sub("", content, count=1)
    return rest.lstrip().startswith(TEAM_GENERATED_MARKER)


# --- Générateur ---------------------------------------------------------------

def normalize_team_options(opts: dict | None) -> dict:
    """Options du générateur depuis le payload d'activation : `models`
    ({agent_id: alias}), `default_model`, `regenerate`, `prefix` (id sûr,
    sinon None = préfixe persisté ou id du workspace). Valeurs invalides
    ignorées (jamais d'erreur : le module reste applicable)."""
    opts = opts or {}
    models: dict[str, str] = {}
    raw = opts.get("models")
    if isinstance(raw, dict):
        for k, v in raw.items():
            if isinstance(k, str) and safe_id(k) and isinstance(v, str) and v in TEAM_MODEL_ALIASES:
                models[k] = v
    default = opts.get("default_model")
    if not (isinstance(default, str) and default in TEAM_MODEL_ALIASES):
        default = None
    prefix = opts.get("prefix")
    prefix = prefix.strip() if isinstance(prefix, str) else None
    if not (prefix and safe_id(prefix)):
        prefix = None
    return {"models": models, "default_model": default,
            "regenerate": bool(opts.get("regenerate")), "prefix": prefix}


def generate_agents(ws_dir: Path, vars: dict, options: dict | None = None) -> dict:
    """Génère `.claude/agents/<prefix>-<id>.md` pour chaque agent du manifeste.

    `prefix` = option `prefix`, sinon `team.prefix` du manifeste du
    workspace, sinon `vars['name']` (id du workspace) ; il remplace
    `{{name}}` dans les noms générés ET dans les corps rendus, et il est
    persisté dans `.claude/team.json` (`team.prefix`) pour que les
    régénérations suivantes le relisent.

    Retourne {"generated": [rel, ...], "skipped": [{"path", "reason"}, ...],
    "prefix": str}. Sans manifeste lisible : rien n'est généré (skipped
    avec raison).
    """
    opts = normalize_team_options(options)
    generated: list[str] = []
    skipped: list[dict] = []
    wants_models = bool(opts["models"] or opts["default_model"])
    manifest = load_manifest(ws_dir)
    if manifest is None:
        # Choix de modèles demandés sur un manifeste corrompu : ils ne
        # pourraient pas être mémorisés -> CorruptJsonError (409 côté route).
        if wants_models and (ws_dir / MANIFEST_REL).exists():
            read_json_strict(ws_dir / MANIFEST_REL, None)
        skipped.append({"path": MANIFEST_REL.as_posix(), "reason": "manifeste absent ou illisible"})
        return {"generated": generated, "skipped": skipped, "prefix": None}

    prefix = effective_prefix(manifest, vars, opts["prefix"])
    # Préfixe des agents DÉJÀ générés (avant un éventuel nouveau préfixe) :
    # c'est là que se lisent les modèles d'avant la 2.5.0 (agent_file_models).
    old_prefix = effective_prefix(manifest, vars)
    # Les corps sont rendus avec le préfixe comme `{{name}}` (noms d'agents
    # dans la règle de délégation, mentions dans le corps).
    vars = {**vars, "name": prefix}
    with _MUTATION_LOCK:
        try:
            _persist_prefix(ws_dir, prefix)
        except CorruptJsonError as e:
            skipped.append({"path": MANIFEST_REL.as_posix(), "reason": f"manifeste corrompu : {e}"})
        if wants_models or opts["regenerate"]:
            # Modèles choisis à l'activation écrits dans `agents[i].model` :
            # un « Régénérer » ultérieur sans payload les retrouve (lecture
            # stricte : CorruptJsonError remontée, jamais d'écrasement). Les
            # modèles restés seulement dans les agents générés sont repris
            # d'abord (sinon la régénération les remettrait au défaut).
            try:
                if _persist_models(ws_dir, opts["models"], opts["default_model"], old_prefix):
                    manifest = load_manifest(ws_dir) or manifest
            except CorruptJsonError:
                if wants_models:
                    raise
        # Reprise non écrite (itération en attente) : appliquée au rendu.
        manifest = _with_file_models(manifest, agent_file_models(ws_dir, manifest, old_prefix))
        for rel, target, content, reason in _agent_jobs(ws_dir, manifest, vars, opts):
            if content is None:
                skipped.append({"path": rel, "reason": reason})
                continue
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
                generated.append(rel)
            except OSError as e:
                log.warning("génération agent %s : %s", target, e)
                skipped.append({"path": rel, "reason": f"write error: {e}"})
    return {"generated": generated, "skipped": skipped, "prefix": prefix}


def _agent_jobs(ws_dir: Path, manifest: dict, vars: dict, opts: dict) -> list[tuple]:
    """Travail du générateur, sans rien écrire : par agent du manifeste,
    (rel, cible, contenu rendu à écrire, None) ou (rel, cible, None, raison
    du saut). `vars['name']` = préfixe effectif ; `opts` normalisées."""
    jobs: list[tuple] = []
    for agent in manifest_agents(manifest):
        src_rel = str(agent.get("file") or f"team/agents/{agent['id']}.md")
        src = _claude_path(ws_dir, src_rel)
        target = ws_dir / AGENTS_DIR_REL / f"{_agent_name(agent, vars)}.md"
        rel = target.relative_to(ws_dir).as_posix()
        if src is None:
            jobs.append((rel, target, None, f"corps source hors de .claude refusé : {src_rel}"))
            continue
        try:
            body = src.read_text(encoding="utf-8")
        except OSError:
            jobs.append((rel, target, None, f"corps source absent : .claude/{src_rel}"))
            continue
        if target.exists():
            if not opts["regenerate"]:
                jobs.append((rel, target, None, "already present"))
                continue
            try:
                existing = target.read_text(encoding="utf-8")
            except OSError:
                existing = ""
            if not _is_generated(existing):
                jobs.append((rel, target, None, "édité à la main (marqueur généré absent)"))
                continue
        jobs.append((rel, target, render_agent(agent, manifest, vars, body, opts), None))
    return jobs


def agents_rewrite_pending(ws_dir: Path, vars: dict, options: dict | None = None) -> dict | None:
    """Itération /improve en attente qui bloquerait une ré-application :
    `generate_agents` réécrirait RÉELLEMENT au moins un agent (contenu rendu
    différent de l'agent présent, ou agent absent : team.json ou corps
    modifié depuis la phase 1, nouveau préfixe...). None sinon (rien ne
    changerait, ou aucune itération en attente). Lecture seule, tolérante
    (manifeste corrompu : traité par l'appelant)."""
    manifest = load_manifest(ws_dir)
    if manifest is None:
        return None
    pend = pending_iteration(ws_dir, manifest)
    if not pend:
        return None
    opts = normalize_team_options(options)
    # Même rendu que generate_agents sous itération en attente : les modèles
    # restés seulement dans les agents générés sont conservés (pas de faux refus).
    manifest = _with_file_models(manifest, agent_file_models(
        ws_dir, manifest, effective_prefix(manifest, vars or {})))
    vars = {**(vars or {}), "name": effective_prefix(manifest, vars or {}, opts["prefix"])}
    for _rel, target, content, _reason in _agent_jobs(ws_dir, manifest, vars, opts):
        if content is None:
            continue
        try:
            existing = target.read_text(encoding="utf-8")
        except OSError:
            return pend
        if existing.replace("\r\n", "\n") != content.replace("\r\n", "\n"):
            return pend
    return None


# --- État (routes GET) ----------------------------------------------------------

def _evals_unlocked(ws_dir: Path) -> bool:
    local = read_json(ws_dir / ".claude" / "settings.local.json", {})
    return isinstance(local, dict) and local.get("evals_unlocked") is True


def _count_jsonl(path: Path) -> int:
    try:
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    except OSError:
        return 0


def stale_agent_ids(ws_dir: Path, manifest: dict, vars: dict, prefix: str) -> list[str]:
    """Ids des agents générés par Nebula (marqueur présent) dont le fichier
    diffère du rendu actuel (corps source ou manifeste modifié depuis la
    dernière génération). Même rendu que `generate_agents(regenerate)`,
    fins de ligne ignorées ; pas de comparaison de dates. Lecture seule."""
    vars = {**vars, "name": prefix}
    opts = normalize_team_options({"regenerate": True})
    by_rel = {}
    for agent in manifest_agents(manifest):
        by_rel[(AGENTS_DIR_REL / f"{_agent_name(agent, vars)}.md").as_posix()] = agent["id"]
    out = []
    for rel, target, content, _reason in _agent_jobs(ws_dir, manifest, vars, opts):
        if content is None:
            continue
        try:
            existing = target.read_text(encoding="utf-8")
        except OSError:
            # Fichier généré disparu : une régénération le recréerait.
            out.append(by_rel.get(rel) or rel)
            continue
        if existing.replace("\r\n", "\n") != content.replace("\r\n", "\n"):
            out.append(by_rel.get(rel) or rel)
    return out


def team_state(ws_id: str, vars: dict | None = None) -> tuple[int, dict]:
    """Manifeste + agents (générés ou non, modèle effectif, outils) + verrou.
    `vars` : variables de rendu du workspace (cf. overlay_vars), pour
    `stale_agents` ; défaut : id du workspace seul."""
    if not safe_id(ws_id):
        return 400, {"error": "id invalide"}
    ws_dir = resolve_ws_dir(ws_id)
    if not ws_dir.exists():
        return 404, {"error": "workspace absent sur disque"}
    manifest = load_manifest(ws_dir)
    if manifest is None:
        return 200, {"active": False, "agents": [], "manifest": None}
    prefix = effective_prefix(manifest, {"name": ws_id})
    vars = {"name": prefix, "label": ws_id}
    # Modèles d'avant la 2.5.0 restés seulement dans les agents générés :
    # affichés comme modèles actuels (vue), persistés à la prochaine écriture.
    file_models = agent_file_models(ws_dir, manifest, prefix)
    manifest = _with_file_models(manifest, file_models)
    agents = []
    for a in manifest_agents(manifest):
        fm = agent_frontmatter(a, manifest, vars)
        model_source = ("agent_file" if a["id"] in file_models
                        else "manifest" if _declared_model(a) else "default")
        target = ws_dir / AGENTS_DIR_REL / f"{fm['name']}.md"
        present = target.is_file()
        generated_by_nebula = False
        if present:
            try:
                generated_by_nebula = _is_generated(target.read_text(encoding="utf-8"))
            except OSError:
                pass
        agents.append({
            "id": a["id"], "role": a.get("role") or "", "description": a.get("description") or "",
            "model": a.get("model") or (manifest.get("models") or {}).get("default") or "sonnet",
            "effective_model": fm["model"], "tools": fm["tools"],
            # Provenance du modèle : `manifest` (déclaré dans team.json),
            # `agent_file` (choix d'avant la 2.5.0 lu dans l'agent généré,
            # pas encore écrit dans team.json), `default` (défaut du manifeste).
            "model_source": model_source,
            # Effort déclaré (brut) et effort réellement rendu (None = aucun
            # `effort:` dans l'agent généré, réglage par défaut de Claude Code).
            "effort": a.get("effort") if isinstance(a.get("effort"), str) else None,
            "effective_effort": fm["effort"],
            "read_only": bool(a.get("read_only")), "name": fm["name"],
            "path": target.relative_to(ws_dir).as_posix(),
            "generated": present, "generated_by_nebula": generated_by_nebula,
            # Routage always-on (couche 2) : None = non déclaré (manifeste
            # d'avant le routage), True / False sinon.
            "auto": agent_auto(a), "triggers": agent_triggers(a),
        })
    loop = manifest.get("improvement_loop") or {}
    signals = measure_signals(ws_dir, manifest)
    return 200, {
        "active": True,
        # Agents générés dont le fichier diffère du rendu actuel (corps ou
        # manifeste modifié depuis la dernière génération) : à régénérer.
        "stale_agents": stale_agent_ids(ws_dir, manifest, {"label": ws_id, **(vars or {})}, prefix),
        "manifest": {"team": manifest.get("team") or {}, "models": manifest.get("models") or {},
                     "improvement_loop": loop},
        "agents": agents,
        # Propositions modèle / effort (règles par rôle + signal mesuré),
        # appliquées seulement au clic (POST .../team/agents-config).
        "suggestions": suggest_agent_config(manifest, signals),
        "suggestions_basis": {
            "measured": signals is not None,
            "date": (signals or {}).get("date") or None,
            "iteration": (signals or {}).get("iteration"),
        },
        "model_aliases": list(TEAM_MODEL_ALIASES),
        "effort_levels": list(TEAM_EFFORT_LEVELS),
        "prefix": prefix,
        "routing": routing_state(manifest),
        # Itération /improve en attente de verdict ({"iteration": n}) ou None :
        # la modale d'activation verrouille alors modèles et efforts.
        "pending": pending_iteration(ws_dir, manifest),
        "config_hash": team_config_hash(ws_dir, ws_id),
        "evals_locked": bool(loop.get("eval_set_locked")),
        "evals_unlocked": _evals_unlocked(ws_dir),
    }


def _claude_path(ws_dir: Path, rel: str) -> Path | None:
    """Chemin `rel` du manifeste résolu sous `ws_dir/.claude`, ou None s'il en sort.

    Le manifeste vient du workspace (dépôt tiers adopté, overlay qui ne
    remplace jamais un team.json existant) : un `file` ou un `journal`
    absolu ou en `../` ferait lire, voire recopier dans `.claude/agents/`,
    un fichier hors du workspace.
    """
    base = (ws_dir / ".claude").resolve()
    try:
        p = (base / rel).resolve()
    except (OSError, ValueError):
        return None
    return p if p.is_relative_to(base) else None


def _parse_journal(path: Path) -> tuple[list[dict], int]:
    """Lignes JSON du journal (objets seulement) + nombre de lignes invalides."""
    entries: list[dict] = []
    invalid = 0
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return entries, invalid
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            invalid += 1
            continue
        if not isinstance(obj, dict):
            invalid += 1
            continue
        entries.append(obj)
    return entries, invalid


def _norm_status(raw) -> str:
    s = str(raw or "").strip().lower()
    if s.startswith("accept"):
        return "accepted"
    if s.startswith("rejet") or s.startswith("reject"):
        return "rejected"
    if s.startswith("pend") or s.startswith("attente"):
        return "pending"
    return s or "unknown"


def _as_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def count_register_statuses(path: Path) -> dict[str, int]:
    """Compte les items `**[STATUT ...]**` par statut dans un registre."""
    counts = {s: 0 for s in REGISTER_STATUSES}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return counts
    for m in _STATUS_RE.finditer(text):
        counts[m.group(1)] += 1
    return counts


def improvement_state(ws_id: str) -> tuple[int, dict]:
    """Journal parsé + stats + compteurs des registres + état des évals."""
    if not safe_id(ws_id):
        return 400, {"error": "id invalide"}
    ws_dir = resolve_ws_dir(ws_id)
    if not ws_dir.exists():
        return 404, {"error": "workspace absent sur disque"}
    manifest = load_manifest(ws_dir)
    loop = (manifest or {}).get("improvement_loop") or {}
    # Chemin hors de .claude : traité comme absent (rien n'est lu ailleurs).
    journal_p = _claude_path(ws_dir, str(loop.get("journal") or "journal/changes.jsonl"))
    eval_p = _claude_path(ws_dir, str(loop.get("eval_set") or "evals/eval-set.jsonl"))
    holdout_p = _claude_path(ws_dir, str(loop.get("holdout_set") or "evals/holdout.jsonl"))

    entries, invalid = _parse_journal(journal_p) if journal_p else ([], 0)
    journal = []
    for i, e in enumerate(entries, 1):
        status = _norm_status(e.get("status"))
        regs = e.get("regressions")
        if not isinstance(regs, list):
            regs = [] if regs in (None, "", 0) else [str(regs)]
        journal.append({
            "iteration": e.get("iteration") if isinstance(e.get("iteration"), int) else i,
            "date": str(e.get("date") or ""),
            "target": str(e.get("target") or ""),
            "hypothesis": str(e.get("hypothesis") or ""),
            "score_before": _as_float(e.get("score_before")),
            "score_after": _as_float(e.get("score_after")),
            "regressions": [str(r) for r in regs],
            "status": status,
            "commit": str(e.get("commit") or "") or None,
            # Empreinte de la configuration en place APRÈS l'itération
            # (candidat si acceptée, baseline si rejetée) : cf. team_config_hash.
            "config_version": str(e.get("config_version") or "") or None,
            # Cas inexécutables (outil absent, commande introuvable) lors de
            # la mesure : une baseline qui en contient n'est pas réutilisable.
            "unrunnable": e.get("unrunnable") if isinstance(e.get("unrunnable"), int) else 0,
            # Phase 1 de /improve : empreinte de la baseline mesurée (le
            # config_version d'une ligne pending est celle du CANDIDAT).
            "baseline_version": str(e.get("baseline_version") or "") or None,
            "untracked": bool(e.get("untracked")),
            "_raw": e,
        })
    _enrich_journal(journal)
    # Protocole en deux phases (cf. commands/improve.md) : une itération
    # peut avoir une ligne `pending` (candidat posé, session A) puis une
    # ligne de résolution (session B). La DERNIÈRE ligne d'une itération
    # fait foi ; une itération encore `pending` n'est ni acceptée ni rejetée.
    by_iter: dict = {}
    for j in journal:
        by_iter[j["iteration"]] = j
    resolved = [j for j in by_iter.values() if j["status"] in ("accepted", "rejected")]
    pending_entries = [j for j in by_iter.values() if j["status"] == "pending"]
    pending = pending_entries[-1] if pending_entries else None
    accepted = sum(1 for j in resolved if j["status"] == "accepted")
    rejected = sum(1 for j in resolved if j["status"] == "rejected")
    # Série des scores : le score après chaque itération acceptée (la
    # configuration courante), précédé de la baseline de la 1re itération.
    scores: list[float] = []
    if journal and journal[0]["score_before"] is not None:
        scores.append(journal[0]["score_before"])
    for j in resolved:
        if j["status"] == "accepted" and j["score_after"] is not None:
            scores.append(j["score_after"])
    last_score = scores[-1] if scores else None
    # Rejets consécutifs en fin de journal (arrêt de la boucle).
    streak = 0
    for j in reversed(resolved):
        if j["status"] == "rejected":
            streak += 1
        else:
            break

    registers = {name.split(".")[0]: count_register_statuses(ws_dir / ".claude" / name)
                 for name in REGISTER_FILES}
    # Baseline à jour : la dernière ligne du journal mesure la configuration
    # courante (même config_version que l'empreinte calculée maintenant) et
    # n'a pas de cas inexécutable. /improve la réutilise alors sans re-mesurer.
    config_hash = team_config_hash(ws_dir, ws_id) if manifest is not None else None
    last_entry = resolved[-1] if resolved else None
    baseline_current = bool(
        last_entry and config_hash and last_entry["config_version"] == config_hash
        and not last_entry["unrunnable"]
    )
    baseline_version = last_entry["config_version"] if last_entry else None
    # Candidat en attente de verdict : toujours en place si son empreinte
    # est l'empreinte courante (sinon il a été altéré entre les sessions).
    pending_info = None
    if pending:
        pending_info = {
            "iteration": pending["iteration"],
            "target": pending["target"],
            "hypothesis": pending["hypothesis"],
            "score_before": pending["score_before"],
            "config_version": pending["config_version"],
            "baseline_version": pending["baseline_version"],
            "in_place": bool(config_hash and pending["config_version"] == config_hash),
        }
    stats_extra = _extra_stats(journal, by_iter, resolved)
    result = {
        "active": manifest is not None,
        "journal": journal,
        "invalid_lines": invalid,
        "config_hash": config_hash,
        "baseline_current": baseline_current,
        "baseline_version": baseline_version,
        "pending": pending_info,
        "stats": {"iterations": len(by_iter), "accepted": accepted, "rejected": rejected,
                  "pending": len(pending_entries),
                  "last_score": last_score, "scores": scores,
                  "consecutive_rejects": streak, **stats_extra},
        "loop": {k: loop.get(k) for k in ("accept_if", "max_iterations",
                                           "stop_after_consecutive_rejects", "runs_per_eval")},
        "evals": {
            "locked": bool(loop.get("eval_set_locked")),
            "unlocked": _evals_unlocked(ws_dir),
            "cases": _count_jsonl(eval_p) if eval_p else 0,
            "holdout_cases": _count_jsonl(holdout_p) if holdout_p else 0,
        },
        "registers": registers,
        "todo_items": _todo_items(ws_dir / ".claude" / "improvements.md"),
        "cases": _cases_summary(eval_p, entries),
    }
    return 200, result


# --- Métriques de la boucle d'amélioration ----------------------------------------

_TOKEN_KEYS = ("input", "output", "cache_read", "cache_creation")


def _num(v):
    """Nombre >= 0 (bool exclu), sinon None."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return v if v >= 0 else None


def _enrich_journal(journal: list[dict]) -> None:
    """Ajoute à chaque ligne les métriques AGRÉGÉES de son itération (coût,
    jetons, durée, appels : sommes de la ligne `pending` et de la ligne de
    résolution), calculées avant la règle « la dernière ligne fait foi ».
    Les sommes sont répétées sur chaque ligne d'une même itération : pour
    totaliser, passer par `stats`. Retire la clé interne `_raw`."""
    groups: dict = {}
    for j in journal:
        groups.setdefault(j["iteration"], []).append(j)
    for lines in groups.values():
        raws = [j["_raw"] for j in lines]
        costs = [c for c in (_num(r.get("cost_usd")) for r in raws) if c is not None]
        durs = [c for c in (_num(r.get("duration_ms")) for r in raws) if c is not None]
        calls = [c for c in (_num(r.get("calls")) for r in raws) if c is not None]
        tok_lines = [r["tokens"] for r in raws if isinstance(r.get("tokens"), dict)]
        tokens = None
        if tok_lines:
            tokens = {k: sum(_num(t.get(k)) or 0 for t in tok_lines) for k in _TOKEN_KEYS}

        def last(key, raws=raws):
            for r in reversed(raws):
                if r.get(key) not in (None, ""):
                    return r[key]
            return None

        fa = last("failures_after")
        if isinstance(fa, list):
            fa = len(fa)
        elif not isinstance(fa, int) or isinstance(fa, bool):
            fa = None
        reason, archive = last("reason"), last("diff_archive")
        agg = {
            "cost_usd": round(sum(costs), 6) if costs else None,
            "tokens": tokens,
            "duration_ms": sum(durs) if durs else None,
            "calls": sum(calls) if calls else None,
            "reason": str(reason) if reason is not None else None,
            "diff_archive": str(archive) if archive is not None else None,
            "failures_after": fa,
        }
        for j in lines:
            j.update(agg)
    for j in journal:
        j.pop("_raw", None)


def _extra_stats(journal: list[dict], by_iter: dict, resolved: list[dict]) -> dict:
    """Statistiques ajoutées : taux d'acceptation, gain cumulé, coûts moyens."""
    acc = [j for j in resolved if j["status"] == "accepted"]
    gains = [j["score_after"] - j["score_before"] for j in acc
             if j["score_after"] is not None and j["score_before"] is not None]
    costs = [j["cost_usd"] for j in by_iter.values() if j["cost_usd"] is not None]
    toks = [j["tokens"] for j in by_iter.values() if j["tokens"] is not None]
    return {
        "acceptance_rate": round(len(acc) / len(resolved), 4) if resolved else None,
        "cumulative_gain": round(sum(gains), 4),
        "avg_cost_usd": round(sum(costs) / len(costs), 6) if costs else None,
        "avg_tokens": ({k: round(sum(t[k] for t in toks) / len(toks), 1) for k in _TOKEN_KEYS}
                       if toks else None),
    }


_ITEM_RE = re.compile(r"^- \*\*\[(?P<status>[^\]]+)\]\s*(?P<title>.+?)\*\*")
_PRIO_RE = re.compile(r"\(\s*(P\d)\b")
_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def _todo_items(path: Path) -> list[dict]:
    """Items `[TODO]` d'improvements.md : `{title, priority, date}` (lecture seule)."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, ValueError):
        return []
    out = []
    for head in text.splitlines():
        m = _ITEM_RE.match(head)
        if not m or m.group("status").strip() != "TODO":
            continue
        pm, dm = _PRIO_RE.search(head), _DATE_RE.search(head)
        out.append({"title": m.group("title").strip(), "priority": pm.group(1) if pm else None,
                    "date": dm.group(1) if dm else None})
    return out


def _cases_summary(eval_p: Path | None, entries: list[dict]) -> list[dict]:
    """Résumé du jeu d'évals : `{id, agent, grader, last_result}`. Le dernier
    résultat vient de la dernière ligne du journal portant une liste d'échecs
    (`pass` / `fail` ; `unrunnable` si l'id figure dans `unrunnable_ids`),
    null sans mesure. LECTURE seule."""
    if eval_p is None:
        return []
    cases, _ = _parse_journal(eval_p)
    failed, unrun = None, set()
    for e in reversed(entries):
        for key in _FAILURE_KEYS:
            ids = _failure_ids(e.get(key))
            if ids is not None:
                failed = ids
                break
        if failed is not None:
            unrun = _failure_ids(e.get("unrunnable_ids")) or set()
            break
    out = []
    for c in cases:
        cid = c.get("id")
        if not isinstance(cid, str):
            continue
        if failed is None:
            res = None
        elif cid in unrun:
            res = "unrunnable"
        else:
            res = "fail" if cid in failed else "pass"
        out.append({"id": cid, "agent": c.get("agent") if isinstance(c.get("agent"), str) else None,
                    "grader": c.get("grader") if isinstance(c.get("grader"), str) else None,
                    "last_result": res})
    return out


# --- Modèle et effort par agent : propositions + application ------------------

# Seuils du signal mesuré : un agent n'est signalé que sur assez de cas.
SIGNAL_MIN_CASES = 2
SIGNAL_MAX_SUCCESS = 0.5
# Clés du journal portant des ids de cas échoués, par ordre de préférence
# dans une même ligne (mesure du candidat, puis mesure de la baseline).
_FAILURE_KEYS = ("failures_after", "failures", "failures_before")


def _failure_ids(raw) -> set[str] | None:
    """Ids de cas échoués d'un champ du journal (liste de chaînes ou d'objets
    `{"id": ...}`), ou None si le champ n'est pas une liste (absent)."""
    if not isinstance(raw, list):
        return None
    out: set[str] = set()
    for f in raw:
        if isinstance(f, str) and f:
            out.add(f)
        elif isinstance(f, dict) and isinstance(f.get("id"), str):
            out.add(f["id"])
    return out


def measure_signals(ws_dir: Path, manifest: dict) -> dict | None:
    """Signal mesuré pour les propositions : dernière ligne du journal qui
    porte une liste d'échecs, croisée avec le champ `agent` des cas de
    `eval-set.jsonl` (LECTURE seule). Retourne `{"date", "iteration",
    "by_agent": {id: {"passed", "total"}}}`, ou None sans mesure exploitable
    (journal vide, aucune liste d'échecs, jeu d'évals absent)."""
    loop = manifest.get("improvement_loop") or {}
    journal_p = _claude_path(ws_dir, str(loop.get("journal") or "journal/changes.jsonl"))
    eval_p = _claude_path(ws_dir, str(loop.get("eval_set") or "evals/eval-set.jsonl"))
    if journal_p is None or eval_p is None:
        return None
    entries, _ = _parse_journal(journal_p)
    chosen, failed = None, None
    for e in reversed(entries):
        for key in _FAILURE_KEYS:
            ids = _failure_ids(e.get(key))
            if ids is not None:
                chosen, failed = e, ids
                break
        if chosen is not None:
            break
    if chosen is None:
        return None
    cases, _ = _parse_journal(eval_p)  # même format JSONL, lecture seule
    if not cases:
        return None
    by_agent: dict[str, dict] = {}
    for c in cases:
        cid, aid = c.get("id"), c.get("agent")
        if not (isinstance(cid, str) and isinstance(aid, str)):
            continue
        d = by_agent.setdefault(aid, {"passed": 0, "total": 0})
        d["total"] += 1
        if cid not in failed:
            d["passed"] += 1
    it = chosen.get("iteration")
    return {"date": str(chosen.get("date") or ""), "iteration": it if isinstance(it, int) else None,
            "by_agent": by_agent}


def _effort_rank(effort: str | None) -> int:
    return TEAM_EFFORT_LEVELS.index(effort) if effort in TEAM_EFFORT_LEVELS else -1


def suggest_agent_config(manifest: dict, signals: dict | None = None) -> list[dict]:
    """Propositions modèle / effort par agent (fonction pure).

    1. Règle du rôle (TEAM_ROLE_DEFAULTS), qui ne fait que COMPLÉTER :
       - modèle du rôle proposé seulement à un agent SANS modèle déclaré
         dans team.json (un modèle déclaré n'est jamais remis en cause) ;
       - effort du rôle (plafonné à `high`) proposé seulement s'il est
         STRICTEMENT au-dessus de l'effort actuel. Un agent sans effort est
         rapporté à TEAM_SESSION_DEFAULT_EFFORT (`medium`, défaut Claude Code des
         modèles 5.5) : les rôles à `high` lui proposent `high`, jamais de baisse.
    2. Signal mesuré (`measure_signals`) : agent avec au moins
       SIGNAL_MIN_CASES cas et un taux de réussite < SIGNAL_MAX_SUCCESS ->
       +1 cran d'effort au-dessus du plus haut entre l'actuel (ou le défaut
       de session) et la règle ; rien au-delà de `max`. Jamais de changement
       de modèle par le signal.

    Retourne `[{"agent", "current": {model, effort}, "proposed": {model,
    effort}, "reasons": [...], "source": "rule" | "measure" | "rule+measure"}]`,
    seulement pour les agents dont la proposition diffère de l'actuel."""
    out: list[dict] = []
    high = _effort_rank("high")
    by_agent = (signals or {}).get("by_agent") or {}
    for a in manifest_agents(manifest):
        cur = {"model": _effective_model(a, manifest, None), "effort": _effective_effort(a)}
        cur_rank = _effort_rank(cur["effort"] or TEAM_SESSION_DEFAULT_EFFORT)
        prop = dict(cur)
        reasons: list[str] = []
        sources: list[str] = []
        rule = TEAM_ROLE_DEFAULTS.get(a["id"])
        if rule:
            r_model = rule.get("model")
            if (_declared_model(a) is None and r_model in TEAM_MODEL_ALIASES
                    and r_model != cur["model"]):
                prop["model"] = r_model
            r_rank = min(_effort_rank(rule.get("effort")), high)
            if r_rank > cur_rank:
                prop["effort"] = TEAM_EFFORT_LEVELS[r_rank]
            if prop != cur:
                reasons.append(f"Règle du rôle : {rule.get('why') or a['id']}.")
                sources.append("rule")
        stat = by_agent.get(a["id"])
        if (isinstance(stat, dict) and stat.get("total", 0) >= SIGNAL_MIN_CASES
                and stat.get("passed", 0) / stat["total"] < SIGNAL_MAX_SUCCESS):
            base = max(_effort_rank(prop["effort"]), cur_rank)
            if base + 1 < len(TEAM_EFFORT_LEVELS):
                prop["effort"] = TEAM_EFFORT_LEVELS[base + 1]
                date = (signals or {}).get("date") or "?"
                reasons.append(f"{stat['passed']}/{stat['total']} cas réussis à la mesure du "
                               f"{date} : effort +1 cran.")
                sources.append("measure")
        if prop != cur and sources:
            out.append({"agent": a["id"], "current": cur, "proposed": prop,
                        "reasons": reasons, "source": "+".join(sources)})
    return out


def set_agents_config(ws_id: str, agents_cfg, vars: dict | None = None) -> tuple[int, dict]:
    """Écrit `model` / `effort` par agent dans `.claude/team.json`, puis
    régénère les agents (seuls ceux qui portent le marqueur généré).

    `agents_cfg` = `{"<id>": {"model": "...", "effort": "...|null"}}` (clés
    optionnelles ; `effort: null` retire l'effort ; `{}` = régénération seule
    des agents marqués, `written: false`). 400 agent ou valeur hors
    liste ; 404 module inactif ; 409 manifeste corrompu ou itération
    `/improve` en attente de verdict (le candidat serait mesuré sur une autre
    configuration). Rien n'est écrit si rien ne change. Jamais la section
    `improvement_loop`. Réponse : `written`, `generated` (contenu réellement
    changé), `skipped`, `config_hash_before/after`, `baseline_stale`."""
    if not safe_id(ws_id):
        return 400, {"error": "id invalide"}
    ws_dir = resolve_ws_dir(ws_id)
    if not ws_dir.exists():
        return 404, {"error": "workspace absent sur disque"}
    if not isinstance(agents_cfg, dict):
        return 400, {"error": "corps attendu : {\"agents\": {\"<id>\": {\"model\", \"effort\"}}}"}
    path = ws_dir / MANIFEST_REL
    with _MUTATION_LOCK:
        try:
            data = read_json_strict(path, None)
        except CorruptJsonError as e:
            return 409, {"error": f"manifeste corrompu : {e}"}
        if not isinstance(data, dict) or not isinstance(data.get("agents"), list):
            return 404, {"error": "module claude-team inactif (manifeste absent)"}
        by_id = {a["id"]: a for a in data["agents"]
                 if isinstance(a, dict) and safe_id(str(a.get("id") or ""))}
        for aid, cfg in agents_cfg.items():
            if aid not in by_id:
                return 400, {"error": f"agent inconnu du manifeste : {aid}"}
            if not isinstance(cfg, dict):
                return 400, {"error": f"configuration invalide pour {aid}"}
            if "model" in cfg and cfg["model"] not in TEAM_MODEL_ALIASES:
                return 400, {"error": f"modèle invalide pour {aid} (attendu : "
                                      f"{', '.join(TEAM_MODEL_ALIASES)})"}
            if "effort" in cfg and cfg["effort"] is not None and cfg["effort"] not in TEAM_EFFORT_LEVELS:
                return 400, {"error": f"effort invalide pour {aid} (attendu : "
                                      f"{', '.join(TEAM_EFFORT_LEVELS)} ou null)"}
        hash_before = team_config_hash(ws_dir, ws_id)
        # Modèles d'avant la 2.5.0 restés seulement dans les agents générés :
        # déclarés d'abord (en mémoire), écrits avec le changement demandé,
        # sinon la régénération des 7 agents les remettrait au défaut. Seuls,
        # ils ne déclenchent aucune écriture.
        adopted = agent_file_models(ws_dir, data, effective_prefix(data, {"name": ws_id}))
        for aid, model in adopted.items():
            by_id[aid]["model"] = model
        changed = False
        for aid, cfg in agents_cfg.items():
            a = by_id[aid]
            # Égal au modèle effectif actuel : pas un changement (un modèle
            # implicite n'est pas rendu explicite pour rien).
            if "model" in cfg and cfg["model"] != _effective_model(a, data, None):
                a["model"] = cfg["model"]
                changed = True
            if "effort" in cfg:
                if cfg["effort"] is None:
                    if "effort" in a:
                        del a["effort"]
                        changed = True
                elif a.get("effort") != cfg["effort"]:
                    a["effort"] = cfg["effort"]
                    changed = True
        generated: list[str] = []
        skipped: list[dict] = []
        # Corps vide (`{}`) : régénération seule des agents marqués.
        if changed or not agents_cfg:
            # Itération /improve en attente : refus seulement si quelque chose
            # change réellement (la copie modifiée n'est jamais écrite).
            _, impr = improvement_state(ws_id)
            if changed and impr.get("pending"):
                return 409, {"error": pending_message(impr["pending"], "les modèles ou l'effort"),
                             "pending": impr["pending"]}
            regen_vars = {"label": ws_id, **(vars or {}), "name": ws_id}
            if not changed and impr.get("pending"):
                # Régénération seule : refus seulement si un agent changerait réellement.
                pend = agents_rewrite_pending(ws_dir, regen_vars, {"regenerate": True})
                if pend:
                    return 409, {"error": pending_message(pend, "les agents générés"),
                                 "pending": pend}
                # Rien ne changerait : pas de réécriture (ni team.json ni agents).
                return 200, {
                    "ok": True, "written": False, "generated": [], "skipped": [],
                    "adopted_models": {},
                    "config_hash_before": hash_before, "config_hash_after": hash_before,
                    "baseline_stale": bool(impr.get("baseline_version")) and not impr.get("baseline_current"),
                }
            if changed:
                write_json(path, data)
            try:
                manifest_before = path.read_bytes()
            except OSError:
                manifest_before = None
            prefix = effective_prefix(data, {"name": ws_id})
            targets = [ws_dir / AGENTS_DIR_REL / f"{prefix}-{aid}.md" for aid in by_id]

            def _read(p: Path):
                try:
                    return p.read_bytes()
                except OSError:
                    return None
            before = {p.relative_to(ws_dir).as_posix(): _read(p) for p in targets}
            r = generate_agents(ws_dir, regen_vars, {"regenerate": True})
            try:
                manifest_after = path.read_bytes()
            except OSError:
                manifest_after = None
            if manifest_after != manifest_before:
                changed = True
            generated = [rel for rel in r["generated"] if before.get(rel) != _read(ws_dir / rel)]
            skipped = r["skipped"]
        hash_after = team_config_hash(ws_dir, ws_id)
        _, impr_after = improvement_state(ws_id)
    return 200, {
        "ok": True, "written": changed, "generated": generated, "skipped": skipped,
        # Modèles repris des agents générés et désormais déclarés dans team.json.
        "adopted_models": adopted if changed else {},
        "config_hash_before": hash_before, "config_hash_after": hash_after,
        # Une baseline existait et ne mesure plus la configuration courante.
        "baseline_stale": bool(impr_after.get("baseline_version")) and not impr_after.get("baseline_current"),
    }
