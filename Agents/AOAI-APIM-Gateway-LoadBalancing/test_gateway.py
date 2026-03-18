"""
APIM AI Gateway Test Suite — Multi-Region Load Balancing
Tests: LB Distribution, Concurrency, Circuit Breaker, Rate Limit, Throughput

Usage:
  python test_gateway.py --test all
  python test_gateway.py --test lb --gateway https://your-apim.azure-api.net --key your-key

Author: Xinyu Wei
"""
import argparse, concurrent.futures, json, time, statistics, sys
from datetime import datetime
from collections import Counter
import requests

def send_request(i, url, headers, payload, timeout=30):
    t0 = time.time()
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=timeout)
        elapsed = round(time.time()-t0, 3)
        region = r.headers.get("x-ms-region","unknown")
        res = {"req":i,"status":r.status_code,"elapsed":elapsed,"region":region}
        if r.status_code == 200:
            res["content"] = r.json()["choices"][0]["message"]["content"][:40]
        else:
            res["error"] = r.text[:120]
            if r.status_code == 429:
                res["retry_after"] = r.headers.get("retry-after","N/A")
        return res
    except Exception as e:
        return {"req":i,"status":"ERR","elapsed":round(time.time()-t0,3),"error":str(e)[:80]}

def print_summary(results, title):
    ok = [r for r in results if r.get("status")==200]
    r429 = [r for r in results if r.get("status")==429]
    err = [r for r in results if r.get("status") not in (200,429,"ERR")]
    print(f"\n{'='*58}\n  {title}\n{'='*58}")
    print(f"  Total: {len(results)}  |  200: {len(ok)}  |  429: {len(r429)}  |  Other: {len(err)}")
    if ok:
        times = sorted(r["elapsed"] for r in ok)
        p50 = times[len(times)//2]
        p95 = times[int(len(times)*0.95)] if len(times)>=2 else times[-1]
        print(f"  Latency  avg={statistics.mean(times):.2f}s  P50={p50:.2f}s  P95={p95:.2f}s")
        regions = Counter(r.get("region","?") for r in ok)
        print(f"  Backends:")
        for reg, cnt in sorted(regions.items(), key=lambda x:-x[1]):
            bar = "█"*int(cnt/len(ok)*24)
            print(f"    {reg:<22} {cnt:>3} ({cnt/len(ok)*100:.0f}%) {bar}")

def test_lb(url, headers, n=20):
    print(f"\n[TEST] Load Balancing — {n} sequential requests")
    SHORT = {"messages":[{"role":"user","content":"Reply: OK"}],"max_tokens":3}
    results = []
    for i in range(n):
        r = send_request(i, url, headers, SHORT)
        print(f"  [{i+1:02d}] HTTP {r['status']}  {r['elapsed']:.2f}s  → {r.get('region','?')}")
        results.append(r); time.sleep(0.3)
    print_summary(results, f"Load Balancing ({n} requests)")
    return results

def test_concurrency(url, headers, levels=None):
    if levels is None: levels = [5, 10, 20]
    print(f"\n[TEST] High Concurrency — levels: {levels}")
    MEDIUM = {"messages":[{"role":"user","content":"What is Azure OpenAI? 2 sentences."}],"max_tokens":60}
    for c in levels:
        print(f"\n  ── C={c} ──")
        with concurrent.futures.ThreadPoolExecutor(max_workers=c) as ex:
            results = list(ex.map(lambda i: send_request(i, url, headers, MEDIUM), range(c)))
        ok = [r for r in results if r.get("status")==200]
        times = sorted(r["elapsed"] for r in ok) if ok else []
        regions = Counter(r.get("region") for r in ok)
        p50 = times[len(times)//2] if times else 0
        print(f"  Success {len(ok)}/{c}  P50={p50:.2f}s  Regions: {dict(regions)}")
        time.sleep(3)

def test_circuit(url, headers):
    print(f"\n[TEST] Circuit Breaker Failover")
    SHORT = {"messages":[{"role":"user","content":"Reply: OK"}],"max_tokens":3}
    gateway_base = url.rsplit("/openai", 1)[0]
    bad_url = f"{gateway_base}/openai/deployments/nonexistent/chat/completions{url.split('?')[1] if '?' in url else ''}"

    print("  Phase A: Baseline")
    baseline = [send_request(i, url, headers, SHORT) for i in range(8)]
    ok_b = [r for r in baseline if r.get("status")==200]
    print(f"  {len(ok_b)}/8 success  {dict(Counter(r.get('region') for r in ok_b))}")

    print("  Phase B: Error injection")
    for i in range(6):
        requests.post(bad_url, headers=headers, json=SHORT, timeout=10)

    print("  Phase C: Recovery")
    time.sleep(3)
    post = [send_request(i, url, headers, SHORT) for i in range(8)]
    ok_p = [r for r in post if r.get("status")==200]
    print(f"  {len(ok_p)}/8 success  {dict(Counter(r.get('region') for r in ok_p))}")

def test_throughput(url, headers, duration=30, rps=3):
    print(f"\n[TEST] Sustained Throughput — {duration}s @ {rps} rps")
    SHORT = {"messages":[{"role":"user","content":"Reply: OK"}],"max_tokens":3}
    results, i = [], 0
    t_end = time.time() + duration
    while time.time() < t_end:
        t0 = time.time()
        r = send_request(i, url, headers, SHORT)
        results.append(r); i += 1
        wait = 1.0/rps - (time.time()-t0)
        if wait > 0: time.sleep(wait)
    print_summary(results, f"Sustained {duration}s @ {rps}rps")

def test_ratelimit(url, headers, burst=30, workers=15):
    """Burst traffic to observe 429 from azure-openai-token-limit policy."""
    print(f"\n[TEST] Rate Limit Burst — {burst} concurrent @ {workers} workers")
    MEDIUM = {"messages":[{"role":"user","content":"Write about AI in 50 words."}],"max_tokens":100}
    def req(i):
        try:
            r = requests.post(url, headers=headers, json=MEDIUM, timeout=25)
            return {"status": r.status_code, "region": r.headers.get("x-ms-region","?"),
                    "remaining": r.headers.get("x-ratelimit-remaining-tokens","N/A"),
                    "retry_after": r.headers.get("retry-after","")}
        except: return {"status": "ERR"}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(req, range(burst)))
    ok = sum(1 for r in results if r.get("status")==200)
    r429 = sum(1 for r in results if r.get("status")==429)
    print(f"  200: {ok}  429: {r429}  other: {len(results)-ok-r429}")
    if r429:
        sample = [r.get("retry_after") for r in results if r.get("status")==429][:5]
        print(f"  retry-after samples: {sample}")

def main():
    parser = argparse.ArgumentParser(description="APIM Gateway Test Suite")
    parser.add_argument("--test", default="lb", choices=["lb","concurrency","circuit","ratelimit","throughput","all"])
    parser.add_argument("--gateway", default="https://<your-apim>.azure-api.net", help="APIM gateway URL")
    parser.add_argument("--key", default="<your-subscription-key>", help="APIM subscription key")
    parser.add_argument("--deployment", default="gpt-4o-mini", help="Deployment name")
    parser.add_argument("--api-version", default="2024-08-01-preview")
    args = parser.parse_args()

    url = f"{args.gateway}/openai/deployments/{args.deployment}/chat/completions?api-version={args.api_version}"
    headers = {"api-key": args.key, "Content-Type": "application/json"}

    print(f"APIM Gateway Test Suite\nGateway: {args.gateway}\nModel: {args.deployment}\nTime: {datetime.now():%Y-%m-%d %H:%M:%S}\n")

    if args.test in ("lb","all"):         test_lb(url, headers)
    if args.test in ("concurrency","all"):test_concurrency(url, headers)
    if args.test in ("circuit","all"):    test_circuit(url, headers)
    if args.test in ("ratelimit","all"):  test_ratelimit(url, headers)
    if args.test in ("throughput","all"): test_throughput(url, headers)

if __name__=="__main__": main()
