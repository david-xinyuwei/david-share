"""Export allowlisted run evidence from the author's verified local archive."""

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import tarfile

from analyze_results import digest_file, dump_json, require


EVENT_FIELDS = (
    "run_id", "event", "updated_utc", "phase", "stage", "completed", "total",
    "groups_completed", "groups_total", "latest_group", "latest_route",
)
TERMINAL_FIELDS = (
    "run_id", "phase", "stage", "completed", "total", "groups_completed",
    "groups_total", "remaining_groups", "error", "error_type", "updated_utc",
)
CONTRACT_FIELDS = (
    "run_id", "method", "target", "draft", "serving", "routes", "sampling",
    "quality", "serving_checks", "throughput", "stream_measurement",
)


def export(source, destination):
    archive_path = source / "evidence-final.tgz"
    projection = json.loads((destination / "data/groups.json").read_text(encoding="utf-8"))
    require(digest_file(archive_path) == projection["coverage"]["archive_sha256"], "SOURCE_ARCHIVE_CHANGED")
    source_hashes = {}
    with tarfile.open(archive_path, "r:gz") as archive:
        def read_bytes(name):
            stream = archive.extractfile(name)
            require(stream is not None, "SOURCE_MEMBER_MISSING")
            with stream:
                raw = stream.read()
            source_hashes[name] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
            return raw

        def read_json(name):
            return json.loads(read_bytes(name))

        contract = read_json("src/experiment.json")
        campaign = read_json("state/campaign.json")
        runway = read_json("state/full-runway.json")
        source_events = [json.loads(line) for line in read_bytes("logs/campaign-events.jsonl").splitlines() if line]
        events = [{key: event[key] for key in EVENT_FIELDS if key in event} for event in source_events]
        starts = [event for event in events if event["event"] == "CAMPAIGN_START"]
        require(bool(starts), "CAMPAIGN_START_MISSING")
        start = starts[-1]["updated_utc"]
        end = campaign["updated_utc"]
        duration = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()
        require(duration > 0, "INVALID_INVOCATION_CLOCK")
        groups = projection["groups"]
        require(campaign["completed"] == sum(group["completed"] for group in groups), "CAMPAIGN_COUNT_MISMATCH")
        activation = []
        for group in groups:
            original = read_json(group["source"]["member"])
            require(source_hashes[group["source"]["member"]]["sha256"] == group["source"]["sha256"], "GROUP_SOURCE_CHANGED")
            loaded = original["loaded"]
            activation.append({"group_id": group["group_id"], "route": loaded["route"],
                               "status": loaded["status"], "engine_status": original["engine"]["status"],
                               "observed_checks": sorted(key for key, value in loaded["matches"].items() if value),
                               "cold_start_contamination": original.get("cold_start_contamination"),
                               "elapsed_wall_s": original["elapsed_wall_s"]})
        example_group = next(group for group in groups if group["stage"] == "S" and group["route"] == "baseline")
        requests = read_json(f"results/{example_group['group_id']}/ordered-requests.json")
        examples = []
        for dataset in ("humaneval_plus", "math_500"):
            example = next(request for request in requests if request["dataset"] == dataset)
            examples.append({**example, "group_id": example_group["group_id"]})
        code_dir = destination / "source"
        code_dir.mkdir(exist_ok=True)
        for name in ("campaign_runner.py", "scoring.py", "stream_metrics.py"):
            (code_dir / name).write_bytes(read_bytes("src/" + name))
    closure_raw = (source / "closure.json").read_bytes()
    closure = json.loads(closure_raw)
    require(closure["run_id"] == campaign["run_id"] and closure["evidence_verified"], "CLOSURE_IDENTITY_MISMATCH")
    finalizer_raw = (source / "finalizer.log").read_bytes()
    verified = [line.split("=", 1)[1] for line in finalizer_raw.decode("utf-8").splitlines() if line.startswith("EVIDENCE_LOCAL_VERIFIED=")]
    require(bool(verified), "COLLECTION_VERIFICATION_TIME_MISSING")
    closure_time = closure["finished_utc"]
    require(datetime.fromisoformat(end) <= datetime.fromisoformat(verified[-1]) <= datetime.fromisoformat(closure_time), "CLOSURE_ORDER_INVALID")
    public = {
        "run_id": campaign["run_id"],
        "source_archive": {"sha256": digest_file(archive_path), "bytes": archive_path.stat().st_size},
        "terminal": {key: campaign[key] for key in TERMINAL_FIELDS},
        "timing": {"last_invocation_start_utc": start, "last_invocation_end_utc": end,
                   "last_invocation_elapsed_s": duration,
                   "definition": "Final campaign invocation, including restored earlier groups and nonmeasurement overhead; not total GPU allocation or sum of request latency."},
        "runway": {key: runway[key] for key in ("status", "safety_factor", "remaining_seconds", "estimated_seconds_with_safety", "server_startup_seconds", "collection_reserve_seconds", "scope_reduced")},
        "closure": {"evidence_verified_utc": verified[-1], "power_decision": closure["power_decision"],
                    "power_verified_utc": closure_time, "evidence_verified": closure["evidence_verified"],
                    "source_sha256": hashlib.sha256(closure_raw).hexdigest()},
        "stages": {stage: {"completed_groups": sum(group["stage"] == stage for group in groups),
                            "completed_responses": sum(group["completed"] for group in groups if group["stage"] == stage),
                            "measured_group_wall_s": sum(group["elapsed_wall_s"] for group in groups if group["stage"] == stage)} for stage in ("C", "G", "S", "F")},
        "activation": activation,
        "source_members": source_hashes,
        "projection": "Allowlisted source fields, unchanged scientific values. Administrative resource fields and raw server logs excluded; original archive retained by author.",
    }
    evidence = destination / "evidence"
    evidence.mkdir(exist_ok=True)
    dump_json(evidence / "run.json", public)
    dump_json(evidence / "configuration.json", {key: contract[key] for key in CONTRACT_FIELDS})
    dump_json(evidence / "request-examples.json", examples)
    (evidence / "events.jsonl").write_text("".join(json.dumps(event, sort_keys=True) + "\n" for event in events), encoding="utf-8")
    source_scopes = Counter(group["stage"] for group in groups)
    print(json.dumps({"status": "PUBLIC_EVIDENCE_EXPORTED", "groups": dict(source_scopes),
                      "last_invocation_start_utc": start, "last_invocation_end_utc": end,
                      "last_invocation_elapsed_s": duration, "runway": public["runway"],
                      "request_examples": len(examples), "source_code_files": 3}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    export(args.source.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()