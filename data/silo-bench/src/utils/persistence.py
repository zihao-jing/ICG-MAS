"""JSON/JSONL I/O using srsly."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import srsly


def read_json(path: str | Path) -> Any:
    """Read a JSON file and return its contents."""
    return srsly.read_json(str(path))


def write_json(path: str | Path, data: Any) -> None:
    """Write data to a JSON file, creating parent directories as needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    srsly.write_json(str(path), data)


def append_jsonl(path: str | Path, data: dict[str, Any]) -> None:
    """Append a single JSON object as a line to a JSONL file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(srsly.json_dumps(data) + "\n")


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    """Read all lines from a JSONL file."""
    path = Path(path)
    if not path.exists():
        return []
    return list(srsly.read_jsonl(str(path)))
