from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .files import sha256
from .frontmatter import read_markdown


@dataclass
class ValidationIssue:
    level: str
    code: str
    path: str
    message: str


def validate_workspace(root: Path) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    required = [
        "AGENTS.md",
        "00_公司认知/通用招聘标准.md",
        "00_公司认知/个人招聘判断偏好.md",
        "04_全局索引/待确认事项.md",
    ]
    for relative in required:
        if not (root / relative).exists():
            issues.append(ValidationIssue("ERROR", "MISSING_REQUIRED", relative, "缺少必需文件"))

    for position in (root / "02_岗位").iterdir() if (root / "02_岗位").exists() else []:
        if position.is_dir() and not (position / "岗位.md").exists():
            issues.append(ValidationIssue("ERROR", "MISSING_POSITION", str(position.relative_to(root)), "岗位目录缺少岗位.md"))

    overviews = list((root / "02_岗位").glob("*/候选人/*/00_候选人总览.md"))
    overviews += list((root / "03_简历库").glob("*/*/00_候选人总览.md"))
    for overview in overviews:
        try:
            data, _ = read_markdown(overview)
        except Exception as exc:
            issues.append(ValidationIssue("ERROR", "BAD_FRONTMATTER", str(overview.relative_to(root)), str(exc)))
            continue
        sources = data.get("source_files") or []
        resume_sources = [item for item in sources if isinstance(item, dict) and "面试" not in str(item.get("path", ""))]
        if not resume_sources:
            issues.append(ValidationIssue("ERROR", "MISSING_RESUME_SOURCE", str(overview.relative_to(root)), "候选人没有原始简历来源记录"))
        for item in sources:
            if isinstance(item, dict):
                source_path = root / str(item.get("path", ""))
                if not source_path.exists():
                    issues.append(ValidationIssue("ERROR", "BROKEN_SOURCE", str(overview.relative_to(root)), f"来源文件不存在：{item.get('path')}"))
                elif item.get("sha256") and sha256(source_path) != item.get("sha256"):
                    issues.append(ValidationIssue("ERROR", "SOURCE_HASH_MISMATCH", str(overview.relative_to(root)), f"原始材料哈希不一致：{item.get('path')}"))
        recommendation = data.get("ai_recommendation")
        tier = data.get("education_tier")
        if recommendation in {"强推", "推"} and tier not in {"985", "211"}:
            issues.append(ValidationIssue("ERROR", "EDUCATION_RULE", str(overview.relative_to(root)), "非985/211或未验证学历被建议推进"))
        if recommendation in {"强推", "推"} and tier == "211" and not str(data.get("exception_reason", "")).strip():
            issues.append(ValidationIssue("ERROR", "MISSING_EXCEPTION", str(overview.relative_to(root)), "211推进缺少破格理由"))
        if recommendation not in {None, "", "待分析"} and not str(data.get("resume_evidence", "")).strip():
            issues.append(ValidationIssue("ERROR", "MISSING_EVIDENCE", str(overview.relative_to(root)), "AI简历判断缺少证据"))

    for report in (root / "02_岗位").glob("*/候选人/*/02_面试/*/面试报告.md"):
        raw = [p for p in report.parent.glob("原始纪要.*") if "提取文本" not in p.name]
        if not raw:
            issues.append(ValidationIssue("ERROR", "MISSING_INTERVIEW_RAW", str(report.relative_to(root)), "面试报告缺少原始纪要"))
        text = report.read_text(encoding="utf-8")
        for heading in ("## 面试官评价（忠实提取）", "## Codex 独立分析", "## 人工正式结论", "## 输入追溯"):
            if heading not in text:
                issues.append(ValidationIssue("ERROR", "INTERVIEW_STRUCTURE", str(report.relative_to(root)), f"缺少分层字段：{heading}"))

    index = root / "04_全局索引" / "全部候选人.csv"
    if index.exists():
        with index.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("path") and not (root / row["path"]).exists():
                    issues.append(ValidationIssue("ERROR", "BROKEN_INDEX", str(index.relative_to(root)), f"失效路径：{row['path']}"))
    else:
        issues.append(ValidationIssue("WARNING", "MISSING_INDEX", str(index.relative_to(root)), "尚未生成候选人索引"))
    return issues
