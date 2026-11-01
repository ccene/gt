import { useEffect, useState } from "react";
import { api, type Player } from "./api";
import { useApp } from "./store";
import { connectWs, wsSend } from "./ws";
import AudioPanel, { VisionButton } from "./AudioPanel";
import PasskeyPanel from "./PasskeyPanel";
import { CampaignBar, ChatPanel, CombatPanel } from "./panels";
import "./styles.css";

const FACES = [4, 6, 8, 10, 12, 20, 100];
const LENGTH_OPTIONS = [0.5, 1, 2, 3, 4]; // hours; 1h is the default campaign length

function JoinScreen() {
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [idea, setIdea] = useState("");
  const [lengthHours, setLengthHours] = useState(1);
  const [genre, setGenre] = useState("classic fantasy");
  const [tone, setTone] = useState("heroic");
  const [hosted, setHosted] = useState<{ code: string; admin_token?: string; storyTitle?: string } | null>(null);

  const hostNew = async () => {
    setBusy(true);
    setError("");
    try {
      const s = await api.createSession(null, Math.round(lengthHours * 60));
      setHosted({ code: s.code, admin_token: s.admin_token });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  // The host's story input goes to the LLM, which generates the campaign;
  // the session is then created with that story and the chosen length.
  const hostWithStory = async () => {
    setBusy(true);
    setError("");
    try {
      const story = await api.generateCampaign(idea, lengthHours, genre, tone);
      const s = await api.createSession(story.id, Math.round(lengthHours * 60));
      setHosted({ code: s.code, admin_token: s.admin_token, storyTitle: story.title });
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
      const joined = await api.joinSession(code.trim().toUpperCase(), player.id);
      useApp.getState().setPlayerToken(joined.player_token);
      useApp.getState().setPlayerId(player.id);
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
      <div className="divider"><span>or host a game</span></div>
      <label>
        Story idea (the AI turns this into your campaign)
        <textarea
          value={idea}
          onChange={(e) => setIdea(e.target.value)}
          placeholder="e.g. A crew of sky-pirates raids a cloud castle…"
          rows={3}
        />
      </label>
      <div className="row">
        <label>
          Campaign length
          <select value={lengthHours} onChange={(e) => setLengthHours(Number(e.target.value))}>
            {LENGTH_OPTIONS.map((h) => (
              <option key={h} value={h}>
                {h === 1 ? "1 hour (default)" : h < 1 ? `${h * 60} minutes` : `${h} hours`}
              </option>
            ))}
          </select>
        </label>
        <label>
          Genre
          <select value={genre} onChange={(e) => setGenre(e.target.value)}>
            {["classic fantasy", "gothic horror", "sci-fi", "mystery", "heist", "post-apocalyptic"].map((g) => (
              <option key={g} value={g}>{g}</option>
            ))}
          </select>
        </label>
        <label>
          Tone
          <select value={tone} onChange={(e) => setTone(e.target.value)}>
            {["heroic", "grimdark", "comedic", "mysterious", "epic"].map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </label>
      </div>
      <button className="primary" disabled={busy} onClick={hostWithStory} data-testid="generate-and-host">
        {busy ? "Generating campaign…" : "✨ Generate story & host"}
      </button>
      <button className="host-btn" disabled={busy} onClick={hostNew}>
        🎲 Quick host (no story)
      </button>
      {hosted && (
        <div className="host-code" data-testid="host-code">
          <p className="muted">Share this code with your players:</p>
          <div className="big-code">{hosted.code}</div>
          {hosted.storyTitle && <p className="ok">Campaign: {hosted.storyTitle}</p>}
          <button
            className="primary"
            onClick={() => {
              useApp.getState().setAdminToken(hosted.admin_token ?? "");
              void api.joinSession(hosted.code).then((j) => {
                useApp.getState().setPlayerToken(j.player_token);
                useApp.getState().setPlayerId(null);
                useApp.getState().setSnapshot(j.snapshot);
              });
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
  const myPlayerId = useApp((s) => s.playerId);
  const myCharacter = useApp((s) => s.characters.find((c) => c.player_id === s.playerId));
  const [players, setPlayers] = useState<Player[]>([]);
  const [playerId, setPlayerId] = useState<number | null>(null);
  const [charName, setCharName] = useState("");
  const [hp, setHp] = useState(20);
  const [charClass, setCharClass] = useState("Fighter");
  const [level, setLevel] = useState(1);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    void api.listPlayers().then(setPlayers).catch(() => {});
  }, []);

  // prefill from the player's existing character (if any) and default the select
  useEffect(() => {
    if (myPlayerId != null) setPlayerId(myPlayerId);
  }, [myPlayerId]);
  const myCharId = myCharacter?.id;
  useEffect(() => {
    if (myCharacter) {
      setCharName(myCharacter.name);
      setHp(Number(myCharacter.sheet.hp ?? 20));
      setCharClass(String(myCharacter.sheet.class ?? "Fighter"));
      setLevel(Number(myCharacter.sheet.level ?? 1));
    }
  }, [myCharId]);

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
          {players.length === 0 && <option value="" disabled>(join first to create your player)</option>}
          {players.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
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
  const [mode, setMode] = useState<"normal" | "adv" | "dis">("normal");
  const dice = useApp((s) => s.dice);
  const last = dice[dice.length - 1];

  const roll = (f: number) => {
    if (sessionId == null) return;
    wsSend({ type: "roll", count: 1, faces: f, modifier: mod, roller: "you", mode });
  };

  return (
    <div className="panel">
      <h2>Dice</h2>
      {last && (
        <div className="dice-result" data-testid="last-roll">
          <span className="dice-total">{last.total}</span>
          <span className="dice-detail">
            {last.dice}: [{last.rolls.join(", ")}]
            {last.kept != null && ` kept ${last.kept}`}
            {last.modifier !== 0 ? ` ${last.modifier > 0 ? "+" : ""}${last.modifier}` : ""} by {last.roller}
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
      <div className="row">
        {(["normal", "adv", "dis"] as const).map((m) => (
          <button
            key={m}
            className={`chip ${mode === m ? "on" : ""}`}
            onClick={() => setMode(m)}
            title={m === "adv" ? "advantage (d20)" : m === "dis" ? "disadvantage (d20)" : "normal roll"}
          >
            {m === "adv" ? "Advantage" : m === "dis" ? "Disadvantage" : "Normal"}
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

function StoryPanel() {
  const s = useApp((st) => st);
  const campaign = s.story?.content?.campaign;
  if (!s.story || !campaign) return null;
  return (
    <div className="panel" data-testid="story-panel">
      <h2>📖 {s.story.title}</h2>
      {campaign.logline && <p className="muted">{campaign.logline}</p>}
      {campaign.opening_scene && <p className="transcript">{campaign.opening_scene}</p>}
      {Array.isArray(campaign.chapters) && campaign.chapters.length > 0 && (
        <ol className="chapter-list">
          {campaign.chapters.map((ch, i) => (
            <li key={i} className={i === s.chapterIndex ? "current" : ""}>
              <strong>{ch.title}</strong>
              {ch.summary && <span className="muted"> — {ch.summary}</span>}
            </li>
          ))}
        </ol>
      )}
      {Array.isArray(campaign.npcs) && campaign.npcs.length > 0 && (
        <p className="muted small">NPCs: {campaign.npcs.map((n) => n.name).join(", ")}</p>
      )}
    </div>
  );
}

function TableView() {
  const s = useApp((st) => st);
  const map = s.maps[s.maps.length - 1];
  const adjHp = (charId: number, delta: number) => {
    const c = s.characters.find((x) => x.id === charId);
    if (!c || s.sessionId == null) return;
    const hp = Math.max(0, Number(c.sheet.hp ?? 0) + delta);
    void api.updateCharacter(s.sessionId, charId, { hp }).catch(() => {});
  };
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
          <li key={c.id} className="hero">
            <div className="row spread">
              <span>
                <strong>{c.name}</strong> <span className="muted">({c.player})</span>
              </span>
              <span className="hp-controls">
                <button className="small" onClick={() => adjHp(c.id, -1)} aria-label={`damage ${c.name}`}>−</button>
                <span>HP {String(c.sheet.hp ?? "?")}</span>
                <button className="small" onClick={() => adjHp(c.id, 1)} aria-label={`heal ${c.name}`}>+</button>
              </span>
            </div>
            {Array.isArray(c.sheet.conditions) && (c.sheet.conditions as string[]).length > 0 && (
              <div className="row chips">
                {(c.sheet.conditions as string[]).map((cond) => (
                  <span key={cond} className="chip on">{cond}</span>
                ))}
              </div>
            )}
          </li>
        ))}
      </ul>
      {s.narration.length > 0 && (
        <div className="narration">
          <h3>Narration</h3>
          <p>{s.narration[s.narration.length - 1]}</p>
        </div>
      )}
      {s.recap.length > 0 && (
        <div className="narration" data-testid="recap">
          <h3>Recap — what happened so far</h3>
          <p>{s.recap[s.recap.length - 1]}</p>
        </div>
      )}
    </div>
  );
}

function SessionEndedBanner() {
  const s = useApp((st) => st);
  if (s.state !== "ended") return null;
  return (
    <div className="panel" data-testid="session-ended-banner" style={{ borderColor: "var(--ok)" }}>
      <h2>🏁 Session ended</h2>
      {s.endedEmails.length > 0 ? (
        <ul className="hero-list">
          {s.endedEmails.map((e, i) => (
            <li key={i}>
              <strong>{e.character ?? e.player ?? "player"}</strong>{" "}
              <span className="muted">
                {e.error ? `save point failed: ${e.error}` : e.sent ? `save point emailed (${e.via})` : `save point saved to ${e.via ?? "outbox"}`}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">No save points to send (no players with characters joined).</p>
      )}
    </div>
  );
}

function HostControls() {
  const s = useApp((st) => st);
  const [scene, setScene] = useState("The party enters the torch-lit crypt.");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (!s.adminToken) return null;

  const endSession = async () => {
    if (s.sessionId == null) return;
    setBusy(true);
    setError("");
    try {
      await api.setState(s.sessionId, "ended", s.adminToken);
    } catch (e) {
      setError(`Could not end session: ${(e as Error).message}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="panel">
      <h2>Host controls</h2>
      <div className="row">
        {s.state !== "playing" && s.state !== "ended" && (
          <button className="primary" onClick={() => s.sessionId && api.setState(s.sessionId, "playing", s.adminToken)}>
            Start session
          </button>
        )}
        <button onClick={() => s.sessionId && api.nextChapter(s.sessionId, s.adminToken)}>Next chapter</button>
        {s.state !== "ended" && (
          <button className="danger" disabled={busy} onClick={endSession}>
            {busy ? "Ending…" : "End session (email save points)"}
          </button>
        )}
      </div>
      {error && <p className="error">{error}</p>}
      <label>
        Scene
        <input value={scene} onChange={(e) => setScene(e.target.value)} />
      </label>
      <div className="row">
        <button onClick={() => s.sessionId && api.narrate(s.sessionId, scene)}>Narrate scene (AI)</button>
        <button onClick={() => s.sessionId && api.recap(s.sessionId)}>📜 Recap so far (AI)</button>
      </div>
    </div>
  );
}

export default function App() {
  const sessionId = useApp((s) => s.sessionId);
  const state = useApp((s) => s.state);
  const code = useApp((s) => s.code);
  const playerId = useApp((s) => s.playerId);
  const myCharacter = useApp((s) => s.characters.find((c) => c.player_id === s.playerId));
  useEffect(() => {
    if (sessionId != null) return connectWs(sessionId);
    return undefined;
  }, [sessionId]);

  if (sessionId == null) return <JoinScreen />;
  // The character form shows in the lobby, and for any player who has not
  // created a character yet — even if the session is already in play.
  const showCharacterForm = state === "lobby" || (playerId != null && !myCharacter);
  return (
    <div className="screen">
      <header className="topbar">
        <span className="title small">⚔️ D&amp;D Table</span>
        <span className="code-badge">code {code}</span>
      </header>
      <PasskeyPanel />
      {state === "ended" && <SessionEndedBanner />}
      {showCharacterForm && <CharacterForm />}
      <StoryPanel />
      <CampaignBar />
      <TableView />
      <CombatPanel />
      <DicePad />
      <ChatPanel />
      <AudioPanel />
      <VisionButton />
      <HostControls />
    </div>
  );
}
