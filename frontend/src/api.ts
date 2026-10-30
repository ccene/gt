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
  clients: number;
}

export interface Snapshot {
  type: "snapshot";
  session: { id: number; code: string; state: string; chapter_index: number; save_point: Record<string, unknown> };
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
    headers: { "Content-Type": "application/json" },
    ...init,
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
  createSession: (storyId: number | null = null, adminToken = "") =>
    req<SessionInfo & { admin_token?: string }>("/api/sessions", {
      method: "POST",
      body: JSON.stringify({ story_id: storyId }),
      headers: adminToken ? { "X-Admin-Token": adminToken } : undefined,
    }),
  joinSession: (code: string) =>
    req<{ session_id: number; player_token: string; state: string; snapshot: Snapshot }>(
      "/api/sessions/join",
      { method: "POST", body: JSON.stringify({ code }) }
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
  roll: (id: number, count: number, faces: number, modifier: number, roller: string) =>
    req(`/api/sessions/${id}/roll`, {
      method: "POST",
      body: JSON.stringify({ count, faces, modifier, roller }),
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
  generateStory: (genre: string, tone: string) =>
    req("/api/stories/generate", { method: "POST", body: JSON.stringify({ genre, tone }) }),
  aiHealth: () => req<Record<string, unknown>>("/api/ai/health"),
};

export function wsUrl(sessionId: number): string {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${location.host}/api/sessions/${sessionId}/ws`;
}
