"""Measure the limits of the Work IQ MCP read tools (fetch, fetch_blob, retrieve) in your own tenant.

Every call goes through the Interactive Demo page in Live mode (scripts/demo_runner.py), is billed in
Copilot Credits and reads the signed-in user's own Microsoft 365 data. Full answers are saved under
<out>/raw (private). The console and <out>/summary hold structure, counts, sizes and error texts only.

Stages (run them in this order the first time):
  mail         /me/messages: page size without $top, $top cap, $skip, $skiptoken, @odata.nextLink, $filter, $search
  collections  the same two questions (page size without $top, $top cap) on five other collections
  chat         chat messages per request
  multi        number of paths one fetch call accepts
  body         size of one answer (100 messages with their full body)
  blob         largest file fetch_blob returns (writes synthetic text files into a OneDrive folder first)
  retrieve     number of results and characters per result, strategies, capabilities, query length
  fulltext     is results[].markdown the whole item or an extract (needs the records of the retrieve stage)
"""
import argparse
import base64
import hashlib
import html
import json
import os
import pathlib
import re
import sys
import time
import urllib.parse

import demo_runner as dr
from shape import tool_result

GRAPH = "https://graph.microsoft.com/v1.0"
RETRIEVAL = "application/vnd.ms-workiq.retrieval"  # key of the retrieve answer inside structuredContent


class Run:
    def __init__(self, out, stage, reuse=False, blob_dir=None, blob_files=None):
        self.out = pathlib.Path(out)
        self.blob_dir = pathlib.Path(blob_dir) if blob_dir else self.out / "blob_test"
        self.blob_files = [pathlib.Path(p) for p in blob_files or []]
        self.raw = self.out / "raw"
        (self.out / "summary").mkdir(parents=True, exist_ok=True)
        self.console = (self.out / f"console_{stage}.txt").open("w", encoding="utf-8")
        self.stage, self.rows, self.reuse = stage, [], reuse
        self.s = dr.Session()
        self.log(f"# stage {stage}  account shown by the page: {self.s.account() or '(none)'}  recorder: {self.s.recorder}")

    def log(self, text):
        print(text)
        self.console.write(text + "\n")
        self.console.flush()

    def call(self, case, tool, arguments, note="", timeout=300, shown=None, fresh=False):
        """One tools/call. `shown` replaces the arguments in console and summary when they hold an ID or a private path.
        `fresh` sends the call even when a record exists (for a state that changes, such as an upload in progress)."""
        saved = self.raw / f"{case}.json"
        if self.reuse and saved.exists() and not fresh:
            rec = json.loads(saved.read_text(encoding="utf-8"))  # recorded earlier in this run: not sent or billed again
        else:
            time.sleep(1.0)
            rec = self.s.call(tool, arguments, timeout)
            if tool == "fetch_blob":
                rec = compact_blob(rec)
            dr.save(rec, self.raw, case)
        row = {"case": case, "tool": tool, "arguments": shown if shown is not None else arguments, "note": note}
        if "ui_error" in rec:
            row["ui_error"] = rec["ui_error"]
        else:
            is_error, texts, structured = tool_result(rec.get("response"))
            row.update(sent_utc=rec["sent_utc"], http_status=rec["http_status"], ms=rec["ms_to_last_byte"] or rec["ms_to_headers"],
                       response_bytes=rec["response_bytes"], request_id=rec["headers"].get("request-id"),
                       retry_after=rec["headers"].get("retry-after"), sent_as_typed=rec["sent_as_typed"], is_error=is_error)
            if is_error or structured is None:
                row["text"] = [t[:700] for t in texts]
                if rec.get("response") is None:
                    row["body_head"] = rec["response_text"][:500]
            row["result"] = SUMMARIZERS[tool](structured, rec) if structured is not None else None
            if isinstance(structured, dict) and isinstance(structured.get("note"), str):
                row["service_note"] = structured["note"]  # for example "Results limited to 10 items per collection. ..."
        self.rows.append(row)
        self.log(json.dumps(row, ensure_ascii=False))
        return rec, row

    def check(self, name, value, detail=""):
        """A fact computed from the saved answers (for example: do two pages overlap)."""
        row = {"check": name, "value": value, "detail": detail}
        self.rows.append(row)
        self.log(json.dumps(row, ensure_ascii=False))

    def finish(self):
        path = self.out / "summary" / f"{self.stage}.json"
        path.write_text(json.dumps(self.rows, ensure_ascii=False, indent=1), encoding="utf-8")
        self.log(f"# saved {path}")
        self.s.close()
        self.console.close()


def link_shape(link):
    """Describe an @odata.nextLink without its cursor value."""
    q = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
    out = {}
    for k, v in sorted(q.items()):
        out[k] = v[0] if k in ("$top", "$skip") else f"({len(v[0])} chars)"
    return out


def summarize_fetch(structured, rec):
    out = []
    for r in structured.get("results", []):
        d = r.get("data")
        item = {"statusCode": r.get("statusCode")}
        if isinstance(d, dict):
            if isinstance(d.get("value"), list):
                item["count"] = len(d["value"])
            if d.get("@odata.nextLink"):
                item["nextLink"] = link_shape(d["@odata.nextLink"])
            if "error" in d:
                e = d["error"]
                item["error"] = {"code": e.get("code"), "message": str(e.get("message"))[:400]} if isinstance(e, dict) else str(e)[:400]
        elif d is not None:
            item["data"] = str(d)[:400]
        for k in r:
            if k not in ("data", "statusCode"):
                item[k] = str(r[k])[:300]
        out.append(item)
    return out


def find_blob(value):
    """The object that carries base64Content, wherever it sits in structuredContent."""
    if isinstance(value, dict):
        if "base64Content" in value:
            return value
        for v in value.values():
            found = find_blob(v)
            if found is not None:
                return found
    return None


def summarize_blob(structured, rec):
    blob = find_blob(structured) or structured
    out = {k: blob.get(k) for k in ("statusCode", "contentType", "sizeBytes", "decodedBytes", "base64Chars", "sha256", "decodeError") if k in blob}
    out["keys"] = sorted(blob)
    for k in blob:
        if "preview" in k.lower():
            out[k + "_chars"] = len(blob[k]) if isinstance(blob[k], str) else len(json.dumps(blob[k], ensure_ascii=False))
    return out


def retrieval(rec):
    sc = ((rec.get("response") or {}).get("result") or {}).get("structuredContent") or {}
    return sc.get(RETRIEVAL) or {}


FIELD = re.compile(r"^  - \*\*([a-z][A-Za-z]{1,30}):\*\* ?", re.M)  # a line such as "  - **truncationInfo:** Content has been truncated"


def markdown_fields(markdown):
    """results[].markdown is a title line followed by '  - **field:** value' lines. Return {field: characters of its value}."""
    marks = list(FIELD.finditer(markdown))
    out = {}
    for m, nxt in zip(marks, marks[1:] + [None]):
        value = markdown[m.end():nxt.start() if nxt else len(markdown)].strip()
        out[m.group(1)] = len(value) if m.group(1) != "truncationInfo" else value[:120]  # truncationInfo is written by the service: keep its text
    return out


def summarize_retrieve(structured, rec):
    """Counts, sizes and type names of a retrieve answer; no text of any result."""
    body = structured.get(RETRIEVAL) or {}
    results = body.get("results") or []
    meta = body.get("searchMetadata")  # an object with strategy grounding, a list of such objects with strategy copilot
    metas = [m for m in (meta if isinstance(meta, list) else [meta]) if isinstance(m, dict)]
    kinds = {}
    months = []
    for x in results:
        for kind, fields in (x.get("resourceMetadata") or {}).items():
            kinds.setdefault(kind, set()).update(fields if isinstance(fields, dict) else [])
            for name, v in (fields.items() if isinstance(fields, dict) else []):
                if name.lower().endswith("time") and isinstance(v, str):
                    iso, us = re.match(r"(\d{4})-(\d{2})", v), re.match(r"(\d{1,2})/\d{1,2}/(\d{4})", v)  # 2026-11-17 or 11/17/2026
                    if iso or us:
                        months.append(f"{iso.group(1)}-{iso.group(2)}" if iso else f"{us.group(2)}-{int(us.group(1)):02d}")
    out = {"resultCount": body.get("resultCount"), "results": len(results), "stoppedReason": body.get("stoppedReason"),
           "markdown_chars_each": [len(x.get("markdown") or "") for x in results],
           "markdown_chars_total": sum(len(x.get("markdown") or "") for x in results),
           "markdown_fields_each": [markdown_fields(x.get("markdown") or "") for x in results],
           "starts_with_untrusted_notice": sum((x.get("markdown") or "").startswith(str(structured.get("@workiq.untrustedContent"))) for x in results),
           "entityType_each": [x.get("entityType") for x in results],
           "contentProtection_each": [x.get("contentProtection") for x in results],
           "encrypted_each": [(x.get("sensitivityLabel") or {}).get("isEncrypted") for x in results],
           "result_keys": sorted({k for x in results for k in x}),
           "metadata_fields": {k: sorted(v) for k, v in sorted(kinds.items())},
           "months": sorted(set(months)),
           "searchMetadata": [{"types": m.get("types"), "totalResults": m.get("totalResults"), "actualResults": m.get("actualResults"),
                               "searchTerms": len(m.get("searchTerms") or [])} for m in metas],
           "searchMetadata_is": type(meta).__name__ if meta is not None else None,
           "other_keys": sorted(k for k in body if k not in ("results", "resultCount", "searchMetadata", "stoppedReason"))}
    extra = sorted(k for k in structured if k not in (RETRIEVAL, "@workiq.untrustedContent"))
    if extra:
        out["structuredContent_other_keys"] = {k: len(json.dumps(structured[k], ensure_ascii=False)) for k in extra}
    return out


SUMMARIZERS = {"fetch": summarize_fetch, "fetch_blob": summarize_blob, "retrieve": summarize_retrieve,
               "call_function": lambda sc, rec: {"keys": sorted(sc)}}


def compact_blob(rec):
    """Replace the Base64 payload by its size and SHA-256 so that megabytes are not written to disk twice."""
    sc = find_blob(((rec.get("response") or {}).get("result") or {}).get("structuredContent"))
    if isinstance(sc, dict) and isinstance(sc.get("base64Content"), str):
        b64 = sc["base64Content"]
        try:
            raw = base64.b64decode(b64)
            sc["sha256"], sc["decodedBytes"] = hashlib.sha256(raw).hexdigest(), len(raw)
        except Exception as e:
            sc["decodeError"] = str(e)
        sc["base64Chars"] = len(b64)
        sc["base64Content"] = f"<{len(b64)} Base64 characters removed>"
        rec["response_text"] = f"<{rec['response_bytes']} bytes; Base64 payload removed, see response.result.structuredContent>"
    return rec


def first_value(rec, index=0):
    sc = ((rec.get("response") or {}).get("result") or {}).get("structuredContent") or {}
    results = sc.get("results") or []
    data = results[index].get("data") if len(results) > index else None
    return data if isinstance(data, dict) else {}


def relative(link):
    return link[len(GRAPH):] if link.startswith(GRAPH) else link


def ids(rec):
    return [m.get("id") for m in first_value(rec).get("value", [])]


def stage_mail(r):
    base = "/me/messages?$select=id"
    r.call("mail_01_no_top", "fetch", {"entityUrls": [base]}, "collection without $top: how many items come back")
    by_top = {}
    for top in (25, 26, 100, 101, 1000):
        by_top[top], _ = r.call(f"mail_02_top_{top}", "fetch", {"entityUrls": [f"{base}&$top={top}"]}, f"$top={top}")
    skip, _ = r.call("mail_03_skip", "fetch", {"entityUrls": [f"{base}&$top=5&$skip=5"]}, "$skip in the request")
    r.check("$skip=5 returns items 6 to 10 of the list", ids(skip) == ids(by_top[25])[5:10] and len(ids(skip)) == 5,
            "IDs of mail_03_skip compared with positions 6-10 of mail_02_top_25")
    token, _ = r.call("mail_04_skiptoken", "fetch", {"entityUrls": [f"{base}&$top=5&$skiptoken=abc"]}, "a made-up $skiptoken in the request")
    r.check("a made-up $skiptoken is ignored (first page comes back)", ids(token) == ids(by_top[25])[:5] and len(ids(token)) == 5,
            "IDs of mail_04_skiptoken compared with positions 1-5 of mail_02_top_25")
    link = first_value(by_top[100]).get("@odata.nextLink")
    if link:
        page2, _ = r.call("mail_05_follow_nextlink", "fetch", {"entityUrls": [relative(link)]},
                          "the @odata.nextLink of the $top=100 answer, sent back as a path",
                          shown={"entityUrls": ["<@odata.nextLink of mail_02_top_100, host removed>"], "nextLink": link_shape(link)})
        r.check("page 2 holds 100 other messages", len(ids(page2)) == 100 and not set(ids(page2)) & set(ids(by_top[100])),
                "IDs of mail_05_follow_nextlink compared with mail_02_top_100")
    else:
        r.log("# mail_05 skipped: the $top=100 answer carried no @odata.nextLink")
    oldest, _ = r.call("mail_06_oldest", "fetch", {"entityUrls": ["/me/messages?$select=id,receivedDateTime&$top=1&$orderby=receivedDateTime asc"]},
                       "oldest message the tool reaches")
    first = (first_value(oldest).get("value") or [{}])[0].get("receivedDateTime", "")
    r.check("month of the oldest message returned", first[:7], "receivedDateTime of mail_06_oldest, cut to year and month")
    r.call("mail_07_filter_date", "fetch", {"entityUrls": ["/me/messages?$select=id,receivedDateTime&$top=5&$filter=receivedDateTime lt 2025-01-01T00:00:00Z"]},
           "$filter on a date")
    search, _ = r.call("mail_08_search", "fetch", {"entityUrls": ['/me/messages?$select=id&$top=5&$search="Ignite"']}, "$search")
    link = first_value(search).get("@odata.nextLink")
    if link:
        page2, _ = r.call("mail_09_search_follow_nextlink", "fetch", {"entityUrls": [relative(link)]},
                          "the @odata.nextLink of the $search answer (it carries a real $skiptoken), sent back as a path",
                          shown={"entityUrls": ["<@odata.nextLink of mail_08_search, host removed>"], "nextLink": link_shape(link)})
        r.check("page 2 of the $search holds other messages", bool(ids(page2)) and not set(ids(page2)) & set(ids(search)),
                f"{len(ids(page2))} IDs of mail_09 compared with mail_08_search")
    r.call("mail_10_skip_5000", "fetch", {"entityUrls": [f"{base}&$top=5&$skip=5000"]}, "a deep $skip")


def stage_chat(r):
    rec, _ = r.call("chat_01_list", "fetch", {"entityUrls": ["/me/chats?$select=id,chatType&$top=5"]}, "my chats")
    chats = [c["id"] for c in first_value(rec).get("value", [])]
    chats = (["48:notes"] + chats)[:3]
    for n, cid in enumerate(chats, 1):
        path = f"/me/chats/{cid}/messages"
        shown = "/me/chats/{chat-id}/messages"
        rec0, _ = r.call(f"chat_02_{n}_no_top", "fetch", {"entityUrls": [path]}, "chat messages without $top", shown={"entityUrls": [shown]})
        for top in (10, 11, 50) + ((20, 21) if n == 1 else ()):
            rec_top, _ = r.call(f"chat_03_{n}_top_{top}", "fetch", {"entityUrls": [f"{path}?$top={top}"]}, f"chat messages, $top={top}",
                                shown={"entityUrls": [f"{shown}?$top={top}"]})
            if top == 10:
                rec0 = rec_top
        if n == 1:
            r.call("chat_05_1_other_path_top_50", "fetch", {"entityUrls": [f"/chats/{cid}/messages?$top=50"]},
                   "the same chat addressed as /chats/{id} instead of /me/chats/{id}, $top=50", shown={"entityUrls": ["/chats/{chat-id}/messages?$top=50"]})
        link = first_value(rec0).get("@odata.nextLink")
        if link:
            r.call(f"chat_04_{n}_follow_nextlink", "fetch", {"entityUrls": [relative(link)]}, "the @odata.nextLink of the $top=10 answer, sent back as a path",
                   shown={"entityUrls": ["<@odata.nextLink of the $top=10 answer, host removed>"], "nextLink": link_shape(link)})
        else:
            r.log(f"# chat_04_{n} skipped: no @odata.nextLink in the $top=10 answer")


def stage_multi(r):
    def works(n):
        _, row = r.call(f"multi_{n:03d}_paths", "fetch", {"entityUrls": ["/me?$select=id"] * n},
                        f"{n} paths in one call (the same light path {n} times)", shown={"entityUrls": f"['/me?$select=id'] x {n}"})
        res = row.get("result")
        return not row.get("is_error") and isinstance(res, list) and len(res) == n and all(x.get("statusCode") == 200 for x in res)

    ok, bad = 0, None
    for n in (2, 20, 50, 100, 200, 400):
        if works(n):
            ok = n
        else:
            bad = n
            break
    while bad and bad - ok > 1:  # bisect between the largest count that worked and the smallest that failed
        mid = (ok + bad) // 2
        if works(mid):
            ok = mid
        else:
            bad = mid
    r.check("largest number of paths one fetch call answered", ok, f"smallest number that failed: {bad}")


def stage_body(r):
    rec, row = r.call("body_01_25_messages", "fetch", {"entityUrls": ["/me/messages?$select=id,bodyPreview,body&$top=25"]},
                      "25 newest messages with their full body")
    sizes = sorted((len((m.get("body") or {}).get("content", "")), len(m.get("bodyPreview", ""))) for m in first_value(rec).get("value", []))
    if sizes:
        r.check("characters of body.content per message, 25 newest messages", {"smallest": sizes[0][0], "largest": sizes[-1][0]},
                "body.content is the message as stored (HTML for most mail)")
        r.check("characters of bodyPreview per message, 25 newest messages", {"smallest": min(s[1] for s in sizes), "largest": max(s[1] for s in sizes)},
                "bodyPreview is the short preview field of Microsoft Graph")
    rec, row = r.call("body_02_100_messages", "fetch", {"entityUrls": ["/me/messages?$select=id,body&$top=100"]},
                      "100 messages with their full body: is the size of one answer capped", timeout=600)
    bodies = [m.get("body") or {} for m in first_value(rec).get("value", [])]
    sizes = sorted(len(b.get("content", "")) for b in bodies)
    if sizes:
        html_bodies = [b.get("content", "") for b in bodies if b.get("contentType") == "html" and b.get("content", "").strip()]
        r.check("100 messages with their full body in one answer",
                {"bodies": len(sizes), "empty_bodies": sum(n == 0 for n in sizes), "characters_in_total": sum(sizes), "largest_body_characters": sizes[-1],
                 "answer_bytes": row.get("response_bytes"), "html_bodies_with_text": len(html_bodies),
                 "html_bodies_that_end_with_the_closing_html_tag": sum(c.rstrip().lower().endswith("</html>") for c in html_bodies)},
                "an HTML body that ends with </html> was not cut at the end")


COLLECTIONS = (("events", "/me/events"), ("inbox", "/me/mailFolders/inbox/messages"), ("drive_children", "/me/drive/root/children"),
               ("people", "/me/people"), ("chats", "/me/chats"))


def stage_collections(r):
    for name, path in COLLECTIONS:
        r.call(f"coll_{name}_no_top", "fetch", {"entityUrls": [f"{path}?$select=id"]}, f"{path} without $top")
        r.call(f"coll_{name}_top_101", "fetch", {"entityUrls": [f"{path}?$select=id&$top=101"]}, f"{path}, $top=101")


BLOB_SIZES = (1_000, 3_900_000, 4_000_000, 4_000_001, 4_194_304, 4_194_305, 5_000_000)


def blob_bytes(n):
    """n bytes of numbered text lines; the same n always gives the same bytes."""
    lines, size, i = [], 0, 0
    while size < n:
        line = f"{i:09d} Work IQ fetch_blob size test. Synthetic text, no real data.\n".encode("ascii")
        lines.append(line)
        size += len(line)
        i += 1
    return b"".join(lines)[:n]


def drive_path(folder):
    """Path of a local OneDrive folder inside the drive, for example /Desktop/x/blob_test."""
    folder = pathlib.Path(folder).resolve()
    for var in ("OneDriveCommercial", "OneDrive"):
        root = os.environ.get(var)
        if root and folder.is_relative_to(pathlib.Path(root).resolve()):
            return "/" + folder.relative_to(pathlib.Path(root).resolve()).as_posix()
    raise SystemExit(f"{folder} is not inside a OneDrive folder of this PC. Pass --blob-dir <a folder that OneDrive syncs>.")


def stage_blob(r):
    """Read files of known size back with fetch_blob and compare the SHA-256 with the local file.
    Default: synthetic text files written into <blob-dir>, which OneDrive has to upload first.
    --blob-files: local files that OneDrive has already uploaded (any type); only size, extension and hash are reported."""
    if r.blob_files:
        files = r.blob_files
    else:
        r.blob_dir.mkdir(parents=True, exist_ok=True)
        files = []
        for n in BLOB_SIZES:
            f = r.blob_dir / f"blob_{n}.txt"
            if not f.exists() or f.stat().st_size != n:
                f.write_bytes(blob_bytes(n))
            files.append(f)
        r.log(f"# {len(files)} synthetic text files in {r.blob_dir}")
    local = []
    for f in files:
        data = f.read_bytes()
        local.append({"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "ext": f.suffix.lower() or "(none)"})
    paths = ["/me/drive/root:" + urllib.parse.quote(drive_path(f)) + "?$select=id,size" for f in files]
    shown = {"entityUrls": f"['/me/drive/root:/<path of the file in OneDrive>?$select=id,size'] x {len(paths)}"}
    items = [{}] * len(files)
    for attempt in range(1, 2 if r.blob_files else 7):
        rec, _ = r.call(f"blob_00_items_{attempt:02d}", "fetch", {"entityUrls": paths}, "the test files in OneDrive: ID and size of each",
                        shown=shown, fresh=not r.blob_files)
        items = [first_value(rec, i) for i in range(len(files))]
        uploaded = sum(it.get("size") == lo["bytes"] for it, lo in zip(items, local))
        if uploaded == len(files) or r.blob_files:
            break
        r.log(f"# {uploaded} of {len(files)} files are in OneDrive with their full size; next look in 20 s")
        time.sleep(20)
    r.check("test files found in OneDrive with the size of the local file", sum(it.get("size") == lo["bytes"] for it, lo in zip(items, local)),
            f"of {len(files)}; a file that OneDrive has not uploaded (or stores with another size) is skipped")
    full, refused = [], []
    for it, lo in sorted(zip(items, local), key=lambda p: p[1]["bytes"]):
        n = lo["bytes"]
        if it.get("size") != n:
            r.log(f"# {lo['ext']} file of {n:,} bytes skipped: OneDrive reports size {it.get('size')}")
            continue
        rec, row = r.call(f"blob_01_{n}_bytes", "fetch_blob", {"path": f"/me/drive/items/{it['id']}/content"}, f"a {lo['ext']} file of {n:,} bytes",
                          timeout=600, shown={"path": "/me/drive/items/{item-id}/content"})
        res = row.get("result") or {}
        same = res.get("sha256") == lo["sha256"] and res.get("decodedBytes") == n
        r.check(f"{n:,} bytes: the decoded content is byte-identical to the local file", same,
                f"sizeBytes {res.get('sizeBytes')}, decoded {res.get('decodedBytes')}, isError {row.get('is_error')}")
        (full if same else refused).append(n)
    r.check("largest file returned in full (bytes)", max(full) if full else None, f"smallest file not returned in full: {min(refused) if refused else None}")


QUESTION = "What was announced about Work IQ at Microsoft Ignite 2026?"
CAPABILITIES = ("Email", "OneDriveAndSharePoint", "TeamsMessages", "Meetings", "People")


def long_query(n):
    parts, i = [QUESTION, "Also consider these numbered topics:"], 1
    while len(" ".join(parts)) < n:
        parts.append(f"topic {i} of the Ignite 2026 agenda,")
        i += 1
    return " ".join(parts)[:n]


def sources(rec):
    return [x.get("entityUrl") or x.get("resourceId") for x in retrieval(rec).get("results") or []]


def stage_retrieve(r):
    first, _ = r.call("retrieve_01_question", "retrieve", {"query": QUESTION}, "a question in English; all sources; default strategy")
    again, _ = r.call("retrieve_02_same_again", "retrieve", {"query": QUESTION}, "the same call a second time")
    r.check("the same query returns the same sources in the same order", sources(first) == sources(again),
            f"{len(sources(first))} and {len(sources(again))} sources; {len(set(sources(first)) & set(sources(again)))} in both answers")
    r.call("retrieve_03_keywords", "retrieve", {"query": "Work IQ MCP retrieve tool"}, "keywords instead of a sentence")
    r.call("retrieve_03_keywords_again", "retrieve", {"query": "Work IQ MCP retrieve tool"}, "the keyword query a second time")
    r.call("retrieve_04_chinese", "retrieve", {"query": "微软 Ignite 2026 大会上关于 Work IQ 发布了什么？"}, "the question in Chinese")
    r.call("retrieve_05_strategy_copilot", "retrieve", {"query": QUESTION, "strategy": "copilot"}, "strategy=copilot")
    for cap in CAPABILITIES:
        r.call(f"retrieve_06_only_{cap}", "retrieve", {"query": QUESTION, "capabilities": [{"name": cap}]}, f"capabilities limited to {cap}")
    r.call("retrieve_07_top_50", "retrieve", {"query": QUESTION, "top": 50}, "top=50, a parameter the tool schema does not list")
    r.call("retrieve_08_ask_for_50", "retrieve", {"query": QUESTION + " Return 50 results."}, "asking for 50 results inside the query text")
    r.call("retrieve_08_ask_for_100", "retrieve", {"query": QUESTION + " Return 100 results."}, "asking for 100 results inside the query text")
    for n in (1600, 6000):
        r.call(f"retrieve_09_query_{n}_chars", "retrieve", {"query": long_query(n)}, f"a query of {n:,} characters", shown={"query": f"({n} characters)"})
    r.call("retrieve_10_developer_card", "retrieve", {"query": QUESTION, "includeDeveloperCard": True}, "includeDeveloperCard=true")
    r.call("retrieve_11_old_mail", "retrieve", {"query": "Which emails did I receive in 2023 about Azure OpenAI?", "capabilities": [{"name": "Email"}]},
           "a question about 2023, email only: how far back do the results go")
    r.call("retrieve_12_bad_strategy", "retrieve", {"query": QUESTION, "strategy": "all"}, "a strategy value the schema does not list")
    r.call("retrieve_13_empty_query", "retrieve", {"query": ""}, "an empty query")
    r.call("retrieve_14_week_english", "retrieve", {"query": "What important emails did I receive in the last week?"}, "a second question, in English")
    r.call("retrieve_14_week_chinese", "retrieve", {"query": "最近一周我收到了哪些重要邮件？"}, "the second question in Chinese")


TAGS = re.compile(r"<(script|style)\b.*?</\1>|<!--.*?-->|<[^>]+>", re.S | re.I)


def squeeze(text):
    """Lower case, without white space and without markdown punctuation, so that two renderings of one text compare."""
    return re.sub(r"[\s\\*_`#>\[\]()|~-]+", "", text).lower()


def coverage(markdown, full_text, probes=21, width=16):
    """Cut `probes` short pieces out of the full text at even distances; report which of them the markdown holds."""
    md, full = squeeze(markdown), squeeze(full_text)
    if len(full) < width * 2:
        return None
    hits = []
    for i in range(probes):
        start = (len(full) - width) * i // (probes - 1)
        hits.append(full[start:start + width] in md)
    last = max((i for i, h in enumerate(hits) if h), default=None)
    return {"pieces_found": sum(hits), "pieces": probes, "last_piece_found_at_percent": None if last is None else round(100 * last / (probes - 1)),
            "full_text_chars": len(full), "markdown_chars": len(md)}


def stage_fulltext(r):
    """Is results[].markdown the whole item or an extract? Read every item a retrieve call returned with fetch and compare.
    Emails and chat messages: their body text against the markdown. Files: their size in bytes against the markdown length."""
    by_source, rows = {}, []
    for f in sorted(r.raw.glob("retrieve_*.json")):
        for x in retrieval(json.loads(f.read_text(encoding="utf-8"))).get("results") or []:
            url = relative(x.get("entityUrl") or "")
            if not url:
                continue
            if url not in by_source:
                rows.append((f.stem, x.get("entityType"), url, x.get("markdown") or ""))
            by_source.setdefault(url, []).append(len(x.get("markdown") or ""))
    if not rows:
        r.log("# no saved retrieve result with an entityUrl: run the retrieve stage first")
        return
    repeated = [sizes for sizes in by_source.values() if len(sizes) > 1]
    r.check("sources that came back in more than one retrieve call", len(repeated),
            f"of {len(by_source)} different sources; {sum(len(set(s)) > 1 for s in repeated)} of them came back with markdown of different lengths")
    rows = rows[:50]  # one fetch call takes at most 50 paths
    is_message = [bool(re.search(r"/messages/", u)) for _, _, u, _ in rows]
    paths = [u + "?$select=" + ("id,body" if m else "id,size,file") for (_, _, u, _), m in zip(rows, is_message)]
    saved = r.raw / "fulltext_01_items.json"
    stale = saved.exists() and json.loads(saved.read_text(encoding="utf-8")).get("arguments", {}).get("entityUrls") != paths
    rec, _ = r.call("fulltext_01_items", "fetch", {"entityUrls": paths}, f"the {len(rows)} different items that retrieve returned, read with fetch",
                    timeout=600, fresh=stale,  # a record made for another list of items is not reused
                    shown={"entityUrls": f"['<entityUrl of a retrieve result>?$select=id,body (message) or id,size,file (file)'] x {len(rows)}"})
    whole = partial = 0
    for i, ((case, kind, url, md), message) in enumerate(zip(rows, is_message)):
        data = first_value(rec, i)
        where = f"result {i + 1} ({kind}, first seen in {case})"
        fields = markdown_fields(md)
        mark = {"marked_truncated": "truncationInfo" in fields, "snippet_chars": fields.get("snippet")}
        if not data:
            r.check(f"{where}: could not be read with fetch", None, "see the raw record for the status code")
        elif message:
            body = data.get("body") or {}
            cov = coverage(md, html.unescape(TAGS.sub(" ", body.get("content") or "")))
            if cov:
                whole += cov["pieces_found"] >= cov["pieces"] - 2
                partial += cov["pieces_found"] < cov["pieces"] - 2
            r.check(f"{where}: how much of the message body is in results[].markdown", (cov | mark) if cov else None,
                    "21 pieces of 16 characters, cut at even distances from the body text read with fetch")
        else:
            r.check(f"{where}: file size against markdown length",
                    {"file_bytes": data.get("size"), "mimeType": (data.get("file") or {}).get("mimeType"), "markdown_chars": len(md)} | mark, "")
    r.check("messages whose body is in the markdown from start to end (at least 19 of 21 pieces)", whole, f"messages with less: {partial}")


STAGES = {"mail": stage_mail, "collections": stage_collections, "chat": stage_chat, "multi": stage_multi, "body": stage_body,
          "blob": stage_blob, "retrieve": stage_retrieve, "fulltext": stage_fulltext}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("stage", choices=list(STAGES))
    ap.add_argument("--out", required=True, help="private evidence folder of this run")
    ap.add_argument("--reuse", action="store_true", help="do not send a call whose record already exists in <out>/raw")
    ap.add_argument("--blob-dir", help="blob stage: local folder inside OneDrive for the synthetic test files (default <out>/blob_test)")
    ap.add_argument("--blob-files", nargs="+", help="blob stage: local files that OneDrive has already uploaded, used instead of synthetic files")
    ap.add_argument("--blob-files-from", help="blob stage: UTF-8 text file with one such local file per line")
    a = ap.parse_args()
    blob_files = list(a.blob_files or [])
    if a.blob_files_from:
        blob_files += [line.strip() for line in pathlib.Path(a.blob_files_from).read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    r = Run(a.out, a.stage, a.reuse, a.blob_dir, blob_files)
    try:
        STAGES[a.stage](r)
    finally:
        r.finish()
    return 0


if __name__ == "__main__":
    sys.exit(main())
