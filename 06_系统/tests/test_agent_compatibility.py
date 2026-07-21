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
    assert len(claude_names) == 12


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


SKILL_REFERENCE_PATTERN = re.compile(r"\$[a-z][a-z0-9-]*")
