"""Prompt-cache behaviour of a coding session on the three Claude 5.5 deployments.

A coding assistant sends the same instructions and repository files at the
front of every request and appends the conversation. Each scenario changes one
thing and records what the API reports as written to / read from the cache:

  none                 no cache_control (baseline)
  auto                 top-level cache_control (automatic caching), then a second
                       conversation with the same instructions + files
  system_only          one explicit breakpoint at the end of the repository block,
                       then a second conversation
  system_plus_auto     explicit repository breakpoint + top-level automatic caching,
                       then a second conversation
  effort_switch        adaptive thinking, automatic caching; top-level effort low, low, high, low
  effort_switch_message  the same switch sent as per-message effort (beta header
                       mid-conversation-output-config-2026-07-01), which the docs say keeps the cache
  mode_switch          automatic caching; thinking off, off, adaptive, adaptive (Sonnet, Haiku)
  prewarm              non-streaming max_tokens 0 request with the repository breakpoint,
                       then the first real question
  idle_5m / idle_1h    automatic caching with the 5-minute / 1-hour TTL; 6.5 minutes idle
                       between turn 1 and turn 2
  ttft_cold / ttft_warm  cold request then identical-prefix warm request, short answer;
                       repository context (all models) and a larger context (Sonnet, Haiku)

Each conversation starts with its own nonce at the top of the system prompt, so
it starts cold; a 'second conversation' reuses the nonce of the one before it.
Each model starts only after its matrix stream has finished, so the two tests
never share a deployment's rate limit. The client paces under 85% of the test
deployment's token and output-token limits; a 429 that still happens is
recorded and the same request is sent again after Retry-After.
"""
import argparse
import json
import threading
import time
import uuid
from collections import deque
from pathlib import Path

import httpx

from claude_api import (API_VERSION, BASE, TokenProvider, _keep_headers, _safe_json, cost_usd, new_client,
                        sha256_json, stream_message, utcnow)

SHORT = {"claude-opus-5-5": "opus", "claude-sonnet-5-5": "sonnet", "claude-haiku-5-5": "haiku"}
BASE_MODE = {"claude-opus-5-5": "adaptive", "claude-sonnet-5-5": "between_tools", "claude-haiku-5-5": "disabled"}
TPM = {"claude-opus-5-5": 40000, "claude-sonnet-5-5": 80000, "claude-haiku-5-5": 80000}
OTPM = {model: limit // 5 for model, limit in TPM.items()}
REPO_FILES = ["_auth.py", "_config.py", "_urls.py"]
LARGE_FILES = ["_auth.py", "_config.py", "_urls.py", "_models.py", "_client.py"]
INSTRUCTIONS = """You are a senior Python engineer pairing with a developer on the httpx code base.
The repository files you may read are included below. Answer concisely, show complete code when you write code,
and keep the existing style (type hints, docstrings, naming)."""
QUESTIONS = [
    "In five bullet points, explain how an Auth subclass takes part in sending a request: which methods are called, "
    "in what order, and how a response can trigger a retry.",
    "Write a new Auth subclass BearerTokenAuth that takes a token-refresh callback, sends 'Authorization: Bearer "
    "<token>', and refreshes the token once when the server answers 401. Return the complete class.",
    "Write pytest tests for BearerTokenAuth using httpx.MockTransport: one test for a normal request and one for "
    "refresh-on-401.",
    "Write a git commit message (subject line plus a short body) for the change we made in this session.",
]
SECOND_QUESTION = "List the public classes defined in these files, with one line each on what they are for."
PAIR_QUESTION = "Reply with the single word OK."
MAX_TOKENS = 3000
PAIR_MAX_TOKENS = 256
IDLE_S = 390
PAIRS = 5
EFFORT_BETA = {"anthropic-beta": "mid-conversation-output-config-2026-07-01"}


def context_text(package_dir, files):
    return "\n\n".join(f"### httpx/{name}\n```python\n{(package_dir / name).read_text(encoding='utf-8')}\n```"
                       for name in files)


class Pacer:
    def __init__(self, model):
        self.model, self.total, self.output = model, deque(), deque()

    @staticmethod
    def _used(queue):
        cutoff = time.time() - 60
        while queue and queue[0][0] < cutoff:
            queue.popleft()
        return sum(value for _, value in queue)

    def wait(self, estimate_total, estimate_output):
        waited = 0
        while waited < 180 and (self._used(self.total) + estimate_total > 0.85 * TPM[self.model]
                                or self._used(self.output) + estimate_output > 0.85 * OTPM[self.model]):
            time.sleep(1)
            waited += 1
        return waited

    def add(self, usage):
        if usage:
            now = time.time()
            self.total.append((now, sum(usage.get(k) or 0 for k in (
                "input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens"))))
            self.output.append((now, usage.get("output_tokens") or 0))


def post_once(client, tokens, body):
    """Non-streaming call, used for max_tokens=0 pre-warming."""
    record = {"sent_utc": utcnow(), "status": None, "http_status": None}
    start = time.perf_counter()
    try:
        response = client.post(BASE + "/v1/messages", content=json.dumps(body).encode("utf-8"),
                               headers={"Authorization": "Bearer " + tokens.get(), "anthropic-version": API_VERSION,
                                        "content-type": "application/json"})
        record["http_status"] = response.status_code
        record["headers"] = _keep_headers(response.headers)
        data = _safe_json(response.content) if response.content else {}
        if response.status_code == 200:
            record.update(usage=data.get("usage"), stop_reason=data.get("stop_reason"), status="completed", text="")
        else:
            record.update(error_body=data, status="http_error")
    except httpx.HTTPError as exc:
        record.update(status="transport_error", error={"type": type(exc).__name__, "message": str(exc)[:500]})
    record["timing"] = {"end": round(time.perf_counter() - start, 4)}
    return record


class Conversation:
    def __init__(self, runner, scenario, repetition, context, nonce=None, extra_headers=None):
        self.runner, self.scenario, self.repetition, self.context = runner, scenario, repetition, context
        self.nonce = nonce or uuid.uuid4().hex[:12]
        self.extra_headers = extra_headers
        self.messages, self.turn = [], 0

    def system(self, breakpoint, ttl):
        repo_block = {"type": "text", "text": "Repository files:\n\n" + self.context}
        if breakpoint:
            repo_block["cache_control"] = {"type": "ephemeral", **({"ttl": ttl} if ttl else {})}
        return [{"type": "text", "text": f"Conversation {self.nonce}. {INSTRUCTIONS}"}, repo_block]

    def ask(self, question, mode=None, effort="low", automatic=False, breakpoint=False, ttl=None,
            max_tokens=MAX_TOKENS, stream=True, keep=True, message_effort=None):
        self.turn += 1
        runner, model = self.runner, self.runner.model
        mode = mode or BASE_MODE[model]
        if message_effort:  # effort-only system message; it stays in the history, as the docs describe
            self.messages.append({"role": "system", "content": [], "output_config": {"effort": message_effort}})
        body = {"model": model, "max_tokens": max_tokens, "stream": stream,
                "thinking": {"type": mode}, "output_config": {"effort": effort},
                "system": self.system(breakpoint, ttl),
                "messages": self.messages + [{"role": "user", "content": question}]}
        if automatic:
            body["cache_control"] = {"type": "ephemeral", **({"ttl": ttl} if ttl else {})}
        prompt_chars = len(json.dumps(body["system"])) + len(json.dumps(body["messages"]))
        for attempt in range(1, 5):
            paced = runner.pacer.wait(prompt_chars // 3, min(max_tokens, 2000))
            try:
                record = (stream_message(runner.client, runner.tokens, body, extra_headers=self.extra_headers)
                          if stream else post_once(runner.client, runner.tokens, body))
            except Exception as exc:  # harness-side failure, kept apart from platform outcomes
                record = {"sent_utc": utcnow(), "status": "client_exception", "http_status": None,
                          "error": {"type": type(exc).__name__, "message": str(exc)[:500]}, "timing": {}}
            usage = record.get("usage") or {}
            runner.pacer.add(usage)
            row = {"model": model, "scenario": self.scenario, "repetition": self.repetition, "nonce": self.nonce,
                   "turn": self.turn, "attempt": attempt, "mode": mode, "effort": effort,
                   "message_effort": message_effort, "beta": (self.extra_headers or {}).get("anthropic-beta"),
                   "automatic": automatic,
                   "breakpoint": breakpoint, "ttl": ttl, "max_tokens": max_tokens, "stream": stream,
                   "prompt_chars": prompt_chars, "paced_wait_s": paced, "request_sha256": sha256_json(body),
                   "status": record.get("status"), "http_status": record.get("http_status"),
                   "stop_reason": record.get("stop_reason"), "error_body": record.get("error_body"),
                   "error": record.get("error"), "usage": usage or None, "timing": record.get("timing"),
                   "sent_utc": record.get("sent_utc"), "cost_usd": cost_usd(model, usage) if usage else 0.0,
                   "text_chars": len(record.get("text") or ""), "headers": record.get("headers")}
            runner.write(row)
            if record.get("http_status") != 429:
                break
            time.sleep(float((record.get("headers") or {}).get("retry-after", 30)) + 1)
        if keep and record.get("text"):
            self.messages += [{"role": "user", "content": question},
                              {"role": "assistant", "content": record["text"]}]
        return row


class Runner:
    def __init__(self, model, out_path, lock, contexts):
        self.model, self.out_path, self.lock, self.contexts = model, out_path, lock, contexts
        self.client, self.tokens, self.pacer = new_client(), TokenProvider(), Pacer(model)

    def write(self, row):
        with self.lock:
            with self.out_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"{utcnow()} {SHORT[self.model]} {row['scenario']} r{row['repetition']} t{row['turn']} "
              f"a{row['attempt']} {row['status']} http={row['http_status']} usage={row['usage']}", flush=True)

    def conversation(self, scenario, repetition, nonce=None, context="repo", extra_headers=None):
        return Conversation(self, scenario, repetition, self.contexts[context], nonce, extra_headers)

    def run(self, repetitions):
        off_mode = self.model != "claude-opus-5-5"
        for rep in range(1, repetitions + 1):
            c = self.conversation("none", rep)
            for q in QUESTIONS:
                c.ask(q)
            for scenario, options in (("auto", {"automatic": True}), ("system_only", {"breakpoint": True}),
                                      ("system_plus_auto", {"automatic": True, "breakpoint": True})):
                c = self.conversation(scenario, rep)
                for q in QUESTIONS:
                    c.ask(q, **options)
                self.conversation(scenario + "_second", rep, nonce=c.nonce).ask(SECOND_QUESTION, **options)
            c = self.conversation("effort_switch", rep)
            for turn, q in enumerate(QUESTIONS, start=1):
                c.ask(q, mode="adaptive", automatic=True, effort="high" if turn == 3 else "low")
            c = self.conversation("effort_switch_message", rep, extra_headers=EFFORT_BETA)
            for turn, q in enumerate(QUESTIONS, start=1):
                c.ask(q, mode="adaptive", automatic=True, message_effort={3: "high", 4: "low"}.get(turn))
            if off_mode:
                c = self.conversation("mode_switch", rep)
                for turn, q in enumerate(QUESTIONS, start=1):
                    c.ask(q, automatic=True, mode="adaptive" if turn >= 3 else None)
            c = self.conversation("prewarm", rep)
            c.ask("warm-up", breakpoint=True, max_tokens=0, stream=False, keep=False)
            c.ask(QUESTIONS[0], breakpoint=True)
            idle = [self.conversation("idle_5m", rep), self.conversation("idle_1h", rep)]
            idle[0].ask(QUESTIONS[0], automatic=True)
            idle[1].ask(QUESTIONS[0], automatic=True, ttl="1h")
            time.sleep(IDLE_S)
            idle[0].ask(QUESTIONS[1], automatic=True)
            idle[1].ask(QUESTIONS[1], automatic=True, ttl="1h")
        sizes = ["repo", "large"] if off_mode else ["repo"]
        for size in sizes:
            for pair in range(1, PAIRS + 1):
                cold = self.conversation(f"ttft_cold_{size}", pair, context=size)
                cold.ask(PAIR_QUESTION, breakpoint=True, max_tokens=PAIR_MAX_TOKENS, keep=False)
                self.conversation(f"ttft_warm_{size}", pair, nonce=cold.nonce, context=size).ask(
                    PAIR_QUESTION, breakpoint=True, max_tokens=PAIR_MAX_TOKENS, keep=False)
        self.client.close()


def wait_for_matrix(run_dir, model):
    """Return once the matrix has a final row for every planned task of this model."""
    while True:
        state = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        if state["status"] != "RUNNING":
            return state["status"]
        final = set()
        path = run_dir / f"responses_{SHORT[model]}.jsonl"
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                if row.get("http_status") != 429 or row.get("final"):
                    final.add(row["task_id"])
        if len(final) >= state["planned"][model]:
            return f"model finished ({len(final)} tasks)"
        time.sleep(60)


def run_model(model, args, contexts, out_path, lock):
    if args.wait_run_dir:
        reason = wait_for_matrix(Path(args.wait_run_dir), model)
        print(f"{utcnow()} {SHORT[model]} start: {reason}", flush=True)
    Runner(model, out_path, lock, contexts).run(args.repetitions)
    print(f"{utcnow()} {SHORT[model]} done", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--models", default=",".join(SHORT))
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--wait-run-dir", default="")
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    package = Path(args.package_dir)
    contexts = {"repo": context_text(package, REPO_FILES), "large": context_text(package, LARGE_FILES)}
    (out_dir / "context.json").write_text(json.dumps({
        "instructions": INSTRUCTIONS, "questions": QUESTIONS, "second_question": SECOND_QUESTION,
        "pair_question": PAIR_QUESTION, "repo_files": REPO_FILES, "large_files": LARGE_FILES,
        "context_chars": {k: len(v) for k, v in contexts.items()},
        "context_sha256": {k: sha256_json(v) for k, v in contexts.items()},
        "max_tokens": MAX_TOKENS, "pair_max_tokens": PAIR_MAX_TOKENS, "idle_seconds": IDLE_S, "pairs": PAIRS,
        "base_mode": BASE_MODE, "tpm": TPM, "otpm_assumed": OTPM, "repetitions": args.repetitions,
        "started_utc": utcnow()}, indent=1), encoding="utf-8")
    lock = threading.Lock()
    out_path = out_dir / "cache_results.jsonl"
    threads = [threading.Thread(target=run_model, args=(m, args, contexts, out_path, lock))
               for m in args.models.split(",")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    print(f"{utcnow()} all done", flush=True)


if __name__ == "__main__":
    main()
