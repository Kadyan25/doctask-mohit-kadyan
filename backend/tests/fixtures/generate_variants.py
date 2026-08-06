"""One-off generator for the .pdf and .docx corpus fixtures — proves the parser
handles more than markdown, using real documents in those formats rather than
renamed text files. Run once from backend/: python tests/fixtures/generate_variants.py
"""

from pathlib import Path

from docx import Document
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

CORPUS = Path(__file__).parent / "corpus"


def make_pdf():
    source = (CORPUS / "status_week1.md").read_text(encoding="utf-8").splitlines()
    out_path = CORPUS / "status_week1.pdf"
    c = canvas.Canvas(str(out_path), pagesize=letter)
    _, height = letter
    y = height - 72
    for line in source:
        c.drawString(72, y, line)
        y -= 14
    c.save()
    print(f"wrote {out_path}")


def make_docx():
    source = (CORPUS / "change_request_001.md").read_text(encoding="utf-8").splitlines()
    out_path = CORPUS / "change_request_001.docx"
    doc = Document()
    for line in source:
        doc.add_paragraph(line)
    doc.save(str(out_path))
    print(f"wrote {out_path}")


if __name__ == "__main__":
    make_pdf()
    make_docx()
