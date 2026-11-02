"""Document validation, extraction, chunking, and indexing."""

import logging
import re
import uuid
from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import Document
from app.services import bm25_index
from app.services.chunking import chunk_pages
from app.services.embeddings import embed_texts
from app.services.vectorstore import add_chunks

logger = logging.getLogger(__name__)
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


def extract_pages(path: Path) -> list[tuple[int, str]]:
    """Extract text from a supported document with page numbers."""
    extension = path.suffix.lower()
    if extension == ".pdf":
        reader = PdfReader(str(path))
        return [(index, page.extract_text() or "") for index, page in enumerate(reader.pages, 1)]
    if extension == ".docx":
        document = DocxDocument(str(path))
        return [(1, "\n".join(p.text for p in document.paragraphs if p.text.strip()))]
    if extension in {".txt", ".md"}:
        return [(1, path.read_text(encoding="utf-8-sig"))]
    raise ValueError(f"Unsupported file extension: {extension}")


def sanitize_filename(filename: str) -> str:
    """Reduce an upload name to a safe basename."""
    name = Path(filename).name
    return re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip(" .") or "document"


def ingest_document(document_id: str, db: Session) -> None:
    """Process a stored upload and update its database ingestion state."""
    document = db.get(Document, document_id)
    if document is None:
        logger.error("Ingestion requested for missing document %s", document_id)
        return
    try:
        pages = extract_pages(Path(document.stored_path))
        settings = get_settings()
        chunks = chunk_pages(pages, settings.chunk_size, settings.chunk_overlap)
        if not chunks:
            raise ValueError("No extractable text was found in the document")
        records = []
        for index, chunk in enumerate(chunks):
            records.append(
                {
                    "id": f"{document_id}:{index}",
                    "text": str(chunk["text"]),
                    "metadata": {
                        "doc_id": document_id,
                        "filename": document.filename,
                        "page": int(chunk["page"]),
                        "chunk_index": index,
                    },
                }
            )
        embeddings = embed_texts([record["text"] for record in records])
        add_chunks(records, embeddings)
        bm25_index.upsert(records)
        document.chunk_count = len(records)
        document.status = "ready"
        document.error = None
        db.commit()
        logger.info("Ingested %s chunks from %s", len(records), document.filename)
    except Exception as exc:
        db.rollback()
        failed = db.get(Document, document_id)
        if failed:
            failed.status = "error"
            failed.error = str(exc)[:500]
            db.commit()
        logger.exception("Document ingestion failed for %s", document_id)
        raise


def new_document_id() -> str:
    """Generate an opaque document identifier."""
    return str(uuid.uuid4())
