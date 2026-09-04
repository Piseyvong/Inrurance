import "../test/setup";

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";

import { InsuranceAgentBubble } from "./InsuranceAgentBubble";

function renderAt(path: string) {
  return render(<MemoryRouter initialEntries={[path]}><InsuranceAgentBubble /></MemoryRouter>);
}

describe("InsuranceAgentBubble", () => {
  beforeEach(() => sessionStorage.clear());

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
});
