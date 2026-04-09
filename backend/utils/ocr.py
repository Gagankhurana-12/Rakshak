import io
import os

# --- TESSERACT WINDOWS CONFIG ---
TESS_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.path.exists(TESS_PATH):
    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = TESS_PATH
    except Exception:
        pass
# --------------------------------

class OCRService:
    @staticmethod
    def extract_text_from_pdf(pdf_bytes: bytes) -> str:
        """Extract text from PDF using PyMuPDF (fitz). Falls back to OCR if needed."""
        try:
            import fitz  # PyMuPDF
            import pytesseract
            from PIL import Image
        except Exception as exc:
            raise RuntimeError(
                "OCR dependencies are missing. Install requirements before uploading documents."
            ) from exc

        text = ""
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page in doc:
            page_text = page.get_text()
            if page_text.strip():
                text += page_text + "\n"
            else:
                # OCR Fallback for scanned pages
                pix = page.get_pixmap()
                img = Image.open(io.BytesIO(pix.tobytes()))
                text += pytesseract.image_to_string(img) + "\n"
        doc.close()
        return text

    @staticmethod
    def extract_text_from_image(image_bytes: bytes) -> str:
        """Extract text from an image using Tesseract."""
        try:
            import pytesseract
            from PIL import Image
        except Exception as exc:
            raise RuntimeError(
                "OCR dependencies are missing. Install requirements before uploading documents."
            ) from exc

        img = Image.open(io.BytesIO(image_bytes))
        return pytesseract.image_to_string(img)

ocr_service = OCRService()
