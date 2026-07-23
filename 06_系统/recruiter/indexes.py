from __future__ import annotations

import csv
from pathlib import Path

from .audit import log_action
from .frontmatter import read_markdown


RANK = {"强推": 0, "推": 1, "建议待定": 2, "建议淘汰": 3, "待分析": 4}


def _candidate_records(root: Path) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    sources = [
        ("在岗", root / "02_岗位", "*/候选人/*/00_候选人总览.md"),
        ("已归档", root / "03_简历库", "*/*/00_候选人总览.md"),
    ]
    for location, base, pattern in sources:
        for path in base.glob(pattern):
            data, _ = read_markdown(path)
            records.append(
                {
                    "candidate_id": str(data.get("candidate_id", "")),
                    "name": str(data.get("name", path.parent.name)),
                    "position": str(data.get("position", "")),
                    "ai_recommendation": str(data.get("ai_recommendation", "")),
                    "human_decision": str(data.get("human_decision", "")),
                    "current_stage": str(data.get("current_stage", "")),
                    "process_status": str(data.get("process_status", "")),
                    "final_result": str(data.get("final_result", "")),
                    "reusable": "true" if data.get("reusable") else "false",
                    "reuse_level": str(data.get("reuse_level", "")),
                    "closure_category": str(data.get("closure_category", "")),
                    "closure_reason": str(data.get("closure_reason", "")),
                    "reuse_targets": str(data.get("reuse_targets", "")),
                    "summary": str(data.get("resume_summary", "")),
                    "risk": str(data.get("resume_risk", "")),
                    "location": location,
                    "path": str(path.relative_to(root)),
                }
            )
    return records


def _write_csv(path: Path, records: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)


def rebuild_indexes(root: Path) -> dict[str, int]:
    positions: list[dict[str, str]] = []
    for path in (root / "02_岗位").glob("*/岗位.md"):
        data, _ = read_markdown(path)
        positions.append(
            {
                "position_id": str(data.get("position_id", "")),
                "position_name": str(data.get("position_name", path.parent.name)),
                "status": str(data.get("status", "")),
                "updated_at": str(data.get("updated_at", "")),
                "path": str(path.relative_to(root)),
            }
        )
    positions.sort(key=lambda row: row["position_id"])
    candidates = _candidate_records(root)
    candidates.sort(key=lambda row: (row["position"], RANK.get(row["ai_recommendation"], 9), row["name"]))
    index_dir = root / "04_全局索引"
    _write_csv(index_dir / "岗位清单.csv", positions, ["position_id", "position_name", "status", "updated_at", "path"])
    candidate_fields = [
        "candidate_id",
        "name",
        "position",
        "ai_recommendation",
        "human_decision",
        "current_stage",
        "process_status",
        "final_result",
        "reusable",
        "reuse_level",
        "closure_category",
        "closure_reason",
        "reuse_targets",
        "summary",
        "risk",
        "location",
        "path",
    ]
    _write_csv(index_dir / "全部候选人.csv", candidates, candidate_fields)
    reusable = [row for row in candidates if row["reusable"] == "true"]
    _write_csv(index_dir / "可复用候选人.csv", reusable, candidate_fields)

    for position in {row["position"] for row in candidates if row["location"] == "在岗"}:
        rows = [row for row in candidates if row["position"] == position and row["location"] == "在岗"]
        position_dir = root / "02_岗位" / position
        _write_csv(position_dir / "候选人总表.csv", rows, candidate_fields)
        lines = [
            "# 候选人总表",
            "",
            "| 排序 | 姓名 | AI建议 | 人工结论 | 当前轮次 | 核心匹配点 | 主要风险 |",
            "|---:|---|---|---|---|---|---|",
        ]
        for rank, row in enumerate(rows, 1):
            clean = {key: row[key].replace("|", "｜").replace("\n", " ") for key in row}
            lines.append(
                f"| {rank} | {clean['name']} | {clean['ai_recommendation']} | {clean['human_decision']} | "
                f"{clean['current_stage']} | {clean['summary']} | {clean['risk']} |"
            )
        (position_dir / "候选人总表.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        pending_rows = [row for row in rows if row["human_decision"] == "待确认"]
        pending_lines = [
            "# 本批次待人工确认",
            "",
            "请明确给出每位候选人的人工结论：推进、待定或淘汰。AI 建议不会被人工结论覆盖。",
            "",
            "| 排序 | 姓名 | AI建议 | 业务摘要 | 主要风险 | 人工结论 |",
            "|---:|---|---|---|---|---|",
        ]
        for rank, row in enumerate(pending_rows, 1):
            clean = {key: row[key].replace("|", "｜").replace("\n", " ") for key in row}
            pending_lines.append(
                f"| {rank} | {clean['name']} | {clean['ai_recommendation']} | {clean['summary']} | {clean['risk']} | 待确认 |"
            )
        if not pending_rows:
            pending_lines.append("| - | 暂无 | - | - | - | - |")
        (position_dir / "本批次待人工确认.md").write_text("\n".join(pending_lines) + "\n", encoding="utf-8")

    log_action(root, "indexes.rebuilt", positions=len(positions), candidates=len(candidates), reusable=len(reusable))
    return {"positions": len(positions), "candidates": len(candidates), "reusable": len(reusable)}
