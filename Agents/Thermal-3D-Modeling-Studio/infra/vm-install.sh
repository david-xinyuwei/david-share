#!/usr/bin/env bash
# Install or update the Thermal 3D Modeling Studio on this VM. infra/up.ps1 runs it as root through Azure Run Command and
# passes its settings in THERMAL_CONFIG_B64: base64 of a JSON object with fqdn, aiEndpoint, gpt6Deployment,
# imageDeployment, identityClientId, portalUsername, portalPassword ("" keeps the password already on the VM),
# repoUrl, repoRef, repoSubdir and buildSolids.
#
#   1 wait for the first-boot package jobs     2 fetch the studio from the repository
#   3 studio/deploy/bootstrap_vm.sh: packages, service user, Python venv with pinned packages, nginx, certificate
#   4 /opt/thermal-3d-studio/.env               5 studio/deploy/remote_install.sh: code, three.js, systemd service
#   6 the 15 reference STEP solids, Chinese and English names     7 restart and health checks
#
# Run Command returns only the last 4 KB of output, so this prints one line per step and THERMAL_INSTALL=PASS|FAIL;
# the full log is /var/log/thermal-install.log. Running it again updates the code and keeps the solids and the sign-in.
set -Eeuo pipefail
LOG=/var/log/thermal-install.log
APP_DIR=/opt/thermal-3d-studio
SRC=/opt/thermal-3d-studio-src
START=$(date +%s)
exec 3>&1 >>"$LOG" 2>&1
say() { local m; m="[$(date -u +%H:%M:%S)] $*"; echo "$m"; echo "$m" >&3; }
# Run Command returns only the last 4 KB: print the log tail first and the verdict line last.
fail() { trap - ERR; tail -n 25 "$LOG" | tr -d '\r' | grep -v '^$' | cut -c1-150 | sed 's/^/  | /' >&3; say "THERMAL_INSTALL=FAIL $*"; exit 1; }
trap 'fail "line $LINENO (exit $?): $BASH_COMMAND"' ERR

[ -n "${THERMAL_CONFIG_B64:-}" ] || fail "THERMAL_CONFIG_B64 is not set: run infra/up.ps1"
CFG=$(mktemp)
chmod 600 "$CFG"
trap 'rm -f "$CFG"' EXIT
echo "$THERMAL_CONFIG_B64" | base64 -d >"$CFG"
cfg() { python3 -c 'import json,sys; v=json.load(open(sys.argv[1]))[sys.argv[2]]; print(str(v).lower() if isinstance(v, bool) else v)' "$CFG" "$1"; }
FQDN=$(cfg fqdn)
REPO_URL=$(cfg repoUrl)
REPO_REF=$(cfg repoRef)
SUBDIR=$(cfg repoSubdir)
BUILD_SOLIDS=$(cfg buildSolids)
[[ "$FQDN" =~ ^[a-z0-9.-]+$ ]] || fail "bad fqdn: $FQDN"
[[ "$REPO_URL" =~ ^https://[A-Za-z0-9./_-]+$ ]] || fail "bad repoUrl: $REPO_URL"
[[ "$REPO_REF" =~ ^[A-Za-z0-9._/-]+$ ]] || fail "bad repoRef: $REPO_REF"
[[ "$SUBDIR" =~ ^[A-Za-z0-9._/-]+$ ]] || fail "bad repoSubdir: $SUBDIR"
say "install log: $LOG"

say "1/7 waiting for the first-boot package jobs"
cloud-init status --wait >/dev/null 2>&1 || true
# Wait while the boot-time apt-daily jobs or any apt/dpkg process run (at most 5 minutes). The unattended-upgrades
# daemon itself stays resident on Ubuntu and holds no lock, so it is not waited for.
for _ in $(seq 1 60); do
  systemctl is-active --quiet apt-daily.service apt-daily-upgrade.service || pgrep -x 'apt|apt-get|dpkg' >/dev/null || break
  sleep 5
done
# Any package job still holding the lock is waited for by apt itself.
printf 'DPkg::Lock::Timeout "600";\n' >/etc/apt/apt.conf.d/90-thermal-lock-timeout
export DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a NEEDRESTART_SUSPEND=1

say "2/7 fetching $SUBDIR/studio from $REPO_URL at $REPO_REF"
command -v git >/dev/null || { apt-get update -q; apt-get install -y -q --no-install-recommends git; }
rm -rf "$SRC"
# Shallow, blobless, sparse: only the studio directory of the repository is downloaded. Works for a branch or a commit.
git clone -q --depth 1 --filter=blob:none --sparse --no-checkout "$REPO_URL" "$SRC"
git -C "$SRC" sparse-checkout set "$SUBDIR/studio"
git -C "$SRC" fetch -q --depth 1 origin "$REPO_REF"
git -C "$SRC" checkout -q --detach FETCH_HEAD
COMMIT=$(git -C "$SRC" rev-parse HEAD)
STUDIO="$SRC/$SUBDIR/studio"
[ -f "$STUDIO/app.py" ] && [ -f "$STUDIO/deploy/bootstrap_vm.sh" ] || fail "no studio under $SUBDIR at $REPO_REF"
say "   commit $COMMIT"

say "3/7 host setup: packages, Python venv with pinned packages, nginx, certificate for $FQDN"
SETUP=$(mktemp -d)
chmod 755 "$SETUP"   # bootstrap_vm.sh installs requirements.txt from here as the user studio; mktemp -d gives 0700
cp "$STUDIO/deploy/bootstrap_vm.sh" "$STUDIO/deploy/constraints.txt" "$STUDIO/deploy/nginx-thermal-3d-studio.conf" \
   "$STUDIO/requirements.txt" "$SETUP/"
bash "$SETUP/bootstrap_vm.sh" "$FQDN"
say "   $(python3 --version), cadquery $("$APP_DIR/venv/bin/python" -c 'import cadquery; print(cadquery.__version__)')"

say "4/7 settings: $APP_DIR/.env"
python3 - "$CFG" "$STUDIO/.env.example" "$APP_DIR/.env" <<'PY'
import json, os, re, secrets, sys

cfg_path, example_path, env_path = sys.argv[1:4]
cfg = json.load(open(cfg_path, encoding="utf-8"))
current = {}
if os.path.exists(env_path):
    for line in open(env_path, encoding="utf-8").read().splitlines():
        m = re.match(r"^([A-Z0-9_]+)=(.*)$", line)
        if m:
            current[m.group(1)] = m.group(2)
password = cfg.get("portalPassword") or current.get("PORTAL_PASSWORD", "")
if not password:
    sys.exit("no sign-in password: up.ps1 passes one on the first install")
values = {
    "AOAI_ENDPOINT": cfg["aiEndpoint"],
    "AOAI_DEPLOYMENT": cfg["gpt6Deployment"],
    "AOAI_IMAGE_DEPLOYMENT": cfg.get("imageDeployment") or "",
    "AZURE_CLIENT_ID": cfg["identityClientId"],
    "PUBLIC_BASE_URL": "https://" + cfg["fqdn"],
    "PORTAL_USERNAME": cfg.get("portalUsername") or "studio",
    "PORTAL_PASSWORD": password,
    "PORTAL_SESSION_SECRET": current.get("PORTAL_SESSION_SECRET") or secrets.token_hex(32),
    "HOST_CONNECTION_FOR_ALL": "1",
}
lines, seen = [], set()
for line in open(example_path, encoding="utf-8").read().splitlines():
    m = re.match(r"^([A-Z0-9_]+)=(.*)$", line)
    if not m:
        lines.append(line)
        continue
    key = m.group(1)
    seen.add(key)
    # deployment values win; any other setting changed on the VM is kept; new settings come from .env.example
    lines.append(f"{key}={values.get(key, current.get(key, m.group(2)))}")
lines += [f"{k}={v}" for k, v in current.items() if k not in seen]
fd = os.open(env_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
PY
chown studio:studio "$APP_DIR/.env"
chmod 600 "$APP_DIR/.env"

say "5/7 code, three.js and the systemd service"
tar -czf /tmp/thermal-3d-studio.tar.gz -C "$STUDIO" --exclude=./.env --exclude=./venv --exclude=./.venv \
    --exclude=./__pycache__ --exclude=./cad_out --exclude=./static/vendor .
bash "$STUDIO/deploy/remote_install.sh"

# Commands inside $(...) inherit the ERR trap: anything that may legitimately exit non-zero there ends in || true.
solids() { [ -d "$APP_DIR/$1" ] || { echo 0; return 0; }; find "$APP_DIR/$1" -mindepth 2 -maxdepth 2 -name model.step | wc -l; }
# pregen_cad.py as the user studio: $1 = log file, $2 = extra environment ("" for none), the rest = its arguments.
pregen() { local out=$1 envs=$2; shift 2; sudo -u studio -H env $envs bash -c "cd $APP_DIR && venv/bin/python pregen_cad.py $*" >"$out" 2>&1 || true; cat "$out"; }
# The ids in its last line "done. failed: ['a', 'b']"; nothing for "done. failed: none".
failed_ids() { { grep -m1 'done. failed:' "$1" | grep -o "'[a-z0-9_-]*'" | tr -d "'" | paste -sd ' ' -; } || true; }
NO_EDGE=none
if [ "$BUILD_SOLIDS" = "true" ]; then
  say "6/7 building the 15 reference STEP solids with OpenCascade (no model call)"
  t=$(date +%s)
  pregen /tmp/thermal-pregen-zh.log ""
  if ! grep -q "done. failed: none" /tmp/thermal-pregen-zh.log; then
    bad=$(failed_ids /tmp/thermal-pregen-zh.log)
    [ -n "$bad" ] || fail "pregen_cad.py: $(tail -n 1 /tmp/thermal-pregen-zh.log)"
    # OpenCascade 7.9.3 on Linux crashes (SIGSEGV in libTKBRep) in the edge-break pass of some solids, every time
    # (seen for nb_thermal). Those are built again without the edge break: the same parts with sharp edges.
    say "   failed in the edge-break pass: $bad; building them again without the edge break"
    pregen /tmp/thermal-pregen-zh-noedge.log "CAD_EDGE_FINISH=0" $bad
    grep -q "done. failed: none" /tmp/thermal-pregen-zh-noedge.log ||
      fail "pregen_cad.py without the edge break: $(grep -m1 'failed:' /tmp/thermal-pregen-zh-noedge.log || tail -n 1 /tmp/thermal-pregen-zh-noedge.log)"
    NO_EDGE=$(echo $bad | tr ' ' ',')
  fi
  say "   Chinese part names: done in $(( $(date +%s) - t )) s"
  t=$(date +%s)
  pregen /tmp/thermal-pregen-en.log "" --lang en
  grep -q "done. failed: none" /tmp/thermal-pregen-en.log ||
    fail "pregen_cad.py --lang en: $(grep -m1 'failed:' /tmp/thermal-pregen-en.log || tail -n 1 /tmp/thermal-pregen-en.log); run up.ps1 again to retry"
  say "   English part names: done in $(( $(date +%s) - t )) s"
else
  say "6/7 reference solids skipped (-SkipReferenceSolids)"
fi
ZH=$(solids cad_cache)
EN=$(solids cad_cache_en)

say "7/7 restart and health checks"
systemctl restart thermal-3d-studio
for _ in $(seq 1 60); do
  curl -fsS http://127.0.0.1:3005/healthz >/dev/null 2>&1 && break
  sleep 1
done
curl -fsS http://127.0.0.1:3005/healthz >/dev/null || fail "the service is not healthy after the restart"
HTTPS=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "https://$FQDN/healthz" || true)
say "THERMAL_INSTALL=PASS commit=$COMMIT solids_zh=$ZH solids_en=$EN no_edge_break=$NO_EDGE https_from_vm=$HTTPS seconds=$(( $(date +%s) - START ))"
