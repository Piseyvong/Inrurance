import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getOfficerClaims } from "../api/review";
import { Alert } from "../components/Alert";
import { ArrowRightIcon, InboxIcon, UserCheckIcon } from "../components/icons";
import { PageHeader } from "../components/PageHeader";
import { StatusBadge } from "../components/StatusBadge";
import type { Claim } from "../types/api";
import { formatDateTime } from "../utils/documents";

export function OfficerPortalPage() {
  const [claims, setClaims] = useState<Claim[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getOfficerClaims()
      .then((result) => {
        setClaims(result);
        setError(null);
      })
      .catch((apiError: Error) => setError(apiError.message));
  }, []);

  return (
    <div className="pageStack">
      <PageHeader title="Officer Portal" eyebrow="Human Review Queue" subtitle="Only claims routed to officer review appear here." />
      <Alert>
        Claims below $50 can be auto-approved only by deterministic rules when all checks are clean. AI and OCR do not approve or reject claims.
      </Alert>
      {error ? <Alert tone="danger">{error}</Alert> : null}

      <section className="panel claimsPanel" aria-labelledby="officer-queue-title">
        <div className="sectionHeading">
          <h2 id="officer-queue-title">Claims Requiring Review</h2>
          <span className="sectionNote">{claims.length} in queue</span>
        </div>
        {claims.length === 0 ? (
          <div className="emptyState">
            <span className="emptyStateIcon">
              <InboxIcon size={28} />
            </span>
            <h3>No Claims Need Officer Review</h3>
            <p>Claims appear here after deterministic verification routes them to human review.</p>
          </div>
        ) : (
          <div className="tableWrap">
            <table className="claimsTable">
              <thead>
                <tr>
                  <th scope="col">Claim ID</th>
                  <th scope="col">Claimant</th>
                  <th scope="col">Amount</th>
                  <th scope="col">Status</th>
                  <th scope="col">Created</th>
                  <th scope="col">
                    <span className="srOnly">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {claims.map((claim) => (
                  <tr key={claim.id}>
                    <td data-label="Claim ID">
                      <Link className="claimIdLink" to={`/officer/claims/${claim.id}/review`}>
                        #{claim.id}
                      </Link>
                    </td>
                    <td data-label="Claimant">{claim.claimant_name ?? "Pending extraction"}</td>
                    <td data-label="Amount">{claim.claimed_amount ?? "Not provided"}</td>
                    <td data-label="Status">
                      <StatusBadge status={claim.status} />
                    </td>
                    <td data-label="Created">
                      <time dateTime={claim.created_at ?? undefined}>{formatDateTime(claim.created_at)}</time>
                    </td>
                    <td data-label="Actions">
                      <Link className="tableAction" to={`/officer/claims/${claim.id}/review`}>
                        <UserCheckIcon size={14} />
                        Review
                        <ArrowRightIcon size={14} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
