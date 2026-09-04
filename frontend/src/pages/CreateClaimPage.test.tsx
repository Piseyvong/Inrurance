import "../test/setup";

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createClaim, getClaim, uploadClaimDocument } from "../api/claims";
import { runClaimPrecheck } from "../api/verification";
import type { ClaimWithDocuments, DocumentRecord, DocumentType } from "../types/api";
import { CreateClaimPage } from "./CreateClaimPage";

vi.mock("../api/claims", () => ({
  createClaim: vi.fn(),
  getClaim: vi.fn(),
  uploadClaimDocument: vi.fn()
}));

vi.mock("../api/verification", () => ({
  runClaimPrecheck: vi.fn()
}));

const mockedCreateClaim = vi.mocked(createClaim);
const mockedGetClaim = vi.mocked(getClaim);
const mockedUploadClaimDocument = vi.mocked(uploadClaimDocument);
const mockedRunClaimPrecheck = vi.mocked(runClaimPrecheck);

const uploaded: Partial<Record<DocumentType, DocumentRecord>> = {};

function buildClaim(id: number): ClaimWithDocuments {
  return {
    id,
    claimant_name: "Jane Doe",
    policy_number: "POL-123",
    claim_type: "health_outpatient",
    incident_date: "2026-07-31",
    claimed_amount: "150.00",
    status: "intake",
    created_at: null,
    documents: Object.values(uploaded).filter(Boolean) as DocumentRecord[],
    document_completeness: { is_complete: true },
    missing_required_document_types: []
  };
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/claims/new"]}>
      <Routes>
        <Route path="/claims/new" element={<CreateClaimPage />} />
        <Route path="/claims/:claimId/verification" element={<div>Pre-check destination</div>} />
      </Routes>
    </MemoryRouter>
  );
}

async function fillValidForm(user: ReturnType<typeof userEvent.setup>) {
  await user.selectOptions(screen.getByLabelText(/select insurance type/i), "health_outpatient");
}

beforeEach(() => {
  localStorage.clear();
  uploaded["claim_form"] = undefined;
  uploaded["medical_report"] = undefined;
  uploaded["receipt"] = undefined;
  mockedRunClaimPrecheck.mockResolvedValue({
    claim_id: 42,
    claim_status: "ready_for_officer_review",
    document_completeness: { is_complete: true, missing_document_types: [] },
    documents: [],
    extracted_fields: [],
    rule_results: [],
    reasons_for_human_review: [],
    evidence_review: {
      overall_score: 100,
      status: "strong",
      passed_checks: 3,
      total_checks: 3,
      issue_count: 0,
      summary: "Evidence is consistent and complete.",
      document_scores: []
    }
  });
});

describe("CreateClaimPage", () => {
  it("renders heading, banner, stepper with step 1 active, and the empty documents state", () => {
    renderPage();

    expect(screen.getByText(/create claim/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Create a New Claim" })).toBeInTheDocument();
    expect(screen.getByText(/reads these documents, extracts their fields/i)).toBeInTheDocument();

    expect(screen.getByText("Insurance Type").closest("li")).toHaveClass("active");
    expect(screen.getByText("Required Documents")).toBeInTheDocument();
    expect(screen.getByText("Document Extraction")).toBeInTheDocument();
    expect(screen.getByText("Review Result")).toBeInTheDocument();

    expect(screen.getByText(/select an insurance type to see the required documents/i)).toBeInTheDocument();
    expect(screen.queryByText(/Healthcare Claim Form/)).not.toBeInTheDocument();
  });

  it("requires selecting an insurance type before creating a claim shell", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: /save insurance type/i }));

    expect(screen.getByText("Select an insurance type.")).toBeInTheDocument();
    expect(mockedCreateClaim).not.toHaveBeenCalled();
  });

  it("reveals the required documents after selecting a claim type", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.selectOptions(screen.getByLabelText(/select insurance type/i), "health_outpatient");

    expect(screen.getByText("Healthcare Claim Form")).toBeInTheDocument();
    expect(screen.getByText("Medical Report or Certificate")).toBeInTheDocument();
    expect(screen.getByText("Medical Receipt or Invoice")).toBeInTheDocument();
    expect(screen.queryByText(/select an insurance type to see the required documents/i)).not.toBeInTheDocument();
  });

  it("creates a claim with backend values and enables document uploads", async () => {
    mockedCreateClaim.mockResolvedValueOnce(buildClaim(42));
    mockedGetClaim.mockImplementation(async (id) => buildClaim(id));
    const user = userEvent.setup();
    renderPage();

    await fillValidForm(user);
    await user.click(screen.getByRole("button", { name: /save insurance type/i }));

    await waitFor(() =>
      expect(mockedCreateClaim).toHaveBeenCalledWith(
        expect.objectContaining({
          claim_type: "health_outpatient"
        })
      )
    );
    expect(localStorage.getItem("lastClaimId")).toBe("42");
    expect(await screen.findByRole("button", { name: /extract from documents/i })).toBeInTheDocument();
    expect(screen.getByText("Required Documents").closest("li")).toHaveClass("active");
    expect(screen.getByText(/0 of 3 uploaded/i)).toBeInTheDocument();
  });

  it("prompts to upload required documents before continuing", async () => {
    mockedCreateClaim.mockResolvedValueOnce(buildClaim(42));
    mockedGetClaim.mockImplementation(async (id) => buildClaim(id));
    const user = userEvent.setup();
    renderPage();

    await fillValidForm(user);
    await user.click(screen.getByRole("button", { name: /save insurance type/i }));
    await user.click(await screen.findByRole("button", { name: /extract from documents/i }));

    expect(await screen.findByText(/select all required documents before extracting/i)).toBeInTheDocument();
    expect(screen.queryByText("Pre-check destination")).not.toBeInTheDocument();
  });

  it("uploads a document through the existing endpoint and shows its status", async () => {
    mockedCreateClaim.mockResolvedValueOnce(buildClaim(42));
    mockedGetClaim.mockImplementation(async (id) => buildClaim(id));
    mockedUploadClaimDocument.mockImplementation(async (id, docType, file) => {
      const record: DocumentRecord = {
        id: 900 + Object.values(uploaded).filter(Boolean).length,
        claim_id: id,
        doc_type: docType as DocumentType,
        original_filename: file.name,
        file_path: "/uploads/test.pdf",
        mime_type: "application/pdf",
        file_size: file.size,
        uploaded_at: new Date().toISOString()
      };
      uploaded[docType as DocumentType] = record;
      return record;
    });

    const user = userEvent.setup();
    renderPage();
    await fillValidForm(user);
    await user.click(screen.getByRole("button", { name: /save insurance type/i }));
    await screen.findByRole("button", { name: /extract from documents/i });

    const input = screen.getByLabelText("Select Healthcare Claim Form");
    const row = within(input.closest("section")!);
    const file = new File(["%PDF-1.4 fake"], "claim-form.pdf", { type: "application/pdf" });
    await user.upload(input, file);
    await user.click(row.getByRole("button", { name: /^upload$/i }));

    await waitFor(() => expect(mockedUploadClaimDocument).toHaveBeenCalledWith(42, "claim_form", file));
    expect(await row.findByText("uploaded")).toBeInTheDocument();
    expect(screen.getByText(/1 of 3 uploaded/i)).toBeInTheDocument();
  });

  it("uploads selected required documents before navigating to extraction results", async () => {
    mockedCreateClaim.mockResolvedValueOnce(buildClaim(42));
    mockedGetClaim.mockImplementation(async (id) => buildClaim(id));
    mockedUploadClaimDocument.mockImplementation(async (id, docType, file) => {
      const record: DocumentRecord = {
        id: 900 + Object.values(uploaded).filter(Boolean).length,
        claim_id: id,
        doc_type: docType as DocumentType,
        original_filename: file.name,
        file_path: `/uploads/${file.name}`,
        mime_type: "application/pdf",
        file_size: file.size,
        uploaded_at: new Date().toISOString()
      };
      uploaded[docType as DocumentType] = record;
      return record;
    });

    const user = userEvent.setup();
    renderPage();
    await fillValidForm(user);
    await user.click(screen.getByRole("button", { name: /save insurance type/i }));
    await screen.findByRole("button", { name: /extract from documents/i });

    const documents = [
      ["Select Healthcare Claim Form", "claim_form"],
      ["Select Medical Report or Certificate", "medical_report"],
      ["Select Medical Receipt or Invoice", "receipt"]
    ] as const;

    for (const [label, docType] of documents) {
      const input = screen.getByLabelText(label);
      const file = new File(["%PDF-1.4 " + docType], `${docType}.pdf`, { type: "application/pdf" });
      await user.upload(input, file);
    }

    await user.click(screen.getByRole("button", { name: /upload and extract documents/i }));
    await waitFor(() => expect(mockedRunClaimPrecheck).toHaveBeenCalledWith(42));
    expect(mockedUploadClaimDocument).toHaveBeenCalledTimes(3);
    expect(await screen.findByText("Pre-check destination")).toBeInTheDocument();
  });
});
