#!/usr/bin/env bash
# Host hardening for running the D&D table app on a laptop/Raspberry Pi.
# LAN-only exposure: default-deny inbound, allow only the app port + SSH from the LAN.
# Run with sudo. Idempotent.
set -euo pipefail

APP_PORT="${APP_PORT:-8000}"
LAN_SUBNET="${LAN_SUBNET:-192.168.0.0/16}"

if [ "$(id -u)" -ne 0 ]; then
  echo "run with sudo" >&2
  exit 1
fi

if command -v ufw >/dev/null 2>&1; then
  ufw --force reset
  ufw default deny incoming
  ufw default allow outgoing
  ufw allow in on "$(ip -4 route show default | awk '{print $5}' | head -1)" to any port 22 proto tcp comment 'ssh lan'
  ufw allow from "$LAN_SUBNET" to any port "$APP_PORT" proto tcp comment 'dnd-table lan'
  ufw --force enable
  echo "ufw: default-deny incoming; allowed ssh + :$APP_PORT from $LAN_SUBNET"
elif command -v firewall-cmd >/dev/null 2>&1; then
  firewall-cmd --permanent --set-default-zone=drop
  firewall-cmd --permanent --zone=drop --add-rich-rule="rule family=ipv4 source address=$LAN_SUBNET port port=$APP_PORT protocol=tcp accept"
  firewall-cmd --reload
  echo "firewalld: drop zone default; app port open to $LAN_SUBNET only"
else
  echo "no ufw/firewalld found; install ufw and re-run" >&2
  exit 1
fi

# unattended security upgrades (Debian/Raspberry Pi OS)
if command -v apt-get >/dev/null 2>&1; then
  apt-get install -y unattended-upgrades >/dev/null 2>&1 || true
  echo "unattended-upgrades: ensure 'APT::Periodic::Unattended-Upgrade \"1\";' is set"
fi

# data dir permissions
chmod 700 /opt/dnd-table/data /opt/dnd-table/outbox 2>/dev/null || true
[ -f /opt/dnd-table/.env ] && chmod 600 /opt/dnd-table/.env
echo "hardening done. Verify with: sudo ufw status verbose"
