#!/usr/bin/env bash
# Install/upgrade the Thermal 3D Modeling Studio on the VM (run as root by deploy.ps1).
# Expects /tmp/thermal-3d-studio.tar.gz from deploy.ps1, a host prepared by deploy/bootstrap_vm.sh, and .env already provisioned
# (owner studio, mode 600). The service runs as the unprivileged user "studio" on 127.0.0.1:3005 behind nginx.
set -euo pipefail
APP_DIR=/opt/thermal-3d-studio
TARBALL=/tmp/thermal-3d-studio.tar.gz
AS_STUDIO="sudo -u studio -H"

[ -x "$APP_DIR/venv/bin/python" ] || { echo ">> $APP_DIR/venv missing: run deploy/bootstrap_vm.sh first"; exit 1; }
[ -f "$APP_DIR/.env" ] || { echo ">> $APP_DIR/.env missing: provision it before deploying (never shipped in the tarball)"; exit 1; }
tar -xzf "$TARBALL" -C "$APP_DIR" --no-same-owner
rm -f "$TARBALL"
chown -R studio:studio "$APP_DIR"
# Tarballs built from OneDrive folders carry the Windows read-only attribute as r-x directories.
chmod -R u+rwX,go-w "$APP_DIR"
cd "$APP_DIR"
sed -i 's/\r$//' deploy/*.sh deploy/constraints.txt .env.example requirements.txt 2>/dev/null || true

$AS_STUDIO venv/bin/python -m pip install --quiet -r requirements.txt -c deploy/constraints.txt

if [ ! -f static/vendor/three/three.module.js ] || [ ! -f static/vendor/three/jsm/loaders/STLLoader.js ] || [ ! -f static/vendor/three/jsm/loaders/GLTFLoader.js ] \
   || [ ! -f static/vendor/three/jsm/geometries/RoundedBoxGeometry.js ] \
   || [ ! -f static/vendor/three/jsm/math/SimplexNoise.js ]; then   # RoundedBoxGeometry: studio-kit filletBox(); GTAO chain: workspace AO
  echo ">> vendoring three.js"; $AS_STUDIO bash deploy/vendor_three.sh static/vendor/three
fi
# Context-shell assets (own procedural GLBs) ship in the tarball.
for f in static/assets/car/sedan.glb static/assets/notebook/laptop14_open.glb static/assets/notebook/laptop14_closed.glb; do
  [ -f "$f" ] || echo ">> WARNING: asset $f missing (run assets/build_*.py locally and redeploy)"
done
# Pre-compress vendor scripts (served as <file>.js.gz with Content-Encoding: gzip when the browser accepts it). Idempotent.
find static/vendor -type f -name '*.js' | while read -r f; do
  if [ ! -f "$f.gz" ] || [ "$f" -nt "$f.gz" ]; then $AS_STUDIO gzip -kf9 "$f"; fi
done
echo ">> vendor gz files: $(find static/vendor -name '*.js.gz' | wc -l)"
$AS_STUDIO mkdir -p cad_out

# Signed-in users always use the server-managed Azure connection; enforce it on upgrades too.
if grep -q '^HOST_CONNECTION_FOR_ALL=' .env; then
  sed -i 's/^HOST_CONNECTION_FOR_ALL=.*/HOST_CONNECTION_FOR_ALL=1/' .env
else
  printf '\nHOST_CONNECTION_FOR_ALL=1\n' >> .env
fi
chown studio:studio .env && chmod 600 .env

install -m 644 deploy/thermal-3d-studio.service /etc/systemd/system/thermal-3d-studio.service
systemctl daemon-reload
systemctl enable --quiet thermal-3d-studio
systemctl restart thermal-3d-studio
sleep 2
for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:3005/healthz >/dev/null 2>&1; then echo ">> healthy: $(curl -fsS http://127.0.0.1:3005/healthz)"; exit 0; fi
  sleep 1
done
echo ">> service did not become healthy; last log lines:"; tail -n 40 /var/log/thermal-3d-studio.log; exit 1
