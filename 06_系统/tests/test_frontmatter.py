from pathlib import Path

from recruiter.frontmatter import read_markdown, write_markdown


def test_frontmatter_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "record.md"
    write_markdown(path, {"name": "张三", "reusable": False, "sources": ["a.txt"]}, "# 正文\n")
    data, body = read_markdown(path)
    assert data == {"name": "张三", "reusable": False, "sources": ["a.txt"]}
    assert body.startswith("# 正文")
