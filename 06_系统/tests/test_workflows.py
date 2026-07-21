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
    create_position(root, "AI产品经理", "负责 AI 产品从发现到交付。\n要求：5 年产品经验，985 本科。")
    (root / "01_待处理" / "简历" / "林晓-AI产品经理.txt").write_text(
        "姓名：林晓\n目标岗位：AI产品经理\n第一学历：985本科\n经历：负责企业知识助手，推动上线。",
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
        "985",
    )
    analysis = (workspace / "02_岗位" / "AI产品经理" / "候选人" / "林晓" / "01_简历分析.md").read_text(encoding="utf-8")
    assert "## 相对位置" in analysis
    assert "## 已确认个人偏好的影响" in analysis
    counts = rebuild_indexes(workspace)
    assert counts["candidates"] == 1
    assert "林晓" in (workspace / "02_岗位" / "AI产品经理" / "本批次待人工确认.md").read_text(encoding="utf-8")
    with (workspace / "04_全局索引" / "全部候选人.csv").open(encoding="utf-8-sig") as handle:
        row = next(csv.DictReader(handle))
    assert row["ai_recommendation"] == "推"
    assert not [i for i in validate_workspace(workspace) if i.level == "ERROR"]


def test_education_guard(workspace: Path) -> None:
    add_position_and_resume(workspace)
    ingest_resumes(workspace)
    with pytest.raises(ValueError, match="cannot be recommended"):
        record_resume_analysis(workspace, "AI产品经理", "林晓", "推", "摘要", "证据", "风险", "未知", "未验证")


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
    record_resume_analysis(workspace, "AI产品经理", "林晓", "推", "摘要", "证据", "风险", "未知", "985")
    confirm_screening(workspace, "AI产品经理", "林晓", "推进")
    with pytest.raises(PermissionError):
        confirm_screening(workspace, "AI产品经理", "林晓", "待定")
    data, _ = read_markdown(workspace / "02_岗位" / "AI产品经理" / "候选人" / "林晓" / "00_候选人总览.md")
    assert data["human_decision"] == "推进"


def test_full_interview_brief_archive_and_history(workspace: Path) -> None:
    add_position_and_resume(workspace)
    ingest_resumes(workspace)
    record_resume_analysis(workspace, "AI产品经理", "林晓", "推", "闭环经验明确", "知识助手已上线", "数据不足", "影响范围待核验", "985")
    confirm_screening(workspace, "AI产品经理", "林晓", "推进")
    (workspace / "01_待处理" / "面试纪要" / "林晓-AI产品经理-第1轮.txt").write_text(
        "候选人：林晓\n岗位：AI产品经理\n第1轮面试\n面试官评价：拆解清楚。\n事实：候选人说明知识助手先灰度后全量。",
        encoding="utf-8",
    )
    assert ingest_interviews(workspace)[0]["status"] == "已建档"
    record_interview_analysis(workspace, "AI产品经理", "林晓", 1, "面试官认为拆解清楚。", "展示了分阶段验证思路。", "纪要记录先灰度后全量。", "上线效果数据待核验。")
    report = (workspace / "02_岗位" / "AI产品经理" / "候选人" / "林晓" / "02_面试" / "01_第1轮" / "面试报告.md").read_text(encoding="utf-8")
    assert "## 本轮改变了什么" in report
    assert "## AI 独立分析" in report
    assert "## AI 下一步倾向" in report
    set_interview_decision(workspace, "AI产品经理", "林晓", 1, "通过，进入终面")
    brief = generate_final_brief(workspace, "AI产品经理", "林晓", "薪资期望在预算内。")
    brief_text = brief.read_text(encoding="utf-8")
    assert brief.exists() and "不替代最终录用决定" in brief_text
    assert "建议进入录用讨论 / 谨慎推进 / 继续验证 / 不建议推进" in brief_text
    assert "## 十、已确认个人偏好的影响" in brief_text
    archive = close_candidate(workspace, "AI产品经理", "林晓", "HC暂停，人才保留", reusable=True)
    rebuild_indexes(workspace)
    assert archive.exists()
    hits = search_history(workspace, "知识助手")
    assert hits and hits[0]["name"] == "林晓"
    calibration = calibrate_position(workspace, "AI产品经理")
    assert calibration.exists()
    assert not [i for i in validate_workspace(workspace) if i.level == "ERROR"]
