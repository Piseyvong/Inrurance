import { useEffect, useState } from "react";

import { getAuditHistory } from "../api/review";
import { Alert } from "../components/Alert";
import { PageHeader } from "../components/PageHeader";
import { useClaimIdParam } from "../hooks/useClaimIdParam";
import type { AuditLogEntry } from "../types/api";
import { formatDateTime } from "../utils/documents";
import { BackButton } from "../components/BackButton";

export function AuditHistoryPage() {
  const claimId = useClaimIdParam();
  const [entries, setEntries] = useState<AuditLogEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!claimId) return;
    getAuditHistory(claimId)
      .then((result) => {
        setEntries(result);
        setError(null);
      })
      .catch((apiError: Error) => setError(apiError.message));
  }, [claimId]);

  if (!claimId) return <Alert tone="danger">Invalid claim ID.</Alert>;

  return (
    <div className="pageStack">
      <PageHeader title={`Claim ${claimId} Audit History`} eyebrow="Audit Timeline"><BackButton to={`/officer/claims/${claimId}`} label="Claim review" /></PageHeader>
      {error ? <Alert tone="danger">{error}</Alert> : null}
      {!error && entries.length === 0 ? <Alert>No audit history found for this claim.</Alert> : null}
      <ol className="timeline">
        {entries.map((entry) => (
          <li key={entry.id}>
            <time>{formatDateTime(entry.timestamp)}</time>
            <strong>{entry.actor}</strong>
            <span>{entry.action.split("_").join(" ")}</span>
            <p>{entry.details || "No details recorded."}</p>
          </li>
        ))}
      </ol>
    </div>
  );
}
