"""Record where this client actually sits (public IP geolocation, city/region/country + ASN only) beside a run,
plus the resource regions from the run config, so the report can state the real network path. No secrets."""
import json, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

run = Path(sys.argv[1]).resolve()
out = run / "CLIENT-LOCATION.json"
rec = {"capturedAtUtc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "sources": []}
for url in ("https://ipinfo.io/json", "https://ifconfig.co/json"):
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            g = json.load(r)
        rec["sources"].append({"url": url, "city": g.get("city"), "region": g.get("region") or g.get("region_name"),
                               "country": g.get("country") or g.get("country_iso"), "asn_org": g.get("org") or g.get("asn_org"),
                               "timezone": g.get("timezone") or (g.get("time_zone"))})
    except Exception as e:
        rec["sources"].append({"url": url, "error": type(e).__name__})
rec["resources"] = {"MAI-Image-2.6": "xinyuwei-2026-eastus-img (East US, GlobalStandard)",
                    "gpt-image-2 / 2.5-flare / 2.5-sunburst": "xinyuwei-2026-resource (East US 2, GlobalStandard)"}
rec["note"] = ("GlobalStandard deployments do not pin the GPU to the resource region; timings are client->Azure front door->"
               "wherever the model is served. Resource region is a fact; GPU region is not observable from the client.")
out.write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(rec, ensure_ascii=False, indent=2))
