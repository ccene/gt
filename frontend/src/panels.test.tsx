import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CampaignBar, ChatPanel, CombatPanel } from "./panels";
import { useApp } from "./store";

vi.mock("./ws", () => ({ wsSend: vi.fn(() => true), connectWs: () => () => {} }));

const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => ({ ok: true, json: async () => ({}) }));

function seedSession(overrides: Record<string, unknown> = {}) {
  useApp.getState().setSnapshot({
    session: { id: 5, code: "ABC123", state: "playing", chapter_index: 0, save_point: {} },
    campaign: {
      minutes: 60,
      started_at: new Date(Date.now() - 10 * 60_000).toISOString(),
      ends_at: new Date(Date.now() + 50 * 60_000).toISOString(),
    },
    story: null,
    combat: { active: false, round: 0, turn_index: 0, combatants: [] },
    characters: [
      { id: 1, name: "Aria", player: "Aria", sheet: { hp: 30, max_hp: 30, ac: 16, init_mod: 2 } },
    ],
    maps: [],
    events: [],
    clients: 1,
    ...overrides,
  });
  useApp.getState().setAdminToken("tok");
}

describe("CampaignBar", () => {
  beforeEach(() => {
    useApp.getState().reset();
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockClear();
  });

  it("shows the planned length and a live remaining time", () => {
    seedSession();
    render(<CampaignBar />);
    expect(screen.getByTestId("campaign-length")).toHaveTextContent("1h planned");
    expect(screen.getByTestId("campaign-remaining")).toHaveTextContent(/remaining/);
  });

  it("shows extend buttons to the host while playing and calls the API", async () => {
    const { userEvent } = await import("@testing-library/user-event");
    seedSession();
    render(<CampaignBar />);
    await userEvent.click(screen.getByText("+30 min"));
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/sessions/5/campaign/extend");
    expect(JSON.parse(String(init.body))).toEqual({ minutes: 30 });
  });

  it("hides extend buttons from players (no admin token)", () => {
    seedSession();
    useApp.getState().setAdminToken("");
    render(<CampaignBar />);
    expect(screen.queryByText("+30 min")).not.toBeInTheDocument();
  });
});

describe("CombatPanel", () => {
  beforeEach(() => {
    useApp.getState().reset();
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockClear();
  });

  it("host can start combat with the heroes", async () => {
    const { userEvent } = await import("@testing-library/user-event");
    seedSession();
    render(<CombatPanel />);
    await userEvent.click(screen.getByText(/Start combat/));
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/sessions/5/combat");
    const body = JSON.parse(String(init.body));
    expect(body.combatants[0].name).toBe("Aria");
    expect((init.headers as Record<string, string>)["X-Admin-Token"]).toBe("tok");
  });

  it("renders the turn order and advances turns", async () => {
    const { userEvent } = await import("@testing-library/user-event");
    seedSession({
      combat: {
        active: true,
        round: 1,
        turn_index: 0,
        combatants: [
          { id: 1, name: "Aria", initiative: 18, init_mod: 2, hp: 30, max_hp: 30, ac: 16, is_enemy: false, conditions: [], turn_order: 0 },
          { id: 2, name: "Goblin", initiative: 12, init_mod: 1, hp: 7, max_hp: 7, ac: 13, is_enemy: true, conditions: ["poisoned"], turn_order: 1 },
        ],
      },
    });
    render(<CombatPanel />);
    expect(screen.getByText(/round 1/)).toBeInTheDocument();
    expect(screen.getByTestId("hp-Goblin")).toHaveTextContent("HP 7/7");
    await userEvent.click(screen.getByText(/Next turn/));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/sessions/5/combat/next", expect.anything()));
  });

  it("applies damage and toggles conditions via the API", async () => {
    const { userEvent } = await import("@testing-library/user-event");
    seedSession({
      combat: {
        active: true,
        round: 1,
        turn_index: 0,
        combatants: [
          { id: 2, name: "Goblin", initiative: 12, init_mod: 1, hp: 7, max_hp: 7, ac: 13, is_enemy: true, conditions: [], turn_order: 0 },
        ],
      },
    });
    render(<CombatPanel />);
    await userEvent.click(screen.getByLabelText("damage Goblin"));
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    let call = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(call[0]).toBe("/api/sessions/5/combat/2");
    expect(JSON.parse(String(call[1].body))).toEqual({ hp_delta: -1 });

    await userEvent.click(screen.getByText("poisoned"));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    call = fetchMock.mock.calls[1] as unknown as [string, RequestInit];
    expect(JSON.parse(String(call[1].body))).toEqual({ condition_toggle: "poisoned" });
  });

  it("shows a waiting note to players when no combat is running", () => {
    seedSession();
    useApp.getState().setAdminToken("");
    render(<CombatPanel />);
    expect(screen.getByText(/No combat running/)).toBeInTheDocument();
  });
});

describe("ChatPanel", () => {
  beforeEach(() => {
    useApp.getState().reset();
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockClear();
  });

  it("sends over WS when connected and renders incoming messages", async () => {
    const { userEvent } = await import("@testing-library/user-event");
    const { wsSend } = await import("./ws");
    seedSession();
    render(<ChatPanel />);
    await userEvent.type(screen.getByPlaceholderText(/Say something/i), "hello{Enter}");
    expect(wsSend).toHaveBeenCalledWith({ type: "chat", text: "hello" });

    useApp.getState().pushEvent("chat", { from: "Aria", text: "hi there" });
    await waitFor(() => expect(screen.getByText("hi there")).toBeInTheDocument());
  });

  it("falls back to REST with the player token when the socket is down", async () => {
    const { userEvent } = await import("@testing-library/user-event");
    const { wsSend } = await import("./ws");
    (wsSend as ReturnType<typeof vi.fn>).mockReturnValue(false);
    seedSession();
    useApp.getState().setPlayerToken("tok123");
    render(<ChatPanel />);
    await userEvent.type(screen.getByPlaceholderText(/Say something/i), "ping{Enter}");
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/sessions/5/chat");
    expect(JSON.parse(String(init.body))).toEqual({ text: "ping" });
    expect((init.headers as Record<string, string>)["X-Player-Token"]).toBe("tok123");
  });
});
