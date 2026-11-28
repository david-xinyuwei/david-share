# Work IQ MCP: What retrieve, fetch and fetch_blob Return, and Where Each One Stops

[![Tools](https://img.shields.io/badge/tools-retrieve%20%C2%B7%20fetch%20%C2%B7%20fetch__blob-0078D4)](#results)
[![Measured](https://img.shields.io/badge/measured-27%20Nov%202026%20%C2%B7%20one%20tenant-0078D4)](docs/RESULTS.md#test-setup)
[![Recorded calls](https://img.shields.io/badge/recorded%20tool%20calls-109-0078D4)](results/limits.json)
[![Run it](https://img.shields.io/badge/run%20it-Python%20%2B%20Microsoft%20Edge-0078D4)](#steps)
[![Offline tests](https://img.shields.io/badge/offline%20tests-28%20unittest-0078D4)](docs/TESTING.md)

Author: Xinyu Wei · [中文](README_CN.md)

## Purpose

An agent that works on a user's mail, chats and files through Work IQ MCP searches first and then reads what the search found. Before a team builds on that, it needs to know where each step stops: how many results one search returns, how much text comes with a result, whether the whole message or file can be read afterwards, how large that file may be, and whether a list can be read past its first page.

This test measured those limits in a real Microsoft 365 tenant on 27 November 2026, with the three read tools of Work IQ MCP, `retrieve`, `fetch` and `fetch_blob`, and compared them with the limits that Microsoft Learn documents. It answers four questions:

1. What does `retrieve` return for one question: how many results, and whole items or extracts?
2. Can `fetch` read a whole message, and can it read a list past its first page?
3. How large a file does `fetch_blob` return, and what happens above that size?
4. Do the measured limits match the documented ones?

The answers are under [Results](#results). Test setup, method, every call and what the test does not cover are in [`docs/RESULTS.md`](docs/RESULTS.md). To measure your own tenant, follow the [Steps](#steps).

<img src="images/official_BRK302_slide13.png" width="900" alt="Microsoft slide titled Work IQ toolset. Left box: 13 tools, verbs that stay the same: retrieve, ask, list_agents, fetch, fetch_blob, create_entity, update_entity, delete_entity, do_action, call_function, search_paths, get_schema, listen. Middle box: Work IQ, tool plus path. Right box: Paths, nouns that keep growing: /me/… for Microsoft 365, /businessapps/… for business apps, /&lt;provider&gt;/… for memory, connectors and partners. Three example rows below: fetch /me/messages/{id} reads an email; do_action /me/messages/{id}/forward forwards a thread; update_entity /businessapps/…/records/{id} updates a CRM record.">

How Microsoft presents the tools: slide 13 of the Ignite 2026 session BRK302, "Build personalized AI experiences with Work IQ" ([session page](https://ignite.microsoft.com/en-US/sessions/BRK302), [slides](https://medius.microsoft.com/video/asset/PPT/e241973d-6bc2-4333-8aa4-d78d94c37b2b)), shown whole and unchanged. A call is a tool plus a path. This test covers three of the 13 tools: `retrieve`, `fetch` and `fetch_blob`. The slide names a tool `listen`; the list that the service returned on the test day has `discover` and no `listen`, and the other 12 names are the same ([`results/tools_list.json`](results/tools_list.json)).

<img src="images/limits-overview-en.png" width="900" alt="Diagram from left to right. Your agent, an MCP client, sends tools/call to the Work IQ MCP endpoint. 1, retrieve, search across mail, files, chats and meetings: 0 to 13 results per call, and the tool has no parameter for a count or a next page; up to 9,441 characters of text per result in the snippet field, the longest seen, so a long item comes back as an extract, not in full; 38 of 72 results were marked Content has been truncated by the service, and each of them carries 1,733 to 1,802 characters; each result names the path of its item in entityUrl, which the two tools on the right can read. 2, fetch, read mail, chat messages, events and metadata by path: the whole message body, the largest one read had 930,551 characters; 100 items is the most $top returns per page, 20 for chat messages, and the next page comes with @odata.nextLink or $skip; 50 paths in one call, 51 paths returned InternalError. 3, fetch_blob, read a file from OneDrive or SharePoint: the whole file up to 4 MB, byte for byte, 4,117,319 bytes came back identical to the local copy; refused from 4,194,352 bytes on with Payload too large, and no part of the file comes back.">

What the figure shows: the three read tools and the point where each one stopped in this test. `retrieve` searches and returns a few results, each with an extract of up to 9,441 characters and the path of its item. `fetch` reads that path and returns the whole message, and reads lists 100 items at a time. `fetch_blob` returns a whole file up to 4 MB and refuses a larger one. It is an original explanatory diagram, drawn because the slide above states no limit; every number in it is read from [`results/limits.json`](results/limits.json).

Three things to know before you rely on a number:

- **One tenant, one user, one day.** Microsoft Learn calls the collection limits of `fetch` "per-tenant policy limits", and three of them differed here from the documented values ([result 4](#result-4-three-documented-limits-differ-from-what-the-tenant-did)). Measure your own tenant before you design on a number; the [Steps](#steps) do that in about 15 minutes.
- **`retrieve` is in public preview**, and [Microsoft Learn](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/work-iq/mcp/retrieve#use-markdown-for-model-grounding) tells clients not to parse its Markdown for stable fields, because the format "can change". The field names `snippet` and `truncationInfo` below are what the service wrote on the test day.
- **Live calls read real data and cost Copilot Credits.** The page that sends the calls says so: "Live mode: calls run against your real tenant data and consume Copilot credits." Full answers stay in a private folder on your PC. This repository holds no mail, chat, file or meeting content and no item ID: only what each call asked, with IDs replaced, and the counts, sizes, times, field names and error texts that the service returned.

## Results

Four results:

1. [`retrieve` returns a few extracts, not whole items](#result-1-retrieve-returns-a-few-extracts-not-whole-items): 0 to 13 results per call and up to 9,441 characters of text per result; 38 of 72 results were marked `Content has been truncated`, and each of those carries 1,733 to 1,802 characters.
2. [`fetch` returns whole messages and reads a list page by page](#result-2-fetch-returns-whole-messages-and-reads-a-list-page-by-page): a message body of 930,551 characters came back; `$top` returns at most 100 items per page, 20 for chat messages; `@odata.nextLink` and `$skip` reach the next pages; a call with 50 paths was answered, calls with 51 or more were not.
3. [`fetch_blob` returns a whole file up to 4 MB](#result-3-fetch_blob-returns-a-whole-file-up-to-4-mb): 4,117,319 bytes came back identical to the local file; 4,194,352 bytes were refused.
4. [Three documented limits differ from what the tenant did](#result-4-three-documented-limits-differ-from-what-the-tenant-did): no default of 25 items, 20 chat messages per request instead of 10, and `$skip` is not blocked.

Where they come from: 109 recorded tool calls on 27 November 2026 (78 `fetch`, 9 `fetch_blob`, 22 `retrieve`), sent through Microsoft's [Interactive Demo page for Work IQ MCP](https://interactivedemo.microsoft.com/work-iq/mcp?server=workiq-remote) in Live mode, in one tenant, as one signed-in user who read his own data. All 109 answers arrived with HTTP status 200, the refused calls too: a tool reports a refusal or an error inside the answer, not in the HTTP status. No answer reported throttling; at most 12 calls fell within one minute, so this is not a load test. An answer took 1.0 second for `fetch`, 2.9 seconds for `fetch_blob` and 7.4 seconds for `retrieve` (medians, timed in the page on one PC, so they include the network between that PC and the service). The screenshots are the product's own page during these calls, with IDs covered.

### Result 1: retrieve returns a few extracts, not whole items

<img src="images/official_BRK302_slide14.png" width="900" alt="Microsoft slide titled Retrieve with grounding: cited passages for your agent. Subtitle: Your model does the reasoning. Work IQ returns the evidence. Left, a request: retrieve, strategy grounding, query portal language decision, as the signed-in user. Below it, a response labelled passages, no synthesis: passage 1, Legal review, 21 Oct, Launch must be bilingual; passage 2, Requirements.docx section 4.2, Two languages at launch. Right, four boxes: Raw evidence, your model writes the answer; Permission-trimmed, only what the user can open; Cited, every passage links to its source; Your content, Microsoft 365 plus synced connectors.">

What Microsoft says `retrieve` returns: slide 14 of the same session, shown whole and unchanged. The answer is a list of passages, each with its source; it is not the whole item and not a written answer. The slide gives no count and no length. The chart and the table below are what this test measured: how many passages one call returns and how long each one is.

<img src="images/retrieve-snippets-en.png" width="900" alt="Bar chart: characters of the snippet field of each of the 70 results that carry one, out of 72 results from 20 calls, sorted by length; the axis runs from 0 to 10,000 characters. The 38 results that the service marked Content has been truncated are red and all lie between 1,733 and 1,802 characters. The 32 results without that mark are blue and range from 575 to 9,441 characters. Median 1,798, largest 9,441.">

One bar per result. Red: the 38 results whose Markdown carries the line `truncationInfo: Content has been truncated`; each has 1,733 to 1,802 characters. Blue: the 32 results without that line, 575 to 9,441 characters.

| What the `retrieve` call asked | Results returned |
|---|---|
| "What was announced about Work IQ at Microsoft Ignite 2026?", all sources | 5 |
| the same call a second time | 3 |
| keywords instead of a sentence ("Work IQ MCP retrieve tool"), sent twice | 0 and 0 |
| the question in Chinese | 0 |
| the question with `strategy: "copilot"` (50.6 seconds; the other answered calls took 3.9 to 12.1) | 3 |
| the question limited to one source: Email, OneDriveAndSharePoint, TeamsMessages, Meetings, People | 2, 4, 2, 2, 0 |
| the question with `top: 50`, a parameter the tool does not list | 4 |
| the question plus "Return 50 results." | 13 |
| the question plus "Return 100 results." | 7 |
| a second question, "What important emails did I receive in the last week?", in English and in Chinese | 7 and 7 |

What to look at:

- **The number of results is small and is not yours to set.** The 20 answered calls returned 0 to 13 results. The tool has no parameter for a count or a next page, and its answer carries no link to more. `top: 50`, a parameter the tool does not list, raised no error, and the call returned 4 results, between the 5 and the 3 that the same question returned without it. Asking for 50 results inside the question gave 13; asking for 100 gave 7; no other call returned more than 7. The same question sent twice gave 5 results and then 3, and 2 sources were in both answers.
- **A result carries an extract.** `results[].markdown` holds a title, metadata lines and a `snippet` field. 70 of the 72 results had one: median 1,798 characters, largest 9,441. The longest whole `markdown` had 11,599 characters; the largest answer of one call held 43,236 characters of Markdown in total.
- **No truncation mark does not mean the whole item.** The 16 mail and chat messages among the results were read again with `fetch` and compared. 14 of them carried no truncation mark, and for 8 of those 14 the snippet is shorter than the message's own text, so it cannot be the whole message. The longest message has 238,687 characters of text (white space not counted); its snippet has 8,978 characters and no `truncationInfo` line. A short message can come back whole: for 3 messages of 481 to 1,211 characters, all 21 samples taken from the body were found in the result.
- **The size of the item does not matter.** The 14 files among the results have 25,915 to 817,685,365 bytes. The largest, a meeting recording, came back as a snippet of 1,800 characters.
- **The index finds far more than one call returns.** In the call limited to OneDriveAndSharePoint, the answer's own metadata reported "117690 results for File domains"; the call returned 4.
- **Each result names its item.** `entityUrl`, for example `/me/messages/{id}` or `/drives/{id}/items/{id}`, worked as a `fetch` path for all 30 items that were read back. 7 of the 14 files are larger than the 4 MB that `fetch_blob` returns ([result 3](#result-3-fetch_blob-returns-a-whole-file-up-to-4-mb)).

The table of every call, the fields of a result and the 30 comparisons are in [`docs/RESULTS.md`](docs/RESULTS.md#retrieve-every-call).

### Result 2: fetch returns whole messages and reads a list page by page

<img src="images/ui_skip.png" width="900" alt="Interactive Demo page in Live mode, tool fetch. Request: entityUrls with the single path /me/messages?$select=id&amp;$top=2&amp;$skip=3. Response: results with two messages whose IDs are covered, an @odata.nextLink that reads /me/messages?%24select=id&amp;%24top=2&amp;%24skip=5, statusCode 200, and the note Results limited to 2 items per collection. If you need different results, refine your $filter or $search parameters.">

The product's page during the call `/me/messages?$select=id&$top=2&$skip=3`: status 200, two messages, an `@odata.nextLink` that continues at `$skip=5`, and the service's own note "Results limited to 2 items per collection". Message IDs, ETags and the user's object ID are covered.

| Path or parameters sent with `fetch` | What came back |
|---|---|
| `/me/messages` without `$top` | 10 items |
| `$top=25`, `$top=26`, `$top=100` | 25, 26 and 100 items |
| `$top=101`, `$top=1000` | 100 items, with the note "Results limited to 100 items per collection" |
| `$top=5&$skip=5` | items 6 to 10 of the list |
| the `@odata.nextLink` of the `$top=100` answer, sent back as the path | 100 other messages |
| `$top=5&$skip=5000` | 5 items |
| messages of a chat: without `$top`, `$top=11`, `$top=50` (3 chats each), `$top=21` (1 chat) | 20, 11, 20 and 20 items |
| 100 messages with `$select=id,body` | 100 bodies with 5,686,377 characters in one answer of 7,690,363 bytes, after 5.3 seconds |
| 50 paths in one call, 51 paths in one call | 50 results, `InternalError` |

<img src="images/ui_51_paths.png" width="900" alt="Interactive Demo page in Live mode, tool fetch. Request: entityUrls with the path /me?$select=id repeated; the list continues below the visible part of the box. Response: error An internal error occurred. Contact support if the problem persists, errorCode InternalError, recoveryAction None.">

The call with 51 paths ([`cases/fetch_51_paths.json`](cases/fetch_51_paths.json)): the service answers `InternalError`. The same call with 50 paths returned 50 results.

What to look at:

- **The body is whole.** The largest body read had 930,551 characters. All 96 HTML bodies with text in the 100-message answer end with `</html>`; one body was empty and three were plain text. The short field is `bodyPreview`, at most 255 characters.
- **A page holds at most 100 items, 20 for chat messages.** A larger `$top` is cut to that number, and the answer says so in its `note`. Without `$top` the page size depends on the collection: 10 items for mail, events and people, 19 chats, 20 chat messages, and all 163 children of a OneDrive folder in one answer.
- **Lists can be read past the first page.** `$skip` in the request works, and the `@odata.nextLink` of an answer, sent back as the path, returns the next page. That link carries `$skip` for mail and events and a `$skiptoken` for chats, chat messages, OneDrive folders and `$search`. `$filter` on a date and `$search` work as well.
- **No lookback window was seen.** Sorted oldest first, the mail list starts in October 2022; `retrieve`, asked about 2023, returned mail from March and August 2023.
- **A call with 50 paths was answered; calls with 51 to 100 were not.** Calls with 2, 20 and 50 paths returned a result for every path, which is how the 30 items of result 1 were read back in a single call. All 6 calls with 51, 53, 56, 62, 75 and 100 paths returned `InternalError`. That error names no limit, so 50 is the largest number that worked in this run, not a limit that the service states.

### Result 3: fetch_blob returns a whole file up to 4 MB

<img src="images/ui_blob_over_limit.png" width="900" alt="Interactive Demo page in Live mode, tool fetch_blob. The tool description reads: Download a binary file (document, PDF, image, photo) from a WorkIQ content path, up to 4 MB. Request: path /me/drive/items/, an item ID that is covered, /content. Response: error Payload too large; downloads are limited to 4 MB, and a requestId whose value is covered.">

The product's page during the call for a file of 4,194,352 bytes: "Payload too large; downloads are limited to 4 MB." The item ID and the request ID are covered.

| File size (bytes) | File type | Result | Time (seconds) | Size of the answer (bytes) |
|---|---|---|---|---|
| 864 | .json | identical to the local file | 2.0 | 1,909 |
| 3,692,641 | .png | identical to the local file | 5.4 | 5,313,565 |
| 3,815,774 | .html | identical to the local file | 4.1 | 5,094,699 |
| 4,116,808 | .png | identical to the local file | 4.2 | 5,926,201 |
| 4,117,319 | .png | identical to the local file | 3.9 | 5,931,216 |
| 4,194,352 | .mp4 | refused: "Payload too large; downloads are limited to 4 MB." | 2.6 | 275 |
| 4,405,081 | .json | refused, same message | 2.2 | 275 |
| 20,050,987 | .pptx | refused, same message | 2.9 | 275 |

What to look at:

- **A file within the limit comes back byte for byte.** "Identical" means that the SHA-256 of the decoded `base64Content` equals the SHA-256 of the same file on the PC.
- **The limit lies between 4,117,319 and 4,194,352 bytes.** That fits 4 MB counted in units of 1,024, `4 × 1,024 × 1,024 = 4,194,304` bytes, and rules out 4,000,000. The two sizes next to 4,194,304 were not tested, so the exact byte is not known.
- **The answer is larger than the file.** The file travels as Base64 inside JSON: 4,117,319 bytes became an answer of 5,931,216 bytes.
- **Above the limit nothing comes back.** The tool's parameters are `path`, `format` and `agentId`; none of them asks for a part of a file. In this test a file above the limit reached the caller only as the extract that `retrieve` returns. `format`, which the tool description says converts a file on download, was not tested.

### Result 4: three documented limits differ from what the tenant did

<img src="images/ui_chats_top_101.png" width="900" alt="Interactive Demo page in Live mode, tool fetch. Request: entityUrls with the single path /me/chats?$select=id&amp;$top=101. Response: statusCode 400 and the error message The query specified in the URI is not valid. The limit of 50 for Top query has been exceeded. The value from the incoming request is 100. Three request IDs in the answer are covered.">

The product's page during the call `/me/chats?$select=id&$top=101`. The call sent 101. The error says that the limit for this collection is 50 and that the value which arrived was 100. The paths of `fetch` are Microsoft Graph paths: the tool's own description says "Use well-known Microsoft Graph paths directly" ([`results/tools_list.json`](results/tools_list.json)), and Microsoft Graph documents for [List chats](https://learn.microsoft.com/en-us/graph/api/chat-list?view=graph-rest-1.0#optional-query-parameters) that the "Maximum allowed `$top` value is 50". The request IDs in the answer are covered.

| Limit | [Microsoft Learn, Work IQ MCP tool reference](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/work-iq/mcp/tool-reference) (updated 20 November 2026) | Measured on 27 November 2026 | Same or different |
|---|---|---|---|
| `fetch`, a collection asked without `$top` | "the system injects a default $top of 25" | 10 items for mail, events and people; 19 chats; 20 chat messages; 163 items of a OneDrive folder | different |
| `fetch`, largest `$top` | "a maximum cap of 100" | 100: `$top=101` and `$top=1000` return 100 | same |
| `fetch`, chat messages | "Chat messages are capped at 10 per request." | 20: `$top=11` returns 11, `$top=21` and `$top=50` return 20 | different |
| `fetch`, `$skip` and `$skiptoken` | "The system blocks the $skip and $skiptoken query parameters." | `$skip=5` returns items 6 to 10; a next-page link with `$skip` or `$skiptoken` returns the next page | different |
| `fetch_blob`, file size | "The default raw-file limit is 4 MB and can be configured per path." | 4,117,319 bytes returned, 4,194,352 bytes refused | same |
| `fetch_blob`, above the limit | "returns an MCP tool error containing the configured limit; it doesn't return blob content" | error "Payload too large; downloads are limited to 4 MB." | same |
| `fetch`, paths in one call | not stated | 50 answered; 51 to 100 returned `InternalError` | not documented |
| `retrieve`, results per call and text per result | not stated | 0 to 13 results; up to 9,441 characters in `snippet` | not documented |

What to look at:

- **Two of the three differences give the caller more than the page says; the third is a different default.** Chat messages came back 20 per request where the page says 10, and `$skip` worked where the page says it is blocked. The default is not larger: without `$top`, mail, events and people returned 10 items where the page says 25, while a OneDrive folder returned all 163 of its items. The same page calls these per-tenant policy limits, so another tenant, or this tenant on another day, can behave as documented. The page's own example answer carries a next-page link with `$top=10&$skip=10`, which matches the measurement.
- **`$top` is lowered to 100 before the request reaches Microsoft Graph, and Graph's own limits still apply.** The call above sent 101, the error reports 100 as the value that arrived, and 50 is the maximum that Microsoft Graph documents for this collection. That Work IQ is what lowers the value is an inference from this error text and from the note "Results limited to 100 items per collection" in the mail answers; the service's code was not seen.
- **A made-up `$skiptoken` returned the first page.** Whether Work IQ removed it or Graph ignored it cannot be told from the answer.

| You want | Read |
|---|---|
| the test setup, the method, every call and what was not tested | [`docs/RESULTS.md`](docs/RESULTS.md) |
| what each script under [`scripts/`](scripts/) does, what the offline tests under [`tests/`](tests/) check and what they do not prove | [`docs/TESTING.md`](docs/TESTING.md) |
| every number on this page as data | [`results/limits.json`](results/limits.json), one row per call in [`results/summary/`](results/summary/) |
| the tool list and schemas the service returned on the test day | [`results/tools_list.json`](results/tools_list.json) |
| the arguments of five calls, ready to send again with `scripts/call_once.py` | [`cases/`](cases/) |
| where the figures and screenshots come from | [`images/SOURCES.json`](images/SOURCES.json), [`NOTICE.md`](NOTICE.md) |

## Steps

These steps measure the same limits in your own tenant, as you, on your own mail, chats and files.

| Order | Where | What | Command | Takes about |
|---|---|---|---|---|
| 1 | your PC | get the code, install one package, run the offline tests | `git clone`, `pip install websocket-client` | 2 minutes |
| 2 | your PC | open the Interactive Demo in a separate Edge profile and sign in | `python scripts/edge_cdp.py start --url <page>` | 1 minute |
| 3 | your PC | check the page with the tool list | `python scripts/call_once.py --list-tools --case 00_tools_list --out "$out\raw"` | seconds |
| 4 | your PC | run the eight stages: 78 calls plus one per file you name | `python scripts/run_limits.py <stage> --out $out --reuse` | 10 minutes |
| 5 | your PC | turn the records into numbers | `python scripts/build_results.py $out --results "$out\public"` | seconds |
| 6 | your PC | close the browser | `python scripts/edge_cdp.py close` | seconds |

The times are estimates for a first run. One part was measured: in the published run the 86 calls of step 4 waited 5.1 minutes for their answers in total; the rest of that step is the time the page needs to send each call.

Prerequisites:

- **Tenant.** Work IQ is enabled, and you are assigned to a spending policy for Copilot Credits that includes the Work IQ API; [Microsoft Learn lists both](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/work-iq/mcp/retrieve#before-you-begin) before the first call. The Interactive Demo is the client, so you register no application. A tenant that blocks the Interactive Demo, or asks for admin consent at its sign-in, was not tested.
- **Cost.** The eight stages send 56 `fetch` and 22 `retrieve` calls, plus one `fetch_blob` call per file you name for the file test; the published run named 8 files and sent 86 calls. Microsoft's [licensing announcement for Work IQ](https://www.microsoft.com/en-us/licensing/news/work-iq-general-availability), as read on 28 November 2026, describes two parts: a variable charge for query-style use (grounding, retrieval and reasoning) and 0.1 Copilot Credits per call of the Work IQ Tool API. Which part applies to each of the three tools, and what this test was charged, was not checked.
- **Data.** The scripts read: IDs of your newest messages, events, people, chats and OneDrive root items; the bodies of your 100 newest messages and of the messages that `retrieve` returns; messages of 3 chats; the files you name for the file test; and what `retrieve` finds for the questions in `scripts/run_limits.py`. Only `retrieve`, `fetch` and `fetch_blob` are called, so nothing is written to Microsoft 365 through Work IQ.
- **Tools.** Windows, Microsoft Edge, Python with the package `websocket-client`. Tested with Windows 11, Microsoft Edge 158, Python 3.13.15 and websocket-client 1.9.2. macOS and Linux were not tested: `scripts/edge_cdp.py` looks for Edge in its Windows install folders.

### 1. Get the code and run the offline tests

```powershell
git clone --filter=blob:none --sparse https://github.com/david-xinyuwei/david-share.git
cd david-share
git sparse-checkout set Agents/Work-IQ-MCP-Raw-Data-Limits
cd Agents/Work-IQ-MCP-Raw-Data-Limits

python -m pip install websocket-client
python -m unittest discover -s tests
```

The last command needs no browser and no sign-in. It ends with:

```text
Ran 28 tests in <n>s

OK
```

### 2. Open the Interactive Demo and sign in

```powershell
python scripts/edge_cdp.py start --url "https://interactivedemo.microsoft.com/work-iq/mcp?server=workiq-remote"
```

```text
EDGE Edg/<version> port 9351 profile C:\Users\<you>\AppData\Local\EdgeAutomation\workiq-demo
```

An Edge window opens with a profile of its own; the Edge windows you work in are not touched. In that window, click **Sign in to go live** and finish the sign-in yourself. The scripts type no password and never read the token: the page gets it and sends every call.

The scripts drive that window through its DevTools port, 9351, which listens on `127.0.0.1` only. While the window is open, any program on this PC that connects to the port can act in the signed-in page, so close the window when you are done ([step 6](#6-close-the-browser)).

Then check the page:

```powershell
python scripts/edge_cdp.py wake --match interactivedemo
```

```text
sent: ['Page.setWebLifecycleState', 'Emulation.setFocusEmulationEnabled']
{"visibilityState": "visible", "hasFocus": true, "firstTimerMs": 319, "secondTimerMs": 311, "logEntries": 0, "account": "<your name>"}
```

`account` shows your name when the page is in Live mode and is empty in Demo mode. The two timer values are near `300` when the page is awake. You can work in other windows during the test: the scripts tell the page that it is active before every call, because Edge otherwise stops the timers of a covered window.

### 3. Check the page with the tool list

```powershell
$out = "$HOME\workiq-limits\run1"
python scripts/call_once.py --list-tools --case 00_tools_list --out "$out\raw"
```

`$out` is a private folder: the full answers, with the content of your mail, are saved under `$out\raw`. Keep it out of shared folders and out of Git. The command reloads the page and records the tool list that the page requests:

```text
account shown by the page: <your name>
HTTP 200  headers after <n> ms, last byte after <n> ms  <n> bytes  request-id <id>  sent as typed: None
13 tools: retrieve, fetch_blob, ask, list_agents, delete_entity, do_action, discover, create_entity, get_schema, search_paths, call_function, fetch, update_entity
saved <out>\raw\00_tools_list.json
```

Your tenant can list other tools. The measurements need `retrieve`, `fetch` and `fetch_blob`.

### 4. Run the measurements

```powershell
foreach ($stage in 'mail', 'collections', 'chat', 'multi', 'body', 'retrieve', 'fulltext') {
    python scripts/run_limits.py $stage --out $out --reuse
}
python scripts/run_limits.py blob --out $out --reuse --blob-files "<file 1>" "<file 2>" "<file 3>"
```

Each call prints one line with its arguments, the HTTP status, the time, the size of the answer and counts; no line shows the content of a message or a file. `--reuse` skips a call whose record is already in `$out\raw`, so a stage that was interrupted can be started again without sending its finished calls a second time.

For the `blob` stage, name files that are already in your OneDrive, from the folder that OneDrive syncs on this PC, with sizes on both sides of 4 MB: for example one below 4,000,000 bytes, one between 4,000,000 and 4,194,304 and one above. The stage finds each file in OneDrive, asks `fetch_blob` for it and compares the SHA-256 with the local file. Without `--blob-files` the stage writes seven text files of fixed sizes into `$out\blob_test` and waits for OneDrive to upload them, which needs `$out` inside a OneDrive folder. On the test day OneDrive did not upload them, so the published run used files that were already there.

Then show every call in one table:

```powershell
python scripts/summary_table.py $out mail collections chat multi body blob retrieve fulltext
```

The first lines of the published run:

```text
== mail: 14 calls
mail_01_no_top                     HTTP 200 3628 ms 3162 B err=False typed=True :: status 200, 10 items, nextLink($skip=10,$top=10)
mail_02_top_25                     HTTP 200 1047 ms 6946 B err=False typed=True :: status 200, 25 items, nextLink($skip=25,$top=25)
```

A different count in your tenant is a result, not an error. A line with `UI_ERROR` means that the page did not send the call; see [If a step stops](#if-a-step-stops).

### 5. Turn the records into numbers

```powershell
python scripts/run_stats.py $out --json "$out\summary\run_stats.json"
python scripts/retrieve_fields.py $out --json "$out\summary\retrieve_fields.json"
python scripts/build_results.py $out --results "$out\public"
```

`$out\public\limits.json` now holds your tenant's values under the same names as [`results/limits.json`](results/limits.json) of this repository, so the two can be compared line by line. It contains counts, sizes, field names and error texts. The summaries next to it, in `$out\public\summary`, also hold the text of your `retrieve` queries; read them before you share them. The request IDs of the service are left out of this public copy; they stay in `$out\summary`, where you find them for a support case. `$out\raw` still holds your content and stays private.

### 6. Close the browser

```powershell
python scripts/edge_cdp.py close
```

```text
EDGE_CLOSED
```

The sign-in stays in the separate profile folder. Delete `%LOCALAPPDATA%\EdgeAutomation\workiq-demo` to remove it.

### If a step stops

| You see | Do |
|---|---|
| `EDGE_NOT_RUNNING on port 9351` or `NO_DEMO_PAGE` | run step 2 again |
| `account shown by the page: (none` | the page is in Demo mode: click **Sign in to go live** in the automation Edge window |
| `the page did not react within 60 s` | Edge stopped the page's timers; run `python scripts/edge_cdp.py wake --match interactivedemo`, then the stage again with `--reuse` |
| `TIMERS_FROZEN` from the `wake` command | bring the automation Edge window to the front once, then run `wake` again |
| `no tool named ... in the page` | your tenant does not list that tool; run step 3 and read the tool list |
| a `fetch` line with `status 403`, or a tool error that names a policy | your tenant's Work IQ MCP policy blocks that path; the line is your result for it |
| `is not inside a OneDrive folder of this PC` | pass `--blob-files` with files from the folder that OneDrive syncs |
| `file of <n> bytes skipped: OneDrive reports size <m>` | OneDrive stores that file with another size, which happens with Office files; name another file |
