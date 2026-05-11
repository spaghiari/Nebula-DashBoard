"""Install / uninstall des hooks Reflexive dans .claude/settings.json d'un workspace.

Stratégie de coexistence : on ne touche jamais aux hooks tiers. Chaque hook
Reflexive est identifié par le marqueur `REFLEXIVE_HOOK_MARKER` placé dans le
champ `command`. À l'uninstall, seules les entrées portant ce marqueur sont
retirées ; si un bloc `matcher` ou un event devient vide, on le nettoie.

Backup `.bak` créé avant toute modification (cohérent avec `write_json`).
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from dashcore.config import ROOT, log, _MUTATION_LOCK

# Marqueur inséré dans le `command` pour reconnaître nos hooks à l'uninstall.
# (Préfixe inutile pour le shell, suffit qu'il apparaisse dans la string.)
REFLEXIVE_HOOK_MARKER = "# nebula-reflexive-hook"

HOOKS_DIR = ROOT / "dashboard" / "dashcore" / "reflexive" / "hooks"

# Mapping event Claude Code → script. Matcher utilisé pour PostToolUse.
HOOK_EVENTS: dict[str, tuple[str, str | None]] = {
    "SessionStart": ("load_context.py", None),
    "PostToolUse":  ("log_tool_use.py", ""),
    "Stop":         ("finalize_interaction.py", None),
}


def _python_exe() -> str:
    # On capture l'interpréteur qui fait tourner le dashboard : c'est celui
    # qui dispose de la stdlib qu'on utilise dans les hooks (rien d'externe,
    # donc tout python 3.10+ marche, mais autant pointer le bon).
    return sys.executable or "python"


def _build_command(script_name: str) -> str:
    script = HOOKS_DIR / script_name
    return f'"{_python_exe()}" "{script}" {REFLEXIVE_HOOK_MARKER}'


def _settings_path(workspace_path: str) -> Path:
    return Path(workspace_path) / ".claude" / "settings.json"


def _read_settings(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8")) or {}
    except json.JSONDecodeError as e:
        log.warning("settings.json illisible (%s) : %s", path, e)
        return {}


def _write_settings(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _is_reflexive_entry(entry: dict) -> bool:
    """Une entrée de la liste hooks. Vrai si tous ses sous-hooks sont à nous."""
    subs = entry.get("hooks") or []
    if not subs:
        return False
    return all(
        isinstance(h, dict)
        and REFLEXIVE_HOOK_MARKER in (h.get("command") or "")
        for h in subs
    )


def install_hooks(workspace_path: str) -> dict:
    """Idempotent. Renvoie un récap des actions."""
    sp = _settings_path(workspace_path)
    with _MUTATION_LOCK:
        data = _read_settings(sp)
        hooks = data.setdefault("hooks", {})
        added: list[str] = []

        for event, (script, matcher) in HOOK_EVENTS.items():
            entries = hooks.setdefault(event, [])
            command = _build_command(script)
            # Cherche une entrée Reflexive existante pour cet event
            existing = next(
                (e for e in entries if _is_reflexive_entry(e)),
                None,
            )
            if existing:
                # Met à jour la commande au cas où le chemin Nebula a bougé
                existing["hooks"] = [{"type": "command", "command": command}]
                if matcher is not None:
                    existing["matcher"] = matcher
                continue
            entry: dict = {"hooks": [{"type": "command", "command": command}]}
            if matcher is not None:
                entry["matcher"] = matcher
            entries.append(entry)
            added.append(event)

        _write_settings(sp, data)
    log.info("Reflexive hooks installés dans %s (ajoutés=%s)", sp, added)
    return {"settings_path": str(sp), "added_events": added}


def uninstall_hooks(workspace_path: str) -> dict:
    """Idempotent. Ne touche aux hooks tiers : seuls les nôtres sont retirés."""
    sp = _settings_path(workspace_path)
    if not sp.exists():
        return {"settings_path": str(sp), "removed_events": [], "noop": True}
    with _MUTATION_LOCK:
        data = _read_settings(sp)
        hooks = data.get("hooks") or {}
        removed: list[str] = []
        for event in list(hooks.keys()):
            before = hooks[event]
            after = [e for e in before if not _is_reflexive_entry(e)]
            if len(after) != len(before):
                removed.append(event)
            if after:
                hooks[event] = after
            else:
                del hooks[event]
        if not hooks and "hooks" in data:
            del data["hooks"]
        _write_settings(sp, data)
    log.info("Reflexive hooks retirés de %s (events=%s)", sp, removed)
    return {"settings_path": str(sp), "removed_events": removed}
