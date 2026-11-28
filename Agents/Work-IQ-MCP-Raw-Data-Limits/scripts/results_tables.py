"""Print the per-call tables of a run as Markdown, from its summaries (counts, sizes, field names and error texts only).

  python scripts/results_tables.py results            the tables of docs/RESULTS.md, from the published run
  python scripts/results_tables.py <out> --lang zh    the same tables for your own run, with Chinese headers
  python scripts/results_tables.py results --update docs/RESULTS.md    refresh the tables inside that page
The tables in docs/RESULTS.md and docs/RESULTS_CN.md are the output of this script; tests/test_offline.py compares them.
"""
import argparse
import json
import pathlib
import re
import sys

TABLES = ("lists", "paths", "files", "retrieve", "types", "readback")
EXT = {"presentationml.presentation": ".pptx", "wordprocessingml.document": ".docx", "spreadsheetml.sheet": ".xlsx", "application/pdf": ".pdf",
       "video/mp4": ".mp4", "application/xml": ".xml", "application/json": ".json", "image/png": ".png", "text/html": ".html"}
TEXT = {
    "en": {"none": "none", "yes": "yes", "no": "no", "identical": "identical to the local file", "refused": "refused: “{e}”", "results200": "{n} results, each with status 200",
           "chars": "{n} characters of text", "bytes": "{n} bytes, {ext}", "no_snippet": "no `snippet` field", "of": "{k} of {n}", "error": "error: {t}",
           "next_of": "<@odata.nextLink of {c}, host removed>",
           "lists": ["Call", "Path sent to `fetch`", "Status of the path", "Items returned", "Next-page link carries", "Note or error from the service"],
           "paths": ["Call", "Paths in one call", "What came back"],
           "files": ["Call", "File size (bytes)", "File type", "`contentType` in the answer", "Result", "Time (seconds)", "Base64 characters in the answer", "Size of the answer (bytes)"],
           "retrieve": ["Call", "What was asked", "Time (seconds)", "Results returned", "Types of the results", "`snippet` characters, shortest to longest",
                        "Results marked `Content has been truncated`", "`markdown` characters in total", "Size of the answer (bytes)"],
           "types": ["Type of result (`entityType`)", "Results", "`markdown` characters, shortest to longest", "`snippet` characters, shortest to longest",
                     "Results marked `Content has been truncated`", "Fields in `markdown` (number of results when not in all)"],
           "readback": ["Item", "Type of result", "First returned by", "Whole item, read with `fetch`", "`snippet` characters in the result",
                        "Marked `Content has been truncated`", "Samples of the body found in the result"]},
    "zh": {"none": "无", "yes": "是", "no": "否", "identical": "与本机文件完全一致", "refused": "拒绝：“{e}”", "results200": "{n} 个结果，状态码都是 200",
           "chars": "正文 {n} 个字符", "bytes": "{n} 字节，{ext}", "no_snippet": "没有 `snippet` 字段", "of": "{n} 个里找到 {k} 个", "error": "报错：{t}",
           "next_of": "<{c} 响应里的 @odata.nextLink，去掉主机名>",
           "lists": ["调用", "发给 `fetch` 的路径", "该路径的状态码", "返回条数", "下一页链接带的参数", "服务给的提示或报错"],
           "paths": ["调用", "一次调用里的路径数", "返回了什么"],
           "files": ["调用", "文件大小（字节）", "文件类型", "响应里的 `contentType`", "结果", "用时（秒）", "响应里的 Base64 字符数", "响应大小（字节）"],
           "retrieve": ["调用", "问了什么", "用时（秒）", "返回的结果条数", "结果的类型", "`snippet` 字符数，最短到最长",
                        "被标 `Content has been truncated` 的条数", "`markdown` 字符数合计", "响应大小（字节）"],
           "types": ["结果类型（`entityType`）", "结果条数", "`markdown` 字符数，最短到最长", "`snippet` 字符数，最短到最长",
                     "被标 `Content has been truncated` 的条数", "`markdown` 里的字段（不是每条都有的，括号里是条数）"],
           "readback": ["原件", "结果类型", "最早由哪次调用返回", "用 `fetch` 读回的原件", "结果里 `snippet` 的字符数",
                        "是否被标 `Content has been truncated`", "正文采样片段在结果里找到几个"]},
}
ASKED_ZH = {"retrieve_01_question": "英文问题；全部来源；默认策略", "retrieve_02_same_again": "同一个调用再发一次", "retrieve_03_keywords": "把问句换成关键词",
            "retrieve_03_keywords_again": "关键词查询再发一次", "retrieve_04_chinese": "同一个问题用中文问", "retrieve_07_top_50": "top=50，工具没有列出的参数",
            "retrieve_08_ask_for_50": "在问题里要 50 条结果", "retrieve_08_ask_for_100": "在问题里要 100 条结果", "retrieve_09_query_1600_chars": "1,600 个字符的查询",
            "retrieve_09_query_6000_chars": "6,000 个字符的查询", "retrieve_11_old_mail": "问 2023 年的邮件，只搜邮件：结果能回溯多远",
            "retrieve_12_bad_strategy": "strategy 取一个工具没有列出的值", "retrieve_13_empty_query": "空查询", "retrieve_14_week_english": "第二个问题，英文",
            "retrieve_14_week_chinese": "第二个问题，中文"}


def n(value):
    return f"{value:,}" if isinstance(value, (int, float)) else str(value)


def span(values):
    """'1,733 to 1,802' as '1,733–1,802'; one value alone; a dash for none."""
    values = [v for v in values if v is not None]
    if not values:
        return "—"
    return n(min(values)) if min(values) == max(values) else f"{n(min(values))}–{n(max(values))}"


def table(header, rows):
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    return "\n".join(lines + ["| " + " | ".join(str(c) for c in row) + " |" for row in rows])


def load(folder, name):
    return json.loads((pathlib.Path(folder) / "summary" / f"{name}.json").read_text(encoding="utf-8"))


def calls(folder, stage):
    return [r for r in load(folder, stage) if "case" in r]


def error_message(text):
    found = re.search(r"'message': \"(.*?)\"", text) or re.search(r"'message': '(.*?)'", text)
    return found.group(1) if found else text[:160]


def lists(folder, t):
    rows = []
    for stage in ("mail", "collections", "chat"):
        for r in calls(folder, stage):
            x = r["result"][0] if isinstance(r.get("result"), list) and r["result"] else {}
            path = r["arguments"]["entityUrls"][0]
            source = re.fullmatch(r"<@odata\.nextLink of (.+), host removed>", path)
            if source:
                path = t["next_of"].format(c=source.group(1).replace("the $top=10 answer", r["case"].replace("chat_04", "chat_03").replace("follow_nextlink", "top_10")))
            link = x.get("nextLink") or {}
            carries = ", ".join(f"`{k}={v}`" if k in ("$top", "$skip") else f"`{k}`" for k, v in link.items() if k in ("$top", "$skip", "$skiptoken")) or t["none"]
            note = (r.get("service_note") or "").split(". ")[0]
            if x.get("error"):
                note = t["error"].format(t=error_message(str(x["error"])))
            rows.append([f"`{r['case']}`", f"`{path}`", x.get("statusCode", "—"), n(x["count"]) if "count" in x else "—", carries, note or t["none"]])
    return table(t["lists"], rows)


def paths(folder, t):
    rows = []
    for r in calls(folder, "multi"):
        res = r.get("result")
        if r.get("is_error"):
            back = f"`{json.loads(r['text'][0]).get('errorCode')}`"
        else:
            back = t["results200"].format(n=len(res)) if all(x.get("statusCode") == 200 for x in res) else ", ".join(str(x.get("statusCode")) for x in res)
        rows.append([f"`{r['case']}`", int(r["case"].split("_")[1]), back])
    return table(t["paths"], rows)


def files(folder, t):
    rows = []
    for r in sorted((r for r in calls(folder, "blob") if r["case"].startswith("blob_01_")), key=lambda r: int(r["case"].split("_")[2])):
        res = r.get("result") or {}
        result = t["identical"] if res.get("decodedBytes") == int(r["case"].split("_")[2]) else t["refused"].format(e=json.loads(r["text"][0]).get("error"))
        rows.append([f"`{r['case']}`", n(int(r["case"].split("_")[2])), r["note"].split()[1], f"`{res['contentType']}`" if res.get("contentType") else "—", result,
                     f"{r['ms'] / 1000:.1f}", n(res["base64Chars"]) if res.get("base64Chars") else "—", n(r["response_bytes"])])
    return table(t["files"], rows)


def retrieve(folder, t):
    rows = []
    for r in calls(folder, "retrieve"):
        asked = ASKED_ZH.get(r["case"], r["note"]) if t is TEXT["zh"] else r["note"]
        if t is TEXT["zh"] and r["case"].startswith("retrieve_06_only_"):
            asked = "只搜 " + r["case"].split("_only_")[1]
        res = r.get("result")
        if not isinstance(res, dict):
            rows.append([f"`{r['case']}`", asked, f"{r['ms'] / 1000:.1f}", "—", t["error"].format(t=json.loads(r["text"][0]).get("error")), "—", "—", "—", n(r["response_bytes"])])
            continue
        kinds = {}
        for kind in res["entityType_each"]:
            kinds[kind] = kinds.get(kind, 0) + 1
        rows.append([f"`{r['case']}`", asked, f"{r['ms'] / 1000:.1f}", res["results"], ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())) or "—",
                     span([f.get("snippet") for f in res["markdown_fields_each"]]), sum("truncationInfo" in f for f in res["markdown_fields_each"]),
                     n(res["markdown_chars_total"]), n(r["response_bytes"])])
    return table(t["retrieve"], rows)


def types(folder, t):
    rows = []
    for kind, f in sorted(load(folder, "retrieve_fields").items()):
        names = sorted(f["fields"], key=lambda name: (-f["fields"][name]["in_results"], name))
        fields = ", ".join(f"`{name}`" + ("" if f["fields"][name]["in_results"] == f["results"] else f" ({f['fields'][name]['in_results']})") for name in names)
        snippet = f["fields"].get("snippet")
        rows.append([kind, f["results"], span([f["markdown_chars_min"], f["markdown_chars_max"]]), span([snippet["chars_min"], snippet["chars_max"]]) if snippet else "—",
                     f["truncationInfo"].get("Content has been truncated", 0), fields])
    return table(t["types"], rows)


def readback(folder, t):
    rows = []
    for r in load(folder, "fulltext"):
        found = re.match(r"result (\d+) \((\w+), first seen in (\w+)\)", r.get("check", ""))
        v = r.get("value")
        if not found or not isinstance(v, dict):
            continue
        if "file_bytes" in v:
            ext = next((e for key, e in EXT.items() if key in (v.get("mimeType") or "")), v.get("mimeType") or "?")
            whole, samples = t["bytes"].format(n=n(v["file_bytes"]), ext=ext), "—"
        else:
            whole, samples = t["chars"].format(n=n(v["full_text_chars"])), t["of"].format(k=v["pieces_found"], n=v["pieces"])
        rows.append([found.group(1), found.group(2), f"`{found.group(3)}`", whole, n(v["snippet_chars"]) if v.get("snippet_chars") else t["no_snippet"],
                     t["yes"] if v["marked_truncated"] else t["no"], samples])
    return table(t["readback"], rows)


def render(folder, name, lang="en"):
    return {"lists": lists, "paths": paths, "files": files, "retrieve": retrieve, "types": types, "readback": readback}[name](folder, TEXT[lang])


def update(page, folder, lang):
    """Replace the table that follows each '<!-- table: name -->' line of a Markdown page; return the names replaced."""
    lines, out, done, i = pathlib.Path(page).read_text(encoding="utf-8").split("\n"), [], [], 0
    while i < len(lines):
        out.append(lines[i])
        marker = re.fullmatch(r"<!-- table: (\w+) -->", lines[i].strip())
        i += 1
        if marker and marker.group(1) in TABLES:
            while i < len(lines) and lines[i].startswith("|"):
                i += 1  # the old table
            out += render(folder, marker.group(1), lang).split("\n")
            done.append(marker.group(1))
    pathlib.Path(page).write_text("\n".join(out), encoding="utf-8", newline="\n")
    return done


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("folder", help="folder that holds summary/*.json: results (the published run) or the evidence folder of your run")
    ap.add_argument("--lang", choices=("en", "zh"), default="en")
    ap.add_argument("--table", choices=TABLES, action="append", help="only this table; repeatable")
    ap.add_argument("--update", metavar="PAGE", help="write the tables into this Markdown page, after its '<!-- table: name -->' lines, instead of printing them")
    a = ap.parse_args()
    if a.update:
        print("tables written into", a.update + ":", ", ".join(update(a.update, a.folder, a.lang)) or "none (the page has no table marker)")
        return 0
    for name in a.table or TABLES:
        print(f"<!-- table: {name} -->\n{render(a.folder, name, a.lang)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
