"""Health check endpoint."""

from fastapi import APIRouter

from app.config import get_settings
from app.schemas import HealthOut

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    """Report that the API process is responsive."""
    settings = get_settings()
    return HealthOut(status="ok", provider=settings.llm_provider, model=settings.llm_model)
