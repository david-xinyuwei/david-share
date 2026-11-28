"""Turn the summaries of a run into the public dataset of this repository.

Reads  <out>/summary/*.json (written by run_limits.py, run_stats.py and retrieve_fields.py; they hold counts, sizes,
       field names and error texts, no mail, chat or file content)
Writes results/summary/<stage>.json  the same rows without file hashes and without the request IDs of the service,
                                     with the time of each call also in seconds
       results/limits.json           every number the README and docs/RESULTS quote, computed here from the rows just
                                     written, none typed by hand
"""
import argparse
import json
import pathlib
import re
import sys

STAGES = ("mail", "collections", "chat", "multi", "body", "blob", "retrieve", "fulltext")
REPO = pathlib.Path(__file__).resolve().parents[1]
GUID = re.compile(r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}")
REMOVED = "(removed)"


def scrub(value):
    """What the public copy of a summary leaves out.

    - the SHA-256 of the user's own files: the check rows already say whether the bytes were identical;
    - the request IDs of the service: the field request_id of a row, and every GUID inside a text, which is where an
      error text carries its requestId. They point at single calls of the tested user and tell a reader nothing.
      The private summaries under <out>/summary keep them for a support case.
    """
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items() if k not in ("sha256", "request_id")}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    if isinstance(value, str):
        return GUID.sub(REMOVED, value)
    return value


class Stage:
    def __init__(self, rows):
        self.rows = rows
        self.by_case = {r["case"]: r for r in rows if "case" in r}
        self.checks = {r["check"]: r for r in rows if "check" in r}

    def count(self, case, index=0):
        """Items in the collection answer of a fetch call; None when the call failed."""
        res = self.by_case[case].get("result")
        return res[index].get("count") if isinstance(res, list) and len(res) > index else None

    def check(self, name):
        return self.checks[name]["value"]


def build(out):
    s = {name: Stage(json.loads((out / "summary" / f"{name}.json").read_text(encoding="utf-8"))) for name in STAGES}
    stats = json.loads((out / "summary" / "run_stats.json").read_text(encoding="utf-8"))
    fields = json.loads((out / "summary" / "retrieve_fields.json").read_text(encoding="utf-8"))
    mail, coll, chat, multi, body, blob, ret, full = (s[n] for n in STAGES)

    chats_error = coll.by_case["coll_chats_top_101"]["result"][0].get("error", "")
    paths_error = json.loads(multi.by_case["multi_051_paths"]["text"][0])
    chat_cases = sorted(c for c in chat.by_case if c.startswith("chat_02_"))
    fetch = {
        "messages_without_top": mail.count("mail_01_no_top"),
        "messages_by_top": {str(top): mail.count(f"mail_02_top_{top}") for top in (25, 26, 100, 101, 1000)},
        "top_cap": mail.count("mail_02_top_1000"),
        "skip_5_returns_items_6_to_10": mail.check("$skip=5 returns items 6 to 10 of the list"),
        "made_up_skiptoken_is_ignored": mail.check("a made-up $skiptoken is ignored (first page comes back)"),
        "nextlink_page_2_holds_100_other_messages": mail.check("page 2 holds 100 other messages"),
        "search_nextlink_page_2_holds_other_messages": mail.check("page 2 of the $search holds other messages"),
        "skip_5000_returns": mail.count("mail_10_skip_5000"),
        "filter_on_date_returns": mail.count("mail_07_filter_date"),
        "search_returns": mail.count("mail_08_search"),
        "oldest_message_month": mail.check("month of the oldest message returned"),
        "collections_without_top": {n: coll.count(f"coll_{n}_no_top") for n in ("events", "inbox", "drive_children", "people", "chats")},
        "collections_top_101": {n: coll.count(f"coll_{n}_top_101") for n in ("events", "inbox", "drive_children", "people", "chats")},
        "chats_top_101_error": "limit of '50'" in chats_error and "'100'" in chats_error,
        "chat_messages_without_top": sorted({chat.count(c) for c in chat_cases}),
        "chat_messages_by_top": {str(top): sorted({chat.count(c) for c in chat.by_case if c.startswith("chat_03_") and c.endswith(f"_top_{top}")})
                                 for top in (10, 11, 20, 21, 50)},
        "chat_messages_cap": chat.count("chat_03_1_top_50"),
        "chats_tested": len(chat_cases),
        "service_notes": sorted({r["service_note"].split(". ")[0] for st in (mail, coll, chat) for r in st.rows if r.get("service_note")},
                                key=lambda t: int(t.split()[3])),
        "paths_per_call_max": multi.check("largest number of paths one fetch call answered"),
        "paths_per_call_answered": sorted(int(c.split("_")[1]) for c, r in multi.by_case.items() if not r.get("is_error")),
        "paths_per_call_failed": sorted(int(c.split("_")[1]) for c, r in multi.by_case.items() if r.get("is_error")),
        "paths_per_call_first_failure": min(int(c.split("_")[1]) for c, r in multi.by_case.items() if r.get("is_error")),
        "paths_error_code": paths_error.get("errorCode"),
        "body_25_newest": body.check("characters of body.content per message, 25 newest messages"),
        "body_preview_25_newest": body.check("characters of bodyPreview per message, 25 newest messages"),
        "body_100_messages": body.check("100 messages with their full body in one answer"),
        "body_100_messages_seconds": round(body.by_case["body_02_100_messages"]["ms"] / 1000, 1),
    }

    files = []
    for case in sorted((c for c in blob.by_case if c.startswith("blob_01_")), key=lambda c: int(c.split("_")[2])):
        row, n = blob.by_case[case], int(case.split("_")[2])
        files.append({"bytes": n, "type": row["note"].split()[1], "returned_in_full": blob.check(f"{n:,} bytes: the decoded content is byte-identical to the local file"),
                      "seconds": round(row["ms"] / 1000, 1), "answer_bytes": row["response_bytes"],
                      "error": json.loads(row["text"][0]).get("error") if row.get("is_error") and row.get("text") else None})
    large = [f["answer_bytes"] / f["bytes"] for f in files if f["returned_in_full"] and f["bytes"] > 3_000_000]
    fetch_blob = {
        "files": files,
        "answer_bytes_per_file_byte_above_3_megabytes": [round(min(large), 2), round(max(large), 2)] if large else None,
        "largest_returned_bytes": max(f["bytes"] for f in files if f["returned_in_full"]),
        "smallest_refused_bytes": min(f["bytes"] for f in files if not f["returned_in_full"]),
        "four_mebibytes": 4 * 1024 * 1024,
        "four_megabytes_decimal": 4_000_000,  # the other reading of "4 MB", which the measurement rules out
        "error": sorted({f["error"] for f in files if f["error"]}),
    }

    answers = {c: r["result"] for c, r in ret.by_case.items() if isinstance(r.get("result"), dict)}
    counts = {c: a["results"] for c, a in answers.items()}
    snippets = [f["fields"]["snippet"] for f in fields.values() if "snippet" in f["fields"]]
    each = [(fl["snippet"], "truncationInfo" in fl) for a in answers.values() for fl in a["markdown_fields_each"] if "snippet" in fl]
    cut, uncut = sorted(n for n, marked in each if marked), sorted(n for n, marked in each if not marked)
    all_results = sum(f["results"] for f in fields.values())
    truncated = sum(f["truncationInfo"].get("Content has been truncated", 0) for f in fields.values())
    retrieve = {
        "calls_answered": len(answers),
        "calls_refused": sorted(json.loads(r["text"][0])["error"] for r in ret.by_case.values() if r.get("is_error")),
        "results_per_call": {c: n for c, n in sorted(counts.items())},
        "results_per_call_max": max(counts.values()),
        "results_per_call_max_case": max(counts, key=counts.get),
        "results_per_call_max_without_a_number_in_the_query": max(n for c, n in counts.items() if "ask_for" not in c),
        "calls_with_zero_results": sorted(c for c, n in counts.items() if n == 0),
        "results_total": all_results,
        "results_marked_truncated": truncated,
        "by_type": {kind: {"results": f["results"], "markdown_chars": [f["markdown_chars_min"], f["markdown_chars_max"]],
                           "snippet_chars": [f["fields"]["snippet"]["chars_min"], f["fields"]["snippet"]["chars_max"]] if "snippet" in f["fields"] else None,
                           "marked_truncated": f["truncationInfo"].get("Content has been truncated", 0)} for kind, f in fields.items()},
        "snippet_chars_max": max(x["chars_max"] for x in snippets),
        "results_with_snippet": len(each),
        "snippet_chars_median": sorted(n for n, _ in each)[len(each) // 2],
        "snippet_chars_marked_truncated": [cut[0], cut[-1]],
        "snippet_chars_not_marked": [uncut[0], uncut[-1]],
        "results_with_snippet_not_marked": len(uncut),
        "markdown_chars_max": max(f["markdown_chars_max"] for f in fields.values()),
        "markdown_chars_per_call_max": max(a["markdown_chars_total"] for a in answers.values()),
        "same_question_twice": [counts["retrieve_01_question"], counts["retrieve_02_same_again"]],
        "same_question_twice_same_sources": ret.check("the same query returns the same sources in the same order"),
        "seconds_default_strategy": [round(min(r["ms"] for c, r in ret.by_case.items() if c in answers and "copilot" not in c) / 1000, 1),
                                     round(max(r["ms"] for c, r in ret.by_case.items() if c in answers and "copilot" not in c) / 1000, 1)],
        "seconds_strategy_copilot": round(ret.by_case["retrieve_05_strategy_copilot"]["ms"] / 1000, 1),
        "index_matches_reported": answers["retrieve_06_only_OneDriveAndSharePoint"]["searchMetadata"][0]["totalResults"],
        "old_mail_months": answers["retrieve_11_old_mail"]["months"],
    }

    message_rows = [r["value"] for name, r in full.checks.items() if "message body" in name and isinstance(r["value"], dict)]
    file_rows = [r["value"] for name, r in full.checks.items() if "file size" in name and isinstance(r["value"], dict)]
    # body text and snippet are both counted in characters; the body text is counted without white space, so a snippet
    # (counted with white space) that is shorter than it cannot hold the whole body
    all_found = [m for m in message_rows if m["pieces_found"] == m["pieces"]]
    unmarked = [m for m in message_rows if not m["marked_truncated"]]
    longest = max(message_rows, key=lambda m: m["full_text_chars"])
    largest_file = max(file_rows, key=lambda f: f["file_bytes"])
    fulltext = {
        "items_read_back_with_fetch": len(full.by_case["fulltext_01_items"]["result"]),
        "items_read_back_status_200": sum(x.get("statusCode") == 200 for x in full.by_case["fulltext_01_items"]["result"]),
        "messages_compared": len(message_rows),
        "messages_marked_truncated": len(message_rows) - len(unmarked),
        "messages_not_marked": len(unmarked),
        "messages_not_marked_with_snippet_shorter_than_body_text": sum((m["snippet_chars"] or 0) < m["full_text_chars"] for m in unmarked),
        "pieces_per_message": message_rows[0]["pieces"],
        "messages_with_all_pieces_found": len(all_found),
        "messages_with_all_pieces_found_and_snippet_not_shorter": sum((m["snippet_chars"] or 0) >= m["full_text_chars"] for m in all_found),
        "messages_with_all_pieces_found_body_text_chars": [min(m["full_text_chars"] for m in all_found), max(m["full_text_chars"] for m in all_found)] if all_found else None,
        "messages_with_pieces_missing": len(message_rows) - len(all_found),
        "longest_message": {"body_text_chars": longest["full_text_chars"], "snippet_chars": longest["snippet_chars"],
                            "marked_truncated": longest["marked_truncated"], "pieces_found": longest["pieces_found"], "pieces": longest["pieces"]},
        "files_compared": len(file_rows),
        "files_marked_truncated": sum(f["marked_truncated"] for f in file_rows),
        "file_bytes": [min(f["file_bytes"] for f in file_rows), max(f["file_bytes"] for f in file_rows)],
        "files_larger_than_4_mebibytes": sum(f["file_bytes"] > 4 * 1024 * 1024 for f in file_rows),
        "file_markdown_chars": [min(f["markdown_chars"] for f in file_rows), max(f["markdown_chars"] for f in file_rows)],
        "largest_file": {"bytes": largest_file["file_bytes"], "snippet_chars": largest_file["snippet_chars"], "marked_truncated": largest_file["marked_truncated"]},
        "sources_seen_in_more_than_one_call": full.check("sources that came back in more than one retrieve call"),
    }

    stage_calls = [r for st in s.values() for r in st.rows if "case" in r]
    per_tool = {}
    for r in stage_calls:
        per_tool[r["tool"]] = per_tool.get(r["tool"], 0) + 1
    run = {"date_utc": stats["first_utc"][:10], "first_call_utc": stats["first_utc"][:19] + "Z", "last_call_utc": stats["last_utc"][:19] + "Z",
           "tools_call_records": stats["tools_call_records"], "calls_per_tool": {t: v["calls"] for t, v in stats["per_tool"].items()},
           "stage_calls": len(stage_calls), "stage_calls_per_tool": dict(sorted(per_tool.items())),
           "stage_calls_answer_minutes": round(sum(r["ms"] for r in stage_calls) / 60000, 1),  # time waiting for answers, without the time the page takes
           "records_outside_the_stages": stats["tools_call_records"] - len(stage_calls),
           "tool_results_that_report_throttling": stats["tool_results_that_report_throttling"],
           "answers_with_retry_after_header": stats["answers_with_retry_after_header"],
           "http_status": stats["http_status"], "http_429": stats["http_429"], "most_calls_in_60_seconds": stats["most_calls_in_60_seconds"],
           "median_seconds": {t: round(v["ms_median"] / 1000, 1) for t, v in stats["per_tool"].items()},
           "client": "Interactive Demo page (interactivedemo.microsoft.com/work-iq/mcp), Live mode, in Microsoft Edge",
           "endpoint": "https://workiq.svc.cloud.microsoft/mcp", "scope": "one Microsoft 365 tenant, one signed-in user, the user's own data"}
    return {"run": run, "fetch": fetch, "fetch_blob": fetch_blob, "retrieve": retrieve, "fulltext": fulltext}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out", help="private evidence folder of the run")
    ap.add_argument("--results", default=str(REPO / "results"), help="public results folder (default: results/ of this repository)")
    a = ap.parse_args()
    out, results = pathlib.Path(a.out), pathlib.Path(a.results)
    (results / "summary").mkdir(parents=True, exist_ok=True)
    for name in STAGES:
        rows = scrub(json.loads((out / "summary" / f"{name}.json").read_text(encoding="utf-8")))
        for row in rows:
            if isinstance(row.get("ms"), (int, float)):
                row["seconds"] = round(row["ms"] / 1000, 1)  # the unit the pages quote
        (results / "summary" / f"{name}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    for name in ("run_stats", "retrieve_fields"):
        data = scrub(json.loads((out / "summary" / f"{name}.json").read_text(encoding="utf-8")))
        (results / "summary" / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    limits = build(results)  # from the public rows just written, so no number depends on a field that is not published
    (results / "limits.json").write_text(json.dumps(limits, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(limits, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
