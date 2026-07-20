from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    for directory in [
        "00_公司认知",
        "01_待处理/简历",
        "01_待处理/面试纪要",
        "01_待处理/待确认",
        "02_岗位",
        "03_简历库",
        "04_全局索引",
        "07_运行记录",
    ]:
        (tmp_path / directory).mkdir(parents=True, exist_ok=True)
    (tmp_path / "AGENTS.md").write_text("# rules\n", encoding="utf-8")
    (tmp_path / "00_公司认知" / "通用招聘标准.md").write_text("# 标准\n", encoding="utf-8")
    (tmp_path / "00_公司认知" / "个人招聘判断偏好.md").write_text(
        "# 个人招聘判断偏好\n\n## 已确认招聘偏好\n\n暂无。\n",
        encoding="utf-8",
    )
    (tmp_path / "04_全局索引" / "待确认事项.md").write_text("# 待确认事项\n", encoding="utf-8")
    (tmp_path / "07_运行记录" / "actions.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "07_运行记录" / "errors.jsonl").write_text("", encoding="utf-8")
    return tmp_path
