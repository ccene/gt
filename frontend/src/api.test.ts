import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, wsUrl } from "./api";

function mockFetch(impl: (url: string, init?: RequestInit) => unknown) {
  return vi.fn(async (url: string, init?: RequestInit) => ({
    ok: true,
    status: 200,
    json: async () => impl(url, init),
    text: async () => JSON.stringify(impl(url, init)),
  }));
}

describe("api client", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", mockFetch(() => ({ ok: true })));
  });

  it("posts player creation", async () => {
    const f = mockFetch((_url, init) => JSON.parse(String(init?.body)));
    vi.stubGlobal("fetch", f);
    const res = await api.createPlayer("Aria", "a@b.c");
    expect(res).toEqual({ name: "Aria", email: "a@b.c" });
    expect(f).toHaveBeenCalledWith("/api/players", expect.objectContaining({ method: "POST" }));
  });

  it("sends admin token header", async () => {
    const f = mockFetch(() => ({ state: "playing" }));
    vi.stubGlobal("fetch", f);
    await api.setState(1, "playing", "tok123");
    const [, init] = f.mock.calls[0] as [string, RequestInit];
    expect((init.headers as Record<string, string>)["X-Admin-Token"]).toBe("tok123");
  });

  it("always sends Content-Type: application/json even without extra headers", async () => {
    // Regression: spreading `headers: undefined` used to wipe the JSON
    // content-type, so every PWA POST failed with 422 in the real browser.
    const f = mockFetch(() => ({ id: 1, code: "ABC123" }));
    vi.stubGlobal("fetch", f);
    await api.createSession(null, 60);
    const [, init] = f.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    expect(headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(String(init.body))).toEqual({ story_id: null, campaign_minutes: 60 });
  });

  it("merges extra headers with the JSON content-type", async () => {
    const f = mockFetch(() => ({}));
    vi.stubGlobal("fetch", f);
    await api.extendCampaign(1, 30, "tok");
    const [, init] = f.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    expect(headers["Content-Type"]).toBe("application/json");
    expect(headers["X-Admin-Token"]).toBe("tok");
  });

  it("throws on non-ok response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: false, status: 404, text: async () => "session not found" }))
    );
    await expect(api.getSession(999)).rejects.toThrow("404");
  });

  it("builds ws url with the player token", () => {
    expect(wsUrl(5, "tok123")).toContain("/api/sessions/5/ws");
    expect(wsUrl(5, "tok123")).toContain("token=tok123");
  });
});
