"""Can the current az sign-in mint a Cognitive Services token, and when does it expire? Prints no token.

Honours AZURE_CONFIG_DIR (isolated profile) and AZ_CLI (path to az / az.cmd) from the environment."""
import json, os, shutil, subprocess, sys, datetime
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
env = os.environ.copy()
az = env.get("AZ_CLI") or shutil.which("az.cmd") or shutil.which("az") or "az"
p = subprocess.run([az, "account", "get-access-token", "--resource", "https://cognitiveservices.azure.com", "-o", "json"],
                   env=env, capture_output=True, text=True, timeout=120)
print("returncode", p.returncode)
print("stderr", p.stderr.strip()[-600:])
if p.stdout.strip():
    d = json.loads(p.stdout)
    tok = d.pop("accessToken", "")
    print("token_len", len(tok), "expiresOn", d.get("expiresOn"), "expires_on_epoch", d.get("expires_on"), "sub", d.get("subscription", "")[:8], "tenant", d.get("tenant", "")[:8])
    print("now", datetime.datetime.now().isoformat(timespec="seconds"))
    # decode exp/iat/aud from JWT payload without verifying (diagnostic only)
    import base64
    payload = tok.split(".")[1] + "=="
    claims = json.loads(base64.urlsafe_b64decode(payload))
    print("aud", claims.get("aud"), "iat", datetime.datetime.fromtimestamp(claims["iat"]).isoformat(), "exp", datetime.datetime.fromtimestamp(claims["exp"]).isoformat())
