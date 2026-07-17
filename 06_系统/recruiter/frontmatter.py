from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def read_markdown(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    data = yaml.safe_load(text[4:end]) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Invalid frontmatter mapping: {path}")
    body = text[end + 5 :]
    if body.startswith("\n"):
        body = body[1:]
    return data, body


def write_markdown(path: Path, data: dict[str, Any], body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = yaml.safe_dump(data, allow_unicode=True, sort_keys=False).strip()
    path.write_text(f"---\n{header}\n---\n\n{body.lstrip()}", encoding="utf-8")


def update_frontmatter(path: Path, **changes: Any) -> dict[str, Any]:
    data, body = read_markdown(path)
    data.update(changes)
    write_markdown(path, data, body)
    return data
