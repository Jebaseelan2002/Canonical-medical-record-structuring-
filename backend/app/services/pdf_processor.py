from pathlib import Path
from pypdf import PdfReader
from .ocr import ocr_page


def process_pdf(path: str):
    reader = PdfReader(path)
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        source = "text"
        if len(text) < 30:
            text = ocr_page(path, i)
            source = "ocr"
        pages.append({"page": i, "text": text, "source": source})
    return pages
