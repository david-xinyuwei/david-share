# Results per scenario

[中文](RESULTS_CN.md) · [README](../README.md) · [Testing](TESTING.md)

Every number on this page is copied from [`data/results.json`](../data/results.json), which `tools/build_results.py` builds from the 30 recorded responses in `studio/cache/` and the run recorded in [`evidence/run-20261113/`](../evidence/run-20261113/). `tests/test_repo.py` fails if a number here has no value in that file. Where each number was measured is in the README under [How the numbers were produced](../README.md#how-the-numbers-were-produced).

## Every scenario at a glance

The 15 scenarios as the studio shows them. Tracks A and B are screenshots from the recorded run (2026-11-14, no model call): the page GPT-6 wrote for the scenario card, shown as written, and the OCCT solid of the reference script in the studio's viewport. Track C is the picture gpt-image-2.5 drew from a snapshot of that solid, one call per scenario through the studio page on 2026-11-10. It is an illustration: the image model redraws the part, so details can differ from the STEP ([Track C](#track-c-the-engineering-render-against-the-step) shows by how much for the module). The 2D Drawing / Photo → 3D card sends a sample drawing, `studio/static/samples/exv_body_drawing.png`, with its prompt.

| Scenario | Track A: the page GPT-6 wrote | Track B: the OCCT solid | Track C: gpt-image-2.5 redraw (illustration) |
|---|---|---|---|
| EV Battery Cold Plate | <img src="../images/gallery-coldplate-gpt6-en.jpg" width="260" alt="EV Battery Cold Plate: the three.js page GPT-6 wrote for this scenario card, shown as written (recorded answer)"> | <img src="../images/gallery-coldplate-brep-en.jpg" width="260" alt="EV Battery Cold Plate: the OCCT B-rep solid of the reference script in the studio's 3D viewport"> | <img src="../images/render-coldplate.jpg" width="260" alt="EV Battery Cold Plate: gpt-image-2.5 redraw of a snapshot of the solid; an illustration, not geometry"> |
| Micro-channel Heat Exchanger | <img src="../images/gallery-mchx-gpt6-en.jpg" width="260" alt="Micro-channel Heat Exchanger: the three.js page GPT-6 wrote for this scenario card, shown as written (recorded answer)"> | <img src="../images/gallery-mchx-brep-en.jpg" width="260" alt="Micro-channel Heat Exchanger: the OCCT B-rep solid of the reference script in the studio's 3D viewport"> | <img src="../images/render-mchx.jpg" width="260" alt="Micro-channel Heat Exchanger: gpt-image-2.5 redraw of a snapshot of the solid; an illustration, not geometry"> |
| Electronic Expansion Valve Body | <img src="../images/gallery-exv-gpt6-en.jpg" width="260" alt="Electronic Expansion Valve Body: the three.js page GPT-6 wrote for this scenario card, shown as written (recorded answer)"> | <img src="../images/gallery-exv-brep-en.jpg" width="260" alt="Electronic Expansion Valve Body: the OCCT B-rep solid of the reference script in the studio's 3D viewport"> | <img src="../images/render-exv.jpg" width="260" alt="Electronic Expansion Valve Body: gpt-image-2.5 redraw of a snapshot of the solid; an illustration, not geometry"> |
| 2D Drawing / Photo → 3D | <img src="../images/gallery-drawing2d-gpt6-en.jpg" width="260" alt="2D Drawing / Photo → 3D: the three.js page GPT-6 wrote for this scenario card, shown as written (recorded answer)"> | <img src="../images/gallery-drawing2d-brep-en.jpg" width="260" alt="2D Drawing / Photo → 3D: the OCCT B-rep solid of the reference script in the studio's 3D viewport"> | <img src="../images/render-drawing2d.jpg" width="260" alt="2D Drawing / Photo → 3D: gpt-image-2.5 redraw of a snapshot of the solid; an illustration, not geometry"> |
| AIDC GPU Liquid-cooling Cold Plate | <img src="../images/gallery-aidc-gpt6-en.jpg" width="260" alt="AIDC GPU Liquid-cooling Cold Plate: the three.js page GPT-6 wrote for this scenario card, shown as written (recorded answer)"> | <img src="../images/gallery-aidc-brep-en.jpg" width="260" alt="AIDC GPU Liquid-cooling Cold Plate: the OCCT B-rep solid of the reference script in the studio's 3D viewport"> | <img src="../images/render-aidc.jpg" width="260" alt="AIDC GPU Liquid-cooling Cold Plate: gpt-image-2.5 redraw of a snapshot of the solid; an illustration, not geometry"> |
| 4-way Reversing Valve · Copper Reduction | <img src="../images/gallery-fourway-gpt6-en.jpg" width="260" alt="4-way Reversing Valve · Copper Reduction: the three.js page GPT-6 wrote for this scenario card, shown as written (recorded answer)"> | <img src="../images/gallery-fourway-brep-en.jpg" width="260" alt="4-way Reversing Valve · Copper Reduction: the OCCT B-rep solid of the reference script in the studio's 3D viewport"> | <img src="../images/render-fourway.jpg" width="260" alt="4-way Reversing Valve · Copper Reduction: gpt-image-2.5 redraw of a snapshot of the solid; an illustration, not geometry"> |
| Integrated Thermal Management Module | <img src="../images/gallery-module-gpt6-en.jpg" width="260" alt="Integrated Thermal Management Module: the three.js page GPT-6 wrote for this scenario card, shown as written (recorded answer)"> | <img src="../images/gallery-module-brep-en.jpg" width="260" alt="Integrated Thermal Management Module: the OCCT B-rep solid of the reference script in the studio's 3D viewport"> | <img src="../images/module-gpt-image-render.jpg" width="260" alt="Integrated Thermal Management Module: gpt-image-2.5 redraw of a snapshot of the solid; an illustration, not geometry"> |
| AI-assisted Simulation Estimate | <img src="../images/gallery-thermal_sim-gpt6-en.jpg" width="260" alt="AI-assisted Simulation Estimate: the three.js page GPT-6 wrote for this scenario card, shown as written (recorded answer)"> | <img src="../images/gallery-thermal_sim-brep-en.jpg" width="260" alt="AI-assisted Simulation Estimate: the OCCT B-rep solid of the reference script in the studio's 3D viewport"> | <img src="../images/render-thermal_sim.jpg" width="260" alt="AI-assisted Simulation Estimate: gpt-image-2.5 redraw of a snapshot of the solid; an illustration, not geometry"> |
| APS Scheduling Reasoning | <img src="../images/gallery-aps-gpt6-en.jpg" width="260" alt="APS Scheduling Reasoning: the three.js page GPT-6 wrote for this scenario card, shown as written (recorded answer)"> | <img src="../images/gallery-aps-brep-en.jpg" width="260" alt="APS Scheduling Reasoning: the OCCT B-rep solid of the reference script in the studio's 3D viewport"> | <img src="../images/render-aps.jpg" width="260" alt="APS Scheduling Reasoning: gpt-image-2.5 redraw of a snapshot of the solid; an illustration, not geometry"> |
| Vehicle Thermal Management System | <img src="../images/gallery-vehicle_tms-gpt6-en.jpg" width="260" alt="Vehicle Thermal Management System: the three.js page GPT-6 wrote for this scenario card, shown as written (recorded answer)"> | <img src="../images/gallery-vehicle_tms-brep-en.jpg" width="260" alt="Vehicle Thermal Management System: the OCCT B-rep solid of the reference script in the studio's 3D viewport"> | <img src="../images/render-vehicle_tms.jpg" width="260" alt="Vehicle Thermal Management System: gpt-image-2.5 redraw of a snapshot of the solid; an illustration, not geometry"> |
| AIDC Coolant Distribution Unit | <img src="../images/gallery-cdu-gpt6-en.jpg" width="260" alt="AIDC Coolant Distribution Unit: the three.js page GPT-6 wrote for this scenario card, shown as written (recorded answer)"> | <img src="../images/gallery-cdu-brep-en.jpg" width="260" alt="AIDC Coolant Distribution Unit: the OCCT B-rep solid of the reference script in the studio's 3D viewport"> | <img src="../images/render-cdu.jpg" width="260" alt="AIDC Coolant Distribution Unit: gpt-image-2.5 redraw of a snapshot of the solid; an illustration, not geometry"> |
| Notebook Dual-Fan Thermal Module | <img src="../images/gallery-nb_thermal-gpt6-en.jpg" width="260" alt="Notebook Dual-Fan Thermal Module: the three.js page GPT-6 wrote for this scenario card, shown as written (recorded answer)"> | <img src="../images/gallery-nb_thermal-brep-en.jpg" width="260" alt="Notebook Dual-Fan Thermal Module: the OCCT B-rep solid of the reference script in the studio's 3D viewport"> | <img src="../images/render-nb_thermal.jpg" width="260" alt="Notebook Dual-Fan Thermal Module: gpt-image-2.5 redraw of a snapshot of the solid; an illustration, not geometry"> |
| Magnesium A-Cover & Die-Casting Mold Concept | <img src="../images/gallery-nb_chassis_mold-gpt6-en.jpg" width="260" alt="Magnesium A-Cover &amp; Die-Casting Mold Concept: the three.js page GPT-6 wrote for this scenario card, shown as written (recorded answer)"> | <img src="../images/gallery-nb_chassis_mold-brep-en.jpg" width="260" alt="Magnesium A-Cover &amp; Die-Casting Mold Concept: the OCCT B-rep solid of the reference script in the studio's 3D viewport"> | <img src="../images/render-nb_chassis_mold.jpg" width="260" alt="Magnesium A-Cover &amp; Die-Casting Mold Concept: gpt-image-2.5 redraw of a snapshot of the solid; an illustration, not geometry"> |
| Notebook Assembly-Line Digital Twin | <img src="../images/gallery-nb_assembly_line-gpt6-en.jpg" width="260" alt="Notebook Assembly-Line Digital Twin: the three.js page GPT-6 wrote for this scenario card, shown as written (recorded answer)"> | <img src="../images/gallery-nb_assembly_line-brep-en.jpg" width="260" alt="Notebook Assembly-Line Digital Twin: the OCCT B-rep solid of the reference script in the studio's 3D viewport"> | <img src="../images/render-nb_assembly_line.jpg" width="260" alt="Notebook Assembly-Line Digital Twin: gpt-image-2.5 redraw of a snapshot of the solid; an illustration, not geometry"> |
| Packaging & Container-Loading Optimisation | <img src="../images/gallery-nb_packing-gpt6-en.jpg" width="260" alt="Packaging &amp; Container-Loading Optimisation: the three.js page GPT-6 wrote for this scenario card, shown as written (recorded answer)"> | <img src="../images/gallery-nb_packing-brep-en.jpg" width="260" alt="Packaging &amp; Container-Loading Optimisation: the OCCT B-rep solid of the reference script in the studio's 3D viewport"> | <img src="../images/render-nb_packing.jpg" width="260" alt="Packaging &amp; Container-Loading Optimisation: gpt-image-2.5 redraw of a snapshot of the solid; an illustration, not geometry"> |

**One recorded page fails.** GPT-6's Chinese page for the notebook assembly line stops with `TypeError: Cannot read properties of undefined (reading 'x')` in every attempt of this run: its animation loop asks three.js `CatmullRomCurve3.getPointAt` for a point on a curve that has an undefined control point. The line is drawn, but the page's own error banner covers it (the Chinese picture on [the Chinese page](RESULTS_CN.md#15-个场景一览)), and the studio reports that the scene did not render. The English page for the same card, above, runs. The pictures show what GPT-6 wrote, errors included.

## Track A: GPT-6 writes the three.js page

**Input.** For each of the 15 scenario cards, the card's prompt in `studio/scenarios.py` (`prompt` for the Chinese UI, `prompt_en` for the English UI) as the only user message, with that scenario's system prompt. One request per scenario and language. Example, the integrated module in English, verbatim:

> Model a concept assembly of an EV integrated thermal-management module: a central engineering-plastic manifold 260×160×60 mm with two φ16 mm main coolant passages; mounted on it a 5-way electronic coolant valve (φ60×70 mm, aluminium housing), an electronic coolant pump (φ70×90 mm, aluminium housing with outlet), a plate heat exchanger chiller (120×80×60 mm, stainless steel, 20 plates may be simplified) and two φ16 mm quick-connect fittings. Provide the 3D model with an “Exploded view” button that separates each component along its own direction, and report the part count, per-part mass and total module mass.

**What was measured.** `pregen.py` sent each request through the same `run_generation` function that serves `/api/generate` and saved the response to `studio/cache/`. *Total time* runs from sending the request to the parsed response; *first visible token* is when the first token of the answer arrived. *Output tokens* is the API's `completion_tokens` (it includes reasoning tokens when there were any); *output speed* is visible output tokens divided by the time after the first visible token. The page length counts the lines of the three.js HTML.

| Scenario | Total time (s): Chinese / English | First visible token (s): Chinese / English | Output tokens: Chinese / English | Output speed after the first token (tokens/s): Chinese / English | Page length (lines): Chinese / English |
|---|---|---|---|---|---|
| EV Battery Cold Plate | 356.2 / 170.4 | 182.8 / 25.8 | 8,463 / 3,757 | 34.0 / 26.0 | 416 / 207 |
| Micro-channel Heat Exchanger | 148.1 / 110.0 | 53.7 / 7.4 | 4,195 / 3,805 | 37.6 / 37.1 | 216 / 203 |
| Electronic Expansion Valve Body | 144.8 / 120.0 | 16.4 / 5.8 | 3,849 / 4,103 | 30.0 / 35.9 | 188 / 205 |
| 2D Drawing / Photo → 3D | 101.0 / 123.9 | 10.8 / 16.7 | 3,347 / 3,680 | 37.1 / 34.3 | 190 / 203 |
| AIDC GPU Liquid-cooling Cold Plate | 152.6 / 164.0 | 13.8 / 11.2 | 4,070 / 4,032 | 29.3 / 26.4 | 204 / 203 |
| 4-way Reversing Valve · Copper Reduction | 155.1 / 184.4 | 13.7 / 11.2 | 4,281 / 4,620 | 30.3 / 26.7 | 197 / 195 |
| Integrated Thermal Management Module | 142.6 / 127.1 | 9.1 / 19.9 | 4,244 / 3,927 | 31.8 / 36.6 | 213 / 191 |
| AI-assisted Simulation Estimate | 290.6 / 193.1 | 75.0 / 7.1 | 5,238 / 4,774 | 24.3 / 25.7 | 253 / 251 |
| APS Scheduling Reasoning | 180.2 / 151.4 | 14.3 / 6.7 | 4,888 / 4,942 | 29.5 / 34.2 | 233 / 246 |
| Vehicle Thermal Management System | 314.3 / 277.4 | 26.7 / 14.3 | 7,914 / 6,320 | 27.5 / 24.0 | 287 / 281 |
| AIDC Coolant Distribution Unit | 320.1 / 249.4 | 53.8 / 30.1 | 6,874 / 6,783 | 25.8 / 30.9 | 300 / 293 |
| Notebook Dual-Fan Thermal Module | 162.5 / 143.0 | 48.9 / 29.7 | 7,845 / 7,313 | 69.1 / 64.5 | 330 / 291 |
| Magnesium A-Cover & Die-Casting Mold Concept | 85.0 / 84.0 | 8.6 / 4.8 | 5,473 / 5,533 | 71.6 / 69.9 | 219 / 213 |
| Notebook Assembly-Line Digital Twin | 113.4 / 116.0 | 5.6 / 6.7 | 7,457 / 6,929 | 69.2 / 63.4 | 344 / 323 |
| Packaging & Container-Loading Optimisation | 87.5 / 76.1 | 8.4 / 7.3 | 5,624 / 4,913 | 71.1 / 71.4 | 213 / 211 |

- **Reasoning effort.** Only the 12 runs saved from 2026-09-10 09:11 UTC on record the effort that was sent, and all 12 sent `none`; the 18 earlier runs did not record it. Two of those 18 used reasoning tokens: the Chinese cold plate (2,559) and the Chinese micro-channel heat exchanger (650). Reasoning tokens are produced before the first visible token, and the Chinese cold plate also had the longest wait for it, 182.8 s.
- **Two speeds.** The 8 notebook runs recorded on 2026-09-12 streamed at 63.4–71.6 tokens/s; every other run streamed at 24.0–37.6 tokens/s. All 30 runs called the deployment `gpt-6-astra`; every run that recorded the model version returned `gpt-6-astra-2026-09-03`, and the first seven, saved on 2026-09-09, did not record it. The cause of the difference is not established (service load is one candidate, not tested).
- **Single runs.** Each cell is one response. A repeat of the same prompt gives a different page, different metrics and a different time.

## Track B: OpenCascade builds the reference solids

**Input.** `studio/cad_examples/<scenario>.py`: 15 hand-written CadQuery scripts that follow the same contract GPT-6 is given (`PARTS`, `MATERIALS`, real fillets, bores, grooves) and pass the same allow-list check. They are not GPT-6 output.

**What was measured.** `python pregen_cad.py` ran each script through `cad_runner.run_script`, the function a live **Generate STEP** uses, on the test laptop on 2026-11-13. *OCCT time* runs from starting the separate Python process until it exits after writing STEP, STL and GLB: starting Python, importing CadQuery, building the solid, the edge-break pass and the exports. The edge-break pass has a time budget, `CAD_EDGE_FINISH_BUDGET_S`: `200` s per scenario in `pregen_cad.py`; a live request keeps the default, `40` s. *Edges rounded* counts the sharp edges that got a fillet out of the candidates found; parts made of more than `12` solids (fin packs, tube arrays, pallets) are skipped.

<img src="../images/track-b-cad-tab-en.jpg" width="800" alt="CAD tab of the integrated module in the English UI: buttons Download STEP, Download STL and Download CadQuery script, an STL preview of the solid, and a table of metrics computed by OCCT: volume, mass, bounding box and surface area of the STEP solid.">

The CAD tab of the integrated module with its pre-generated solid; a live **Generate STEP** result appears in the same place. It offers the STEP, the STL and the CadQuery script for download, an STL preview, and the metrics OCCT computed from the B-rep: volume, mass, bounding box and surface area. The table below lists these for every scenario.

| Scenario | Parts | Solids | Faces | Mass (kg) | Bounding box (mm) | Edges rounded / candidate edges | OCCT time (s) | of which edge break (s) | STEP size (MB) |
|---|---|---|---|---|---|---|---|---|---|
| EV Battery Cold Plate | 4 | 1 | 284 | 1.582 | 360 × 180 × 13.5 | 77 / 238 | 68.7 | 52.0 | 1.2 |
| Micro-channel Heat Exchanger | 8 | 306 | 3,504 | 0.384 | 371 × 49.5 × 216.8 | 484 / 484 | 86.3 | 61.6 | 16.2 |
| Electronic Expansion Valve Body | 6 | 2 | 181 | 0.488 | 68 × 36 × 124 | 87 / 112 | 49.0 | 38.6 | 1.4 |
| 2D Drawing / Photo → 3D | 4 | 4 | 59 | 0.384 | 72 × 32 × 136 | 29 / 35 | 14.1 | 6.1 | 0.3 |
| AIDC GPU Liquid-cooling Cold Plate | 5 | 1 | 570 | 0.511 | 140 × 90 × 10 | 98 / 252 | 138.0 | 54.9 | 1.9 |
| 4-way Reversing Valve · Copper Reduction | 12 | 2 | 304 | 0.656 | 116 × 50 × 92 | 134 / 154 | 46.7 | 31.3 | 2.3 |
| Integrated Thermal Management Module | 7 | 25 | 796 | 4.023 | 322 × 168 × 152 | 277 / 542 | 110.5 | 86.4 | 4.1 |
| AI-assisted Simulation Estimate | 12 | 12 | 432 | 1.750 | 362 × 180 × 20 | 228 / 248 | 34.6 | 5.8 | 1.4 |
| APS Scheduling Reasoning | 15 | 121 | 2,308 | 12.503 | 1105 × 530 × 32 | 964 / 964 | 59.1 | 10.3 | 6.9 |
| Vehicle Thermal Management System | 29 | 202 | 1,901 | 879.344 | 3316 × 1480 × 870 | 0 / 0 | 19.7 | 0.0 | 6.9 |
| AIDC Coolant Distribution Unit | 32 | 289 | 1,928 | 2,943.824 | 8410 × 1205 × 2100 | 0 / 0 | 31.5 | 0.0 | 6.1 |
| Notebook Dual-Fan Thermal Module | 14 | 278 | 3,302 | 0.096 | 280 × 190 × 9 | 283 / 588 | 199.2 | 131.6 | 11.2 |
| Magnesium A-Cover & Die-Casting Mold Concept | 4 | 2 | 500 | 14.680 | 392 × 297 × 73.3 | 194 / 304 | 76.9 | 59.2 | 1.9 |
| Notebook Assembly-Line Digital Twin | 31 | 151 | 1,571 | 9,855.507 | 28850 × 18450 × 2700 | 0 / 0 | 12.0 | 0.0 | 5.2 |
| Packaging & Container-Loading Optimisation | 11 | 1038 | 7,022 | 13,348.454 | 14696 × 2498 × 2896 | 240 / 240 | 70.9 | 8.1 | 19.6 |

- **Five scenes are layouts, not parts.** The APS scheduling sand table, the vehicle thermal management system, the CDU row with eight racks, the notebook assembly line and the packaging and container loading model a system or a plan. Their mass is the volume of every modeled solid times the density the script gives it: a property of the layout model, not of a product you could weigh.
- **`0 / 0` edges is intended** for the vehicle system, the CDU row and the assembly line. Their scripts set `EDGE_FINISH = 0`, because a sub-millimetre edge break is invisible at metre scale. Where fewer edges were rounded than found, OCCT rejected the rest or the time budget ran out; every fillet step is checked (one valid solid, volume within `5` %), so each part stays a valid solid.
- **Where the time goes.** Every scenario starts a new Python process and imports CadQuery before it models anything. In the slowest build, the notebook dual-fan module, the edge break took 131.6 of 199.2 s.

## Track C: the engineering render against the STEP

Track C makes two kinds of picture. **Photoreal render** sends a snapshot of the 3D view to gpt-image-2.5, which redraws it as a presentation picture; those are the pictures in the last column of the [table above](#every-scenario-at-a-glance). With **Overlay CAD**, the **Render** tab lays the outline and edges of the STEP view that the snapshot was taken from over the picture. The image model re-frames what it draws, so the outline is placed with one uniform scale and a shift, never stretched or rotated; wherever a cyan line does not lie on the part, the picture departs from the STEP. The note beside the picture gives the silhouette IoU of that fit and calls it indicative.

<img src="../images/render-tab-en.jpg" width="800" alt="The studio's Render tab for the integrated module in the English UI: the pre-generated gpt-image-2.5 picture of the module with Overlay CAD on, so the cyan outline and edges of the STEP view lie over the redrawn part. Beside it, the toggle between the gpt-image visualization and the engineering render, and the note that explains the fit and gives its silhouette IoU.">

The engineering render is the other kind of picture: three.js draws the STEP's own mesh with the camera of its outline, so nothing has to be fitted. The rest of this section measures it.

**Input.** The `model.glb` of each solid built above: the STEP's own triangle mesh.

**What was measured.** `python pregen_engineering.py <15 scenarios> --out <dir> --no-install` rendered each mesh in headless Edge at 2048×1152 with 256 accumulated frames, drew the STEP outline and edges with the same camera, and compared the part area segmented from the finished picture with the STEP silhouette. *IoU* is overlap divided by union; *outline offset* is the distance in pixels from each STEP outline pixel to the segmented outline. Nothing is scaled or shifted to make them match.

| Scenario | Silhouette IoU with the STEP (%) | Outline offset, median (px) | Outline offset, 90th percentile (px) | Render time (s) |
|---|---|---|---|---|
| EV Battery Cold Plate | 17.2 | 10.6 | 369.6 | 2.5 |
| Micro-channel Heat Exchanger | 95.1 | 3.0 | 17.0 | 14.0 |
| Electronic Expansion Valve Body | 94.1 | 3.2 | 4.0 | 2.4 |
| 2D Drawing / Photo → 3D | 93.8 | 3.2 | 4.0 | 2.1 |
| AIDC GPU Liquid-cooling Cold Plate | 91.1 | 11.4 | 45.8 | 3.9 |
| 4-way Reversing Valve · Copper Reduction | 94.7 | 3.2 | 15.6 | 2.5 |
| Integrated Thermal Management Module | 97.5 | 3.2 | 4.1 | 3.6 |
| AI-assisted Simulation Estimate | 15.1 | 13.0 | 314.5 | 4.5 |
| APS Scheduling Reasoning | 94.4 | 3.6 | 4.1 | 10.8 |
| Vehicle Thermal Management System | 90.2 | 3.6 | 22.8 | 8.9 |
| AIDC Coolant Distribution Unit | 90.4 | 3.6 | 17.0 | 10.3 |
| Notebook Dual-Fan Thermal Module | 97.7 | 3.2 | 3.6 | 13.6 |
| Magnesium A-Cover & Die-Casting Mold Concept | 97.5 | 3.6 | 6.3 | 2.7 |
| Notebook Assembly-Line Digital Twin | 68.0 | 8.5 | 38.6 | 8.6 |
| Packaging & Container-Loading Optimisation | 96.3 | 3.2 | 5.0 | 30.0 |

- **What the IoU checks.** The picture and the cyan STEP lines come from the same mesh and the same camera, so they cannot drift apart. IoU checks that the finished picture shows the part where the STEP silhouette is, and it is only as good as the segmentation that finds the part in the picture: `part_area()` in `studio/pregen_render_cad.py`, which looks for edges and shading against the plain backdrop.
- **Twelve renders score 90.2–97.7 %.** For them the segmentation found the whole STEP silhouette and a little around it.
- **Three score low because of the segmentation, not the render.** The EV battery cold plate (17.2 %) and the cold plate of the simulation estimate (15.1 %) are large, smooth, light plates: the segmentation found their edges and small features but missed most of the flat top. The assembly line (68.0 %) is made of thin frames, and the segmentation also took in area around and between them. The cold plate has the lowest IoU, and its STEP outline still lies on the plate:

<img src="../images/coldplate-engineering-render-step-lines.jpg" width="800" alt="Engineering render of the EV battery cold plate on a light backdrop: a large, flat, light-grey plate with two ports and mounting lugs. The cyan STEP outline and edges lie on the plate's outer edge, its slots and its lugs.">

- **How to check it yourself.** `python tools/segmentation_check.py <dir>` reads the pictures that `pregen_engineering.py --out <dir>` writes and reports, per scenario, how much of the STEP silhouette the segmentation found and how much of what it found lies inside the silhouette. [`segmentation-check.json`](../evidence/run-20261113/engineering/segmentation-check.json) is its output for this run.
- **Render time** was 2.1–30.0 s per picture on the laptop's integrated GPU; the packaging scene, with 1,038 solids, took the longest.

## Limits

- One machine for Tracks B and C: a Windows on Arm laptop running x64 Python under emulation. Times on a native x64 machine or the Linux VM were not measured for this repository. One resource and one deployment for Track A.
- Track A shows what the model wrote once per scenario, not its average quality or speed.
- The live Track B path (GPT-6 writes the CadQuery script, OCCT runs it) is not timed in this repository's evidence. Run **Generate STEP** to see your own attempts and times in the CAD tab.
- Each scenario's gpt-image picture was made once through the studio page on 2026-11-10 and is shown as saved.
