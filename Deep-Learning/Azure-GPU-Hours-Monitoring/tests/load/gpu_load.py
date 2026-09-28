#!/usr/bin/env python3
"""Synthetic GPU load with a known schedule, used to check how GPU-minutes are classified.

    python3 tests/load/gpu_load.py                                   # full 480 s, held 180 s, partial 300 s at 50 %
    python3 tests/load/gpu_load.py --phase full:180 --phase held:120 --phase partial:180:0.5

Phases:
  full:<s>             bf16 8192x8192 matmul back to back (SM active close to 100 %)
  held:<s>             process alive with a 20 GiB buffer allocated and no kernels (busy, not effective)
  partial:<s>:<duty>   the same matmul for <duty> of every second, sleeping the rest

Needs PyTorch with CUDA. Run it as the OS user whose GPU hours you expect to see in kql/per_user.kql.
"""
import argparse
import time

DEFAULT = ["full:480", "held:180", "partial:300:0.5"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phase", action="append", help="full:<s> | held:<s> | partial:<s>:<duty> (repeatable)")
    ap.add_argument("--hold-gib", type=float, default=20.0, help="GPU memory kept allocated for the whole run")
    args = ap.parse_args()
    import torch

    a = torch.randn(8192, 8192, device="cuda", dtype=torch.bfloat16)
    b = torch.randn(8192, 8192, device="cuda", dtype=torch.bfloat16)
    buf = torch.empty(int(args.hold_gib * 1024**3) // 2, device="cuda", dtype=torch.bfloat16)  # noqa: F841

    def run(seconds: float, duty: float = 1.0) -> None:
        end = time.time() + seconds
        while time.time() < end:
            t0 = time.time()
            while time.time() - t0 < duty:
                for _ in range(20):
                    a @ b
                torch.cuda.synchronize()
            if duty < 1.0:
                time.sleep(1.0 - duty)

    for spec in args.phase or DEFAULT:
        kind, *rest = spec.split(":")
        seconds = float(rest[0])
        print(f"{time.strftime('%H:%M:%S')} {spec}", flush=True)
        if kind == "full":
            run(seconds)
        elif kind == "held":
            time.sleep(seconds)
        elif kind == "partial":
            run(seconds, float(rest[1]))
        else:
            raise SystemExit(f"unknown phase {spec}")
    print("done", flush=True)


if __name__ == "__main__":
    main()
