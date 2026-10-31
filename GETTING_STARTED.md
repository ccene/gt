# Getting Started — D&D Table Companion

Turn one laptop or Raspberry Pi into the game-master screen for your table.
Everyone else plays from a phone browser — no app store, no accounts, no
passwords. You share one 6-character code and you're playing.

---

## 1. What you need

- **One host computer**: a laptop, or a Raspberry Pi 4 (4 GB+) with Raspberry Pi OS.
  It needs Python 3.11+ and Node 20+.
- **A phone or tablet per player**, on the **same Wi-Fi** as the host computer.
- **Optional — a Mistral API key** (`MISTRAL_API_KEY` in `.env`) for the smart AI
  storyteller/narrator. Without it everything still works on a built-in local
  fallback, so you can play fully offline.

## 2. One-time setup on the host computer

```bash
git clone https://github.com/ccene/gt.git   # or: cd into your existing copy && git pull
cd gt
./scripts/setup.sh                          # creates .venv, installs backend deps, builds the phone web app
```

Takes a few minutes the first time.

**Optional:** the repo already has a `.env` (gitignored) with your keys. To edit
it: `nano .env`. Useful knobs:

| Variable | What it does |
|---|---|
| `MISTRAL_API_KEY` | Enables the AI storyteller (Mistral, EU servers only). Empty = local fallback |
| `MISTRAL_MONTHLY_BUDGET_USD` | Hard monthly spend cap (default $25); the app auto-falls-back to local when hit |
| `ACCESS_TOKEN` | Optional shared LAN password. When set, hosting/story-generation/passkey-setup require it (header `X-Access-Token`) |
| `SMTP_HOST` / `SMTP_*` | Where save-point emails go. Empty = written as files to `outbox/` instead |
| `HOST` / `PORT` | Bind address (default `0.0.0.0:8000`) |

## 3. Start the server

```bash
./scripts/run.sh
```

```
Serving on http://0.0.0.0:8000 — open the LAN IP on each player's device
```

Find the host's local IP: `hostname -I` (Linux) or the Wi-Fi icon (Pi desktop) —
it looks like `192.168.1.50`. **Everyone must be on the same Wi-Fi.** If the port
is blocked, `sudo scripts/harden-host.sh` installs a default-deny firewall that
opens port 8000 to your LAN only.

Sanity check: open `http://localhost:8000` on the host — you should see the
join screen. `http://localhost:8000/health` returns `{"status":"ok"}`.

## 4. Play with friends — two ways

### Option A — Instant demo (recommended the first time)

```bash
python3 scripts/seed_demo.py     # safe to re-run any time; resets the demo
./scripts/run.sh
```

Then everyone (including you) opens `http://192.168.1.50:8000` — **your** host IP —
and joins with code **DEMO42**. You get 4 pre-made heroes (Aria, Bram, Cleo,
Dana), a 3-chapter story (*The Sunken Crypt of Morvaine*), maps, and a running
1-hour campaign clock. On iPhone/iPad, Share → **Add to Home Screen** installs
it like an app.

### Option B — Your own game (the normal way)

1. On the host computer open `http://localhost:8000`.
2. Type a **story idea** — one sentence is enough, e.g.
   *"a crew of sky-pirates raids a cloud castle at dawn"*.
3. Pick the **campaign length** — default **1 hour** (you can extend it later
   mid-game with **+30 min** / **+1 hour**), plus a genre and tone.
4. Tap **✨ Generate story & host**. The AI turns your idea into a campaign —
   title, logline, opening scene, NPCs, and chapters (~20 min of play each, so
   1 hour = 3 chapters).
5. A big 6-letter code appears (e.g. **K7XQ2M**). Tap **Enter as host →**.
   Shout the code or send it in your group chat.

   (No idea right now? Tap **🎲 Quick host (no story)**.)

6. Each player opens `http://<host-ip>:8000` on their phone, enters their
   **name**, **email** (for their end-of-session save point), and the **code**,
   then taps **Join session**. In the lobby they fill in their character
   (name, HP, class, level). Everyone sees the same table live from then on.
7. The host taps **Start session** — the campaign clock starts counting down.

## 5. What you can do during a session

| What | How |
|---|---|
| 📖 Follow the story | The story panel shows the campaign title, logline, opening scene and the chapter list with the current chapter highlighted |
| ⏳ Watch the clock | The campaign bar counts down (1 h default); host taps **+30 min** / **+1 hour** to extend |
| 🎲 Roll dice | Tap any die (d4…d100) — everyone sees it instantly. **Advantage/Disadvantage** on d20 rolls twice and keeps high/low |
| ⚔️ Run combat | Host: **Start combat** → **Roll initiative** (sorts everyone) → **Next turn** walks the order with a round counter. Anyone taps **−/+** for damage/heal and condition chips (poisoned, prone, concentrating…) to toggle them. Host can **add enemies mid-fight** |
| 🛡️ Track heroes | Heroes list shows HP with **−/+** buttons and condition chips, live for everyone |
| 💬 Talk | Table chat — messages appear on every device instantly, attributed to the player who sent them |
| 📜 Catch up | Host: **📜 Recap so far (AI)** — summarizes what happened for anyone who lost the thread |
| 🗺️ Show the map | Table panel shows the current map with markers |
| 🎙️ Narrate out loud | Host writes a scene (or taps **Narrate scene (AI)**), any player taps **Read narration aloud** and their phone speaks it |
| 🎤 Listen to the table | Host: **Record table talk** — transcribed **locally** on the host (Whisper); audio is never stored, only the text |
| 📷 Describe the table | Host: **Capture table & describe** — one photo goes to Mistral's EU vision model on this explicit tap only |
| ⏭️ Next chapter | Host: **Next chapter** (screen goes to a loading state, like a video game) |
| 🏁 End the session | Host: **End session** — every player with an email gets their updated character sheet + save point (with no SMTP configured, they land as files in `outbox/`) |
| 🔑 Host login | **Host passkey** panel: register a passkey once (Face ID/Touch ID/PIN), then sign in with it instead of the admin token |

## 6. Game-night checklist for the host

1. `./scripts/run.sh` is running; you can open `http://localhost:8000`.
2. You hosted a game (story generated or quick host) and have the code.
3. Players are on the same Wi-Fi and joined with the code.
4. You tapped **Start session** (campaign clock running).
5. Playing? Combat tracker for fights, dice for rolls, chat for table talk,
   **Recap** when someone asks "wait, what happened?", **+30 min** when the
   night is going well.
6. Done? **End session** — save points are emailed (or dropped in `outbox/`).

## 7. Troubleshooting

| Problem | Fix |
|---|---|
| `./scripts/setup.sh` fails | Check `python3 --version` (3.11+) and `node --version` (20+) |
| Players can't connect | Same Wi-Fi on both; `hostname -I` for the right IP; firewall: `sudo scripts/harden-host.sh` |
| "Transcription failed (503)" | Optional local speech model missing — `.venv/bin/pip install faster-whisper` enables it |
| Narration says "local fallback" | No `MISTRAL_API_KEY` in `.env`, or the monthly budget cap was reached — add the key or enjoy the fallback |
| Session code rejected (404) | Codes are case-insensitive but exact — 6 chars; check for a typo |
| Want to wipe everything | Stop the server, delete `data/` and `outbox/`, then `python3 scripts/seed_demo.py` for a fresh demo |
| Re-run the self-test | `python3 scripts/smoke_loop.py --watch 3` — boots the app headlessly and plays a full session, 37 assertions |

## 8. What runs where (the 30-second version)

- The **host computer** runs everything: the game server, the SQLite database
  (one file in `data/`), and serves the phone web pages.
- **Phones** are thin views — all dice are rolled on the host (server-side
  RNG), and the real-time channel is a WebSocket authenticated with the token
  each player got when joining.
- **AI**: with a Mistral key, story generation/narration/vision go to
  Mistral's **EU** endpoints only (no US LLM providers); otherwise local Ollama
  or the built-in fallback. Speech-to-text is always local, audio never hits
  disk. Monthly spend is capped by `MISTRAL_MONTHLY_BUDGET_USD`.
- **Privacy/security**: LAN-only + default-deny firewall, passkey host login,
  snapshots scoped to session members, no raw audio/photos stored, secrets
  only in `.env` (never committed; CI scans for them).

See [README.md](README.md) for the quick API tour, [MASTER_PLAN.md](MASTER_PLAN.md)
for the full architecture, and [deploy/README.md](deploy/README.md) for running
it 24/7 on a Raspberry Pi with systemd.
