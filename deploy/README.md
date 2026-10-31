# Deploying on a Raspberry Pi / laptop

1. Copy the repo to `/opt/dnd-table`, create `.env` (chmod 600) from `.env.example`.
2. `./scripts/setup.sh` (creates `.venv`, installs backend + builds frontend).
3. Optional: `python3 scripts/seed_demo.py` for demo data.
4. Harden the host: `sudo scripts/harden-host.sh` (default-deny firewall, app port open to the LAN only, unattended upgrades).
5. Install the service: `sudo cp deploy/dnd-table.service /etc/systemd/system/ && sudo systemctl enable --now dnd-table@$(whoami)`
   (adjust `User=`/paths in the unit to your setup).
6. Players open `http://<pi-ip>:8000` on their phones and "Add to Home Screen" (iPad PWA).

**Security notes**
- LAN-only by design: no public ports, no tunnels. Remote access only via WireGuard, never port forwarding.
- Admin actions are gated by a **WebAuthn passkey** (register/sign-in in the PWA host panel); the per-session admin token remains as fallback.
- Mistral API key lives only in `.env` (0600) and is used with a dedicated key + spend cap + MFA on the Mistral account.
- Mic audio is transcribed by local Whisper; raw audio is never stored. Camera frames go to Pixtral (EU) only on explicit host action.
- Backups: copy `data/` with `cp` to local disk/USB, encrypted with `age` or `gpg` — never to cloud sync.
