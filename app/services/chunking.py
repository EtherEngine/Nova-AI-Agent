"""Text chunking with character windows and overlap."""

from __future__ import annotations

DEFAULT_CHUNK_SIZE = 1000
DEFAULT_OVERLAP = 150


def chunk_text(
    text: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[str]:
    """Split text into overlapping chunks, preferring paragraph boundaries.

    A simple, dependency-free splitter: paragraphs are packed into windows of
    roughly ``chunk_size`` characters; oversized paragraphs are hard-split with
    ``overlap`` characters carried over between windows.
    """
    normalized = text.strip()
    if not normalized:
        return []
    if overlap >= chunk_size:
        overlap = chunk_size // 4

    paragraphs = [p.strip() for p in normalized.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""

    def flush() -> None:
        nonlocal current
        if current.strip():
            chunks.append(current.strip())
        current = ""

    for paragraph in paragraphs:
        if len(paragraph) > chunk_size:
            flush()
            start = 0
            while start < len(paragraph):
                chunks.append(paragraph[start : start + chunk_size])
                start += chunk_size - overlap
            continue
        if len(current) + len(paragraph) + 2 > chunk_size:
            flush()
        current = f"{current}\n\n{paragraph}".strip() if current else paragraph

    flush()
    return chunks
