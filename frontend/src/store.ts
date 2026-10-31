import { create } from "./zustand-lite";

export interface DiceEvent {
  dice: string;
  rolls: number[];
  modifier: number;
  total: number;
  roller: string;
}

export interface ChatEvent {
  from: string;
  text: string;
}

export interface AppState {
  sessionId: number | null;
  code: string;
  adminToken: string;
  state: string;
  chapterIndex: number;
  savePoint: Record<string, unknown>;
  clients: number;
  characters: { id: number; name: string; player: string; sheet: Record<string, unknown> }[];
  maps: { id: number; label: string; markers: { x: number; y: number; label: string }[] }[];
  dice: DiceEvent[];
  narration: string[];
  chat: ChatEvent[];
  connected: boolean;
  setSnapshot: (s: {
    session: { id: number; code: string; state: string; chapter_index: number; save_point: Record<string, unknown> };
    characters: AppState["characters"];
    maps: AppState["maps"];
    events: { kind: string; payload: unknown; at?: string }[];
    clients: number;
  }) => void;
  pushEvent: (kind: string, payload: unknown) => void;
  setConnected: (v: boolean) => void;
  setAdminToken: (t: string) => void;
  reset: () => void;
}

const initial = {
  sessionId: null,
  code: "",
  adminToken: "",
  state: "lobby",
  chapterIndex: 0,
  savePoint: {},
  clients: 0,
  characters: [],
  maps: [],
  dice: [],
  narration: [],
  chat: [],
  connected: false,
};

export const useApp = create<AppState>((set: (p: Partial<AppState> | ((s: AppState) => Partial<AppState>)) => void) => ({
  ...initial,
  setSnapshot: (s: {
    session: { id: number; code: string; state: string; chapter_index: number; save_point: Record<string, unknown> };
    characters: AppState["characters"];
    maps: AppState["maps"];
    events: { kind: string; payload: unknown }[];
    clients: number;
  }) =>
    set({
      sessionId: s.session.id,
      code: s.session.code,
      state: s.session.state,
      chapterIndex: s.session.chapter_index,
      savePoint: s.session.save_point,
      characters: s.characters,
      maps: s.maps,
      clients: s.clients,
      dice: s.events
        .filter((e: { kind: string }) => e.kind === "dice")
        .map((e: { payload: unknown }) => e.payload as unknown as DiceEvent)
        .slice(-20),
      narration: s.events
        .filter((e: { kind: string }) => e.kind === "narration")
        .map((e: { payload: unknown }) => (e.payload as { text?: string }).text ?? "")
        .slice(-10),
      chat: s.events
        .filter((e: { kind: string }) => e.kind === "chat")
        .map((e: { payload: unknown }) => e.payload as unknown as ChatEvent)
        .slice(-50),
    }),
  pushEvent: (kind: string, payload: unknown) =>
    set((st: AppState) => {
      if (kind === "dice") return { dice: [...st.dice, payload as DiceEvent].slice(-20) };
      if (kind === "narration")
        return { narration: [...st.narration, (payload as { text?: string }).text ?? ""].slice(-10) };
      if (kind === "chat") return { chat: [...st.chat, payload as ChatEvent].slice(-50) };
      if (kind === "state")
        return { state: (payload as { state: string }).state };
      if (kind === "chapter")
        return {
          chapterIndex: (payload as { chapter_index: number }).chapter_index,
          savePoint: (payload as { save_point: Record<string, unknown> }).save_point,
          state: "loading",
        };
      if (kind === "map") return { maps: [...st.maps, payload as AppState["maps"][number]] };
      return st;
    }),
  setConnected: (v: boolean) => set({ connected: v }),
  setAdminToken: (t: string) => set({ adminToken: t }),
  reset: () => set(initial),
}));
