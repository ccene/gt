import { useEffect, useState } from "react";
import { api } from "./api";
import { useApp } from "./store";
import { wsSend } from "./ws";

/** Campaign clock: default 1 hour, host can extend mid-session. */
export function CampaignBar() {
  const s = useApp((st) => st);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, []);

  const endsAt = s.campaign.ends_at ? Date.parse(s.campaign.ends_at) : null;
  const startedAt = s.campaign.started_at ? Date.parse(s.campaign.started_at) : null;
  const totalMs = endsAt && startedAt ? endsAt - startedAt : s.campaign.minutes * 60_000;
  const remainingMs = endsAt ? Math.max(0, endsAt - now) : totalMs;
  const elapsedPct = totalMs > 0 ? Math.min(100, (1 - remainingMs / totalMs) * 100) : 0;

  const fmt = (ms: number) => {
    const totalSec = Math.floor(ms / 1000);
    const h = Math.floor(totalSec / 3600);
    const m = Math.floor((totalSec % 3600) / 60);
    const sec = totalSec % 60;
    return h > 0 ? `${h}h ${String(m).padStart(2, "0")}m` : `${m}m ${String(sec).padStart(2, "0")}s`;
  };

  const extend = (minutes: number) => {
    if (s.sessionId != null && s.adminToken)
      void api.extendCampaign(s.sessionId, minutes, s.adminToken).catch(() => {});
  };

  return (
    <div className="panel campaign-bar" data-testid="campaign-bar">
      <div className="row spread">
        <h2>⏳ Campaign</h2>
        <span className="badge" data-testid="campaign-length">
          {s.campaign.minutes >= 60 ? `${s.campaign.minutes / 60}h` : `${s.campaign.minutes}min`} planned
        </span>
      </div>
      <div className="timer-track">
        <div className="timer-fill" style={{ width: `${elapsedPct}%` }} />
      </div>
      <div className="row spread">
        <span className="timer-label" data-testid="campaign-remaining">
          {endsAt ? `${fmt(remainingMs)} remaining` : "not started yet"}
        </span>
        {s.adminToken && s.state === "playing" && (
          <span className="row">
            <button className="small" onClick={() => extend(30)}>+30 min</button>
            <button className="small" onClick={() => extend(60)}>+1 hour</button>
          </span>
        )}
      </div>
    </div>
  );
}

const CONDITION_CHOICES = ["poisoned", "prone", "stunned", "frightened", "concentrating", "invisible", "restrained"];

/** Initiative / combat tracker — the tool DMs ask for most. */
export function CombatPanel() {
  const s = useApp((st) => st);
  const [enemyName, setEnemyName] = useState("");
  const [enemyHp, setEnemyHp] = useState(10);
  const isHost = !!s.adminToken;
  const sid = s.sessionId;

  const startWithHeroes = async () => {
    if (sid == null || !isHost) return;
    const combatants = s.characters.map((c) => ({
      name: c.name,
      hp: Number(c.sheet.hp ?? 10),
      max_hp: Number(c.sheet.max_hp ?? c.sheet.hp ?? 10),
      ac: c.sheet.ac != null ? Number(c.sheet.ac) : null,
      init_mod: Number(c.sheet.init_mod ?? 0),
      is_enemy: false,
      conditions: Array.isArray(c.sheet.conditions) ? (c.sheet.conditions as string[]) : [],
    }));
    try {
      await api.combatStart(sid, combatants, s.adminToken);
    } catch {
      /* surfaced via events */
    }
  };

  const addEnemy = async () => {
    if (sid == null || !isHost || !enemyName.trim()) return;
    const existing = s.combat.active ? s.combat.combatants : [];
    const combatants = [
      ...existing.map((c) => ({
        name: c.name, hp: c.hp, max_hp: c.max_hp, ac: c.ac, init_mod: c.init_mod,
        is_enemy: c.is_enemy, conditions: c.conditions, initiative: c.initiative,
      })),
      { name: enemyName.trim(), hp: enemyHp, max_hp: enemyHp, is_enemy: true, init_mod: 0, conditions: [] },
    ];
    setEnemyName("");
    try {
      await api.combatStart(sid, combatants, s.adminToken);
    } catch {
      /* ignore */
    }
  };

  const adj = (cid: number, hp_delta: number) => {
    if (sid != null) void api.combatUpdate(sid, cid, { hp_delta }).catch(() => {});
  };
  const toggleCond = (cid: number, cond: string) => {
    if (sid != null) void api.combatUpdate(sid, cid, { condition_toggle: cond }).catch(() => {});
  };

  if (!s.combat.active) {
    return (
      <div className="panel" data-testid="combat-panel">
        <h2>⚔️ Combat</h2>
        {isHost ? (
          <div className="row">
            <button className="primary" onClick={startWithHeroes} disabled={s.characters.length === 0}>
              Start combat (heroes)
            </button>
          </div>
        ) : (
          <p className="muted">No combat running — the host can start one.</p>
        )}
        {isHost && (
          <div className="row">
            <input value={enemyName} onChange={(e) => setEnemyName(e.target.value)} placeholder="Enemy name" />
            <input
              type="number"
              value={enemyHp}
              min={1}
              style={{ width: "5.5rem" }}
              onChange={(e) => setEnemyHp(Number(e.target.value))}
            />
            <button onClick={addEnemy} disabled={!enemyName.trim()}>Add enemy</button>
          </div>
        )}
      </div>
    );
  }

  const current = s.combat.combatants[s.combat.turn_index];
  return (
    <div className="panel" data-testid="combat-panel">
      <div className="row spread">
        <h2>⚔️ Combat — round {s.combat.round}</h2>
        {isHost && (
          <span className="row">
            <button className="small" onClick={() => sid != null && void api.combatRoll(sid, s.adminToken)}>Roll initiative</button>
            <button className="small primary" onClick={() => sid != null && void api.combatNext(sid, s.adminToken)}>
              Next turn →
            </button>
            <button className="small danger" onClick={() => sid != null && void api.combatEnd(sid, s.adminToken)}>
              End
            </button>
          </span>
        )}
      </div>
      <ol className="combat-list">
        {s.combat.combatants.map((c, i) => (
          <li key={c.id} className={`combatant ${i === s.combat.turn_index ? "current" : ""} ${c.hp <= 0 ? "down" : ""}`}>
            <div className="row spread">
              <strong>
                {c.is_enemy ? "👹" : "🛡️"} {c.name}
              </strong>
              <span className="badge">init {c.initiative}</span>
            </div>
            <div className="row spread">
              <span className="hp-controls">
                <button className="small" onClick={() => adj(c.id, -1)} aria-label={`damage ${c.name}`}>−</button>
                <span data-testid={`hp-${c.name}`}>
                  HP {c.hp}/{c.max_hp}
                </span>
                <button className="small" onClick={() => adj(c.id, 1)} aria-label={`heal ${c.name}`}>+</button>
                {c.ac != null && <span className="muted">AC {c.ac}</span>}
              </span>
            </div>
            <div className="row chips">
              {CONDITION_CHOICES.map((cond) => (
                <button
                  key={cond}
                  className={`chip ${c.conditions.includes(cond) ? "on" : ""}`}
                  onClick={() => toggleCond(c.id, cond)}
                >
                  {cond}
                </button>
              ))}
            </div>
          </li>
        ))}
      </ol>
      {current && <p className="muted">On turn: <strong>{current.name}</strong></p>}
      {isHost && (
        <div className="row">
          <input value={enemyName} onChange={(e) => setEnemyName(e.target.value)} placeholder="Add enemy mid-fight" />
          <input
            type="number"
            value={enemyHp}
            min={1}
            style={{ width: "5.5rem" }}
            onChange={(e) => setEnemyHp(Number(e.target.value))}
          />
          <button onClick={addEnemy} disabled={!enemyName.trim()}>Add</button>
        </div>
      )}
    </div>
  );
}

/** Table chat — works over WS, falls back to REST. */
export function ChatPanel() {
  const s = useApp((st) => st);
  const [text, setText] = useState("");
  const sid = s.sessionId;

  const send = () => {
    const msg = text.trim();
    if (!msg || sid == null) return;
    // the server attributes the sender from the WS token / X-Player-Token
    const ok = wsSend({ type: "chat", text: msg });
    if (!ok) void api.chat(sid, msg, s.playerToken).catch(() => {});
    setText("");
  };

  return (
    <div className="panel" data-testid="chat-panel">
      <h2>💬 Table chat</h2>
      <div className="chat-log">
        {s.chat.length === 0 && <p className="muted">No messages yet.</p>}
        {s.chat.map((m, i) => (
          <p key={i} className="chat-msg">
            <strong>{m.from}:</strong> {m.text}
          </p>
        ))}
      </div>
      <div className="row">
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Say something…" maxLength={500}
          onKeyDown={(e) => { if (e.key === "Enter") send(); }} />
        <button className="primary" onClick={send} disabled={!text.trim()}>Send</button>
      </div>
    </div>
  );
}
