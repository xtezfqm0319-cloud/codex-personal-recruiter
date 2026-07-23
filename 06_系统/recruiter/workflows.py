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
INTERVIEW_INCLINATIONS = ("建议推进", "继续验证", "建议暂缓", "不建议推进")
REUSE_LEVELS = ("优先复用", "有条件复用", "暂不主动复用", "不建议复用")
PREFERENCE_TYPES = ("通用招聘判断", "岗位族专项", "交互偏好")
PREFERENCE_DECISIONS = ("确认", "拒绝")
CLOSURE_CATEGORIES = (
    "已录用",
    "能力或证据未达要求",
    "岗位匹配不佳",
    "候选人退出",
    "Offer 未接受",
    "HC、预算或业务变化",
    "时机、地点或条件不匹配",
    "诚信或材料可信度风险",
    "流程或信息不足",
    "其他已明确原因",
)


def _replace_section(body: str, heading: str, content: str) -> str:
    pattern = rf"({re.escape(heading)}\n\n).*?(?=\n## |\Z)"
    return re.sub(pattern, lambda match: match.group(1) + content.strip() + "\n", body, flags=re.DOTALL)


def _append_section_entry(body: str, heading: str, entry: str) -> str:
    marker = f"{heading}\n"
    if marker not in body:
        return body.rstrip() + f"\n\n{heading}\n\n{entry.strip()}\n"
    start = body.index(marker) + len(marker)
    next_heading = body.find("\n## ", start)
    end = len(body) if next_heading < 0 else next_heading
    current = body[start:end].rstrip()
    combined = f"{current}\n\n{entry.strip()}" if current else f"\n{entry.strip()}"
    return body[:start] + combined + "\n" + body[end:]


def _required(value: str, field: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field} must not be empty")
    return normalized


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
        f"- 第{item.get('round')}轮：{item.get('inclination', '未记录倾向')}｜{item.get('ai_analysis')}"
        f"（证据：{item.get('evidence')}；未验证：{item.get('unverified')}）"
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
                    f"# {candidate}｜第 {round_no} 轮面试报告\n\n## 一、本轮结论摘要\n\n待分析。\n\n"
                    "## 二、面试官评价（忠实提取）\n\n待 AI 提取。\n\n"
                    "## 三、本轮问题覆盖\n\n待分析。\n\n"
                    "## 四、候选人陈述与证据事实\n\n待分析。\n\n"
                    "## 五、AI 独立分析\n\n待分析。\n\n"
                    "## 六、本轮改变了什么\n\n待分析。\n\n"
                    "## 七、与历轮材料的矛盾\n\n待分析。\n\n"
                    "## 八、风险与未验证项\n\n待分析。\n\n"
                    "## 九、AI 下一步倾向\n\n待分析。\n\n"
                    "## 十、已确认个人偏好的影响\n\n待分析。\n\n"
                    "## 十一、人工正式结论\n\n待确认。\n\n## 十二、输入追溯\n\n"
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
    question_coverage: str = "",
    strengthened: str = "",
    weakened: str = "",
    unchanged: str = "",
    contradictions: str = "",
    inclination: str = "继续验证",
    decision_changer: str = "",
    next_verification: str = "",
    next_round_value: str = "",
    preference_impact: str = "",
) -> Path:
    if round_no not in range(1, 6):
        raise ValueError("Interview round must be 1—5")
    if inclination not in INTERVIEW_INCLINATIONS:
        raise ValueError(f"Interview inclination must be one of: {', '.join(INTERVIEW_INCLINATIONS)}")
    folder = root / "02_岗位" / position / "候选人" / candidate / "02_面试" / f"{round_no:02d}_第{round_no}轮"
    raws = [p for p in folder.glob("原始纪要.*") if "提取文本" not in p.name]
    if not raws:
        raise FileNotFoundError(f"No original interview notes in {folder}")
    raw = raws[0]
    digest = sha256(raw)
    body = f"""# {candidate}｜第 {round_no} 轮面试报告

## 一、本轮结论摘要

- AI 下一步倾向：{inclination}
- 决定性理由：{ai_analysis}
- 最大风险：{unverified}
- 最可能改变当前倾向的新证据：{decision_changer.strip() or unverified}
- 是否值得再投入一轮：{next_round_value.strip() or '需根据剩余问题是否重要、可验证且会改变决定判断。'}

## 二、面试官评价（忠实提取）

{interviewer_evaluation}

## 三、本轮问题覆盖

{question_coverage.strip() or '本轮无面试准备文件或未提供问题覆盖信息。'}

## 四、候选人陈述与证据事实

{evidence}

## 五、AI 独立分析

{ai_analysis}

## 六、本轮改变了什么

### 得到支持的判断

{strengthened.strip() or '本轮未记录足以增强既有判断的非重复证据。'}

### 被削弱或推翻的判断

{weakened.strip() or '本轮未发现。'}

### 保持不变的关键判断

{unchanged.strip() or '未单独记录。'}

## 七、与历轮材料的矛盾

{contradictions.strip() or '本轮未发现需要单独处理的材料矛盾。'}

## 八、风险与未验证项

{unverified}

## 九、AI 下一步倾向

- 倾向：{inclination}
- 为什么：{ai_analysis}
- 若继续，下一轮只需验证：{next_verification.strip() or unverified}
- 可能反转倾向的条件：{decision_changer.strip() or unverified}

## 十、已确认个人偏好的影响

{preference_impact.strip() or '未使用个人偏好，仅按岗位画像和本轮证据判断。'}

## 十一、人工正式结论

待确认。此处不得由 AI 助手替代用户写入。

## 十二、输入追溯

- 原始纪要：`{raw.relative_to(root)}`
- SHA-256：`{digest}`
"""
    report = folder / "面试报告.md"
    report.write_text(body, encoding="utf-8")
    overview = root / "02_岗位" / position / "候选人" / candidate / "00_候选人总览.md"
    data, _ = read_markdown(overview)
    summaries = list(data.get("interview_summaries") or [])
    entry = {
        "round": round_no,
        "ai_analysis": ai_analysis,
        "evidence": evidence,
        "unverified": unverified,
        "question_coverage": question_coverage,
        "strengthened": strengthened,
        "weakened": weakened,
        "unchanged": unchanged,
        "contradictions": contradictions,
        "inclination": inclination,
        "decision_changer": decision_changer,
        "next_verification": next_verification,
        "next_round_value": next_round_value,
        "preference_impact": preference_impact,
    }
    summaries = [item for item in summaries if item.get("round") != round_no] + [entry]
    update_frontmatter(overview, current_stage=f"第{round_no}轮已分析", updated_at=today(), interview_summaries=summaries)
    refresh_candidate_overview(overview)
    log_action(root, "interview.analysis_recorded", candidate=candidate, position=position, round=round_no)
    return report


def set_interview_decision(
    root: Path,
    position: str,
    candidate: str,
    round_no: int,
    decision: str,
    reason: str = "",
    confirmed_change: bool = False,
) -> Path:
    overview = root / "02_岗位" / position / "候选人" / candidate / "00_候选人总览.md"
    data, _ = read_markdown(overview)
    current = data.get("interview_human_decisions", {}) or {}
    key = str(round_no)
    old_decision = current.get(key)
    if key in current and current[key] != decision:
        subject = f"{candidate}｜{position}｜第{round_no}轮"
        if not confirmed_change:
            reason_note = f"；用户理由：{reason.strip()}" if reason.strip() else ""
            add_pending(
                root,
                "修改人工面试结论",
                subject,
                f"当前为“{current[key]}”，拟改为“{decision}”{reason_note}",
                "用户再次明确确认后修改",
            )
            raise PermissionError("Queued pending confirmation instead of overwriting interview decision")
        pending_id = resolve_pending(
            root,
            "修改人工面试结论",
            subject,
            f"第{round_no}轮人工结论已由“{current[key]}”修改为“{decision}”",
            required_text=f"当前为“{current[key]}”，拟改为“{decision}”",
        )
        if pending_id is None:
            raise PermissionError("No matching pending confirmation exists for this interview-decision change")
    current[key] = decision
    reasons = data.get("interview_human_decision_reasons", {}) or {}
    if reason.strip():
        reasons[key] = reason.strip()
    elif old_decision is not None and old_decision != decision:
        reasons.pop(key, None)
    update_frontmatter(
        overview,
        interview_human_decisions=current,
        interview_human_decision_reasons=reasons,
        current_stage=f"第{round_no}轮-{decision}",
        updated_at=today(),
    )
    refresh_candidate_overview(overview)
    report = root / "02_岗位" / position / "候选人" / candidate / "02_面试" / f"{round_no:02d}_第{round_no}轮" / "面试报告.md"
    text = report.read_text(encoding="utf-8")
    text = re.sub(
        r"(## (?:十一、)?人工正式结论\n\n).*?(?=\n## (?:十二、)?输入追溯)",
        rf"\1{decision}\n",
        text,
        flags=re.DOTALL,
    )
    report.write_text(text, encoding="utf-8")
    log_action(
        root,
        "interview.decision_recorded",
        candidate=candidate,
        position=position,
        round=round_no,
        decision=decision,
        reason=reason.strip(),
    )
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
    interview_summaries = overview.get("interview_summaries") or []
    interview_decisions = overview.get("interview_human_decisions") or {}
    interview_reasons = overview.get("interview_human_decision_reasons") or {}
    change_lines = []
    for item in sorted(interview_summaries, key=lambda value: value.get("round", 0)):
        round_no = str(item.get("round", ""))
        decision = interview_decisions.get(round_no, "待确认")
        reason = interview_reasons.get(round_no, "")
        reason_text = f"｜理由：{reason}" if reason else ""
        change_lines.append(
            f"- 第{round_no}轮：AI 倾向 {item.get('inclination', '未记录')}｜"
            f"判断：{item.get('ai_analysis', '未记录')}｜"
            f"证据：{item.get('evidence', '未记录')}｜"
            f"未验证：{item.get('unverified', '未记录')}｜"
            f"人工结论：{decision}{reason_text}"
        )
    change_summary = "\n".join(change_lines) or "- 待 AI 助手对照历轮原始纪要和报告补充。"
    sources = overview.get("source_files") or []
    source_list = "\n".join(f"- `{item.get('path')}`｜SHA-256 `{item.get('sha256')}`" for item in sources if isinstance(item, dict))
    resume_analysis = candidate_dir / "01_简历分析.md"
    comparison = root / "02_岗位" / position / "候选人比较.md"
    preference_file = root / "00_公司认知" / "个人招聘判断偏好.md"
    generated_sources = [position_file, overview_file]
    if resume_analysis.exists():
        generated_sources.append(resume_analysis)
    if comparison.exists():
        generated_sources.append(comparison)
    generated_sources.extend(preparations)
    generated_sources.extend(reports)
    if preference_file.exists():
        generated_sources.append(preference_file)
    generated_source_list = "\n".join(f"- `{path.relative_to(root)}`" for path in generated_sources)
    brief_dir = candidate_dir / "03_终面"
    brief_dir.mkdir(parents=True, exist_ok=True)
    brief = brief_dir / "终面简报.md"
    body = f"""# {candidate}｜{position}｜终面决策简报

## 一、一页决策摘要

- AI 倾向：待 AI 助手基于完整材料明确为“建议进入录用讨论 / 谨慎推进 / 继续验证 / 不建议推进”之一。
- 倾向含义：待 AI 助手说明当前是证据足够、需接受风险，还是仍有录用阻塞项。
- 决定性理由：待 AI 助手压缩为一至三条。
- 最大下行风险：{overview.get('resume_risk', '未记录')}
- 终面是否值得：待 AI 助手根据未解问题的重要性、可验证性和决策价值判断。
- 最可能改变当前倾向的新证据：{overview.get('resume_unverified', '未记录')}

## 二、岗位决策证据表

| 岗位判断项 | 当前结论 | 最强支持证据 | 最强反证或边界 | 证据状态 | 对录用判断的影响 |
| --- | --- | --- | --- | --- | --- |
| 待对照正式岗位画像逐项补充 | {overview.get('resume_summary', '待分析')} | {overview.get('resume_evidence', '未记录')} | {overview.get('resume_risk', '未记录')} | 待综合历轮证据 | 待判断 |

## 三、候选人最值得录用的价值

- 待 AI 助手将最关键的业务价值、岗位任务、证据和边界连接起来。

## 四、最大下行风险

- 当前线索：{overview.get('resume_risk', '未记录')}
- 可能后果、发生条件和可降低方式：待 AI 助手补充。

## 五、历轮判断发生了什么变化

{change_summary}

## 六、材料冲突与可信度

- 待 AI 助手回到原始材料，保留冲突双方的路径、轮次、口径解释和决策影响。

## 七、岗位胜任、证据可信度与录用可行性

### 岗位胜任

- 待 AI 助手基于正式岗位画像判断。

### 证据可信度

- 待 AI 助手区分独立证据、候选人主张和重复叙述。

### 录用可行性

- HR 补充：{hr_notes or '未提供，保留为待确认。'}
- 待 AI 助手区分已确认信息、候选人主张和待确认约束。

## 八、终面决定性问题

- 待 AI 助手只保留会改变录用倾向的问题，并补充追问、强弱证据与判断变化条件。

## 九、时间不足时必问的三题

1. 待补充。
2. 待补充。
3. 待补充。

## 十、已明确、不建议重复询问的内容

- 待 AI 助手基于历轮已充分证据补充。

## 十一、人工正式结论与分歧

- 人工筛选结论：{overview.get('human_decision', '未记录')}
- 人工筛选理由：{overview.get('human_decision_reason', '未记录')}
- 历轮人工面试结论：{', '.join(f'第{key}轮：{value}' for key, value in interview_decisions.items()) or '未记录'}
- AI 倾向与人工结论的分歧：待 AI 助手说明。

## 十二、已确认个人偏好的影响

- 来源：`00_公司认知/个人招聘判断偏好.md`
- 待 AI 助手说明具体使用了哪些已确认偏好、影响了什么；没有适用偏好时明确写“未使用”。

## 十三、事实、判断与未验证项清单

### 已确认事实

- 候选人：{candidate}
- 岗位：{position}
- 当前阶段：{overview.get('current_stage', '未记录')}

### 候选人主张

- 待 AI 助手从原始材料中忠实提取。

### AI 判断

- AI 简历建议：{overview.get('ai_recommendation', '未记录')}

### 未验证项

- {overview.get('resume_unverified', '未记录')}

## 十四、输入材料与追溯

{source_list}
{generated_source_list}

本简报提供 AI 证据判断和终面准备，不替代人工最终录用决定。
"""
    brief.write_text(body.rstrip() + "\n", encoding="utf-8")
    update_frontmatter(overview_file, current_stage="终面待进行", updated_at=today(), final_brief=str(brief.relative_to(root)))
    refresh_candidate_overview(overview_file)
    log_action(root, "final_brief.generated", candidate=candidate, position=position, path=str(brief.relative_to(root)))
    return brief


def close_candidate(
    root: Path,
    position: str,
    candidate: str,
    result: str,
    reusable: bool = False,
    closure_category: str = "",
    closure_reason: str = "",
    reuse_level: str = "",
    validated_strengths: str = "",
    weakened_findings: str = "",
    unverified_findings: str = "",
    capability_boundary: str = "",
    reuse_targets: str = "",
    reuse_conditions: str = "",
    reuse_risks: str = "",
    future_verification: str = "",
    decision_changer: str = "",
    lesson: str = "",
    preference_impact: str = "",
) -> Path:
    active = root / "02_岗位" / position / "候选人" / candidate
    overview = active / "00_候选人总览.md"
    if not overview.exists():
        raise FileNotFoundError(overview)
    archive = root / "03_简历库" / position / candidate
    if archive.exists():
        pending = add_pending(root, "归档路径冲突", f"{candidate}｜{position}", f"目标已存在：{archive.relative_to(root)}", "人工确认合并策略，禁止覆盖原档案")
        raise FileExistsError(f"Archive exists; queued {pending}")
    data, _ = read_markdown(overview)
    if not result.strip():
        raise ValueError("Final result must be explicit before archiving")
    closure_category = closure_category.strip() or "其他已明确原因"
    if closure_category not in CLOSURE_CATEGORIES:
        raise ValueError(f"Closure category must be one of: {', '.join(CLOSURE_CATEGORIES)}")
    reuse_level = reuse_level.strip() or ("有条件复用" if reusable else "暂不主动复用")
    if reuse_level not in REUSE_LEVELS:
        raise ValueError(f"Reuse level must be one of: {', '.join(REUSE_LEVELS)}")
    if reusable and reuse_level not in {"优先复用", "有条件复用"}:
        raise ValueError("--reusable conflicts with the selected reuse level")
    reusable = reuse_level in {"优先复用", "有条件复用"}
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
        "closure_category": closure_category,
        "closure_reason": closure_reason.strip() or result.strip(),
        "reuse_level": reuse_level,
        "validated_strengths": validated_strengths.strip() or str(data.get("resume_evidence", "未单独记录。")),
        "weakened_findings": weakened_findings.strip(),
        "archive_unverified": unverified_findings.strip() or str(data.get("resume_unverified", "未单独记录。")),
        "capability_boundary": capability_boundary.strip()
        or "本次结果只适用于当时岗位、条件和已经获得的证据，不能据此泛化为对候选人全部能力的判断。",
        "reuse_targets": reuse_targets.strip(),
        "reuse_conditions": reuse_conditions.strip(),
        "reuse_risks": reuse_risks.strip() or str(data.get("resume_risk", "未单独记录。")),
        "future_verification": future_verification.strip(),
        "reuse_decision_changer": decision_changer.strip(),
        "archive_lesson": lesson.strip(),
        "archive_preference_impact": preference_impact.strip(),
        "updated_at": today(),
        "source_files": sources,
    }
    if data.get("final_brief"):
        changes["final_brief"] = str(data["final_brief"]).replace(old_prefix, new_prefix, 1)
    summary_relative = Path(new_prefix) / "归档摘要.md"
    changes["archive_summary"] = str(summary_relative)
    update_frontmatter(overview, **changes)
    refresh_candidate_overview(overview)

    interview_decisions = data.get("interview_human_decisions") or {}
    interview_reasons = data.get("interview_human_decision_reasons") or {}
    human_rounds = "\n".join(
        f"- 第{round_no}轮：{decision}"
        f"{f'｜理由：{interview_reasons.get(str(round_no))}' if interview_reasons.get(str(round_no)) else ''}"
        for round_no, decision in sorted(interview_decisions.items(), key=lambda item: int(item[0]))
    ) or "- 未记录人工面试结论。"
    trace_paths = []
    for path in sorted(active.rglob("*")):
        if path.is_file() and path.name != "归档摘要.md":
            trace_paths.append(f"- `{str(path.relative_to(root)).replace(old_prefix, new_prefix, 1)}`")
    summary_body = f"""# {candidate}｜{position}｜归档摘要

## 一、人工正式结果

- 最终结果：{result.strip()}
- 结束日期：{today()}
- 结束原因类别：{closure_category}
- 本次流程为何结束：{changes['closure_reason']}

## 二、能力判断与结果边界

### 已验证优势

{changes['validated_strengths']}

### 被削弱或反证的判断

{changes['weakened_findings'] or '未单独记录；需回到面试报告和终面简报核验具体判断。'}

### 仍未验证

{changes['archive_unverified']}

### 本次结果不能推出什么

{changes['capability_boundary']}

## 三、未来复用判断

- 复用等级：{reuse_level}
- 最适合再次考虑的岗位或场景：{changes['reuse_targets'] or '当前未形成明确复用场景。'}
- 复用前提：{changes['reuse_conditions'] or '未单独记录。'}
- 仍需关注的风险：{changes['reuse_risks']}
- 可能改变复用等级的新情况：{changes['reuse_decision_changer'] or '未单独记录。'}

## 四、再次评估的最小验证动作

{changes['future_verification'] or '重新评估前先更新当前意愿、最近经历和与目标岗位相关的关键未验证项。'}

## 五、对未来相似候选人的个案启示

{changes['archive_lesson'] or '本次未形成可独立复用的个案启示。'}

## 六、原人工结论与 AI 判断

- 人工筛选结论：{data.get('human_decision', '未记录')}
- 人工筛选理由：{data.get('human_decision_reason', '未记录') or '未记录'}
{human_rounds}
- AI 简历建议：{data.get('ai_recommendation', '未记录')}
- 已确认个人偏好的影响：{changes['archive_preference_impact'] or '未使用或未单独记录。'}

## 七、输入材料与追溯

{chr(10).join(trace_paths) or '- 未发现可列出的候选人材料（需修复）。'}

本摘要保留人工正式结果、AI 判断和证据边界，不替代原始材料。
"""
    (active / "归档摘要.md").write_text(summary_body.rstrip() + "\n", encoding="utf-8")
    archive.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(active), str(archive))
    for generated in archive.rglob("*.md"):
        text = generated.read_text(encoding="utf-8")
        if old_prefix in text:
            generated.write_text(text.replace(old_prefix, new_prefix), encoding="utf-8")
    ended = root / "02_岗位" / position / "已结束候选人索引.md"
    with ended.open("a", encoding="utf-8") as handle:
        handle.write(f"\n- {today()}｜{candidate}｜{result}｜复用等级：{reuse_level}｜`{archive.relative_to(root)}`\n")
    log_action(
        root,
        "candidate.archived",
        candidate=candidate,
        position=position,
        result=result,
        closure_category=closure_category,
        reusable=reusable,
        reuse_level=reuse_level,
        path=str(archive.relative_to(root)),
    )
    return archive


def search_history(root: Path, query: str, position: str = "") -> list[dict[str, str]]:
    tokens = [item.lower() for item in re.split(r"\s+", query.strip()) if item]
    results: list[dict[str, str]] = []
    for overview in (root / "03_简历库").glob("*/*/00_候选人总览.md"):
        data, body = read_markdown(overview)
        archive_summary = overview.parent / "归档摘要.md"
        archive_text = archive_summary.read_text(encoding="utf-8") if archive_summary.exists() else ""
        haystack = f"{overview}\n{data}\n{body}\n{archive_text}".lower()
        matches = sum(token in haystack for token in tokens)
        reusable = bool(data.get("reusable"))
        if tokens and matches == 0:
            continue
        original_position = str(data.get("position", overview.parents[1].name))
        results.append(
            {
                "name": str(data.get("name", overview.parent.name)),
                "original_position": original_position,
                "final_result": str(data.get("final_result", "未记录")),
                "closure_category": str(data.get("closure_category", "未记录")),
                "closure_reason": str(data.get("closure_reason", data.get("final_result", "未记录"))),
                "reusable": "是" if reusable else "否",
                "reuse_level": str(data.get("reuse_level", "有条件复用" if reusable else "暂不主动复用")),
                "reuse_targets": str(data.get("reuse_targets", "未记录")),
                "reuse_risks": str(data.get("reuse_risks", data.get("resume_risk", "未记录"))),
                "future_verification": str(data.get("future_verification", "未记录")),
                "position_match": "是" if position and position.lower() == original_position.lower() else "否",
                "archive_summary": str(archive_summary.relative_to(root)) if archive_summary.exists() else "",
                "path": str(overview.relative_to(root)),
                "matches": str(matches),
            }
        )
    reuse_order = {"优先复用": 0, "有条件复用": 1, "暂不主动复用": 2, "不建议复用": 3}
    results.sort(
        key=lambda item: (
            reuse_order.get(item["reuse_level"], 4),
            item["position_match"] != "是",
            -int(item["matches"]),
            item["name"],
        )
    )
    log_action(root, "history.searched", query=query, position=position, count=len(results))
    return results


def propose_recruiting_preference(
    root: Path,
    preference_type: str,
    scope: str,
    rule: str,
    effect: str,
    evidence_standard: str,
    exceptions: str,
    counterexample: str,
    source: str,
) -> str:
    if preference_type not in PREFERENCE_TYPES:
        raise ValueError(f"Preference type must be one of: {', '.join(PREFERENCE_TYPES)}")
    values = {
        "scope": _required(scope, "scope"),
        "rule": _required(rule, "rule"),
        "effect": _required(effect, "effect"),
        "evidence_standard": _required(evidence_standard, "evidence_standard"),
        "exceptions": _required(exceptions, "exceptions"),
        "counterexample": _required(counterexample, "counterexample"),
        "source": _required(source, "source"),
    }
    subject = f"{preference_type}｜{values['scope']}"
    reason = (
        f"拟确认规则：“{values['rule']}”｜影响：{values['effect']}｜"
        f"证据要求：{values['evidence_standard']}｜例外：{values['exceptions']}｜"
        f"反例：{values['counterexample']}｜来源：{values['source']}"
    )
    pending_id = add_pending(
        root,
        "确认个人招聘偏好",
        subject,
        reason,
        "用户确认同一条完整规则后写入个人招聘判断偏好主档案；确认前不得用于正式判断",
    )
    log_action(
        root,
        "preference.proposed",
        pending_id=pending_id,
        preference_type=preference_type,
        scope=values["scope"],
        rule=values["rule"],
    )
    return pending_id


def resolve_recruiting_preference(
    root: Path,
    decision: str,
    preference_type: str,
    scope: str,
    rule: str,
    effect: str,
    evidence_standard: str,
    exceptions: str,
    counterexample: str,
    source: str,
    retain_rejection: bool = False,
) -> Path:
    if decision not in PREFERENCE_DECISIONS:
        raise ValueError(f"Decision must be one of: {', '.join(PREFERENCE_DECISIONS)}")
    if preference_type not in PREFERENCE_TYPES:
        raise ValueError(f"Preference type must be one of: {', '.join(PREFERENCE_TYPES)}")
    values = {
        "scope": _required(scope, "scope"),
        "rule": _required(rule, "rule"),
        "effect": _required(effect, "effect"),
        "evidence_standard": _required(evidence_standard, "evidence_standard"),
        "exceptions": _required(exceptions, "exceptions"),
        "counterexample": _required(counterexample, "counterexample"),
        "source": _required(source, "source"),
    }
    path = root / "00_公司认知" / "个人招聘判断偏好.md"
    if not path.exists():
        raise FileNotFoundError(path)
    data, body = read_markdown(path)
    if decision == "确认" and f"- 完整规则：{values['rule']}" in body:
        raise ValueError("The same confirmed preference already exists")

    subject = f"{preference_type}｜{values['scope']}"
    pending_id = resolve_pending(
        root,
        "确认个人招聘偏好",
        subject,
        f"用户已{decision}完整规则；{'写入正式偏好主档案' if decision == '确认' else '不得用于正式判断'}",
        required_text=f"拟确认规则：“{values['rule']}”",
    )
    if pending_id is None:
        raise PermissionError("No matching pending preference proposal exists")

    preference_id = pending_id.replace("PENDING-", "PREF-", 1)
    if decision == "确认":
        section = {
            "通用招聘判断": "## 已确认招聘偏好",
            "岗位族专项": "## 岗位族专项偏好",
            "交互偏好": "## 已确认交互偏好",
        }[preference_type]
        impact = "汇报顺序 / 追问方式 / 工作节奏 / 文件落盘" if preference_type == "交互偏好" else values["effect"]
        entry = f"""### {preference_id}

- 状态：已确认
- 类型：{preference_type}
- 适用范围：{values['scope']}
- 完整规则：{values['rule']}
- 影响环节：{impact}
- 证据要求：{values['evidence_standard']}
- 例外与不适用情形：{values['exceptions']}
- 已知反例：{values['counterexample']}
- 不得进一步推出：不得超出上述范围，不得改写原始事实、正式岗位画像或人工候选人结论
- 来源案例与用户原话：{values['source']}
- 确认日期：{today()}
- 与岗位画像或其他偏好的关系：发生冲突时必须显式说明并重新确认，不静默覆盖"""
        body = _append_section_entry(body, section, entry)
        body = _append_section_entry(
            body,
            "## 变更记录",
            f"- {today()}：确认 {preference_id}（{preference_type}｜{values['scope']}）。",
        )
        data["status"] = data.get("status", "使用中")
        data["updated_at"] = today()
        data["confirmed_recruiting_preferences"] = int(data.get("confirmed_recruiting_preferences") or 0) + 1
        write_markdown(path, data, body)
    elif retain_rejection:
        entry = f"""### REJECTED-{pending_id.removeprefix('PENDING-')}

- 原规则或提案：{values['rule']}
- 状态：已拒绝
- 范围：{preference_type}｜{values['scope']}
- 原因：用户明确拒绝该完整规则；保留记录仅用于避免未来重复误推
- 日期：{today()}
- 后续边界：不得作为有效偏好使用"""
        body = _append_section_entry(body, "## 已拒绝或撤销的偏好", entry)
        body = _append_section_entry(
            body,
            "## 变更记录",
            f"- {today()}：拒绝并保留提案记录 REJECTED-{pending_id.removeprefix('PENDING-')}。",
        )
        data["updated_at"] = today()
        write_markdown(path, data, body)

    log_action(
        root,
        "preference.resolved",
        pending_id=pending_id,
        preference_id=preference_id if decision == "确认" else "",
        decision=decision,
        preference_type=preference_type,
        scope=values["scope"],
        retained_rejection=retain_rejection,
    )
    return path


def _open_pending_items(root: Path) -> list[dict[str, str]]:
    path = root / "04_全局索引" / "待确认事项.md"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    items: list[dict[str, str]] = []
    for match in re.finditer(r"(?m)^## (PENDING-[^｜\n]+)｜([^\n]+)\n(.*?)(?=^## |\Z)", text, re.DOTALL):
        block = match.group(3)
        if "- 状态：待确认" not in block:
            continue

        def field(name: str) -> str:
            found = re.search(rf"(?m)^- {re.escape(name)}：(.*)$", block)
            return found.group(1).strip() if found else ""

        items.append(
            {
                "id": match.group(1),
                "kind": match.group(2).strip(),
                "subject": field("对象"),
                "reason": field("原因"),
                "action": field("待执行动作"),
            }
        )
    return items


def prepare_daily_brief(root: Path) -> Path:
    def clean(value: object) -> str:
        return str(value or "未记录").replace("|", "｜").replace("\n", " ")

    position_records: list[dict[str, object]] = []
    candidate_records: list[dict[str, object]] = []
    for position_file in sorted((root / "02_岗位").glob("*/岗位.md")):
        position_data, _ = read_markdown(position_file)
        position_name = str(position_data.get("position_name", position_file.parent.name))
        status = str(position_data.get("status", "未记录"))
        candidates = []
        for overview in sorted((position_file.parent / "候选人").glob("*/00_候选人总览.md")):
            data, _ = read_markdown(overview)
            record = dict(data)
            record["path"] = str(overview.relative_to(root))
            record["position"] = str(data.get("position", position_name))
            record["name"] = str(data.get("name", overview.parent.name))
            candidates.append(record)
            candidate_records.append(record)
        position_records.append(
            {
                "name": position_name,
                "status": status,
                "path": str(position_file.relative_to(root)),
                "candidates": candidates,
            }
        )

    pending_items = _open_pending_items(root)
    user_rows = []
    for record in candidate_records:
        if record.get("human_decision") == "待确认" and record.get("ai_recommendation") not in {None, "", "待分析"}:
            user_rows.append(
                f"| {clean(record['position'])} / {clean(record['name'])} | 确认本批筛选结论 | "
                f"推进 / 待定 / 淘汰 | AI 建议：{clean(record.get('ai_recommendation'))} | "
                f"见候选人总览及简历分析 | 见未验证项 | 给出一个结论或批量例外 | 阻塞后续流程 |"
            )
    for item in pending_items:
        user_rows.append(
            f"| {clean(item['subject'])} | {clean(item['kind'])} | 确认 / 拒绝 / 补充信息 | "
            f"待 AI 结合原始材料给出倾向 | {clean(item['reason'])} | 未经确认不得执行 | "
            f"确认一个选项 | {clean(item['action'])} |"
        )

    ai_rows = []
    resume_inbox = sorted(p for p in (root / "01_待处理" / "简历").glob("*") if p.is_file())
    interview_inbox = sorted(p for p in (root / "01_待处理" / "面试纪要").glob("*") if p.is_file())
    if resume_inbox:
        ai_rows.append(f"| 处理 {len(resume_inbox)} 份待处理简历 | 生成岗位证据判断与批量确认汇总 | 待执行 | 识别不清或涉及已有人工结论时 |")
    if interview_inbox:
        ai_rows.append(f"| 处理 {len(interview_inbox)} 份面试纪要 | 生成分层面试报告并更新流程证据 | 待执行 | 候选人、岗位或轮次识别不清时 |")
    unanalyzed = [r for r in candidate_records if r.get("ai_recommendation") in {None, "", "待分析"}]
    if unanalyzed:
        ai_rows.append(f"| 完成 {len(unanalyzed)} 名已建档候选人的简历证据分析 | 形成四档建议和岗位内比较输入 | 待执行 | 正式岗位画像不完整时 |")

    position_rows = []
    for record in position_records:
        candidates = record["candidates"]
        waiting = sum(
            c.get("human_decision") == "待确认" and c.get("ai_recommendation") not in {None, "", "待分析"}
            for c in candidates
        )
        unanalyzed_count = sum(c.get("ai_recommendation") in {None, "", "待分析"} for c in candidates)
        current_problem = (
            f"{waiting} 名候选人等待人工筛选决定"
            if waiting
            else (f"{unanalyzed_count} 名候选人待完成证据分析" if unanalyzed_count else "事实底稿未发现待处理候选人判断")
        )
        closest = "、".join(str(c["name"]) for c in candidates[:3]) or "暂无活跃候选人"
        position_rows.append(
            f"| {clean(record['name'])} | {clean(current_problem)} | {clean(closest)} | "
            f"待 AI 结合完整材料判断 | 待判断 | 新材料、明确日期或用户决定 |"
        )

    candidate_sources = "\n".join(f"- `{clean(record['path'])}`" for record in candidate_records)
    position_sources = "\n".join(f"- `{clean(record['path'])}`" for record in position_records)
    pending_path = root / "04_全局索引" / "待确认事项.md"
    body = f"""# 今日招聘简报

- 生成日期：{today()}
- 数据范围：本地正式主档案
- 生成阶段：确定性事实底稿，待 AI 读取关键原始材料后完成业务优先级判断

## 一句话结论

事实底稿已刷新；当前不凭文件时间、数量或缺失字段制造优先级。

## 一、现在最值得关注的事

待 AI 根据真实决策阻塞、明确时间窗口、延后成本和下一步价值选出最多三项；没有高价值事项时可以少于三项。

## 二、只等你决定

| 岗位/候选人 | 需要决定什么 | 可选项 | AI 当前倾向 | 最强依据 | 最大风险 | 你的最小输入 | 不决定的影响 |
|---|---|---|---|---|---|---|---|
{chr(10).join(user_rows) or '| 当前没有需要你决定的事项 | — | — | — | — | — | — | — |'}

## 三、AI 可以直接继续

| 业务行动 | 将产生的结果 | 当前状态 | 仅在什么情况下需要你介入 |
|---|---|---|---|
{chr(10).join(ai_rows) or '| 当前没有从事实字段中识别出的直接处理任务 | — | — | — |'}

## 四、等待外部信息

| 岗位/候选人 | 等待谁提供什么 | 当前无需重复做什么 | 重新进入优先队列的触发条件 | 日期来源 |
|---|---|---|---|---|
| 待 AI 从面试安排、候选人总览和用户近期目标中识别 | — | — | — | 不得根据文件时间猜测 |

## 五、岗位注意力概览

| 岗位 | 当前最重要的问题 | 最接近决策的候选人/批次 | 主要阻塞 | 下一步所有者 | 重新评估触发条件 |
|---|---|---|---|---|---|
{chr(10).join(position_rows) or '| 暂无正式岗位 | — | — | — | — | 新建或恢复岗位 |'}

## 六、可以放心稍后处理

待 AI 说明哪些事项延后不会产生实际损失，以及重新进入优先队列的触发条件；不得把可重建索引或例行文件整理包装成业务优先事项。

## 七、事实边界与信息来源

- 待处理简历：{len(resume_inbox)} 份。
- 待处理面试纪要：{len(interview_inbox)} 份。
- 待确认事项：{len(pending_items)} 项。
- 正式岗位：
{position_sources or '- 暂无。'}
- 活跃候选人总览：
{candidate_sources or '- 暂无。'}
- 待确认主档案：`{pending_path.relative_to(root)}`

本文件是可重建业务视图，不是岗位状态、候选人结论、日期或优先级的新事实来源。开放式优先级判断必须回到上述主档案和关键证据。
"""
    path = root / "04_全局索引" / "今日招聘简报.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body.rstrip() + "\n", encoding="utf-8")
    log_action(
        root,
        "daily_brief.facts_prepared",
        positions=len(position_records),
        candidates=len(candidate_records),
        pending=len(pending_items),
        resume_inbox=len(resume_inbox),
        interview_inbox=len(interview_inbox),
    )
    return path


def calibrate_position(root: Path, position: str) -> Path:
    records: list[dict[str, object]] = []
    paths = list((root / "02_岗位" / position / "候选人").glob("*/00_候选人总览.md"))
    paths += list((root / "03_简历库" / position).glob("*/00_候选人总览.md"))
    for path in paths:
        data, _ = read_markdown(path)
        data = dict(data)
        data["_path"] = str(path.relative_to(root))
        records.append(data)
    differences = [r for r in records if r.get("human_decision") not in {None, "待确认"} and r.get("ai_recommendation") not in {None, "待分析"}]
    def clean(value: object) -> str:
        return str(value or "未记录").replace("|", "｜").replace("\n", " ")

    rows = "\n".join(
        f"| {clean(r.get('name'))} | {clean(r.get('ai_recommendation'))} | "
        f"{clean(r.get('human_decision'))}：{clean(r.get('human_decision_reason'))} | "
        f"{clean((sorted(r.get('interview_summaries') or [], key=lambda item: item.get('round', 0)) or [{}])[-1].get('inclination'))} | "
        f"{clean(r.get('final_result', '进行中'))}：{clean(r.get('closure_reason'))} | `{clean(r.get('_path'))}` |"
        for r in differences
    ) or "| 暂无 | 暂无 | 暂无 | 暂无 | 暂无 | 样本不足 |"
    interviewed = sum(bool(r.get("interview_summaries")) for r in records)
    closed = sum(r.get("process_status") == "已结束" for r in records)
    profile = root / "02_岗位" / position / "岗位.md"
    profile_data, _ = read_markdown(profile)
    target = root / "02_岗位" / position / "岗位校准" / "当前校准建议.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        f"""# {position}｜岗位校准建议

生成日期：{today()}

## 一、结论摘要

- 最值得调整：待 AI 助手基于完整决策链判断，不能仅由最终结果倒推。
- 建议保持：待识别有区分力且没有稳定反证的正式规则。
- 当前只能继续观察：待说明样本不足、阶段缺失或外部原因混杂的信号。

## 二、样本范围与可比性

- 候选人记录：{len(records)} 个。
- AI 与人工筛选结论均可比较：{len(differences)} 个。
- 有面试分析：{interviewed} 个。
- 已结束流程：{closed} 个。
- 当前岗位画像版本：{profile_data.get('image_version', '未记录')}。
- 可比性边界：待 AI 助手检查不同画像版本、时间范围、流程深度和结果缺失。

## 三、完整决策链证据表

| 候选人 | AI 筛选建议 | 人工筛选结论与理由 | 最近 AI 面试倾向 | 最终结果与结束原因 | 主档案 |
| --- | --- | --- | --- | --- | --- |
{rows}

## 四、重复一致、分歧与后续反转

- 待分别检查可能的假阳性、假阴性、AI 与人工共同误判，以及没有区分力的规则。
- 最终录用、淘汰或退出不能自动证明早期筛选正确或错误。

## 五、问题归因

### 岗位画像

待分析。

### 简历筛选证据规则

待分析。

### 面试验证

待分析。

### 流程或外部条件

待分析；先排除 HC、预算、市场、时机、候选人退出和 Offer 条件。

### 个人偏好

待分析；未经确认的偏好不得写入正式规则。

### 个体差异

待分析；单一案例不得直接泛化。

## 六、优先校准建议

### 建议一

- 建议类型：待选择“保持 / 澄清表述 / 调整证据标准 / 调整优先级 / 增加例外 / 调整面试验证 / 继续观察”。
- 当前原文或规则：待从 `02_岗位/{position}/岗位.md` 准确引用。
- 建议后的完整文字：待补充；必须可直接执行。
- 支持案例与路径：待补充。
- 反例或不适用边界：待补充。
- 历史反事实：待说明哪些历史决定可能改变。
- 预期收益：待补充。
- 误伤与放宽风险：待补充。
- 继续观察与撤回条件：待补充。
- 信心：待用高、中、低定性说明。

## 七、明确不建议修改的内容

- 待说明哪些规则应保持，以及为什么不应因近期结果改动。

## 八、待确认事项

- 当前没有已确认修改。任何正式画像变更必须先提供精确的修改前和修改后文字并获得用户明确确认。

## 九、输入材料与追溯

- 正式岗位画像：`{profile.relative_to(root)}`
{chr(10).join(f"- `{clean(r.get('_path'))}`" for r in records) or '- 当前没有候选人主档案。'}

本文件仅是校准建议。未经用户确认，不得修改正式 `岗位.md`、增加 `image_version` 或改写人工候选人结论。
""",
        encoding="utf-8",
    )
    log_action(root, "position.calibration_generated", position=position, records=len(records))
    return target
