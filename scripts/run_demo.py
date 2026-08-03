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
    prepare_daily_brief,
    propose_recruiting_preference,
    record_interview_analysis,
    record_resume_analysis,
    resolve_recruiting_preference,
    start_preference_calibration,
    record_preference_calibration_answer,
    summarize_preference_calibration,
    complete_preference_calibration,
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
    (root / "05_共享模板").mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        PROJECT / "05_共享模板" / "首次招聘判断校准模板.md",
        root / "05_共享模板" / "首次招聘判断校准模板.md",
    )

    steps: list[str] = []
    start_preference_calibration(root)
    calibration_answers = (
        ("CAL-Q1", "证据门槛与面试投入", "选潜力信号强且可低成本验证的人"),
        ("CAL-Q2", "个人贡献与团队结果", "先看能说清关键取舍和结果边界的人"),
        ("CAL-Q3", "精确经验与可迁移能力", "有适应时间时可接受可迁移能力"),
        ("CAL-Q4", "确定性与潜力风险", "失败代价中等时允许有验证路径的不确定性"),
        ("CAL-Q5", "汇报与决策交互", "默认先给先约谁和最小确认项"),
    )
    for question_id, dimension, answer in calibration_answers:
        record_preference_calibration_answer(
            root,
            question_id,
            "核心问题",
            dimension,
            f"演示用取舍情境：{dimension}",
            answer,
            f"初步理解：{answer}，但不扩大为无条件门槛。",
            "岗位时间、失败代价或验证成本改变时需重新判断。",
        )
    record_preference_calibration_answer(
        root,
        "CAL-R1",
        "反向验证",
        "个人贡献证据的停止条件",
        "如果候选人不是最终负责人，但能证明职责范围内的关键取舍，是否仍认为证据不足",
        "不，职责范围内的清晰贡献仍然有效。",
        "用户要求的是个人贡献边界，不是必须拥有最高职务或最终负责人头衔。",
        "能证明职责范围内关键取舍时，不因非最终负责人而降低判断。",
    )
    summarize_preference_calibration(
        root,
        "1. 团队结果不能直接证明个人贡献；要求本人关键取舍和结果边界证据。",
        "- 对可迁移能力的偏好受上手时间影响，暂作观察。",
        "- 不推断候选人必须是项目最终负责人。\n- 不把简历表达质量直接等同于能力。",
        "- 未使用时可能因大项目结果优先 A；使用后优先能说清个人取舍的 B。若 A 补充本人关键贡献证据，结论可反转。",
    )
    preference = {
        "preference_type": "岗位族专项",
        "scope": "需要独立判断的产品岗位",
        "rule": "团队结果不能直接证明候选人的个人贡献，必须看到本人做出的关键取舍和结果边界。",
        "effect": "影响证据置信度、岗位内排序和面试验证",
        "evidence_standard": "材料至少说明本人识别的问题、关键选择、推动动作和结果归因",
        "exceptions": "岗位只要求明确执行时，不把独立决策作为能力底线",
        "counterexample": "候选人不是最终负责人，但能证明职责范围内的关键取舍和结果",
        "source": "模拟用户明确确认：以后产品岗位都按这条完整规则判断。",
    }
    pending_preference = propose_recruiting_preference(root, **preference)
    resolve_recruiting_preference(root, "确认", **preference)
    complete_preference_calibration(root, "- 规则 1：已确认并写入正式偏好。\n- 其余倾向：保留观察，不影响正式判断。")
    steps.append(f"首次招聘判断校准：5 个核心情境 + 1 个反向验证；{pending_preference} 确认后才写入正式主档案")

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

    daily_brief = prepare_daily_brief(root)
    steps.append(f"生成今日招聘事实底稿：{daily_brief.relative_to(root)}；区分用户决定、AI 可继续和外部等待")

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

    archive = close_candidate(
        root,
        "企业AI产品经理",
        "陈曦",
        "HC暂停，未录用；面试通过，人才保留",
        closure_category="HC、预算或业务变化",
        closure_reason="候选人通过业务面试，但当前岗位 HC 暂停，本次流程结束。",
        reuse_level="优先复用",
        validated_strengths="企业知识助手落地、分阶段验证和跨团队推进已有简历与面试证据支持。",
        weakened_findings="业务结果归因和个人最终决策边界仍不完整。",
        unverified_findings="终面尚未完成，最终决策边界和长期业务结果仍未验证。",
        capability_boundary="本次未录用来自 HC 暂停，不能据此判断候选人岗位能力不足。",
        reuse_targets="HC 恢复后的企业 AI 产品岗位，尤其适合需要从试点推进到规模化落地的场景。",
        reuse_conditions="岗位仍重视企业客户理解、产品落地和跨团队推进。",
        reuse_risks="重新启用前仍需核验业务结果归因和候选人的最终决策边界。",
        future_verification="先更新当前意愿和近况，再只验证个人最终决策边界及结果口径。",
        decision_changer="若新增证据显示关键方案和停止条件均由他人决定，复用等级应下调。",
        lesson="外部原因结束时，要单独保存已经验证的能力，避免未来把未录用误读为能力不匹配。",
    )
    rebuild_indexes(root)
    hits = search_history(root, "企业 AI 知识助手")
    calibration = calibrate_position(root, "企业AI产品经理")
    steps.append(f"结束并归档：{archive.relative_to(root)}；生成结构化归档摘要和四级复用判断")
    steps.append(f"进入历史人才索引：检索命中 {len(hits)} 人；岗位校准建议：{calibration.relative_to(root)}")

    issues = validate_workspace(root)
    errors = [issue for issue in issues if issue.level == "ERROR"]
    result = PROJECT / "output" / "demo" / "端到端测试结果.md"
    result.write_text(
        "# 端到端测试结果\n\n"
        + "\n".join(f"{idx}. {step}" for idx, step in enumerate(steps, 1))
        + f"\n\n## 校验\n\n- 错误：{len(errors)}\n- 警告：{len([i for i in issues if i.level == 'WARNING'])}\n"
        + ("\n".join(f"- {i.level} {i.code}: {i.path} - {i.message}" for i in issues) or "- 工作区校验通过。")
        + "\n\n## 招聘总控入口对应场景\n\n"
        + "- 用户说“处理新简历并告诉我先约谁”时，总入口会连续覆盖上面的简历建档、证据分析、岗位内比较和批量确认准备，只在写入人工正式结论前停下。\n"
        + "- 用户确认推进后再说“分析一面，值得的话准备终面”，总入口会沿用同一候选人上下文，完成纪要分析并呈现判断变化；人工面试结论仍由用户决定。\n"
        + "- 本演示脚本实际执行相同的底层确定性工作流；总入口负责在 Codex 或 Claude Code 对话中理解和编排这些步骤，不调用外部模型 API。\n"
        + "\n\n## 说明\n\n- 所有材料均为脱敏模拟数据。\n- 演示中的开放式业务判断由脚本显式传入，模拟 AI 助手按 Skills 生成后调用 `record-*` 落盘；Python 本身没有调用模型。\n",
        encoding="utf-8",
    )
    print(result)
    print(f"validation_errors={len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
