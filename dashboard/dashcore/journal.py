"""Journal markdown — entrées datées dans memory/journal.md."""
from __future__ import annotations

import datetime as dt
import re

from dashcore.config import JOURNAL_FILE


JOURNAL_ENTRY = re.compile(r"^## (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\s*$", re.MULTILINE)


def read_journal() -> list[dict]:
    if not JOURNAL_FILE.exists():
        return []
    text = JOURNAL_FILE.read_text(encoding="utf-8")
    entries = []
    parts = JOURNAL_ENTRY.split(text)
    # parts = [preamble, ts1, body1, ts2, body2, ...]
    for i in range(1, len(parts), 2):
        ts = parts[i].strip()
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        entries.append({"ts": ts, "text": body})
    return entries


def append_journal(text: str) -> None:
    JOURNAL_FILE.parent.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().isoformat(timespec="seconds")
    header_needed = (
        not JOURNAL_FILE.exists()
        or not JOURNAL_FILE.read_text(encoding="utf-8").startswith("# Journal")
    )
    with JOURNAL_FILE.open("a", encoding="utf-8") as f:
        if header_needed:
            f.write("# Journal\n\n")
        f.write(f"## {ts}\n{text.strip()}\n\n")


def clear_journal() -> None:
    if JOURNAL_FILE.exists():
        JOURNAL_FILE.unlink()
