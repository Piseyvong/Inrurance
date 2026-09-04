# Health Insurance Claims Verification Demo

AI-assisted backend demo for outpatient health insurance claim intake, document
OCR, structured extraction, deterministic verification, and officer review.

## Safety Boundary

The AI, OCR, and LLM never approve or reject claims. They may only extract
structured candidate fields from OCR text. Verification is deterministic and
routes missing documents, OCR failures, unclear values, mismatches, and invalid
formats to a human claims officer. Clean claims under `$50` can be auto-approved
only by the deterministic rules engine.

## Architecture

- `app/main.py` creates the FastAPI app and registers routers.
- `app/database.py` configures SQLAlchemy sessions.
- `app/config.py` loads environment-based settings.
- `app/models/` contains SQLAlchemy models.
- `app/schemas/` contains Pydantic API schemas.
- `app/routers/` exposes HTTP endpoints.
- `app/services/` contains testable business logic.
- `/officer` frontend route and `/officer/claims` API expose the officer queue.
- `alembic/versions/` contains database migrations.
- `uploads/` stores original uploaded documents locally.
- `processed_uploads/` stores temporary OCR-prepared files.
- `tests/` contains service-level tests with mocked OCR.

## Setup

```powershell
cd "D:\Work\Insurance AI Agent"
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
docker compose up -d
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m scripts.run_backend
```

If you use your own PostgreSQL, copy `.env.example` to `.env` and adjust the
database settings before running Alembic.

## Environment Variables

- `BACKEND_HOST`, default `127.0.0.1`
- `BACKEND_PORT`, default `8000` for local development
- `DATABASE_URL` or `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `UPLOAD_DIR`, default `uploads`
- `PROCESSED_DIR`, default `processed_uploads`
- `MAX_UPLOAD_BYTES`, default `10485760`
- `OCR_PROVIDER`, default `kiri`; set `demo_text` only for synthetic local API testing
- `AZURE_OPENAI_ENDPOINT`, Azure OpenAI endpoint from Microsoft Foundry
- `AZURE_OPENAI_API_KEY`, Azure OpenAI key for local testing
- `AZURE_OPENAI_DEPLOYMENT`, existing model deployment name from View deployments
- `LLM_REQUEST_TIMEOUT_SECONDS`, default `20`
- `LLM_MAX_RETRIES`, default `2`
- `CORS_ORIGINS`, optional comma-separated list

## API Flow

Open Swagger UI:

```text
http://127.0.0.1:8000/docs
```

Create a claim:

```powershell
$claim = curl.exe -s -X POST "http://127.0.0.1:8000/claims" `
  -H "Content-Type: application/json" `
  -d "{\"claimant_name\":\"Demo User\",\"policy_number\":\"POL-001\",\"incident_date\":\"2026-07-31\",\"claimed_amount\":50.00}" | ConvertFrom-Json
```

Create small synthetic files with valid file signatures:

```powershell
[IO.File]::WriteAllBytes("claim_form.pdf", [Text.Encoding]::ASCII.GetBytes("%PDF-1.4`nclaimant_name: Demo User`npolicy_number: POL-001`nincident_date: 2026-07-31`nclaimed_amount: 50.00"))
[IO.File]::WriteAllBytes("medical_report.pdf", [Text.Encoding]::ASCII.GetBytes("%PDF-1.4`nclaimant_name: Demo User`ntreatment_date: 2026-07-31`ndiagnosis: Flu"))
[IO.File]::WriteAllBytes("receipt.pdf", [Text.Encoding]::ASCII.GetBytes("%PDF-1.4`ntotal_amount: 50.00`nservice_date: 2026-07-31"))
```

Upload the three required documents:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/claims/$($claim.id)/documents" -F "doc_type=claim_form" -F "file=@claim_form.pdf;type=application/pdf"
curl.exe -X POST "http://127.0.0.1:8000/claims/$($claim.id)/documents" -F "doc_type=medical_report" -F "file=@medical_report.pdf;type=application/pdf"
curl.exe -X POST "http://127.0.0.1:8000/claims/$($claim.id)/documents" -F "doc_type=receipt" -F "file=@receipt.pdf;type=application/pdf"
```

Fetch claim and documents:

```powershell
curl.exe "http://127.0.0.1:8000/claims/$($claim.id)"
curl.exe "http://127.0.0.1:8000/claims/$($claim.id)/documents"
```

Process each document, replacing `DOCUMENT_ID` with the returned ids:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/documents/DOCUMENT_ID/process"
curl.exe "http://127.0.0.1:8000/documents/DOCUMENT_ID/ocr-runs"
curl.exe -X POST "http://127.0.0.1:8000/documents/DOCUMENT_ID/extract"
```

Run deterministic verification and retrieve the report:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/claims/$($claim.id)/verification"
curl.exe "http://127.0.0.1:8000/claims/$($claim.id)/verification"
curl.exe "http://127.0.0.1:8000/claims/$($claim.id)/audit"
```

Open officer queue claims:

```powershell
curl.exe "http://127.0.0.1:8000/officer/claims"
```

Record an officer review action:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/claims/$($claim.id)/review" `
  -H "Content-Type: application/json" `
  -d "{\"actor\":\"claims_officer\",\"action\":\"review_note\",\"details\":\"Synthetic demo claim reviewed.\"}"
```

## Tests

Use a writable pytest temp directory on this Windows setup:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp C:\tmp\insurance_ai_agent_pytest
```

## Azure OpenAI

The backend uses the OpenAI v1 Python client with an Azure OpenAI base URL:

```text
{AZURE_OPENAI_ENDPOINT}/openai/v1/
```

If the endpoint already ends in `/openai/v1/`, the app does not append it a
second time. Use the Azure OpenAI endpoint from Foundry, not the Foundry Project
endpoint.

Fill these values in `.env`:

```text
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_DEPLOYMENT=
```

Test the model connection after starting FastAPI:

```powershell
curl.exe "http://127.0.0.1:8000/health/llm"
```

The route sends a tiny non-sensitive prompt and verifies Azure returns non-empty
text. It never logs API keys, uploaded documents, claim documents, or complete
sensitive prompts.

## OCR Notes

The real OCR provider is Kiri OCR through the verified package API:

```python
from kiri_ocr import OCR

ocr = OCR(decode_method="accurate")
text, results = ocr.extract_text(file_path)
```

The backend stores raw text, line text, line confidence, bounding boxes when
available, and the `kiri_ocr` engine name in `ocr_runs`. PDF uploads are rendered
to page images before they are sent to Kiri OCR. `OCR_PROVIDER=demo_text` remains
available only for synthetic local workflow tests.

## Known Limitations

- Khmer OCR quality depends on fonts, scan quality, document layout, and model confidence.
- Handwriting is not reliably supported.
- Poor rotation, blur, low resolution, glare, and compression can lower OCR quality.
- PDF rendering depends on Poppler `pdftoppm` being available.
- Local file storage is for demo use only.
- FastAPI processing endpoints are synchronous in this MVP and should move to a queue for production.
- There is no production authentication or role enforcement yet.
- Uploaded medical documents are not encrypted at rest in this demo.
- The local fallback extractor is for demo testing when no LLM API key is configured.

## Production Improvements

- Add authentication and role separation for claimants and officers.
- Add encrypted object storage and retention policies.
- Replace synchronous processing with Celery, Dramatiq, or a managed queue.
- Evaluate Kiri OCR against a larger real Khmer-English claims document set.
- Add malware scanning and stricter content inspection.
- Add richer officer correction workflows and immutable audit protections.
- Add a deterministic rules engine only when automatic approval is explicitly requested.
