import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import App from "./App";
import { useApp } from "./store";

vi.mock("./ws", () => ({ connectWs: () => () => {}, wsSend: vi.fn(() => true) }));

describe("App", () => {
  beforeEach(() => {
    useApp.getState().reset();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: true, json: async () => [] }))
    );
  });

  it("shows join screen when no session", () => {
    render(<App />);
    expect(screen.getByText(/Join your game session/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText("ABC123")).toBeInTheDocument();
  });

  it("shows table view with dice after snapshot", async () => {
    useApp.getState().setSnapshot({
      session: { id: 1, code: "XYZ789", state: "playing", chapter_index: 0, save_point: {} },
      characters: [{ id: 1, name: "Aria the Bold", player: "Aria", sheet: { hp: 30 } }],
      maps: [{ id: 1, label: "Old Crypt", markers: [{ x: 40, y: 50, label: "party" }] }],
      events: [],
      clients: 2,
    });
    render(<App />);
    await waitFor(() => expect(screen.getByText(/Old Crypt/i)).toBeInTheDocument());
    expect(screen.getByText("Aria the Bold")).toBeInTheDocument();
    expect(screen.getByText("d20")).toBeInTheDocument();
    expect(screen.getByText(/playing/i)).toBeInTheDocument();
  });
});
