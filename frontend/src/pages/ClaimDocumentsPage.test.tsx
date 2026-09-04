import "../test/setup";

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ClaimDocumentsPage } from "./ClaimDocumentsPage";
import { getClaim, uploadClaimDocument } from "../api/claims";
import { getOcrRuns } from "../api/documents";

vi.mock("../api/claims", () => ({
  getClaim: vi.fn(),
  uploadClaimDocument: vi.fn()
}));

vi.mock("../api/documents", () => ({
  getOcrRuns: vi.fn(),
  processDocument: vi.fn(),
  extractDocumentFields: vi.fn()
}));

describe("ClaimDocumentsPage", () => {
  it("displays document completeness and rejects invalid selected file types", async () => {
    vi.mocked(getClaim).mockResolvedValueOnce({
      id: 7,
      claimant_name: "Demo Patient",
      policy_number: "POL-DEMO-001",
      claim_type: "health_outpatient",
      incident_date: "2026-07-31",
      claimed_amount: null,
      status: "intake",
      created_at: null,
      documents: [],
      document_completeness: { is_complete: false, missing_document_types: ["claim_form", "medical_report", "receipt"] },
      missing_required_document_types: ["claim_form", "medical_report", "receipt"]
    });
    vi.mocked(getOcrRuns).mockResolvedValue([]);

    render(
      <MemoryRouter initialEntries={["/claims/7/documents"]}>
        <Routes>
          <Route path="/claims/:claimId/documents" element={<ClaimDocumentsPage />} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByText(/healthcare claim form/i)).toBeInTheDocument();
    const fileInputs = screen.getAllByLabelText(/select pdf or image/i);
    await userEvent.upload(fileInputs[0], new File(["bad"], "bad.exe", { type: "application/octet-stream" }), {
      applyAccept: false
    });

    expect(await screen.findByText(/select a pdf, jpg, jpeg, or png file/i)).toBeInTheDocument();
    expect(uploadClaimDocument).not.toHaveBeenCalled();
  });
});
