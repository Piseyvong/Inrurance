import "../test/setup";

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { VerificationPage } from "./VerificationPage";
import { getClaim, getClaimDocuments } from "../api/claims";
import { getVerification, runClaimPrecheck } from "../api/verification";
import type { VerificationReport } from "../types/api";

vi.mock("../api/claims", () => ({
  getClaim: vi.fn(),
  getClaimDocuments: vi.fn()
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
          rule_name: "consistent_identity_claim_form_vs_medical_report",
          result: "mismatch",
          details: "{\"left\":{\"document_id\":1,\"field_name\":\"claimant_name\",\"field_value\":\"Demo Patient\",\"supporting_line_refs\":null},\"right\":{\"document_id\":2,\"field_name\":\"patient_name\",\"field_value\":\"Other Patient\",\"supporting_line_refs\":null}}",
          evaluated_at: null
        }
      ],
      reasons_for_human_review: ["consistent_identity_claim_form_vs_medical_report"],
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

  it("shows a live per-document progress checklist while the AI pre-check runs", async () => {
    const baseDocuments = [
      { id: 201, claim_id: 9, doc_type: "claim_form", original_filename: "cf.png", mime_type: null, file_size: null, uploaded_at: null, ocr_status: "pending", extraction_status: "pending", verification_status: "pending" },
      { id: 202, claim_id: 9, doc_type: "medical_report", original_filename: "mr.png", mime_type: null, file_size: null, uploaded_at: null, ocr_status: "pending", extraction_status: "pending", verification_status: "pending" },
      { id: 203, claim_id: 9, doc_type: "invoice", original_filename: "inv.png", mime_type: null, file_size: null, uploaded_at: null, ocr_status: "pending", extraction_status: "pending", verification_status: "pending" }
    ];

    vi.mocked(getClaim).mockResolvedValue({
      id: 9,
      claimant_name: "Demo Patient",
      policy_number: "POL-DEMO-002",
      claim_type: "health_outpatient",
      incident_date: "2026-07-31",
      claimed_amount: "50.00",
      status: "submitted",
      created_at: null,
      documents: baseDocuments,
      document_completeness: { is_complete: true, missing_document_types: [] },
      missing_required_document_types: []
    });
    vi.mocked(getVerification).mockRejectedValue(new Error("no report yet"));
    vi.mocked(getClaimDocuments).mockResolvedValue([
      { ...baseDocuments[0], ocr_status: "processing" },
      baseDocuments[1],
      baseDocuments[2]
    ]);

    let resolvePrecheck: (report: VerificationReport) => void = () => undefined;
    vi.mocked(runClaimPrecheck).mockReturnValue(
      new Promise<VerificationReport>((resolve) => {
        resolvePrecheck = resolve;
      })
    );

    render(
      <MemoryRouter initialEntries={["/claims/9/verification"]}>
        <Routes>
          <Route path="/claims/:claimId/verification" element={<VerificationPage />} />
        </Routes>
      </MemoryRouter>
    );

    fireEvent.click(await screen.findByRole("button", { name: /run document ai pre-check/i }));

    expect(await screen.findByText(/reading your documents/i)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Scanning document")).toBeInTheDocument());
    expect(screen.getAllByText("Waiting to start").length).toBe(2);

    resolvePrecheck({
      claim_id: 9,
      claim_status: "auto_approved",
      document_completeness: { is_complete: true, missing_document_types: [] },
      documents: baseDocuments,
      extracted_fields: [],
      rule_results: [],
      reasons_for_human_review: [],
      evidence_review: {
        overall_score: 100,
        status: "strong",
        passed_checks: 1,
        total_checks: 1,
        issue_count: 0,
        summary: "Evidence is consistent and complete.",
        document_scores: []
      }
    });

    await waitFor(() => expect(screen.queryByText(/reading your documents/i)).not.toBeInTheDocument());
  });
});
