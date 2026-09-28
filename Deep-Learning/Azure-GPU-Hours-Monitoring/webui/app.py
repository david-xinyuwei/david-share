"""GPU-hours dashboard and JSON API.

Reads GpuMetrics_CL / Heartbeat from Log Analytics using the app's managed identity
(ManagedIdentityCredential on App Service, AzureCliCredential when run locally) and
serves a single-page dashboard plus a JSON API (/api/data) for platform integration.
Access is protected by a shared access code (HTTP Basic, password = ACCESS_CODE).

Environment:
  WORKSPACE_ID   Log Analytics workspace GUID (required)
  ACCESS_CODE    shared access code; empty disables auth (local dev only)
  CACHE_SECONDS  per-(range, idle) response cache, default 60
  TZ_HOURS       UTC offset for hourly/daily buckets, default 8 (Asia/Shanghai)
  PORT           local dev port, default 8000
"""
import hmac
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from azure.identity import AzureCliCredential, ManagedIdentityCredential
from azure.monitor.query import LogsQueryClient, LogsQueryStatus
from flask import Flask, Response, jsonify, request, send_from_directory

WORKSPACE_ID = os.environ.get("WORKSPACE_ID", "")
ACCESS_CODE = os.environ.get("ACCESS_CODE", "")
CACHE_SECONDS = int(os.environ.get("CACHE_SECONDS", "60"))
TZ_HOURS = int(os.environ.get("TZ_HOURS", "8"))  # UTC offset for hourly / daily buckets (8 = Beijing)

if not WORKSPACE_ID:
    raise SystemExit("WORKSPACE_ID environment variable is required (Log Analytics workspace GUID)")

RANGES = {"1h": timedelta(hours=1), "6h": timedelta(hours=6), "24h": timedelta(days=1),
          "7d": timedelta(days=7), "30d": timedelta(days=30)}

class CachedCredential:
    """Thread-safe token cache so parallel queries don't each fetch a token."""

    def __init__(self, inner):
        self._inner = inner
        self._lock = threading.Lock()
        self._tokens = {}

    def _get(self, scopes, fetch):
        key = tuple(scopes)
        with self._lock:
            tok = self._tokens.get(key)
            if tok is None or tok.expires_on - time.time() < 300:
                tok = fetch()
                self._tokens[key] = tok
            return tok

    def get_token(self, *scopes, **kwargs):
        return self._get(scopes, lambda: self._inner.get_token(*scopes, **kwargs))

    def get_token_info(self, *scopes, options=None):
        return self._get(("info",) + scopes, lambda: self._inner.get_token_info(*scopes, options=options))


def make_credential():
    # App Service / Container Apps expose IDENTITY_ENDPOINT when a managed identity is enabled.
    if os.environ.get("IDENTITY_ENDPOINT") or os.environ.get("MSI_ENDPOINT"):
        return ManagedIdentityCredential()
    return AzureCliCredential(process_timeout=60)


app = Flask(__name__, static_folder="static")
client = LogsQueryClient(CachedCredential(make_credential()))
_cache: dict = {}
_lock = threading.Lock()


# ---------------------------------------------------------------- auth
@app.before_request
def require_code():
    if not ACCESS_CODE or request.path == "/healthz":
        return None
    auth = request.authorization
    if auth and auth.password and hmac.compare_digest(auth.password, ACCESS_CODE):
        return None
    return Response("需要访问码 / Access code required", 401,
                    {"WWW-Authenticate": 'Basic realm="GPU Hours", charset="UTF-8"'})


# ---------------------------------------------------------------- KQL
def base(t0: str) -> str:
    return f"""let t0 = {t0};
let gpu = GpuMetrics_CL | where TimeGenerated > t0;
let gpuCount = gpu | summarize Gpus = dcount(GpuId) by Computer;
"""


def q_per_vm(t0, idle):
    return base(t0) + f"""let alloc = Heartbeat
| where TimeGenerated > t0 and Computer in ((gpuCount | project Computer))
| summarize RunMinutes = dcount(bin(TimeGenerated, 1m)) by Computer
| join kind=inner gpuCount on Computer
| extend Alloc = RunMinutes * Gpus / 60.0;
let used = gpu
| summarize Busy = countif(ProcCount > 0 or GpuUtil >= {idle}) / 60.0,
            Eff = sum(coalesce(SmActive, 0.0)) / 60.0,
            VmSize = take_any(VmSize), GpuName = take_any(GpuName) by Computer;
alloc | join kind=leftouter used on Computer
| project Computer, VmSize, GpuName, Gpus, RunHours = RunMinutes / 60.0, Alloc,
          Busy = coalesce(Busy, 0.0), Eff = coalesce(Eff, 0.0)
| extend Idle = max_of(Alloc - Busy, 0.0), UtilPct = iff(Alloc > 0, 100.0 * Eff / Alloc, 0.0)
| order by Alloc desc"""


def q_bucketed(t0, idle, bucket_expr):
    # bucket_expr uses TimeGenerated shifted to Beijing time; label returned as string.
    return base(t0) + f"""let alloc = Heartbeat
| where TimeGenerated > t0 and Computer in ((gpuCount | project Computer))
| extend B = {bucket_expr}
| summarize RunMinutes = dcount(bin(TimeGenerated, 1m)) by Computer, B
| join kind=inner gpuCount on Computer
| summarize Alloc = sum(RunMinutes * Gpus) / 60.0 by B;
let used = gpu
| extend B = {bucket_expr}
| summarize Busy = countif(ProcCount > 0 or GpuUtil >= {idle}) / 60.0,
            Eff = sum(coalesce(SmActive, 0.0)) / 60.0 by B;
alloc | join kind=leftouter used on B
| project B, Alloc, Busy = coalesce(Busy, 0.0), Eff = coalesce(Eff, 0.0)
| extend Idle = max_of(Alloc - Busy, 0.0), UtilPct = iff(Alloc > 0, 100.0 * Eff / Alloc, 0.0)
| order by B asc"""


def q_series(t0, grain_min):
    return base(t0) + f"""gpu
| summarize SM = avg(SmActive) * 100, Util = avg(GpuUtil), Tensor = avg(TensorActive) * 100,
            MemGB = avg(FbUsedMiB) / 1024.0, PowerW = avg(PowerW)
          by T = bin(TimeGenerated, {grain_min}m), Gpu = strcat(Computer, '/GPU', tostring(GpuId))
| order by T asc"""


def q_users(t0):
    return base(t0) + """gpu
| where isnotempty(Users)
| mv-expand User = split(Users, ',') to typeof(string)
| summarize Busy = count() / 60.0, Eff = sum(coalesce(SmActive, 0.0)) / 60.0,
            AvgSm = 100.0 * avg(SmActive), PeakMemGB = max(FbUsedMiB) / 1024.0,
            Processes = strcat_array(make_set(Processes, 10), ',')
          by User, Computer
| order by Busy desc"""


def q_latest():
    return """GpuMetrics_CL
| where TimeGenerated > ago(15m)
| summarize arg_max(TimeGenerated, *) by Computer, GpuId
| project TimeGenerated, Computer, VmSize, GpuId, GpuName, GpuUtil, SmPct = SmActive * 100,
          MemGB = FbUsedMiB / 1024.0, PowerW, TempC, Users, Processes
| order by Computer asc, GpuId asc"""


def q_idle(idle):
    return f"""GpuMetrics_CL
| where TimeGenerated > ago(60m)
| summarize Minutes = count(), BusyMinutes = countif(ProcCount > 0 or GpuUtil >= {idle}),
            LastSeen = max(TimeGenerated), VmSize = take_any(VmSize) by Computer, GpuId
| where Minutes >= 30 and BusyMinutes == 0
| project Computer, GpuId, VmSize, Minutes, LastSeen"""


def run(query: str, span: timedelta):
    res = client.query_workspace(WORKSPACE_ID, query, timespan=span + timedelta(hours=1))
    if res.status != LogsQueryStatus.SUCCESS:
        raise RuntimeError(getattr(res, "partial_error", "query failed"))
    t = res.tables[0]
    out = []
    for row in t.rows:
        d = {}
        for c, v in zip(t.columns, row):
            if isinstance(v, datetime):
                v = v.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            elif isinstance(v, float):
                v = round(v, 3)
            d[c] = v
        out.append(d)
    return out


def collect(range_key: str, idle: int):
    span = RANGES[range_key]
    t0 = f"ago({int(span.total_seconds())}s)"
    grain = max(1, int(span.total_seconds() / 60 / 720))  # <= ~720 points per series
    shift = f"TimeGenerated + {TZ_HOURS}h"
    hour_b = f"format_datetime(bin({shift}, 1h), 'MM-dd HH:mm')"
    day_b = f"format_datetime(startofday({shift}), 'yyyy-MM-dd')"
    jobs = {
        "perVm": (q_per_vm(t0, idle), span),
        "hourly": (q_bucketed(t0, idle, hour_b), span),
        "daily": (q_bucketed(t0, idle, day_b), span),
        "series": (q_series(t0, grain), span),
        "users": (q_users(t0), span),
        "latest": (q_latest(), timedelta(minutes=15)),
        "idleNow": (q_idle(idle), timedelta(hours=1)),
    }
    with ThreadPoolExecutor(max_workers=len(jobs)) as ex:
        futs = {k: ex.submit(run, q, s) for k, (q, s) in jobs.items()}
        data = {k: f.result() for k, f in futs.items()}
    vms = data["perVm"]
    alloc = sum(v["Alloc"] for v in vms)
    busy = sum(v["Busy"] for v in vms)
    eff = sum(v["Eff"] for v in vms)
    data["summary"] = {
        "Alloc": round(alloc, 3), "Busy": round(busy, 3), "Eff": round(eff, 3),
        "Idle": round(max(alloc - busy, 0), 3),
        "UtilPct": round(100 * eff / alloc, 1) if alloc else 0.0,
        "Vms": len(vms), "Gpus": sum(v["Gpus"] for v in vms),
    }
    data["meta"] = {"range": range_key, "idle": idle, "grainMin": grain,
                    "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    return data


# ---------------------------------------------------------------- routes
@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/healthz")
def healthz():
    return "ok"


@app.get("/api/data")
def api_data():
    rk = request.args.get("range", "24h")
    if rk not in RANGES:
        return jsonify(error="invalid range"), 400
    try:
        idle = int(request.args.get("idle", "5"))
    except ValueError:
        return jsonify(error="invalid idle"), 400
    idle = min(max(idle, 0), 100)
    key = (rk, idle)
    with _lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < CACHE_SECONDS:
            return jsonify(hit[1])
    try:
        data = collect(rk, idle)
    except Exception as e:  # noqa: BLE001
        app.logger.exception("query failed")
        return jsonify(error=f"query failed: {type(e).__name__}"), 502
    with _lock:
        _cache[key] = (time.time(), data)
    return jsonify(data)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "8000")), debug=False)
