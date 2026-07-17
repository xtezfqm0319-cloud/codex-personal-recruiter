from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path


SUPPORTED = {".txt", ".md", ".pdf", ".docx"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        raw = path.read_bytes()
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            from charset_normalizer import from_bytes

            match = from_bytes(raw).best()
            if match is None:
                raise ValueError(f"Cannot detect text encoding: {path}")
            return str(match)
    if suffix == ".pdf":
        from pypdf import PdfReader

        text = "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
        if not text.strip():
            raise ValueError("PDF has no extractable text layer; OCR is not included")
        return text
    if suffix == ".docx":
        from docx import Document

        return "\n".join(p.text for p in Document(str(path)).paragraphs)
    raise ValueError(f"Unsupported file type: {suffix}")


def safe_name(value: str) -> str:
    value = re.sub(r"[\\/:*?\"<>|]", "-", value.strip())
    value = re.sub(r"\s+", " ", value)
    return value.strip(". ")


def move_unique(source: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    target = destination
    counter = 2
    while target.exists():
        target = destination.with_name(f"{destination.stem}-{counter}{destination.suffix}")
        counter += 1
    return Path(shutil.move(str(source), str(target)))


def copy_unique(source: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    target = destination
    counter = 2
    while target.exists():
        target = destination.with_name(f"{destination.stem}-{counter}{destination.suffix}")
        counter += 1
    shutil.copy2(source, target)
    return target


def first_match(patterns: list[str], text: str) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip()
    return None
