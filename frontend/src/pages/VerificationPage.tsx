import { useEffect, useState, type ReactElement } from "react";
import { Link } from "react-router-dom";
import { getClaim, getClaimDocuments } from "../api/claims";
import { getVerification, runClaimPrecheck } from "../api/verification";
import { Alert } from "../components/Alert";
import { PageHeader } from "../components/PageHeader";
import { ProgressTracker } from "../components/ProgressTracker";
import { StatusBadge } from "../components/StatusBadge";
import { BackButton } from "../components/BackButton";
import { ExtractionField } from "../components/ExtractionField";
import { AlertTriangleIcon, CheckCircleIcon, ClockIcon, MinusCircleIcon, XCircleIcon } from "../components/icons";
import { useClaimIdParam } from "../hooks/useClaimIdParam";
import type { ClaimWithDocuments, DocumentRecord, DocumentReviewScore, VerificationReport } from "../types/api";
import { comparisonRules, groupFieldsByDocument, hasHumanReviewReasons, verificationRuleDetail } from "../utils/verification";
import { documentLabel, formatDateTime, outcomeLabel } from "../utils/documents";
import { groupReviewReasons } from "../utils/reviewReasons";

type TabTone = "good" | "warning" | "danger" | "neutral";
type TabKey = "summary" | "comparison" | `doc-${number}`;

const tabToneIcon: Record<TabTone, (props: { size?: number }) => ReactElement> = {
  good: CheckCircleIcon,
  warning: AlertTriangleIcon,
  danger: XCircleIcon,
  neutral: MinusCircleIcon
};

function documentTabTone(score: DocumentReviewScore | undefined): TabTone {
  if (!score) return "neutral";
  if (score.status === "strong") return "good";
  if (score.status === "needs_review") return "danger";
  if (score.status === "moderate") return "warning";
  return "neutral";
}

type DocStage = "queued" | "scanning" | "reading" | "checking" | "done" | "failed";

/**
 * The backend processes required documents one at a time — OCR, then
 * extraction, then a final rules pass — committing each document's status to
 * the database as it goes. This mirrors that same sequence so the "live"
 * checklist reflects what the server is actually doing, not a fake timer.
 */
function documentStage(document: DocumentRecord): DocStage {
  if (document.ocr_status === "failed" || document.extraction_status === "failed") return "failed";
  if (document.verification_status === "completed") return "done";
  if (document.extraction_status === "processing") return "reading";
  if (document.extraction_status === "succeeded") return "checking";
  if (document.ocr_status === "processing") return "scanning";
  if (document.ocr_status === "succeeded") return "reading";
  return "queued";
}

const DOC_STAGE_META: Record<DocStage, { label: string; tone: "neutral" | "active" | "good" | "danger" }> = {
  queued: { label: "Waiting to start", tone: "neutral" },
  scanning: { label: "Scanning document", tone: "active" },
  reading: { label: "Reading details", tone: "active" },
  checking: { label: "Checking against your claim", tone: "active" },
  done: { label: "Checked", tone: "good" },
  failed: { label: "Needs attention", tone: "danger" }
};

const DOC_STAGE_ICON: Record<"neutral" | "active" | "good" | "danger", (props: { size?: number }) => ReactElement> = {
  neutral: MinusCircleIcon,
  active: ClockIcon,
  good: CheckCircleIcon,
  danger: XCircleIcon
};

/** Jumps straight to whichever tab needs attention, so a reviewer sees the problem without clicking through every document. */
function pickDefaultTab(report: VerificationReport | null): TabKey {
  if (!report) return "summary";
  const toneOf = (documentId: number) => documentTabTone(report.evidence_review.document_scores.find((item) => item.document_id === documentId));
  const comparison = comparisonRules(report.rule_results);
  const comparisonHasMismatch = comparison.some((rule) => ["mismatch", "missing"].includes(rule.result));
  const comparisonHasUnclear = comparison.some((rule) => rule.result === "unclear");
  const dangerDoc = report.documents.find((document) => toneOf(document.id) === "danger");
  if (dangerDoc) return `doc-${dangerDoc.id}`;
  if (comparisonHasMismatch) return "comparison";
  const warningDoc = report.documents.find((document) => toneOf(document.id) === "warning");
  if (warningDoc) return `doc-${warningDoc.id}`;
  if (comparisonHasUnclear) return "comparison";
  return "summary";
}

export function VerificationPage() {
  const claimId = useClaimIdParam();
  const [claim, setClaim] = useState<ClaimWithDocuments | null>(null);
  const [report, setReport] = useState<VerificationReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<TabKey>("summary");
  const [tabPinned, setTabPinned] = useState(false);
  const [liveDocuments, setLiveDocuments] = useState<DocumentRecord[] | null>(null);

  async function refresh() {
    if (!claimId) return;
    setClaim(await getClaim(claimId));
    setReport(await getVerification(claimId).catch(() => null));
  }

  useEffect(() => {
    setTabPinned(false);
    refresh().catch((apiError: Error) => setError(apiError.message));
  }, [claimId]);

  useEffect(() => {
    if (!tabPinned) setActiveTab(pickDefaultTab(report));
  }, [report, tabPinned]);

  function selectTab(key: TabKey) {
    setTabPinned(true);
    setActiveTab(key);
  }

  async function verify() {
    if (!claimId) return;
    setLoading(true);
    setError(null);
    setTabPinned(false);
    setLiveDocuments(claim?.documents ?? null);
    const pollDocuments = () => {
      getClaimDocuments(claimId)
        .then(setLiveDocuments)
        .catch(() => undefined);
    };
    pollDocuments();
    const interval = window.setInterval(pollDocuments, 1500);
    try {
      setReport(await runClaimPrecheck(claimId));
      setClaim(await getClaim(claimId));
    } catch (apiError) {
      setError(apiError instanceof Error ? apiError.message : "Verification failed.");
    } finally {
      window.clearInterval(interval);
      setLiveDocuments(null);
      setLoading(false);
    }
  }

  if (!claimId) return <Alert tone="danger">Invalid claim ID.</Alert>;

  const fieldsByDocument = groupFieldsByDocument(report?.extracted_fields ?? []);
  const approved = claim?.status === "auto_approved";
  const reviewRequired = !approved && report ? hasHumanReviewReasons(report.reasons_for_human_review) : false;
  const missingDocuments = claim?.missing_required_document_types ?? [];
  const canRunPrecheck = Boolean(claim && missingDocuments.length === 0);
  const extractedValue = (fieldName: string, preferredTypes: string[] = []) => {
    const candidates = (report?.extracted_fields ?? []).filter((field) => field.field_name === fieldName && (field.normalized_value || field.field_value) && ["VALID","CORRECTED"].includes((field.validation_status ?? "").toUpperCase()));
    for (const documentType of preferredTypes) {
      const document = report?.documents.find((item) => item.doc_type === documentType);
      const match = candidates.find((field) => field.document_id === document?.id);
      if (match?.normalized_value || match?.field_value) return match.normalized_value || match.field_value;
    }
    return candidates[0]?.normalized_value ?? candidates[0]?.field_value ?? "Not found in extracted evidence";
  };

  const workspaceDocuments = claim?.documents ?? report?.documents ?? [];
  const comparisonResults = comparisonRules(report?.rule_results ?? []);
  const comparisonTone: TabTone = !comparisonResults.length
    ? "neutral"
    : comparisonResults.some((rule) => ["mismatch", "missing"].includes(rule.result))
    ? "danger"
    : comparisonResults.some((rule) => rule.result === "unclear")
    ? "warning"
    : "good";
  const tabs: Array<{ key: TabKey; label: string; tone: TabTone; meta?: string }> = [
    { key: "summary", label: "Summary", tone: missingDocuments.length ? "warning" : "neutral" },
    ...workspaceDocuments.map((document) => {
      const score = report?.evidence_review.document_scores.find((item) => item.document_id === document.id);
      return {
        key: `doc-${document.id}` as TabKey,
        label: documentLabel(document.doc_type),
        tone: documentTabTone(score),
        meta: score ? `${score.extracted_required_fields}/${score.required_fields} fields` : undefined
      };
    }),
    { key: "comparison" as TabKey, label: "Cross-Document Checks", tone: comparisonTone }
  ];
  const reviewReasonGroups = reviewRequired ? groupReviewReasons(report!.reasons_for_human_review, report!.rule_results) : [];

  return (
    <div className="pageStack verificationPage">
      <BackButton to={`/claims/${claimId}/documents`} label="Documents" />
      <PageHeader title={`Claim ${claimId} Verification`} eyebrow="Deterministic Verification">
        {approved ? <Link className="secondaryButton" to="/portal">Return to customer portal</Link> : <button type="button" onClick={verify} disabled={loading || !canRunPrecheck} title={!canRunPrecheck ? "Upload every required document before running the pre-check." : undefined}>
          {loading ? "Reading Documents..." : canRunPrecheck ? "Run Document AI Pre-Check" : "Upload documents to continue"}
        </button>}
      </PageHeader>
      {claim ? <ProgressTracker claim={claim} verification={report} /> : null}
      {loading ? (
        <section className="panel processingPanel" aria-live="polite">
          <h2>Reading your documents…</h2>
          <p>Each document is scanned, then its details are read and checked against your claim — one at a time.</p>
          <div className="processingList">
            {(liveDocuments ?? workspaceDocuments).map((document) => {
              const stage = documentStage(document);
              const meta = DOC_STAGE_META[stage];
              const Icon = DOC_STAGE_ICON[meta.tone];
              return (
                <div key={document.id} className={`processingRow ${meta.tone}`}>
                  <Icon size={18} />
                  <span className="processingRowLabel">{documentLabel(document.doc_type)}</span>
                  <span className="processingRowStage">{meta.label}</span>
                </div>
              );
            })}
          </div>
        </section>
      ) : null}
      {approved ? <Alert tone="success"><strong>Claim approved.</strong> The benefit payment will be issued within seven business days.</Alert> : null}
      {missingDocuments.length ? (
        <Alert tone="warning">
          Upload all required documents before OCR can start: <strong>{missingDocuments.map(documentLabel).join(", ")}</strong>.{" "}
          <Link to={`/claims/${claimId}/documents`}>Go to document upload</Link>
        </Alert>
      ) : null}
      {error ? <Alert tone="danger">{error}</Alert> : null}
      {!approved && report ? (
        <section className={`verdictCard ${reviewRequired ? "review" : "good"}`} aria-label="Verification result">
          {reviewRequired ? <AlertTriangleIcon className="verdictCardIcon" size={22} /> : <CheckCircleIcon className="verdictCardIcon" size={22} />}
          <div>
            <h2>{reviewRequired ? "This claim needs a person to review it" : "Evidence checks complete"}</h2>
            <p>{reviewRequired ? report.evidence_review.summary || "A few details in your documents need a second look." : "Your documents match the details in your claim — a reviewer will give it a final look."}</p>
          </div>
          <div className="verdictScore">
            <strong>{report.evidence_review.overall_score}%</strong>
            <span>Evidence score</span>
          </div>
        </section>
      ) : null}
      <p className="verdictHint">AI and OCR provide evidence only. Eligibility is determined by the matched policy rules; incomplete or uncertain evidence always goes to a person.</p>
      {reviewRequired ? (
        <section className="reviewSummary" aria-label="What needs confirmation">
          <div className="reviewSummaryHead">
            <h3>What needs confirmation</h3>
            <span className="reviewSummaryCount">{reviewReasonGroups.reduce((total, group) => total + group.items.length, 0)} items</span>
          </div>
          <div className="reviewReasonGroups">
            {reviewReasonGroups.map((group) => {
              const Icon = tabToneIcon[group.tone];
              return (
                <div key={group.category} className={`reviewReasonGroup ${group.tone} ${group.category}`}>
                  <div className="reviewReasonGroupHeading">
                    <Icon size={15} />
                    <span>{group.label}</span>
                    <small>{group.items.length}</small>
                  </div>
                  <ul>
                    {group.items.map((item) => (
                      <li key={item.key}>{item.text}</li>
                    ))}
                  </ul>
                </div>
              );
            })}
          </div>
        </section>
      ) : null}

      {approved ? (
        <section className="panel">
          <h2>Document Completeness</h2>
          <div className="tableLike">
            {(claim?.documents ?? []).map((document) => (
              <div key={document.id}>
                <span>{documentLabel(document.doc_type)}</span>
                <StatusBadge status="received" />
                <span>{document.original_filename ?? "Uploaded evidence"}</span>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {!approved && (claim || report) ? (
        <section className="panel verificationWorkspace" aria-labelledby="evidence-review-title">
          {report?.rule_results.length ? (
            <>
              <div className="sectionHeading">
                <div>
                  <h2 id="evidence-review-title">AI Evidence Review</h2>
                  <p>{report.evidence_review.summary}</p>
                </div>
              </div>
              <div className="scoreGrid">
                <div>
                  <span>Checks Passed</span>
                  <strong>
                    {report.evidence_review.passed_checks} / {report.evidence_review.total_checks}
                  </strong>
                </div>
                <div>
                  <span>Review Issues</span>
                  <strong>{report.evidence_review.issue_count}</strong>
                </div>
              </div>
            </>
          ) : (
            <h2 id="evidence-review-title">Claim Evidence</h2>
          )}

          <div className="verificationTabs" role="tablist">
            {tabs.map((tab) => {
              const Icon = tabToneIcon[tab.tone];
              return (
                <button
                  key={tab.key}
                  type="button"
                  role="tab"
                  aria-selected={activeTab === tab.key}
                  className={`verificationTab ${tab.tone}${activeTab === tab.key ? " active" : ""}`}
                  onClick={() => selectTab(tab.key)}
                >
                  <Icon size={15} />
                  <span>{tab.label}</span>
                  {tab.meta ? <small>{tab.meta}</small> : null}
                </button>
              );
            })}
          </div>

          <div className="verificationTabPanel" role="tabpanel">
            {activeTab === "summary" ? (
              <>
                <h3 className="verificationSubheading">Extracted Claim Summary</h3>
                {claim && report?.extracted_fields.length ? (
                  <div className="summaryGrid">
                    <span>Claim ID</span>
                    <strong>{claim.id}</strong>
                    <span>Claimant</span>
                    <strong>{extractedValue("claimant_name", ["claim_form"])}</strong>
                    <span>Policy</span>
                    <strong>{extractedValue("policy_number", ["claim_form"])}</strong>
                    <span>Incident Date</span>
                    <strong>{extractedValue("incident_date", ["claim_form"])}</strong>
                    <span>Claimed Amount</span>
                    <strong>{extractedValue("claim_amount", ["claim_form"])}</strong>
                    <span>Medical Evidence</span>
                    <strong>{extractedValue("diagnosis", ["medical_report"])}</strong>
                  </div>
                ) : (
                  <p>Run the AI pre-check to see the extracted claim summary.</p>
                )}
                <h3 className="verificationSubheading">Document Completeness</h3>
                <div className="tableLike">
                  {workspaceDocuments.map((document) => (
                    <div key={document.id}>
                      <span>{documentLabel(document.doc_type)}</span>
                      <StatusBadge status="received" />
                      <span>{document.original_filename ?? "Uploaded evidence"}</span>
                    </div>
                  ))}
                </div>
                {claim?.missing_required_document_types?.length ? (
                  <p className="fieldError">Missing: {claim.missing_required_document_types.map(documentLabel).join(", ")}</p>
                ) : null}
              </>
            ) : null}

            {workspaceDocuments.map((document) => {
              if (activeTab !== `doc-${document.id}`) return null;
              const fields = (fieldsByDocument.get(document.id) ?? []).filter((field) => (field.validation_status ?? "").toUpperCase() !== "NOT_APPLICABLE");
              return (
                <div className="evidenceGroup" key={document.id}>
                  {!report ? (
                    <p>Run the AI pre-check to extract evidence from this document.</p>
                  ) : fields.length ? (
                    fields.map((field) => (
                      <ExtractionField key={field.id} name={field.field_name} value={field.field_value} normalizedValue={field.normalized_value} status={field.validation_status} confidence={field.confidence} extractionMethod={field.extraction_method} lineRefs={field.supporting_line_refs} source={field.source_text} interpretation={field.semantic_reason}/>
                    ))
                  ) : (
                    <p>No extracted fields are available yet.</p>
                  )}
                </div>
              );
            })}

            {activeTab === "comparison" ? (
              !comparisonResults.length ? (
                <p>Run verification to see comparison results.</p>
              ) : (
                <div className="comparisonTable">
                  {comparisonResults.map((rule) => {
                    const detail = verificationRuleDetail(rule);
return (
  <div key={rule.id} className={`result-${rule.result}`}>
    <span className="comparisonRuleName">{rule.rule_name.split("_").join(" ")}</span>
    <StatusBadge status={outcomeLabel(rule.result)} />
    <span className="comparisonRuleDetail">{detail || "No additional information"}</span>
    <small className="comparisonRuleTime">{formatDateTime(rule.evaluated_at)}</small>
  </div>
);
                  })}
                </div>
              )
            ) : null}
          </div>
        </section>
      ) : null}
    </div>
  );
}
