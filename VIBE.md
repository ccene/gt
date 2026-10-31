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
| Backend core | `backend/` (FastAPI + Uvicorn + SQLite) | REST API (`routers.py`), dice RNG (`dice.py`), session state machine `lobby→loading→playing→chapter_end→ended`, WebSocket hub (`hub.py`), passkey host admin (`passkeys.py`), 44 pytest tests (`backend/tests/`) |
| AI adapter | `backend/ai.py` | Mistral-first chain → Ollama → deterministic local fallback; SQLite-cached; `MISTRAL_MONTHLY_BUDGET_USD` hard cap with failover |
| Audio/vision | `backend/audio.py`, `backend/vision.py` | Local Whisper STT (audio never written to disk), Pixtral vision on explicit host action |
| Email | `backend/emailer.py` | End-of-session save points; SMTP or `./outbox/` in dev |
| Frontend PWA | `frontend/` (React 19 + Vite + TS) | Join/host screen (`🎲 Host a new game` → big shareable code), character form, table view (map/markers/heroes), dice pad, host controls, passkey panel; 12 Vitest tests + 2 Playwright e2e (iPhone/iPad viewports) |
| Demo | `scripts/seed_demo.py` | Session `DEMO42`, admin token `demo-admin-token`, 4 players, 3-chapter story, 3 maps, seeded events |
| Ops | `scripts/{setup,run}.sh`, `deploy/`, `scripts/harden-host.sh` | `.venv` setup, one-command run on `0.0.0.0:8000`, systemd unit, default-deny firewall |
| CI | `.github/workflows/ci.yml` | Repo hygiene + gitleaks, backend (ruff/mypy/pytest cov≥80), frontend (eslint/tsc/vitest/build), Playwright e2e — all green on main |

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
3. `POST /api/sessions` → new game, 6-char code (the "Host a new game" flow).
4. `POST /api/players` + character sheet → submit.
5. `POST /api/sessions/join` with the code → snapshot containing the character.
6. Join with a **bad** code → 404.
7. Admin token starts the session (`state=playing`).
8. **Two WebSocket clients** connect; one sends a `roll`; both receive the
   same `dice` event in real time; `ping`→`pong` reports `clients: 2`.
9. REST roll `2d6+3` shape/bounds.
10. `POST /narrate` → narration text from any provider (Mistral key from
    `.env`, else Ollama, else local fallback — all acceptable).
11. `POST /notes` → transcript summarization.
12. `POST /chapter` (admin) → `chapter_index` 1, `state=loading`.
13. `POST /maps` (admin) → map set.
14. `POST /state {state:"ended"}` (admin) → **save-point email appears in
    `outbox/`** containing the character name and save point.
15. Admin action **without** token → 403.

20 assertions per pass, PASS/FAIL printed per step, exit code 0 only if all
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

Key endpoints: `GET /health` · `POST /api/sessions` (host) ·
`POST /api/sessions/join {code}` · `POST /api/sessions/{id}/roll|narrate|notes|state|chapter|maps`
(header `X-Admin-Token` for admin actions) · `WS /api/sessions/{id}/ws`
(send `{"type":"roll","faces":20,"roller":"Aria"}`).
