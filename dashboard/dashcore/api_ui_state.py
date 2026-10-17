"""État UI persisté côté serveur (thème, onboarding…)."""
from __future__ import annotations

import json
import threading
from dashcore.config import UI_STATE_FILE, log

_DEFAULTS: dict = {"theme": "nebula", "onboarded": False, "claude_plan": "auto"}
_CLAUDE_PLANS = frozenset({"auto", "pro", "max", "api"})
_ALLOWED_KEYS = frozenset(_DEFAULTS)
_THEME_LEGACY = {"atelier": "nebula", "atelier-clair": "nebula-clair"}
_lock = threading.RLock()


def _read() -> dict:
    try:
        if UI_STATE_FILE.exists():
            data = json.loads(UI_STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                merged = {**_DEFAULTS, **{k: v for k, v in data.items() if k in _ALLOWED_KEYS}}
                # Migration douce : ancien thème "atelier*" → "nebula*"
                if merged.get("theme") in _THEME_LEGACY:
                    merged["theme"] = _THEME_LEGACY[merged["theme"]]
                if merged.get("claude_plan") not in _CLAUDE_PLANS:
                    merged["claude_plan"] = "auto"
                return merged
    except Exception:
        pass
    return dict(_DEFAULTS)


def _write(state: dict) -> None:
    UI_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    UI_STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_ui_state() -> tuple[int, dict]:
    with _lock:
        return 200, _read()


def patch_ui_state(patch: dict) -> tuple[int, dict]:
    if "claude_plan" in patch and patch["claude_plan"] not in _CLAUDE_PLANS:
        return 400, {"error": "claude_plan invalide (auto|pro|max|api)"}
    with _lock:
        state = _read()
        for k, v in patch.items():
            if k in _ALLOWED_KEYS:
                state[k] = v
        try:
            _write(state)
        except Exception as exc:
            log.error("patch_ui_state: %s", exc)
            return 500, {"error": str(exc)}
        return 200, {"ok": True, "state": state}
