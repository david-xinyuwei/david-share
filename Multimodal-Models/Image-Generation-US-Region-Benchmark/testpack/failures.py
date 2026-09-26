"""Show failed samples and their HTTP attempts (status, error text, request ids). Usage: python failures.py runs/<tag>"""
import json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
run = Path(sys.argv[1]).resolve()
d = json.loads((run / "5way_v2_results.json").read_text(encoding="utf-8"))
bad = [r for r in d.get("raw_data", []) if not r["ok"]]
print(f"failed samples: {len(bad)} / {len(d.get('raw_data', []))}")
attempts = [json.loads(l) for l in (run / "attempts.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
for r in bad:
    sid = f"{r['group']}-r{r['round']}-p{r['prompt_idx']:02d}"
    print(f"\n== {sid}  attempts={r['attempt_count']} logical={r['logical_request_seconds']:.0f}s  prompt='{r['prompt_short']}'")
    for a in [a for a in attempts if a.get("sample_id") == sid]:
        print(f"   a{a['attempt']} http={a.get('http_status')} {a.get('request_seconds', 0):.1f}s ok={a['ok']} "
              f"err={str(a.get('error') or a.get('exception_type') or '')[:300]} ids={a.get('headers', {}).get('apim-request-id', '')}")
