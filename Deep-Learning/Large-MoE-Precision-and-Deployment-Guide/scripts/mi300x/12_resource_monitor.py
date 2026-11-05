#!/usr/bin/env python3
"""Record timestamped native GPU and host counters during a serving run."""
import argparse
import datetime
import json
import signal
import subprocess
import threading
import time
from pathlib import Path


def host_counters():
    cpu = [int(value) for value in Path("/proc/stat").read_text().splitlines()[0].split()[1:9]]
    memory = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, value = line.split(":", 1)
        if key in ("MemTotal", "MemAvailable"):
            memory[key] = int(value.split()[0]) * 1024
    network = {}
    for device in Path("/sys/class/net").iterdir():
        if device.name == "lo":
            continue
        counters = {}
        for counter in ("rx_bytes", "tx_bytes"):
            path = device / "statistics" / counter
            if path.exists():
                counters[counter] = int(path.read_text())
        network[device.name] = counters
    infiniband = {}
    for port in Path("/sys/class/infiniband").glob("*/ports/*"):
        counters = {}
        for counter in ("port_rcv_data", "port_xmit_data"):
            path = port / "counters" / counter
            if path.exists():
                counters[counter + "_bytes"] = int(path.read_text()) * 4
        infiniband[str(port.relative_to("/sys/class/infiniband"))] = counters
    return {"cpu_ticks": cpu, "memory_bytes": memory, "network_bytes": network, "infiniband_bytes": infiniband}


def sample(previous=None):
    started = time.time()
    result = subprocess.run(
        ["rocm-smi", "--showuse", "--showmemuse", "--showmeminfo", "vram", "--showpower", "--json"],
        capture_output=True, text=True, timeout=20, check=True,
    )
    host = host_counters()
    cpu_percent = None
    if previous is not None:
        current_ticks = host["cpu_ticks"]
        previous_ticks = previous["host"]["cpu_ticks"]
        total = sum(current_ticks) - sum(previous_ticks)
        idle = sum(current_ticks[3:5]) - sum(previous_ticks[3:5])
        if total > 0:
            cpu_percent = 100 * (total - idle) / total
    return {"unix_s": started, "utc": datetime.datetime.fromtimestamp(started, datetime.timezone.utc).isoformat(),
            "sample_seconds": time.time() - started, "gpu_native": json.loads(result.stdout),
            "host": host, "host_cpu_percent": cpu_percent}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--samples", type=int, default=0)
    parser.add_argument("--stop-file", type=Path)
    args = parser.parse_args()
    if args.interval <= 0 or args.samples < 0:
        parser.error("interval must be positive and samples non-negative")
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    previous = None
    count = 0
    with args.output.open("x", encoding="utf-8") as output:
        while not stop.is_set() and not (args.stop_file and args.stop_file.exists()):
            started = time.monotonic()
            record = sample(previous)
            output.write(json.dumps(record) + "\n")
            output.flush()
            previous = record
            count += 1
            if args.samples and count >= args.samples:
                break
            stop.wait(max(0.0, args.interval - (time.monotonic() - started)))
    print(json.dumps({"monitor": "COMPLETE", "samples": count, "output": str(args.output)}), flush=True)


if __name__ == "__main__":
    main()