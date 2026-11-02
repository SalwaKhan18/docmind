"""Document upload, status, and deletion endpoints."""

import logging
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import Document, SessionLocal, get_db
from app.schemas import DocumentOut, UploadOut
from app.services import bm25_index
from app.services.ingestion import SUPPORTED_EXTENSIONS, ingest_document, sanitize_filename
from app.services.vectorstore import delete_document as delete_vectors

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def _process_upload(document_id: str) -> None:
    """Run background ingestion with an independent database session."""
    db = SessionLocal()
    try:
        ingest_document(document_id, db)
    except Exception:
        logger.exception("Background ingestion failed for document %s", document_id)
    finally:
        db.close()


@router.post("", response_model=UploadOut, status_code=202)
async def upload_documents(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
) -> UploadOut:
    """Validate uploads, store them, and schedule document ingestion."""
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required")
    settings = get_settings()
    upload_dir = settings.data_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    accepted: list[Document] = []
    saved_paths: list[Path] = []
    try:
        for upload in files:
            original_name = upload.filename or ""
            extension = Path(original_name).suffix.lower()
            if extension not in SUPPORTED_EXTENSIONS:
                raise HTTPException(
                    status_code=415,
                    detail=f"Unsupported file type: {extension or 'unknown'}",
                )
            content = await upload.read(MAX_UPLOAD_BYTES + 1)
            if len(content) > MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"{sanitize_filename(original_name)} exceeds the 20 MB limit",
                )
            document_id = str(uuid4())
            filename = sanitize_filename(original_name)
            stored_path = upload_dir / f"{document_id}{extension}"
            stored_path.write_bytes(content)
            saved_paths.append(stored_path)
            document = Document(
                id=document_id,
                filename=filename,
                stored_path=str(stored_path),
                status="processing",
                chunk_count=0,
            )
            db.add(document)
            accepted.append(document)
        db.commit()
        for document in accepted:
            db.refresh(document)
            background_tasks.add_task(_process_upload, document.id)
        return UploadOut(documents=[DocumentOut.model_validate(doc) for doc in accepted])
    except HTTPException:
        db.rollback()
        for path in saved_paths:
            path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        db.rollback()
        for path in saved_paths:
            path.unlink(missing_ok=True)
        logger.exception("Upload storage failed")
        raise HTTPException(
            status_code=500, detail="Could not store uploaded documents"
        ) from exc
    finally:
        for upload in files:
            await upload.close()


@router.get("", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db)) -> list[DocumentOut]:
    """Return all documents, including their ingestion status."""
    return [
        DocumentOut.model_validate(doc)
        for doc in db.query(Document).order_by(Document.created_at.desc()).all()
    ]


@router.delete("/{document_id}", status_code=204)
def remove_document(document_id: str, db: Session = Depends(get_db)) -> None:
    """Delete a document and its stored, vector, and keyword-index data."""
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    delete_vectors(document_id)
    bm25_index.remove_document(document_id)
    stored_path = Path(document.stored_path).resolve()
    uploads_root = (get_settings().data_dir / "uploads").resolve()
    if stored_path.parent == uploads_root and stored_path.exists():
        stored_path.unlink()
    db.delete(document)
    db.commit()
