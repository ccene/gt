import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import PasskeyPanel from "./PasskeyPanel";

describe("PasskeyPanel", () => {
  it("renders register and sign-in buttons when WebAuthn is available", () => {
    vi.stubGlobal("navigator", { credentials: {} });
    render(<PasskeyPanel />);
    expect(screen.getByText(/Register passkey/i)).toBeInTheDocument();
    expect(screen.getByText(/Sign in with passkey/i)).toBeInTheDocument();
  });

  it("renders nothing when WebAuthn is unavailable", () => {
    vi.stubGlobal("navigator", {});
    const { container } = render(<PasskeyPanel />);
    expect(container.firstChild).toBeNull();
  });
});
