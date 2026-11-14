#!/usr/bin/env bash
# One-time host setup on a fresh Ubuntu 24.04 VM, run as root:  bash bootstrap_vm.sh <public fqdn>
# Packages, an unprivileged service user, the venv with pinned dependencies, nginx + Let's Encrypt.
# Expects requirements.txt, constraints.txt and nginx-thermal-3d-studio.conf next to this script.
set -euo pipefail
FQDN="${1:?usage: bootstrap_vm.sh <public fqdn>}"
APP_DIR=/opt/thermal-3d-studio
SRC="$(cd "$(dirname "$0")" && pwd)"
export DEBIAN_FRONTEND=noninteractive
log() { echo "[$(date -u +%H:%M:%S)] $*"; }

log "packages"
apt-get update -q
apt-get install -y -q --no-install-recommends python3-venv python3-pip nginx certbot curl ca-certificates openssl \
  libgl1 libglu1-mesa libegl1 libxrender1 libxext6 libx11-6 libxi6 libxcursor1 libxinerama1 libxft2 libfontconfig1 libgomp1

log "service user and directories"
id studio >/dev/null 2>&1 || useradd --system --create-home --home-dir /var/lib/studio --shell /usr/sbin/nologin studio
install -d -o studio -g studio -m 750 "$APP_DIR"
install -d -m 755 /var/www/acme
cd "$APP_DIR"   # ezdxf (imported by cadquery) stats ./ezdxf.ini: the cwd must be readable by studio

log "venv with pinned dependencies"
[ -x "$APP_DIR/venv/bin/python" ] || sudo -u studio -H python3 -m venv "$APP_DIR/venv"
sudo -u studio -H "$APP_DIR/venv/bin/python" -m pip install -q --upgrade pip
sudo -u studio -H "$APP_DIR/venv/bin/python" -m pip install -q -r "$SRC/requirements.txt" -c "$SRC/constraints.txt"
sudo -u studio -H "$APP_DIR/venv/bin/python" -c "import cadquery, fastapi, openai, docx; print('IMPORT_OK cadquery', cadquery.__version__)"

if [ ! -f "/etc/letsencrypt/live/$FQDN/fullchain.pem" ]; then
  log "nginx: port 80 for the ACME challenge only"
  cat > /etc/nginx/sites-available/thermal-3d-studio <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name $FQDN;
    location ^~ /.well-known/acme-challenge/ { root /var/www/acme; }
    location / { return 503; }
}
EOF
  ln -sf /etc/nginx/sites-available/thermal-3d-studio /etc/nginx/sites-enabled/thermal-3d-studio
  rm -f /etc/nginx/sites-enabled/default
  nginx -t && systemctl reload nginx
  log "certificate for $FQDN"
  certbot certonly --webroot -w /var/www/acme -d "$FQDN" --non-interactive --agree-tos --register-unsafely-without-email
fi
install -d /etc/letsencrypt/renewal-hooks/deploy
printf '#!/bin/sh\nsystemctl reload nginx\n' > /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
chmod 755 /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh

log "nginx: HTTPS front"
sed "s/__FQDN__/$FQDN/g" "$SRC/nginx-thermal-3d-studio.conf" > /etc/nginx/sites-available/thermal-3d-studio
ln -sf /etc/nginx/sites-available/thermal-3d-studio /etc/nginx/sites-enabled/thermal-3d-studio
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
systemctl is-active --quiet certbot.timer && log "certbot.timer active (auto-renew)"
log "BOOTSTRAP_DONE"
