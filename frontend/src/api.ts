export interface Player {
  id: number;
  name: string;
  email: string;
  character: { id: number; name: string; sheet: Record<string, unknown> } | null;
}

export interface SessionInfo {
  id: number;
  code: string;
  state: string;
  chapter_index: number;
  save_point: Record<string, unknown>;
  campaign: CampaignInfo;
  clients: number;
}

export interface CampaignInfo {
  minutes: number;
  started_at: string | null;
  ends_at: string | null;
}

export interface Campaign {
  title: string;
  logline?: string;
  setting?: string;
  opening_scene?: string;
  chapters?: { title: string; summary?: string; key_scenes?: string[] }[];
  npcs?: { name: string; role?: string; one_liner?: string }[];
}

export interface Story {
  id: number;
  title: string;
  source: string;
  content: { provider?: string; length_hours?: number; campaign?: Campaign; [k: string]: unknown };
}

export interface StoryGenerated {
  id: number;
  title: string;
  length_hours: number;
  content: Story["content"];
}

export interface Combatant {
  id: number;
  name: string;
  initiative: number;
  init_mod: number;
  hp: number;
  max_hp: number;
  ac: number | null;
  is_enemy: boolean;
  conditions: string[];
  turn_order: number;
}

export interface CombatState {
  active: boolean;
  round: number;
  turn_index: number;
  combatants: Combatant[];
}

export interface Snapshot {
  type: "snapshot";
  session: { id: number; code: string; state: string; chapter_index: number; save_point: Record<string, unknown> };
  campaign: CampaignInfo;
  story: Story | null;
  combat: CombatState;
  characters: { id: number; name: string; player: string; sheet: Record<string, unknown> }[];
  maps: { id: number; label: string; markers: MapMarker[] }[];
  events: { kind: string; payload: unknown; at: string }[];
  clients: number;
}

export interface MapMarker {
  x: number;
  y: number;
  label: string;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers as Record<string, string> | undefined) },
  });
  if (!resp.ok) {
    throw new Error(`${resp.status}: ${await resp.text()}`);
  }
  return resp.json() as Promise<T>;
}

export const api = {
  createPlayer: (name: string, email: string) =>
    req<Player>("/api/players", {
      method: "POST",
      body: JSON.stringify({ name, email }),
    }),
  listPlayers: () => req<Player[]>("/api/players"),
  submitCharacter: (playerId: number, name: string, sheet: Record<string, unknown>) =>
    req("/api/players/" + playerId + "/character", {
      method: "POST",
      body: JSON.stringify({ name, sheet }),
    }),
  createSession: (storyId: number | null = null, campaignMinutes = 60, adminToken = "") =>
    req<SessionInfo & { admin_token?: string }>("/api/sessions", {
      method: "POST",
      body: JSON.stringify({ story_id: storyId, campaign_minutes: campaignMinutes }),
      headers: adminToken ? { "X-Admin-Token": adminToken } : undefined,
    }),
  extendCampaign: (id: number, minutes: number, adminToken: string) =>
    req<CampaignInfo>(`/api/sessions/${id}/campaign/extend`, {
      method: "POST",
      body: JSON.stringify({ minutes }),
      headers: { "X-Admin-Token": adminToken },
    }),
  joinSession: (code: string, playerId: number | null = null) =>
    req<{ session_id: number; player_token: string; state: string; snapshot: Snapshot }>(
      "/api/sessions/join",
      { method: "POST", body: JSON.stringify({ code, player_id: playerId }) }
    ),
  getSession: (id: number) => req<SessionInfo>(`/api/sessions/${id}`),
  setState: (id: number, state: string, adminToken: string) =>
    req<SessionInfo>(`/api/sessions/${id}/state`, {
      method: "POST",
      body: JSON.stringify({ state }),
      headers: { "X-Admin-Token": adminToken },
    }),
  nextChapter: (id: number, adminToken: string) =>
    req<SessionInfo>(`/api/sessions/${id}/chapter`, {
      method: "POST",
      headers: { "X-Admin-Token": adminToken },
    }),
  roll: (id: number, count: number, faces: number, modifier: number, roller: string, mode = "normal") =>
    req(`/api/sessions/${id}/roll`, {
      method: "POST",
      body: JSON.stringify({ count, faces, modifier, roller, mode }),
    }),
  chat: (id: number, text: string, playerToken: string) =>
    req<{ from: string; text: string }>(`/api/sessions/${id}/chat`, {
      method: "POST",
      body: JSON.stringify({ text }),
      headers: { "X-Player-Token": playerToken },
    }),
  recap: (id: number) =>
    req<{ provider: string; text: string }>(`/api/sessions/${id}/recap`, { method: "POST", body: "{}" }),
  updateCharacter: (sessionId: number, characterId: number, patch: Record<string, unknown>) =>
    req<{ id: number; name: string; sheet: Record<string, unknown> }>(
      `/api/sessions/${sessionId}/characters/${characterId}/update`,
      { method: "POST", body: JSON.stringify(patch) }
    ),
  combatStart: (id: number, combatants: Partial<Combatant>[], adminToken: string) =>
    req<CombatState>(`/api/sessions/${id}/combat`, {
      method: "POST",
      body: JSON.stringify({ combatants }),
      headers: { "X-Admin-Token": adminToken },
    }),
  combatRoll: (id: number, adminToken: string) =>
    req<CombatState>(`/api/sessions/${id}/combat/roll`, {
      method: "POST",
      body: "{}",
      headers: { "X-Admin-Token": adminToken },
    }),
  combatNext: (id: number, adminToken: string) =>
    req<CombatState>(`/api/sessions/${id}/combat/next`, {
      method: "POST",
      body: "{}",
      headers: { "X-Admin-Token": adminToken },
    }),
  combatUpdate: (id: number, combatantId: number, patch: Record<string, unknown>) =>
    req<CombatState>(`/api/sessions/${id}/combat/${combatantId}`, {
      method: "POST",
      body: JSON.stringify(patch),
    }),
  combatEnd: (id: number, adminToken: string) =>
    req<CombatState>(`/api/sessions/${id}/combat/end`, {
      method: "POST",
      body: "{}",
      headers: { "X-Admin-Token": adminToken },
    }),
  narrate: (id: number, scene: string) =>
    req<{ provider: string; text: string }>(`/api/sessions/${id}/narrate`, {
      method: "POST",
      body: JSON.stringify({ scene }),
    }),
  setMap: (id: number, label: string, markers: MapMarker[], adminToken: string) =>
    req(`/api/sessions/${id}/maps`, {
      method: "POST",
      body: JSON.stringify({ label, markers }),
      headers: { "X-Admin-Token": adminToken },
    }),
  generateCampaign: (prompt: string, lengthHours: number, genre = "classic fantasy", tone = "heroic") =>
    req<StoryGenerated>("/api/stories/generate", {
      method: "POST",
      body: JSON.stringify({ prompt, length_hours: lengthHours, genre, tone }),
    }),
  listStories: () => req<Story[]>("/api/stories"),
  aiHealth: () => req<Record<string, unknown>>("/api/ai/health"),
};

export function wsUrl(sessionId: number, token: string): string {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const q = token ? `?token=${encodeURIComponent(token)}` : "";
  return `${proto}://${location.host}/api/sessions/${sessionId}/ws${q}`;
}
