import { useEffect, useState } from "react";
import { api } from "./api";
import { useApp } from "./store";
import { connectWs, wsSend } from "./ws";
import AudioPanel, { VisionButton } from "./AudioPanel";
import PasskeyPanel from "./PasskeyPanel";
import "./styles.css";

const FACES = [4, 6, 8, 10, 12, 20, 100];

function JoinScreen() {
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [hosted, setHosted] = useState<{ code: string; admin_token?: string } | null>(null);

  const hostNew = async () => {
    setBusy(true);
    setError("");
    try {
      const s = await api.createSession(null);
      setHosted({ code: s.code, admin_token: s.admin_token });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const join = async () => {
    setBusy(true);
    setError("");
    try {
      let player = (await api.listPlayers()).find((p) => p.name.toLowerCase() === name.trim().toLowerCase());
      if (!player) player = await api.createPlayer(name.trim(), email.trim());
      const joined = await api.joinSession(code.trim().toUpperCase());
      useApp.getState().setSnapshot(joined.snapshot);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="screen">
      <h1 className="title">⚔️ D&amp;D Table</h1>
      <p className="subtitle">Join your game session</p>
      <label>
        Your name
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Aria" autoComplete="name" />
      </label>
      <label>
        Email (for your save point)
        <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="aria@example.com" type="email" />
      </label>
      <label>
        Session code
        <input
          className="code-input"
          value={code}
          onChange={(e) => setCode(e.target.value.toUpperCase())}
          placeholder="ABC123"
          maxLength={6}
        />
      </label>
      {error && <p className="error">{error}</p>}
      <button className="primary" disabled={busy || !code || !name} onClick={join}>
        {busy ? "Joining…" : "Join session"}
      </button>
      <div className="divider"><span>or</span></div>
      <button className="host-btn" disabled={busy} onClick={hostNew}>
        🎲 Host a new game
      </button>
      {hosted && (
        <div className="host-code" data-testid="host-code">
          <p className="muted">Share this code with your players:</p>
          <div className="big-code">{hosted.code}</div>
          <button
            className="primary"
            onClick={() => {
              useApp.getState().setAdminToken(hosted.admin_token ?? "");
              void api.joinSession(hosted.code).then((j) => useApp.getState().setSnapshot(j.snapshot));
            }}
          >
            Enter as host →
          </button>
        </div>
      )}
    </div>
  );
}

function CharacterForm() {
  const players = useApp((s) => s);
  const [playerId, setPlayerId] = useState<number | null>(null);
  const [charName, setCharName] = useState("");
  const [hp, setHp] = useState(20);
  const [charClass, setCharClass] = useState("Fighter");
  const [level, setLevel] = useState(1);
  const [msg, setMsg] = useState("");

  const submit = async () => {
    if (!playerId) return;
    await api.submitCharacter(playerId, charName, { hp, class: charClass, level });
    setMsg("Character saved ✓");
  };

  return (
    <div className="panel">
      <h2>Your character</h2>
      <label>
        Player
        <select value={playerId ?? ""} onChange={(e) => setPlayerId(Number(e.target.value))}>
          <option value="">— choose —</option>
          {players.characters.length === 0 && <option value="" disabled>(create via join screen first)</option>}
        </select>
      </label>
      <label>
        Character name
        <input value={charName} onChange={(e) => setCharName(e.target.value)} placeholder="Aria the Bold" />
      </label>
      <div className="row">
        <label>
          HP
          <input type="number" value={hp} onChange={(e) => setHp(Number(e.target.value))} />
        </label>
        <label>
          Level
          <input type="number" value={level} min={1} max={20} onChange={(e) => setLevel(Number(e.target.value))} />
        </label>
      </div>
      <label>
        Class
        <input value={charClass} onChange={(e) => setCharClass(e.target.value)} />
      </label>
      <button className="primary" disabled={!playerId || !charName} onClick={submit}>
        Save character
      </button>
      {msg && <p className="ok">{msg}</p>}
    </div>
  );
}

function DicePad() {
  const sessionId = useApp((s) => s.sessionId);
  const [mod, setMod] = useState(0);
  void 0;
  const dice = useApp((s) => s.dice);
  const last = dice[dice.length - 1];

  const roll = (f: number) => {
    if (sessionId == null) return;
    wsSend({ type: "roll", count: 1, faces: f, modifier: mod, roller: "you" });
  };

  return (
    <div className="panel">
      <h2>Dice</h2>
      {last && (
        <div className="dice-result" data-testid="last-roll">
          <span className="dice-total">{last.total}</span>
          <span className="dice-detail">
            {last.dice}: [{last.rolls.join(", ")}] {last.modifier !== 0 ? `${last.modifier > 0 ? "+" : ""}${last.modifier}` : ""} by {last.roller}
          </span>
        </div>
      )}
      <div className="dice-grid">
        {FACES.map((f) => (
          <button key={f} className="die" onClick={() => roll(f)}>
            d{f}
          </button>
        ))}
      </div>
      <label className="mod-row">
        Modifier
        <input type="number" value={mod} onChange={(e) => setMod(Number(e.target.value))} />
      </label>
    </div>
  );
}

function TableView() {
  const s = useApp((st) => st);
  const map = s.maps[s.maps.length - 1];
  return (
    <div className="panel">
      <h2>Table</h2>
      <div className="status-row">
        <span className={`badge state-${s.state}`}>{s.state}</span>
        <span className="badge">chapter {s.chapterIndex + 1}</span>
        <span className="badge">{s.clients} connected</span>
        <span className={`badge conn-${s.connected ? "up" : "down"}`}>{s.connected ? "● live" : "○ offline"}</span>
      </div>
      {map && (
        <div className="map" data-testid="map">
          <div className="map-label">{map.label}</div>
          {map.markers.map((m, i) => (
            <div key={i} className="marker" style={{ left: `${m.x}%`, top: `${m.y}%` }}>
              {m.label}
            </div>
          ))}
        </div>
      )}
      <h3>Heroes</h3>
      <ul className="hero-list">
        {s.characters.map((c) => (
          <li key={c.id}>
            <strong>{c.name}</strong> <span className="muted">({c.player})</span>{" "}
            <span className="muted">HP {String(c.sheet.hp ?? "?")}</span>
          </li>
        ))}
      </ul>
      {s.narration.length > 0 && (
        <div className="narration">
          <h3>Narration</h3>
          <p>{s.narration[s.narration.length - 1]}</p>
        </div>
      )}
    </div>
  );
}

function HostControls() {
  const s = useApp((st) => st);
  const [scene, setScene] = useState("The party enters the torch-lit crypt.");
  if (!s.adminToken) return null;
  const hd = { "X-Admin-Token": s.adminToken };
  void hd;
  return (
    <div className="panel">
      <h2>Host controls</h2>
      <div className="row">
        {s.state !== "playing" && (
          <button className="primary" onClick={() => s.sessionId && api.setState(s.sessionId, "playing", s.adminToken)}>
            Start session
          </button>
        )}
        <button onClick={() => s.sessionId && api.nextChapter(s.sessionId, s.adminToken)}>Next chapter</button>
        <button
          className="danger"
          onClick={() => s.sessionId && api.setState(s.sessionId, "ended", s.adminToken)}
        >
          End session (email save points)
        </button>
      </div>
      <label>
        Scene
        <input value={scene} onChange={(e) => setScene(e.target.value)} />
      </label>
      <button onClick={() => s.sessionId && api.narrate(s.sessionId, scene)}>Narrate scene (AI)</button>
    </div>
  );
}

export default function App() {
  const sessionId = useApp((s) => s.sessionId);
  const state = useApp((s) => s.state);
  useEffect(() => {
    if (sessionId != null) return connectWs(sessionId);
    return undefined;
  }, [sessionId]);

  if (sessionId == null) return <JoinScreen />;
  return (
    <div className="screen">
      <header className="topbar">
        <span className="title small">⚔️ D&amp;D Table</span>
        <span className="code-badge">code {useApp.getState().code}</span>
      </header>
      <PasskeyPanel />
      {state === "lobby" && <CharacterForm />}
      <TableView />
      <DicePad />
      <AudioPanel />
      <VisionButton />
      <HostControls />
    </div>
  );
}
