from pathlib import Path

from docx import Document

from recruiter.files import extract_text, sha256


def test_extract_docx_and_hash(tmp_path: Path) -> None:
    path = tmp_path / "简历.docx"
    document = Document()
    document.add_paragraph("姓名：周宁")
    document.add_paragraph("目标岗位：产品经理")
    document.save(path)
    text = extract_text(path)
    assert "周宁" in text and "产品经理" in text
    assert len(sha256(path)) == 64


def test_extract_baseline_pdf() -> None:
    project = Path(__file__).resolve().parents[2]
    path = project / "Codex 个人招聘工作台｜整体架构与技术方案 V1.0.pdf"
    text = extract_text(path)
    assert "整体架构与技术方案" in text
