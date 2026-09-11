import "../test/setup";

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { askInsuranceAgent } from "../api/chat";
import { InsuranceAgentBubble } from "./InsuranceAgentBubble";

vi.mock("../api/chat", async (importOriginal) => {
  const original = await importOriginal<typeof import("../api/chat")>();
  return {
    ...original,
    askInsuranceAgent: vi.fn(),
    requestConsultation: vi.fn(),
  };
});
const mockAsk = vi.mocked(askInsuranceAgent);

function renderAt(path: string) {
  return render(<MemoryRouter initialEntries={[path]}><InsuranceAgentBubble /></MemoryRouter>);
}

describe("InsuranceAgentBubble", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
  });

  it("appears in guest mode on public routes and restores the session conversation", async () => {
    sessionStorage.setItem("insuranceAgentConversation", JSON.stringify([{ sender: "agent", text: "Saved conversation" }]));
    renderAt("/");
    await userEvent.click(screen.getByRole("button", { name: /open insurance ai agent/i }));
    expect(screen.getByText("Guest mode")).toBeInTheDocument();
    expect(screen.getByText("Saved conversation")).toBeInTheDocument();
  });

  it("uses the same bubble in customer mode", async () => {
    sessionStorage.setItem("insuranceSession", JSON.stringify({ user_id: 1, role: "customer", full_name: "Demo Customer", email: "customer@demo.insure" }));
    renderAt("/portal");
    await userEvent.click(screen.getByRole("button", { name: /open insurance ai agent/i }));
    expect(screen.getByText("Customer mode")).toBeInTheDocument();
  });

  it("is hidden from officer and admin workflows", () => {
    const officer = renderAt("/officer");
    expect(screen.queryByRole("button", { name: /insurance ai agent/i })).not.toBeInTheDocument();
    officer.unmount();
    renderAt("/admin");
    expect(screen.queryByRole("button", { name: /insurance ai agent/i })).not.toBeInTheDocument();
  });

  it("renders a structured claim status card from the agent reply", async () => {
    mockAsk.mockResolvedValue({
      reply: "I found a matching claim: claim #6. Current status: human_review_required.",
      mode: "customer",
      actions: [],
      structured_data: {
        type: "claim_status",
        claims: [{
          id: 6,
          claim_type: "medical",
          status: "human_review_required",
          amount: 250,
          documents: [
            { name: "Claim form", submitted: false },
            { name: "Medical report", submitted: false },
            { name: "Invoice / receipt", submitted: false },
          ],
          next_steps: ["Submit the required documents.", "Provide additional context."],
        }],
        policies: null,
      },
    });
    renderAt("/portal");
    await userEvent.click(screen.getByRole("button", { name: /open insurance ai agent/i }));
    const input = screen.getByPlaceholderText(/ask in english or khmer/i);
    await userEvent.type(input, "what is my claim status for number 6");
    await userEvent.click(screen.getByRole("button", { name: /send message/i }));
    expect(await screen.findByText("#6")).toBeInTheDocument();
    expect(screen.getByText("Under Review")).toBeInTheDocument();
    expect(screen.getByText("Required Documents:")).toBeInTheDocument();
    expect(screen.getByText("Claim form")).toBeInTheDocument();
    expect(screen.getByText("Medical report")).toBeInTheDocument();
    expect(screen.getByText("Next Steps:")).toBeInTheDocument();
    expect(screen.getByText("Submit the required documents.")).toBeInTheDocument();
  });

  it("renders structured policy info cards from the agent reply", async () => {
    mockAsk.mockResolvedValue({
      reply: "Here are your policies:",
      mode: "customer",
      actions: [],
      structured_data: {
        type: "policy_info",
        claims: null,
        policies: [{
          policy_number: "POL-102",
          product_name: "Health Insurance",
          status: "active",
          coverage_type: "health",
          end_date: "2026-12-31",
          benefits: ["Health out-patient", "Health in-patient"],
        }],
      },
    });
    renderAt("/portal");
    await userEvent.click(screen.getByRole("button", { name: /open insurance ai agent/i }));
    const input = screen.getByPlaceholderText(/ask in english or khmer/i);
    await userEvent.type(input, "what policies do I have");
    await userEvent.click(screen.getByRole("button", { name: /send message/i }));
    expect(await screen.findByText("POL-102")).toBeInTheDocument();
    expect(screen.getByText("Health Insurance")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByText("Covered Benefits:")).toBeInTheDocument();
    expect(screen.getByText("Health out-patient")).toBeInTheDocument();
  });

  it("renders bold text inside agent messages", async () => {
    mockAsk.mockResolvedValue({
      reply: "Your claim is **approved** and payment is on its way.",
      mode: "customer",
      actions: [],
      structured_data: null,
    });
    renderAt("/portal");
    await userEvent.click(screen.getByRole("button", { name: /open insurance ai agent/i }));
    const input = screen.getByPlaceholderText(/ask in english or khmer/i);
    await userEvent.type(input, "claim status");
    await userEvent.click(screen.getByRole("button", { name: /send message/i }));
    const strong = await screen.findByText("approved", { selector: "strong" });
    expect(strong).toBeInTheDocument();
    expect(strong.tagName).toBe("STRONG");
  });
});
