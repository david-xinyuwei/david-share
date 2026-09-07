"""Request-scoped accounting for the reviewed vLLM streaming protocol."""

import json


class StreamProtocolError(ValueError):
    pass


class StreamMetrics:
    def __init__(self, model, started_ns, max_output_tokens):
        self.model = model
        self.started_ns = started_ns
        self.max_output_tokens = max_output_tokens
        self.last_received_ns = started_ns
        self.response_id = None
        self.prompt_token_ids = None
        self.token_ids = []
        self.content_parts = []
        self.reasoning_parts = []
        self.usage = None
        self.finish_reason = None
        self.done = False
        self.generated_event_count = 0
        self.timestamps = {"dispatch": started_ns}

    @staticmethod
    def _ids(value, field):
        if not isinstance(value, list) or any(type(token) is not int or token < 0 for token in value):
            raise StreamProtocolError(f"Invalid {field}")
        return value

    @staticmethod
    def _text(value, field):
        if value is None:
            return ""
        if not isinstance(value, str):
            raise StreamProtocolError(f"Invalid {field}")
        return value

    def consume(self, data, received_ns):
        if type(received_ns) is not int or received_ns < self.last_received_ns:
            raise StreamProtocolError("Receive clock is not monotonic")
        self.last_received_ns = received_ns
        if self.done:
            raise StreamProtocolError("Data received after DONE")
        if data == "[DONE]":
            self.done = True
            self.timestamps["done"] = received_ns
            return

        chunk = json.loads(data)
        if not isinstance(chunk, dict) or chunk.get("model") != self.model:
            raise StreamProtocolError("Response model mismatch")
        response_id = chunk.get("id")
        if not isinstance(response_id, str) or not response_id:
            raise StreamProtocolError("Missing response identity")
        if self.response_id is not None and response_id != self.response_id:
            raise StreamProtocolError("Response identity changed")
        self.response_id = response_id

        prompt_ids = chunk.get("prompt_token_ids")
        if prompt_ids is not None:
            prompt_ids = self._ids(prompt_ids, "prompt_token_ids")
            if self.prompt_token_ids is not None and prompt_ids != self.prompt_token_ids:
                raise StreamProtocolError("Prompt token IDs changed")
            self.prompt_token_ids = prompt_ids

        choices = chunk.get("choices", [])
        if not isinstance(choices, list) or len(choices) > 1:
            raise StreamProtocolError("Expected a single choice or usage event")
        for choice in choices:
            if not isinstance(choice, dict) or choice.get("index") != 0:
                raise StreamProtocolError("Unexpected choice index")
            delta = choice.get("delta") or {}
            if not isinstance(delta, dict) or delta.get("tool_calls") or delta.get("function_call"):
                raise StreamProtocolError("Unexpected output shape or tool call")
            content = self._text(delta.get("content"), "content")
            reasoning = self._text(delta.get("reasoning"), "reasoning")
            legacy = self._text(delta.get("reasoning_content"), "reasoning_content")
            if legacy and reasoning and legacy != reasoning:
                raise StreamProtocolError("Conflicting reasoning fields")
            reasoning = reasoning or legacy
            if content or reasoning:
                self.timestamps.setdefault("first_reasoning_or_content", received_ns)
            if content:
                self.timestamps.setdefault("first_final_content", received_ns)
                self.content_parts.append(content)
            if reasoning:
                self.reasoning_parts.append(reasoning)

            generated_ids = choice.get("token_ids")
            if generated_ids is not None:
                generated_ids = self._ids(generated_ids, "token_ids")
                if generated_ids:
                    self.timestamps.setdefault("first_token_ids", received_ns)
                    self.timestamps["last_token_ids"] = received_ns
                    self.generated_event_count += 1
                    self.token_ids.extend(generated_ids)
                    if len(self.token_ids) > self.max_output_tokens:
                        raise StreamProtocolError("Output exceeded requested token budget")

            finish = choice.get("finish_reason")
            if finish is not None:
                if finish not in ("stop", "length"):
                    raise StreamProtocolError(f"Unsupported finish reason: {finish}")
                if self.finish_reason is not None:
                    raise StreamProtocolError("Duplicate finish event")
                self.finish_reason = finish
                self.timestamps["finish_reason"] = received_ns

        usage = chunk.get("usage")
        if usage is not None:
            if not isinstance(usage, dict):
                raise StreamProtocolError("Invalid usage shape")
            for field in ("prompt_tokens", "completion_tokens"):
                if type(usage.get(field)) is not int or usage[field] < 0:
                    raise StreamProtocolError(f"Invalid usage {field}")
            self.usage = usage
            self.timestamps["final_usage"] = received_ns

    def _elapsed(self, timestamp):
        value = self.timestamps.get(timestamp)
        return None if value is None else (value - self.started_ns) / 1_000_000_000

    def finalize(self):
        if not self.done or self.finish_reason is None or self.usage is None:
            raise StreamProtocolError("Missing DONE, finish_reason or final usage")
        if self.prompt_token_ids is None:
            raise StreamProtocolError("Missing authoritative prompt token IDs")
        if len(self.prompt_token_ids) != self.usage["prompt_tokens"]:
            raise StreamProtocolError("Prompt token IDs disagree with usage")
        output_tokens = self.usage["completion_tokens"]
        if len(self.token_ids) != output_tokens:
            raise StreamProtocolError("Generated token IDs disagree with usage")
        if output_tokens > 0 and "first_token_ids" not in self.timestamps:
            raise StreamProtocolError("Missing generated-token timestamps")
        if self.timestamps["final_usage"] < self.timestamps["finish_reason"]:
            raise StreamProtocolError("Final usage preceded completion")
        if self.timestamps["done"] < self.timestamps["final_usage"]:
            raise StreamProtocolError("DONE preceded final usage")
        tpot = None
        tpot_status = "NOT_DEFINED_OUTPUT_LE_1"
        if output_tokens > 1:
            tpot = (self.timestamps["last_token_ids"] - self.timestamps["first_token_ids"]) / 1_000_000_000 / (output_tokens - 1)
            tpot_status = "SINGLE_CHUNK" if self.generated_event_count == 1 else "VALID"
        return {
            "response_id": self.response_id,
            "content": "".join(self.content_parts),
            "reasoning": "".join(self.reasoning_parts),
            "prompt_token_ids": self.prompt_token_ids,
            "token_ids": self.token_ids,
            "usage": self.usage,
            "finish_reason": self.finish_reason,
            "timestamps_ns": dict(self.timestamps),
            "ttft_token_s": self._elapsed("first_token_ids"),
            "ttft_visible_s": self._elapsed("first_reasoning_or_content"),
            "time_to_first_final_answer_s": self._elapsed("first_final_content"),
            "last_token_s": self._elapsed("last_token_ids"),
            "e2e_s": self._elapsed("done"),
            "tpot_s": tpot,
            "tpot_status": tpot_status,
            "generated_event_count": self.generated_event_count,
            "empty_final": not "".join(self.content_parts).strip(),
        }