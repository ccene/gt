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
3. No new spend and no US LLM providers: Mistral AI (EU-hosted, existing
   plan) first, with a fully local Ollama fallback (see §5).
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
| STT          | Browser capture + local Whisper | Fully local, no US services                     |
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

## 5. AI: Mistral first, Ollama local fallback, no US providers, always a fallback

A single `AIAdapter` interface (`chat`, `vision`, `stt`, `embed`) with a
configured priority chain. Every call has a deterministic local fallback
(template-based narration / rulebook lookup), so the app never breaks when a
key is missing or the network is down.

Priority chain (first available wins):

1. **Mistral AI** (La Plateforme, EU-hosted, GDPR-compliant, EU data
   residency — no player data goes to US services):
   - chat: `mistral-large-latest` (or the model in your plan) — DM
     narration, story generation/shaping, table-conversation notes
   - vision: Pixtral — reading physical maps/miniatures from the camera
   - embeddings: Mistral Embed — story/session memory retrieval
2. **Ollama running locally on the host** — fully offline, zero data leaving
   the machine: chat (e.g., llama3.2), embeddings (nomic-embed-text), and
   STT via a local Whisper model (faster-whisper / whisper.cpp).

Cost and latency control: all model calls happen in the loading/chapter
phase (never in the real-time play loop) and are cached in SQLite, so a
session replays with zero API calls. During play, narration uses cached
outputs plus browser TTS.

### Cost model (fits inside your existing Mistral plan allowance)

Mistral Pro bundles a monthly API-credit allowance (≈ $30/month on the
current Pro card — confirm the exact figure in your La Plateforme admin
console; it has changed over time). Anything beyond the allowance is
billed per token, so the app adds three guardrails:

1. **Cheap-by-default routing**: DM narration and notes default to
   `mistral-small-latest` ($0.15/$0.60 per M tokens); Large is used only
   for story generation/shaping. Prompt caching (up to 90% off repeated
   input) is always on.
2. **Hard app-level budget cap**: `MISTRAL_MONTHLY_BUDGET_USD` (default
   25). The app tracks spend in SQLite and, once the cap is reached,
   automatically fails over to local Ollama for the rest of the month.
   A hard spend limit should also be set in the La Plateforme console.
3. **Caching + phase restriction**: model calls only in loading/chapter
   phases and cached, so replays and retries cost nothing.

Estimate for your usage pattern (one ~4 h session every other week, ~8
sessions/month, 4 players): story prep + notes + arbitration ≈ 250 K input
+ 80 K output tokens per session on a Small/Large mix ≈ **$2–4/month** —
comfortably inside the bundled allowance, and the budget cap guarantees
no surprise overage.

No US-based LLM providers are used anywhere in the chain. STT is local
Whisper on the host; vision is Mistral Pixtral when online.

All keys are optional env vars; the app boots and plays fully offline with
none of them. Email: any SMTP provider you already use; in dev, emails are
written to a local `./outbox/` instead of being sent.

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

The backend/frontend/e2e jobs are disabled (`if: false`) until `backend/`
and `frontend/` exist, so CI is green from day one. Note: `hashFiles()`
in a job-level `if` is not used because it breaks workflow parsing in this
environment; when the app scaffold lands, replace the constant guards with
path detection (e.g., a small setup script writing `backend/.ci-enabled`).

## 9. Running on a laptop / Raspberry Pi

- `./scripts/setup.sh` — create venv, install backend + build frontend.
- `./scripts/run.sh` — start Uvicorn on 0.0.0.0:8000, print the LAN URL.
- `deploy/dnd-table.service` — systemd unit for auto-start on a Pi.
- Optional `docker compose up` for a laptop. Hardware target: Pi 4 (4 GB+),
  64-bit Raspberry Pi OS Lite, Python 3.11.
- Security: LAN-only by default, optional access token, no secrets in repo
  (`.env.example` documents everything; `.env` is gitignored).

## 10. Security (ironclad by design)

Threat model: the app lives on a home LAN and must never be reachable from
the internet; API keys and player data must never leave the machine except
to Mistral's EU endpoints; the host account is protected with MFA/passkeys.

- **Network exposure**: binds to the LAN interface only (never 0.0.0.0 on a
  WAN-facing host); `ufw`/firewall default-deny inbound, allow only the app
  port from the LAN subnet; optionally isolate the host on a guest/IoT VLAN.
  No tunnels, no public ingress, no open ports. HTTPS via a locally trusted
  cert (mkcert/Caddy) so all traffic on the LAN is encrypted; HSTS on.
  Remote access, if ever needed, only via WireGuard/Tailscale, not port
  forwarding.
- **Authentication**: players join a session with a random 6-digit code +
  per-session 256-bit token (stored hashed, rotated every session, rate
  limited). Host/admin actions (start session, end session, email save
  points, change settings) are gated by **WebAuthn passkey** — no passwords
  anywhere; register a platform passkey on the host laptop/Pi. Optional
  `ACCESS_TOKEN` env adds a second factor for admin endpoints.
- **Secrets**: `MISTRAL_API_KEY`, SMTP credentials, and tokens live only in
  `.env` (chmod 600) or a systemd `EnvironmentFile` with 0600 perms — never
  in git, never in logs, never in the DB. CI scans history for secrets
  (gitleaks) plus the `scripts/check-repo.sh` heuristic check. Use a
  **dedicated API key** (not your personal one) with a workspace/org spend
  cap, enable **MFA on the Mistral account**, and rotate the key immediately
  if it ever appears in a log or commit. Keys are loaded at process start
  and zeroed on shutdown where the OS allows.
- **Data at rest**: SQLite DB and all media in `./data/` with directory
  perms 0700; optional SQLCipher encryption; backups are encrypted
  (age/gpg) to local disk/USB only — no cloud sync. Raw microphone audio
  and camera frames are never written to disk: STT runs locally (Whisper)
  and only transcripts are stored; vision frames go to Mistral Pixtral (EU)
  only during an explicit vision action, with an on-screen recording
  indicator, and are discarded after the call. Retention is configurable;
  session end can purge transcripts.
- **Supply chain / hygiene**: dependabot for Actions/pip/npm; `unattended-
  upgrades` on the Pi; CI runs pip-audit, npm audit, bandit, and gitleaks
  on every PR; minimal dependency footprint.
- **Audit**: append-only audit log (who joined, who rolled, admin actions,
  AI calls with token counts) in SQLite, viewable by the passkey-authenticated
  host.

## 11. Roadmap

| Phase | Deliverable                                                            |
|-------|------------------------------------------------------------------------|
| P0    | This plan, repo reset, CI, scripts, templates (this PR)                |
| P1    | ✅ Backend core: SQLite models, REST, dice, session state machine, 36 pytest tests |
| P2    | ✅ Mobile-first PWA (React+Vite): join/lobby, character submit, table view, Vitest |
| P3    | ✅ Real-time: WebSocket sync (dice/map/narration/chat), reconnect snapshot, map view |
| P4    | ✅ AI adapter: Mistral first, Ollama fallback, deterministic fallback, budget cap, cache; story gen/import; demo seed script |
| P5    | ✅ Audio: browser TTS narration, mic capture → local Whisper STT (audio never stored); camera vision via Pixtral (EU, explicit host action, budget-capped) |
| P6    | ✅ End-of-session save-point emails (SMTP or ./outbox/ in dev)       |
| P7    | ✅ Pi/laptop deployment: systemd unit (hardened), firewall script (default-deny, LAN-only), deploy docs |

Each phase lands as its own PR with tests; CI must stay green throughout.
