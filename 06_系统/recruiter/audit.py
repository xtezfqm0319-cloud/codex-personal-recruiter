from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def today() -> str:
    return datetime.now().astimezone().date().isoformat()


def log_action(root: Path, action: str, **details: Any) -> None:
    path = root / "07_运行记录" / "actions.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"time": now_iso(), "action": action, **details}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def log_error(root: Path, action: str, error: str, **details: Any) -> None:
    path = root / "07_运行记录" / "errors.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"time": now_iso(), "action": action, "error": error, **details}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def add_pending(root: Path, kind: str, subject: str, reason: str, action: str) -> str:
    pending_id = "PENDING-" + datetime.now().strftime("%Y%m%d%H%M%S%f")
    path = root / "04_全局索引" / "待确认事项.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("# 待确认事项\n", encoding="utf-8")
    block = (
        f"\n## {pending_id}｜{kind}\n\n"
        f"- 对象：{subject}\n"
        f"- 原因：{reason}\n"
        f"- 待执行动作：{action}\n"
        f"- 状态：待确认\n"
    )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(block)
    log_action(root, "pending.created", pending_id=pending_id, kind=kind, subject=subject)
    return pending_id


def resolve_pending(root: Path, kind: str, subject: str, resolution: str, required_text: str = "") -> str | None:
    path = root / "04_全局索引" / "待确认事项.md"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    blocks = list(re.finditer(r"(?m)^## (PENDING-[^｜\n]+)｜([^\n]+)\n.*?(?=^## |\Z)", text, re.DOTALL))
    for match in reversed(blocks):
        pending_id, pending_kind = match.group(1), match.group(2).strip()
        block = match.group(0)
        if (
            pending_kind != kind
            or f"- 对象：{subject}\n" not in block
            or "- 状态：待确认" not in block
            or (required_text and required_text not in block)
        ):
            continue
        resolved = block.replace(
            "- 状态：待确认",
            f"- 状态：已确认并执行\n- 处理结果：{resolution}",
            1,
        )
        path.write_text(text[: match.start()] + resolved + text[match.end() :], encoding="utf-8")
        log_action(root, "pending.resolved", pending_id=pending_id, kind=kind, subject=subject, resolution=resolution)
        return pending_id
    return None
