#!/usr/bin/env python3
"""Render SGLang launch and benchmark commands from a profile, with optional ablation.

    python tools/render_launch.py --profile rocm-mi300x-pd --role decode
    python tools/render_launch.py --profile rocm-mi300x-pd --role decode --ablate ck-a8w8-gemm
    python tools/render_launch.py --profile cuda-hopper-pd --role prefill
    python tools/render_launch.py --list

A profile is a JSON file in profiles/. Each role has a base command; each
technique adds environment variables and arguments to the roles it touches.
`--ablate <technique>` removes exactly that technique's contribution (and adds
its `ablate_env`, if any), which is how a single-variable A/B is set up. The
script only prints a bash snippet; it never starts a process.
"""
from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ROOT / "profiles"


def load_profile(name: str) -> dict:
    path = PROFILES / f"{name}.json"
    if not path.is_file():
        raise SystemExit(f"unknown profile {name!r}; see --list")
    return json.loads(path.read_text(encoding="utf-8"))


def known_techniques() -> set[str]:
    catalog = json.loads((PROFILES / "techniques.json").read_text(encoding="utf-8"))
    return {t["id"] for t in catalog["techniques"]}


def compose(profile: dict, role: str, ablate: list[str]) -> tuple[dict[str, str], list[str], list[str]]:
    """Return (env, argv, notes) for one role."""
    if role not in profile["roles"]:
        raise SystemExit(f"profile {profile['profile']} has no role {role!r}; roles: {', '.join(profile['roles'])}")
    catalog = known_techniques()
    for tech in ablate:
        if tech not in catalog:
            raise SystemExit(f"unknown technique {tech!r}")
        if tech not in profile["techniques"]:
            raise SystemExit(f"technique {tech!r} is not part of profile {profile['profile']}")
    spec = profile["roles"][role]
    env: dict[str, str] = {}
    if spec["command"][-1] == "sglang.launch_server":
        env.update(profile.get("platform_env", {}))
    env.update(spec.get("env", {}))
    argv = list(spec["command"]) + list(spec["args"])
    notes: list[str] = []
    for tech, per_role in profile["techniques"].items():
        if tech not in catalog:
            raise SystemExit(f"profile uses unknown technique {tech!r}")
        part = per_role.get(role)
        if part is None:
            continue
        if tech in ablate:
            env.update(part.get("ablate_env", {}))
            continue
        env.update(part.get("env", {}))
        argv.extend(part.get("args", []))
        if part.get("note"):
            notes.append(f"{tech}: {part['note']}")
    flags = [a for a in argv if a.startswith("--")]
    duplicates = sorted({f for f in flags if flags.count(f) > 1})
    if duplicates:
        raise SystemExit(f"duplicate flags in rendered command: {duplicates}")
    return env, argv, notes


def _quote(token: str) -> str:
    if "${" in token:
        return f'"{token}"'
    return shlex.quote(token)


def render(profile: dict, role: str, ablate: list[str]) -> str:
    env, argv, notes = compose(profile, role, ablate)
    lines = [f"# profile={profile['profile']} status={profile['status']} role={role}"]
    if ablate:
        lines.append("# ablate=" + ",".join(sorted(ablate)))
    lines.extend(f"# {n}" for n in notes)
    if "SGLANG_SIMULATE_ACC_LEN" in env:
        lines.append("# WARNING: fixed MTP acceptance (SGLANG_SIMULATE_ACC_LEN) is a performance-method setting;")
        lines.append("#          throughput measured this way is not production throughput. Ablate")
        lines.append("#          'simulated-acceptance' for real acceptance.")
    lines.extend(f"export {k}={_quote(v)}" for k, v in sorted(env.items()))
    cmd_len = len(profile["roles"][role]["command"])
    head = " ".join(_quote(t) for t in argv[:cmd_len])
    tail = argv[cmd_len:]
    body, i = [], 0
    while i < len(tail):
        tok = tail[i]
        if i + 1 < len(tail) and not tail[i + 1].startswith("--"):
            body.append(f"{tok} {_quote(tail[i + 1])}")
            i += 2
        else:
            body.append(tok)
            i += 1
    lines.append(head + " \\")
    for n, item in enumerate(body):
        lines.append("  " + item + (" \\" if n < len(body) - 1 else ""))
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profile")
    ap.add_argument("--role")
    ap.add_argument("--ablate", action="append", default=[], help="technique id to remove (repeatable)")
    ap.add_argument("--list", action="store_true", help="list profiles, roles and techniques")
    args = ap.parse_args(argv)
    if args.list:
        for path in sorted(PROFILES.glob("*.json")):
            if path.name == "techniques.json":
                continue
            prof = json.loads(path.read_text(encoding="utf-8"))
            print(f"{prof['profile']} [{prof['status']}] roles={','.join(prof['roles'])} "
                  f"techniques={','.join(prof['techniques'])}")
        return 0
    if not args.profile or not args.role:
        ap.error("--profile and --role are required unless --list is given")
    sys.stdout.write(render(load_profile(args.profile), args.role, args.ablate))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
