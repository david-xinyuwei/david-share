# Testing

[中文](TESTING_CN.md) · [README](../README.md)

Six layers, from cheapest to most expensive. The first three need no Azure account; the browser check and the engineering renders need Microsoft Edge; only the deployment and the live checks create Azure resources or call a model, and cost money.

## What each layer checks

| Layer | Command (in `studio/` unless noted) | Needs | Checks | Does not check |
|---|---|---|---|---|
| Python unit and contract tests, 73 | `python -m unittest discover -s tests -p "test_*.py"` | the venv; the 15 reference solids from `pregen_cad.py` | output contracts and parsing, SSE events and heartbeats, sign-in and sessions, input limits, the server-managed connection (no key reaches the browser), the CAD allow-list, the retry loop that feeds errors back, cancel and kill of the OCCT child, cached results served like live ones, the proposal `.docx`, a reasoning effort the deployment refuses (the 400 of 2026-11-14) sent as the next higher accepted value | a real model answer (mocked) and a real OCCT run (mocked), except that every reference script must pass the same allow-list as model output and have a fresh build |
| Node front-end tests, 38 | `node --test tests/test_connection.cjs tests/test_viewer_bridge.cjs` | Node.js 18+, three.js from `tools/vendor_three.py` | connection dialog in server-managed mode, render-ready detection from real WebGL draw calls, failure reporting, PNG and GLB export rules, quad-view layout and framing | real WebGL pixels (the canvas is simulated) |
| Real OCCT build, 15 solids | `python pregen_cad.py`, then `python pregen_cad.py --lang en` | the venv | every reference script runs through `cad_runner.run_script` and writes STEP, STL, GLB and `parts.json`; the English build has the same solids under English names | CadQuery scripts written by GPT-6 (those only run live) |
| Browser check, 23 steps | `python tests/check_workspace_browser.py --headless --output <dir>` with the studio on `127.0.0.1:8015` (below) | Edge, `requirements-dev.txt` | the served files equal the source; a scenario opens with its pre-generated STEP solid; ambient occlusion darkens the part; shading, section, isolation and both exports work; English UI; 390 px narrow screen; a scene written to the current prompt renders through the same bridge; no request reaches a model endpoint | GPU rendering (it uses software WebGL); a live model result |
| Engineering renders, 15 | `python pregen_engineering.py <ids> --out <dir> --no-install` | Edge, `requirements-dev.txt`, the solids from `pregen_cad.py` | each STEP mesh renders with no unmatched part, and the silhouette IoU between the picture and the STEP from the same camera | the gpt-image render (that one needs Azure) |
| Deployment, end to end | `./infra/up.ps1`, `./infra/verify.ps1 -Full`, `./infra/down.ps1` in the repository root (README steps 2, 3 and 5) | an Azure subscription with quota (README [Steps](../README.md#steps)), Azure CLI, PowerShell 7.3 | every resource is created from `infra/main.bicep` in a new resource group; the VM installs the studio from the repository and serves HTTPS with a Let's Encrypt certificate; through that address: health, the HTTP redirect, a wrong password refused, sign-in, the 15 scenarios, the pre-generated solid of every scenario in both languages, one GPT-6 call with the VM's managed identity, a live **Generate STEP** with its STEP file downloaded and one gpt-image concept picture; the removal leaves no resource group and no soft-deleted AI resource | the browser UI on the VM (the browser check covers the same pages locally), a live three.js page, **Photoreal render** and the proposal; the cost |
| Live checks, manual | **Call GPT-6 live**, **Photoreal render**, **Proposal (.docx)** in the UI | a deployment (README step 2) | the real model path end to end | not automated; each click costs tokens. `verify.ps1 -Full` covers **Generate STEP** and the concept picture |

### Browser check

```powershell
$env:PORTAL_USERNAME = 'preview'; $env:PORTAL_PASSWORD = 'local-ui-test-only'
$env:AOAI_ENDPOINT = 'https://example.invalid'; $env:AOAI_REASONING_EFFORT = 'low'
Start-Process python -ArgumentList '-m','uvicorn','app:app','--host','127.0.0.1','--port','8015'
python tests/check_workspace_browser.py --headless --output $env:TEMP\studio-browser-check
```

Expected: 23 `PASS <step>` lines and `{"status": "PASS", "checks": 23, ...}`. The check fails if any request reaches `/api/generate`, `/api/cad`, `/api/render`, `/api/concept` or `/api/proposal` (the one `/api/cad` it needs is answered inside the browser from `tests/fixtures/`). Stop the server afterwards.

### Engineering renders

```powershell
python pregen_engineering.py aidc aps cdu coldplate drawing2d exv fourway mchx module nb_assembly_line nb_chassis_mold nb_packing nb_thermal thermal_sim vehicle_tms --out $env:TEMP\studio-engineering --no-install
```

Expected: one JSON line per scenario with `"ok": true` and an `iou_pct`. Without `--no-install` the pictures also go to `render_cache/<id>/`, where the studio's render tab picks them up.
