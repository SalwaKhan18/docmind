"""Page-aware recursive text chunking."""

import re


def split_text(text: str, chunk_size: int = 800, overlap: int = 150) -> list[str]:
    """Split text on paragraph and sentence boundaries with bounded overlap."""
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("chunk_size must be positive and overlap smaller than chunk_size")
    normalized = re.sub(r"[ \t]+", " ", text).strip()
    if not normalized:
        return []
    paragraphs = re.split(r"\n\s*\n", normalized)
    sentences: list[str] = []
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        sentences.extend(
            part.strip() for part in re.split(r"(?<=[.!?])\s+", paragraph) if part.strip()
        )

    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > chunk_size:
            if current:
                chunks.append(current)
                current = ""
            step = chunk_size - overlap
            chunks.extend(
                sentence[start : start + chunk_size]
                for start in range(0, len(sentence), step)
            )
            continue
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) <= chunk_size:
            current = candidate
            continue
        if current:
            chunks.append(current)
        available_overlap = max(0, chunk_size - len(sentence) - 1)
        suffix = current[-min(overlap, available_overlap) :] if available_overlap else ""
        current = f"{suffix} {sentence}".strip() if suffix else sentence
    if current:
        chunks.append(current)
    return chunks


def chunk_pages(
    pages: list[tuple[int, str]], chunk_size: int = 800, overlap: int = 150
) -> list[dict[str, int | str]]:
    """Chunk extracted pages while retaining one-based page numbers."""
    chunks: list[dict[str, int | str]] = []
    for page_number, text in pages:
        chunks.extend(
            {"page": page_number, "text": chunk}
            for chunk in split_text(text, chunk_size=chunk_size, overlap=overlap)
        )
    return chunks
