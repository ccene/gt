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
