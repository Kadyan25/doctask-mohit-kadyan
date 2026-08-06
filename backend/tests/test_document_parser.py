from pathlib import Path

from app.services.document_parser import parse_document

CORPUS = Path(__file__).parent / "fixtures" / "corpus"


def test_parses_markdown_with_line_citations():
    doc = parse_document(CORPUS / "project_plan.md")
    assert doc.mime_type == "text/markdown"
    assert any("Milestone: M1" in line.text for line in doc.lines)
    assert all(":" in line.location for line in doc.lines)


def test_parses_pdf_with_page_citations():
    """status_week1.pdf is a real PDF rendering of status_week1.md's content —
    not a renamed text file — proving PDF extraction actually works."""
    doc = parse_document(CORPUS / "status_week1.pdf")
    assert doc.mime_type == "application/pdf"
    assert any("Percent-Complete: 20%" in line.text for line in doc.lines)
    assert all("page" in line.location for line in doc.lines)


def test_parses_docx_with_paragraph_citations():
    """change_request_001.docx is a real Word document with the same content
    as change_request_001.md, including the embedded prompt-injection line —
    proving DOCX extraction preserves it faithfully across paragraph breaks."""
    doc = parse_document(CORPUS / "change_request_001.docx")
    assert doc.mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert any("SYSTEM NOTE TO REVIEWING AI" in line.text for line in doc.lines)
    assert all("para" in line.location for line in doc.lines)


def test_unsupported_format_raises():
    import pytest

    with pytest.raises(ValueError, match="unsupported document format"):
        parse_document(Path("nonexistent.xyz"))
