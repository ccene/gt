// Audit regression tests (frontend) — written before the fixes, confirmed red.
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { useApp } from "./store";
import { connectWs } from "./ws";

vi.mock("./ws", async (importOriginal) => {
  const mod = await importOriginal<typeof import("./ws")>();
  return { ...mod, wsSend: vi.fn(() => true) };
});

const SNAP = {
  session: { id: 5, code: "ABC123", state: "lobby", chapter_index: 0, save_point: {} },
  characters: [],
  maps: [],
  events: [],
  clients: 1,
};

describe("audit: CharacterForm", () => {
  beforeEach(() => {
    useApp.getState().reset();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => ({
        ok: true,
        json: async () =>
          url === "/api/players"
            ? [
                { id: 1, name: "Aria", email: "aria@example.com", character: null },
                { id: 2, name: "Bram", email: "bram@example.com", character: null },
              ]
            : { id: 9, name: "Aria the Bold", sheet: { hp: 30 } },
      }))
    );
  });

  it("lists players from the API in the select so a character can be saved", async () => {
    const { userEvent } = await import("@testing-library/user-event");
    useApp.getState().setSnapshot(SNAP);
    render(<App />);
    // the lobby character form must offer the known players
    const select = await screen.findByRole("combobox");
    await waitFor(() => expect(screen.getByRole("option", { name: "Aria" })).toBeInTheDocument());
    expect(screen.getByRole("option", { name: "Bram" })).toBeInTheDocument();

    await userEvent.selectOptions(select, "1");
    await userEvent.type(screen.getByPlaceholderText("Aria the Bold"), "Aria the Bold");
    await userEvent.click(screen.getByRole("button", { name: /Save character/i }));
    await waitFor(() => expect(screen.getByText(/Character saved/i)).toBeInTheDocument());
    const f = vi.mocked(fetch);
    const charCall = f.mock.calls.find(([url]) => String(url).includes("/character"));
    expect(charCall).toBeTruthy();
    expect(JSON.parse(String(charCall?.[1]?.body))).toMatchObject({ name: "Aria the Bold" });
  });
});

describe("audit: websocket lifecycle", () => {
  beforeEach(() => {
    useApp.getState().reset();
    vi.useFakeTimers();
  });

  function fakeWsClass() {
    const instances: { url: string; onclose: (() => void) | null; readyState: number; sent: string[] }[] = [];
    class FakeWS {
      static OPEN = 1;
      readyState = 1;
      onopen: (() => void) | null = null;
      onmessage: ((ev: { data: string }) => void) | null = null;
      onerror: (() => void) | null = null;
      onclose: (() => void) | null = null;
      sent: string[] = [];
      constructor(public url: string) {
        instances.push(this as never);
      }
      send(data: string) {
        this.sent.push(data);
      }
      close() {
        this.readyState = 3;
      }
    }
    return { FakeWS, instances };
  }

  it("carries the player token in the WS url", () => {
    const { FakeWS, instances } = fakeWsClass();
    vi.stubGlobal("WebSocket", FakeWS);
    useApp.getState().setSnapshot(SNAP);
    useApp.getState().setPlayerToken("tok123");
    const cleanup = connectWs(5);
    expect(instances[0].url).toContain("/api/sessions/5/ws");
    expect(instances[0].url).toContain("token=tok123");
    cleanup();
    vi.useRealTimers();
  });

  it("does not reconnect after the session ended", () => {
    const { FakeWS, instances } = fakeWsClass();
    vi.stubGlobal("WebSocket", FakeWS);
    useApp.getState().setSnapshot({ ...SNAP, session: { ...SNAP.session, state: "ended" } });
    const cleanup = connectWs(5);
    expect(instances.length).toBe(1);
    instances[0].onclose?.(); // connection dropped
    vi.advanceTimersByTime(10_000);
    expect(instances.length).toBe(1); // no reconnect loop on an ended session
    cleanup();
    vi.useRealTimers();
  });

  it("reconnects while the session is live", () => {
    const { FakeWS, instances } = fakeWsClass();
    vi.stubGlobal("WebSocket", FakeWS);
    useApp.getState().setSnapshot({ ...SNAP, session: { ...SNAP.session, state: "playing" } });
    const cleanup = connectWs(5);
    instances[0].onclose?.();
    vi.advanceTimersByTime(2_000);
    expect(instances.length).toBe(2);
    cleanup();
    vi.useRealTimers();
  });
});

describe("audit: lobby / character creation mid-session", () => {
  beforeEach(() => {
    useApp.getState().reset();
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => [] })));
  });

  it("shows the character form when a player joins a session already in play", () => {
    useApp.getState().setPlayerId(1);
    useApp.getState().setSnapshot({
      session: { id: 5, code: "ABC123", state: "playing", chapter_index: 0, save_point: {} },
      characters: [], // player 1 has no character yet
      maps: [],
      events: [],
      clients: 1,
    });
    render(<App />);
    expect(screen.getByText(/Your character/i)).toBeInTheDocument();
  });

  it("hides the character form once the player has a character (not in lobby)", () => {
    useApp.getState().setPlayerId(1);
    useApp.getState().setSnapshot({
      session: { id: 5, code: "ABC123", state: "playing", chapter_index: 0, save_point: {} },
      characters: [{ id: 9, name: "Aria the Bold", player: "Aria", player_id: 1, sheet: { hp: 30 } }],
      maps: [],
      events: [],
      clients: 1,
    });
    render(<App />);
    expect(screen.queryByText(/Your character/i)).not.toBeInTheDocument();
    expect(screen.getByText("Aria the Bold")).toBeInTheDocument();
  });

  it("stores the player id when joining", async () => {
    const { userEvent } = await import("@testing-library/user-event");
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => ({
        ok: true,
        json: async () =>
          url === "/api/players"
            ? [{ id: 7, name: "Aria", email: "a@b.c", character: null }]
            : url.includes("/api/sessions/join")
              ? { session_id: 5, player_token: "tok", state: "lobby", snapshot: { session: { id: 5, code: "ABC123", state: "lobby", chapter_index: 0, save_point: {} }, characters: [], maps: [], events: [], clients: 1 } }
              : { id: 7, name: "Aria", email: "a@b.c" },
      }))
    );
    render(<App />);
    await userEvent.type(screen.getByPlaceholderText("Aria"), "Aria");
    await userEvent.type(screen.getByPlaceholderText("ABC123"), "ABC123");
    await userEvent.click(screen.getByRole("button", { name: /Join session/i }));
    await waitFor(() => expect(useApp.getState().playerId).toBe(7));
    expect(useApp.getState().playerToken).toBe("tok");
  });
});

describe("audit: end-session feedback", () => {
  beforeEach(() => {
    useApp.getState().reset();
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => ({}) })));
  });

  it("shows a banner with save-point results when the session ends", async () => {
    useApp.getState().setSnapshot({
      session: { id: 5, code: "ABC123", state: "playing", chapter_index: 0, save_point: {} },
      characters: [],
      maps: [],
      events: [],
      clients: 1,
    });
    render(<App />);
    const { act } = await import("@testing-library/react");
    act(() => {
      useApp.getState().pushEvent("state", { state: "ended" });
      useApp.getState().pushEvent("session_ended", { emails: [{ player: "Aria", character: "AriaC", sent: false, via: "outbox" }] });
    });
    await waitFor(() => expect(screen.getByTestId("session-ended-banner")).toBeInTheDocument());
    expect(screen.getByTestId("session-ended-banner")).toHaveTextContent(/save point/i);
    expect(screen.getByTestId("session-ended-banner")).toHaveTextContent(/AriaC/);
  });
});

describe("audit: host login with a pasted admin token", () => {
  it("sets the admin token from the host-login input", async () => {
    const { userEvent } = await import("@testing-library/user-event");
    vi.stubGlobal("navigator", { credentials: {} });
    useApp.getState().reset();
    useApp.getState().setSnapshot({
      session: { id: 5, code: "DEMO42", state: "playing", chapter_index: 0, save_point: {} },
      characters: [],
      maps: [],
      events: [],
      clients: 1,
    });
    render(<App />);
    expect(screen.queryByText(/Host controls/i)).not.toBeInTheDocument(); // no token yet
    await userEvent.type(screen.getByPlaceholderText(/admin token/i), "demo-admin-token");
    await userEvent.click(screen.getByRole("button", { name: /use token/i }));
    await waitFor(() => expect(useApp.getState().adminToken).toBe("demo-admin-token"));
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: /Host controls/i })).toBeInTheDocument()
    );
  });
});
