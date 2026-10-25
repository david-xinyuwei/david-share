import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from litellm.integrations.custom_logger import CustomLogger


def collect_markers(value, path=""):
    markers = []
    if isinstance(value, dict):
        for name, child in value.items():
            child_path = f"{path}.{name}" if path else name
            if name == "cache_control":
                markers.append({"path": child_path, "value": child})
            else:
                markers.extend(collect_markers(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            markers.extend(collect_markers(child, f"{path}[{index}]"))
    return markers


def safe_request(request):
    if not isinstance(request, dict):
        return {"capture": "FULL_REQUEST_NOT_AVAILABLE"}
    record = {
        name: request[name]
        for name in ("model", "max_tokens", "stream", "speed", "thinking", "output_config")
        if name in request
    }
    record["capture"] = "PROVIDER_REQUEST_FIELDS"
    record["cache_markers"] = collect_markers(request)
    for name in ("system", "messages", "tools"):
        if name in request:
            serialized = json.dumps(request[name], ensure_ascii=False, separators=(",", ":"))
            record[f"{name}_sha256"] = hashlib.sha256(serialized.encode()).hexdigest()
    return record


class RequestObserver(CustomLogger):
    def _capture(self, stage, kwargs):
        additional = kwargs.get("additional_args") or {}
        request = additional.get("complete_input_dict")
        if request is None:
            request = kwargs.get("complete_input_dict")
        record = {
            "capture_utc": datetime.now(timezone.utc).isoformat(),
            "stage": stage,
            "call_id": kwargs.get("litellm_call_id"),
            **safe_request(request),
        }
        directory = Path("/tmp/claude-gateway-evidence")
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / "provider-trace.jsonl").open("a", encoding="utf-8") as output:
            output.write(json.dumps(record, ensure_ascii=False) + "\n")
        print("CLAUDE_PROVIDER_TRACE " + json.dumps(record, ensure_ascii=False), flush=True)

    def log_pre_api_call(self, model, messages, kwargs):
        self._capture("pre_api_call", kwargs)

    def log_post_api_call(self, kwargs, response_obj, start_time, end_time):
        self._capture("post_api_call", kwargs)


observer = RequestObserver()