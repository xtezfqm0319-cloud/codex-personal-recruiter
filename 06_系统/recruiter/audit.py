from __future__ import annotations

import json
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
