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

### Backend

Quickstart (local SQLite, no Docker/Postgres, no Tesseract/Azure OpenAI keys
needed — good for exercising the API/UI only):

```powershell
cd "Inrurance"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env
```

Then edit `.env` and set:

```text
DATABASE_URL=sqlite+aiosqlite:///./insurance_demo.db
OCR_PROVIDER=demo_text
```

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m scripts.run_backend
```

The backend serves on `http://127.0.0.1:8000` (Swagger UI at `/docs`).

For the full stack (real Postgres, real Tesseract OCR, real Azure OpenAI
extraction), instead of the SQLite/demo_text overrides above:

```powershell
docker compose up -d
```

and copy `.env.example` to `.env` as-is (leave `DATABASE_URL` pointed at
Postgres, `OCR_PROVIDER=tesseract`, and fill in `TESSERACT_CMD`,
`TESSERACT_TESSDATA_DIR`, and the `AZURE_OPENAI_*` values) before running
Alembic and the backend.

### Frontend

```powershell
cd "Inrurance\frontend"
npm install
copy .env.example .env
npm run dev
```

The frontend reads `VITE_PORT` from `frontend/.env` (default `5175`; set it to
`5173` if you need that port) and serves on `http://127.0.0.1:<VITE_PORT>`.
Make sure the backend's `CORS_ORIGINS` includes that origin.

## Production Deployment (VM)

The production stack runs in Docker: Postgres + the FastAPI backend (with
Tesseract and Poppler baked into the image) + the built React frontend served
by nginx. The backend creates its own tables on startup, so there is no
separate migration command, and Tesseract needs no install on the host.

```bash
# 1. Get the repo onto the VM and cd into it
cd /path/to/Inrurance

# 2. Create the production env file and fill in real values
cp .env.production.example .env.production
nano .env.production
```

Minimum values to set in `.env.production`:

- `POSTGRES_PASSWORD` — a real database password (required).
- `VITE_API_BASE_URL` — the backend's **public** address browsers reach,
  e.g. `http://your-server-ip:8011` (required). This is compiled into the
  frontend bundle at build time — changing it later requires a rebuild.
- `CORS_ORIGINS` — the browser-facing frontend origin,
  e.g. `http://your-server-ip:8086`.
- `AZURE_OPENAI_ENDPOINT` / `AZURE_OPENAI_API_KEY` / `AZURE_OPENAI_DEPLOYMENT`
  — Azure OpenAI credentials for real extraction. Leave them blank and the
  backend falls back to the local demo extractor.

Note: keep `OCR_PROVIDER=tesseract` and do **not** set `TESSERACT_CMD` or
`TESSERACT_TESSDATA_DIR` here — the backend image already points them at its
own Linux Tesseract install, and Windows paths copied from a local `.env` will
break OCR inside the container.

Build and start:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build

# Check status and logs
docker compose -f docker-compose.prod.yml --env-file .env.production ps
docker compose -f docker-compose.prod.yml --env-file .env.production logs -f backend

# Confirm the LLM connection (reports Azure verified, or demo mode when no key)
curl http://your-server-ip:8011/health/llm
```

Then open the frontend at `http://your-server-ip:8086`.

Redeploy after a code change:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

One caveat: the example ports (`BACKEND_PUBLISHED_PORT=8011`,
`FRONTEND_PUBLISHED_PORT=8086`) were chosen because ports 80 and 8000-8085
were already in use on the target VM. Confirm with `docker ps` /
`sudo ss -tlnp` before deploying, and if you change them, update
`VITE_API_BASE_URL` and `CORS_ORIGINS` to match.

## Environment Variables

- `BACKEND_HOST`, default `127.0.0.1`
- `BACKEND_PORT`, default `8000` for local development
- `DATABASE_URL` or `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `UPLOAD_DIR`, default `uploads`
- `PROCESSED_DIR`, default `processed_uploads`
- `MAX_UPLOAD_BYTES`, default `10485760`
- `OCR_PROVIDER`, default `tesseract`; set `demo_text` only for synthetic local API testing
- `TESSERACT_CMD`, optional absolute path to `tesseract.exe` on Windows
- `TESSERACT_LANGUAGES`, default `khm+eng`
- `TESSERACT_TESSDATA_DIR`, a directory containing `khm.traineddata` and `eng.traineddata`; use a path without spaces on Windows, such as `C:\tesseract-tessdata`
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

The real OCR provider is local Tesseract OCR configured for Khmer and English:

```python
import pytesseract
from PIL import Image

text = pytesseract.image_to_string(Image.open(file_path), lang="khm+eng")
```

The backend stores raw text, line text, line confidence, bounding boxes when
available, and the `tesseract` engine name in `ocr_runs`. PDF uploads are rendered
to page images before they are sent to Tesseract. `OCR_PROVIDER=demo_text` remains
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
- Evaluate Tesseract OCR against a larger real Khmer-English claims document set.
- Add malware scanning and stricter content inspection.
- Add richer officer correction workflows and immutable audit protections.
- Add a deterministic rules engine only when automatic approval is explicitly requested.
