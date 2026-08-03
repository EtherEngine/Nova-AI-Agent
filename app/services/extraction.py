"""Text extraction for supported document types (PDF, Markdown, TXT)."""

from __future__ import annotations

import io

from pypdf import PdfReader

PDF_TYPES = {"application/pdf"}
TEXT_TYPES = {"text/plain", "text/markdown", "text/x-markdown"}
TEXT_EXTENSIONS = {".txt", ".md", ".markdown"}
PDF_EXTENSIONS = {".pdf"}

ALLOWED_EXTENSIONS = TEXT_EXTENSIONS | PDF_EXTENSIONS


class ExtractionError(Exception):
    """Raised when a document cannot be parsed into text."""


def _extension(filename: str) -> str:
    dot = filename.rfind(".")
    return filename[dot:].lower() if dot != -1 else ""


def extract_text(filename: str, content_type: str, data: bytes) -> str:
    """Extract plain text from an uploaded document.

    Selection is by extension (primary) with the MIME type as a hint. Raises
    :class:`ExtractionError` for unsupported or unreadable files.
    """
    extension = _extension(filename)

    if extension in PDF_EXTENSIONS or content_type in PDF_TYPES:
        try:
            reader = PdfReader(io.BytesIO(data))
            pages = [page.extract_text() or "" for page in reader.pages]
        except Exception as exc:  # pypdf raises various errors on bad input
            raise ExtractionError("PDF konnte nicht gelesen werden.") from exc
        text = "\n\n".join(pages).strip()
    elif extension in TEXT_EXTENSIONS or content_type in TEXT_TYPES:
        try:
            text = data.decode("utf-8").strip()
        except UnicodeDecodeError as exc:
            raise ExtractionError("Datei ist kein gültiges UTF-8.") from exc
    else:
        raise ExtractionError(f"Nicht unterstützter Dateityp: {extension or content_type!r}.")

    if not text:
        raise ExtractionError("Aus der Datei konnte kein Text extrahiert werden.")
    return text
