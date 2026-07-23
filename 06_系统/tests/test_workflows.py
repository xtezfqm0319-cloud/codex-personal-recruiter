from __future__ import annotations

import csv
from pathlib import Path

import pytest

from recruiter.frontmatter import read_markdown
from recruiter.indexes import rebuild_indexes
from recruiter.validators import validate_workspace
from recruiter.workflows import (
    calibrate_position,
    close_candidate,
    confirm_screening,
    create_position,
    generate_final_brief,
    ingest_interviews,
    ingest_resumes,
    record_interview_analysis,
    record_resume_analysis,
    search_history,
    set_interview_decision,
)


def add_position_and_resume(root: Path) -> None:
    create_position(root, "AI产品经理", "负责 AI 产品从发现到交付。\n要求：5 年相关产品经验。")
    (root / "01_待处理" / "简历" / "林晓-AI产品经理.txt").write_text(
        "姓名：林晓\n目标岗位：AI产品经理\n经历：负责企业知识助手，推动上线。",
        encoding="utf-8",
    )


def test_ingest_resume_and_rebuild_index(workspace: Path) -> None:
    add_position_and_resume(workspace)
    result = ingest_resumes(workspace)
    assert result[0]["status"] == "已建档"
    resume = workspace / "02_岗位" / "AI产品经理" / "候选人" / "林晓" / "林晓-AI产品经理.txt"
    assert resume.exists()
    quality = workspace / "02_岗位" / "AI产品经理" / "候选人" / "林晓" / "原始简历提取质量.md"
    assert quality.exists() and "结论：通过" in quality.read_text(encoding="utf-8")
    record_resume_analysis(
        workspace,
        "AI产品经理",
        "林晓",
        "推",
        "有从发现到上线的产品闭环证据。",
        "简历明确写有企业知识助手上线经历。",
        "规模和效果数据未披露。",
        "个人贡献边界待验证。",
        "符合",
        verification="- 追问候选人在知识助手上线中的最终决策边界；若只承担协调执行，当前建议应下调。",
        preference_impact="- 未使用个人偏好，仅按岗位画像和证据判断。",
    )
    analysis = (workspace / "02_岗位" / "AI产品经理" / "候选人" / "林晓" / "01_简历分析.md").read_text(encoding="utf-8")
    assert "## 相对位置" in analysis
    assert "## 已确认个人偏好的影响" in analysis
    assert "最终决策边界" in analysis
    assert "未使用个人偏好" in analysis
    counts = rebuild_indexes(workspace)
    assert counts["candidates"] == 1
    assert "林晓" in (workspace / "02_岗位" / "AI产品经理" / "本批次待人工确认.md").read_text(encoding="utf-8")
    with (workspace / "04_全局索引" / "全部候选人.csv").open(encoding="utf-8-sig") as handle:
        row = next(csv.DictReader(handle))
    assert row["ai_recommendation"] == "推"
    assert not [i for i in validate_workspace(workspace) if i.level == "ERROR"]


def test_hard_constraint_guard(workspace: Path) -> None:
    add_position_and_resume(workspace)
    ingest_resumes(workspace)
    with pytest.raises(ValueError, match="hard constraint"):
        record_resume_analysis(workspace, "AI产品经理", "林晓", "推", "摘要", "证据", "风险", "未知", "不符合")


def test_hard_constraint_exception_requires_reason(workspace: Path) -> None:
    add_position_and_resume(workspace)
    ingest_resumes(workspace)
    with pytest.raises(ValueError, match="exception requires"):
        record_resume_analysis(workspace, "AI产品经理", "林晓", "推", "摘要", "证据", "风险", "未知", "存在经确认例外")


def test_ambiguous_resume_goes_to_pending(workspace: Path) -> None:
    create_position(workspace, "AI产品经理", "JD")
    (workspace / "01_待处理" / "简历" / "未知.txt").write_text("只有零散经历，没有姓名和目标岗位。", encoding="utf-8")
    result = ingest_resumes(workspace)
    assert result[0]["status"] == "待确认"
    assert (workspace / "01_待处理" / "待确认" / "未知.txt").exists()
    assert (workspace / "01_待处理" / "待确认" / "未知-文本提取质量.md").exists()
    assert "PENDING-" in (workspace / "04_全局索引" / "待确认事项.md").read_text(encoding="utf-8")


def test_human_decision_cannot_be_overwritten(workspace: Path) -> None:
    add_position_and_resume(workspace)
    ingest_resumes(workspace)
    record_resume_analysis(workspace, "AI产品经理", "林晓", "推", "摘要", "证据", "风险", "未知", "符合")
    confirm_screening(workspace, "AI产品经理", "林晓", "推进")
    with pytest.raises(PermissionError):
        confirm_screening(workspace, "AI产品经理", "林晓", "待定")
    data, _ = read_markdown(workspace / "02_岗位" / "AI产品经理" / "候选人" / "林晓" / "00_候选人总览.md")
    assert data["human_decision"] == "推进"


def test_human_reason_and_confirmed_decision_change_are_traceable(workspace: Path) -> None:
    add_position_and_resume(workspace)
    ingest_resumes(workspace)
    record_resume_analysis(workspace, "AI产品经理", "林晓", "推", "摘要", "证据", "风险", "未知", "符合")
    overview = confirm_screening(workspace, "AI产品经理", "林晓", "推进", "用户认为项目闭环证据值得面试验证")
    data, body = read_markdown(overview)
    assert data["human_decision_reason"] == "用户认为项目闭环证据值得面试验证"
    assert "人工结论理由：用户认为项目闭环证据值得面试验证" in body

    with pytest.raises(PermissionError):
        confirm_screening(workspace, "AI产品经理", "林晓", "待定", "用户希望先比较同岗位其他候选人")
    pending = (workspace / "04_全局索引" / "待确认事项.md").read_text(encoding="utf-8")
    assert "当前人工结论为“推进”，拟改为“待定”" in pending

    confirm_screening(
        workspace,
        "AI产品经理",
        "林晓",
        "待定",
        "用户希望先比较同岗位其他候选人",
        confirmed_change=True,
    )
    data, body = read_markdown(overview)
    assert data["human_decision"] == "待定"
    assert data["human_decision_reason"] == "用户希望先比较同岗位其他候选人"
    assert "状态：已确认并执行" in (workspace / "04_全局索引" / "待确认事项.md").read_text(encoding="utf-8")
    assert "人工结论理由：用户希望先比较同岗位其他候选人" in body


def test_confirmed_decision_change_requires_a_matching_pending_item(workspace: Path) -> None:
    add_position_and_resume(workspace)
    ingest_resumes(workspace)
    confirm_screening(workspace, "AI产品经理", "林晓", "推进")
    with pytest.raises(PermissionError, match="No matching pending"):
        confirm_screening(workspace, "AI产品经理", "林晓", "待定", confirmed_change=True)


def test_confirmed_decision_change_must_match_the_queued_target(workspace: Path) -> None:
    add_position_and_resume(workspace)
    ingest_resumes(workspace)
    confirm_screening(workspace, "AI产品经理", "林晓", "推进")
    with pytest.raises(PermissionError):
        confirm_screening(workspace, "AI产品经理", "林晓", "待定")
    with pytest.raises(PermissionError, match="No matching pending"):
        confirm_screening(workspace, "AI产品经理", "林晓", "淘汰", confirmed_change=True)
    data, _ = read_markdown(workspace / "02_岗位" / "AI产品经理" / "候选人" / "林晓" / "00_候选人总览.md")
    assert data["human_decision"] == "推进"


def test_full_interview_brief_archive_and_history(workspace: Path) -> None:
    add_position_and_resume(workspace)
    ingest_resumes(workspace)
    record_resume_analysis(workspace, "AI产品经理", "林晓", "推", "闭环经验明确", "知识助手已上线", "数据不足", "影响范围待核验", "符合")
    confirm_screening(workspace, "AI产品经理", "林晓", "推进")
    (workspace / "01_待处理" / "面试纪要" / "林晓-AI产品经理-第1轮.txt").write_text(
        "候选人：林晓\n岗位：AI产品经理\n第1轮面试\n面试官评价：拆解清楚。\n事实：候选人说明知识助手先灰度后全量。",
        encoding="utf-8",
    )
    assert ingest_interviews(workspace)[0]["status"] == "已建档"
    record_interview_analysis(
        workspace,
        "AI产品经理",
        "林晓",
        1,
        "面试官认为拆解清楚。",
        "本轮支持候选人具备分阶段验证思路，但业务结果归因仍不完整。",
        "候选人表示先进行20人灰度，再扩大到600人；纪要记录了灰度到全量的过程。",
        "上线效果的基线、口径及个人最终决策边界待核验。",
        question_coverage="灰度策略问题已充分回答；业务结果归因只得到部分回答。",
        strengthened="原‘具备分阶段验证思路’的判断得到新增行为证据支持。",
        weakened="本轮未发现被明确推翻的判断。",
        unchanged="业务结果归因风险保持不变。",
        contradictions="本轮未发现需要单独处理的材料矛盾。",
        inclination="建议推进",
        decision_changer="若后续显示灰度范围和停止条件均由他人制定，当前倾向应下调。",
        next_verification="只验证个人最终决策边界和结果归因。",
        next_round_value="值得；剩余问题重要且可以通过一次项目深挖解决。",
        preference_impact="未使用个人偏好，仅按岗位画像和本轮证据判断。",
    )
    report = (workspace / "02_岗位" / "AI产品经理" / "候选人" / "林晓" / "02_面试" / "01_第1轮" / "面试报告.md").read_text(encoding="utf-8")
    assert "## 六、本轮改变了什么" in report
    assert "## 五、AI 独立分析" in report
    assert "## 九、AI 下一步倾向" in report
    assert "AI 下一步倾向：建议推进" in report
    assert "灰度策略问题已充分回答" in report
    assert "当前倾向应下调" in report
    overview, overview_body = read_markdown(
        workspace / "02_岗位" / "AI产品经理" / "候选人" / "林晓" / "00_候选人总览.md"
    )
    assert overview["interview_summaries"][0]["inclination"] == "建议推进"
    assert "第1轮：建议推进" in overview_body
    set_interview_decision(workspace, "AI产品经理", "林晓", 1, "通过，进入终面")
    report = (workspace / "02_岗位" / "AI产品经理" / "候选人" / "林晓" / "02_面试" / "01_第1轮" / "面试报告.md").read_text(encoding="utf-8")
    assert "## 十一、人工正式结论\n\n通过，进入终面" in report
    brief = generate_final_brief(workspace, "AI产品经理", "林晓", "薪资期望在预算内。")
    brief_text = brief.read_text(encoding="utf-8")
    assert brief.exists() and "不替代人工最终录用决定" in brief_text
    assert "建议进入录用讨论 / 谨慎推进 / 继续验证 / 不建议推进" in brief_text
    assert "## 二、岗位决策证据表" in brief_text
    assert "## 五、历轮判断发生了什么变化" in brief_text
    assert "## 八、终面决定性问题" in brief_text
    assert "## 十、已明确、不建议重复询问的内容" in brief_text
    assert "## 十二、已确认个人偏好的影响" in brief_text
    assert "灰度策略问题已充分回答" not in brief_text
    assert "第1轮：AI 倾向 建议推进" in brief_text
    assert "HR 补充：薪资期望在预算内。" in brief_text
    archive = close_candidate(
        workspace,
        "AI产品经理",
        "林晓",
        "HC暂停，人才保留",
        closure_category="HC、预算或业务变化",
        closure_reason="候选人面试证据支持继续，但当前岗位 HC 暂停。",
        reuse_level="优先复用",
        validated_strengths="分阶段验证和企业产品落地已有简历与一面证据支持。",
        weakened_findings="业务结果归因仍不完整。",
        unverified_findings="个人最终决策边界尚未完成验证。",
        capability_boundary="本次未录用来自 HC，不代表岗位能力不符合。",
        reuse_targets="恢复 HC 后的企业 AI 产品岗位。",
        reuse_conditions="岗位仍需要企业产品落地和分阶段验证能力。",
        reuse_risks="业务结果归因仍需复核。",
        future_verification="更新当前意愿，并只验证个人最终决策边界。",
        decision_changer="若近期经历显示仅承担协调执行，复用等级应下调。",
        lesson="外部原因结束时，应把已验证能力和未录用结果分开保存。",
    )
    rebuild_indexes(workspace)
    assert archive.exists()
    overview, _ = read_markdown(archive / "00_候选人总览.md")
    assert overview["reuse_level"] == "优先复用"
    assert overview["closure_category"] == "HC、预算或业务变化"
    assert overview["archive_summary"] == "03_简历库/AI产品经理/林晓/归档摘要.md"
    archive_summary = (archive / "归档摘要.md").read_text(encoding="utf-8")
    assert "## 二、能力判断与结果边界" in archive_summary
    assert "本次未录用来自 HC，不代表岗位能力不符合" in archive_summary
    assert "恢复 HC 后的企业 AI 产品岗位" in archive_summary
    hits = search_history(workspace, "知识助手")
    assert hits and hits[0]["name"] == "林晓"
    assert hits[0]["reuse_level"] == "优先复用"
    assert hits[0]["closure_category"] == "HC、预算或业务变化"
    assert hits[0]["archive_summary"].endswith("归档摘要.md")
    calibration = calibrate_position(workspace, "AI产品经理")
    assert calibration.exists()
    calibration_text = calibration.read_text(encoding="utf-8")
    assert "## 二、样本范围与可比性" in calibration_text
    assert "## 四、重复一致、分歧与后续反转" in calibration_text
    assert "## 六、优先校准建议" in calibration_text
    assert "未经用户确认，不得修改正式 `岗位.md`" in calibration_text
    assert not [i for i in validate_workspace(workspace) if i.level == "ERROR"]


def test_close_candidate_rejects_conflicting_reuse_flags(workspace: Path) -> None:
    add_position_and_resume(workspace)
    ingest_resumes(workspace)
    with pytest.raises(ValueError, match="conflicts"):
        close_candidate(
            workspace,
            "AI产品经理",
            "林晓",
            "流程结束",
            reusable=True,
            reuse_level="不建议复用",
        )


def test_interview_analysis_rejects_unknown_inclination(workspace: Path) -> None:
    add_position_and_resume(workspace)
    ingest_resumes(workspace)
    confirm_screening(workspace, "AI产品经理", "林晓", "推进")
    (workspace / "01_待处理" / "面试纪要" / "林晓-AI产品经理-第1轮.txt").write_text(
        "候选人：林晓\n岗位：AI产品经理\n第1轮面试\n候选人表示参与项目。",
        encoding="utf-8",
    )
    ingest_interviews(workspace)
    with pytest.raises(ValueError, match="Interview inclination"):
        record_interview_analysis(
            workspace,
            "AI产品经理",
            "林晓",
            1,
            "纪要未记录",
            "证据不足",
            "仅记录参与项目",
            "个人贡献待验证",
            inclination="强推",
        )


def test_interview_decision_change_requires_matching_reconfirmation(workspace: Path) -> None:
    add_position_and_resume(workspace)
    ingest_resumes(workspace)
    confirm_screening(workspace, "AI产品经理", "林晓", "推进")
    (workspace / "01_待处理" / "面试纪要" / "林晓-AI产品经理-第1轮.txt").write_text(
        "候选人：林晓\n岗位：AI产品经理\n第1轮面试\n候选人说明了项目经历。",
        encoding="utf-8",
    )
    ingest_interviews(workspace)
    record_interview_analysis(workspace, "AI产品经理", "林晓", 1, "纪要未记录", "仍需验证", "项目经历", "个人贡献待验证")
    set_interview_decision(workspace, "AI产品经理", "林晓", 1, "通过", "用户认可本轮证据")

    with pytest.raises(PermissionError):
        set_interview_decision(workspace, "AI产品经理", "林晓", 1, "待定", "用户希望比较其他候选人")
    with pytest.raises(PermissionError, match="No matching pending"):
        set_interview_decision(workspace, "AI产品经理", "林晓", 1, "淘汰", confirmed_change=True)

    set_interview_decision(
        workspace,
        "AI产品经理",
        "林晓",
        1,
        "待定",
        "用户希望比较其他候选人",
        confirmed_change=True,
    )
    overview, _ = read_markdown(
        workspace / "02_岗位" / "AI产品经理" / "候选人" / "林晓" / "00_候选人总览.md"
    )
    assert overview["interview_human_decisions"]["1"] == "待定"
    assert overview["interview_human_decision_reasons"]["1"] == "用户希望比较其他候选人"
    pending = (workspace / "04_全局索引" / "待确认事项.md").read_text(encoding="utf-8")
    assert "状态：已确认并执行" in pending
