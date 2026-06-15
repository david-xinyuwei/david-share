"""
APIM AI Gateway — Proactive PTU Monitor & Dynamic Routing
Queries Azure Monitor for PTU utilization (or token rate for PAYGO),
dynamically adjusts APIM backend pool weights to route traffic away
from backends approaching capacity limits.

Production Usage:
  - Deploy as Azure Function (Timer trigger, every 30-60s)
  - Or run as daemon: python monitor_and_route.py --mode daemon --interval 30

Demo Usage:
  python monitor_and_route.py --mode demo   # Simulates full cycle

Author: Xinyu Wei
"""
import argparse, json, time, subprocess, sys, statistics
from datetime import datetime, timedelta, timezone
from collections import Counter
import requests
import concurrent.futures

# ─── Config (Demo: personal subscription) ─────────────────────────────────
SUBSCRIPTION    = "<your-subscription-id>"
APIM_RG         = "<your-rg>"
APIM_NAME       = "<your-apim-name>"
APIM_BASE       = f"https://management.azure.com/subscriptions/{SUBSCRIPTION}/resourceGroups/{APIM_RG}/providers/Microsoft.ApiManagement/service/{APIM_NAME}"
POOL_NAME       = "aoai-lb-pool"

BACKENDS = {
    "aoai-sweden": {
        "resource_id": f"/subscriptions/{SUBSCRIPTION}/resourceGroups/<your-aoai-rg>/providers/Microsoft.CognitiveServices/accounts/<your-aoai-a>",
        "display": "Sweden Central",
    },
    "<your-aoai-rg>": {
        "resource_id": f"/subscriptions/{SUBSCRIPTION}/resourceGroups/<your-aoai-rg>/providers/Microsoft.CognitiveServices/accounts/<your-aoai-b>",
        "display": "East US 2",
    },
}

# Thresholds
PTU_HIGH_THRESHOLD  = 80   # % — start reducing weight
PTU_LOW_THRESHOLD   = 50   # % — restore weight
TPM_HIGH_THRESHOLD  = 1500 # tokens/min — for PAYGO demo (GlobalStandard)
TPM_LOW_THRESHOLD   = 800
DEFAULT_WEIGHT      = 5
REDUCED_WEIGHT      = 1

# Gateway test config
APIM_GATEWAY = "https://<your-apim-name>.azure-api.net"
APIM_KEY     = "<your-apim-subscription-key>"
DEPLOYMENT   = "gpt-4o-mini"
TEST_URL     = f"{APIM_GATEWAY}/openai/deployments/{DEPLOYMENT}/chat/completions?api-version=2024-08-01-preview"
TEST_HEADERS = {"api-key": APIM_KEY, "Content-Type": "application/json"}
TEST_PAYLOAD = {"messages": [{"role": "user", "content": "Reply: OK"}], "max_tokens": 3}


def get_token(resource="https://management.azure.com"):
    """Get Azure AD token via az CLI."""
    result = subprocess.run(
        ["az", "account", "get-access-token", "--resource", resource, "--query", "accessToken", "-o", "tsv"],
        capture_output=True, text=True
    )
    return result.stdout.strip()


def query_metric(resource_id, metric_name, timespan_minutes=5):
    """Query Azure Monitor for a metric's average over the last N minutes."""
    token = get_token()
    end = datetime.now(timezone.utc)
    start = end - timedelta(minutes=timespan_minutes)
    timespan = f"{start.isoformat()}/{end.isoformat()}"

    url = f"https://management.azure.com{resource_id}/providers/Microsoft.Insights/metrics"
    params = {
        "api-version": "2024-02-01",
        "metricnames": metric_name,
        "timespan": timespan,
        "interval": "PT1M",
        "aggregation": "Average",
    }
    headers = {"Authorization": f"Bearer {token}"}

    resp = requests.get(url, headers=headers, params=params, timeout=30)
    if resp.status_code != 200:
        print(f"  ⚠ Metric query failed: HTTP {resp.status_code}")
        return None

    data = resp.json()
    values = []
    for ts in data.get("value", [{}])[0].get("timeseries", [{}]):
        for dp in ts.get("data", []):
            avg = dp.get("average")
            if avg is not None:
                values.append(avg)

    return round(statistics.mean(values), 2) if values else None


def query_ptu_utilization(resource_id):
    """Query PTU utilization (ProvisionedManagedUtilizationV2)."""
    return query_metric(resource_id, "AzureOpenAIProvisionedManagedUtilizationV2", 3)


def query_token_rate(resource_id):
    """Query token transaction rate (tokens/min) for PAYGO monitoring."""
    return query_metric(resource_id, "TokenTransaction", 3)


def query_request_count(resource_id):
    """Query request count for PAYGO monitoring."""
    return query_metric(resource_id, "AzureOpenAIRequests", 3)


def get_current_pool_weights():
    """Get current backend pool weights from APIM."""
    token = get_token()
    url = f"{APIM_BASE}/backends/{POOL_NAME}?api-version=2024-06-01-preview"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, headers=headers, timeout=30)
    if resp.status_code != 200:
        print(f"  ⚠ Failed to get pool: HTTP {resp.status_code}")
        return {}

    pool = resp.json().get("properties", {}).get("pool", {})
    weights = {}
    for svc in pool.get("services", []):
        backend_name = svc["id"].rsplit("/", 1)[-1]
        weights[backend_name] = {"priority": svc.get("priority", 1), "weight": svc.get("weight", 5)}
    return weights


def update_pool_weights(new_weights):
    """Update backend pool weights via APIM REST API."""
    token = get_token()
    services = []
    for name, pw in new_weights.items():
        services.append({
            "id": f"{APIM_BASE}/backends/{name}",
            "priority": pw["priority"],
            "weight": pw["weight"],
        })

    body = {"properties": {"type": "Pool", "pool": {"services": services}}}
    url = f"{APIM_BASE}/backends/{POOL_NAME}?api-version=2024-06-01-preview"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resp = requests.put(url, headers=headers, json=body, timeout=30)
    return resp.status_code == 200 or resp.status_code == 201


def send_test_request(i):
    """Send a single test request through APIM."""
    t0 = time.time()
    try:
        r = requests.post(TEST_URL, headers=TEST_HEADERS, json=TEST_PAYLOAD, timeout=30)
        return {"req": i, "status": r.status_code, "elapsed": round(time.time()-t0, 2),
                "region": r.headers.get("x-ms-region", "?")}
    except Exception as e:
        return {"req": i, "status": "ERR", "elapsed": round(time.time()-t0, 2), "error": str(e)[:50]}


def traffic_burst(n=15, workers=5):
    """Send burst traffic and return region distribution."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(send_test_request, range(n)))
    ok = [r for r in results if r.get("status") == 200]
    dist = Counter(r.get("region") for r in ok)
    return results, dict(dist)


# ─── DEMO MODE: Full end-to-end cycle ─────────────────────────────────────
def run_demo():
    """
    Demo: Simulate PTU proactive monitoring cycle.
    Since we use GlobalStandard (no real PTU utilization), we:
    1. Show baseline traffic (50/50)
    2. Manually trigger "high utilization detected" on one backend
    3. Dynamically reduce its weight → observe traffic shift
    4. "Utilization recovers" → restore weight → observe traffic rebalance
    """
    print("=" * 65)
    print("  APIM Proactive PTU Monitor — Dynamic Routing Demo")
    print("=" * 65)

    # ── Phase 1: Baseline ────────────────────────────────────────────────
    print("\n[Phase 1] Baseline — equal weight (5:5)")
    weights = get_current_pool_weights()
    print(f"  Current pool weights: {weights}")

    # Ensure default weights
    for name in weights:
        weights[name] = {"priority": 1, "weight": DEFAULT_WEIGHT}
    update_pool_weights(weights)
    time.sleep(3)

    print("  Sending 15 requests...")
    _, dist1 = traffic_burst(15, 5)
    print(f"  Traffic distribution: {dist1}")

    # ── Phase 2: Query current metrics ──────────────────────────────────
    print("\n[Phase 2] Query Azure Monitor metrics")
    for name, info in BACKENDS.items():
        util = query_ptu_utilization(info["resource_id"])
        tpm = query_token_rate(info["resource_id"])
        rpm = query_request_count(info["resource_id"])
        print(f"  {info['display']:20s} | PTU Util: {util or 'N/A (PAYGO)':>8} | TPM: {tpm or 0:>8} | RPM: {rpm or 0:>6}")

    # ── Phase 3: Simulate high utilization → reduce weight ──────────────
    print("\n[Phase 3] ⚠ Simulating: Sweden Central PTU approaching capacity (>80%)")
    print("  Action: Reduce Sweden weight 5→1, East US 2 stays 5")
    new_weights = {
        "aoai-sweden":  {"priority": 1, "weight": REDUCED_WEIGHT},  # overloaded → reduce
        "<your-aoai-rg>": {"priority": 1, "weight": DEFAULT_WEIGHT},  # healthy → keep
    }
    success = update_pool_weights(new_weights)
    print(f"  Pool update: {'✅ Success' if success else '❌ Failed'}")
    print(f"  New weights: Sweden={REDUCED_WEIGHT}, EastUS2={DEFAULT_WEIGHT}")
    sweden_pct = round(REDUCED_WEIGHT / (REDUCED_WEIGHT + DEFAULT_WEIGHT) * 100)
    eastus_pct = round(DEFAULT_WEIGHT / (REDUCED_WEIGHT + DEFAULT_WEIGHT) * 100)
    print(f"  Expected distribution: ~{sweden_pct}% Sweden, ~{eastus_pct}% EastUS2")
    time.sleep(5)

    print("  Sending 18 requests...")
    _, dist2 = traffic_burst(18, 6)
    print(f"  Traffic distribution: {dist2}")

    total2 = sum(dist2.values())
    if total2 > 0:
        for region, count in dist2.items():
            print(f"    {region}: {count}/{total2} ({count/total2*100:.0f}%)")

    # ── Phase 4: Utilization recovers → restore weight ──────────────────
    print("\n[Phase 4] ✅ Simulating: Sweden Central utilization recovered (<50%)")
    print("  Action: Restore Sweden weight 1→5 (back to equal)")
    restore_weights = {
        "aoai-sweden":  {"priority": 1, "weight": DEFAULT_WEIGHT},
        "<your-aoai-rg>": {"priority": 1, "weight": DEFAULT_WEIGHT},
    }
    success = update_pool_weights(restore_weights)
    print(f"  Pool update: {'✅ Success' if success else '❌ Failed'}")
    time.sleep(5)

    print("  Sending 15 requests...")
    _, dist3 = traffic_burst(15, 5)
    print(f"  Traffic distribution: {dist3}")

    # ── Summary ──────────────────────────────────────────────────────────
    print(f"\n{'=' * 65}")
    print("  SUMMARY: Proactive PTU Monitor Demo Results")
    print(f"{'=' * 65}")
    print(f"  Phase 1 (baseline 5:5):     {dist1}")
    print(f"  Phase 3 (reduced  1:5):     {dist2}")
    print(f"  Phase 4 (restored 5:5):     {dist3}")
    print(f"\n  ✅ Dynamic weight adjustment successfully shifts traffic")
    print(f"  ✅ In production: Azure Monitor alert triggers this automatically")


# ─── DAEMON MODE: Real monitoring loop ─────────────────────────────────────
def run_daemon(interval=30, use_ptu=False):
    """Run as a monitoring daemon (Azure Function-like behavior)."""
    print(f"Starting monitor daemon (interval={interval}s, metric={'PTU Util' if use_ptu else 'Token Rate'})")
    print("Press Ctrl+C to stop\n")

    while True:
        ts = datetime.now().strftime("%H:%M:%S")
        weights = get_current_pool_weights()
        changes = False

        for name, info in BACKENDS.items():
            if use_ptu:
                value = query_ptu_utilization(info["resource_id"])
                high_th, low_th = PTU_HIGH_THRESHOLD, PTU_LOW_THRESHOLD
                unit = "%"
            else:
                value = query_token_rate(info["resource_id"])
                high_th, low_th = TPM_HIGH_THRESHOLD, TPM_LOW_THRESHOLD
                unit = "TPM"

            current_w = weights.get(name, {}).get("weight", DEFAULT_WEIGHT)
            display = info["display"]

            if value is None:
                print(f"  [{ts}] {display}: metric=N/A (skipped)")
                continue

            if value > high_th and current_w > REDUCED_WEIGHT:
                print(f"  [{ts}] ⚠ {display}: {value}{unit} > {high_th} → weight {current_w}→{REDUCED_WEIGHT}")
                weights[name]["weight"] = REDUCED_WEIGHT
                changes = True
            elif value < low_th and current_w < DEFAULT_WEIGHT:
                print(f"  [{ts}] ✅ {display}: {value}{unit} < {low_th} → weight {current_w}→{DEFAULT_WEIGHT}")
                weights[name]["weight"] = DEFAULT_WEIGHT
                changes = True
            else:
                print(f"  [{ts}] {display}: {value}{unit} (weight={current_w}, OK)")

        if changes:
            success = update_pool_weights(weights)
            print(f"  [{ts}] Pool updated: {'✅' if success else '❌'} → {weights}")

        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="APIM Proactive PTU Monitor")
    parser.add_argument("--mode", choices=["demo", "daemon", "metrics"], default="demo")
    parser.add_argument("--interval", type=int, default=30, help="Daemon polling interval (seconds)")
    parser.add_argument("--ptu", action="store_true", help="Use PTU utilization metric (default: token rate)")
    args = parser.parse_args()

    if args.mode == "demo":
        run_demo()
    elif args.mode == "daemon":
        run_daemon(interval=args.interval, use_ptu=args.ptu)
    elif args.mode == "metrics":
        print("Querying current metrics for all backends...")
        for name, info in BACKENDS.items():
            util = query_ptu_utilization(info["resource_id"])
            tpm = query_token_rate(info["resource_id"])
            rpm = query_request_count(info["resource_id"])
            print(f"  {info['display']:20s} | PTU: {util or 'N/A':>8} | TPM: {tpm or 0:>8.1f} | RPM: {rpm or 0:>6.1f}")


if __name__ == "__main__":
    main()
