# Master Plan — D&D Table Companion ("the table app")

A real-time dungeon-master companion for a game table. One device (laptop or
Raspberry Pi) hosts the app; players connect from their phones/iPads over the
local network. Cloud AI calls are allowed and preferred for quality, but the
app must run at zero extra cost using free tiers and local fallbacks.

## 1. Goals and non-negotiables

1. Hosted on a laptop or Raspberry Pi on the LAN; players join from mobile
   browsers. No app-store install — it is a mobile-first PWA.
2. Real-time during the session so immersion never breaks: all heavy work
   (story generation, map/NPC prep, model warm-up) happens in the loading /
   chapter-transition phase, like video-game loading screens.
3. Zero extra spend: only free tiers and locally runnable models (see §5).
4. Robust automated testing at every layer, enforced by CI.
5. Mobile-first design: designed at 360px width first, scaled up.

## 2. Core features

- Pre-session character submission by each player (name, class, level, stats,
  HP, inventory, notes) stored as JSON character sheets.
- Session lobby showing connected players and their characters.
- Big-screen display for everyone at the table: current scene graphics/text,
  instructions, and a map of where the players are.
- Dice rolling with server-side randomness, animated and synced to all
  clients in real time.
- Speaker narration (TTS) of DM decisions and scene text.
- Microphone capture of table conversation; notes and "what happens next"
  assessment, done in the background (never blocking the session loop).
- Optional front-camera vision (e.g., reading a physical map or miniatures).
- Story generation on the spot, or import + shaping of an existing story.
- End of session: every registered player receives an email with their
  updated character sheet and a save-point (chapter/progress snapshot).
- Agent-backed interactions (DM voice, rules arbitration, NPC dialogue)
  through a provider-agnostic AI adapter.

## 3. Architecture

```
players' phones/iPads (PWA, mobile-first)
        |  HTTPS/WS over LAN (http://<host-ip>:8000)
        v
+------------------------------------------------------+
|  Host device (laptop / Raspberry Pi 4+, 4-8 GB)      |
|  FastAPI (Python 3.11+) + Uvicorn                    |
|    - REST API (characters, sessions, stories, saves) |
|    - WebSocket channel (real-time session state:     |
|      map, initiative, dice, narration, notes)        |
|    - Static hosting of the built PWA                 |
|  SQLite (single file, zero-config, perfect for Pi)   |
|  Local asset cache (maps, images, audio)             |
+------------------------------------------------------+
        |  outbound only, cloud free tiers
        v
   AI providers (see §5)  +  SMTP/HTTP email (see §6)
```

- One process, one port: the Pi serves both API and the built frontend, so
  setup is "run one script, open the printed URL on each phone".
- State machine per session: `lobby -> loading(chapter prep) -> playing ->
  chapter_end -> ... -> ended`. Heavy work only in `loading`/`chapter_end`.
- WebSocket is the single source of truth during play; REST for setup and
  persistence. Reconnecting clients get a full state snapshot (fast resume).
- Background worker (asyncio task) handles mic transcription, note
  summarization, and end-of-session emails so the real-time loop stays light.

### Suggested stack

| Layer        | Choice                          | Why                                            |
|--------------|---------------------------------|------------------------------------------------|
| Backend      | Python 3.11+ FastAPI + Uvicorn  | Async, WebSockets, great on a Pi, easy tests  |
| Database     | SQLite via SQLAlchemy (or raw)  | Single file, no daemon, backup = copy a file   |
| Frontend     | Vite + TypeScript PWA           | Tiny build, installable on iPad home screen    |
| Real-time    | WebSocket (FastAPI)             | Dice/map/narration sync to all clients         |
| State        | Server-authoritative            | Phones are thin views; Pi is the game master   |
| TTS          | Browser SpeechSynthesis first   | Free, works on iPad Safari, zero latency setup |
| STT          | Browser capture + free cloud STT| See §5                                          |
| Tests        | pytest + Vitest + Playwright    | Unit, API/WS integration, mobile-viewport e2e  |
| CI           | GitHub Actions                  | Lint, typecheck, tests, coverage, build, e2e   |
| Packaging    | `scripts/run.sh` + systemd unit | One-command run on laptop/Pi                   |

## 4. Mobile-first design rules

- Design at 360x640 first; every screen must be fully usable one-handed.
- Touch targets >= 44x44 px; large dice buttons; high-contrast dark theme
  readable in a dim room.
- CSS with `dvh` units, safe-area insets (`env(safe-area-inset-*)`), no
  hover-dependent interactions, `prefers-reduced-motion` respected.
- PWA manifest + service worker: installable to iPad home screen, works
  offline for cached assets, large readable type (base 18px+).
- Layout: bottom navigation for thumbs; the "table view" (map + scene) is
  the default landing screen during play and is readable from across a table.

## 5. AI: free-tier only, provider-agnostic, always has a fallback

A single `AIAdapter` interface (`chat`, `vision`, `stt`, `embed`) with a
configured priority chain. Every call has a deterministic local fallback
(template-based narration / rulebook lookup), so the app never breaks when a
key is missing or the network is down.

Priority chain (first available wins, all free tiers):

1. Groq free tier (fast chat, generous free limits) — DM narration, notes.
2. Google AI Studio (Gemini) free tier — story generation, shaping, vision.
3. Hugging Face Inference (free endpoints) — STT (Whisper), embeddings.
4. Ollama running locally on the host — fully offline fallback for chat/STT.

All keys are optional env vars; the app boots and plays with none of them.
Free email sending: any free SMTP (e.g., Gmail app password) or Resend free
tier (100 emails/day); in dev, emails go to a file outbox instead.

## 6. Data model (SQLite)

- `players` (id, name, email)
- `characters` (id, player_id, sheet JSON, updated_at)
- `stories` (id, source: generated|imported, content JSON, chapters)
- `sessions` (id, story_id, state, chapter_index, save_point JSON)
- `session_events` (dice rolls, narration, notes — append-only log)
- `maps` (id, image path/URL, markers JSON)

## 7. Testing strategy (robust = layered, all in CI)

- Backend unit tests (pytest): dice RNG distribution + bounds, rules calc,
  state machine transitions, AI adapter fallback chain (providers mocked).
- Backend API tests (httpx + FastAPI TestClient): character CRUD, session
  lifecycle, auth-less LAN token, email outbox.
- WebSocket integration tests: two clients see the same dice roll and map
  update; reconnect gets full snapshot.
- AI contract tests: adapter returns structured output for each provider
  (mocked HTTP), fallback triggers on timeout/error.
- Frontend unit tests (Vitest): components, dice animation logic, store.
- E2E tests (Playwright, emulated mobile viewport 390x844 iPhone + iPad):
  submit character -> start session -> roll dice -> see it on second
  "player" device -> end session -> save point generated.
- Coverage gate: >= 80% backend, >= 70% frontend; CI fails below.
- Property-style tests for dice (bounds over 10k rolls) and session state
  serialization round-trips.

## 8. CI (GitHub Actions, `.github/workflows/ci.yml`)

On every PR and push to main:

1. Repo hygiene check (`scripts/check-repo.sh`): required files, no secrets
   committed, no leftover junk.
2. Backend: ruff lint, mypy, pytest with coverage gate, pip-audit, bandit.
3. Frontend: eslint, tsc typecheck, Vitest with coverage, build, npm audit.
4. E2E: Playwright mobile-viewport smoke (boots server, runs key flows).
5. Artifact: built PWA uploaded for manual QA on a real device.

Jobs for backend/frontend activate automatically once `backend/` and
`frontend/` exist (path-guarded), so CI is green from day one.

## 9. Running on a laptop / Raspberry Pi

- `./scripts/setup.sh` — create venv, install backend + build frontend.
- `./scripts/run.sh` — start Uvicorn on 0.0.0.0:8000, print the LAN URL.
- `deploy/dnd-table.service` — systemd unit for auto-start on a Pi.
- Optional `docker compose up` for a laptop. Hardware target: Pi 4 (4 GB+),
  64-bit Raspberry Pi OS Lite, Python 3.11.
- Security: LAN-only by default, optional access token, no secrets in repo
  (`.env.example` documents everything; `.env` is gitignored).

## 10. Roadmap

| Phase | Deliverable                                                            |
|-------|------------------------------------------------------------------------|
| P0    | This plan, repo reset, CI, scripts, templates (this PR)                |
| P1    | Backend core: models, REST, SQLite, dice, session state machine, tests |
| P2    | Mobile-first PWA shell: lobby, character submit, table view, PWA setup |
| P3    | Real-time engine: WebSocket sync, map view, synced dice, Playwright e2e|
| P4    | AI adapter + free-tier chain + fallbacks; DM narration; story gen/import|
| P5    | Audio: TTS narration, mic capture + STT notes; camera vision (optional)|
| P6    | End-of-session email with updated sheet + save point                   |
| P7    | Pi deployment hardening, systemd, performance pass, docs               |

Each phase lands as its own PR with tests; CI must stay green throughout.
