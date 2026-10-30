import { beforeEach, describe, expect, it } from "vitest";
import { useApp } from "./store";

describe("store", () => {
  beforeEach(() => useApp.getState().reset());

  it("applies a snapshot", () => {
    useApp.getState().setSnapshot({
      session: { id: 7, code: "ABC123", state: "playing", chapter_index: 2, save_point: { label: "Chapter 3" } },
      characters: [{ id: 1, name: "Aria", player: "Aria", sheet: { hp: 30 } }],
      maps: [{ id: 1, label: "crypt", markers: [{ x: 10, y: 20, label: "party" }] }],
      events: [
        { kind: "dice", payload: { dice: "1d20", rolls: [17], modifier: 0, total: 17, roller: "Aria" } as never },
        { kind: "narration", payload: { text: "Darkness…" } as never },
      ],
      clients: 3,
    });
    const s = useApp.getState();
    expect(s.sessionId).toBe(7);
    expect(s.state).toBe("playing");
    expect(s.chapterIndex).toBe(2);
    expect(s.characters[0].name).toBe("Aria");
    expect(s.dice[0].total).toBe(17);
    expect(s.narration).toContain("Darkness…");
  });

  it("pushes live events", () => {
    useApp.getState().pushEvent("dice", { dice: "2d6", rolls: [3, 5], modifier: 1, total: 9, roller: "Bob" });
    useApp.getState().pushEvent("state", { state: "ended" });
    useApp.getState().pushEvent("chapter", { chapter_index: 4, save_point: { label: "Chapter 5" } });
    const s = useApp.getState();
    expect(s.dice.at(-1)?.total).toBe(9);
    expect(s.state).toBe("loading"); // chapter event sets loading
    expect(s.chapterIndex).toBe(4);
  });

  it("caps dice history", () => {
    for (let i = 0; i < 30; i++) {
      useApp.getState().pushEvent("dice", { dice: "1d4", rolls: [1], modifier: 0, total: 1, roller: "x" });
    }
    expect(useApp.getState().dice.length).toBe(20);
  });
});
