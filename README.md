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

```bash
./scripts/setup.sh        # install backend deps + build frontend PWA
python3 scripts/seed_demo.py   # optional: load mock demo data (code DEMO42)
./scripts/run.sh          # serve API + PWA on http://0.0.0.0:8000
```

Open the printed LAN URL on each player's device. Demo: join with session code
**DEMO42**; 4 mock players (Aria, Bram, Cleo, Dana), a 3-chapter story, 3 maps,
and pre-seeded dice/narration events are included. Host admin token for the demo:
`demo-admin-token` (start/end session, next chapter, set map, AI narration).

The AI adapter uses Mistral first (set `MISTRAL_API_KEY` in `.env`) and falls
back to local Ollama, then to a deterministic local narration — the demo works
fully offline.

## Demo walkthrough (API)

```bash
GET  /health
POST /api/sessions/join      {"code":"DEMO42"}
POST /api/sessions/1/roll    {"count":1,"faces":20,"modifier":3,"roller":"Aria"}
POST /api/sessions/1/narrate {"scene":"The party enters the crypt"}
POST /api/sessions/1/state   {"state":"ended"}  header X-Admin-Token: demo-admin-token
# ended session writes save-point emails to ./outbox/
```

WebSocket live channel: `ws://<host>:8000/api/sessions/1/ws` — send
`{"type":"roll","faces":20,"roller":"Aria"}` and every connected client receives
the `dice` event in real time.

## Development

- Backend tests: `cd backend && pytest`
- Frontend tests: `cd frontend && npm test`
- E2E (mobile viewports): `cd frontend && npm run e2e`
- CI runs all of the above on every PR (see `.github/workflows/ci.yml`).

Configuration is via environment variables — copy `.env.example` to `.env`.
All AI provider keys are optional; without them the app uses local fallbacks.

## Pi / laptop deployment
See [deploy/README.md](deploy/README.md): `sudo scripts/harden-host.sh` (default-deny
firewall, app port open to LAN only) + `deploy/dnd-table.service` systemd unit.
