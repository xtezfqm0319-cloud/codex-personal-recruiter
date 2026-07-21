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
SKILL_REFERENCE_PATTERN = re.compile(r"\$[a-z][a-z0-9-]*")
