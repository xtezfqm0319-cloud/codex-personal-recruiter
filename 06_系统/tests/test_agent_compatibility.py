from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_claude_instructions_import_shared_rules() -> None:
    content = (PROJECT_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert content.startswith("@AGENTS.md")
    assert ".claude/skills/" in content
    assert ".agents/skills/" in content


def test_claude_skills_match_canonical_skills() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/sync_agent_skills.py", "--root", ".", "--check"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    codex_names = {path.name for path in (PROJECT_ROOT / ".agents/skills").iterdir() if (path / "SKILL.md").exists()}
    claude_names = {path.name for path in (PROJECT_ROOT / ".claude/skills").iterdir() if (path / "SKILL.md").exists()}
    assert claude_names == codex_names
    assert len(claude_names) == 13


def test_claude_cross_skill_calls_use_slash_commands() -> None:
    for skill in (PROJECT_ROOT / ".claude/skills").glob("*/SKILL.md"):
        assert not SKILL_REFERENCE_PATTERN.search(skill.read_text(encoding="utf-8")), skill


def test_create_position_has_detailed_chinese_contract() -> None:
    skill = (PROJECT_ROOT / ".agents/skills/create-position/SKILL.md").read_text(encoding="utf-8")
    reference_path = PROJECT_ROOT / ".agents/skills/create-position/references/建岗判断与输出规范.md"
    reference = reference_path.read_text(encoding="utf-8")

    assert "[建岗判断与输出规范.md](references/建岗判断与输出规范.md)" in skill
    assert "每轮最多提出三个问题" in skill
    for heading in ("## 1. 第一轮回复格式", "## 4. 证据强弱与验证阶段", "## 7. 选人规则预览格式", "## 10. 写入前自检"):
        assert heading in reference


def test_process_resumes_has_detailed_chinese_contract() -> None:
    skill = (PROJECT_ROOT / ".agents/skills/process-resumes/SKILL.md").read_text(encoding="utf-8")
    reference_path = PROJECT_ROOT / ".agents/skills/process-resumes/references/简历筛选判断与输出规范.md"
    reference = reference_path.read_text(encoding="utf-8")

    assert "[简历筛选判断与输出规范.md](references/简历筛选判断与输出规范.md)" in skill
    assert "第一遍：逐份建立证据判断" in skill
    assert "第二遍：岗位内统一比较" in skill
    for heading in (
        "## 3. 两遍判断流程",
        "## 6. 四档建议的完整边界",
        "## 10. 岗位内排序与面试容量",
        "## 15. 写入前自检",
    ):
        assert heading in reference


def test_compare_candidates_has_detailed_chinese_contract() -> None:
    skill = (PROJECT_ROOT / ".agents/skills/compare-candidates/SKILL.md").read_text(encoding="utf-8")
    reference_path = PROJECT_ROOT / ".agents/skills/compare-candidates/references/候选人比较判断与输出规范.md"
    reference = reference_path.read_text(encoding="utf-8")

    assert "[候选人比较判断与输出规范.md](references/候选人比较判断与输出规范.md)" in skill
    assert "先确定比较范围" in skill
    assert "有限名额决策" in skill
    for heading in (
        "## 3. 阶段可比性",
        "## 5. 证据归一与去重",
        "## 7. 优势冲突、支配关系与并列",
        "## 10. 相邻候选人解释",
        "## 15. 写入前自检",
    ):
        assert heading in reference


def test_confirm_screening_has_detailed_chinese_contract() -> None:
    skill = (PROJECT_ROOT / ".agents/skills/confirm-screening/SKILL.md").read_text(encoding="utf-8")
    reference_path = PROJECT_ROOT / ".agents/skills/confirm-screening/references/人工筛选确认判断与执行规范.md"
    reference = reference_path.read_text(encoding="utf-8")

    assert "[人工筛选确认判断与执行规范](references/人工筛选确认判断与执行规范.md)" in skill
    assert "批量表达必须先在内部展开为逐人映射" in skill
    assert "--confirmed-change" in skill
    for heading in (
        "## 3. 人工结论的严格含义",
        "## 5. 批量范围与指代解析",
        "## 8. 人工理由的记录规则",
        "## 10. 已有人工结论的变更",
        "## 17. 写入前自检",
    ):
        assert heading in reference


def test_prepare_interview_has_detailed_chinese_contract() -> None:
    skill = (PROJECT_ROOT / ".agents/skills/prepare-interview/SKILL.md").read_text(encoding="utf-8")
    reference_path = PROJECT_ROOT / ".agents/skills/prepare-interview/references/面试准备判断与问题设计规范.md"
    reference = reference_path.read_text(encoding="utf-8")
    template = (PROJECT_ROOT / "05_共享模板/面试准备清单模板.md").read_text(encoding="utf-8")

    assert "[面试准备判断与问题设计规范](references/面试准备判断与问题设计规范.md)" in skill
    assert "本轮结束后，用户需要做什么决定" in skill
    assert "时间有限时必问的三题" in skill
    for heading in (
        "## 3. 定义本轮决策任务",
        "## 5. 选择高信息价值问题",
        "## 8. 追问路径的设计",
        "## 13. 偏好、偏差与公平边界",
        "## 17. 写入前自检",
    ):
        assert heading in reference
    for field in ("本轮唯一核心目标", "具体证据缺口或冲突", "对当前判断的影响", "面试官需要原样记录"):
        assert field in template


def test_analyze_interview_has_detailed_chinese_contract() -> None:
    skill = (PROJECT_ROOT / ".agents/skills/analyze-interview/SKILL.md").read_text(encoding="utf-8")
    reference_path = PROJECT_ROOT / ".agents/skills/analyze-interview/references/面试纪要分析与多轮证据规范.md"
    reference = reference_path.read_text(encoding="utf-8")
    template = (PROJECT_ROOT / "05_共享模板/面试报告模板.md").read_text(encoding="utf-8")

    assert "[面试纪要分析与多轮证据规范](references/面试纪要分析与多轮证据规范.md)" in skill
    assert "面试官评价、候选人陈述、可用证据、AI 独立判断和人工正式结论" in skill
    assert "--question-coverage" in skill
    assert "--decision-changer" in skill
    for heading in (
        "## 3. 五层信息分离",
        "## 6. 对照面试准备检查问题覆盖",
        "## 8. 本轮变化账本",
        "## 9. 多轮证据累积与去重",
        "## 13. 判断下一轮是否值得",
        "## 17. 写入前自检",
    ):
        assert heading in reference
    for field in ("本轮问题覆盖", "候选人陈述与证据事实", "与历轮材料的矛盾", "人工正式结论"):
        assert field in template


def test_generate_final_brief_has_detailed_chinese_contract() -> None:
    skill = (PROJECT_ROOT / ".agents/skills/generate-final-brief/SKILL.md").read_text(encoding="utf-8")
    reference_path = PROJECT_ROOT / ".agents/skills/generate-final-brief/references/终面简报规则.md"
    reference = reference_path.read_text(encoding="utf-8")
    template = (PROJECT_ROOT / "05_共享模板/终面简报模板.md").read_text(encoding="utf-8")

    assert "[终面决策简报判断与输出规范](references/终面简报规则.md)" in skill
    assert "分开三个决策维度" in skill
    assert "谨慎推进" in skill and "继续验证" in skill
    assert "时间不足时的必问三题" in skill
    for heading in (
        "## 5. 建立决策证据表",
        "## 8. 岗位胜任、证据可信度与录用可行性",
        "## 11. 四类 AI 倾向",
        "## 13. 终面是否还值得",
        "## 14. 终面必问项设计",
        "## 19. 写入前自检",
    ):
        assert heading in reference
    for field in (
        "岗位决策证据表",
        "最大下行风险",
        "历轮判断发生了什么变化",
        "时间不足时必问的三题",
        "人工正式结论与分歧",
    ):
        assert field in template


def test_close_candidate_has_detailed_chinese_contract() -> None:
    skill = (PROJECT_ROOT / ".agents/skills/close-candidate/SKILL.md").read_text(encoding="utf-8")
    reference_path = PROJECT_ROOT / ".agents/skills/close-candidate/references/候选人结束归档判断与输出规范.md"
    reference = reference_path.read_text(encoding="utf-8")
    template = (PROJECT_ROOT / "05_共享模板/候选人归档摘要模板.md").read_text(encoding="utf-8")

    assert "[候选人结束归档判断与输出规范](references/候选人结束归档判断与输出规范.md)" in skill
    assert "人工正式结果" in skill
    assert "优先复用" in skill and "不建议复用" in skill
    assert "--capability-boundary" in skill
    for heading in (
        "## 5. 四层结论分离",
        "## 7. 结果不能推出什么",
        "## 8. 四级复用判断",
        "## 13. 归档摘要格式",
        "## 17. 写入前自检",
    ):
        assert heading in reference
    for field in ("人工正式结果", "能力判断与结果边界", "未来复用判断", "再次评估的最小验证动作"):
        assert field in template


def test_search_history_has_detailed_chinese_contract() -> None:
    skill = (PROJECT_ROOT / ".agents/skills/search-history/SKILL.md").read_text(encoding="utf-8")
    reference_path = PROJECT_ROOT / ".agents/skills/search-history/references/历史人才检索与复用判断规范.md"
    reference = reference_path.read_text(encoding="utf-8")
    template = (PROJECT_ROOT / "05_共享模板/历史人才复用建议模板.md").read_text(encoding="utf-8")

    assert "[历史人才检索与复用判断规范](references/历史人才检索与复用判断规范.md)" in skill
    assert "CLI 命中只用于召回" in skill
    assert "旧岗位上的“强推、淘汰、面试通过”均不能直接继承" in skill
    for heading in (
        "## 6. 召回不等于匹配",
        "## 10. 旧结论的有效范围",
        "## 13. 四类当前复用优先级",
        "## 14. 多人比较与排序",
        "## 19. 写入前自检",
    ):
        assert heading in reference
    for field in ("本次查询与边界", "最强反证或边界", "原岗位与当前需求的关键差异", "最小下一步"):
        assert field in template


def test_calibrate_position_has_detailed_chinese_contract() -> None:
    skill = (PROJECT_ROOT / ".agents/skills/calibrate-position/SKILL.md").read_text(encoding="utf-8")
    reference_path = PROJECT_ROOT / ".agents/skills/calibrate-position/references/岗位校准判断与输出规范.md"
    reference = reference_path.read_text(encoding="utf-8")
    template = (PROJECT_ROOT / "05_共享模板/岗位校准建议模板.md").read_text(encoding="utf-8")

    assert "[岗位校准判断与输出规范](references/岗位校准判断与输出规范.md)" in skill
    assert "最终录用、淘汰或退出只是结果" in skill
    assert "历史反事实" in skill
    for heading in (
        "## 4. 样本可比性审计",
        "## 7. 四类重点案例",
        "## 8. 结果泄漏和事后合理化",
        "## 14. 反事实检查",
        "## 22. 写入前自检",
    ):
        assert heading in reference
    for field in ("样本范围与可比性", "完整决策链证据表", "误伤与放宽风险", "明确不建议修改的内容"):
        assert field in template


def test_learn_preferences_has_detailed_chinese_contract() -> None:
    skill = (PROJECT_ROOT / ".agents/skills/learn-recruiting-preferences/SKILL.md").read_text(encoding="utf-8")
    reference_path = (
        PROJECT_ROOT / ".agents/skills/learn-recruiting-preferences/references/个人招聘偏好识别与应用规范.md"
    )
    reference = reference_path.read_text(encoding="utf-8")
    template = (PROJECT_ROOT / "05_共享模板/个人招聘判断偏好模板.md").read_text(encoding="utf-8")

    assert "[个人招聘偏好识别与应用规范](references/个人招聘偏好识别与应用规范.md)" in skill
    assert "个案决定" in skill and "不可学习内容" in skill
    assert "propose-preference" in skill and "resolve-preference" in skill
    for heading in (
        "## 3. 六层反馈分类",
        "## 6. 规则候选的完整结构",
        "## 9. 反例与过度泛化检查",
        "## 13. 确认、拒绝、修改与撤销",
        "## 16. 已确认偏好的应用审计",
        "## 20. 写入前自检",
    ):
        assert heading in reference
    for field in ("完整规则", "决策影响", "证据要求", "已知反例", "不得进一步推出"):
        assert field in template


def test_daily_brief_has_detailed_chinese_contract() -> None:
    skill = (PROJECT_ROOT / ".agents/skills/daily-recruiting-brief/SKILL.md").read_text(encoding="utf-8")
    reference_path = PROJECT_ROOT / ".agents/skills/daily-recruiting-brief/references/今日招聘优先级与行动简报规范.md"
    reference = reference_path.read_text(encoding="utf-8")
    template = (PROJECT_ROOT / "05_共享模板/今日招聘简报模板.md").read_text(encoding="utf-8")

    assert "[今日招聘优先级与行动简报规范](references/今日招聘优先级与行动简报规范.md)" in skill
    assert "需要用户决定" in skill and "AI 可以直接继续" in skill and "需要外部信息或等待" in skill
    assert "prepare-daily-brief" in skill
    for heading in (
        "## 3. 三类行动所有者",
        "## 5. 跨岗位优先级判断",
        "## 8. 前三事项的完整结构",
        "## 11. 最小用户决策集",
        "## 14. 可以稍后处理",
        "## 20. 写入前自检",
    ):
        assert heading in reference
    for field in ("为什么是现在", "今天不处理的实际影响", "你的最小输入", "重新进入优先队列的触发条件"):
        assert field in template


def test_recruiting_workbench_controller_routes_and_continues_tasks() -> None:
    skill_path = PROJECT_ROOT / ".agents/skills/run-recruiting-workbench/SKILL.md"
    reference_path = (
        PROJECT_ROOT / ".agents/skills/run-recruiting-workbench/references/招聘意图路由与连续执行规范.md"
    )
    metadata_path = PROJECT_ROOT / ".agents/skills/run-recruiting-workbench/agents/openai.yaml"
    skill = skill_path.read_text(encoding="utf-8")
    reference = reference_path.read_text(encoding="utf-8")
    metadata = metadata_path.read_text(encoding="utf-8")
    agents = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")

    assert "[招聘意图路由与连续执行规范](references/招聘意图路由与连续执行规范.md)" in skill
    assert "总入口只负责理解、路由、编排、连续推进和统一交付" in skill
    assert "前两个" in skill and "按刚才建议执行" in skill
    assert "证据已足够，可以决定" in skill
    assert "结果 → 关键判断 → 只需用户决定 → 接下来" in agents
    assert "$run-recruiting-workbench" in agents
    assert "招聘工作台总入口" in metadata
    assert "$run-recruiting-workbench" in metadata

    professional_skills = {
        "create-position",
        "process-resumes",
        "compare-candidates",
        "confirm-screening",
        "prepare-interview",
        "analyze-interview",
        "generate-final-brief",
        "close-candidate",
        "search-history",
        "calibrate-position",
        "learn-recruiting-preferences",
        "daily-recruiting-brief",
    }
    for name in professional_skills:
        assert f"${name}" in skill or f"${name}" in reference

    for heading in (
        "## 3. 用户意图的六种形态",
        "## 5. 单环节路由表",
        "## 6. 多环节组合路径",
        "## 7. 用户是否需要介入",
        "## 8. 连续对话与指代",
        "## 10. 统一对话结果",
        "## 13. 待确认与异常体验",
        "## 17. 执行前后自检",
    ):
        assert heading in reference


def test_claude_workbench_controller_uses_native_skill_calls() -> None:
    skill = (PROJECT_ROOT / ".claude/skills/run-recruiting-workbench/SKILL.md").read_text(encoding="utf-8")
    reference = (
        PROJECT_ROOT / ".claude/skills/run-recruiting-workbench/references/招聘意图路由与连续执行规范.md"
    ).read_text(encoding="utf-8")
    for name in ("process-resumes", "confirm-screening", "prepare-interview", "daily-recruiting-brief"):
        assert f"/{name}" in skill or f"/{name}" in reference
        assert f"${name}" not in skill
        assert f"${name}" not in reference


SKILL_REFERENCE_PATTERN = re.compile(r"\$[a-z][a-z0-9-]*")
