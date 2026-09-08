from pdf2image import convert_from_path
import pytesseract


def ocr_page(pdf_path: str, page_number: int) -> str:
    try:
        images = convert_from_path(pdf_path, first_page=page_number, last_page=page_number, dpi=180)
        return pytesseract.image_to_string(images[0]).strip() if images else ""
    except Exception as exc:
        return f"[OCR unavailable: {exc}]"
