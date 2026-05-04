import os


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp"}
MAX_OCR_CHARS = 12000
DEFAULT_TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]


def _normalize_engine(engine):
    if not engine:
        return None
    value = engine.strip().lower()
    if value in {"tesseract"}:
        return "tesseract"
    return None


def _truncate_text(text):
    if len(text) <= MAX_OCR_CHARS:
        return text
    return text[:MAX_OCR_CHARS]


def _unsupported_type_result(engine):
    return {
        "status": "skipped_unsupported",
        "engine": engine,
        "text": None,
        "message": "skipped unsupported file type",
    }


def _extract_with_tesseract(file_path):
    try:
        from PIL import Image
        import pytesseract
        from pytesseract import TesseractError
        from pytesseract.pytesseract import TesseractNotFoundError
    except ImportError:
        return {
            "status": "failed",
            "engine": "tesseract",
            "text": None,
            "message": "tesseract dependencies not installed",
        }

    tesseract_cmd = os.environ.get("TESSERACT_CMD", "").strip()
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    else:
        for candidate in DEFAULT_TESSERACT_PATHS:
            if os.path.exists(candidate):
                pytesseract.pytesseract.tesseract_cmd = candidate
                break

    try:
        with Image.open(file_path) as image:
            text = pytesseract.image_to_string(image) or ""
    except TesseractNotFoundError:
        return {
            "status": "failed",
            "engine": "tesseract",
            "text": None,
            "message": "tesseract binary not found on server (install it and set PATH or TESSERACT_CMD)",
        }
    except TesseractError as exc:
        return {
            "status": "failed",
            "engine": "tesseract",
            "text": None,
            "message": f"tesseract error: {exc}",
        }

    normalized_text = _truncate_text(text.strip())
    if not normalized_text:
        return {
            "status": "no_text_detected",
            "engine": "tesseract",
            "text": "",
            "message": "no text detected",
        }

    return {
        "status": "success",
        "engine": "tesseract",
        "text": normalized_text,
        "message": f"text extracted ({len(normalized_text)} chars)",
    }


def extract_evidence_text(file_path, filename, engine):
    if engine is None or str(engine).strip() == "":
        return {
            "status": "not_requested",
            "engine": None,
            "text": None,
            "message": "ocr not requested",
        }

    selected_engine = _normalize_engine(engine)
    if not selected_engine:
        return {
            "status": "failed",
            "engine": str(engine).strip().lower(),
            "text": None,
            "message": "unsupported ocr engine",
        }

    _root, extension = os.path.splitext(filename.lower())
    if extension not in IMAGE_EXTENSIONS:
        return _unsupported_type_result(selected_engine)

    if selected_engine == "tesseract":
        return _extract_with_tesseract(file_path)

    return {
        "status": "failed",
        "engine": selected_engine,
        "text": None,
        "message": "unsupported ocr engine",
    }
