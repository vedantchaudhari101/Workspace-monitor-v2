#!/usr/bin/env bash
# =============================================================================
# Workspace Monitor — one-command server setup (Ubuntu 22.04/24.04, x86 or ARM)
#
# Run from the project folder on the server:
#     bash deploy/oracle/setup.sh
#
# What it does:
#   1. Opens ports 80 and 443 in the server's own firewall (Oracle's Ubuntu
#      images block them by default, even after you open them in the console).
#   2. Installs Docker.
#   3. Asks a few questions and writes deploy/oracle/.env.
#   4. Builds and starts the app behind Caddy (automatic HTTPS).
#
# Safe to run again: it keeps your existing settings unless you choose to change them.
# =============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$HERE/.env"
COMPOSE=(sudo docker compose -f "$HERE/docker-compose.yml")

say()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m%s\033[0m\n' "$*"; }

if [ "$(id -u)" -eq 0 ]; then
  warn "Run this as the normal 'ubuntu' user (without sudo). It asks for sudo itself when needed."
  exit 1
fi

# ── 1. Firewall on the server ────────────────────────────────────────────────
say "Opening ports 80 and 443 in the server firewall"
if ! command -v netfilter-persistent >/dev/null 2>&1; then
  sudo DEBIAN_FRONTEND=noninteractive apt-get update -y
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y iptables-persistent
fi
if ! sudo iptables -C INPUT -p tcp -m multiport --dports 80,443 -m conntrack --ctstate NEW -j ACCEPT 2>/dev/null; then
  sudo iptables -I INPUT 1 -p tcp -m multiport --dports 80,443 -m conntrack --ctstate NEW -j ACCEPT
  sudo iptables -I INPUT 1 -p udp --dport 443 -m conntrack --ctstate NEW -j ACCEPT
  # Save before Docker is installed so Docker's own rules are never saved here.
  if ! command -v docker >/dev/null 2>&1; then
    sudo netfilter-persistent save
  else
    warn "Docker is already installed; the port rule is active now but may not survive a reboot."
    warn "If the site stops loading after a reboot, run this script again."
  fi
  echo "Ports 80 and 443 are open."
else
  echo "Already open."
fi

# ── 2. Docker ─────────────────────────────────────────────────────────────────
say "Installing Docker"
if command -v docker >/dev/null 2>&1; then
  echo "Docker is already installed: $(docker --version)"
else
  curl -fsSL https://get.docker.com | sudo sh
  sudo systemctl enable --now docker
fi

# ── 3. Settings ───────────────────────────────────────────────────────────────
PUBLIC_IP="$(curl -fsS -4 --max-time 5 https://ifconfig.me 2>/dev/null || curl -fsS -4 --max-time 5 https://api.ipify.org 2>/dev/null || echo "")"

write_env=true
if [ -f "$ENV_FILE" ]; then
  say "Existing settings found"
  grep -E '^(SITE_ADDRESS|ADMIN_EMAIL|SEED_DEMO|SHOW_DEMO_LOGIN)=' "$ENV_FILE" || true
  read -r -p "Keep these settings? [Y/n] " keep
  case "${keep:-Y}" in [nN]*) write_env=true ;; *) write_env=false ;; esac
fi

if $write_env; then
  say "A few questions (press Enter to accept the value in brackets)"

  echo
  echo "Web address. If you created a free DuckDNS name (e.g. workspace-monitor.duckdns.org)"
  echo "and pointed it at this server, type it here to get an https:// link."
  echo "Leave it empty to use plain http://${PUBLIC_IP:-<server-ip>} for now."
  read -r -p "Domain []: " DOMAIN
  DOMAIN="$(echo "$DOMAIN" | sed -e 's#^https\?://##' -e 's#/.*$##' | tr -d '[:space:]')"
  if [ -n "$DOMAIN" ]; then SITE_ADDRESS="$DOMAIN"; else SITE_ADDRESS=":80"; fi

  read -r -p "Admin email [admin@workspace.dev]: " ADMIN_EMAIL
  ADMIN_EMAIL="${ADMIN_EMAIL:-admin@workspace.dev}"

  while true; do
    read -r -s -p "Admin password, letters/numbers/@#%_.- only (leave empty to generate one): " ADMIN_PASSWORD; echo
    if [ -z "$ADMIN_PASSWORD" ] || [[ "$ADMIN_PASSWORD" =~ ^[A-Za-z0-9@#%_.-]{8,}$ ]]; then break; fi
    warn "Use at least 8 characters from: letters, numbers and @ # % _ . -"
  done
  if [ -z "$ADMIN_PASSWORD" ]; then
    ADMIN_PASSWORD="$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 14)"
    GENERATED_PASSWORD=true
  fi

  read -r -p "Include the example building with demo data? [Y/n] " seed
  case "${seed:-Y}" in [nN]*) SEED_DEMO=false ;; *) SEED_DEMO=true ;; esac

  echo
  echo "Show a 'fill in the demo account' button on the sign-in page?"
  echo "Visitors can then sign in without asking you, but they can also upload"
  echo "videos and approve recommendations. You can change this later."
  read -r -p "Show demo login button? [y/N] " demo
  case "${demo:-N}" in [yY]*) SHOW_DEMO_LOGIN=true ;; *) SHOW_DEMO_LOGIN=false ;; esac

  SECRET_KEY="$(tr -dc 'a-f0-9' </dev/urandom | head -c 64)"

  umask 077
  cat >"$ENV_FILE" <<EOF
# Written by setup.sh — edit and run 'bash deploy/oracle/setup.sh' again to apply.
SITE_ADDRESS=$SITE_ADDRESS
ADMIN_EMAIL=$ADMIN_EMAIL
ADMIN_PASSWORD=$ADMIN_PASSWORD
SECRET_KEY=$SECRET_KEY
SEED_DEMO=$SEED_DEMO
SHOW_DEMO_LOGIN=$SHOW_DEMO_LOGIN
MAX_UPLOAD_MB=200
EOF
  echo "Saved to $ENV_FILE"
fi

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

# ── 4. Build and start ────────────────────────────────────────────────────────
say "Building and starting (the first build takes 10–20 minutes)"
"${COMPOSE[@]}" up -d --build

say "Waiting for the app to start"
for _ in $(seq 1 60); do
  if "${COMPOSE[@]}" exec -T app curl -fs http://localhost:8000/health >/dev/null 2>&1; then
    ok=true; break
  fi
  sleep 5
done

if [ "${ok:-false}" != true ]; then
  warn "The app hasn't answered yet. See what it's doing with:"
  warn "  sudo docker compose -f deploy/oracle/docker-compose.yml logs -f app"
  exit 1
fi

if [ "$SITE_ADDRESS" = ":80" ]; then URL="http://${PUBLIC_IP:-<your-server-ip>}"; else URL="https://$SITE_ADDRESS"; fi

say "Done"
echo "Open:      $URL"
echo "Sign in:   $ADMIN_EMAIL"
if [ "${GENERATED_PASSWORD:-false}" = true ]; then
  echo "Password:  $ADMIN_PASSWORD   (write this down; it's also in deploy/oracle/.env)"
else
  echo "Password:  the one you entered (also stored in deploy/oracle/.env)"
fi
if [ "$SITE_ADDRESS" != ":80" ]; then
  echo
  echo "HTTPS certificates can take a minute on first visit. If the page doesn't load,"
  echo "check that $SITE_ADDRESS points to ${PUBLIC_IP:-this server} and that port 443 is open in the Oracle console."
fi
