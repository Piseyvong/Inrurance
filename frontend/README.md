# Claims Verification Frontend

React + TypeScript frontend for the health-insurance claims verification demo.
It connects to the existing FastAPI backend and presents claim intake,
document processing, deterministic verification, officer review, and audit
history.

## Safety Boundary

The UI does not use AI to approve or reject claims. It displays evidence,
extraction results, discrepancies, verification flags, deterministic
auto-approval status, and human-review routing.

OCR processing is handled by the backend. The dashboard intentionally does not
show technical OCR readiness cards.

## Folder Structure

- `src/api/`: typed backend API wrappers.
- `src/types/`: shared API response types.
- `src/components/`: reusable layout, alerts, badges, progress, and document cards.
- `src/pages/`: routed screens for dashboard, intake, documents, verification, review, and audit.
- `src/hooks/`: route parameter helpers.
- `src/utils/`: document and verification normalization helpers.

## Setup

```powershell
cd "D:\Work\Insurance AI Agent\frontend"
npm install
Copy-Item .env.example .env
npm run dev
```

Default `.env`:

```text
VITE_PORT=5175
VITE_API_BASE_URL=http://127.0.0.1:8001
```

## Backend Dependency

Start the backend first:

```powershell
cd "D:\Work\Insurance AI Agent"
docker compose up -d
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m scripts.run_backend
```

The sample backend `.env` uses `OCR_PROVIDER=kiri` for real Khmer-English OCR.
Use `OCR_PROVIDER=demo_text` only for synthetic local walkthroughs.

## Demo Flow

1. Open `http://127.0.0.1:5175`.
2. Confirm the dashboard renders the hero, summary cards, and recent-claims table.
3. Create a synthetic outpatient claim.
4. Upload the claim form, medical report, and receipt.
5. Use Process document for each upload.
6. Use Extract fields for each successfully processed document.
7. Open Verification and run deterministic verification.
8. Clean claims under `$50` can become `auto_approved` by deterministic rules.
9. Confirm mismatches show `Human review required`.
10. Open `http://127.0.0.1:5175/officer` for the officer portal queue.
11. Open Officer Review from that queue and write a review note.

## Recent Claims Activity

The backend exposes no claim-listing endpoint, so the dashboard's activity table
is a small browser-side log of claims created or opened in this session. Records
are written from real API responses only (never fabricated), and the table shows
an empty state until the first claim is created or opened.

## Build And Test

```powershell
npm run build
npm run test
```

## Known Limitations

- The frontend relies on the backend for authoritative validation.
- Synthetic `demo_text` processing is not real Khmer OCR.
- Kiri OCR quality and handwriting handling still need validation on more real documents.
- Local file storage and synchronous processing are demo constraints.
- No production authentication, role enforcement, malware scanning, or deployment hardening is included.
