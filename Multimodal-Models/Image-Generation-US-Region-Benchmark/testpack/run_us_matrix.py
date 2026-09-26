"""US image-model matrix for the Chicago workshop, 9 groups: MAI-Image-2.6; GPT-Image-2 at low / high;
GPT-Image-2.5 flare and sunburst at auto / low / high. 17 prompts (11 from the published repo + 6 from Anzhe's
Sept 14-17 report), 2 rounds, second round in reverse group order. `auto` exists only on the 2.5 deployments.

Runs from the tester's own machine so the timings include the real client-to-Azure path.
Resumable: re-running the same command skips samples already completed.

Auth: both US resources have key auth disabled by subscription policy (disableLocalAuth=true, PATCH to false is
reverted by policy), so the default is an Entra ID bearer token from `az account get-access-token`. Log in once
(`az login`, optionally with AZURE_CONFIG_DIR pointing at an isolated profile) and hold the role
`Cognitive Services User` / `Cognitive Services OpenAI User` (or Owner) on the two accounts. If keys are ever
re-enabled, putting AZURE_OPENAI_API_KEY / AZURE_API_KEY in .env switches those groups back to api-key auth.

    python run_us_matrix.py            # full matrix: 9 groups x 17 prompts x 2 rounds = 306 images
    python run_us_matrix.py --dry-run  # validate inputs, no network calls
    python run_us_matrix.py --smoke    # warm-up only: 1 image per group (9 images) to prove auth and deployment names
"""
import hashlib
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNNER = HERE / "source" / "benchmark_5way_v2.py"
PROMPTS = HERE / "source" / "prompts.csv"
ENV_FILE = HERE / ".env"
RUN_TAG = os.environ.get("RUN_TAG") or f"us-matrix-{datetime.now():%Y%m%d}"
OUTPUT = HERE / "runs" / RUN_TAG

# Deployment names exactly as they exist on the two resources; tiers per Xinyu's 2026-09-26 decision
# (gpt-image-2 has no `auto`; the 2.5 deployments do, and echo the tier they actually used in the response).
GPT_GROUPS = ["gpt-image-2:low,high", "gpt-image-2.5-flare:auto,low,high", "gpt-image-2.5-sunburst:auto,low,high"]
REQUIRED = ("GPT_ENDPOINT", "MAI_ENDPOINT")
OPTIONAL_KEYS = ("AZURE_OPENAI_API_KEY", "AZURE_API_KEY")


def load_env(env):
    """Overlay .env (if present) on the process environment; placeholders like <paste ...> count as unset."""
    source = ENV_FILE if ENV_FILE.is_file() else (HERE / ".env.example")
    for raw in source.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if value.startswith("<"):
            continue
        env.setdefault(key, value)  # a real environment variable always wins over the file
    for key in OPTIONAL_KEYS:
        if env.get(key, "").startswith("<"):
            env.pop(key)
    missing = [k for k in REQUIRED if not env.get(k) or env[k].startswith("<")]
    if missing:
        raise SystemExit(f"Set these (in .env or the environment) first: {missing}")
    env["AUTH_MODE"] = "api-key" if all(env.get(k) for k in OPTIONAL_KEYS) else (
        "mixed" if any(env.get(k) for k in OPTIONAL_KEYS) else "entra-bearer")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv):
    for path in (RUNNER, PROMPTS):
        if not path.is_file():
            raise SystemExit(f"Missing input: {path}")
    env = os.environ.copy()
    load_env(env)
    env["PYTHONIOENCODING"] = "utf-8"
    env.setdefault("BENCHMARK_CLIENT_LOCATION", "tester workstation; see README")

    passthrough = [a for a in argv if a != "--smoke"]
    prompts = PROMPTS
    out = OUTPUT
    if "--smoke" in argv:
        # The runner's warm-up phase already sends one request per group; that is the cheapest way to
        # prove both keys and every deployment name before committing to 340 images. Same output
        # directory, so the real run later resumes past these warm-ups instead of repeating them.
        passthrough.append("--warmup-only")

    cmd = [sys.executable, "-u", str(RUNNER),
           "--mai-model", "MAI-Image-2.6",
           *sum((["--gpt-model", g] for g in GPT_GROUPS), []),
           "--prompts-csv", str(prompts),
           "--output", str(out),
           "--resume", *passthrough]

    out.mkdir(parents=True, exist_ok=True)
    # Freeze runner + prompts beside the results so the archive is self-describing.
    src = out / "source"
    src.mkdir(exist_ok=True)
    for p in (RUNNER, prompts):
        (src / p.name).write_bytes(p.read_bytes())
    (out / "RUN-INFO.txt").write_text(
        f"started_local={datetime.now().isoformat(timespec='seconds')}\n"
        f"runner_sha256={sha256(RUNNER)}\nprompts_sha256={sha256(prompts)}\n"
        f"client_location={env['BENCHMARK_CLIENT_LOCATION']}\n"
        f"auth_mode={env['AUTH_MODE']}\naz_profile={env.get('AZURE_CONFIG_DIR', '(default)')}\n"
        f"gpt_endpoint_host={env['GPT_ENDPOINT'].split('//')[-1]}\nmai_endpoint_host={env['MAI_ENDPOINT'].split('//')[-1]}\n"
        f"command={' '.join(cmd[2:])}\n", encoding="utf-8")

    print(f"RUNNER_SHA256 {sha256(RUNNER)}")
    print(f"PROMPTS_SHA256 {sha256(prompts)}")
    print(f"AUTH_MODE {env['AUTH_MODE']}  AZ_PROFILE {env.get('AZURE_CONFIG_DIR', '(default)')}")
    print(f"OUTPUT {out}")
    print("COMMAND", " ".join(cmd[2:]), flush=True)
    return subprocess.run(cmd, env=env, cwd=str(HERE)).returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
