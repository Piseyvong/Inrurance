import "../test/setup";

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DashboardPage } from "./DashboardPage";
import { getClaim } from "../api/claims";
import { getLlmHealth } from "../api/health";
import { ApiError } from "../api/client";

vi.mock("../api/claims", () => ({
  getClaim: vi.fn()
}));

vi.mock("../api/health", () => ({
  getLlmHealth: vi.fn()
}));

const mockedGetClaim = vi.mocked(getClaim);
const mockedGetLlmHealth = vi.mocked(getLlmHealth);

describe("DashboardPage", () => {
  beforeEach(() => {
    localStorage.clear();
    mockedGetLlmHealth.mockResolvedValue({
      llm: "ok",
      provider: "azure_openai",
      deployment: "gpt-4o",
      response_received: true,
      sample_response: "ok"
    });
  });

  it("shows the intake dashboard without technical readiness or approval language", () => {
    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>
    );

    expect(screen.getByText(/health insurance claims verification/i)).toBeInTheDocument();
    expect(screen.getByText(/secure\. intelligent\. compliant\./i)).toBeInTheDocument();
    expect(screen.getByText(/outpatient claims intake/i)).toBeInTheDocument();
    expect(screen.queryByText(/ai approval controls/i)).not.toBeInTheDocument();
    expect(screen.getByText(/no claims yet/i)).toBeInTheDocument();
  });

  it("shows the Azure OpenAI connection status from the backend", async () => {
    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>
    );

    expect(await screen.findByText(/azure openai connected: gpt-4o/i)).toBeInTheDocument();
  });

  it("shows a validation error when submitting an empty claim id", async () => {
    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>
    );

    await userEvent.click(screen.getByRole("button", { name: /open claim/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/enter a claim id/i);
    expect(mockedGetClaim).not.toHaveBeenCalled();
  });

  it("shows a clear error when the claim does not exist", async () => {
    mockedGetClaim.mockRejectedValueOnce(new ApiError("Claim not found", 404, { detail: "Claim not found" }));

    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>
    );

    await userEvent.type(screen.getByLabelText(/claim id/i), "999");
    await userEvent.click(screen.getByRole("button", { name: /open claim/i }));

    expect(await screen.findByText(/claim 999 does not exist/i)).toBeInTheDocument();
  });

  it("opens an existing claim and records it as recent activity", async () => {
    mockedGetClaim.mockResolvedValueOnce({
      id: 42,
      claimant_name: "Demo Patient",
      policy_number: "POL-DEMO-001",
      claim_type: "health_outpatient",
      incident_date: "2026-07-31",
      claimed_amount: "50.00",
      status: "intake",
      created_at: null,
      documents: [],
      document_completeness: { is_complete: false, missing_document_types: [] },
      missing_required_document_types: []
    });

    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>
    );

    await userEvent.type(screen.getByLabelText(/claim id/i), "42");
    await userEvent.click(screen.getByRole("button", { name: /open claim/i }));

    expect(mockedGetClaim).toHaveBeenCalledWith(42);
    expect(localStorage.getItem("recentClaims")).toContain("42");
  });
});
