from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


SUPPORTED = {".txt", ".md", ".pdf", ".docx"}
MIN_PAGE_INFORMATIVE_CHARS = 35
MAX_GARBAGE_RATIO = 0.08
_RAPID_OCR_ENGINE: Any | None = None


@dataclass(frozen=True)
class PageExtractionQuality:
    page: int
    text_layer_chars: int
    final_chars: int
    has_visual_content: bool
    used_ocr: bool
    status: str


@dataclass(frozen=True)
class ExtractionReport:
    status: str
    method: str
    page_count: int
    meaningful_pages: int
    complete_pages: int
    text_layer_pages: int
    ocr_pages: tuple[int, ...]
    unresolved_pages: tuple[int, ...]
    ocr_engine: str | None
    notes: tuple[str, ...]
    pages: tuple[PageExtractionQuality, ...]

    @property
    def complete(self) -> bool:
        return self.status == "通过"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TextExtractionResult:
    text: str
    report: ExtractionReport


class OCRUnavailableError(RuntimeError):
    """Raised when no supported local OCR engine can run."""


class TextExtractionIncompleteError(ValueError):
    """Raised when a document cannot be read completely enough for safe use."""

    def __init__(self, message: str, report: ExtractionReport):
        super().__init__(message)
        self.report = report


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _informative_chars(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9\u3400-\u9fff]", text))


def _garbage_ratio(text: str) -> float:
    if not text:
        return 0.0
    bad = sum(
        1
        for char in text
        if char == "\ufffd" or (ord(char) < 32 and char not in "\n\r\t") or 0xE000 <= ord(char) <= 0xF8FF
    )
    return bad / len(text)


def _page_is_complete(text: str) -> bool:
    return _informative_chars(text) >= MIN_PAGE_INFORMATIVE_CHARS and _garbage_ratio(text) <= MAX_GARBAGE_RATIO


def _page_has_visual_content(page: Any) -> bool:
    try:
        if len(page.images) > 0:
            return True
    except Exception:
        pass
    try:
        contents = page.get_contents()
        if contents is None:
            return False
        if isinstance(contents, list):
            size = sum(len(item.get_data()) for item in contents)
        else:
            size = len(contents.get_data())
        return size >= 80
    except Exception:
        return False


def _page_has_embedded_images(page: Any) -> bool:
    try:
        return len(page.images) > 0
    except Exception:
        return False


def _render_pdf_pages(path: Path, page_numbers: list[int], output_dir: Path) -> dict[int, Path]:
    try:
        import pymupdf
    except ImportError as exc:
        raise OCRUnavailableError("本地 OCR 缺少 PDF 页面渲染依赖 PyMuPDF；请重新安装项目依赖") from exc

    rendered: dict[int, Path] = {}
    document = pymupdf.open(path)
    try:
        for page_number in page_numbers:
            page = document.load_page(page_number - 1)
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(3, 3), alpha=False)
            target = output_dir / f"page-{page_number:04d}.png"
            pixmap.save(target)
            rendered[page_number] = target
    finally:
        document.close()
    return rendered


def _vision_binary() -> Path:
    source = Path(__file__).with_name("ocr_vision.swift")
    swiftc = shutil.which("swiftc")
    if platform.system() != "Darwin" or not swiftc or not source.exists():
        raise OCRUnavailableError("Apple Vision OCR 不可用")
    fingerprint = hashlib.sha256(source.read_bytes()).hexdigest()[:16]
    cache = Path(tempfile.gettempdir()) / "codex-personal-recruiter-ocr"
    cache.mkdir(parents=True, exist_ok=True)
    binary = cache / f"vision-ocr-{fingerprint}"
    if binary.exists():
        return binary
    module_cache = cache / "module-cache"
    module_cache.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["CLANG_MODULE_CACHE_PATH"] = str(module_cache)
    env["SWIFT_MODULECACHE_PATH"] = str(module_cache)
    completed = subprocess.run(
        [swiftc, str(source), "-O", "-o", str(binary)],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip().splitlines()[-1:]
        raise OCRUnavailableError(f"Apple Vision OCR 编译失败：{' '.join(detail)}")
    return binary


def _ocr_with_vision(images: dict[int, Path]) -> dict[int, str]:
    binary = _vision_binary()
    ordered = sorted(images.items())
    completed = subprocess.run(
        [str(binary), *(str(image) for _, image in ordered)],
        capture_output=True,
        text=True,
        timeout=max(120, len(ordered) * 45),
    )
    if completed.returncode != 0:
        raise OCRUnavailableError(f"Apple Vision OCR 执行失败：{completed.stderr.strip() or '未知错误'}")
    payload = json.loads(completed.stdout)
    return {page: str(payload.get(str(image), "")) for page, image in ordered}


def _tesseract_languages(executable: str) -> str:
    completed = subprocess.run([executable, "--list-langs"], capture_output=True, text=True, timeout=20)
    available = set(completed.stdout.splitlines()[1:]) if completed.returncode == 0 else set()
    preferred = [language for language in ("chi_sim", "eng") if language in available]
    return "+".join(preferred) if preferred else "eng"


def _ocr_with_tesseract(images: dict[int, Path]) -> tuple[dict[int, str], str]:
    executable = shutil.which("tesseract")
    if not executable:
        raise OCRUnavailableError("Tesseract OCR 不可用")
    languages = _tesseract_languages(executable)
    texts: dict[int, str] = {}
    for page, image in sorted(images.items()):
        completed = subprocess.run(
            [executable, str(image), "stdout", "-l", languages, "--psm", "6"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if completed.returncode != 0:
            raise OCRUnavailableError(f"Tesseract OCR 执行失败：{completed.stderr.strip() or '未知错误'}")
        texts[page] = completed.stdout
    return texts, f"Tesseract ({languages})"


def _ocr_with_rapidocr(images: dict[int, Path]) -> tuple[dict[int, str], str]:
    global _RAPID_OCR_ENGINE
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as exc:
        raise OCRUnavailableError("RapidOCR 不可用") from exc
    if _RAPID_OCR_ENGINE is None:
        _RAPID_OCR_ENGINE = RapidOCR()
    engine = _RAPID_OCR_ENGINE
    texts: dict[int, str] = {}
    for page, image in sorted(images.items()):
        result, _ = engine(str(image))
        lines = [str(item[1]) for item in (result or []) if len(item) >= 2 and str(item[1]).strip()]
        texts[page] = "\n".join(lines)
    return texts, "RapidOCR (本地ONNX)"


def _ocr_images(images: dict[int, Path]) -> tuple[dict[int, str], str]:
    backend = os.environ.get("RECRUITER_OCR_BACKEND", "auto").strip().lower()
    if backend in {"off", "none", "disabled"}:
        raise OCRUnavailableError("本地 OCR 已通过 RECRUITER_OCR_BACKEND 禁用")
    errors: list[str] = []
    if backend in {"auto", "rapidocr"}:
        try:
            return _ocr_with_rapidocr(images)
        except Exception as exc:
            errors.append(str(exc))
            if backend == "rapidocr":
                raise OCRUnavailableError(str(exc)) from exc
    if backend in {"auto", "vision"}:
        try:
            return _ocr_with_vision(images), "Apple Vision"
        except Exception as exc:
            errors.append(str(exc))
            if backend == "vision":
                raise OCRUnavailableError(str(exc)) from exc
    if backend in {"auto", "tesseract"}:
        try:
            return _ocr_with_tesseract(images)
        except Exception as exc:
            errors.append(str(exc))
    if backend not in {"auto", "rapidocr", "vision", "tesseract"}:
        errors.append(f"未知 OCR 后端：{backend}")
    raise OCRUnavailableError("；".join(errors) or "未找到可用的本地 OCR 引擎")


def _direct_report(method: str, text: str) -> ExtractionReport:
    complete = bool(text.strip())
    return ExtractionReport(
        status="通过" if complete else "待确认",
        method=method,
        page_count=1,
        meaningful_pages=1 if complete else 0,
        complete_pages=1 if complete else 0,
        text_layer_pages=1 if complete else 0,
        ocr_pages=(),
        unresolved_pages=() if complete else (1,),
        ocr_engine=None,
        notes=() if complete else ("文件没有可用文本",),
        pages=(),
    )


def _extract_pdf(path: Path) -> TextExtractionResult:
    from pypdf import PdfReader

    pages = list(PdfReader(str(path)).pages)
    if not pages:
        report = ExtractionReport("待确认", "PDF文本层", 0, 0, 0, 0, (), (), None, ("PDF 没有页面",), ())
        raise TextExtractionIncompleteError("PDF 没有页面", report)

    layer_texts = [(page.extract_text() or "").strip() for page in pages]
    visual_flags = [_page_has_visual_content(page) for page in pages]
    image_flags = [_page_has_embedded_images(page) for page in pages]
    ocr_candidates = [
        number
        for number, (text, has_visual, has_images) in enumerate(zip(layer_texts, visual_flags, image_flags), start=1)
        if has_visual and (not _page_is_complete(text) or has_images)
    ]
    ocr_texts: dict[int, str] = {}
    ocr_engine: str | None = None
    notes: list[str] = []
    if ocr_candidates:
        try:
            with tempfile.TemporaryDirectory(prefix="recruiter-ocr-") as temporary:
                images = _render_pdf_pages(path, ocr_candidates, Path(temporary))
                ocr_texts, ocr_engine = _ocr_images(images)
        except OCRUnavailableError as exc:
            notes.append(str(exc))

    final_texts: list[str] = []
    page_reports: list[PageExtractionQuality] = []
    unresolved: list[int] = []
    used_ocr: list[int] = []
    compared_with_ocr: list[int] = []
    meaningful_pages = 0
    complete_pages = 0
    text_layer_pages = 0
    for number, (layer, has_visual) in enumerate(zip(layer_texts, visual_flags), start=1):
        layer_complete = _page_is_complete(layer)
        if layer_complete:
            text_layer_pages += 1
        ocr = ocr_texts.get(number, "").strip()
        attempted_ocr = number in ocr_texts
        did_ocr = attempted_ocr and _informative_chars(ocr) > _informative_chars(layer)
        final = ocr if did_ocr else layer
        if attempted_ocr:
            compared_with_ocr.append(number)
        if did_ocr:
            used_ocr.append(number)
        meaningful = has_visual or bool(layer.strip()) or bool(ocr)
        if meaningful:
            meaningful_pages += 1
        complete = _page_is_complete(final)
        if complete:
            complete_pages += 1
            status = "完整"
        elif meaningful:
            unresolved.append(number)
            status = "待确认"
        else:
            status = "空白页"
        final_texts.append(final)
        page_reports.append(
            PageExtractionQuality(
                page=number,
                text_layer_chars=_informative_chars(layer),
                final_chars=_informative_chars(final),
                has_visual_content=has_visual,
                used_ocr=did_ocr,
                status=status,
            )
        )

    joined = "\n\n".join(f"--- 第 {number} 页 ---\n{text}" for number, text in enumerate(final_texts, start=1)).strip()
    total_chars = _informative_chars(joined)
    complete = meaningful_pages > 0 and not unresolved and total_chars >= max(35, meaningful_pages * 25)
    if not joined.strip():
        notes.append("PDF 文本层与本地 OCR 均未得到可用文本")
    if unresolved:
        notes.append("以下有内容页面未达到文本完整度阈值：" + "、".join(map(str, unresolved)))
    if ocr_candidates and not ocr_texts:
        notes.append("检测到疑似图片内容，但未能执行本地 OCR")
    if used_ocr and not unresolved:
        notes.append("低文本页面已由本地 OCR 补全")
    retained_layer = [page for page in compared_with_ocr if page not in used_ocr]
    if retained_layer:
        notes.append("含图片页面已执行 OCR 完整度对照，以下页面保留了更完整的文本层：" + "、".join(map(str, retained_layer)))
    method = "PDF文本层"
    if used_ocr and text_layer_pages:
        method = "PDF文本层 + 本地OCR"
    elif used_ocr:
        method = "本地OCR"
    report = ExtractionReport(
        status="通过" if complete else "待确认",
        method=method,
        page_count=len(pages),
        meaningful_pages=meaningful_pages,
        complete_pages=complete_pages,
        text_layer_pages=text_layer_pages,
        ocr_pages=tuple(used_ocr),
        unresolved_pages=tuple(unresolved),
        ocr_engine=ocr_engine,
        notes=tuple(dict.fromkeys(notes)),
        pages=tuple(page_reports),
    )
    if not complete:
        reason = "PDF 文本提取完整度不足"
        if unresolved:
            reason += f"（待确认页：{', '.join(map(str, unresolved))}）"
        raise TextExtractionIncompleteError(reason, report)
    return TextExtractionResult(joined, report)


def extract_text_with_report(path: Path) -> TextExtractionResult:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            from charset_normalizer import from_bytes

            match = from_bytes(raw).best()
            if match is None:
                raise ValueError(f"Cannot detect text encoding: {path}")
            text = str(match)
        report = _direct_report("直接读取", text)
    elif suffix == ".pdf":
        return _extract_pdf(path)
    elif suffix == ".docx":
        from docx import Document

        text = "\n".join(p.text for p in Document(str(path)).paragraphs)
        report = _direct_report("DOCX文本层", text)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")
    if not report.complete:
        raise TextExtractionIncompleteError("文件没有可用文本", report)
    return TextExtractionResult(text, report)


def extract_text(path: Path) -> str:
    return extract_text_with_report(path).text


def extraction_report_markdown(report: ExtractionReport, source: str, digest: str = "") -> str:
    ocr_pages = "、".join(map(str, report.ocr_pages)) or "无"
    unresolved = "、".join(map(str, report.unresolved_pages)) or "无"
    lines = [
        "# 文本提取质量报告",
        "",
        f"- 源文件：`{source}`",
        f"- SHA-256：`{digest}`" if digest else "- SHA-256：待计算",
        f"- 结论：{report.status}",
        f"- 处理方式：{report.method}",
        f"- OCR 引擎：{report.ocr_engine or '未使用'}",
        f"- 总页数：{report.page_count}",
        f"- 有内容页：{report.meaningful_pages}",
        f"- 完整页：{report.complete_pages}/{report.meaningful_pages or report.page_count}",
        f"- OCR 补全页：{ocr_pages}",
        f"- 待确认页：{unresolved}",
        "",
        "> “完整页”是文本提取的技术覆盖指标，不是候选人评分，也不代表内容事实已核验。",
    ]
    if report.pages:
        lines.extend(
            [
                "",
                "## 逐页检查",
                "",
                "| 页码 | 文本层有效字符 | 最终有效字符 | 疑似视觉内容 | 使用 OCR | 结论 |",
                "|---:|---:|---:|---|---|---|",
            ]
        )
        for page in report.pages:
            lines.append(
                f"| {page.page} | {page.text_layer_chars} | {page.final_chars} | "
                f"{'是' if page.has_visual_content else '否'} | {'是' if page.used_ocr else '否'} | {page.status} |"
            )
    if report.notes:
        lines.extend(["", "## 说明", "", *(f"- {note}" for note in report.notes)])
    return "\n".join(lines).rstrip() + "\n"


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
