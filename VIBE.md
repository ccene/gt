# VIBE.md — working context for agents on this repo

Read this first when you pick up work here. It captures what the project is,
what has already been built, and — most importantly — the **self-iterating
verification loop** you must use before claiming any change works.

---

## 1. What this project is

**D&D Table Companion** (`ccene/gt`): a real-time dungeon-master companion for
a game table. One laptop or Raspberry Pi hosts the app; players join from
phones/iPads over the LAN via a mobile-first PWA — no app store, just a 6-char
session code. The host screen shows the map, heroes, dice, and narration;
speakers narrate (browser TTS); the mic transcribes table talk locally
(Whisper, audio never stored); the camera can describe the physical table via
Mistral Pixtral (EU only, explicit host action). At session end every player
with an email gets their updated character sheet + save point (SMTP, or
`./outbox/*.eml` in dev).

Non-negotiables (from `MASTER_PLAN.md` §1):

1. Hosted on LAN only; players on mobile browsers. Never expose publicly.
2. **Real-time during play** — all heavy work (story gen, model warm-up) happens
   in loading/chapter-transition phases, like a video-game loading screen.
3. **No US LLM providers.** Mistral (EU, GDPR) first, local Ollama fallback,
   then a deterministic local fallback. App must run fully offline with zero keys.
4. Robust automated testing at every layer, enforced by CI.
5. Mobile-first: designed at 360px first.

Secrets (Mistral key, SMTP, etc.) live **only in the local `.env`** (gitignored,
already provided by the user) — loaded by `backend/config.py` via
pydantic-settings. Never commit, log, or print them. `.env.example` documents
every variable.

## 2. Work that has been done (as of main @ 62ac85f)

All master-plan phases P1–P7 are merged (PRs #9–#12):

| Area | Where | What |
|---|---|---|
| Backend core | `backend/` (FastAPI + Uvicorn + SQLite) | REST API (`routers.py`), dice RNG with advantage/disadvantage (`dice.py`), session state machine `lobby→loading→playing→chapter_end→ended`, WebSocket hub (`hub.py`), passkey host admin (`passkeys.py`), 70 pytest tests (`backend/tests/`) |
| AI adapter | `backend/ai.py` | Mistral-first chain → Ollama → deterministic local fallback; SQLite-cached; `MISTRAL_MONTHLY_BUDGET_USD` hard cap with failover. `generate_campaign(prompt, length_hours)` turns the host's free-text idea into a structured campaign (title/logline/chapters/NPCs, ~20 min per chapter); `recap_session` summarizes the session log |
| Campaign & story | `routers.py`, `db.py` | `POST /api/stories/generate {prompt, length_hours}` (default **1 hour** → 3 chapters); sessions carry `campaign_minutes` (default 60), the clock starts when state becomes `playing`, and the host can `POST /sessions/{id}/campaign/extend {minutes}` (+30/+60) mid-game |
| Combat tracker | `routers.py`, `hub.py` | Initiative tracker (`combatants` + `combat_state` tables): start encounter (admin), roll initiative (d20+mod, sorted), next turn (round counter), HP delta/clamp + condition toggles (anyone), end. Broadcast over WS and included in snapshots |
| Live sheets & chat | `routers.py` | `POST /sessions/{id}/characters/{cid}/update` (HP/conditions merge-patch, broadcast); `POST /sessions/{id}/chat` (REST fallback for WS chat); `POST /sessions/{id}/recap` (AI "what happened so far") |
| Audio/vision | `backend/audio.py`, `backend/vision.py` | Local Whisper STT (audio never written to disk), Pixtral vision on explicit host action |
| Email | `backend/emailer.py` | End-of-session save points; SMTP or `./outbox/` in dev |
| Frontend PWA | `frontend/` (React 19 + Vite + TS) | Join/host screen with **story-idea input + campaign length + "Generate story & host"** (LLM campaign → session code), story panel, campaign timer bar with extend buttons, combat panel, table chat, dice pad with adv/dis, heroes with HP ±/conditions; 16 Vitest tests + 5 Playwright e2e (iPhone/iPad viewports) |
| Demo | `scripts/seed_demo.py` | Session `DEMO42`, admin token `demo-admin-token`, 4 players, 3-chapter story, 3 maps, seeded events |
| Ops | `scripts/{setup,run}.sh`, `deploy/`, `scripts/harden-host.sh` | `.venv` setup, one-command run on `0.0.0.0:8000` (venv resolved by absolute path), systemd unit, default-deny firewall |
| CI | `.github/workflows/ci.yml` | Repo hygiene + gitleaks, backend (ruff/mypy/pytest cov≥80), frontend (eslint/tsc/vitest/build), Playwright e2e — all green on main |

Known bug fixed after main @ d70cba1: `frontend/src/api.ts` `req()` spread `...init`
after `headers`, so callers passing `headers: undefined` (e.g. `createSession`) wiped
`Content-Type: application/json` and every PWA POST got a 422 in the real browser
(the API-level smoke loop used httpx with explicit headers, so it missed this).
Headers are now merged: `{ "Content-Type": "application/json", ...init?.headers }`.

Docs: `README.md` (quick start), `GETTING_STARTED.md` (plain-English guide),
`MASTER_PLAN.md` (full architecture/security/roadmap), `deploy/README.md`.

## 3. The self-iterating loop — how to prove the game actually runs (no human input)

**Rule: never claim a feature works without running the loop.** The loop boots
the real app locally and plays a full session through the same API the PWA
uses. It needs no browser, no clicks, no credentials, and binds only
`127.0.0.1`.

```bash
./scripts/setup.sh                      # once: creates .venv + builds frontend
python3 scripts/smoke_loop.py          # one full pass (exit 0 = all green)
python3 scripts/smoke_loop.py --watch 3 # three consecutive passes
```

`scripts/smoke_loop.py` (new — added with this file) does, per pass:

1. Starts Uvicorn on `127.0.0.1:8123` with a throwaway DB (`DATABASE_URL` override).
2. `GET /health` → ok.
3. `POST /api/stories/generate {prompt, length_hours: 1}` → the LLM turns the
   host's story input into a 3-chapter campaign (any provider, incl. fallback).
4. `POST /api/sessions {story_id, campaign_minutes: 60}` → new game, 6-char
   code, 60-minute campaign (the "Generate story & host" flow).
5. `POST /api/players` + character sheet → submit.
6. `POST /api/sessions/join` with the code → snapshot containing the character,
   the campaign clock, the story, and the (inactive) combat tracker.
7. Join with a **bad** code → 404.
8. Admin token starts the session (`state=playing`) → campaign clock starts
   (`started_at`/`ends_at` = +60 min).
9. `POST /campaign/extend` without token → 403; with token `+30` → 90 min total.
10. **Two WebSocket clients** connect; one sends a `roll`; both receive the
    same `dice` event in real time; `ping`→`pong` reports `clients: 2`.
11. REST roll `2d6+3` shape/bounds; `mode:"adv"` keeps the higher of 2d20.
12. Combat: start encounter (admin) → roll initiative (sorted desc) → next turn
    → HP delta + `poisoned` condition → end.
13. `POST /chat` (REST) and `POST /characters/{id}/update` (HP + conditions).
14. `POST /recap` → AI "what happened so far"; `POST /narrate` → narration text
    from any provider (Mistral key from `.env`, else Ollama, else local
    fallback — all acceptable); `POST /notes` → transcript summarization.
15. `POST /chapter` (admin) → `chapter_index` 1, `state=loading`.
16. `POST /maps` (admin) → map set.
17. `POST /state {state:"ended"}` (admin) → **save-point email appears in
    `outbox/`** containing the character name and save point.
18. Admin action **without** token → 403.

34 assertions per pass, PASS/FAIL printed per step, exit code 0 only if all
pass. Verified locally: `--watch 3` → all 3 passes green.

### When you change code, iterate like this

```bash
# 1. make your change
# 2. fast checks
cd backend && ../.venv/bin/python -m pytest -q        # backend unit/API/WS tests
cd frontend && npm test                                  # frontend unit tests
# 3. THE LOOP — must pass before you open/merge anything
python3 scripts/smoke_loop.py --watch 2
# 4. full gates (what CI runs)
bash scripts/check-repo.sh
cd backend && ../.venv/bin/python -m ruff check . && ../.venv/bin/python -m mypy .
cd frontend && npm run lint && npm run typecheck && npm run build && npm run e2e
```

If the loop fails, the failure line names the broken flow — fix that, re-run
the loop, repeat. Do not "fix" by weakening assertions; if the assertion is
wrong, fix the assertion and say why in the PR.

### Where the loop hooks into automation

- `scripts/check-repo.sh` (CI "Repo hygiene" job) requires `VIBE.md` and
  `scripts/smoke_loop.py` to exist.
- CI's e2e job already boots the server + Playwright; `smoke_loop.py` is the
  faster, human-free equivalent for local iteration — run it first, always.
- Optional next step (not yet wired): add a CI job that runs
  `python3 scripts/smoke_loop.py --watch 2` after the e2e job.

## 4. Conventions for agents working here

- Branch: `vibe/<slug>-<id>`; PRs via `gh pr create --draft` unless asked
  otherwise. Keep CI green; each phase lands as its own PR with tests.
- Small, focused diffs. Follow existing style (ruff/mypy clean backend;
  eslint/tsc clean frontend). No new dependencies unless the repo already
  uses them or the plan requires it.
- Never touch `.env`, never print secrets, never commit `data/`, `outbox/`,
  `.venv/`, `node_modules/`, `dist/` (all gitignored). `scripts/check-repo.sh`
  enforces this.
- Server-authoritative: dice are rolled on the host (`secrets`), phones are
  thin views. Real-time goes over the WebSocket; REST for setup/persistence.
- Keep the play loop light: heavy AI calls only in loading/chapter phases and
  cached in SQLite. During play, use cached outputs + browser TTS.
- Mobile-first UI rules in `MASTER_PLAN.md` §4 (360px first, ≥44px targets,
  `dvh`, safe-area insets, `prefers-reduced-motion`).
- Security posture in `MASTER_PLAN.md` §10: LAN-only, no tunnels/public
  ingress, passkey host admin, no raw audio/frames on disk, append-only audit
  log. If a request would expose the app publicly, refuse it.

## 5. Quick reference

```bash
cp .env.example .env            # already done by user; keys are in .env
./scripts/setup.sh              # .venv + backend deps + frontend build
python3 scripts/seed_demo.py    # optional demo data (code DEMO42)
./scripts/run.sh                # serve API + PWA on http://0.0.0.0:8000
python3 scripts/smoke_loop.py --watch 3   # <-- the self-iterating proof loop
```

Key endpoints: `GET /health` · `POST /api/stories/generate {prompt, length_hours}` ·
`POST /api/sessions {story_id?, campaign_minutes?}` (host) ·
`POST /api/sessions/join {code, player_id?}` → returns `player_token` ·
`POST /api/sessions/{id}/roll|narrate|notes|state|chapter|maps|chat|recap|campaign/extend|combat*`
(admin actions: header `X-Admin-Token`; chat: header `X-Player-Token` — sender is
resolved server-side from the token) · `WS /api/sessions/{id}/ws?token=<player_token>`
(send `{"type":"roll","faces":20,"mode":"adv"}` or `{"type":"chat","text":"..."}`).
When `ACCESS_TOKEN` is set in `.env`, host-capable endpoints (`POST /api/sessions`,
`/api/stories/*`, passkey options) require header `X-Access-Token`; passkey
endpoints also validate `Origin` against the request `Host`.

Auth/data-isolation model (added in the full audit pass): `session_players`
records join membership; snapshots, narration and save-point emails are scoped
to session members; the WS channel requires a valid join token (4401 otherwise);
snapshots carry only the last 200 events; audio transcription stays in memory
(faster-whisper decodes from BytesIO, never disk). Audit regression tests live
in `backend/tests/test_audit.py` and `frontend/src/audit.test.tsx`.
