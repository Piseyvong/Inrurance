import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { claimHistory } from "../api/portal";
import { Alert } from "../components/Alert";
import { BackButton } from "../components/BackButton";
import { ArrowLeftIcon, ArrowRightIcon, ClockIcon } from "../components/icons";
import { PageHeader } from "../components/PageHeader";
import type { ClaimHistoryItem, ClaimHistoryProgress } from "../types/api";
import { formatDateTime } from "../utils/documents";

const PAGE_SIZE = 10;

// Collapsed from the backend's 5 technical fields into the 3 plain-language
// phases customers care about, matching the top ProgressTracker on the
// Documents/Verification pages.
const PROGRESS_STEPS: Array<{ key: "upload" | "processing" | "result"; label: string; destination: "documents" | "verification" }> = [
  { key: "upload", label: "Upload", destination: "documents" },
  { key: "processing", label: "Processing", destination: "verification" },
  { key: "result", label: "Result", destination: "verification" },
];

function threeStageProgress(progress: ClaimHistoryProgress) {
  return {
    upload: progress.documents_uploaded,
    processing: progress.compliance_checked,
    result: progress.decision,
  };
}

function ClaimProgressDots({ claimId, progress, status }: { claimId: number; progress: ClaimHistoryProgress; status: string }) {
  const stages = threeStageProgress(progress);
  const doneCount = PROGRESS_STEPS.filter((step) => stages[step.key]).length;
  return (
    <div className="miniProgress" title={`${doneCount} of ${PROGRESS_STEPS.length} steps complete`}>
      <div className="miniProgressDots">
        {PROGRESS_STEPS.map((step) => (
          <Link
            key={step.key}
            to={`/claims/${claimId}/${step.destination}`}
            className={`miniProgressDot${stages[step.key] ? " is-done" : ""}`}
            title={step.label}
            aria-label={step.label}
          />
        ))}
      </div>
      <span className="miniProgressLabel">{status.replace(/_/g, " ")}</span>
    </div>
  );
}

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "waiting_for_documents", label: "Waiting for documents" },
  { value: "processing", label: "Processing" },
  { value: "pending_human_review", label: "Pending human review" },
  { value: "human_review_required", label: "Human review required" },
  { value: "risk_review", label: "Risk review" },
  { value: "more_information_required", label: "More information required" },
  { value: "coverage_exception", label: "Coverage exception" },
  { value: "auto_approved", label: "Auto approved" },
  { value: "review_completed", label: "Review completed" },
];

export function ClaimHistoryPage() {
  const [items, setItems] = useState<ClaimHistoryItem[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    claimHistory(page, PAGE_SIZE, status || undefined)
      .then((result) => {
        setItems(result.items);
        setTotalPages(result.total_pages);
        setTotal(result.total);
        setError(null);
      })
      .catch((apiError: Error) => setError(apiError.message))
      .finally(() => setLoading(false));
  }, [page, status]);

  return (
    <div className="pageStack">
      <BackButton to="/portal" label="Dashboard" />
      <PageHeader title="Claim History" eyebrow="Customer Portal" />
      {error ? <Alert tone="danger">{error}</Alert> : null}

      <section className="panel claimsPanel" aria-labelledby="claim-history-title">
        <div className="sectionHeading">
          <div>
            <h2 id="claim-history-title">All Claims</h2>
            <p>{total} claim{total === 1 ? "" : "s"} filed on this account.</p>
          </div>
          <label className="historyStatusFilter">
            Status
            <select value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }}>
              {STATUS_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </label>
        </div>

        {!loading && items.length === 0 ? (
          <div className="emptyState">
            <span className="emptyStateIcon">
              <ClockIcon size={28} />
            </span>
            <h3>No Claims Found</h3>
            <p>{status ? "No claims match this status yet." : "Claims you file will appear here."}</p>
          </div>
        ) : (
          <div className="tableWrap">
            <table className="claimsTable">
              <thead>
                <tr>
                  <th scope="col">Claim</th>
                  <th scope="col">Type</th>
                  <th scope="col">Amount</th>
                  <th scope="col">Progress</th>
                  <th scope="col">Decision</th>
                  <th scope="col">Filed</th>
                  <th scope="col">
                    <span className="srOnly">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {items.map((claim) => (
                  <tr key={claim.id}>
                    <td data-label="Claim">
                      <Link className="claimIdLink" to={`/claims/${claim.id}/documents`}>{claim.claim_number}</Link>
                    </td>
                    <td data-label="Type">{claim.claim_type}</td>
                    <td data-label="Amount">{claim.claimed_amount ?? "Not provided"} {claim.claimed_amount ? claim.currency : ""}</td>
                    <td data-label="Progress">
                      <ClaimProgressDots claimId={claim.id} progress={claim.progress} status={claim.status} />
                    </td>
                    <td data-label="Decision">
                      {claim.decision ? `${claim.decision.outcome.replace(/_/g, " ")}${claim.decision.amount ? ` · ${claim.decision.amount} ${claim.currency}` : ""}` : "Pending"}
                    </td>
                    <td data-label="Filed">
                      <time dateTime={claim.created_at ?? undefined}>{formatDateTime(claim.created_at)}</time>
                    </td>
                    <td data-label="Actions">
                      <Link className="tableAction" to={`/claims/${claim.id}/documents`}>
                        View
                        <ArrowRightIcon size={14} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {totalPages > 1 ? (
          <div className="historyPagination">
            <button type="button" className="secondaryButton" disabled={page <= 1 || loading} onClick={() => setPage((current) => current - 1)}>
              <ArrowLeftIcon size={14} />
              Previous
            </button>
            <span className="sectionNote">Page {page} of {totalPages}</span>
            <button type="button" className="secondaryButton" disabled={page >= totalPages || loading} onClick={() => setPage((current) => current + 1)}>
              Next
              <ArrowRightIcon size={14} />
            </button>
          </div>
        ) : null}
      </section>
    </div>
  );
}
