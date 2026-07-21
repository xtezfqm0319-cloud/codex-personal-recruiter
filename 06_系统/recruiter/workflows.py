from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Iterable

from .audit import add_pending, log_action, resolve_pending, today
from .files import (
    SUPPORTED,
    TextExtractionIncompleteError,
    extract_text,
    extract_text_with_report,
    extraction_report_markdown,
    first_match,
    move_unique,
    safe_name,
    sha256,
)
from .frontmatter import read_markdown, update_frontmatter, write_markdown


RECOMMENDATIONS = ("强推", "推", "建议待定", "建议淘汰")
HARD_CONSTRAINT_STATUSES = ("符合", "存在经确认例外", "不符合", "未验证", "不适用")


def _replace_section(body: str, heading: str, content: str) -> str:
    pattern = rf"({re.escape(heading)}\n\n).*?(?=\n## |\Z)"
    return re.sub(pattern, lambda match: match.group(1) + content.strip() + "\n", body, flags=re.DOTALL)


def refresh_candidate_overview(path: Path) -> None:
    data, body = read_markdown(path)
    human_reason = str(data.get("human_decision_reason", "")).strip()
    reason_line = f"\n- 人工结论理由：{human_reason}" if human_reason else ""
    body = _replace_section(
        body,
        "## 一、当前状态",
        f"- 当前轮次：{data.get('current_stage', '未记录')}\n"
        f"- AI建议：{data.get('ai_recommendation', '待分析')}\n"
        f"- 人工结论：{data.get('human_decision', '待确认')}"
        f"{reason_line}\n"
        f"- 当前流程结论：{data.get('process_status', '推进中')}",
    )
    body = _replace_section(body, "## 三、简历阶段判断", str(data.get("resume_summary", "待 AI 分析。")))
    summaries = data.get("interview_summaries") or []
    interview_text = "\n".join(
        f"- 第{item.get('round')}轮：{item.get('ai_analysis')}（证据：{item.get('evidence')}；未验证：{item.get('unverified')}）"
        for item in sorted(summaries, key=lambda item: item.get("round", 0))
    ) or "暂无。"
    body = _replace_section(body, "## 四、历轮面试结论", interview_text)
    body = _replace_section(body, "## 五、当前主要优势", str(data.get("resume_evidence", "待分析。")))
    risks = f"- 风险：{data.get('resume_risk', '待分析。')}\n- 未验证：{data.get('resume_unverified', '待分析。')}"
    body = _replace_section(body, "## 六、当前风险与未验证项", risks)
    write_markdown(path, data, body)


def init_workspace(root: Path) -> None:
    directories = [
        "00_公司认知",
        "01_待处理/简历",
        "01_待处理/面试纪要",
        "01_待处理/待确认",
        "02_岗位",
        "03_简历库",
        "04_全局索引",
        "05_共享模板",
        "06_系统/cache",
        "07_运行记录",
    ]
    for directory in directories:
        (root / directory).mkdir(parents=True, exist_ok=True)
    log_action(root, "workspace.init")


def _next_id(paths: Iterable[Path], prefix: str, width: int) -> str:
    numbers: list[int] = []
    for path in paths:
        if not path.exists():
            continue
        try:
            data, _ = read_markdown(path)
        except Exception:
            continue
        value = str(data.get("position_id") or data.get("candidate_id") or "")
        match = re.search(r"(\d+)$", value)
        if match:
            numbers.append(int(match.group(1)))
    return f"{prefix}-{today()[:4]}-{max(numbers, default=0) + 1:0{width}d}"


def position_names(root: Path) -> list[str]:
    base = root / "02_岗位"
    return sorted(p.name for p in base.iterdir() if p.is_dir() and (p / "岗位.md").exists()) if base.exists() else []


def create_position(root: Path, name: str, jd_text: str, source_file: str | None = None, profile_text: str | None = None) -> Path:
    name = safe_name(name)
    target = root / "02_岗位" / name
    if (target / "岗位.md").exists():
        raise ValueError(f"Position already exists: {name}")
    target.mkdir(parents=True, exist_ok=True)
    (target / "候选人").mkdir()
    (target / "岗位校准").mkdir()
    position_id = _next_id((p / "岗位.md" for p in (root / "02_岗位").iterdir() if p.is_dir()), "POS", 3)
    data = {
        "position_id": position_id,
        "position_name": name,
        "status": "待校准",
        "created_at": today(),
        "updated_at": today(),
        "image_version": 1,
        "source_files": [source_file] if source_file else [],
    }
    profile = profile_text.strip() if profile_text else """### 岗位任务与预期结果

待 AI 助手与用户校准。

### 目标候选人类型

待 AI 助手与用户校准。

### 一票否决条件

待校准。

### 能力底线

待校准。

### 决定性排序因素

待校准。

### 加分项与风险信号

待校准。

### 取舍与经历替代规则

待校准。

### 关键经历和证据标准

待校准。

### 简历筛选规则

待校准。

### 面试重点验证

待校准。

### 现场任务建议

待校准。

### 可放宽条件

待校准。

### 已确认事实、工作假设、矛盾项与未验证项

待校准。"""
    body = f"""# {name}

## 一、JD

{jd_text.strip()}

## 二、岗位画像

{profile}

## 三、公司通用标准

本岗位继承 `00_公司认知/通用招聘标准.md`，不得在此静默修改。

## 四、待校准事项

{'- 暂无；岗位画像已随建岗确认。' if profile_text else '- 岗位画像各项需用户确认。'}

## 五、确认与变更记录

- {today()}：创建待校准版本。
"""
    write_markdown(target / "岗位.md", data, body)
    (target / "候选人总表.md").write_text("# 候选人总表\n\n暂无候选人。\n", encoding="utf-8")
    (target / "已结束候选人索引.md").write_text("# 已结束候选人索引\n", encoding="utf-8")
    log_action(root, "position.created", position=name, position_id=position_id)
    matches = search_history(root, name, name)
    scan_lines = ["# 建岗历史人才扫描", "", f"- 扫描日期：{today()}", f"- 关键词：{name}", f"- 命中：{len(matches)}", ""]
    for item in matches:
        scan_lines.append(f"- {item['name']}｜原岗位：{item['original_position']}｜结果：{item['final_result']}｜`{item['path']}`")
    if not matches:
        scan_lines.append("- 暂无关键词命中；AI 助手可按岗位画像补充语义检索。")
    (target / "建岗历史人才扫描.md").write_text("\n".join(scan_lines) + "\n", encoding="utf-8")
    return target


def _infer_position(text: str, filename: str, positions: list[str]) -> str | None:
    hits = [name for name in positions if name.lower() in f"{filename}\n{text}".lower()]
    return hits[0] if len(hits) == 1 else None


def _infer_name(text: str, filename: str) -> str | None:
    explicit = first_match(
        [r"^(?:姓名|候选人)\s*[:：]\s*([^\s,，|｜]{2,20})", r"^Name\s*[:：]\s*([^\n,]{2,40})"],
        text,
    )
    if explicit:
        return safe_name(explicit)
    stem = Path(filename).stem
    token = re.split(r"[-_—｜|]", stem)[0].strip()
    token = re.sub(r"^(简历|面试纪要|候选人)", "", token).strip()
    if 2 <= len(token) <= 20 and not re.search(r"\d{4,}", token):
        return safe_name(token)
    return None


def _candidate_overview(root: Path, position: str, name: str, resume: Path, digest: str) -> Path:
    all_overviews = list((root / "02_岗位").glob("*/候选人/*/00_候选人总览.md"))
    all_overviews += list((root / "03_简历库").glob("*/*/00_候选人总览.md"))
    candidate_id = _next_id(all_overviews, "CAN", 4)
    data = {
        "candidate_id": candidate_id,
        "name": name,
        "position": position,
        "source": "待补充",
        "current_stage": "待业务筛选",
        "ai_recommendation": "待分析",
        "human_decision": "待确认",
        "human_decision_reason": "",
        "process_status": "推进中",
        "reusable": False,
        "hard_constraint_status": "未验证",
        "created_at": today(),
        "updated_at": today(),
        "source_files": [{"path": str(resume.relative_to(root)), "sha256": digest}],
    }
    body = f"""# {name}｜候选人总览

## 一、当前状态

- 当前轮次：待业务筛选
- AI建议：待分析
- 人工结论：待确认
- 当前流程结论：推进中

## 二、基本信息

- 姓名：{name}
- 目标岗位：{position}

## 三、简历阶段判断

待 AI 分析。

## 四、历轮面试结论

暂无。

## 五、当前主要优势

待分析。

## 六、当前风险与未验证项

- 岗位硬性条件和其他关键事实待核验。

## 七、重要变更记录

- {today()}：从待处理区建档。
"""
    overview = resume.parent / "00_候选人总览.md"
    write_markdown(overview, data, body)
    return overview


def ingest_resumes(root: Path) -> list[dict[str, str]]:
    inbox = root / "01_待处理" / "简历"
    positions = position_names(root)
    results: list[dict[str, str]] = []
    for source in sorted(p for p in inbox.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED):
        try:
            extraction = extract_text_with_report(source)
            text = extraction.text
            name = _infer_name(text, source.name)
            position = _infer_position(text, source.name, positions)
            if not name or not position:
                reason = "无法唯一识别" + ("候选人姓名" if not name else "目标岗位")
                moved = move_unique(source, root / "01_待处理" / "待确认" / source.name)
                digest = sha256(moved)
                quality_report = moved.with_name(f"{moved.stem}-文本提取质量.md")
                quality_report.write_text(
                    extraction_report_markdown(extraction.report, str(moved.relative_to(root)), digest),
                    encoding="utf-8",
                )
                pending = add_pending(
                    root,
                    "待处理简历匹配",
                    source.name,
                    reason,
                    f"确认后移动并建档；当前文件：{moved.relative_to(root)}；质量报告：{quality_report.relative_to(root)}",
                )
                results.append(
                    {
                        "file": source.name,
                        "status": "待确认",
                        "pending_id": pending,
                        "quality_report": str(quality_report.relative_to(root)),
                    }
                )
                continue
            candidate_dir = root / "02_岗位" / position / "候选人" / name
            overview = candidate_dir / "00_候选人总览.md"
            if overview.exists():
                data, _ = read_markdown(overview)
                if data.get("human_decision") != "待确认":
                    moved = move_unique(source, root / "01_待处理" / "待确认" / source.name)
                    digest = sha256(moved)
                    quality_report = moved.with_name(f"{moved.stem}-文本提取质量.md")
                    quality_report.write_text(
                        extraction_report_markdown(extraction.report, str(moved.relative_to(root)), digest),
                        encoding="utf-8",
                    )
                    pending = add_pending(
                        root,
                        "新版简历",
                        f"{name}｜{position}",
                        "候选人已有人工确认结论，新版简历不得自动改变结论",
                        f"人工确认如何处理 {moved.relative_to(root)}；质量报告：{quality_report.relative_to(root)}",
                    )
                    results.append(
                        {
                            "file": source.name,
                            "status": "待确认",
                            "pending_id": pending,
                            "quality_report": str(quality_report.relative_to(root)),
                        }
                    )
                    continue
            candidate_dir.mkdir(parents=True, exist_ok=True)
            canonical = candidate_dir / f"{name}-{position}{source.suffix.lower()}"
            moved = move_unique(source, canonical)
            digest = sha256(moved)
            extracted = candidate_dir / "原始简历提取文本.txt"
            extracted.write_text(text, encoding="utf-8")
            quality_report = candidate_dir / "原始简历提取质量.md"
            quality_report.write_text(
                extraction_report_markdown(extraction.report, str(moved.relative_to(root)), digest),
                encoding="utf-8",
            )
            if not overview.exists():
                _candidate_overview(root, position, name, moved, digest)
            analysis = candidate_dir / "01_简历分析.md"
            if not analysis.exists():
                analysis.write_text(
                    f"# {name}｜简历分析\n\n## 结论\n\n- AI 建议：待分析\n- 业务摘要：待 AI 分析。\n\n"
                    "## 与岗位匹配的证据\n\n待分析。\n\n## 主要风险\n\n待分析。\n\n"
                    "## 未验证项\n\n待分析。\n\n## 建议后续验证\n\n待分析。\n\n"
                    "## 相对位置\n\n待完成同岗位候选人比较。\n\n"
                    "## 已确认个人偏好的影响\n\n待分析；未经确认的偏好不得使用。\n\n"
                    f"## 输入追溯\n\n- 原始材料：`{moved.relative_to(root)}`\n- SHA-256：`{digest}`\n",
                    encoding="utf-8",
                )
            log_action(
                root,
                "resume.ingested",
                candidate=name,
                position=position,
                path=str(moved.relative_to(root)),
                sha256=digest,
                extraction_method=extraction.report.method,
                extraction_status=extraction.report.status,
                ocr_pages=list(extraction.report.ocr_pages),
                unresolved_pages=list(extraction.report.unresolved_pages),
            )
            results.append(
                {
                    "file": source.name,
                    "status": "已建档",
                    "candidate": name,
                    "position": position,
                    "extraction": extraction.report.method,
                    "quality": extraction.report.status,
                }
            )
        except TextExtractionIncompleteError as exc:
            moved = move_unique(source, root / "01_待处理" / "待确认" / source.name)
            digest = sha256(moved)
            quality_report = moved.with_name(f"{moved.stem}-文本提取质量.md")
            quality_report.write_text(
                extraction_report_markdown(exc.report, str(moved.relative_to(root)), digest),
                encoding="utf-8",
            )
            pending = add_pending(
                root,
                "简历文本完整度待确认",
                source.name,
                str(exc),
                f"检查原文件与质量报告：{quality_report.relative_to(root)}",
            )
            results.append(
                {
                    "file": source.name,
                    "status": "待确认",
                    "pending_id": pending,
                    "quality_report": str(quality_report.relative_to(root)),
                }
            )
        except Exception as exc:
            moved = move_unique(source, root / "01_待处理" / "待确认" / source.name)
            pending = add_pending(root, "简历读取失败", source.name, str(exc), f"检查文件：{moved.relative_to(root)}")
            results.append({"file": source.name, "status": "待确认", "pending_id": pending})
    return results


def record_resume_analysis(
    root: Path,
    position: str,
    candidate: str,
    recommendation: str,
    summary: str,
    evidence: str,
    risk: str,
    unverified: str,
    hard_constraint_status: str,
    exception_reason: str = "",
    verification: str = "",
    preference_impact: str = "",
) -> Path:
    if recommendation not in RECOMMENDATIONS:
        raise ValueError(f"Recommendation must be one of: {', '.join(RECOMMENDATIONS)}")
    overview = root / "02_岗位" / position / "候选人" / candidate / "00_候选人总览.md"
    if not overview.exists():
        raise FileNotFoundError(overview)
    data, _ = read_markdown(overview)
    old = data.get("ai_recommendation", "待分析")
    if data.get("human_decision") != "待确认" and old not in {"待分析", recommendation}:
        add_pending(
            root,
            "新版材料改变已确认结论",
            f"{candidate}｜{position}",
            f"AI建议拟从“{old}”改为“{recommendation}”，但人工结论已确认",
            "复核新版材料；保持人工结论不变，确认后再更新 AI 建议",
        )
        raise PermissionError("Queued pending confirmation instead of changing an analyzed confirmed candidate")
    if hard_constraint_status not in HARD_CONSTRAINT_STATUSES:
        raise ValueError(f"Hard constraint status must be one of: {', '.join(HARD_CONSTRAINT_STATUSES)}")
    if hard_constraint_status == "不符合" and recommendation in {"强推", "推"}:
        raise ValueError("A candidate who fails a confirmed hard constraint cannot be recommended as 强推/推")
    if hard_constraint_status == "存在经确认例外" and recommendation in {"强推", "推"} and not exception_reason.strip():
        raise ValueError("A confirmed hard-constraint exception requires a concrete reason")
    candidate_dir = overview.parent
    sources = data.get("source_files") or []
    trace = "\n".join(f"- `{item.get('path')}`｜SHA-256 `{item.get('sha256')}`" for item in sources if isinstance(item, dict))
    body = f"""# {candidate}｜简历分析

## 结论

- AI 建议：{recommendation}
- 业务摘要：{summary}
- 硬性条件核验：{hard_constraint_status}
{f'- 例外理由：{exception_reason}' if exception_reason else ''}

## 与岗位匹配的证据

{evidence}

## 主要风险

{risk}

## 未验证项

{unverified}

## 建议后续验证

{verification.strip() or '- 围绕主要风险和未验证项追问，不把简历表述直接当作已验证能力。'}

## 相对位置

- 待在同岗位 `候选人比较.md` 中完成相对排序和取舍说明。

## 已确认个人偏好的影响

{preference_impact.strip() or '- 未使用个人偏好，仅按岗位画像和证据判断。'}

## 输入追溯

{trace or '- 未找到来源记录（需修复）'}
"""
    path = candidate_dir / "01_简历分析.md"
    path.write_text(body, encoding="utf-8")
    update_frontmatter(
        overview,
        ai_recommendation=recommendation,
        hard_constraint_status=hard_constraint_status,
        updated_at=today(),
        resume_summary=summary,
        resume_evidence=evidence,
        resume_risk=risk,
        resume_unverified=unverified,
        resume_verification=verification,
        preference_impact=preference_impact,
        exception_reason=exception_reason,
    )
    refresh_candidate_overview(overview)
    log_action(root, "resume.analysis_recorded", candidate=candidate, position=position, recommendation=recommendation)
    return path


def confirm_screening(
    root: Path,
    position: str,
    candidate: str,
    decision: str,
    reason: str = "",
    confirmed_change: bool = False,
) -> Path:
    allowed = {"推进", "待定", "淘汰"}
    if decision not in allowed:
        raise ValueError(f"Decision must be one of: {', '.join(sorted(allowed))}")
    overview = root / "02_岗位" / position / "候选人" / candidate / "00_候选人总览.md"
    if not overview.exists():
        raise FileNotFoundError(overview)
    data, _ = read_markdown(overview)
    current = str(data.get("human_decision", "待确认"))
    if current != "待确认" and current != decision:
        subject = f"{candidate}｜{position}"
        if not confirmed_change:
            reason_note = f"；用户理由：{reason.strip()}" if reason.strip() else ""
            add_pending(
                root,
                "修改人工候选人结论",
                subject,
                f"当前人工结论为“{current}”，拟改为“{decision}”{reason_note}",
                "获得明确确认后再修改正式结论",
            )
            raise PermissionError("Queued pending confirmation instead of overwriting human decision")
        pending_id = resolve_pending(
            root,
            "修改人工候选人结论",
            subject,
            f"人工结论已由“{current}”修改为“{decision}”",
            required_text=f"当前人工结论为“{current}”，拟改为“{decision}”",
        )
        if pending_id is None:
            raise PermissionError("No matching pending confirmation exists for this human-decision change")
    stage = "待安排面试" if decision == "推进" else ("筛选待定" if decision == "待定" else "初筛淘汰")
    updates = {"human_decision": decision, "current_stage": stage, "updated_at": today()}
    if reason.strip() or current != decision:
        updates["human_decision_reason"] = reason.strip()
    update_frontmatter(overview, **updates)
    refresh_candidate_overview(overview)
    action = "screening.decision_changed" if current not in {"待确认", decision} else "screening.confirmed"
    log_action(root, action, candidate=candidate, position=position, decision=decision, reason=reason.strip())
    if decision == "淘汰":
        return close_candidate(root, position, candidate, "初筛淘汰", reusable=False)
    return overview


def _round_number(text: str, filename: str) -> int | None:
    combined = f"{filename}\n{text[:500]}"
    chinese = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5}
    match = re.search(r"第?\s*([1-5一二三四五])\s*(?:轮|面)", combined)
    if not match:
        match = re.search(r"([一二三四五])面", combined)
    if not match:
        return None
    value = match.group(1)
    return int(value) if value.isdigit() else chinese[value]


def _active_candidates(root: Path) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for overview in (root / "02_岗位").glob("*/候选人/*/00_候选人总览.md"):
        data, _ = read_markdown(overview)
        found.append((str(data.get("position", overview.parents[2].name)), str(data.get("name", overview.parent.name))))
    return found


def ingest_interviews(root: Path) -> list[dict[str, str]]:
    inbox = root / "01_待处理" / "面试纪要"
    candidates = _active_candidates(root)
    results: list[dict[str, str]] = []
    for source in sorted(p for p in inbox.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED):
        try:
            extraction = extract_text_with_report(source)
            text = extraction.text
            pairs = [(position, name) for position, name in candidates if name in f"{source.name}\n{text}" and position in f"{source.name}\n{text}"]
            round_no = _round_number(text, source.name)
            if len(pairs) != 1 or round_no is None:
                moved = move_unique(source, root / "01_待处理" / "待确认" / source.name)
                digest = sha256(moved)
                quality_report = moved.with_name(f"{moved.stem}-文本提取质量.md")
                quality_report.write_text(
                    extraction_report_markdown(extraction.report, str(moved.relative_to(root)), digest),
                    encoding="utf-8",
                )
                reason = "无法唯一识别候选人、岗位或 1—5 轮面试轮次"
                pending = add_pending(
                    root,
                    "面试纪要匹配",
                    source.name,
                    reason,
                    f"确认后处理：{moved.relative_to(root)}；质量报告：{quality_report.relative_to(root)}",
                )
                results.append(
                    {
                        "file": source.name,
                        "status": "待确认",
                        "pending_id": pending,
                        "quality_report": str(quality_report.relative_to(root)),
                    }
                )
                continue
            position, candidate = pairs[0]
            folder = root / "02_岗位" / position / "候选人" / candidate / "02_面试" / f"{round_no:02d}_第{round_no}轮"
            folder.mkdir(parents=True, exist_ok=True)
            raw = move_unique(source, folder / f"原始纪要{source.suffix.lower()}")
            digest = sha256(raw)
            extracted = folder / "原始纪要提取文本.txt"
            extracted.write_text(text, encoding="utf-8")
            quality_report = folder / "原始纪要提取质量.md"
            quality_report.write_text(
                extraction_report_markdown(extraction.report, str(raw.relative_to(root)), digest),
                encoding="utf-8",
            )
            report = folder / "面试报告.md"
            if not report.exists():
                report.write_text(
                    f"# {candidate}｜第 {round_no} 轮面试报告\n\n## 面试官评价（忠实提取）\n\n待 AI 提取。\n\n"
                    "## AI 独立分析\n\n待分析。\n\n## 证据\n\n待分析。\n\n## 风险与未验证项\n\n待分析。\n\n"
                    "## 本轮改变了什么\n\n待分析。\n\n## AI 下一步倾向\n\n待分析。\n\n"
                    "## 人工正式结论\n\n待确认。\n\n## 输入追溯\n\n"
                    f"- 原始纪要：`{raw.relative_to(root)}`\n- SHA-256：`{digest}`\n",
                    encoding="utf-8",
                )
            overview = root / "02_岗位" / position / "候选人" / candidate / "00_候选人总览.md"
            data, _ = read_markdown(overview)
            sources = list(data.get("source_files") or [])
            sources.append({"path": str(raw.relative_to(root)), "sha256": digest})
            update_frontmatter(overview, current_stage=f"第{round_no}轮待分析", updated_at=today(), source_files=sources)
            refresh_candidate_overview(overview)
            log_action(
                root,
                "interview.ingested",
                candidate=candidate,
                position=position,
                round=round_no,
                sha256=digest,
                extraction_method=extraction.report.method,
                extraction_status=extraction.report.status,
                ocr_pages=list(extraction.report.ocr_pages),
                unresolved_pages=list(extraction.report.unresolved_pages),
            )
            results.append(
                {
                    "file": source.name,
                    "status": "已建档",
                    "candidate": candidate,
                    "position": position,
                    "round": str(round_no),
                    "extraction": extraction.report.method,
                    "quality": extraction.report.status,
                }
            )
        except TextExtractionIncompleteError as exc:
            moved = move_unique(source, root / "01_待处理" / "待确认" / source.name)
            digest = sha256(moved)
            quality_report = moved.with_name(f"{moved.stem}-文本提取质量.md")
            quality_report.write_text(
                extraction_report_markdown(exc.report, str(moved.relative_to(root)), digest),
                encoding="utf-8",
            )
            pending = add_pending(
                root,
                "面试纪要文本完整度待确认",
                source.name,
                str(exc),
                f"检查原文件与质量报告：{quality_report.relative_to(root)}",
            )
            results.append(
                {
                    "file": source.name,
                    "status": "待确认",
                    "pending_id": pending,
                    "quality_report": str(quality_report.relative_to(root)),
                }
            )
        except Exception as exc:
            moved = move_unique(source, root / "01_待处理" / "待确认" / source.name)
            pending = add_pending(root, "面试纪要读取失败", source.name, str(exc), f"检查文件：{moved.relative_to(root)}")
            results.append({"file": source.name, "status": "待确认", "pending_id": pending})
    return results


def record_interview_analysis(
    root: Path,
    position: str,
    candidate: str,
    round_no: int,
    interviewer_evaluation: str,
    ai_analysis: str,
    evidence: str,
    unverified: str,
) -> Path:
    if round_no not in range(1, 6):
        raise ValueError("Interview round must be 1—5")
    folder = root / "02_岗位" / position / "候选人" / candidate / "02_面试" / f"{round_no:02d}_第{round_no}轮"
    raws = [p for p in folder.glob("原始纪要.*") if "提取文本" not in p.name]
    if not raws:
        raise FileNotFoundError(f"No original interview notes in {folder}")
    raw = raws[0]
    digest = sha256(raw)
    body = f"""# {candidate}｜第 {round_no} 轮面试报告

## 面试官评价（忠实提取）

{interviewer_evaluation}

## AI 独立分析

{ai_analysis}

## 证据

{evidence}

## 风险与未验证项

{unverified}

## 本轮改变了什么

- 得到支持的判断：待 AI 助手根据本轮前假设和实际回答补充。
- 被削弱或推翻的判断：待 AI 助手补充。
- 最可能改变下一步倾向的未解决问题：{unverified}

## AI 下一步倾向

- 待 AI 助手基于本轮新增证据明确为推进、继续验证、暂缓或不建议推进，并说明理由。

## 人工正式结论

待确认。此处不得由 AI 助手替代用户写入。

## 输入追溯

- 原始纪要：`{raw.relative_to(root)}`
- SHA-256：`{digest}`
"""
    report = folder / "面试报告.md"
    report.write_text(body, encoding="utf-8")
    overview = root / "02_岗位" / position / "候选人" / candidate / "00_候选人总览.md"
    data, _ = read_markdown(overview)
    summaries = list(data.get("interview_summaries") or [])
    entry = {"round": round_no, "ai_analysis": ai_analysis, "evidence": evidence, "unverified": unverified}
    summaries = [item for item in summaries if item.get("round") != round_no] + [entry]
    update_frontmatter(overview, current_stage=f"第{round_no}轮已分析", updated_at=today(), interview_summaries=summaries)
    refresh_candidate_overview(overview)
    log_action(root, "interview.analysis_recorded", candidate=candidate, position=position, round=round_no)
    return report


def set_interview_decision(root: Path, position: str, candidate: str, round_no: int, decision: str) -> Path:
    overview = root / "02_岗位" / position / "候选人" / candidate / "00_候选人总览.md"
    data, _ = read_markdown(overview)
    current = data.get("interview_human_decisions", {}) or {}
    key = str(round_no)
    if key in current and current[key] != decision:
        add_pending(root, "修改人工面试结论", f"{candidate}｜{position}｜第{round_no}轮", f"当前为“{current[key]}”，拟改为“{decision}”", "用户确认后修改")
        raise PermissionError("Queued pending confirmation instead of overwriting interview decision")
    current[key] = decision
    update_frontmatter(overview, interview_human_decisions=current, current_stage=f"第{round_no}轮-{decision}", updated_at=today())
    refresh_candidate_overview(overview)
    report = root / "02_岗位" / position / "候选人" / candidate / "02_面试" / f"{round_no:02d}_第{round_no}轮" / "面试报告.md"
    text = report.read_text(encoding="utf-8")
    text = re.sub(r"(## 人工正式结论\n\n).*?(?=\n## 输入追溯)", rf"\1{decision}\n", text, flags=re.DOTALL)
    report.write_text(text, encoding="utf-8")
    log_action(root, "interview.decision_recorded", candidate=candidate, position=position, round=round_no, decision=decision)
    return report


def generate_final_brief(root: Path, position: str, candidate: str, hr_notes: str = "") -> Path:
    position_file = root / "02_岗位" / position / "岗位.md"
    candidate_dir = root / "02_岗位" / position / "候选人" / candidate
    overview_file = candidate_dir / "00_候选人总览.md"
    if not position_file.exists() or not overview_file.exists():
        raise FileNotFoundError("Position or active candidate does not exist")
    overview, _ = read_markdown(overview_file)
    reports = sorted(candidate_dir.glob("02_面试/*/面试报告.md"))
    preparations = sorted(candidate_dir.glob("02_面试/*/面试准备.md"))
    if not reports:
        raise ValueError("Final brief requires at least one interview report")
    evidence_sections = []
    for report in reports:
        evidence_sections.append(f"### {report.parent.name}\n\n来源：`{report.relative_to(root)}`\n\n{report.read_text(encoding='utf-8')}")
    sources = overview.get("source_files") or []
    source_list = "\n".join(f"- `{item.get('path')}`｜SHA-256 `{item.get('sha256')}`" for item in sources if isinstance(item, dict))
    brief_dir = candidate_dir / "03_终面"
    brief_dir.mkdir(parents=True, exist_ok=True)
    brief = brief_dir / "终面简报.md"
    body = f"""# {candidate}｜{position}｜终面前简报

## 一、结论摘要

- 倾向建议：待 AI 助手基于完整材料明确为“建议进入录用讨论 / 谨慎推进 / 继续验证 / 不建议推进”之一
- 三条决定性理由：待 AI 助手补充。
- 最大下行风险：{overview.get('resume_risk', '未记录')}
- 最可能改变当前倾向的新证据：{overview.get('resume_unverified', '未记录')}
- AI 简历建议：{overview.get('ai_recommendation', '未记录')}
- 人工筛选结论：{overview.get('human_decision', '未记录')}
- 当前阶段：{overview.get('current_stage', '未记录')}
- 简历业务摘要：{overview.get('resume_summary', '未记录')}

## 二、材料事实（按来源陈述）

- 候选人：{candidate}
- 岗位：{position}
- 硬性条件记录：{overview.get('hard_constraint_status', '未验证')}（该字段只表示当前材料判断，不等于后续核验已完成）
- 以上状态来自：`{overview_file.relative_to(root)}`；岗位标准来自：`{position_file.relative_to(root)}`。

## 三、岗位匹配判断

- 支持证据：{overview.get('resume_evidence', '未记录')}
- 风险：{overview.get('resume_risk', '未记录')}
- 说明：这是 AI 助手基于现有材料的判断，不是事实或录用结论。

## 四、历轮面试证据

{chr(10).join(evidence_sections)}

## 五、HR 补充信息

{hr_notes or '未提供。'}

## 六、材料冲突

- 当前未自动识别到结构化冲突；终面需核对各材料之间不一致的时间、职责边界和结果归因。

## 七、风险与未验证项

- {overview.get('resume_unverified', '未记录')}
- 面试报告中的“风险与未验证项”仍需终面逐项验证。

## 八、终面建议验证问题

- 请围绕关键经历的个人职责、决策依据、可量化结果和复盘追问。
- 请验证材料中尚未确认的任职时间、责任边界、团队规模和业绩归因。

## 九、倾向性判断

待 AI 助手根据全部证据给出清晰倾向。是否录用必须由人基于终面新增证据决定。本简报不替代最终录用决定。

## 十、已确认个人偏好的影响

- 来源：`00_公司认知/个人招聘判断偏好.md`
- 待 AI 助手说明具体使用了哪些已确认偏好；没有适用偏好时明确写“未使用”。

## 十一、输入材料清单

{source_list}
- `{position_file.relative_to(root)}`
- `{overview_file.relative_to(root)}`
{chr(10).join(f'- `{path.relative_to(root)}`' for path in preparations)}
"""
    brief.write_text(body.rstrip() + "\n", encoding="utf-8")
    update_frontmatter(overview_file, current_stage="终面待进行", updated_at=today(), final_brief=str(brief.relative_to(root)))
    refresh_candidate_overview(overview_file)
    log_action(root, "final_brief.generated", candidate=candidate, position=position, path=str(brief.relative_to(root)))
    return brief


def close_candidate(root: Path, position: str, candidate: str, result: str, reusable: bool = False) -> Path:
    active = root / "02_岗位" / position / "候选人" / candidate
    overview = active / "00_候选人总览.md"
    if not overview.exists():
        raise FileNotFoundError(overview)
    archive = root / "03_简历库" / position / candidate
    if archive.exists():
        pending = add_pending(root, "归档路径冲突", f"{candidate}｜{position}", f"目标已存在：{archive.relative_to(root)}", "人工确认合并策略，禁止覆盖原档案")
        raise FileExistsError(f"Archive exists; queued {pending}")
    data, _ = read_markdown(overview)
    old_prefix = str(active.relative_to(root))
    new_prefix = str(archive.relative_to(root))
    sources = []
    for item in data.get("source_files") or []:
        if isinstance(item, dict):
            item = dict(item)
            item["path"] = str(item.get("path", "")).replace(old_prefix, new_prefix, 1)
        sources.append(item)
    changes = {
        "current_stage": "流程结束",
        "process_status": "已结束",
        "final_result": result,
        "reusable": bool(reusable),
        "updated_at": today(),
        "source_files": sources,
    }
    if data.get("final_brief"):
        changes["final_brief"] = str(data["final_brief"]).replace(old_prefix, new_prefix, 1)
    update_frontmatter(overview, **changes)
    refresh_candidate_overview(overview)
    archive.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(active), str(archive))
    for generated in archive.rglob("*.md"):
        text = generated.read_text(encoding="utf-8")
        if old_prefix in text:
            generated.write_text(text.replace(old_prefix, new_prefix), encoding="utf-8")
    ended = root / "02_岗位" / position / "已结束候选人索引.md"
    with ended.open("a", encoding="utf-8") as handle:
        handle.write(f"\n- {today()}｜{candidate}｜{result}｜可复用：{'是' if reusable else '否'}｜`{archive.relative_to(root)}`\n")
    log_action(root, "candidate.archived", candidate=candidate, position=position, result=result, reusable=reusable, path=str(archive.relative_to(root)))
    return archive


def search_history(root: Path, query: str, position: str = "") -> list[dict[str, str]]:
    tokens = [item.lower() for item in re.split(r"\s+", query.strip()) if item]
    results: list[dict[str, str]] = []
    for overview in (root / "03_简历库").glob("*/*/00_候选人总览.md"):
        data, body = read_markdown(overview)
        haystack = f"{overview}\n{data}\n{body}".lower()
        matches = sum(token in haystack for token in tokens)
        reusable = bool(data.get("reusable"))
        if tokens and matches == 0:
            continue
        if position and position.lower() not in haystack and not reusable:
            continue
        results.append(
            {
                "name": str(data.get("name", overview.parent.name)),
                "original_position": str(data.get("position", overview.parents[1].name)),
                "final_result": str(data.get("final_result", "未记录")),
                "reusable": "是" if reusable else "否",
                "path": str(overview.relative_to(root)),
                "matches": str(matches),
            }
        )
    results.sort(key=lambda item: (item["reusable"] != "是", -int(item["matches"]), item["name"]))
    log_action(root, "history.searched", query=query, position=position, count=len(results))
    return results


def calibrate_position(root: Path, position: str) -> Path:
    records = []
    paths = list((root / "02_岗位" / position / "候选人").glob("*/00_候选人总览.md"))
    paths += list((root / "03_简历库" / position).glob("*/00_候选人总览.md"))
    for path in paths:
        data, _ = read_markdown(path)
        records.append(data)
    differences = [r for r in records if r.get("human_decision") not in {None, "待确认"} and r.get("ai_recommendation") not in {None, "待分析"}]
    rows = "\n".join(
        f"| {r.get('name')} | {r.get('ai_recommendation')} | {r.get('human_decision')} | {r.get('final_result', '进行中')} | {r.get('resume_risk', '未记录')} |"
        for r in differences
    ) or "| 暂无 | 暂无 | 暂无 | 暂无 | 样本不足 |"
    target = root / "02_岗位" / position / "岗位校准" / "当前校准建议.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        f"""# {position}｜岗位校准建议

生成日期：{today()}

## 样本对比

| 候选人 | AI筛选建议 | 人工结论 | 最终结果 | 初始风险 |
|---|---|---|---|---|
{rows}

## 观察

- 当前共有 {len(records)} 个候选人记录，{len(differences)} 个包含可对比的 AI 与人工结论。
- 应由 AI 助手结合原始证据判断分歧更可能来自画像、筛选标准、面试标准或个别案例，不从样本数量直接推导因果。

## 建议修改

- 待 AI 助手基于重复出现的通过、淘汰与分歧原因提出，并展示修改前后差异。

## 权限提示

本文件仅是建议。未经用户确认，不得修改正式 `岗位.md` 或增加 `image_version`。
""",
        encoding="utf-8",
    )
    log_action(root, "position.calibration_generated", position=position, records=len(records))
    return target
