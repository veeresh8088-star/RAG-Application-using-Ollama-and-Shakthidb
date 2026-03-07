import PyPDF2
import pytesseract
from pdf2image import convert_from_path
from PIL import Image


def read_pdf(file_path):
    text = ""

    # 1️⃣ Try normal text extraction
    try:
        with open(file_path, "rb") as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted
    except:
        pass

    # 2️⃣ If no text → use OCR
    if not text.strip():
        images = convert_from_path(file_path)

        for image in images:
            text += pytesseract.image_to_string(image)

    return text.strip()
