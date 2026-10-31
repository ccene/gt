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
    expect(screen.getByText(/Quick host/i)).toBeInTheDocument();
    expect(screen.getByTestId("generate-and-host")).toBeInTheDocument();
  });

  it("host button creates a session and shows the big code", async () => {
    const { userEvent } = await import("@testing-library/user-event");
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => ({
        ok: true,
        json: async () =>
          url.includes("/api/sessions") && !url.includes("join")
            ? { id: 5, code: "K7XQ2M", admin_token: "tok", state: "lobby", chapter_index: 0, save_point: {}, clients: 0 }
            : { session_id: 5, snapshot: { session: { id: 5, code: "K7XQ2M", state: "lobby", chapter_index: 0, save_point: {} }, characters: [], maps: [], events: [], clients: 1 } },
      }))
    );
    render(<App />);
    await userEvent.click(screen.getByText(/Quick host/i));
    expect(await screen.findByTestId("host-code")).toBeInTheDocument();
    expect(screen.getByText("K7XQ2M")).toBeInTheDocument();
  });

  it("generate story & host sends the idea to the LLM then creates the session", async () => {
    const { userEvent } = await import("@testing-library/user-event");
    const calls: { url: string; body: unknown; headers: unknown }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        calls.push({ url, body: init?.body ? JSON.parse(String(init.body)) : null, headers: init?.headers });
        return {
          ok: true,
          json: async () =>
            url.includes("/api/stories/generate")
              ? { id: 9, title: "Sky Pirates", length_hours: 1, content: { campaign: { title: "Sky Pirates", chapters: [] } } }
              : url.includes("/api/sessions") && !url.includes("join")
                ? { id: 5, code: "K7XQ2M", admin_token: "tok", state: "lobby", chapter_index: 0, save_point: {}, campaign: { minutes: 60, started_at: null, ends_at: null }, clients: 0 }
                : { session_id: 5, snapshot: { session: { id: 5, code: "K7XQ2M", state: "lobby", chapter_index: 0, save_point: {} }, characters: [], maps: [], events: [], clients: 1 } },
        };
      })
    );
    render(<App />);
    await userEvent.type(screen.getByPlaceholderText(/sky-pirates/i), "sky pirates raid a castle");
    await userEvent.click(screen.getByTestId("generate-and-host"));
    expect(await screen.findByTestId("host-code")).toBeInTheDocument();
    expect(screen.getByText("K7XQ2M")).toBeInTheDocument();
    const gen = calls.find((c) => c.url.includes("/api/stories/generate"));
    expect(gen?.body).toMatchObject({ prompt: "sky pirates raid a castle", length_hours: 1 });
    const create = calls.find((c) => c.url === "/api/sessions");
    expect(create?.body).toMatchObject({ story_id: 9, campaign_minutes: 60 });
    // the JSON content-type must survive even when no extra headers are passed
    expect((gen?.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
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
