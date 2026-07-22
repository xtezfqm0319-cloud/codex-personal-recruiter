from __future__ import annotations

import shutil
import sys
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "06_系统"))

from recruiter.indexes import rebuild_indexes  # noqa: E402
from recruiter.validators import validate_workspace  # noqa: E402
from recruiter.workflows import (  # noqa: E402
    calibrate_position,
    close_candidate,
    confirm_screening,
    create_position,
    generate_final_brief,
    ingest_interviews,
    ingest_resumes,
    init_workspace,
    record_interview_analysis,
    record_resume_analysis,
    search_history,
    set_interview_decision,
)


def main() -> int:
    root = PROJECT / "output" / "demo" / "招聘工作台演示"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    init_workspace(root)
    for relative in [
        "AGENTS.md",
        "00_公司认知/公司与业务.md",
        "00_公司认知/通用招聘标准.md",
        "00_公司认知/能力特质定义.md",
        "00_公司认知/个人招聘判断偏好.md",
    ]:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PROJECT / relative, target)
    (root / "04_全局索引" / "待确认事项.md").write_text("# 待确认事项\n", encoding="utf-8")

    steps: list[str] = []
    fixtures = PROJECT / "06_系统" / "tests" / "fixtures"
    jd = (fixtures / "企业AI产品经理-JD.txt").read_text(encoding="utf-8")
    profile = (fixtures / "企业AI产品经理-已确认画像.md").read_text(encoding="utf-8")
    create_position(root, "企业AI产品经理", jd, "演示内置JD", profile)
    steps.append("新建待校准岗位：02_岗位/企业AI产品经理/岗位.md")

    resume = root / "01_待处理" / "简历" / "陈曦-企业AI产品经理.txt"
    shutil.copy2(fixtures / "陈曦-企业AI产品经理.txt", resume)
    ingest_resumes(root)
    record_resume_analysis(
        root,
        "企业AI产品经理",
        "陈曦",
        "强推",
        "具备企业AI产品从灰度到规模化的直接经历，且有跨团队推进证据。",
        "简历明确记录知识助手从20人灰度扩展到600人，并协调算法和工程优化召回。",
        "简历未给出查找时长下降的具体口径，也未说明个人对关键取舍的最终责任。",
        "业务结果口径、召回优化前后数据、个人决策边界待面试核验。",
        "符合",
        verification="- 追问候选人对产品范围、灰度节奏和算法取舍的最终决策边界；若主要是协调执行，应下调当前建议。",
        preference_impact="- 未使用个人偏好，仅按岗位画像和证据判断。",
    )
    rebuild_indexes(root)
    steps.append("处理简历并生成四档建议：强推；候选人总表已统一排序")

    confirm_screening(root, "企业AI产品经理", "陈曦", "推进")
    rebuild_indexes(root)
    steps.append("人工确认：推进；AI建议与人工结论分别保存")

    notes = root / "01_待处理" / "面试纪要" / "陈曦-企业AI产品经理-第1轮.txt"
    shutil.copy2(fixtures / "陈曦-企业AI产品经理-第1轮.txt", notes)
    ingest_interviews(root)
    record_interview_analysis(
        root,
        "企业AI产品经理",
        "陈曦",
        1,
        "面试官认为候选人能拆解用户痛点、召回问题和推广节奏，并建议进入终面。",
        "候选人展示了分阶段验证与基于失败查询迭代的产品方法；现有材料支持过程判断，但不足以确认最终业务收益。",
        "原始纪要记录20名高频用户灰度、每周检查失败查询、第4周扩展到600人。",
        "查找时长下降缺少统一数据口径；候选人在算法取舍中的最终决策权待核验。",
        question_coverage="灰度策略和失败查询迭代已充分回答；业务结果归因和最终决策权只得到部分回答。",
        strengthened="原‘具备分阶段验证方法’的判断得到了新的行为证据支持。",
        weakened="‘独立负责最终业务结果’仍缺少个人归因证据，不能仅根据项目结果确认。",
        unchanged="查找时长下降的数据口径风险保持不变。",
        contradictions="本轮未发现需要单独处理的材料冲突。",
        inclination="建议推进",
        decision_changer="若后续显示灰度范围、停止条件和算法取舍都由他人决定，当前倾向应下调。",
        next_verification="终面只验证个人最终决策边界和业务结果归因。",
        next_round_value="值得；剩余问题会改变录用判断，且可通过一次项目决策深挖解决。",
        preference_impact="未使用个人偏好，仅按正式岗位画像和本轮证据判断。",
    )
    set_interview_decision(root, "企业AI产品经理", "陈曦", 1, "通过，进入终面")
    steps.append("分析第1轮面试：原始纪要、面试官评价、AI分析、人工结论分层保存")

    brief = generate_final_brief(root, "企业AI产品经理", "陈曦", "HR补充：到岗周期约4周；薪资期望在当前预算范围内，尚未最终确认。")
    steps.append(f"生成终面简报：{brief.relative_to(root)}")

    archive = close_candidate(root, "企业AI产品经理", "陈曦", "HC暂停，未录用；面试通过，人才保留", reusable=True)
    rebuild_indexes(root)
    hits = search_history(root, "企业 AI 知识助手")
    calibration = calibrate_position(root, "企业AI产品经理")
    steps.append(f"结束并归档：{archive.relative_to(root)}")
    steps.append(f"进入历史人才索引：检索命中 {len(hits)} 人；岗位校准建议：{calibration.relative_to(root)}")

    issues = validate_workspace(root)
    errors = [issue for issue in issues if issue.level == "ERROR"]
    result = PROJECT / "output" / "demo" / "端到端测试结果.md"
    result.write_text(
        "# 端到端测试结果\n\n"
        + "\n".join(f"{idx}. {step}" for idx, step in enumerate(steps, 1))
        + f"\n\n## 校验\n\n- 错误：{len(errors)}\n- 警告：{len([i for i in issues if i.level == 'WARNING'])}\n"
        + ("\n".join(f"- {i.level} {i.code}: {i.path} - {i.message}" for i in issues) or "- 工作区校验通过。")
        + "\n\n## 说明\n\n- 所有材料均为脱敏模拟数据。\n- 演示中的开放式业务判断由脚本显式传入，模拟 AI 助手按 Skills 生成后调用 `record-*` 落盘；Python 本身没有调用模型。\n",
        encoding="utf-8",
    )
    print(result)
    print(f"validation_errors={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
