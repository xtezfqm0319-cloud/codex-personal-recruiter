from __future__ import annotations

import argparse
import re
from pathlib import Path


SOURCE_DIRECTORY = Path(".agents/skills")
CLAUDE_DIRECTORY = Path(".claude/skills")
IGNORED_SOURCE_PARTS = {"agents"}
SKILL_REFERENCE = re.compile(r"\$([a-z][a-z0-9-]*)")


def transform_for_claude(path: Path, content: bytes) -> bytes:
    if path.suffix.lower() != ".md":
        return content
    text = content.decode("utf-8")
    return SKILL_REFERENCE.sub(r"/\1", text).encode("utf-8")


def expected_files(root: Path) -> dict[Path, bytes]:
    source = root / SOURCE_DIRECTORY
    if not source.exists():
        raise FileNotFoundError(f"Missing canonical skill directory: {source}")

    expected: dict[Path, bytes] = {}
    for skill_dir in sorted(path for path in source.iterdir() if path.is_dir()):
        if not (skill_dir / "SKILL.md").exists():
            continue
        for path in sorted(skill_dir.rglob("*")):
            if not path.is_file():
                continue
            relative_in_skill = path.relative_to(skill_dir)
            if any(part in IGNORED_SOURCE_PARTS for part in relative_in_skill.parts):
                continue
            target = root / CLAUDE_DIRECTORY / skill_dir.name / relative_in_skill
            expected[target] = transform_for_claude(path, path.read_bytes())
    return expected


def check(root: Path) -> list[str]:
    expected = expected_files(root)
    issues: list[str] = []
    for path, content in expected.items():
        if not path.exists():
            issues.append(f"missing: {path.relative_to(root)}")
        elif path.read_bytes() != content:
            issues.append(f"stale: {path.relative_to(root)}")

    target_root = root / CLAUDE_DIRECTORY
    actual = {path for path in target_root.rglob("*") if path.is_file()} if target_root.exists() else set()
    for path in sorted(actual - set(expected)):
        issues.append(f"unexpected: {path.relative_to(root)}")
    return issues


def sync(root: Path) -> int:
    expected = expected_files(root)
    changed = 0
    for path, content in expected.items():
        if not path.exists() or path.read_bytes() != content:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            changed += 1
    print(f"Claude Code skills synchronized: {len(expected)} files, {changed} changed")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronize canonical project skills to Claude Code project skills.")
    parser.add_argument("--root", default=".", help="Project root")
    parser.add_argument("--check", action="store_true", help="Check synchronization without writing")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if args.check:
        issues = check(root)
        if issues:
            print("Claude Code skill synchronization failed:")
            for issue in issues:
                print(f"- {issue}")
            return 1
        print("Claude Code skills are synchronized")
        return 0

    sync(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
