"""
PDF Service — extracts text from uploaded PDF files using PyMuPDF.
Validates file type, size, and text content.
"""

import io
from fastapi import UploadFile, HTTPException
import fitz  # PyMuPDF

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


class NoPDFTextError(Exception):
    """Raised when a PDF contains no extractable text (scanned image PDF)."""
    pass


async def extract_text_from_pdf(file: UploadFile) -> str:
    """
    Read and validate an uploaded PDF, then extract all text content.

    Raises:
        HTTPException(400): for invalid file type or oversized file.
        NoPDFTextError: if the PDF contains no extractable text.
    """
    # Validate content type
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        # Also check filename extension as a fallback
        if not (file.filename or "").lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_file",
                    "message": "Only PDF files are accepted (max 10 MB).",
                },
            )

    raw_bytes = await file.read()

    # Validate size
    if len(raw_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_file",
                "message": "File exceeds the 10 MB limit. Please compress your PDF and try again.",
            },
        )

    # Validate it's actually a PDF by checking magic bytes
    if not raw_bytes.startswith(b"%PDF"):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_file",
                "message": "Only PDF files are accepted (max 10 MB).",
            },
        )

    # Extract text with PyMuPDF
    try:
        pdf_doc = fitz.open(stream=raw_bytes, filetype="pdf")
    except Exception:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_file",
                "message": "Could not read this PDF. It may be corrupted or password-protected.",
            },
        )

    pages_text: list[str] = []
    for page in pdf_doc:
        pages_text.append(page.get_text())

    pdf_doc.close()

    full_text = "\n".join(pages_text).strip()

    if not full_text or len(full_text) < 50:
        raise NoPDFTextError(
            "Upload a text-based PDF. Scanned image PDFs are not supported."
        )

    return full_text
