from __future__ import annotations

import csv
import re
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
        constraint_status = data.get("hard_constraint_status", "未验证")
        if recommendation in {"强推", "推"} and constraint_status == "不符合":
            issues.append(ValidationIssue("ERROR", "HARD_CONSTRAINT_RULE", str(overview.relative_to(root)), "候选人明确不符合已确认硬性条件但仍被建议推进"))
        if recommendation in {"强推", "推"} and constraint_status == "存在经确认例外" and not str(data.get("exception_reason", "")).strip():
            issues.append(ValidationIssue("ERROR", "MISSING_EXCEPTION", str(overview.relative_to(root)), "硬性条件例外缺少具体理由"))
        if recommendation not in {None, "", "待分析"} and not str(data.get("resume_evidence", "")).strip():
            issues.append(ValidationIssue("ERROR", "MISSING_EVIDENCE", str(overview.relative_to(root)), "AI简历判断缺少证据"))
        archive_summary = data.get("archive_summary")
        if archive_summary:
            summary_path = root / str(archive_summary)
            if not summary_path.exists():
                issues.append(ValidationIssue("ERROR", "MISSING_ARCHIVE_SUMMARY", str(overview.relative_to(root)), "归档候选人缺少归档摘要"))
            else:
                summary_text = summary_path.read_text(encoding="utf-8")
                for heading in ("## 一、人工正式结果", "## 二、能力判断与结果边界", "## 三、未来复用判断", "## 七、输入材料与追溯"):
                    if heading not in summary_text:
                        issues.append(
                            ValidationIssue(
                                "ERROR",
                                "ARCHIVE_SUMMARY_STRUCTURE",
                                str(summary_path.relative_to(root)),
                                f"缺少归档判断字段：{heading}",
                            )
                        )

    for report in (root / "02_岗位").glob("*/候选人/*/02_面试/*/面试报告.md"):
        raw = [p for p in report.parent.glob("原始纪要.*") if "提取文本" not in p.name]
        if not raw:
            issues.append(ValidationIssue("ERROR", "MISSING_INTERVIEW_RAW", str(report.relative_to(root)), "面试报告缺少原始纪要"))
        text = report.read_text(encoding="utf-8")
        heading_groups = (
            ("## 面试官评价（忠实提取）", "## 二、面试官评价（忠实提取）"),
            ("## 人工正式结论", "## 十一、人工正式结论"),
            ("## 输入追溯", "## 十二、输入追溯"),
        )
        for alternatives in heading_groups:
            if not any(heading in text for heading in alternatives):
                issues.append(ValidationIssue("ERROR", "INTERVIEW_STRUCTURE", str(report.relative_to(root)), f"缺少分层字段：{alternatives[-1]}"))
        if not any(heading in text for heading in ("## AI 独立分析", "## Codex 独立分析", "## 五、AI 独立分析")):
            issues.append(ValidationIssue("ERROR", "INTERVIEW_STRUCTURE", str(report.relative_to(root)), "缺少分层字段：## AI 独立分析"))

    for brief in (root / "02_岗位").glob("*/候选人/*/03_终面/终面简报.md"):
        text = brief.read_text(encoding="utf-8")
        required_headings = (
            "## 一、一页决策摘要",
            "## 二、岗位决策证据表",
            "## 六、材料冲突与可信度",
            "## 七、岗位胜任、证据可信度与录用可行性",
            "## 八、终面决定性问题",
            "## 十一、人工正式结论与分歧",
            "## 十四、输入材料与追溯",
        )
        for heading in required_headings:
            if heading not in text:
                issues.append(
                    ValidationIssue(
                        "ERROR",
                        "FINAL_BRIEF_STRUCTURE",
                        str(brief.relative_to(root)),
                        f"缺少终面决策字段：{heading}",
                    )
                )
        if "不替代人工最终录用决定" not in text and "不替代最终录用决定" not in text:
            issues.append(
                ValidationIssue(
                    "ERROR",
                    "FINAL_BRIEF_BOUNDARY",
                    str(brief.relative_to(root)),
                    "终面简报缺少人工最终录用决定边界",
                )
            )

    preference_path = root / "00_公司认知" / "个人招聘判断偏好.md"
    if preference_path.exists():
        try:
            preference_data, preference_body = read_markdown(preference_path)
            confirmed_entries = list(
                re.finditer(r"(?m)^### (PREF-[^\n]+)\n(.*?)(?=^### |^## |\Z)", preference_body, re.DOTALL)
            )
            required_fields = (
                "状态",
                "类型",
                "适用范围",
                "完整规则",
                "影响环节",
                "证据要求",
                "例外与不适用情形",
                "已知反例",
                "不得进一步推出",
                "来源案例与用户原话",
                "确认日期",
            )
            for entry in confirmed_entries:
                entry_id, block = entry.group(1), entry.group(2)
                for field in required_fields:
                    if f"- {field}：" not in block:
                        issues.append(
                            ValidationIssue(
                                "ERROR",
                                "PREFERENCE_STRUCTURE",
                                str(preference_path.relative_to(root)),
                                f"{entry_id} 缺少字段：{field}",
                            )
                        )
            recorded_count = int(preference_data.get("confirmed_recruiting_preferences") or 0)
            if recorded_count != len(confirmed_entries):
                issues.append(
                    ValidationIssue(
                        "ERROR",
                        "PREFERENCE_COUNT",
                        str(preference_path.relative_to(root)),
                        f"frontmatter 记录 {recorded_count} 条，实际结构化偏好 {len(confirmed_entries)} 条",
                    )
                )
        except Exception as exc:
            issues.append(ValidationIssue("ERROR", "PREFERENCE_FILE", str(preference_path.relative_to(root)), str(exc)))

    calibration_path = root / "04_全局索引" / "首次招聘判断校准.md"
    if calibration_path.exists():
        try:
            calibration_data, calibration_body = read_markdown(calibration_path)
            status = str(calibration_data.get("status", ""))
            if status not in {"进行中", "已暂停", "待确认", "已完成"}:
                issues.append(
                    ValidationIssue("ERROR", "CALIBRATION_STATUS", str(calibration_path.relative_to(root)), f"无效状态：{status}")
                )
            for heading in (
                "## 一、校准进度",
                "## 二、逐题记录",
                "## 三、初步规则候选",
                "## 四、待观察倾向",
                "## 五、明确不作推断",
                "## 六、效果预演",
                "## 七、确认结果",
            ):
                if heading not in calibration_body:
                    issues.append(
                        ValidationIssue("ERROR", "CALIBRATION_STRUCTURE", str(calibration_path.relative_to(root)), f"缺少校准字段：{heading}")
                    )
            type_to_field = {
                "核心问题": "core_questions_answered",
                "针对性追问": "followups_answered",
                "反向验证": "reverse_checks_answered",
            }
            for question_type, field in type_to_field.items():
                actual = len(re.findall(rf"(?m)^- 类型：{re.escape(question_type)}\s*$", calibration_body))
                recorded = int(calibration_data.get(field) or 0)
                if actual != recorded:
                    issues.append(
                        ValidationIssue(
                            "ERROR",
                            "CALIBRATION_COUNT",
                            str(calibration_path.relative_to(root)),
                            f"{question_type}记录 {recorded} 条，实际 {actual} 条",
                        )
                    )
            if int(calibration_data.get("followups_answered") or 0) > 2:
                issues.append(ValidationIssue("ERROR", "CALIBRATION_LIMIT", str(calibration_path.relative_to(root)), "针对性追问超过 2 题"))
            if int(calibration_data.get("reverse_checks_answered") or 0) > 1:
                issues.append(ValidationIssue("ERROR", "CALIBRATION_LIMIT", str(calibration_path.relative_to(root)), "反向验证超过 1 题"))
            if status in {"待确认", "已完成"}:
                placeholders = ("待完成对话后生成", "待完成对话后用模拟候选人")
                if any(placeholder in calibration_body for placeholder in placeholders):
                    issues.append(ValidationIssue("ERROR", "CALIBRATION_INCOMPLETE", str(calibration_path.relative_to(root)), "待确认或已完成校准仍包含未生成内容"))
        except Exception as exc:
            issues.append(ValidationIssue("ERROR", "CALIBRATION_FILE", str(calibration_path.relative_to(root)), str(exc)))

    daily_brief = root / "04_全局索引" / "今日招聘简报.md"
    if daily_brief.exists():
        daily_text = daily_brief.read_text(encoding="utf-8")
        for heading in (
            "## 一句话结论",
            "## 一、现在最值得关注的事",
            "## 二、只等你决定",
            "## 三、AI 可以直接继续",
            "## 四、等待外部信息",
            "## 五、岗位注意力概览",
            "## 六、可以放心稍后处理",
            "## 七、事实边界与信息来源",
        ):
            if heading not in daily_text:
                issues.append(
                    ValidationIssue(
                        "ERROR",
                        "DAILY_BRIEF_STRUCTURE",
                        str(daily_brief.relative_to(root)),
                        f"缺少今日简报字段：{heading}",
                    )
                )

    index = root / "04_全局索引" / "全部候选人.csv"
    if index.exists():
        with index.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("path") and not (root / row["path"]).exists():
                    issues.append(ValidationIssue("ERROR", "BROKEN_INDEX", str(index.relative_to(root)), f"失效路径：{row['path']}"))
    else:
        issues.append(ValidationIssue("WARNING", "MISSING_INDEX", str(index.relative_to(root)), "尚未生成候选人索引"))
    return issues
