# Testing

[中文](TESTING_CN.md) · [README](../README.md) · [Results per scenario](RESULTS.md)

Seven layers, from cheapest to most expensive. The first four need no Azure account; the browser check and the engineering renders need Microsoft Edge; only the deployment and the live checks create Azure resources or call a model, and cost money.

## What each layer checks

| Layer | Command (in `studio/` unless noted) | Needs | Checks | Does not check |
|---|---|---|---|---|
| Python unit and contract tests, 72 | `python -m unittest discover -s tests -p "test_*.py"` | the venv; the 15 reference solids from `pregen_cad.py` | output contracts and parsing, SSE events and heartbeats, sign-in and sessions, input limits, the server-managed connection (no key reaches the browser), the CAD allow-list, the retry loop that feeds errors back, cancel and kill of the OCCT child, cached results served like live ones, the proposal `.docx`, a reasoning effort the deployment refuses (the 400 of 2026-11-14) sent as the next higher accepted value | a real model answer (mocked) and a real OCCT run (mocked), except that every reference script must pass the same allow-list as model output and have a fresh build |
| Node front-end tests, 38 | `node --test tests/test_connection.cjs tests/test_viewer_bridge.cjs` | Node.js 18+, three.js from `tools/vendor_three.py` | connection dialog in server-managed mode, render-ready detection from real WebGL draw calls, failure reporting, PNG and GLB export rules, quad-view layout and framing | real WebGL pixels (the canvas is simulated) |
| Real OCCT build, 15 solids | `python pregen_cad.py`, then `python pregen_cad.py --lang en` | the venv | every reference script runs through `cad_runner.run_script` and writes STEP, STL, GLB and `parts.json`; the English build has the same solids under English names | CadQuery scripts written by GPT-6 (those only run live) |
| Repository checks | `python -m unittest discover -s tests -v` in the repository root | Python only | README and docs layout in both languages, links and anchors, images against `images/SOURCES.json`, every result number against `data/results.json`, the two figures against their HTML sources, no private hosts, paths or keys | whether the prose is right; a reader still has to read it |
| Browser check, 23 steps | `python tests/check_workspace_browser.py --headless --output <dir>` with the studio on `127.0.0.1:8015` (below) | Edge, `requirements-dev.txt` | the served files equal the source; a scenario opens with its pre-generated STEP solid; ambient occlusion darkens the part; shading, section, isolation and both exports work; English UI; 390 px narrow screen; a scene written to the current prompt renders through the same bridge; no request reaches a model endpoint | GPU rendering (it uses software WebGL); a live model result |
| Engineering renders, 15 | `python pregen_engineering.py <ids> --out <dir> --no-install` | Edge, `requirements-dev.txt`, the solids from `pregen_cad.py` | each STEP mesh renders with no unmatched part, and the silhouette IoU between the picture and the STEP from the same camera | the gpt-image render (that one needs Azure) |
| Deployment, end to end | `./infra/up.ps1`, `./infra/verify.ps1 -Full`, `./infra/down.ps1` in the repository root (README steps 2, 3 and 5) | an Azure subscription with quota (README [Steps](../README.md#steps)), Azure CLI, PowerShell 7.3 | every resource is created from `infra/main.bicep` in a new resource group; the VM installs the studio from the repository and serves HTTPS with a Let's Encrypt certificate; through that address: health, the HTTP redirect, a wrong password refused, sign-in, the 15 scenarios, the pre-generated solid of every scenario in both languages, one GPT-6 call with the VM's managed identity, a live **Generate STEP** with its STEP file downloaded and one gpt-image concept picture; the removal leaves no resource group and no soft-deleted AI resource | the browser UI on the VM (the browser check covers the same pages locally), a live three.js page, **Photoreal render** and the proposal; the cost |
| Live checks, manual | **Call GPT-6 live**, **Photoreal render**, **Proposal (.docx)** in the UI | a deployment (README step 2) | the real model path end to end | not automated; each click costs tokens. `verify.ps1 -Full` covers **Generate STEP** and the concept picture |

### Browser check

```powershell
$env:PORTAL_USERNAME = 'preview'; $env:PORTAL_PASSWORD = 'local-ui-test-only'
$env:AOAI_ENDPOINT = 'https://example.invalid'; $env:AOAI_REASONING_EFFORT = 'low'
Start-Process python -ArgumentList '-m','uvicorn','app:app','--host','127.0.0.1','--port','8015'
python tests/check_workspace_browser.py --headless --output ../evidence/my-browser-check
```

Expected: 23 `PASS <step>` lines and `{"status": "PASS", "checks": 23, ...}`. The check fails if any request reaches `/api/generate`, `/api/cad`, `/api/render`, `/api/concept` or `/api/proposal` (the one `/api/cad` it needs is answered inside the browser from `tests/fixtures/`). Stop the server afterwards.

### Screenshots

With the studio started as above, `tools/capture_screens.py` takes the pictures of the README and docs/RESULTS from the pre-generated examples:

```powershell
python ../tools/capture_screens.py http://127.0.0.1:8015 ../evidence/my-screens
python ../tools/capture_screens.py http://127.0.0.1:8015 ../evidence/my-screens --only features,gallery --scenarios coldplate,exv
```

The first command takes the six module pictures. `--only` selects other groups: `features` (section and isolation), `gallery` (each scenario as GPT-6's page and as the solid) and `render` (the render tab). `render` needs a saved render in `render_cache/module/`, which `pregen_render.py` makes with the gpt-image deployment and `pregen_render_cad.py` completes with the STEP outline that **Overlay CAD** shows. It also needs `AOAI_IMAGE_DEPLOYMENT` set when the studio starts, because the **Render** tab only appears when an image deployment is named; with `AOAI_ENDPOINT=https://example.invalid` nothing can be called. Expected: one PNG per picture and a `capture.json` whose `model_calls` and `page_errors` are empty; otherwise the tool exits 1.

### Engineering renders

```powershell
python pregen_engineering.py aidc aps cdu coldplate drawing2d exv fourway mchx module nb_assembly_line nb_chassis_mold nb_packing nb_thermal thermal_sim vehicle_tms --out ../evidence/my-engineering --no-install
```

Expected: one JSON line per scenario with `"ok": true` and an `iou_pct`. Without `--no-install` the pictures also go to `render_cache/<id>/`, where the studio's render tab picks them up.

## Recorded run

[`evidence/run-20261113/`](../evidence/run-20261113/) holds one replay of the local path (the install and build of README step 6 and the tests of the README appendix) plus the browser check, the screenshots and the engineering renders, in a new virtual environment on the test laptop: Windows 11 Enterprise on Arm (build 10.0.26300), Snapdragon X X1E80100 with 12 cores, 63.5 GB RAM, x64 Python 3.11.9 under emulation, Node.js v24.18.0 and Microsoft Edge 157.0.4341.57 ([`machine.json`](../evidence/run-20261113/machine.json), [`capture.json`](../evidence/run-20261113/browser/capture.json), [`capture-gallery.json`](../evidence/run-20261113/browser/capture-gallery.json)). The steps up to the first Node test ran on 2026-11-13 from 17:11 (UTC+8); the fix described below, the reruns, the browser check, the screenshots and the renders ran on 2026-11-14. No model was called. Times include pip downloads and the x64 emulation. The studio had 68 Python tests then; the four reasoning-effort tests of 2026-11-14 bring it to 72.

| Step | Command (in `studio/` unless noted) | Result | Time (s) |
|---|---|---|---|
| Install the pinned requirements | `pip install -r requirements.txt -c deploy/constraints.txt` | exit 0 | 776.7 |
| Install the browser and image tools | `pip install -r ../requirements-dev.txt` | exit 0; [`pip-freeze.txt`](../evidence/run-20261113/pip-freeze.txt) then lists 82 packages | 63.9 |
| Check three.js | `python ../tools/vendor_three.py --check` | 15 of 15 files verified | 3.0 |
| Build the 15 STEP solids | `python pregen_cad.py` | 15 of 15 OK, failed: none | 1025.0 |
| English names, first attempt | `python pregen_cad.py --lang en` | **FAIL**: 13 of 15 OK, failed: coldplate, module (see below) | 406.7 |
| Python tests | `python -m unittest discover -s tests -p "test_*.py"` | 68 tests, OK | 29.4 |
| Node tests | `node --test tests/test_connection.cjs tests/test_viewer_bridge.cjs` | 38 tests: 38 pass, 0 fail | 2.0 |
| English names after the fix | `python pregen_cad.py --lang en --force` | 15 of 15 OK, failed: none | 266.5 |
| Python tests again | same as above | 68 tests, OK | 14.0 |
| Node tests again | same as above | 38 tests: 38 pass, 0 fail | 1.4 |
| Browser check | `python tests/check_workspace_browser.py --headless --output <dir>` | PASS: 23 of 23 checks pass, model calls: 0 | 230.4 |
| Screenshots | `python ../tools/capture_screens.py http://127.0.0.1:8015 <dir>` | 6 pictures, model calls: 0 | 126.9 |
| Engineering renders | `python pregen_engineering.py <15 ids> --out <dir> --no-install` | exit 0; 15 of 15 with every mesh matched to its part | 192.0 |
| More screenshots | `python ../tools/capture_screens.py http://127.0.0.1:8015 <dir> --only <group> --langs <lang> --scenarios <ids>` | 11 of 11 batches done, one process each: 66 new pictures, plus the 6 module pictures again (not published); model calls: 0; GPT-6 pages that threw: 1; 8 failed attempts in 3 batches, rerun after fixes (see below) | 3223.1 |

**What failed and what changed.** The first English-name build stopped for the cold plate and the integrated module with `STEP string count differs`. `pregen_cad.py --lang en` builds the Chinese and the English script at the same time with the edge break off, checks that both give the same solid, and then puts the English names into the Chinese STEP by pairing the two files' string literals position by position. With the two OCCT processes running at once, one STEP described four circles as B-spline curves and the other as circles. The solids were the same (same volume, area and faces), but one file had 16 more unnamed (`''`) literals, so the two lists no longer lined up position by position and the build stopped. Built one after the other, each script gave the same file three times out of three; built at the same time, the files differed in this environment and in a second Python environment on the same laptop. Why concurrency changes OCCT's output was not investigated. The fix pairs only non-empty literals (names, units, contexts), whose order does not change. [`fix-step-name-alignment.json`](../evidence/run-20261113/fix-step-name-alignment.json) applies the old and the new pairing to two cold-plate files built the same way, which reproduce the failure: 14,538 vs 14,522 literals with the old pairing; 1,080 vs 1,080 non-empty literals with the new one, five names paired, no conflict, no Chinese left. The rerun with `--force` rebuilt all 15 English caches.

**Screenshot batches that failed.** The more screenshots ran in batches of one language and up to five scenarios, each in its own process and retried once; the time in the table includes every attempt, and [`status_screens.json`](../evidence/run-20261113/status_screens.json) lists each one. Three batches failed and were rerun after a fix; one attempt that would have repeated a failure before its fix was stopped by hand (exit `-1`):

- Notebook cards, English: the batch stopped at the first notebook card with `Cannot read properties of null (reading 'click')`. The studio lists the cards of one industry group at a time (thermal management or notebook), and `capture_screens.py` looked for a card of the other group. `open_scenario()` now loads the scenario's group first.
- Notebook cards, Chinese: GPT-6's Chinese page for the notebook assembly line throws `TypeError: Cannot read properties of undefined (reading 'x')` in its animation loop, after it has drawn the line ([details](RESULTS.md#every-scenario-at-a-glance)). The studio then reports that the scene did not render and keeps its layout buttons disabled, and the tool waited for them. It now takes the picture as the page is and records the studio's message with it as `scene_error` in `capture-gallery.json`; any other page error still fails the run.
- Render tab: the batch found no **Render** tab. The studio shows that tab only when the server names an image deployment, and the run script had not set `AOAI_IMAGE_DEPLOYMENT`. The rerun set it; the endpoint stayed `https://example.invalid`, so no image model could be called.

Both notebook batches were then taken again with the final tool, which also clicks **Original** whenever it is enabled: right after a page has rendered, the button can still show the previous state. The thermal-management batches ran the earlier tool. Their cards are in the group the studio opens with, and each of their pages rendered and took the **Original** click, so the fixes do not change what they show.

**Environment.** `deploy/constraints.txt` pins the 10 packages the studio imports directly; the other packages resolved from PyPI on 2026-11-13, for example python-dateutil 4.0.0, multidict 7.2.1 and trame 4.0.0. [`pip-freeze.txt`](../evidence/run-20261113/pip-freeze.txt) lists every version of this run; to pin all of them, install from that file instead (`pip install -r ../evidence/run-20261113/pip-freeze.txt`, not tested on another machine). `studio/app.py` imports aiohttp, which `requirements.txt` does not list: it arrives with CadQuery (cadquery → trame → wslink → aiohttp).

**Not part of this run:** the Azure deployment, which has its own record below, and the live checks. The 30 recorded GPT-6 responses and the gpt-image pictures were made earlier with the studio's own deployment (2026-09-09 to 2026-09-12 and 2026-11-10).

## Recorded deployment

[`evidence/deploy-20261114/`](../evidence/deploy-20261114/) holds one pass of README steps 2, 3 and 5 on 2026-11-14: `up.ps1`, `verify.ps1 -Full` and `down.ps1 -Yes`, run on the test laptop (Windows 11 on Arm, Azure CLI 2.92.0, PowerShell 7.7.0) into a new resource group in East US 2, with nothing prepared beforehand but `az login`. `up.json`, `verify.json` and `down.json` record the status and duration of every step and check; `up-output.txt`, `verify-output.txt` and `down-output.txt` hold what each script printed, without the line that names the subscription; `infra-sha256.json` holds the SHA-256 of the five `infra/` files that ran; four are unchanged in this revision, and `verify.ps1` has since changed only the reasoning effort its live Generate STEP asks for (`low` instead of `none`). In all of them the deployment's unique name suffix is replaced by `<hash>`.

| Step | Command | Result | Time (min) |
|---|---|---|---|
| Preflight | `up.ps1`, step 1/5 | both models offered in East US 2; gpt-6-astra as Data Zone Standard, because the subscription's Global Standard quota was used up; VM size `Standard_D4as_v6`, the first one on the list that the region offers to the subscription | 2.7 |
| Resource group | `up.ps1`, step 2/5 | created | 0.2 |
| Azure resources | `up.ps1`, step 3/5: `infra/main.bicep` | AI resource with both model deployments, identity and role, network, VM | 0.8 |
| Install on the VM | `up.ps1`, step 4/5: `infra/vm-install.sh` through Run Command | `studio/` from `master` at `d32e1e6e`; 15 reference solids with Chinese and 15 with English part names, the notebook dual-fan module without the edge break (see below); `/healthz` over HTTPS from the VM: 200 | 10.3 |
| HTTPS check | `up.ps1`, step 5/5 | `/healthz` from the laptop: `{"ok":true,"deployment":"gpt-6-astra",...}` | < 0.1 |
| Checks through the public address | `verify.ps1 -Full` | 10 of 10 passed | 2.1 |
| Removal | `down.ps1 -Yes` | resource group deleted, AI resource purged, nothing left | 4.4 |

**The live Generate STEP of `verify.ps1 -Full`.** One request for an aluminium battery cold plate with six S-shaped channels went to `/api/cad`, asking for reasoning effort `none`. It took 1 attempt and 91.5 s, of which 6.7 s in OpenCascade, and returned 4 solids, 315 faces, 1.580 kg and a 1.1 MB STEP file. The deployment did not take `none`. The studio's answer names no reasoning effort (`"reasoning_effort": null` in [`verify.json`](../evidence/deploy-20261114/verify.json)), and `studio/app.py` at `d32e1e6e` leaves it empty only after the deployment refused the parameter and the studio sent the request again without it. GPT-6 therefore reasoned at the deployment's default effort and used 1,472 reasoning tokens. The current `studio/app.py` sends the next higher value the deployment accepts instead (`low` for `none`; README step 4). It is one request, a check that the path works, not a measurement of typical times.

**The browser on the deployment.** Between `verify.ps1` and `down.ps1`, headless Microsoft Edge went through the start of README step 4 on the deployed address, driven by a Playwright script of the author that is not part of this repository. The address served the front end of the installed commit byte for byte and opened the page's own sign-in form, with no browser authentication dialog; a wrong password was refused on the page; the cold plate in English and in Chinese and the notebook dual-fan module opened as pre-generated examples, with the badge, the source bar and the parts that step 4 describes and a STEP file behind the download link. The page sent no request to a model endpoint and threw no error. [`browser.json`](../evidence/deploy-20261114/browser.json) records each check.

**What failed before this pass, and what changed.** Earlier the same day, `up.ps1` ran five times into another resource group. The first four runs stopped on defects that the hand-typed steps of the previous README could not have shown, and each was fixed before the next run. The scripts of this pass contain the fixes:

- `up.ps1` stopped in its preflight. Before the resource group exists, `az cognitiveservices account list -g` returns nothing, and under `Set-StrictMode` the empty result in a pipeline threw. The filters now skip empty results.
- The template was refused with `SkuNotAvailable`. East US 2 offers no `Standard_D4*_v5` or `_v4` size to the test subscription, only `_v6` sizes, and those take the NVMe disk controller only. `up.ps1` now picks the first offered size from its list and sets the disk controller to match.
- On the VM, step 1/7 waited until its time limit because it counted the resident unattended-upgrades daemon as a running package job, and step 3/7 stopped with `Permission denied`: `bootstrap_vm.sh` reads `requirements.txt` and `constraints.txt` as the user `studio` from a temporary directory that only root could read. `vm-install.sh` now waits only for apt jobs that are running and makes that directory readable.
- The fourth run stopped in step 6/7: 14 of the 15 solids were built, and the notebook dual-fan module crashed after 131 s with exit code -11. Rebuilt on the same VM, it crashed twice more at the same place, a segmentation fault in `libTKBRep` of OpenCascade 7.9.3; with the edge break off it was built in 7.2 s. The offline run on the laptop never met this crash: it used the Windows build of the same OpenCascade version. `vm-install.sh` now builds a solid that fails in this step once more without the edge break, and reports it as `no_edge_break`.
- The fifth run went into the same resource group again: `up.ps1` kept the resources, the VM size and the password and completed the install, which is the update path of README step 2, and `verify.ps1 -Full` and `down.ps1 -Yes` passed after it.

**Not covered:** the rest of step 4 in a browser: **Call GPT-6 live** (a live three.js page), **Generate STEP** clicked in the page (`verify.ps1 -Full` sent the same kind of request through the API), **Photoreal render** and the proposal; macOS or Linux as the machine that runs `up.ps1`; and the cost of the run.
