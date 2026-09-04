import "../test/setup";

import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { VerificationPage } from "./VerificationPage";
import { getClaim } from "../api/claims";
import { getVerification, runClaimPrecheck } from "../api/verification";

vi.mock("../api/claims", () => ({
  getClaim: vi.fn()
}));

vi.mock("../api/verification", () => ({
  getVerification: vi.fn(),
  runClaimPrecheck: vi.fn()
}));

describe("VerificationPage", () => {
  it("renders mismatches as human review and has no approval controls", async () => {
    vi.mocked(getClaim).mockResolvedValueOnce({
      id: 8,
      claimant_name: "Demo Patient",
      policy_number: "POL-DEMO-001",
      claim_type: "health_outpatient",
      incident_date: "2026-07-31",
      claimed_amount: "50.00",
      status: "human_review_required",
      created_at: null,
      documents: [],
      document_completeness: { is_complete: true, missing_document_types: [] },
      missing_required_document_types: []
    });
    vi.mocked(getVerification).mockResolvedValueOnce({
      claim_id: 8,
      claim_status: "human_review_required",
      document_completeness: { is_complete: true, missing_document_types: [] },
      documents: [],
      extracted_fields: [],
      rule_results: [
        {
          id: 1,
          claim_id: 8,
          rule_name: "name_claim_form_vs_medical_report",
          result: "mismatch",
          details: "{\"left\":\"Demo Patient\",\"right\":\"Other Patient\"}",
          evaluated_at: null
        }
      ],
      reasons_for_human_review: ["name_claim_form_vs_medical_report"],
      evidence_review: {
        overall_score: 62,
        status: "needs_review",
        passed_checks: 2,
        total_checks: 3,
        issue_count: 1,
        summary: "Evidence has missing, unclear, or mismatched items that need review.",
        document_scores: []
      }
    });

    render(
      <MemoryRouter initialEntries={["/claims/8/verification"]}>
        <Routes>
          <Route path="/claims/:claimId/verification" element={<VerificationPage />} />
        </Routes>
      </MemoryRouter>
    );

    expect((await screen.findAllByText(/human review required/i)).length).toBeGreaterThan(0);
    expect(screen.getByText(/AI evidence review/i)).toBeInTheDocument();
    expect(screen.getByText(/62%/i)).toBeInTheDocument();
    expect(screen.getAllByText(/mismatch/i).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /approve/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /reject/i })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /run document ai pre-check/i })).toBeInTheDocument();
  });
});
