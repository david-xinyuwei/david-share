# Testing

[中文](TESTING_CN.md) · back to the [README](../README.md)

This page says what each script does, what leaves the private folder of a run, what the offline tests check, how a screenshot is made, and what none of this proves. The measured results are in [RESULTS.md](RESULTS.md).

## The scripts

| Script | What it does | Calls Work IQ |
|---|---|---|
| `scripts/edge_cdp.py` | starts and controls the separate Edge profile over the DevTools Protocol: `start`, `targets`, `wake`, `eval`, `shot`, `open`, `close` | no |
| `scripts/demo_signin.py` | optional: clicks **Sign in to go live** and the account tile that Windows offers. It types no password and stops with `NEEDS_USER` at a password, MFA or consent page | no |
| `scripts/demo_runner.py` | library: types the tool arguments into the page's JSON editor, presses **Call tool** and takes the record of the call | yes, when a script uses it |
| `scripts/js/fetch_recorder.js` | runs inside the page: copies the request body, status, headers, timing and answer of each request to the MCP endpoint. It never reads the `Authorization` header | no |
| `scripts/call_once.py` | one call from a JSON file of arguments, or the tool list | one call |
| `scripts/run_limits.py` | the eight stages of the measurement | 78 calls plus one per file named |
| `scripts/summary_table.py` | one line per call, from the summaries of a run | no |
| `scripts/run_stats.py` | number of calls, times, status codes and throttling, from the records of a run | no |
| `scripts/retrieve_fields.py` | the fields of `results[].markdown` per result type | no |
| `scripts/build_results.py` | writes the public copy of a run: the summaries without file hashes and request IDs, and `limits.json` computed from them | no |
| `scripts/results_tables.py` | prints the tables of `docs/RESULTS` from the summaries, or writes them into the page | no |
| `scripts/shot_call.py`, `scripts/redact_shot.py`, `scripts/js/redact_rects.js` | a screenshot of the page during one call, and its public copy with IDs covered | one call per screenshot |
| `scripts/show_tools.py`, `scripts/show_shape.py`, `scripts/show_markdown_layout.py`, `scripts/shape.py` | look at a saved record without showing its content: tool list, structure, masked layout | no |

## What leaves the private folder

| Place | What it holds | May it be shared |
|---|---|---|
| `<out>/raw/` | per call: request, status, headers, timing and the complete answer. For `fetch_blob` the Base64 payload is replaced by its size and SHA-256 | no: it holds your mail, chats and file names |
| `<out>/summary/` and `<out>/console_<stage>.txt` | per call: arguments, time, counts, sizes, field names, error texts and the request ID that the service returned. An argument that holds an ID or a local path is replaced by a placeholder | read it first: it holds the text of your `retrieve` queries |
| `<out>/public/`, written by `build_results.py --results` | the summaries without the SHA-256 of your files and without the request IDs of the service, and `limits.json` | yes, after the same reading |
| `results/` of this repository | the same, for the published run | published |

The offline test `test_public_files_hold_no_ids_addresses_or_paths` searches `results/` and `cases/` for mail, chat and drive IDs, GUIDs (the form of request, object and tenant IDs), mail addresses, SharePoint hosts and local paths. It is a net for known patterns, not a proof that a file holds nothing private.

## Offline tests

```powershell
python -m unittest discover -s tests -v
```

The 28 tests call no service and open no browser. They feed the scripts with made-up answers of the shape the service returned on the test day, and they compare the published files with each other.

| Test class | Tests | What it asserts |
|---|---|---|
| `Replies` | 4 | a reply is read from plain JSON and from an event stream, where the last complete message counts; an incomplete reply is not taken; a tool answer is split into error flag, text parts and structured content |
| `Shapes` | 1 | the structure view keeps key names, counts, lengths and error texts and drops every other text |
| `FetchAnswers` | 3 | a next-page link is described by `$top` and `$skip` without the value of its cursor; the Graph host is removed from a link before it is sent back; the summary of an answer counts items, keeps the error of a failed path and holds no item content |
| `Blobs` | 3 | a synthetic test file has exactly the requested size and the same bytes on every run; the Base64 payload is found wherever it sits in an answer; it is replaced by its size and SHA-256 before the record is saved |
| `RetrieveAnswers` | 6 | the fields of a result's Markdown are read with their lengths and the text of `truncationInfo`; the summary of an answer holds counts, months and field names and no text of a result; both forms of `searchMetadata` are read; a long query has exactly the requested length; two texts compare without white space and Markdown marks; the 21-sample comparison tells a whole text from half of it |
| `Throttling` | 1 | throttling is counted from error texts and status `429` only, never from the content of a successful answer |
| `PublishedDataset` | 5 | `results/limits.json` equals what `build_results.py` computes from `results/summary/`; the public files hold no ID, address or path of the patterns above; the public copy of a row drops the file hash, the request ID of the row and a request ID inside an error text; every stage summary is published and the call totals add up; the case files are the calls shown in the screenshots |
| `Pages` | 4 | both READMEs quote 17 numbers of the dataset and the refusal text of `fetch_blob`; every local link, anchor and image of the seven pages exists; the English and the Chinese page show the same pictures, the same tables and the same number of headings; the tables of `docs/RESULTS` are what `results_tables.py` prints |
| `Images` | 1 | every PNG under `images/` is listed in `images/SOURCES.json` with its SHA-256 |

After a run of your own, `python scripts/results_tables.py <out>` prints the same tables for your tenant.

## How a screenshot is made

```powershell
python scripts/shot_call.py --tool fetch --args-file cases/fetch_skip.json --png "$out\shots\skip.png" --case shot_skip --out "$out\raw"
python -m pip install pillow
python scripts/redact_shot.py "$out\shots\skip.png" images/ui_skip.png
```

1. `shot_call.py` sends the call through the page, which is one more call. It then sets the page to 1,500 by 1,900 CSS pixels at scale 1.25, so that request and answer are visible together, and saves the PNG. Next to it, it saves the rectangle of every text on the page that matches an ID pattern: mail ID, drive item ID, chat ID, ETag, and every GUID, which covers the user's object ID and the request IDs of the service.
2. `redact_shot.py` paints a grey box over each rectangle and cuts the picture below the last row that has dark pixels. Nothing else in the picture is changed.
3. The original stays in the private folder. [`images/SOURCES.json`](../images/SOURCES.json) lists each public copy with the SHA-256 of its original and the number of boxes.

Look at the public copy before you publish it. The patterns cover the IDs that appeared in the four published answers, not every kind of private text; the name of the signed-in user at the top right of the page stays visible.

Two published pictures were taken before the GUID pattern was part of the default: `ui_blob_over_limit.png` and `ui_chats_top_101.png`. The boxes over their request IDs were added to the originals on 28 November 2026 by the position of those values in the picture, and the same `redact_shot.py` painted them. [`images/SOURCES.json`](../images/SOURCES.json) says so for each of the two.

## What this does not prove

- **The offline tests say nothing about the service.** They show that the scripts count correctly on answers of a known shape.
- **One run is one observation.** `retrieve` returned different results for two identical calls, and the limits of `fetch` are set per tenant.
- **The driver depends on the page.** It finds the tool list, the JSON editor and the **Call tool** button by the page's own markup. When Microsoft changes the page, a call ends with `UI_ERROR` and nothing is measured. The scripts were run against the page as it was on 27 November 2026.
- **Seconds include the page.** A client of your own measures other times.
- **`demo_signin.py` was used in one tenant**, where Windows offered the account and no password was asked.
