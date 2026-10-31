# D&D Table Companion

👉 **New here? Read [GETTING_STARTED.md](GETTING_STARTED.md) — a step-by-step, plain-English guide including the demo.**

A real-time dungeon-master companion for the game table. A laptop or
Raspberry Pi hosts the app; players join from phones/iPads over the local
network via a mobile-first PWA. AI calls go to Mistral (EU-hosted,
GDPR-compliant — no US LLM providers) with a fully local Ollama fallback,
so no new services are needed and it also runs offline.

See [MASTER_PLAN.md](MASTER_PLAN.md) for the full architecture, testing
strategy, CI, and roadmap.

## Quick start

👉 **New here? [GETTING_STARTED.md](GETTING_STARTED.md) walks you through playing
with friends step by step — start there.**

```bash
./scripts/setup.sh        # install backend deps + build frontend PWA
./scripts/run.sh          # serve API + PWA on http://0.0.0.0:8000
```

On the host, open `http://localhost:8000`, type a story idea, pick a campaign
length (default **1 hour**, extendable mid-game), and tap
**✨ Generate story & host** — the LLM writes the campaign and you get a 6-char
code to share. Players open `http://<host-ip>:8000` on their phones and join
with the code. Or skip the story: **🎲 Quick host**.

Want to try it instantly instead? `python3 scripts/seed_demo.py` loads a ready
session (code **DEMO42**, 4 mock players, a 3-chapter story, maps, pre-seeded
events, running 1-hour campaign clock; admin token `demo-admin-token`).

The AI adapter uses Mistral first (set `MISTRAL_API_KEY` in `.env`) and falls
back to local Ollama, then to a deterministic local narration — the demo works
fully offline.

## Demo walkthrough (API)

```bash
GET  /health
POST /api/stories/generate   {"prompt":"goblins stole the village bell","length_hours":1}
POST /api/sessions           {"story_id":<id>,"campaign_minutes":60}   # -> {"code":"ABC123","admin_token":"..."}
POST /api/sessions/join      {"code":"ABC123","player_id":1}           # -> player_token + snapshot
POST /api/sessions/1/roll    {"count":1,"faces":20,"modifier":3,"mode":"adv","roller":"Aria"}
POST /api/sessions/1/combat  {"combatants":[{"name":"Goblin","hp":7,"is_enemy":true}]}  header X-Admin-Token
POST /api/sessions/1/combat/roll    # roll initiative, sorted        header X-Admin-Token
POST /api/sessions/1/campaign/extend {"minutes":30}                     # extend the 1h default
POST /api/sessions/1/chat    {"text":"I sneak ahead"}                   header X-Player-Token
POST /api/sessions/1/narrate {"scene":"The party enters the crypt"}
POST /api/sessions/1/state   {"state":"ended"}                          header X-Admin-Token
# ended session writes save-point emails to ./outbox/
```

WebSocket live channel: `ws://<host>:8000/api/sessions/1/ws?token=<player_token>`
(the token from `POST /api/sessions/join`) — send `{"type":"roll","faces":20}`
or `{"type":"chat","text":"hi"}` and every connected client receives the event
in real time, with the sender attributed from the token.

## Development

- **Self-test loop (run this first, no input needed):** `python3 scripts/smoke_loop.py --watch 3` —
  boots the app on 127.0.0.1 and plays a full session (LLM campaign from the host's story idea →
  host → join → campaign clock + extend → dice over WebSocket → combat tracker → chat → AI recap →
  narration → chapter → end → save-point email) asserting 37 steps. See [VIBE.md](VIBE.md).
- Backend tests: `cd backend && pytest`
- Frontend tests: `cd frontend && npm test`
- E2E (mobile viewports): `cd frontend && npm run e2e`
- CI runs all of the above on every PR (see `.github/workflows/ci.yml`).

Configuration is via environment variables — copy `.env.example` to `.env`.
All AI provider keys are optional; without them the app uses local fallbacks.

## Pi / laptop deployment
See [deploy/README.md](deploy/README.md): `sudo scripts/harden-host.sh` (default-deny
firewall, app port open to LAN only) + `deploy/dnd-table.service` systemd unit.
