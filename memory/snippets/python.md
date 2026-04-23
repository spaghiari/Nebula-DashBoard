# Snippets — Python

## CLI avec argparse
```python
#!/usr/bin/env python3
"""Template CLI minimal."""
from __future__ import annotations
import argparse
import logging
import sys
from pathlib import Path

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Description")
    p.add_argument("input", type=Path, help="Fichier d'entrée")
    p.add_argument("-o", "--output", type=Path, default=Path("out.txt"))
    p.add_argument("-v", "--verbose", action="store_true")
    return p

def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    if not args.input.exists():
        logging.error("Fichier introuvable : %s", args.input)
        return 2
    # ... traitement ...
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

## Appel API REST avec retry
```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def make_session(total: int = 3) -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=total,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "POST", "PUT", "DELETE"),
    )
    s.mount("http://", HTTPAdapter(max_retries=retry))
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s

session = make_session()
r = session.get("https://api.exemple.com/v1/items", timeout=10)
r.raise_for_status()
data = r.json()
```

## Lecture / écriture JSON typée
```python
import json
from pathlib import Path
from typing import Any

def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path: Path, data: Any) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
```

## Logger par module
```python
import logging
log = logging.getLogger(__name__)
# Puis : log.info("..."), log.warning("...")
```
