import { wsUrl } from "./api";
import { useApp } from "./store";

let activeWs: WebSocket | null = null;

export function connectWs(sessionId: number): () => void {
  let closed = false;
  let pingTimer: number | undefined;

  const open = () => {
    const token = useApp.getState().playerToken;
    const ws = new WebSocket(wsUrl(sessionId, token));
    activeWs = ws;
    ws.onopen = () => useApp.getState().setConnected(true);
    ws.onclose = () => {
      useApp.getState().setConnected(false);
      // auto-reconnect — but never on an ended session
      if (!closed && useApp.getState().state !== "ended") setTimeout(open, 1500);
    };
    ws.onerror = () => ws.close();
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data as string);
        if (msg.type === "snapshot") useApp.getState().setSnapshot(msg);
        else if (msg.type === "pong") return;
        else useApp.getState().pushEvent(msg.type, msg.payload);
      } catch {
        /* ignore malformed frames */
      }
    };
    pingTimer = window.setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "ping" }));
    }, 15000);
  };
  open();
  return () => {
    closed = true;
    window.clearInterval(pingTimer);
    activeWs?.close();
    activeWs = null;
  };
}

export function wsSend(msg: object): boolean {
  if (activeWs && activeWs.readyState === WebSocket.OPEN) {
    activeWs.send(JSON.stringify(msg));
    return true;
  }
  return false;
}
