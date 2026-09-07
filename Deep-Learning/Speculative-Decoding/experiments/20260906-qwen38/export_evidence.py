"""Export allowlisted run evidence from the author's verified local archive."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import tarfile

from analyze_results import digest_file, dump_json, require


TERMINAL_FIELDS = (
    "run_id", "phase", "stage", "completed", "total", "groups_completed",
    "groups_total", "remaining_groups", "error", "error_type",
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
    public = {
        "run_id": campaign["run_id"],
        "source_archive": {"sha256": digest_file(archive_path), "bytes": archive_path.stat().st_size},
        "terminal": {key: campaign[key] for key in TERMINAL_FIELDS},
        "stages": {stage: {"completed_groups": sum(group["stage"] == stage for group in groups),
                            "completed_responses": sum(group["completed"] for group in groups if group["stage"] == stage),
                            "measured_group_wall_s": sum(group["elapsed_wall_s"] for group in groups if group["stage"] == stage)} for stage in ("C", "G", "S", "F")},
        "activation": activation,
        "source_members": source_hashes,
        "projection": "Allowlisted experimental coverage, activation and provenance; scientific values unchanged. Operational timelines, budget estimates, transfer and power-management records remain private.",
    }
    evidence = destination / "evidence"
    evidence.mkdir(exist_ok=True)
    dump_json(evidence / "run.json", public)
    dump_json(evidence / "configuration.json", {key: contract[key] for key in CONTRACT_FIELDS})
    dump_json(evidence / "request-examples.json", examples)
    source_scopes = Counter(group["stage"] for group in groups)
    print(json.dumps({"status": "PUBLIC_EVIDENCE_EXPORTED", "groups": dict(source_scopes),
                      "request_examples": len(examples), "source_code_files": 3}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    export(args.source.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()