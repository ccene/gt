# D&D Table Companion

A real-time dungeon-master companion for the game table. A laptop or
Raspberry Pi hosts the app; players join from phones/iPads over the local
network via a mobile-first PWA. Cloud AI calls use free tiers only, with
local fallbacks, so it runs at zero extra cost.

See [MASTER_PLAN.md](MASTER_PLAN.md) for the full architecture, testing
strategy, CI, and roadmap.

## Quick start (once the app scaffold lands)

```bash
./scripts/setup.sh   # install backend deps + build frontend
./scripts/run.sh     # serve API + PWA on http://0.0.0.0:8000
```

Open the printed LAN URL on each player's device.

## Development

- Backend tests: `cd backend && pytest`
- Frontend tests: `cd frontend && npm test`
- E2E (mobile viewports): `cd frontend && npm run e2e`
- CI runs all of the above on every PR (see `.github/workflows/ci.yml`).

Configuration is via environment variables — copy `.env.example` to `.env`.
All AI provider keys are optional; without them the app uses local fallbacks.
