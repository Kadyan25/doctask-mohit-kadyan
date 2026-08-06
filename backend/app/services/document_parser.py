from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from docx import Document as DocxDocument
from pypdf import PdfReader


@dataclass
class ParsedLine:
    location: str
    text: str


@dataclass
class ParsedDocument:
    filename: str
    mime_type: str
    lines: list[ParsedLine]

    @property
    def full_text(self) -> str:
        return "\n".join(line.text for line in self.lines)


def _parse_text(path: Path, filename: str) -> ParsedDocument:
    lines = []
    for i, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if raw_line.strip():
            lines.append(ParsedLine(location=f"{filename}:{i}", text=raw_line))
    mime_type = "text/markdown" if path.suffix.lower() == ".md" else "text/plain"
    return ParsedDocument(filename=filename, mime_type=mime_type, lines=lines)


def _parse_pdf(path: Path, filename: str) -> ParsedDocument:
    reader = PdfReader(str(path))
    lines = []
    for page_num, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        for raw_line in text.splitlines():
            if raw_line.strip():
                lines.append(ParsedLine(location=f"{filename}:page{page_num}", text=raw_line))
    return ParsedDocument(filename=filename, mime_type="application/pdf", lines=lines)


def _parse_docx(path: Path, filename: str) -> ParsedDocument:
    doc = DocxDocument(str(path))
    lines = []
    for i, para in enumerate(doc.paragraphs, start=1):
        if para.text.strip():
            lines.append(ParsedLine(location=f"{filename}:para{i}", text=para.text))
    mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return ParsedDocument(filename=filename, mime_type=mime_type, lines=lines)


_PARSERS: dict[str, Callable[[Path, str], ParsedDocument]] = {
    ".md": _parse_text,
    ".txt": _parse_text,
    ".pdf": _parse_pdf,
    ".docx": _parse_docx,
}

SUPPORTED_EXTENSIONS = tuple(_PARSERS.keys())


def parsed_document_to_dict(doc: ParsedDocument) -> dict:
    """JSON-safe form for stashing a parsed document in LangGraph state."""
    return {
        "filename": doc.filename,
        "mime_type": doc.mime_type,
        "lines": [{"location": line.location, "text": line.text} for line in doc.lines],
    }


def parsed_document_from_dict(data: dict) -> ParsedDocument:
    return ParsedDocument(
        filename=data["filename"],
        mime_type=data["mime_type"],
        lines=[ParsedLine(location=item["location"], text=item["text"]) for item in data["lines"]],
    )


def parse_document(path: Path) -> ParsedDocument:
    suffix = path.suffix.lower()
    parser = _PARSERS.get(suffix)
    if parser is None:
        raise ValueError(
            f"unsupported document format: {suffix!r} (supported: {', '.join(SUPPORTED_EXTENSIONS)})"
        )
    return parser(path, path.name)
