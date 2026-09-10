# Claim History and Customer Results Design

## Purpose

Make an existing claim navigable as a persisted lifecycle, present a short bilingual result to customers, preserve full OCR and rule evidence for officers, and prepare a reliable two-claim customer demonstration without confusing evidence quality with claim eligibility.

## Non-negotiable business rules

- OCR and LLM output are evidence, not claim decisions.
- Evidence quality and claim eligibility are separate determinations.
- Low or unavailable evidence confidence must stop automatic approval and route the claim to human validation. It must never cause an automatic rejection.
- An amount above an automatic-approval threshold routes to human review; it is not a rejection.
- Rejection is allowed only when reliable evidence proves an explicit configured policy/business-rule failure or an authorized officer records that decision.
- Opening historical stages is read-only and must not rerun OCR, extraction, compliance, risk screening, or decision logic.
- Every customer-facing and officer-facing endpoint must enforce claim ownership and role authorization on the server.

## Confirmed language behavior

Customer result pages open in English. A visible `English | ខ្មែរ` control switches the complete customer result card to Khmer and remembers the choice in browser storage. Both language variants are returned as approved customer-safe messages; the frontend does not translate technical reason codes itself. Officer technical workspaces remain English for this release.

## Customer and officer information boundary

### Customer

The customer sees only:

- claim number and current lifecycle stage;
- a customer-safe status;
- one to three short sentences explaining the real issue at document/category level;
- the next authorized action, such as replacing one document or returning to the claim;
- original documents they uploaded, without internal storage paths.

The customer must not receive raw OCR text, cleaned OCR text, extraction mappings, field confidence, OCR line/page references, prompt or semantic reasoning, evidence-score internals, raw rule results, risk checks, internal notes, or officer-only decision controls.

### Officer and administrator

The officer workspace retains:

- authorized previews of every original uploaded document;
- raw and cleaned Tesseract text;
- OCR document confidence and configured threshold;
- extracted and normalized values;
- source text, page/line references, and semantic interpretation;
- missing, unclear, conflicting, and corrected fields;
- policy, consistency, risk, and verification checks;
- persisted decisions, actors, timestamps, notes, and audit history.

## Persisted lifecycle model

The backend derives lifecycle stages from existing claim, document, OCR-run, extraction, rule-result, decision, and audit records. A stage is never completed because a user clicked it.

Each stage returned to the frontend has:

```text
key: policy | documents | extraction | compliance | decision
state: completed | current | pending | failed | needs_attention
available: boolean
href: role-safe route or null
label_en: string
label_km: string
summary_en: string or null
summary_km: string or null
completed_at: timestamp or null
```

Stage derivation:

- `policy` is available when a policy match/version is persisted.
- `documents` is available after at least one authorized upload and completed when all required documents exist.
- `extraction` is completed when every required document has a successful persisted OCR/extraction result; it is failed or needs attention when a persisted OCR/extraction failure exists.
- `compliance` is completed when persisted rule results exist for the current evidence set.
- `decision` is completed only when a persisted final decision exists. It is current and available when officer review is pending and a role-appropriate review/status page exists.
- Future stages have `available=false` and no route.

The frontend renders available stages as links with keyboard focus and an icon plus text state. Pending stages use disabled semantics, not click handlers on `<div>` elements.

## Routes and read-versus-run separation

Customer routes remain scoped to the same claim ID:

- `/claims/:claimId/documents` — upload while permitted; read-only originals for historical claims.
- `/claims/:claimId/history/policy` — policy/product/version summary.
- `/claims/:claimId/history/extraction` — customer-safe processing outcome only, never OCR internals.
- `/claims/:claimId/history/compliance` — customer-safe validation outcome only.
- `/claims/:claimId/history/decision` — persisted customer decision/status.

Officer routes reuse `/officer/claims/:claimId` and its evidence tabs, adding direct stage/tab links where useful. Audit history remains officer/admin only.

GET endpoints return persisted results only. POST processing endpoints remain separate and are invoked only by the intentional intake workflow. A historical page mount or lifecycle click must never issue a processing POST.

## Customer outcome contract

The backend produces a role-safe `customer_result` from deterministic facts:

```text
code: AUTO_APPROVED | NEEDS_DOCUMENT_RESUBMISSION | PENDING_MANUAL_REVIEW | POLICY_NOT_COVERED | REJECTED
final: boolean
title_en / title_km
message_en / message_km
next_action: replace_document | view_claim | await_review | none
document_type: string or null
decided_at: timestamp or null
claim_amount: decimal or null
payable_amount: decimal or null
```

Classification order:

1. A persisted authorized final rejection produces `REJECTED`.
2. A reliable explicit coverage failure produces `POLICY_NOT_COVERED`.
3. Correctable unreadable or missing document evidence produces `NEEDS_DOCUMENT_RESUBMISSION`.
4. Conflicts, an amount above the automatic threshold, uncertain evidence that cannot be safely self-corrected, or other review-required results produce `PENDING_MANUAL_REVIEW`.
5. A persisted deterministic approval produces `AUTO_APPROVED`.

Technical reason codes remain stored for officers. Customer messages may name the affected document and broad problem—unreadable, incomplete, or inconsistent—but never expose confidence numbers or source-line internals.

## Explanation layer

Deterministic code selects the outcome, failed-check category, affected document, and next action. The LLM may convert only that allow-listed structure into concise English and Khmer wording. It cannot change the outcome, add a reason, decide coverage, or decide approval/rejection.

If the LLM is unavailable, deterministic bilingual templates provide the same safe result. The message is persisted or deterministically reproducible so opening history never triggers a new decision or materially different explanation.

## State-aware intake UI

The documents page uses persisted claim and document states:

- before processing: all required documents are ready and processing will start automatically;
- OCR/extraction running: documents are being processed;
- compliance running: extraction completed and checks are in progress;
- pending officer: automated checks are complete and the claim is awaiting review;
- completed: processing is complete and lifecycle stages can be reviewed;
- failed/needs attention: a safe retry or replacement action is offered when authorized.

Document cards display real `ocr_status`, `extraction_status`, and `verification_status`. A completed historical claim never displays `Queued / Not Started`. The “Use synthetic or anonymised documents only” banner and other explicit demo/synthetic labeling are removed from the customer claim screen as requested.

## OCR diagnostic findings for supplied photos

The three supplied images were run directly through the configured `TesseractOCRProvider` with `khm+eng`, OEM 3, PSM 4, and post-processing disabled so the measurement represents raw Tesseract evidence:

- claim form: succeeded, 42 normalized lines, average confidence about 0.7823;
- invoice: succeeded, 39 normalized lines, average confidence about 0.6530;
- medical report: succeeded, 46 normalized lines, average confidence about 0.7046.

The images are not blank and Tesseract does not return zero document confidence. All three measurements are below the configured 0.80 automatic threshold. The visible `0` field value is a presentation/data-semantics problem where unavailable or LLM/field confidence is displayed as if it were OCR confidence; zero/non-positive unavailable confidence must render as “Not available.”

The supplied documents also conflict and cannot form an approvable claim set:

- claim form: SOK RATHANA, policy HIC-2024-001258, incident 20 Sep 2024;
- invoice: SOK NASREY, policy CLI-789456123, invoice 12 Apr 2025;
- medical report: SREY NARITA, consultation 15 Jan 2024.

These mismatches must generate a human-review outcome, not an OCR rejection. The demo approval fixture must use documents with consistent claimant, policy, incident/service dates, provider, and amount.

## Demo-data reset

After implementation and verification, remove existing claim-processing history in one transaction, scoped only to claim-dependent records: audit entries, decisions, checks, rule results, extracted fields, OCR runs, document rows/files as configured, notes, and claims. Preserve users, products, policy documents, and issued customer policies.

Seed exactly two clearly labeled customer-visible scenarios without explicit synthetic/demo warnings in the UI:

1. An approved claim with mutually consistent evidence and a persisted deterministic final approval.
2. A rejected claim backed by reliable evidence and a persisted authorized officer or explicit policy decision; low OCR confidence must not be its rejection reason.

Before deletion, report the exact counts and target tables/files. After deletion and seeding, verify the counts and both claim histories. This reset occurs only after the feature and automated tests pass.

## Chatbot behavior

Visitor mode provides general policy information and consultation actions without claiming personal access. Authenticated customer mode may return customer-safe policy and claim status only. Officer internals, OCR evidence, raw rules, and other customers' records are never exposed. Login/account actions follow the actual session and role.

## Error handling

- Missing persisted stage data produces an unavailable/disabled stage, never an empty fabricated result.
- Failed OCR is inspectable by officers and customer-safe for customers.
- Failed bilingual explanation generation falls back to deterministic templates.
- Unauthorized or cross-customer claim access returns not found/forbidden server-side and protected frontend routes redirect to the correct role home.
- Processing failures preserve the original documents and audit trail.

## Verification strategy

Backend tests cover lifecycle derivation for new, OCR-complete, pending-officer, completed, and failed-OCR claims; classification boundaries; low confidence never rejecting; persisted decision history; bilingual safe responses; and ownership/role filtering.

Frontend tests cover accessible lifecycle links and disabled future stages, same-claim routing, no mutation calls during historical navigation, English/Khmer switching, customer technical-data exclusion, officer technical-data inclusion, original-document access, state-aware processing copy, document statuses, protected routes, and logout.

End-to-end verification covers customer upload-to-result, officer review-to-decision, historical navigation, original document preview, the two seeded claims, responsive layouts, and visitor/customer chatbot behavior. The final check uses the running frontend and backend with no unexpected console or API errors.

## Out of scope

- Replacing Tesseract with a different OCR engine.
- Letting an LLM determine evidence thresholds, policy coverage, approval, or rejection.
- Exposing officer evidence internals to customers.
- Redesigning the policy, product, or user-account database architecture.
