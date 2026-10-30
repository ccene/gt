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

  it("throws on non-ok response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({ ok: false, status: 404, text: async () => "session not found" }))
    );
    await expect(api.getSession(999)).rejects.toThrow("404");
  });

  it("builds ws url", () => {
    expect(wsUrl(5)).toContain("/api/sessions/5/ws");
  });
});
