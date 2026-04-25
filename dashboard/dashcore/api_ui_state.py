"""État UI persisté côté serveur (thème, onboarding…)."""
from __future__ import annotations

import json
import threading
from dashcore.config import DASHBOARD_DIR, log

UI_STATE_FILE = DASHBOARD_DIR / "data" / "ui_state.json"
_DEFAULTS: dict = {"theme": "atelier", "onboarded": False}
_ALLOWED_KEYS = frozenset(_DEFAULTS)
_lock = threading.RLock()


def _read() -> dict:
    try:
        if UI_STATE_FILE.exists():
            data = json.loads(UI_STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {**_DEFAULTS, **{k: v for k, v in data.items() if k in _ALLOWED_KEYS}}
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
