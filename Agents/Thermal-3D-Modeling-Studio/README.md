# Thermal 3D Modeling Studio: GPT-6 Writes the Model Code, OpenCascade Builds the STEP

[![Model](https://img.shields.io/badge/model-GPT--6%20Astra%202026--09--03-0078D4)](#purpose)
[![CAD kernel](https://img.shields.io/badge/CAD-CadQuery%202.8%20%C2%B7%20OpenCascade-0078D4)](#terms-used-on-this-page)
[![Scenarios](https://img.shields.io/badge/scenarios-15%20%C2%B7%20English%20%2B%20Chinese-0078D4)](#results)
[![Offline tests](https://img.shields.io/badge/offline%20tests-Python%20%2B%20Node%20%2B%20repo-0078D4)](docs/TESTING.md)

Author: Xinyu Wei · [中文](README_CN.md)

## Purpose

A thermal-management engineer often starts a new part from one sentence or a 2D drawing: "a 320 × 180 × 12 mm aluminium cold plate with six S-shaped channels", an electronic expansion valve body, a manifold module with pumps and valves. Before anyone opens SolidWorks, the team wants to turn the idea around, check its mass and heat-transfer area, compare two versions and show it in a review. Text-to-image and text-to-mesh models return a picture or a mesh with no dimensions, no mass and no STEP file.

This studio asks **GPT-6 Astra** on Microsoft Foundry to write code instead of pixels. In **Track A** it writes a complete three.js page that the browser renders as an interactive concept model. In **Track B** it writes a CadQuery script that the **OpenCascade** kernel turns into a STEP solid whose volume and mass are computed exactly. Image models only make presentation pictures (Tracks C and D).

| Deliverable | Where | Use it to |
|---|---|---|
| The studio | `studio/`: FastAPI backend, browser front end | run the demo locally or on a VM; 15 scenario cards in two groups (thermal parts, notebook manufacturing), English and Chinese UI |
| Prompts and output contracts | `studio/scenarios.py`, `CAD_PROMPT` in `studio/app.py` | see exactly what GPT-6 is told: four marked blocks for the three.js page, `PARTS` / `MATERIALS` for the CadQuery script |
| CAD runner | `studio/cad_runner.py` | run model-written CadQuery safely: allow-list check, separate process, STEP / STL / GLB export, automatic edge break |
| 15 reference CadQuery scripts | `studio/cad_examples/`, `studio/cad_examples_en/` | build 15 STEP solids with no model call; `coldplate.py` is also the worked example inside GPT-6's prompt |
| 30 recorded GPT-6 responses | `studio/cache/` | open every scenario instantly without calling Azure; the Track A numbers in Results come from these files |
| Deployment scripts | `studio/deploy/` | serve the studio from an Ubuntu 24.04 VM behind nginx and Let's Encrypt, with a managed identity instead of keys |
| Tests and the recorded run | `studio/tests/`, `tests/`, `evidence/`, `data/` | check your copy offline and compare it with the run recorded here |

What the studio is not:

- The metrics GPT-6 prints next to a Track A model are its own estimates. Track B computes volume, mass, bounding box and surface area exactly, but of a solid that GPT-6 (or a reference script) built from a description: a concept part with no tolerances or drawings, not a checked design.
- gpt-image pictures are illustrations; the model may change proportions and details. The engineering render of Track C is the picture that lines up with the STEP.
- A live call takes minutes and costs tokens (see [Results](#results)). Browsing the 15 recorded examples calls no model.

| Responsibility | Microsoft Foundry | This repository | You |
|---|---|---|---|
| Models | runs GPT-6 Astra, gpt-image-2.5 and, optionally, MAI-Image-2.6 | the prompts and output contracts | create the deployments, get the quota, pay for the tokens |
| Running the studio | — | app, CAD runner, deployment scripts | a machine or VM, a sign-in password, the Entra role on your resource |
| Engineering decisions | — | exact B-rep metrics of each generated solid | design review, tolerances, release |

<img src="images/architecture-en.png" width="900" alt="Architecture: four tracks across browser, Azure VM and Microsoft Foundry. Track A: the browser runs the three.js page GPT-6 wrote; the backend builds the prompt and streams GPT-6 Astra's answer. Track B: the CAD runner checks and runs GPT-6's CadQuery script with OpenCascade and returns STEP. Track C: gpt-image-2.5 redraws a snapshot, while the engineering renderer draws the STEP mesh with no model. Track D: concept images from gpt-image-2.5 or MAI-Image-2.6. Model calls use the VM's managed identity.">

What the figure shows: the four tracks, which code is ours, and which model each track calls. It is an original explanatory diagram; where each measured number was produced is listed under [Results](#how-the-numbers-were-produced).

### How a request moves

1. **Track A, 3D model.** The browser posts the conversation to `/api/generate`. The backend adds the system prompt (output contract plus modeling rules for the scenario) and streams GPT-6 Astra's answer back over SSE. GPT-6 writes four marked blocks: `<<<SUMMARY>>>`, a complete three.js page in `<<<HTML>>>`, the metrics as JSON in `<<<METRICS>>>`, and three follow-up ideas. When the HTML block closes, the browser starts rendering it in a sandboxed iframe while the metrics are still streaming. The last three model answers stay in the conversation, so "make the channels 8 instead of 6" edits the previous version.
2. **Track B, CAD solid.** **Generate STEP** sends the same part (your request, GPT-6's summary and the `const P = {...}` parameter block of the three.js page) to `/api/cad`. GPT-6 writes a CadQuery script. `cad_runner.py` parses it and rejects anything outside an allow-list (only `cadquery`, `math` and a few standard modules; no `open`, `exec` or exporters), runs it in a separate Python process without the server's Azure settings, breaks sharp edges with R0.3–1.2 mm fillets, and exports `model.step` (an assembly with part names), `model.stl`, `model.glb` and `parts.json`. OpenCascade computes volume, mass, bounding box and surface area from the exact solid. If the script fails, the error goes back to GPT-6, up to 3 attempts.
3. **Track C, images.** **Photoreal render** sends a WebGL snapshot of the 3D view to gpt-image-2.5 (`images.edit`). The engineering render instead draws the STEP's mesh with three.js, from the same camera as the STEP outline, so the two coincide; no image model is involved.
4. **Track D, concept image.** Before any 3D exists, a sentence becomes a concept picture (gpt-image-2.5, or MAI-Image-2.6 which can search the web first); **Build 3D from this image** attaches it to a Track A request.
5. **Proposal.** **Proposal (.docx)** assembles the request, screenshots, metrics and STEP data with python-docx, plus one GPT-6 call that writes the key points, risks and next steps.
6. **Sign-in and keys.** Visitors sign in to the studio; every model call uses the server's connection. On the VM the backend gets a Microsoft Entra token with its managed identity, locally with `az login`; the browser never receives a key or token.

### Terms used on this page

| Term | Meaning here |
|---|---|
| three.js, WebGL | a JavaScript 3D library and the browser API it draws with; Track A's output is a three.js page |
| B-rep (boundary representation) | how CAD describes a solid: exact faces (planes, cylinders, free-form surfaces) bounded by edges and closed into a volume. A Ø6 mm hole is a cylinder of radius 3 mm, not a ring of triangles |
| OpenCascade (OCCT) | open-source geometry kernel: builds B-rep solids, booleans and fillets; reads and writes STEP |
| CadQuery | Python library that describes a part as code and calls OpenCascade |
| STEP (`.step`, ISO 10303) | the exchange format CAD programs read; it carries the exact B-rep and the part names into SolidWorks, NX or Creo |
| STL, GLB (glTF) | triangle meshes. STL for 3D printing and previews; GLB for the web, with materials and a part tree. The studio shows the STEP through its GLB |
| Engineering render | a picture of the STEP's mesh drawn by three.js with no image model; it lines up with the STEP |
| Reasoning effort | how long GPT-6 thinks before it answers (`none` to `xhigh`). `.env.example` sets `none` as the server default; the selector next to the send button changes it per request |
| SSE (server-sent events) | the stream that carries tokens, progress and heartbeats from the backend to the browser |

## Results

**Videos.** Two narrated walkthroughs in English, 7:22 and 6:21 long.

*Recorded examples.* The architecture, then saved GPT-6 pages and pre-generated STEP solids opened with no model call: the electronic expansion valve as the three.js page and the code GPT-6 wrote, its OCCT solid cut by a section, the gpt-image render with the STEP outline laid over it next to the engineering render, the cost comparison for the four-way valve, and a drawing rebuilt in 3D. The video covers the thermal-management cards.

https://github.com/user-attachments/assets/66148365-f3aa-44a7-a129-cef898e68cb3

*Live generation.* One request sent live to the studio on its Azure VM: the EV battery cold plate with eight channels instead of six. GPT-6 Astra streams the three.js page, **Generate STEP** has it write the CadQuery script that OpenCascade builds, and **Photoreal render** calls gpt-image-2.5. The waits are shown in real time, uncut. It is a demonstration, not one of the measured runs below.

https://github.com/user-attachments/assets/7ee81aaa-a5f8-46e3-aae7-0410739226ed

The integrated thermal-management module, one of the 15 scenarios, as the studio shows it. The screenshots and the engineering render come from this repository's recorded run (2026-11-14) with no model call; the gpt-image picture comes from one call through the studio page on 2026-11-10. None of them is retouched.

| Track A: the three.js page GPT-6 wrote (recorded answer) | Track B: the OCCT solid of the same part, quad view |
|---|---|
| <img src="images/track-a-concept-en.jpg" width="440" alt="Studio in English with the integrated thermal-management module opened from its recorded GPT-6 answer. The source bar reads 'Current model: saved example (no GPT-6 call this time)'; the main viewport shows GPT-6's three.js concept model of the manifold with pump, valve and chiller on a grid, and the outliner lists its parts."> | <img src="images/track-b-brep-quad-en.jpg" width="440" alt="The same scenario with the OCCT B-rep solid in the quad view: top, perspective, front and right. The badge reads 'Pre-generated B-rep solid (matches STEP)'; the outliner lists the manifold body, five-way e-valve, e-pump, plate heat exchanger shell, 20 heat-exchanger plates and two quick connectors."> |

| Track C: gpt-image-2.5 redraws a 3D snapshot (illustration) | Track C: engineering render of the STEP mesh, STEP outline and edges in cyan |
|---|---|
| <img src="images/module-gpt-image-render.jpg" width="440" alt="gpt-image-2.5 picture of the integrated module: a photo-style studio shot of a black ribbed manifold carrying an aluminium valve and pump, a stainless plate heat exchanger and quick connectors. The image model redrew it from a 3D snapshot; an illustration, not geometry."> | <img src="images/module-engineering-render-step-lines.jpg" width="440" alt="Engineering render of the integrated module drawn from its STEP mesh on a light studio backdrop, with the STEP outline and edges in cyan lying on the part."> |

**What to look at.** The top row shows one part twice. On the left is the page GPT-6 wrote: its shapes and the metrics it prints are the model's own. On the right is the exact solid of the reference script, measured by OCCT. In the bottom row, gpt-image-2.5 turns a snapshot of the 3D view into a photograph-like picture, but the model redraws the part, so details can differ from the STEP. The engineering render is drawn from the STEP's own mesh, which is why the cyan STEP outline lies on it.

### More scenarios

Six of the other scenarios, from the same recorded run. On the left is the page GPT-6 wrote for the scenario card, shown as written: the scene, the panel of figures and the buttons are the model's own. On the right is the OCCT solid of the reference script in the studio's viewport. All 15 scenarios, each with its gpt-image picture, are in [docs/RESULTS.md](docs/RESULTS.md#every-scenario-at-a-glance).

| Scenario | Track A: the page GPT-6 wrote (recorded answer) | Track B: the OCCT solid of the reference script |
|---|---|---|
| EV Battery Cold Plate | <img src="images/gallery-coldplate-gpt6-en.jpg" width="360" alt="EV Battery Cold Plate: the three.js page GPT-6 wrote for this scenario card, shown as written (recorded answer)"> | <img src="images/gallery-coldplate-brep-en.jpg" width="360" alt="EV Battery Cold Plate: the OCCT B-rep solid of the reference script in the studio's 3D viewport"> |
| Electronic Expansion Valve Body | <img src="images/gallery-exv-gpt6-en.jpg" width="360" alt="Electronic Expansion Valve Body: the three.js page GPT-6 wrote for this scenario card, shown as written (recorded answer)"> | <img src="images/gallery-exv-brep-en.jpg" width="360" alt="Electronic Expansion Valve Body: the OCCT B-rep solid of the reference script in the studio's 3D viewport"> |
| Micro-channel Heat Exchanger | <img src="images/gallery-mchx-gpt6-en.jpg" width="360" alt="Micro-channel Heat Exchanger: the three.js page GPT-6 wrote for this scenario card, shown as written (recorded answer)"> | <img src="images/gallery-mchx-brep-en.jpg" width="360" alt="Micro-channel Heat Exchanger: the OCCT B-rep solid of the reference script in the studio's 3D viewport"> |
| AIDC Coolant Distribution Unit | <img src="images/gallery-cdu-gpt6-en.jpg" width="360" alt="AIDC Coolant Distribution Unit: the three.js page GPT-6 wrote for this scenario card, shown as written (recorded answer)"> | <img src="images/gallery-cdu-brep-en.jpg" width="360" alt="AIDC Coolant Distribution Unit: the OCCT B-rep solid of the reference script in the studio's 3D viewport"> |
| Vehicle Thermal Management System | <img src="images/gallery-vehicle_tms-gpt6-en.jpg" width="360" alt="Vehicle Thermal Management System: the three.js page GPT-6 wrote for this scenario card, shown as written (recorded answer)"> | <img src="images/gallery-vehicle_tms-brep-en.jpg" width="360" alt="Vehicle Thermal Management System: the OCCT B-rep solid of the reference script in the studio's 3D viewport"> |
| Notebook Dual-Fan Thermal Module | <img src="images/gallery-nb_thermal-gpt6-en.jpg" width="360" alt="Notebook Dual-Fan Thermal Module: the three.js page GPT-6 wrote for this scenario card, shown as written (recorded answer)"> | <img src="images/gallery-nb_thermal-brep-en.jpg" width="360" alt="Notebook Dual-Fan Thermal Module: the OCCT B-rep solid of the reference script in the studio's 3D viewport"> |

### Working with the solid

The viewport shows the B-rep solid through the mesh exported with its STEP, so the viewer's tools act on the real part geometry, not on GPT-6's scene.

| Section: a plane normal to Y, quad view | Isolate selection: one part of the solid alone |
|---|---|
| <img src="images/feature-section-en.jpg" width="440" alt="Quad view of the EV battery cold plate B-rep with Section set to Y: a horizontal plane cuts the plate, and the top and perspective views look into its serpentine coolant channel; the front and right views show the thin plate edge-on. The outliner lists the channel base plate, top cover, inlet fitting and outlet fitting."> | <img src="images/feature-isolate-en.jpg" width="440" alt="The EV battery cold plate B-rep in the perspective view after Isolate selection: only the channel base plate is shown, outlined in orange, with the grooves of the serpentine coolant channel and the mounting lugs; in the outliner only the channel base plate is still checked."> |

With **Section** set to Y, a horizontal plane cuts the EV battery cold plate, and the top and perspective views look into its serpentine coolant channel. With **Isolate selection**, the part selected in the outliner, here the channel base plate, is the only one left, so the channel grooves in it are in plain view.

### How the numbers were produced

<img src="images/test-topology-en.png" width="900" alt="Test topology. Track A: pregen.py on a client machine that was not recorded calls run_generation, the function behind /api/generate, which streams from the GPT-6 Astra deployment (Global Standard, resource in East US 2); the clock runs in the client from request sent to first visible token and to the parsed response. Track B: on the test laptop (Windows 11 on Arm, x64 Python under emulation) pregen_cad.py runs each reference script through cad_runner.run_script in a separate process with CadQuery and OpenCascade; the clock runs from process start to STEP, STL and GLB written. Track C: on the same laptop, headless Edge renders each model.glb with engineering-render.mjs and compares it with the STEP silhouette; the clock covers loading and 256 frames.">

What the figure shows: where each measured interval ran, what it called and what its clock includes. It is an original explanatory diagram; the machine facts come from [`evidence/run-20261113/machine.json`](evidence/run-20261113/machine.json), the Track A facts from the recorded responses in `studio/cache/`.

- **Inputs.** Track A: each scenario card's prompt in `studio/scenarios.py`, sent once per scenario and language, 30 requests from 2026-09-09 to 2026-09-12; the module prompt is quoted [verbatim](docs/RESULTS.md#track-a-gpt-6-writes-the-threejs-page). Track B: the 15 hand-written reference scripts in `studio/cad_examples/`, not GPT-6 output. Track C: the `model.glb` of each solid from that build.
- **One run per cell.** Each scenario ran once (Track A once per language), so the median and range below are across scenarios, not repeats of one request. A repeat gives a different page and a different time.
- **Not measured here:** a live Track B request, where GPT-6 writes the CadQuery script and OCCT then runs it. **Generate STEP** shows its attempts and OCCT time in the CAD tab.

| Track | Measured (unit) | Runs | Median | Range (min–max) |
|---|---|---|---|---|
| A · GPT-6 writes the page | Total time per page (s) | 30 | 149.8 | 76.1–356.2 |
| A · GPT-6 writes the page | First visible token (s) | 30 | 13.8 | 4.8–182.8 |
| A · GPT-6 writes the page | Output tokens per page | 30 | 4,900 | 3,347–8,463 |
| A · GPT-6 writes the page | Output speed after the first token (tokens/s) | 30 | 34.1 | 24.0–71.6 |
| B · OCCT builds the solid | OCCT time per scenario (s) | 15 | 59.1 | 12.0–199.2 |
| B · OCCT builds the solid | Parts per solid | 15 | 11 | 4–32 |
| C · engineering render vs STEP | Silhouette IoU with the STEP (%) | 15 | 94.1 | 15.1–97.7 |
| C · engineering render vs STEP | Render time (s) | 15 | 4.5 | 2.1–30.0 |

- **A live 3D page takes minutes.** The median page took 149.8 s and 4,900 output tokens. The recorded examples open without that wait and call no model; a live call pays off when you change the request.
- **The STEP is built locally, with no model and no network.** On this laptop one solid took 12.0–199.2 s; in the slowest, the notebook dual-fan module, the edge break took 131.6 s of it ([details](docs/RESULTS.md#track-b-opencascade-builds-the-reference-solids)).
- **The engineering render lines up with the STEP by construction, and IoU confirms it for twelve of the 15 renders (90.2–97.7 %).** The cold plate, the cold plate of the simulation estimate and the assembly line score lower because the check's segmentation misses large smooth surfaces or takes in area between thin frames; their STEP outlines still lie on the part ([details](docs/RESULTS.md#track-c-the-engineering-render-against-the-step)).

| You want to | Read |
|---|---|
| see every scenario's numbers, the inputs and the limits | [docs/RESULTS.md](docs/RESULTS.md) |
| know what each test layer checks and what it does not | [docs/TESTING.md](docs/TESTING.md) |
| inspect the recorded run: logs, per-solid metadata, render checks, machine | [evidence/run-20261113/](evidence/run-20261113/) |
| reuse the numbers | [data/results.json](data/results.json), built by `tools/build_results.py` |
| check where a picture or icon comes from | [images/SOURCES.json](images/SOURCES.json), [NOTICE.md](NOTICE.md) |

| Directory | What it holds |
|---|---|
| `studio/` | the app: FastAPI backend (`app.py`), front end (`static/`), CAD runner, prompts (`scenarios.py`), recorded GPT-6 responses (`cache/`), reference CadQuery scripts, deployment scripts (`deploy/`) and its own tests (`tests/`) |
| `tools/` | three.js download with pinned hashes, the figure renderer and its HTML sources, the screenshot tool, the results builder, the segmentation check for engineering renders |
| `tests/` | repository checks: page layout in both languages, links, images, numbers, figures, private data |
| `data/` | `results.json`: every number quoted in Results and docs/RESULTS |
| `evidence/run-20261113/` | the recorded clean run: logs, `pip freeze`, OCCT metadata per solid, render checks, browser check, machine facts |
| `images/` | screenshots, renders, the two figures and the Azure icons, each listed in `images/SOURCES.json` |
| `docs/` | results per scenario and the test guide, English and Chinese |

## Steps

| Order | Where | What | Command or script |
|---|---|---|---|
| 1 | Your machine | Install the Python dependencies | `pip install -r requirements.txt -c deploy/constraints.txt` |
| 2 | Your machine | Download three.js r160 and check its hashes | `python ../tools/vendor_three.py` |
| 3 | Your machine | Build the 15 reference STEP solids, no model call | `python pregen_cad.py` and `python pregen_cad.py --lang en` |
| 4 | Your machine | Run the offline tests | `python -m unittest ...`, `node --test ...` |
| 5 | Azure | Deploy the models and give yourself the data-plane role | `az cognitiveservices ...`, `az role assignment create ...` |
| 6 | Your machine | Configure `.env`, sign in to Azure, start the studio | `python -m uvicorn app:app --env-file .env` |
| 7 | Browser | Browse the recorded examples, then make a live call | `http://127.0.0.1:3005` |
| 8 | Azure VM, optional | Serve it over HTTPS with a managed identity | `deploy/bootstrap_vm.sh`, `deploy/deploy.ps1` |

Steps 1–4 need no Azure account and cost nothing. They were replayed in a new virtual environment on 2026-11-13 and 2026-11-14 ([recorded run](docs/TESTING.md#recorded-run)); the replay found a bug in the English-name build of step 3, which is fixed in `pregen_cad.py`, and the rerun passed. Steps 5 and 8 were not replayed for this repository: the recorded GPT-6 runs used an existing deployment, and the VM scripts are the ones the studio's own VM was set up with.

**Prerequisites.** Python 3.11 or 3.12 for x64 (CadQuery's kernel wheels are x64; the recorded run used 3.11.9 on Windows 11), Git, about 1.4 GB of disk for the virtual environment (1,324 MiB in the recorded run, with the optional tools); Node.js 18 or later for the front-end tests; Microsoft Edge for the browser check and the engineering renders; the Azure CLI and access to GPT-6 Astra in your subscription for steps 5–8.

### 1. Get the code and install

```powershell
git clone --filter=blob:none --sparse https://github.com/david-xinyuwei/david-share.git
cd david-share
git sparse-checkout set Agents/Thermal-3D-Modeling-Studio
cd Agents/Thermal-3D-Modeling-Studio/studio
py -3.11 -m venv .venv                      # Linux/macOS: python3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1                # Linux/macOS: source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -c deploy/constraints.txt
python -m pip install -r ../requirements-dev.txt   # optional: browser check and engineering renders
```

Expected: pip ends with `Successfully installed ... cadquery-2.8.0 ... fastapi-0.141.1 ...`. `deploy/constraints.txt` pins the ten packages the studio imports directly; their dependencies resolve from PyPI.

### 2. Download three.js

```powershell
python ../tools/vendor_three.py
```

Expected: `three.js 0.160.0: 15/15 files verified in ...`. The files go to `studio/static/vendor/three/` (not committed). A file whose SHA-256 differs from the pinned value is refused.

### 3. Build the 15 reference solids

```powershell
python pregen_cad.py              # cad_examples/<id>.py  -> cad_cache/<id>/
python pregen_cad.py --lang en    # English part names    -> cad_cache_en/<id>/
python ../tools/build_results.py --compare-local
```

Expected: one `[<id>] OK` line per scenario and `done. failed: none` from each build; the comparison ends with `parts, solids, bounding boxes and densities match run-20261113`. Face counts, masses and times can differ slightly from the recorded run: the edge-break pass has a time budget, so a slower machine may round off a few edges fewer. No model is called; this is the same `cad_runner.run_script` that serves a live **Generate STEP**.

### 4. Run the offline tests

```powershell
$env:AOAI_ENDPOINT = 'https://example.invalid'; $env:PORTAL_PASSWORD = 'x'; $env:AOAI_REASONING_EFFORT = 'none'
python -m unittest discover -s tests -p "test_*.py"
node --test tests/test_connection.cjs tests/test_viewer_bridge.cjs
cd ..; python -m unittest discover -s tests -v; cd studio
```

Expected: `OK` from both Python runs and `fail 0` from Node. Model calls and OCCT runs inside these tests are mocks; [docs/TESTING.md](docs/TESTING.md) lists what each layer checks and what it does not.

### 5. Deploy the models

Create an Azure OpenAI resource and a `gpt-6-astra` deployment as described in [Create and deploy an Azure OpenAI resource](https://learn.microsoft.com/azure/foundry-classic/openai/how-to/create-resource) (Azure CLI tab). The recorded runs used model version `2026-09-03`, deployment type Global Standard and 500K tokens per minute:

```bash
az cognitiveservices account deployment create --name <resource> --resource-group <group> \
  --deployment-name gpt-6-astra --model-name gpt-6-astra --model-version 2026-09-03 \
  --model-format OpenAI --sku-name GlobalStandard --sku-capacity 500
az role assignment create --role "Cognitive Services OpenAI User" \
  --assignee "$(az ad signed-in-user show --query id -o tsv)" \
  --scope "$(az cognitiveservices account show --name <resource> --resource-group <group> --query id -o tsv)"
```

Optional: a `gpt-image-2.5-sunburst` (or `-flare`) deployment on the same resource for Tracks C and D, and an MAI-Image-2.6 deployment on a Foundry resource for the second concept-image provider. Expected: `az cognitiveservices account deployment list --name <resource> --resource-group <group> -o table` shows `gpt-6-astra` with `GlobalStandard`. The role can take a few minutes to apply. [Cognitive Services OpenAI User](https://learn.microsoft.com/azure/foundry-classic/openai/how-to/role-based-access-control) is the role that allows inference calls with Microsoft Entra ID.

### 6. Configure and start

```powershell
Copy-Item .env.example .env       # Linux/macOS: cp .env.example .env
# edit .env: AOAI_ENDPOINT=https://<resource>.openai.azure.com, PORTAL_PASSWORD, PORTAL_SESSION_SECRET
#            and, for Tracks C and D, AOAI_IMAGE_DEPLOYMENT=gpt-image-2.5-sunburst
az login
python -m uvicorn app:app --host 127.0.0.1 --port 3005 --env-file .env
```

Expected: `Uvicorn running on http://127.0.0.1:3005`; `curl http://127.0.0.1:3005/healthz` returns `{"ok":true,"deployment":"gpt-6-astra",...}`. Without `AZURE_CLIENT_ID` the backend takes its Entra token from the Azure CLI. `.env` stays out of Git (`.gitignore`); the browser never receives it.

### 7. Use it

1. Open `http://127.0.0.1:3005` and sign in with `PORTAL_USERNAME` (default `studio`) and your `PORTAL_PASSWORD`.
2. Pick a scenario card. The badge says **Pre-generated example** and the source bar "saved example (no GPT-6 call this time)": a recorded GPT-6 answer and the reference STEP solid open with no model call.
3. Click **Call GPT-6 live**. The source bar switches to the live request ID once the answer arrives; [Results](#results) shows how long that took in the recorded runs.
4. Click **Generate STEP**. The CAD tab shows the attempts, the OCCT time and the B-rep metrics, with downloads for STEP, STL and the CadQuery script.

Stop the studio with `Ctrl+C`. Global Standard deployments bill per token; an idle studio costs nothing on the model side.

### 8. Optional: an Azure VM over HTTPS

The scripts expect Ubuntu 24.04, a DNS name for the VM, inbound 80 and 443 (Let's Encrypt and HTTPS), SSH from your address, and a user-assigned managed identity on the VM with **Cognitive Services OpenAI User** on your resource.

```bash
# copy the setup files to the VM, then run the one-time setup as root
scp deploy/bootstrap_vm.sh deploy/constraints.txt deploy/nginx-thermal-3d-studio.conf requirements.txt azureuser@<vm-fqdn>:~/setup/
ssh azureuser@<vm-fqdn> "sudo bash ~/setup/bootstrap_vm.sh <vm-fqdn>"
# put your .env on the VM: AZURE_CLIENT_ID=<managed identity client id>, PUBLIC_BASE_URL=https://<vm-fqdn>
scp .env azureuser@<vm-fqdn>:~/setup/.env
ssh azureuser@<vm-fqdn> "sudo install -o studio -g studio -m 600 ~/setup/.env /opt/thermal-3d-studio/.env && rm ~/setup/.env"
```

```powershell
.\deploy\deploy.ps1 -SshHost azureuser@<vm-fqdn> -PublicUrl https://<vm-fqdn>/
```

Expected: `bootstrap_vm.sh` ends with `BOOTSTRAP_DONE`; `deploy.ps1` prints `>> healthy: {"ok":true,...}` from the VM and then `>> done: https://<vm-fqdn>/`. The service runs as the unprivileged user `studio` on `127.0.0.1:3005`; nginx terminates TLS on 443 and passes the SSE streams through unbuffered. A VM bills while it runs; deallocate it with `az vm deallocate` when you do not need it.
