import "../test/setup";

import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { AuditHistoryPage } from "./AuditHistoryPage";
import { getAuditHistory } from "../api/review";

vi.mock("../api/review", () => ({
  getAuditHistory: vi.fn()
}));

describe("AuditHistoryPage", () => {
  it("renders audit timeline entries", async () => {
    vi.mocked(getAuditHistory).mockResolvedValueOnce([
      {
        id: 1,
        claim_id: 9,
        actor: "system",
        action: "claim_created",
        details: null,
        timestamp: "2026-07-31T10:00:00Z"
      }
    ]);

    render(
      <MemoryRouter initialEntries={["/claims/9/audit"]}>
        <Routes>
          <Route path="/claims/:claimId/audit" element={<AuditHistoryPage />} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByText(/claim created/i)).toBeInTheDocument();
  });
});
