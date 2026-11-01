import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import PasskeyPanel from "./PasskeyPanel";
import { useApp } from "./store";

describe("PasskeyPanel", () => {
  it("renders register and sign-in buttons when WebAuthn is available", () => {
    vi.stubGlobal("navigator", { credentials: {} });
    render(<PasskeyPanel />);
    expect(screen.getByText(/Register passkey/i)).toBeInTheDocument();
    expect(screen.getByText(/Sign in with passkey/i)).toBeInTheDocument();
  });

  it("still offers the admin-token input when WebAuthn is unavailable", () => {
    vi.stubGlobal("navigator", {});
    render(<PasskeyPanel />);
    expect(screen.queryByText(/Register passkey/i)).not.toBeInTheDocument();
    expect(screen.getByPlaceholderText(/admin token/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Use token/i })).toBeInTheDocument();
  });

  it("accepts a pasted admin token", async () => {
    const { userEvent } = await import("@testing-library/user-event");
    vi.stubGlobal("navigator", { credentials: {} });
    render(<PasskeyPanel />);
    await userEvent.type(screen.getByPlaceholderText(/admin token/i), "demo-admin-token");
    await userEvent.click(screen.getByRole("button", { name: /Use token/i }));
    expect(useApp.getState().adminToken).toBe("demo-admin-token");
    useApp.getState().reset();
  });
});
