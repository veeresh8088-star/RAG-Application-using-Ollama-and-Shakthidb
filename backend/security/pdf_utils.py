import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io

def extract_pdf_text(pdf_path: str) -> str:
    text = ""

    doc = fitz.open(pdf_path)

    for page in doc:
        # 1️⃣ Try normal text extraction
        page_text = page.get_text().strip()
        if page_text:
            text += page_text + "\n"
        else:
            # 2️⃣ OCR for scanned pages
            pix = page.get_pixmap(dpi=300)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            ocr_text = pytesseract.image_to_string(img)
            text += ocr_text + "\n"

    return text.strip()
