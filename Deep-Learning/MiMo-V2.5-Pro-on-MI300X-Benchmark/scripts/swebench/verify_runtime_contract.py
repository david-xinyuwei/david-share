#!/usr/bin/env python3
"""Verify that a running MiMo-V2.5-Pro server matches the SWE-bench accuracy contract.

Run this on the serving host (inside or outside the container, as long as /proc of the
``sglang.launch_server`` process is visible) before pointing the customer's
mini-swe-agent harness at the endpoint::

    python3 verify_runtime_contract.py --mode mtp-on  --url http://127.0.0.1:30001
    python3 verify_runtime_contract.py --mode mtp-off --url http://127.0.0.1:30001

Checks, in order:
1. ``/v1/models`` answers HTTP 200 (no generation is triggered; ``/health`` is avoided
   because with ``SGLANG_ENABLE_HEALTH_ENDPOINT_GENERATION=1`` it runs a real token).
2. Exactly one ``sglang.launch_server`` process listens on the expected port and its
   command line carries the shared flags plus the mode-specific speculative flags.
3. That process's environment carries the kernel-path settings shared by both runs
   (AITER, ``vectorized_5d``, FlyDSL PA with 16 partitions, CK bpreshuffle) and does not
   carry ``SGLANG_SIMULATE_ACC_LEN`` / ``SGLANG_SIMULATE_ACC_METHOD``. In ``mtp-on`` mode
   the wrapper gates are also required: ``SGLANG_MIMO_EAGLE_HIP_NONGREEDY_VERIFY=1``,
   ``ROCM_QUICK_REDUCE_QUANTIZATION=NONE`` and ``SGLANG_ENABLE_HEALTH_ENDPOINT_GENERATION=0``.
4. ``/server_info`` is fetched and the fields it exposes are echoed for the run record;
   missing fields are reported as NOT_AVAILABLE, never assumed.

Exit code 0 prints ``SWEBENCH_RUNTIME_CONTRACT=PASS``; any mismatch exits 1.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

SHARED_FLAGS = (
    "--tp-size 8",
    "--attention-backend aiter",
    "--kv-cache-dtype fp8_e4m3",
    "--page-size 64",
    "--context-length 1048576",
    "--chunked-prefill-size 65536",
    "--reasoning-parser mimo",
    "--tool-call-parser mimo",
)
SPECULATIVE_FLAGS = (
    "--speculative-algorithm EAGLE",
    "--speculative-num-steps 3",
    "--speculative-eagle-topk 1",
    "--speculative-num-draft-tokens 4",
    "--enable-multi-layer-eagle",
)
SHARED_ENV = {
    "SGLANG_USE_AITER": "1",
    "SGLANG_AITER_KV_CACHE_LAYOUT": "vectorized_5d",
    "SGLANG_AITER_PA_DECODE_IMPL": "flydsl",
    "SGLANG_FLYDSL_PA_NUM_PARTITIONS": "16",
    "SGLANG_USE_AITER_CK_BLOCKSCALE_BPRESHUFFLE": "1",
}
MTP_ON_ENV = {
    "SGLANG_MIMO_EAGLE_HIP_NONGREEDY_VERIFY": "1",
    "ROCM_QUICK_REDUCE_QUANTIZATION": "NONE",
    "SGLANG_ENABLE_HEALTH_ENDPOINT_GENERATION": "0",
}
FORBIDDEN_ENV = ("SGLANG_SIMULATE_ACC_LEN", "SGLANG_SIMULATE_ACC_METHOD")
SERVER_INFO_FIELDS = (
    "tp_size",
    "attention_backend",
    "kv_cache_dtype",
    "page_size",
    "context_length",
    "chunked_prefill_size",
    "mem_fraction_static",
    "speculative_algorithm",
    "speculative_num_steps",
    "max_total_num_tokens",
    "max_running_requests",
)


def http_get(url: str) -> tuple[int, bytes]:
    with urlopen(url, timeout=30) as response:
        return response.status, response.read()


def find_server(port: int) -> list[Path]:
    matches = []
    for cmdline_path in Path("/proc").glob("[0-9]*/cmdline"):
        try:
            cmdline = cmdline_path.read_bytes().replace(b"\0", b" ").decode(errors="replace")
        except OSError:
            continue
        if "sglang.launch_server" in cmdline and f"--port {port}" in cmdline:
            matches.append(cmdline_path.parent)
    return matches


def read_environ(proc_dir: Path) -> dict[str, str]:
    raw = (proc_dir / "environ").read_bytes().split(b"\0")
    pairs = (item.decode(errors="replace").split("=", 1) for item in raw if b"=" in item)
    return {key: value for key, value in pairs}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=("mtp-on", "mtp-off"), required=True)
    parser.add_argument("--url", default="http://127.0.0.1:30001")
    parser.add_argument("--port", type=int, default=None, help="server port; defaults to the port in --url")
    parser.add_argument("--skip-proc", action="store_true", help="only check HTTP; use when /proc of the server is not visible")
    args = parser.parse_args()
    base = args.url.rstrip("/")
    port = args.port or int(base.rsplit(":", 1)[-1])
    failures: list[str] = []

    try:
        status, body = http_get(f"{base}/v1/models")
    except URLError as error:
        raise SystemExit(f"FAIL /v1/models unreachable: {error}")
    if status != 200:
        failures.append(f"/v1/models HTTP {status}")
    else:
        ids = [row.get("id") for row in json.loads(body).get("data", [])]
        print(f"models={ids}")

    if not args.skip_proc:
        servers = find_server(port)
        if len(servers) != 1:
            failures.append(f"expected one sglang.launch_server on port {port}, found {len(servers)}")
        else:
            proc_dir = servers[0]
            cmdline = (proc_dir / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
            expected_flags = SHARED_FLAGS + (SPECULATIVE_FLAGS if args.mode == "mtp-on" else ())
            for flag in expected_flags:
                if flag not in cmdline:
                    failures.append(f"missing flag: {flag}")
            if args.mode == "mtp-off":
                for flag in SPECULATIVE_FLAGS:
                    if flag.split()[0] in cmdline:
                        failures.append(f"speculative flag present in mtp-off mode: {flag.split()[0]}")
            environ = read_environ(proc_dir)
            expected_env = dict(SHARED_ENV)
            if args.mode == "mtp-on":
                expected_env.update(MTP_ON_ENV)
            for key, value in expected_env.items():
                if environ.get(key) != value:
                    failures.append(f"env {key}={environ.get(key)!r}, expected {value!r}")
            for key in FORBIDDEN_ENV:
                if key in environ:
                    failures.append(f"forbidden env present: {key}={environ[key]!r}")
            print(f"server_pid={proc_dir.name}")

    try:
        status, body = http_get(f"{base}/server_info")
        info = json.loads(body) if status == 200 else {}
    except (URLError, json.JSONDecodeError):
        info = {}
    for field in SERVER_INFO_FIELDS:
        print(f"server_info.{field}={info.get(field, 'NOT_AVAILABLE')}")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}", file=sys.stderr)
        raise SystemExit(1)
    print(f"SWEBENCH_RUNTIME_CONTRACT=PASS mode={args.mode} port={port}")


if __name__ == "__main__":
    main()
