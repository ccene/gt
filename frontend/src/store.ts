import type { CampaignInfo, CombatState, Story } from "./api";
import { create } from "./zustand-lite";

export interface DiceEvent {
  dice: string;
  rolls: number[];
  modifier: number;
  total: number;
  roller: string;
  mode?: string;
  kept?: number;
}

export interface ChatEvent {
  from: string;
  text: string;
}

export interface AppState {
  sessionId: number | null;
  code: string;
  adminToken: string;
  playerToken: string;
  playerId: number | null;
  endedEmails: { player?: string; character?: string; sent?: boolean; via?: string; error?: string }[];
  state: string;
  chapterIndex: number;
  savePoint: Record<string, unknown>;
  campaign: CampaignInfo;
  story: Story | null;
  combat: CombatState;
  clients: number;
  characters: { id: number; player_id?: number; name: string; player: string; sheet: Record<string, unknown> }[];
  maps: { id: number; label: string; markers: { x: number; y: number; label: string }[] }[];
  dice: DiceEvent[];
  narration: string[];
  chat: ChatEvent[];
  recap: string[];
  connected: boolean;
  setSnapshot: (s: {
    session: { id: number; code: string; state: string; chapter_index: number; save_point: Record<string, unknown> };
    campaign?: CampaignInfo;
    story?: Story | null;
    combat?: CombatState;
    characters: AppState["characters"];
    maps: AppState["maps"];
    events: { kind: string; payload: unknown; at?: string }[];
    clients: number;
  }) => void;
  pushEvent: (kind: string, payload: unknown) => void;
  setConnected: (v: boolean) => void;
  setAdminToken: (t: string) => void;
  setPlayerToken: (t: string) => void;
  setPlayerId: (id: number | null) => void;
  reset: () => void;
}

const initial = {
  sessionId: null,
  code: "",
  adminToken: "",
  playerToken: "",
  playerId: null,
  endedEmails: [],
  state: "lobby",
  chapterIndex: 0,
  savePoint: {},
  campaign: { minutes: 60, started_at: null, ends_at: null } as CampaignInfo,
  story: null,
  combat: { active: false, round: 0, turn_index: 0, combatants: [] } as CombatState,
  clients: 0,
  characters: [],
  maps: [],
  dice: [],
  narration: [],
  chat: [],
  recap: [],
  connected: false,
};

export const useApp = create<AppState>((set: (p: Partial<AppState> | ((s: AppState) => Partial<AppState>)) => void) => ({
  ...initial,
  setSnapshot: (s: {
    session: { id: number; code: string; state: string; chapter_index: number; save_point: Record<string, unknown> };
    campaign?: CampaignInfo;
    story?: Story | null;
    combat?: CombatState;
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
      campaign: s.campaign ?? initial.campaign,
      story: s.story ?? null,
      combat: s.combat ?? initial.combat,
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
      recap: s.events
        .filter((e: { kind: string }) => e.kind === "recap")
        .map((e: { payload: unknown }) => (e.payload as { text?: string }).text ?? "")
        .slice(-5),
    }),
  pushEvent: (kind: string, payload: unknown) =>
    set((st: AppState) => {
      if (kind === "dice") return { dice: [...st.dice, payload as DiceEvent].slice(-20) };
      if (kind === "narration")
        return { narration: [...st.narration, (payload as { text?: string }).text ?? ""].slice(-10) };
      if (kind === "chat") return { chat: [...st.chat, payload as ChatEvent].slice(-50) };
      if (kind === "recap")
        return { recap: [...st.recap, (payload as { text?: string }).text ?? ""].slice(-5) };
      if (kind === "campaign") return { campaign: payload as CampaignInfo };
      if (kind === "combat") return { combat: payload as CombatState };
      if (kind === "character") {
        const updated = payload as { id: number; sheet: Record<string, unknown> };
        return {
          characters: st.characters.map((c) => (c.id === updated.id ? { ...c, sheet: updated.sheet } : c)),
        };
      }
      if (kind === "state")
        return { state: (payload as { state: string }).state };
      if (kind === "session_ended")
        return { endedEmails: (payload as { emails: AppState["endedEmails"] }).emails ?? [] };
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
  setPlayerToken: (t: string) => set({ playerToken: t }),
  setPlayerId: (id: number | null) => set({ playerId: id }),
  reset: () => set(initial),
}));
