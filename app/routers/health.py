from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.config import get_settings
from app.database import engine
from app.services.llm_extraction import LLMServiceError, test_azure_openai_connection

router = APIRouter()


@router.get("/health")
async def health_check():
    """Return API, database, and OCR-provider status for demos."""

    settings = get_settings()
    response = {
        "api": "ok",
        "database": "ok",
        "ocr_provider": settings.ocr_provider,
        "backend_status": "ready",
        "message": "Backend and database are reachable.",
    }
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:
        # The dashboard needs to distinguish "FastAPI is down" from
        # "FastAPI is up but PostgreSQL is unavailable", so health returns a
        # successful HTTP response with a degraded database state.
        response["database"] = "error"
        response["backend_status"] = "database_unavailable"
        response["message"] = _safe_database_error(exc)

    return response


def _safe_database_error(exc: Exception) -> str:
    """Return a useful database error without exposing credentials."""

    message = str(exc).splitlines()[0]
    return message or "Database connection failed."


@router.get("/health/llm")
def llm_health_check():
    """Verify Azure OpenAI connectivity with a tiny non-sensitive prompt."""

    try:
        return {"llm": "ok", **test_azure_openai_connection()}
    except LLMServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.public_message) from exc
