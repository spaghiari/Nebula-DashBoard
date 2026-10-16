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
    GET /api/workspaces/<id>/team et /improvement (onglet « Amélioration »).

Stdlib only ; toute écriture sous _MUTATION_LOCK (réentrant).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from dashcore.config import (
    CAPABILITY_TOOLS, CAPABILITY_WRITE_TOOLS, REGISTER_STATUSES,
    TEAM_GENERATED_MARKER, TEAM_MODEL_ALIASES, _MUTATION_LOCK, log,
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
    """Alias de modèle du frontmatter : override par agent, puis
    `default_model` de l'override, puis `model` de l'agent, puis
    `models.default` du manifeste, puis `sonnet`."""
    overrides = overrides or {}
    per_agent = overrides.get("models") or {}
    for cand in (per_agent.get(agent.get("id")), overrides.get("default_model"),
                 agent.get("model"), (manifest.get("models") or {}).get("default")):
        if isinstance(cand, str) and cand in TEAM_MODEL_ALIASES:
            return cand
    return "sonnet"


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
    model, tools (liste)."""
    desc = str(agent.get("description") or "").strip()
    role = str(agent.get("role") or "").strip()
    model = _effective_model(agent, manifest, overrides)
    usage = ((manifest.get("models") or {}).get(model) or {}).get("usage") if model != "haiku" else None
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
    head = (
        "---\n"
        f"name: {fm['name']}\n"
        f"description: \"{desc}\"\n"
        f"model: {fm['model']}\n"
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
    manifest = load_manifest(ws_dir)
    if manifest is None:
        skipped.append({"path": MANIFEST_REL.as_posix(), "reason": "manifeste absent ou illisible"})
        return {"generated": generated, "skipped": skipped, "prefix": None}

    prefix = effective_prefix(manifest, vars, opts["prefix"])
    # Les corps sont rendus avec le préfixe comme `{{name}}` (noms d'agents
    # dans la règle de délégation, mentions dans le corps).
    vars = {**vars, "name": prefix}
    with _MUTATION_LOCK:
        try:
            _persist_prefix(ws_dir, prefix)
        except CorruptJsonError as e:
            skipped.append({"path": MANIFEST_REL.as_posix(), "reason": f"manifeste corrompu : {e}"})
        for agent in manifest_agents(manifest):
            src_rel = str(agent.get("file") or f"team/agents/{agent['id']}.md")
            src = _claude_path(ws_dir, src_rel)
            target = ws_dir / AGENTS_DIR_REL / f"{_agent_name(agent, vars)}.md"
            rel = target.relative_to(ws_dir).as_posix()
            if src is None:
                skipped.append({"path": rel, "reason": f"corps source hors de .claude refusé : {src_rel}"})
                continue
            try:
                body = src.read_text(encoding="utf-8")
            except OSError:
                skipped.append({"path": rel, "reason": f"corps source absent : .claude/{src_rel}"})
                continue
            if target.exists():
                if not opts["regenerate"]:
                    skipped.append({"path": rel, "reason": "already present"})
                    continue
                try:
                    existing = target.read_text(encoding="utf-8")
                except OSError:
                    existing = ""
                if not _is_generated(existing):
                    skipped.append({"path": rel, "reason": "édité à la main (marqueur généré absent)"})
                    continue
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(render_agent(agent, manifest, vars, body, opts), encoding="utf-8")
                generated.append(rel)
            except OSError as e:
                log.warning("génération agent %s : %s", target, e)
                skipped.append({"path": rel, "reason": f"write error: {e}"})
    return {"generated": generated, "skipped": skipped, "prefix": prefix}


# --- État (routes GET) ----------------------------------------------------------

def _evals_unlocked(ws_dir: Path) -> bool:
    local = read_json(ws_dir / ".claude" / "settings.local.json", {})
    return isinstance(local, dict) and local.get("evals_unlocked") is True


def _count_jsonl(path: Path) -> int:
    try:
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    except OSError:
        return 0


def team_state(ws_id: str) -> tuple[int, dict]:
    """Manifeste + agents (générés ou non, modèle effectif, outils) + verrou."""
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
    agents = []
    for a in manifest_agents(manifest):
        fm = agent_frontmatter(a, manifest, vars)
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
            "read_only": bool(a.get("read_only")), "name": fm["name"],
            "path": target.relative_to(ws_dir).as_posix(),
            "generated": present, "generated_by_nebula": generated_by_nebula,
            # Routage always-on (couche 2) : None = non déclaré (manifeste
            # d'avant le routage), True / False sinon.
            "auto": agent_auto(a), "triggers": agent_triggers(a),
        })
    loop = manifest.get("improvement_loop") or {}
    return 200, {
        "active": True,
        "manifest": {"team": manifest.get("team") or {}, "models": manifest.get("models") or {},
                     "improvement_loop": loop},
        "agents": agents,
        "prefix": prefix,
        "routing": routing_state(manifest),
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
        })
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
    return 200, {
        "active": manifest is not None,
        "journal": journal,
        "invalid_lines": invalid,
        "config_hash": config_hash,
        "baseline_current": baseline_current,
        "baseline_version": last_entry["config_version"] if last_entry else None,
        "pending": pending_info,
        "stats": {"iterations": len(by_iter), "accepted": accepted, "rejected": rejected,
                  "pending": len(pending_entries),
                  "last_score": last_score, "scores": scores,
                  "consecutive_rejects": streak},
        "loop": {k: loop.get(k) for k in ("accept_if", "max_iterations",
                                           "stop_after_consecutive_rejects", "runs_per_eval")},
        "evals": {
            "locked": bool(loop.get("eval_set_locked")),
            "unlocked": _evals_unlocked(ws_dir),
            "cases": _count_jsonl(eval_p) if eval_p else 0,
            "holdout_cases": _count_jsonl(holdout_p) if holdout_p else 0,
        },
        "registers": registers,
    }
