import "../test/setup";

import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { ProgressTracker } from "./ProgressTracker";
import type { ClaimWithDocuments } from "../types/api";

const claim: ClaimWithDocuments = {
  id: 42,
  claimant_name: "Demo Patient",
  policy_number: "POL-DEMO-003",
  claim_type: "health_outpatient",
  incident_date: "2026-07-31",
  claimed_amount: "50.00",
  status: "submitted",
  created_at: null,
  documents: [],
  document_completeness: { is_complete: true, missing_document_types: [] },
  missing_required_document_types: []
};

describe("ProgressTracker", () => {
  it("stays on Upload on the documents page when no phase override is given", () => {
    render(
      <MemoryRouter initialEntries={["/claims/42/documents"]}>
        <ProgressTracker claim={claim} />
      </MemoryRouter>
    );
    const upload = screen.getByText("Upload").closest("li");
    expect(upload).toHaveClass("current");
  });

  it("shows Processing as current with a live percentage when the documents page overrides the phase", () => {
    render(
      <MemoryRouter initialEntries={["/claims/42/documents"]}>
        <ProgressTracker claim={claim} phase="Processing" progress={42} />
      </MemoryRouter>
    );
    const processing = screen.getByText("Processing").closest("li");
    expect(processing).toHaveClass("current");
    expect(screen.getByText("42%")).toBeInTheDocument();
    expect(screen.getByText("Upload").closest("li")).not.toHaveClass("current");
  });
});
