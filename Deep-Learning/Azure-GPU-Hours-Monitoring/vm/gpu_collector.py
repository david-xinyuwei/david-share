#!/usr/bin/env python3
"""DCGM -> JSONL collector for Azure Monitor Agent (Custom JSON Logs).

Streams `dcgmi dmon` samples, averages them per GPU per minute and appends one
JSON line per GPU per minute to /var/log/gpumon/gpu_metrics_YYYYMMDD.json.
AMA picks up the file and ingests it into the GpuMetrics_CL table.
"""
import datetime as dt
import glob
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request

LOG_DIR = os.environ.get("GPUMON_LOG_DIR", "/var/log/gpumon")
SAMPLE_MS = int(os.environ.get("GPUMON_SAMPLE_MS", "10000"))
KEEP_DAYS = int(os.environ.get("GPUMON_KEEP_DAYS", "3"))

# DCGM field id -> output key
FIELDS = [
    (203, "GpuUtil"),        # DCGM_FI_DEV_GPU_UTIL (%)
    (1001, "GrActive"),      # DCGM_FI_PROF_GR_ENGINE_ACTIVE (0-1)
    (1002, "SmActive"),      # DCGM_FI_PROF_SM_ACTIVE (0-1)
    (1004, "TensorActive"),  # DCGM_FI_PROF_PIPE_TENSOR_ACTIVE (0-1)
    (1005, "DramActive"),    # DCGM_FI_PROF_DRAM_ACTIVE (0-1)
    (252, "FbUsedMiB"),      # DCGM_FI_DEV_FB_USED
    (250, "FbTotalMiB"),     # DCGM_FI_DEV_FB_TOTAL
    (155, "PowerW"),         # DCGM_FI_DEV_POWER_USAGE
    (150, "TempC"),          # DCGM_FI_DEV_GPU_TEMP
]


def utcnow():
    return dt.datetime.now(dt.timezone.utc)


def log(msg):
    print(f"{utcnow():%Y-%m-%dT%H:%M:%SZ} {msg}", file=sys.stderr, flush=True)


def imds():
    try:
        req = urllib.request.Request(
            "http://169.254.169.254/metadata/instance/compute?api-version=2021-02-01",
            headers={"Metadata": "true"})
        with urllib.request.urlopen(req, timeout=5) as r:
            c = json.load(r)
        return {
            "VmName": c.get("name", ""),
            "VmSize": c.get("vmSize", ""),
            "VmResourceId": c.get("resourceId", ""),
            "Tags": c.get("tags", ""),
        }
    except Exception as e:  # noqa: BLE001
        log(f"IMDS unavailable: {e}")
        return {"VmName": os.uname().nodename, "VmSize": "", "VmResourceId": "", "Tags": ""}


def gpu_inventory():
    out = subprocess.run(
        ["nvidia-smi", "--query-gpu=index,uuid,name", "--format=csv,noheader"],
        capture_output=True, text=True, encoding="utf-8", timeout=30).stdout
    inv = {}
    for line in out.strip().splitlines():
        idx, uuid, name = [x.strip() for x in line.split(",", 2)]
        inv[int(idx)] = {"GpuUuid": uuid, "GpuName": name}
    return inv


def gpu_processes():
    """Return {gpu_uuid: [(user, proc_name), ...]}."""
    import pwd  # Unix only; imported here so the module also loads on Windows for tests

    res = {}
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=gpu_uuid,pid",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, encoding="utf-8", timeout=30).stdout
    except Exception:  # noqa: BLE001
        return res
    for line in out.strip().splitlines():
        parts = [x.strip() for x in line.split(",")]
        if len(parts) < 2 or not parts[1].isdigit():
            continue
        uuid, pid = parts[0], int(parts[1])
        try:
            user = pwd.getpwuid(os.stat(f"/proc/{pid}").st_uid).pw_name
        except Exception:  # noqa: BLE001
            user = "unknown"
        try:
            with open(f"/proc/{pid}/comm") as f:
                comm = f.read().strip()
        except Exception:  # noqa: BLE001
            comm = "unknown"
        res.setdefault(uuid, []).append((user, comm))
    return res


def parse_val(v):
    if v in ("N/A", "-", ""):
        return None
    try:
        return float(v)
    except ValueError:
        return None


class Aggregator:
    def __init__(self):
        self.lock = threading.Lock()
        self.buf = {}  # gpu_id -> {key: [values]}

    def add(self, gpu_id, values):
        with self.lock:
            b = self.buf.setdefault(gpu_id, {k: [] for _, k in FIELDS})
            for (_, key), v in zip(FIELDS, values):
                if v is not None:
                    b[key].append(v)

    def drain(self):
        with self.lock:
            data, self.buf = self.buf, {}
        return data


def parse_dmon_line(line):
    """Return (gpu_id, [values...]) for a `dcgmi dmon` data line, or None for headers/other lines.

    Data lines look like `GPU 0     100   0.966   ...`; header lines start with `#Entity` or `ID`.
    """
    t = line.split()
    if len(t) >= 2 + len(FIELDS) and t[0] == "GPU" and t[1].isdigit():
        return int(t[1]), [parse_val(x) for x in t[2:2 + len(FIELDS)]]
    return None


def dmon_reader(agg):
    field_ids = ",".join(str(f) for f, _ in FIELDS)
    cmd = ["stdbuf", "-oL", "dcgmi", "dmon", "-e", field_ids, "-d", str(SAMPLE_MS)]
    while True:
        log(f"starting: {' '.join(cmd)}")
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8")
            for line in p.stdout:
                parsed = parse_dmon_line(line)
                if parsed:
                    agg.add(*parsed)
            p.wait()
            log(f"dcgmi exited with {p.returncode}")
        except Exception as e:  # noqa: BLE001
            log(f"dmon error: {e}")
        time.sleep(5)


def cleanup_old():
    cutoff = time.time() - KEEP_DAYS * 86400
    for f in glob.glob(os.path.join(LOG_DIR, "gpu_metrics_*.json")):
        try:
            if os.path.getmtime(f) < cutoff:
                os.remove(f)
        except OSError:
            pass


def mean(xs):
    return round(sum(xs) / len(xs), 4) if xs else None


def build_record(ts, meta, gpu_id, gpu_info, samples, procs):
    """One JSON line for one GPU and one minute.

    ts: aware datetime of the minute start; meta: IMDS fields; gpu_info: {GpuUuid, GpuName};
    samples: {field_key: [values]} for that minute; procs: [(user, process_name), ...] on that GPU.
    The keys must match the stream declared in azure/dcr.json (tests/test_contracts.py enforces it).
    """
    return {
        "TimeGenerated": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        **meta,
        "GpuId": gpu_id,
        **gpu_info,
        "Samples": max((len(v) for v in samples.values()), default=0),
        **{k: mean(samples.get(k, [])) for _, k in FIELDS},
        "ProcCount": len(procs),
        "Users": ",".join(sorted({u for u, _ in procs})),
        "Processes": ",".join(sorted({c for _, c in procs})),
    }


def main():
    os.makedirs(LOG_DIR, exist_ok=True)
    meta = imds()
    inv = gpu_inventory()
    log(f"meta={meta} gpus={inv}")
    agg = Aggregator()
    threading.Thread(target=dmon_reader, args=(agg,), daemon=True).start()

    while True:
        time.sleep(60 - (time.time() % 60))  # align to minute boundary
        # timestamp = start of the minute that just finished
        ts = dt.datetime.fromtimestamp(round(time.time() / 60) * 60 - 60, dt.timezone.utc)
        data = agg.drain()
        if not data:
            continue
        procs = gpu_processes()
        path = os.path.join(LOG_DIR, f"gpu_metrics_{ts:%Y%m%d}.json")
        with open(path, "a", encoding="utf-8") as f:
            for gpu_id in sorted(data):
                gi = inv.get(gpu_id, {"GpuUuid": "", "GpuName": ""})
                rec = build_record(ts, meta, gpu_id, gi, data[gpu_id], procs.get(gi["GpuUuid"], []))
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        cleanup_old()


if __name__ == "__main__":
    main()
