"""Safe, structured diagnostics for OCR, model extraction, and verification."""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from app.config import get_settings


def record_processing_result(stage: str, *, claim_id: int, document_id: int | None = None,
                             doc_type: str | None = None, outcome: str, cause: str,
                             details: dict[str, Any] | None = None) -> None:
    """Append one privacy-safe JSONL record; logging never blocks claim processing.

    The log deliberately excludes raw OCR text, extracted values, uploaded file
    paths, credentials, and request prompts. It is intended to answer whether a
    result was caused by document quality, model availability, or policy rules.
    """

    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "claim_id": claim_id,
        "document_id": document_id,
        "document_type": doc_type,
        "outcome": outcome,
        "cause": cause,
        "details": details or {},
    }
    try:
        path: Path = get_settings().processing_log_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
    except OSError:
        # Diagnostics must never make a customer claim fail.
        pass
