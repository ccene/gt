# Getting Started — D&D Table Companion (plain-English guide)

This app turns one laptop or Raspberry Pi into the "game master screen" for your
table. Everyone else opens a web page on their phone. No app store, no accounts,
no passwords — just a code.

**What you need**
- One computer to host: a laptop, or a Raspberry Pi 4 (4 GB+) with Raspberry Pi OS.
- Phones/tablets for each player, on the **same Wi-Fi** as the host.
- Optional: a Mistral API key (if you want the smart AI narrator; everything
  works without it using the built-in local fallback).

---

## Step 1 — Get the code onto the host computer

On the host computer, open a terminal and run:

```bash
git clone https://github.com/ccene/gt.git
cd gt
```

(If you already have it, just `cd` into the folder and run
`git pull` to get the latest.)

## Step 2 — Install everything (one time only)

```bash
./scripts/setup.sh
```

This creates a private Python environment (`.venv`), installs the backend
dependencies, and builds the phone web app into `frontend/dist`.
Takes a few minutes the first time.

**Optional — turn on the AI narrator:** copy `.env.example` to `.env`
(`cp .env.example .env`), then put your Mistral API key on the
`MISTRAL_API_KEY=` line. Without it, narration uses a built-in local fallback,
so the demo still works fully offline.

## Step 3 — Load the demo data (optional but recommended first time)

```bash
python3 scripts/seed_demo.py
```

(If you see `ModuleNotFoundError: No module named 'httpx'`, you skipped step 2 —
run `./scripts/setup.sh` first. The script also auto-uses `.venv` when present.)

This creates a pretend game already in progress:
- Session code: **DEMO42**
- Four pretend players: **Aria, Bram, Cleo, Dana** (with character sheets)
- A story: *The Sunken Crypt of Morvaine* (3 chapters)
- 3 maps and a few dice rolls / narration already on the table

## Step 4 — Start the server

```bash
./scripts/run.sh
```

You'll see a line like:

```
Serving on http://0.0.0.0:8000 — open the LAN IP on each player's device
```

Find the host computer's local IP address (on Linux/macOS: `hostname -I`;
on the Pi desktop: hover the Wi-Fi icon). It looks like `192.168.1.50`.

## Step 5 — Players join from their phones

Each player opens a browser (Safari on iPad works great) and goes to:

```
http://192.168.1.50:8000     <- use YOUR host computer's IP
```

They type their name, their email (used to send their character sheet after the
session), and the session code **DEMO42**, then tap **Join session**.

On an iPad/iPhone they can tap Share → **Add to Home Screen** to install it
like an app.

## Step 6 — Play the demo

| What | How |
|---|---|
| Roll dice | Tap any die (d4…d100) in the Dice panel — everyone sees the result instantly |
| See the map | The Table panel shows the current map with markers |
| Hear narration | Host taps **Narrate scene** (AI writes the scene), then any player taps **Read narration aloud** (the phone speaks it) |
| Listen to the table | Host taps **Record table talk** — speech is transcribed **locally** (nothing leaves the device except text notes) |
| Read the table with the camera | Host taps **Capture table & describe** — one photo goes to Mistral's EU servers, description comes back |
| Next chapter | Host taps **Next chapter** (screen shows a loading state, like a video game) |
| End the session | Host taps **End session** — every player with an email gets their updated character sheet + save point (in the demo these land as files in `outbox/`) |
| Host login | The **Host passkey** panel: register a passkey once, then sign in with it (Face ID / Touch ID / PIN) instead of any token |

**Demo host credentials:** session code `DEMO42`, admin token
`demo-admin-token` (only needed for API calls; in the app the host controls
appear automatically after joining a session you created, or after passkey
sign-in).

## Step 7 — Run a real session (no demo data)

1. Host runs the server (`./scripts/run.sh`) **without** seeding demo data.
2. Host creates a session — the API does this when you use the app flow; the
   6-letter code appears on screen (share it out loud / on a group chat).
3. Players join with the code and submit their character sheets.
4. Play. At the end, tap **End session** to email everyone their save point.

To create a session from the API directly:

```
POST http://<host-ip>:8000/api/sessions        {}        -> returns {"code": "ABC123", "admin_token": "..."}
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `./scripts/setup.sh` fails | Make sure Python 3.11+ (`python3 --version`) and Node 20+ (`node --version`) are installed |
| Players can't connect | Host and phones must be on the same Wi-Fi; check the host's firewall allows port 8000 (`sudo scripts/harden-host.sh` sets this up) |
| "Transcription failed (503)" | The local speech model isn't installed; that's fine — it's optional. `pip install faster-whisper` inside `.venv` enables it |
| Narration says "local fallback" | No `MISTRAL_API_KEY` in `.env`, or the monthly budget cap was hit — add the key, or just enjoy the fallback |
| Want to wipe demo data | Delete the `data/` and `outbox/` folders, then re-run `python3 scripts/seed_demo.py` |

## What runs where (the 30-second version)

- The **host computer** runs everything: the game server, the database (a
  single file in `data/`), and the phone web pages.
- **Phones** only display and send taps/rolls — all dice are rolled on the
  host so nobody can cheat the RNG.
- **AI**: if you set a Mistral key, story/narration goes to Mistral's EU
  servers (never US providers); otherwise a local model (Ollama) or a built-in
  fallback handles it. Speech-to-text is always local. Your monthly spend is
  capped by `MISTRAL_MONTHLY_BUDGET_USD` (default $25) and the app switches to
  the free local fallback if the cap is hit.
- **Security**: LAN-only, default-deny firewall, passkey host login, no raw
  audio/photos stored, secrets only in `.env` (never committed).

See [MASTER_PLAN.md](MASTER_PLAN.md) for the full architecture and
[deploy/README.md](deploy/README.md) for running it 24/7 on a Raspberry Pi.
