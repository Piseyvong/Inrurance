# Claim History and Customer Results Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a role-safe, bilingual customer claim result and navigable persisted lifecycle while preserving complete Tesseract and decision evidence for officers, then reset demo claims to one approved and one genuinely rejected example.

**Architecture:** A backend `claim_history_service` derives lifecycle and customer outcomes from persisted policy, document, OCR, extraction, rule, decision, and audit records. Customer endpoints return a deliberately narrow schema; officer endpoints continue returning full technical evidence. React uses one lifecycle component with role-safe routes, English-first localized result cards, and GET-only history pages.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy async, Alembic, pytest; React 19, TypeScript, React Router 7, Vitest/Testing Library, Vite; Tesseract `khm+eng`.

**Spec:** `docs/superpowers/specs/2026-09-10-claim-history-customer-results-design.md`

## Global Constraints

- OCR and LLM output are evidence, not claim decisions.
- Low or unavailable evidence confidence routes to human validation and never causes automatic rejection.
- Rejection requires reliable policy evidence or an authorized officer decision.
- Historical GET requests never run OCR, extraction, compliance, risk, or decision mutations.
- Customer APIs never return OCR text, confidence, source lines, semantic reasoning, raw rule data, internal notes, or risk internals.
- Customer result language defaults to English and supports a remembered Khmer mode.
- Preserve original uploads and enforce claim ownership and role authorization server-side.
- Do not add another frontend icon or design-system dependency.
- Do not commit `.env`, uploads, processed files, logs, database files, or `tessdata` binaries.
- The data reset runs only after every verification gate passes and must preserve users, products, policy wording, and issued policies.

---

### Task 1: Restore a Trustworthy Test Baseline

**Files:**
- Modify: `tests/conftest.py`
- Modify: `tests/test_intake.py`
- Modify: `tests/test_processing_and_verification.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: current async service signatures such as `create_claim_record(payload, db: AsyncSession)` and `run_verification(claim_id, db: AsyncSession)`.
- Produces: an async-compatible test suite and repository-local pytest temp base.

- [ ] **Step 1: Write/convert a failing async service test**

```python
@pytest.mark.anyio
async def test_claim_creation_writes_audit_event(async_db_session):
    claim = await create_claim_record(ClaimCreate(claimant_name="Sokha Demo", policy_number="POL-001"), async_db_session)
    audit = (await async_db_session.execute(select(AuditLog).where(AuditLog.claim_id == claim.id))).scalar_one()
    assert audit.action == "claim_created"
```

- [ ] **Step 2: Run the converted test and confirm the current fixture/signature failure**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_intake.py::test_claim_creation_writes_audit_event --basetemp=.pytest-tmp -q`

Expected: FAIL because `async_db_session` is not yet provided or the old synchronous fixture is incompatible.

- [ ] **Step 3: Add a real async SQLite fixture and migrate old service tests**

```python
@pytest.fixture
async def async_db_session(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        yield session
    await engine.dispose()
```

Use `pytest.mark.anyio`, await async services, and query through `await session.execute(...)`. Add `.pytest-tmp/` and `tessdata/` to `.gitignore`.

- [ ] **Step 4: Verify the complete backend baseline**

Run: `.\.venv\Scripts\python.exe -m pytest --basetemp=.pytest-tmp -q`

Expected: all existing backend tests pass with no coroutine warnings.

- [ ] **Step 5: Commit the baseline repair**

```powershell
git add .gitignore tests/conftest.py tests/test_intake.py tests/test_processing_and_verification.py
git commit -m "test: align claim suite with async services"
```

### Task 2: Derive Lifecycle and Customer Outcomes Deterministically

**Files:**
- Create: `app/services/claim_history_service.py`
- Create: `app/schemas/claim_history.py`
- Create: `tests/test_claim_history_service.py`
- Modify: `app/services/verification_service.py`

**Interfaces:**
- Produces: `build_claim_history(claim_id: int, actor: User, db: AsyncSession) -> ClaimHistoryRead`.
- Produces: `classify_customer_result(claim, documents, rules, decisions, policy) -> CustomerResultRead`.
- Produces: `LifecycleStageRead` and `CustomerResultRead` Pydantic models matching the design spec.

- [ ] **Step 1: Write lifecycle classification tests first**

```python
@pytest.mark.anyio
@pytest.mark.parametrize((fixture_name, expected), [
    ("new_upload", ["completed", "completed", "current", "pending", "pending"]),
    ("ocr_finished", ["completed", "completed", "completed", "current", "pending"]),
    ("pending_officer", ["completed", "completed", "completed", "completed", "current"]),
    ("historical_complete", ["completed"] * 5),
    ("failed_ocr", ["completed", "completed", "failed", "pending", "pending"]),
])
async def test_lifecycle_is_derived_from_persisted_records(fixture_name, expected, claim_scenario, customer_user, async_db_session):
    claim = await claim_scenario(fixture_name)
    history = await build_claim_history(claim.id, customer_user, async_db_session)
    assert [stage.state for stage in history.stages] == expected
```

Add a separate test that calls `build_claim_history` twice and asserts OCR-run, rule-result, decision, and audit counts remain unchanged.

- [ ] **Step 2: Run lifecycle tests and verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_claim_history_service.py -q --basetemp=.pytest-tmp`

Expected: FAIL because `claim_history_service` and schemas do not exist.

- [ ] **Step 3: Implement lifecycle schemas and read-only derivation**

```python
class LifecycleStageRead(BaseModel):
    key: Literal["policy", "documents", "extraction", "compliance", "decision"]
    state: Literal["completed", "current", "pending", "failed", "needs_attention"]
    available: bool
    href: str | None
    label_en: str
    label_km: str
    summary_en: str | None = None
    summary_km: str | None = None
    completed_at: datetime | None = None


class CustomerResultRead(BaseModel):
    code: Literal["AUTO_APPROVED", "NEEDS_DOCUMENT_RESUBMISSION", "PENDING_MANUAL_REVIEW", "POLICY_NOT_COVERED", "REJECTED"]
    final: bool
    title_en: str
    title_km: str
    message_en: str
    message_km: str
    next_action: Literal["replace_document", "view_claim", "await_review", "none"]
    document_type: str | None = None
    decided_at: datetime | None = None
    claim_amount: Decimal | None = None
    payable_amount: Decimal | None = None
```

Derive state solely from persisted rows and perform no writes or commits inside the history builder.

- [ ] **Step 4: Write and run customer-outcome boundary tests**

```python
def test_low_ocr_quality_never_classifies_as_rejected():
    result = classify_customer_result(fixture(low_ocr=True, final_decision=None))
    assert result.code in {"NEEDS_DOCUMENT_RESUBMISSION", "PENDING_MANUAL_REVIEW"}
    assert "confidence" not in result.message_en.lower()

def test_amount_above_auto_limit_routes_to_manual_review():
    result = classify_customer_result(fixture(amount=1250, threshold=50, evidence_reliable=True))
    assert result.code == "PENDING_MANUAL_REVIEW"

def test_authorized_final_rejection_is_customer_rejected():
    result = classify_customer_result(fixture(final_decision="rejected", authority="human"))
    assert result.code == "REJECTED"
```

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_claim_history_service.py -q --basetemp=.pytest-tmp`

Expected: PASS.

- [ ] **Step 5: Commit deterministic history logic**

```powershell
git add app/services/claim_history_service.py app/schemas/claim_history.py app/services/verification_service.py tests/test_claim_history_service.py
git commit -m "feat: derive persisted claim lifecycle outcomes"
```

### Task 3: Add Role-Safe History APIs

**Files:**
- Modify: `app/routers/claims.py`
- Modify: `app/routers/review.py`
- Modify: `app/main.py`
- Create: `tests/test_claim_history_api.py`

**Interfaces:**
- Consumes: `build_claim_history(...)` from Task 2.
- Produces: `GET /claims/{claim_id}/history` returning `ClaimHistoryRead` with customer-safe content.
- Produces: officer workspace history fields without changing existing original-document authorization.

- [ ] **Step 1: Write failing API security and response-shape tests**

```python
def test_customer_history_omits_technical_evidence(client, customer_headers, owned_claim):
    body = client.get(f"/claims/{owned_claim.id}/history", headers=customer_headers).json()
    serialized = json.dumps(body).lower()
    for forbidden in ("raw_text", "cleaned_text", "confidence", "source_text", "supporting_line_refs", "semantic_reason", "rule_results"):
        assert forbidden not in serialized

def test_customer_cannot_open_another_customers_history(client, customer_headers, other_claim):
    assert client.get(f"/claims/{other_claim.id}/history", headers=customer_headers).status_code == 404
```

Add a mutation-safety test that snapshots row counts before and after GET.

- [ ] **Step 2: Run API tests and verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_claim_history_api.py -q --basetemp=.pytest-tmp`

Expected: FAIL with 404 for the missing history route.

- [ ] **Step 3: Implement the authenticated history endpoint**

```python
@router.get("/{claim_id}/history", response_model=ClaimHistoryRead)
async def get_claim_history(claim_id: int, x_demo_user: int = Header(...), db: AsyncSession = Depends(get_db)):
    user = await actor(db, x_demo_user)
    claim = await get_claim_or_404(claim_id, db)
    if user.role == "customer" and claim.user_id != user.id:
        raise HTTPException(404, "Claim not found")
    return await build_claim_history(claim_id, user, db)
```

Keep full technical data under officer-authorized endpoints. Do not serialize it into the customer schema and rely on frontend hiding.

- [ ] **Step 4: Verify API tests and full backend suite**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_claim_history_api.py -q --basetemp=.pytest-tmp`

Run: `.\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest-tmp`

Expected: PASS.

- [ ] **Step 5: Commit role-safe APIs**

```powershell
git add app/routers/claims.py app/routers/review.py app/main.py tests/test_claim_history_api.py
git commit -m "feat: expose role-safe claim history API"
```

### Task 4: Build Accessible Lifecycle Navigation

**Files:**
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/api/claims.ts`
- Replace: `frontend/src/components/ProgressTracker.tsx`
- Create: `frontend/src/components/ClaimLifecycle.tsx`
- Create: `frontend/src/components/ClaimLifecycle.test.tsx`
- Modify: `frontend/src/styles.css`

**Interfaces:**
- Consumes: `GET /claims/{claimId}/history`.
- Produces: `getClaimHistory(claimId: number): Promise<ClaimHistory>`.
- Produces: `<ClaimLifecycle claimId={number} stages={LifecycleStage[]} />`.

- [ ] **Step 1: Write failing accessibility/navigation tests**

```tsx
it("links completed stages and disables future stages without changing claim id", () => {
  render(<MemoryRouter><ClaimLifecycle claimId={44} stages={stages}/></MemoryRouter>);
  expect(screen.getByRole("link", {name:/Policy matched.*completed/i})).toHaveAttribute("href", "/claims/44/history/policy");
  expect(screen.queryByRole("link", {name:/Decision/i})).not.toBeInTheDocument();
  expect(screen.getByText("Decision").closest("li")).toHaveAttribute("aria-disabled", "true");
});
```

Add completed, current, pending, failed, and all-completed cases from the acceptance scenarios.

- [ ] **Step 2: Run component tests and verify RED**

Run: `npm test -- --run src/components/ClaimLifecycle.test.tsx`

Working directory: `frontend`

Expected: FAIL because `ClaimLifecycle` does not exist.

- [ ] **Step 3: Implement typed API and semantic lifecycle links**

```tsx
return <ol className="claimLifecycle" aria-label={`Claim ${claimId} lifecycle`}>
  {stages.map(stage => <li key={stage.key} className={stage.state} aria-current={stage.state === "current" ? "step" : undefined} aria-disabled={!stage.available || undefined}>
    {stage.available && stage.href
      ? <Link to={stage.href} aria-label={`${stage.label_en}, ${stage.state}`}>{marker(stage.state)}<span>{stage.label_en}</span><small>{stateLabel(stage.state)}</small></Link>
      : <div>{marker(stage.state)}<span>{stage.label_en}</span><small>{stateLabel(stage.state)}</small></div>}
  </li>)}
</ol>;
```

Use focus-visible states, pointer cursor only for links, disabled semantics for future stages, safe wrapping, and mobile horizontal scrolling inside the component rather than page scrolling.

- [ ] **Step 4: Verify lifecycle tests and frontend build**

Run: `npm test -- --run src/components/ClaimLifecycle.test.tsx`

Run: `npm run build`

Working directory: `frontend`

Expected: PASS.

- [ ] **Step 5: Commit lifecycle UI**

```powershell
git add frontend/src/types/api.ts frontend/src/api/claims.ts frontend/src/components/ProgressTracker.tsx frontend/src/components/ClaimLifecycle.tsx frontend/src/components/ClaimLifecycle.test.tsx frontend/src/styles.css
git commit -m "feat: make persisted claim lifecycle navigable"
```

### Task 5: Create Bilingual Customer History Pages

**Files:**
- Create: `frontend/src/hooks/useCustomerLanguage.ts`
- Create: `frontend/src/components/LanguageSwitch.tsx`
- Create: `frontend/src/components/CustomerResultCard.tsx`
- Create: `frontend/src/pages/ClaimHistoryPage.tsx`
- Create: `frontend/src/pages/ClaimHistoryPage.test.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/pages/VerificationPage.tsx`
- Modify: `frontend/src/styles.css`

**Interfaces:**
- Produces: `useCustomerLanguage(): ["en" | "km", (language) => void]`, stored under `insuranceCustomerLanguage`.
- Produces: `/claims/:claimId/history/:stage` protected for customers.
- Consumes only `ClaimHistory`, never officer evidence types.

- [ ] **Step 1: Write failing customer privacy and language tests**

```tsx
it("shows a safe English result and no OCR internals", async () => {
  renderHistory({customer_result: resultFixture});
  expect(await screen.findByText("Additional review required")).toBeVisible();
  expect(screen.queryByText(/page_1_line|confidence|raw ocr|semantic/i)).not.toBeInTheDocument();
});

it("switches the complete result to Khmer and remembers the choice", async () => {
  const user = userEvent.setup();
  renderHistory({customer_result: resultFixture});
  await user.click(screen.getByRole("button", {name:"ខ្មែរ"}));
  expect(screen.getByText(resultFixture.message_km)).toBeVisible();
  expect(localStorage.getItem("insuranceCustomerLanguage")).toBe("km");
});
```

Add a test asserting a GET history call occurs and `runClaimPrecheck` is never called on mount or lifecycle click.

- [ ] **Step 2: Run customer-history tests and verify RED**

Run: `npm test -- --run src/pages/ClaimHistoryPage.test.tsx`

Working directory: `frontend`

Expected: FAIL because the page and language components do not exist.

- [ ] **Step 3: Implement English-first history pages**

Render policy, original-document list, customer-safe extraction/compliance status, and persisted decision according to the `:stage` parameter. Display only `title_en/message_en` or `title_km/message_km`, claim amount/payable amount when present, decision timestamp, and authorized next action.

```tsx
<LanguageSwitch value={language} onChange={setLanguage}/>
<CustomerResultCard result={history.customer_result} language={language}/>
<BackButton to="/portal" label={language === "km" ? "ការទាមទាររបស់ខ្ញុំ" : "My claims"}/>
```

Replace the customer technical extraction content in `VerificationPage` with navigation to or rendering of this safe result. Keep officer technical rendering in `OfficerReviewPage`.

- [ ] **Step 4: Verify customer tests and build**

Run: `npm test -- --run src/pages/ClaimHistoryPage.test.tsx src/pages/VerificationPage.test.tsx`

Run: `npm run build`

Working directory: `frontend`

Expected: PASS.

- [ ] **Step 5: Commit bilingual customer results**

```powershell
git add frontend/src/hooks/useCustomerLanguage.ts frontend/src/components/LanguageSwitch.tsx frontend/src/components/CustomerResultCard.tsx frontend/src/pages/ClaimHistoryPage.tsx frontend/src/pages/ClaimHistoryPage.test.tsx frontend/src/App.tsx frontend/src/pages/VerificationPage.tsx frontend/src/styles.css
git commit -m "feat: add bilingual customer claim results"
```

### Task 6: Complete Officer Evidence and Original-Document Review

**Files:**
- Modify: `app/routers/review.py`
- Modify: `frontend/src/api/review.ts`
- Modify: `frontend/src/pages/OfficerReviewPage.tsx`
- Modify: `frontend/src/components/ExtractionField.tsx`
- Create: `frontend/src/pages/OfficerReviewPage.test.tsx`
- Modify: `frontend/src/styles.css`

**Interfaces:**
- Consumes: existing officer workspace and authorized document blob endpoints.
- Produces: full original/clean/raw/extracted/verification/decision tabs for officers only.

- [ ] **Step 1: Write failing officer-evidence tests**

```tsx
it("lets an officer compare the original with technical evidence", async () => {
  renderOfficerReview(workspaceFixture);
  expect(await screen.findByRole("tab", {name:"Original Document"})).toBeVisible();
  expect(screen.getByRole("tab", {name:"Clean OCR"})).toBeVisible();
  await userEvent.click(screen.getByRole("tab", {name:"Extracted Fields"}));
  expect(screen.getByText("OCR evidence lines")).toBeVisible();
  expect(screen.getByText("AI semantic interpretation")).toBeVisible();
});
```

Add tests for zero/non-positive field confidence rendering as “Not available,” persisted decision display, and officer-only original-document download.

- [ ] **Step 2: Run officer tests and verify RED**

Run: `npm test -- --run src/pages/OfficerReviewPage.test.tsx`

Working directory: `frontend`

Expected: FAIL on missing decision presentation or incorrect confidence semantics.

- [ ] **Step 3: Implement officer-only evidence hierarchy**

Use `ExtractionField` with field name, normalized value, subtle status badge, labeled non-zero confidence, evidence lines, expandable raw source, and visually distinct semantic interpretation. Add a read-only decision tab that reads persisted decision records. Preserve original preview/download authorization and officer correction/audit actions.

- [ ] **Step 4: Verify officer tests and role security**

Run: `npm test -- --run src/pages/OfficerReviewPage.test.tsx`

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_claim_history_api.py -q --basetemp=.pytest-tmp`

Expected: PASS.

- [ ] **Step 5: Commit officer evidence review**

```powershell
git add app/routers/review.py frontend/src/api/review.ts frontend/src/pages/OfficerReviewPage.tsx frontend/src/components/ExtractionField.tsx frontend/src/pages/OfficerReviewPage.test.tsx frontend/src/styles.css
git commit -m "feat: complete officer evidence and decision review"
```

### Task 7: Make Document Intake State-Aware and Finish Navigation/Auth

**Files:**
- Modify: `frontend/src/components/DocumentCard.tsx`
- Modify: `frontend/src/pages/ClaimDocumentsPage.tsx`
- Modify: `frontend/src/components/AppShell.tsx`
- Modify: `frontend/src/components/ProtectedRoute.tsx`
- Modify: `frontend/src/api/portal.ts`
- Modify: `frontend/src/components/InsuranceAgentBubble.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`
- Create: `frontend/src/components/AppShell.test.tsx`
- Modify: `frontend/src/pages/ClaimDocumentsPage.test.tsx`
- Modify: `frontend/src/components/InsuranceAgentBubble.test.tsx`

**Interfaces:**
- Consumes: persisted document `ocr_status`, `extraction_status`, and `verification_status`.
- Produces: role-aware header/logout, protected routes, state-aware processing messages, and safe chatbot actions.

- [ ] **Step 1: Write failing state/auth/chat tests**

```tsx
it("shows completed persisted document states instead of queued", async () => {
  renderDocuments(processedClaimFixture);
  expect(await screen.findAllByText("Completed")).not.toHaveLength(0);
  expect(screen.queryByText("Processing starts automatically")).not.toBeInTheDocument();
});

it("logout clears session and protected claim state", async () => {
  sessionStorage.setItem("insuranceSession", JSON.stringify(customer));
  renderAppAt("/portal");
  await userEvent.click(screen.getByRole("button", {name:/log out/i}));
  expect(sessionStorage.getItem("insuranceSession")).toBeNull();
  expect(screen.getByRole("link", {name:/customer sign in/i})).toBeVisible();
});
```

Add chatbot tests confirming visitor mode never claims customer access and customer mode returns only safe claim-status actions.

- [ ] **Step 2: Run the targeted tests and verify RED**

Run: `npm test -- --run src/pages/ClaimDocumentsPage.test.tsx src/components/AppShell.test.tsx src/components/InsuranceAgentBubble.test.tsx`

Working directory: `frontend`

Expected: FAIL on stale document copy, incomplete session reactivity, or unsafe chatbot action.

- [ ] **Step 3: Implement persisted status mapping and role navigation**

Map backend states rather than a component-local `processing` boolean. Remove the synthetic/anonymized banner and all customer-facing explicit demo labels. Completed history uses “Claim processing completed. Review the stages above for details”; pending officer uses “Automated checks are complete. This claim is awaiting officer review.”

Finish shared header logic so unauthenticated users see sign-in actions, customers see their dashboard and logout, and officers/admins see their workspaces and logout. `clearSession()` removes session and role-specific cached claim/chat data before redirecting to `/`.

- [ ] **Step 4: Verify targeted tests and complete frontend suite**

Run: `npm test -- --run src/pages/ClaimDocumentsPage.test.tsx src/components/AppShell.test.tsx src/components/InsuranceAgentBubble.test.tsx`

Run: `npm test`

Run: `npm run build`

Working directory: `frontend`

Expected: PASS with no TypeScript errors.

- [ ] **Step 5: Commit state-aware intake and navigation**

```powershell
git add frontend/src/components/DocumentCard.tsx frontend/src/pages/ClaimDocumentsPage.tsx frontend/src/components/AppShell.tsx frontend/src/components/ProtectedRoute.tsx frontend/src/api/portal.ts frontend/src/components/InsuranceAgentBubble.tsx frontend/src/App.tsx frontend/src/styles.css frontend/src/components/AppShell.test.tsx frontend/src/pages/ClaimDocumentsPage.test.tsx frontend/src/components/InsuranceAgentBubble.test.tsx
git commit -m "fix: align claim intake and navigation with persisted state"
```

### Task 8: Add a Safe Two-Claim Demo Reset

**Files:**
- Create: `app/services/demo_reset_service.py`
- Create: `scripts/reset_demo_claims.py`
- Create: `tests/test_demo_reset_service.py`
- Modify: `README.md`

**Interfaces:**
- Produces: `reset_and_seed_demo_claims(db: AsyncSession, customer_email: str) -> DemoResetSummary`.
- Produces: CLI requiring `--confirm RESET-CLAIMS` and printing before/after counts.

- [ ] **Step 1: Write a failing transactional reset test**

```python
@pytest.mark.anyio
async def test_reset_preserves_reference_data_and_seeds_two_valid_scenarios(async_db_session, seeded_demo):
    before_users = await count(async_db_session, User)
    before_products = await count(async_db_session, InsuranceProduct)
    summary = await reset_and_seed_demo_claims(async_db_session, "customer@demo.insure")
    assert await count(async_db_session, User) == before_users
    assert await count(async_db_session, InsuranceProduct) == before_products
    claims = list((await async_db_session.execute(select(Claim).order_by(Claim.id))).scalars())
    assert [claim.status for claim in claims] == ["auto_approved", "rejected"]
    assert summary.claims_after == 2
```

Assert the rejected claim has a final authorized decision and its rationale is not low OCR confidence.

- [ ] **Step 2: Run reset tests and verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_demo_reset_service.py -q --basetemp=.pytest-tmp`

Expected: FAIL because the reset service does not exist.

- [ ] **Step 3: Implement transactionally scoped reset and fixtures**

Delete claim-dependent rows in foreign-key order inside one transaction, using explicit model deletes. Preserve `User`, `InsuranceProduct`, `PolicyDocument`, `PolicyRule`, and `Policy`. Seed one internally consistent approved record and one human-rejected record with persisted lifecycle, decision, and audit data. Do not expose a destructive HTTP endpoint.

The CLI must refuse to run without the exact confirmation token:

```python
if args.confirm != "RESET-CLAIMS":
    parser.error("Pass --confirm RESET-CLAIMS to replace claim history")
```

- [ ] **Step 4: Verify reset tests without touching the live database**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_demo_reset_service.py -q --basetemp=.pytest-tmp`

Expected: PASS against temporary test storage only.

- [ ] **Step 5: Commit the reset tooling**

```powershell
git add app/services/demo_reset_service.py scripts/reset_demo_claims.py tests/test_demo_reset_service.py README.md
git commit -m "feat: add safe two-claim demo reset"
```

### Task 9: End-to-End Verification, Live Reset, and GitHub Push

**Files:**
- Verify only: entire repository
- Mutate live data only by: `scripts/reset_demo_claims.py`

**Interfaces:**
- Consumes: all prior tasks.
- Produces: verified `Pisey` branch on `origin/Pisey` and exactly two live demo claims.

- [ ] **Step 1: Run clean automated verification**

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest-tmp
Push-Location frontend
npm test
npm run build
Pop-Location
git diff --check
```

Expected: zero backend failures/errors, zero frontend test failures, build exit code 0, and no diff-check errors.

- [ ] **Step 2: Start services and verify health without duplicate listeners**

Check ports 8000 and 5176 first. Reuse healthy listeners or stop only the project-owned process before starting the backend and frontend. Verify `GET http://127.0.0.1:8000/health` and load `http://127.0.0.1:5176/`.

- [ ] **Step 3: Run end-user browser flows**

Customer flow: sign in, view two claims, traverse every available lifecycle stage, switch English/Khmer, confirm technical OCR terms are absent, confirm original customer documents remain viewable, and confirm history navigation issues no processing POST requests.

Officer flow: sign in, open both claims, preview originals, inspect clean/raw OCR, extracted fields, confidence/source/meaning, compliance, decisions, and audit history; complete a reversible test action only against temporary/test data.

Chatbot flow: verify visitor general questions, consultation action, customer policy/status questions, role-correct login/logout, and no officer/internal evidence leakage.

Responsive flow: inspect 1920×1080, 1440×900, 1366×768, 1024, 768, and 390 widths for overlap, horizontal page scrolling, clipped actions, footer collisions, and chatbot obstruction.

- [ ] **Step 4: Report and execute the authorized live reset**

Run the CLI once without confirmation and confirm it refuses. Query and report exact claim-dependent row/file counts. Then run:

```powershell
.\.venv\Scripts\python.exe scripts\reset_demo_claims.py --customer customer@demo.insure --confirm RESET-CLAIMS
```

Re-query and verify exactly two claims: one `auto_approved`, one final authorized `rejected`; verify both appear correctly in customer and officer portals.

- [ ] **Step 5: Final secret/artifact and repository check**

```powershell
git status --short
git diff --check
git ls-files .env tessdata uploads processed_uploads logs insurance_demo.db
git grep -n -I -E "AZURE_OPENAI_API_KEY=.+|postgresql[^ ]*:[^ ]+@" -- ':!docs/**'
```

Expected: no local runtime artifacts or credentials are tracked. Review every staged path before committing.

- [ ] **Step 6: Commit remaining verified integration changes**

```powershell
git add . ':!tessdata' ':!uploads' ':!processed_uploads' ':!logs' ':!.env' ':!insurance_demo.db'
git status --short
git commit -m "feat: deliver governed bilingual claim review flow"
```

- [ ] **Step 7: Push the requested branch**

```powershell
git push -u origin Pisey
```

Expected: GitHub reports `Pisey -> Pisey`. Return the branch and commit URLs plus exact test counts and any remaining limitation.
