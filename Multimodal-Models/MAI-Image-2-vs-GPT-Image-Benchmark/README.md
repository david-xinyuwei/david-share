# MAI-Image-2.6 vs GPT-Image-2: All Quality Tiers

> **Author**: Xinyu Wei (魏新宇) — Microsoft AI GBB Senior System Engineer

## What This Run Shows About MAI-Image-2.6

All three items rest on the measurements in this repository. `MAI-Image-2.6` is in preview with no SLA.

1. **11 scenarios sit side by side with all three GPT-Image-2 tiers.** This run returned images for 87/88 formal samples, Both rounds plus the original PNGs are kept below so you can compare each scenario yourself. The per-image observations describe differences without ranking them, so this report does not claim MAI image quality beats or matches GPT-Image-2.

2. **One edit request accepts several reference images.** The service states `Only 1 to 5 image files are supported for edit requests.`, and with two images the second image's content verifiably reached the output. The official parameter table types `image` as a single `string` and does not mention this.

3. **`web_grounding=true` adds current web information at generation time.** The model retrieves current information from Bing Search as extra context, which moved the product text facts in two subjects from wrong to matching the official announcement. The cost is a lower first-attempt success rate and clearly higher latency. This is not the same thing as dense visual grounding.

### Vendor Performance Charts And How This Run Relates To Them

The three charts below come from the Performance area of the vendor's MAI-Image-2.6 page (captured 2026-09-08; the page reports itself last modified 2026-09-04), with the data source annotated inside each chart by the vendor. They are vendor claims measured under different conditions from this repository, so they do not validate our measurements; they appear here side by side for reference.

**Text-to-Image Arena top ten**

![Text-to-Image Arena top ten](assets/official-microsoft-ai-20260908/arena-text-to-image-top10.png)

The vendor annotates MAI-Image-2.6 as ranked #2 (1,336), behind GPT Image 2 Medium at #1 (1,381). This is an aggregate score across prompt categories, not a per-scenario quality verdict.

**Text-to-image speed comparison**

![Text-to-image speed comparison](assets/official-microsoft-ai-20260908/speed-vs-gpt-image-2-medium.png)

The vendor footnote states: internal load test, 100 RPM at 1024x1024, median response time with a band to P90. The only baseline is GPT-Image-2-Medium; the low and high tiers are absent.

**Quality versus price frontier for image editing**

![Quality versus price frontier for image editing](assets/official-microsoft-ai-20260908/quality-vs-price-frontier.png)

The horizontal axis is a third-party published API reference price per 1,000 images and the vertical axis is image-edit Arena Elo. The vendor marks MAI-Image-2.6 (Elo 1324, $38.90) and MAI-Image-2.6-Flash (Elo 1311, $19.50) as sitting on the Pareto frontier, with GPT Image 2 high at Elo 1318 and $211. This measures image editing, a different task from the text-to-image leaderboard above. Prices are third-party reference figures, not a Microsoft quote and not any customer's contracted price.

The same statistic measured in this run (client-side P50 of successful requests): MAI-Image-2.6 38.03 s; GPT-Image-2 low 31.19 s, medium 64.64 s, high 171.26 s. The vendor chart shows MAI 1.31x faster than GPT-Image-2-Medium; this run gives 1.70x: **the direction agrees, the multiple does not**.

Neither validates the other: the vendor measured a 100 RPM load test while this run used two requests per minute at concurrency 1. Here MAI ran in Sweden Central and GPT in East US 2 from the same workstation, so region and transport are part of any latency gap and cannot be separated from this run's data. Twenty-two samples per configuration is a descriptive sample, not a capacity or tail-latency result. This repository never called `MAI-Image-2.6-Flash` and did not reproduce the Arena or Artificial Analysis Elo scores. Two facts absent from the vendor charts: this run's GPT-Image-2 low P50 is 31.19 s, faster than MAI, and MAI is 4.50x faster than GPT-Image-2 high.

[Chart provenance and per-item readings](assets/official-microsoft-ai-20260908/provenance.json) | [Vendor page](https://microsoft.ai/models/mai-image-2-6/)

## Current Run: Both Models and All Quality Tiers

[中文](README-CN.md) | [Side-by-side images](#side-by-side-image-comparison) | [Measurements](data/paired-all-quality-20260907/5way_v2_results.json) | [Metrics](data/paired-all-quality-20260907/summary.json) | [Attempts](data/paired-all-quality-20260907/attempts.jsonl)

**This run returned images for 87/88 formal samples; 1 returned no image. The 4 warmups are excluded from the formal denominator.** Requests were interleaved on the same client with identical prompts, dimensions and repetitions. Deployment regions differ, so end-to-end latency differences cannot be attributed solely to the models. Quality observations are unblinded, not an official benchmark score, human-preference win rate or production reliability claim.

### Test Contract

| Configuration | Model version | Quality field | Dimensions | Resource region | Formal samples |
| --- | --- | --- | --- | --- | --- |
| MAI-Image-2.6 | 2026-07-31 | omitted | 1024x1024 | swedencentral | 22 |
| GPT-Image-2 low | 2026-04-21 | low | 1024x1024 | eastus2 | 22 |
| GPT-Image-2 medium | 2026-04-21 | medium | 1024x1024 | eastus2 | 22 |
| GPT-Image-2 high | 2026-04-21 | high | 1024x1024 | eastus2 | 22 |

The original eleven-prompt CSV is unchanged. Each configuration receives one `blue circle` warmup. Each prompt runs MAI, GPT low, medium, high in round 1, with reversed configuration order in round 2. Concurrency is 1, with 5 seconds after each logical call and at most 3 attempts under the original retry backoff. Each GlobalStandard deployment is configured for 2 requests/minute; GPT tiers share one deployment and limit. Request timeouts are 180 seconds for MAI and 300 for GPT.

Client: Windows-11-10.0.26200-SP0, ARM64, Python 3.13.15, requests 2.34.2.

Formal interval (UTC): `2026-09-07T12:32:56.332837+00:00` to `2026-09-07T16:24:46.795573+00:00`. Formal window including waits: **13,910.46 s**. Observed mixed-workload completion rate: **0.38 images/min** (not per-model or maximum throughput).

### Architecture and Measurement Boundary

```mermaid
flowchart LR
    prompts["Original 11 prompts"] --> runner["Local Windows Python runner"]
    runner --> mai["MAI-Image-2.6 / Sweden Central"]
    runner --> gpt["GPT-Image-2 / East US 2 / low, medium, high"]
    mai --> evidence["PNG, usage, request IDs, timestamps, failures"]
    gpt --> evidence
    evidence --> summary["Offline validation and report"]
```

Original explanatory diagram of this project's client/service calls, not model internals. [MAI API](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai-image) | [GPT image API](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/dall-e).

### Performance and Reliability

| Metric | MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- | --- |
| Successful / planned samples | 22 / 22 | 22 / 22 | 22 / 22 | 21 / 22 |
| First-attempt successes / planned | 20 / 22 | 20 / 22 | 20 / 22 | 20 / 22 |
| HTTP attempts / 429 responses | 24 / 0 | 24 / 0 | 24 / 0 | 25 / 0 |
| Unsuccessful HTTP attempts | 2 | 2 | 2 | 4 |
| Total unsuccessful attempt duration (s) | 192.56 | 329.49 | 5,291.35 | 604.30 |
| Mean request latency (s) | 45.33 | 38.69 | 65.09 | 175.17 |
| P50 / descriptive P95 (s) | 38.03 / 79.77 | 31.19 / 81.41 | 64.64 / 74.82 | 171.26 / 215.09 |
| Sample standard deviation (s) | 18.56 | 19.69 | 6.01 | 23.51 |
| Minimum / maximum request latency (s) | 32.19 / 106.81 | 23.61 / 99.08 | 56.04 / 78.13 | 139.24 / 241.38 |
| Round 1 / round 2 mean (s) | 47.57 / 43.09 | 43.30 / 34.09 | 67.27 / 62.90 | 171.91 / 178.14 |
| Mean logical duration, all samples (s) | 55.06 | 54.65 | 306.58 | 196.12 |
| Mean successful PNG size (KiB) | 1,737 | 1,673 | 1,666 | 1,683 |

Request latency measures `requests.post` through receipt of the complete HTTP response, before JSON/base64 processing and file writes, for successful image-producing attempts only. Logical duration includes failed attempts, retry waits and response processing across all planned samples. Failures are not averaged as zero-second responses or removed from the success-rate denominator. P95 is descriptive linear interpolation over at most 22 observations per group, not a production tail guarantee.

### Exceptions and Waiting

The longest unsuccessful attempt was `gpt-image-2-medium-r1-p09` at 4,968.72 client-observed seconds. This is elapsed client request time, not server-side GPU inference duration; these logs do not establish the underlying cause. Exceptions remain in logical durations, attempt counts and observed completion rate, and missing-image samples remain in the planned denominator.

| Sample | Attempt | HTTP / exception | Client duration (s) | Started (UTC) | Finished (UTC) |
| --- | --- | --- | --- | --- | --- |
| gpt-image-2-high-r1-p01 | 1 | ReadTimeout | 301.99 | 2026-09-07T12:35:59.924543+00:00 | 2026-09-07T12:41:11.917183+00:00 |
| gpt-image-2-high-r1-p01 | 2 | ConnectionError | 0.01 | 2026-09-07T12:41:11.921034+00:00 | 2026-09-07T12:41:21.934816+00:00 |
| gpt-image-2-high-r1-p01 | 3 | ConnectionError | 0.00 | 2026-09-07T12:41:21.937598+00:00 | 2026-09-07T12:41:21.941635+00:00 |
| mai-image-2.6-r1-p02 | 1 | ConnectionError | 0.00 | 2026-09-07T12:41:26.958872+00:00 | 2026-09-07T12:41:36.998889+00:00 |
| gpt-image-2-medium-r1-p09 | 1 | ConnectionError | 4,968.72 | 2026-09-07T13:26:31.695448+00:00 | 2026-09-07T14:49:30.415316+00:00 |
| gpt-image-2-low-r1-p11 | 1 | 400 | 20.50 | 2026-09-07T14:58:49.988889+00:00 | 2026-09-07T14:59:20.487114+00:00 |
| gpt-image-2-high-r2-p08 | 1 | ReadTimeout | 302.29 | 2026-09-07T15:40:22.017096+00:00 | 2026-09-07T15:45:34.310843+00:00 |
| mai-image-2.6-r2-p08 | 1 | ReadTimeout | 192.56 | 2026-09-07T15:52:16.770891+00:00 | 2026-09-07T15:55:39.334382+00:00 |
| gpt-image-2-medium-r2-p09 | 1 | ReadTimeout | 322.63 | 2026-09-07T16:01:37.758367+00:00 | 2026-09-07T16:07:10.387228+00:00 |
| gpt-image-2-low-r2-p09 | 1 | ReadTimeout | 309.00 | 2026-09-07T16:08:16.133855+00:00 | 2026-09-07T16:13:35.129678+00:00 |

### Token Usage

| Configuration | Returned output tokens | Successful / planned samples |
| --- | --- | --- |
| MAI-Image-2.6 | 1024 | 22/22 |
| GPT-Image-2 low | 196 | 22/22 |
| GPT-Image-2 medium | 1756 | 22/22 |
| GPT-Image-2 high | 7024 | 21/22 |

Token counts come from returned usage, not assumptions about the model or tier. Missing values are not replaced with zero. Output-token counts and PNG byte sizes do not independently establish image quality.

### Every Scenario, Both Rounds

Seconds; failed cells remain tied to their original requests and are not replaced by another round.

| Scenario / round | MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- | --- |
| 01 / R1 | 38.82 | 51.44 | 78.13 | Failed |
| 01 / R2 | 33.96 | 26.25 | 63.52 | 182.78 |
| 02 / R1 | 65.12 | 41.67 | 74.93 | 176.78 |
| 02 / R2 | 37.43 | 28.50 | 60.23 | 170.60 |
| 03 / R1 | 32.29 | 82.39 | 68.42 | 170.29 |
| 03 / R2 | 32.19 | 23.61 | 59.58 | 152.75 |
| 04 / R1 | 38.63 | 47.05 | 65.18 | 192.56 |
| 04 / R2 | 34.69 | 23.98 | 59.51 | 171.26 |
| 05 / R1 | 60.09 | 29.09 | 69.86 | 187.57 |
| 05 / R2 | 38.42 | 24.80 | 63.22 | 163.33 |
| 06 / R1 | 80.54 | 62.70 | 71.35 | 190.79 |
| 06 / R2 | 32.25 | 35.88 | 65.19 | 185.09 |
| 07 / R1 | 54.92 | 33.29 | 67.74 | 177.19 |
| 07 / R2 | 37.63 | 35.08 | 66.85 | 170.62 |
| 08 / R1 | 36.49 | 35.03 | 68.73 | 174.50 |
| 08 / R2 | 106.81 | 99.08 | 72.83 | 215.09 |
| 09 / R1 | 49.96 | 37.29 | 61.67 | 169.84 |
| 09 / R2 | 41.92 | 25.10 | 60.62 | 241.38 |
| 10 / R1 | 32.92 | 28.74 | 57.93 | 139.24 |
| 10 / R2 | 42.97 | 25.43 | 64.09 | 153.85 |
| 11 / R1 | 33.49 | 27.58 | 56.04 | 140.32 |
| 11 / R2 | 35.77 | 27.29 | 56.27 | 152.77 |

### Quality Observations

AI-assisted, unblinded inspection only. Each cell describes observed image differences, not a numeric quality score. [Inspection record](data/paired-all-quality-20260907/quality-review.json).

| Scenario | MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- | --- |
| 1 | Both rounds include blue metallic clothing, flowers and foreground blur; R1 has a bright background, R2 is dark, with no visible added text. | Both use tightly framed portraits and metallic flowers in dark scenes; R2 clothing resembles wrinkled silver foil, with little sense of high exposure. | Metallic flowers and blue-silver clothing are clear in both dark-toned images; R2 has a smoothed face and shell-like fabric. | R1 returned no image. R2 shows a backward-looking portrait and silver metallic flowers, with cropped upper hair ornaments and no visible added text. |
| 2 | Both retain the messy bedroom and portal; castles and waterfalls dominate R1's forest, and both add numerous unrequested English slogans. | Both depict stone portals, forest paths and scattered clothing with deep room shadows; R2 adds poster lettering and frame glyphs. | Both show vine-covered stone portals and bedroom clutter; R1 adds glowing frame symbols, R2 includes a deer, and some poster lettering is indistinct. | Both show clear forest depth through the portal; R1 adds green stone-ring symbols, while R2's woody portal ends above floor level. |
| 3 | Both clearly depict the tiny astronaut, lunar ground and eggshell; R1 uses a doll-like face, while R2 has a floating upper shell and small suit markings. | The astronaut waves in R1 and emerges from a speckled shell in R2; lunar ground and visor reflections are clear, without obvious limb anomalies. | Both astronauts grip the broken shell rim against detailed lunar terrain; the suits add NASA or NASA-like badges. | R1 emphasizes a tall rear shell wall, while R2 waves above grounded shell fragments; no prominent text or obvious structural anomalies are visible. |
| 4 | Both include the red dragon, nest, table, window light and steam, but add extensive readable English on books and pages. | The dragon reclines in its nest in both tabletop close-ups, with blurred objects behind; the palette is dark warm brown and page lettering is indistinct. | Both show a sleeping curled dragon, book, twig nest and cup steam; R2 has washed-out window highlights and dense page lettering. | Scales, nests and tabletop objects are clear in both close-ups; R1's curled body hides limbs, R2's cup overlaps the nest rim, and scrolls contain small writing. |
| 5 | Both use white long-eared fluffy subjects, islands and castles matching the fantasy theme; R2 adds an unrequested English slogan at upper right. | R1 shows an antlered pink creature holding a glowing orb, R2 a white horned creature on moss; neither has visible added text. | Both feature large-eyed fluffy subjects on clouds amid small companions and dreamlike decoration, without visible added text. | R1 has another face-like form above the subject, creating hood-versus-second-face ambiguity; R2 clearly shows large ears, flowers and mushrooms, with no text in either. |
| 6 | Both include water, sunbeams, vines, orchids and ruins; R1's underwater textures are busy, and partial submersion is less clear in R2. | Waterside temples, orchids and sunbeams follow the prompt in both rounds; R1 has deep cave-wall shadows, with no added typography visible. | Both clearly depict foreground pillars, carvings and submerged structures, with architecture occupying much of the scene and no visible added typography. | Both clearly depict light shafts, water, vines and right-hand ruins; R1 has washed-out opening highlights, while R2 includes a partly submerged foreground pillar. |
| 7 | Both show silver hair, blue eyes and a holographic workshop; R1 uses an anime style with irregular small lettering, while R2 adds NEXA branding and slogans. | Both show a silver-pixie-haired character touching a hologram with clear skin and jacket textures; both add PROJECT: AURORA, and R2 adds a mug slogan. | Both show a character interacting with mechanical holograms; R1 crops the right panel edge, and both add project names, branding or slogans. | Hair, fabric and metal reflections are distinct in both; panels add project names, R2 adds slogans, and tiny interface lettering remains hard to distinguish. |
| 8 | Both form cosmic landscapes from giant eyes, galaxies and dense curling motifs, adding a meditating figure without visible text. | Both fill the sky with multiple eyes, planets and repeated curls above dense landscapes; R1 has granular fine detail, with no visible text in either. | Both emphasize giant eyes, spheres, spiral galaxies and dense textures; R1 has deep shadows, while R2 centers a glowing geometric sphere. | R1 merges eyes with bridge-like terrain and adds a walker; R2 uses near-symmetric blue-orange eyes and a meditating figure, with no text in either. |
| 9 | Both show silver-gray dragon profiles covered in spirals with carved or porcelain-like surfaces and blurred backgrounds; R2 adds moonlit castles. | Both use blue-gold openwork dragon close-ups with clear eyes and tendrils; R1 crops the upper horn, and some dense ornamental connections are hard to distinguish. | Both blue-gold dragon heads carry differently sized spirals in shallow focus; the skin resembles metallic filigree, with no visible text. | R1 uses a round-eyed blue-purple creature with beaded spiral skin and ambiguous tendril overlaps; R2 has a clear orange eye and multiscale spirals, without visible text. |
| 10 | Both cats bare their teeth and drum with human-like two-stick grips; drums and posters add English text, with R2 cropping the bass drum and lower lettering. | Both cats bare their teeth and raise sticks, with some paw motion blur; shirts and drums add English, and R2 crops the bass drum's lower edge. | Both center the drummer with clear fur and chrome highlights, adding slogans such as I HATE MONDAYS or PAWS OF FURY and some blurred paw/stick edges. | Both clearly depict snarling faces and two-stick poses, with cropped foreground drums and added wording such as HISS OFF or BAD KITTY. |
| 11 | R1's monkey plays a pear-shaped string instrument, R2's plays guitar on stone paving; fur and wood are clear, with unrequested text on a book or tip bowl. | Both subjects play guitar with added performance lettering; R1 looks young-ape-like and R2 crops the headstock. R1's image followed an output-moderation rejection and retry. | Both straw-hatted monkeys play guitar against added performance lettering; R2 has a blurred strumming hand and a cropped right-hand headstock. | R1's monkey plays beside a vintage microphone, R2's sits cross-legged with closed eyes; materials are distinct, with added English signage in both. |

### Measured API Settings

| API item | MAI-Image-2.6 | GPT-Image-2 |
| --- | --- | --- |
| POST | `/mai/v1/images/generations` | `/openai/deployments/{deployment}/images/generations?api-version=2025-04-01-preview` |
| Payload | `model`, `prompt`, `width=1024`, `height=1024` | `prompt`, `n=1`, `size=1024x1024`, `quality=low/medium/high` |
| Auth | `api-key` | `api-key` |
| Output | `data[0].b64_json`, PNG | `data[0].b64_json`, PNG |
| Usage | `usage.num_input_text_tokens`, `usage.num_output_tokens` | `usage.input_tokens_details`, `usage.output_tokens_details` |

## Reproduction and Tests

Supply accessible MAI-Image-2.6 and GPT-Image-2 deployments. Verify their underlying model versions; deployment names alone are not model identity. Clone the repository, fetch this project's Git LFS inputs, and install requests in your Python environment:

```powershell
git clone https://github.com/david-xinyuwei/david-share.git
cd david-share/Multimodal-Models/MAI-Image-2-vs-GPT-Image-Benchmark
git lfs install
git lfs pull --include="Multimodal-Models/MAI-Image-2-vs-GPT-Image-Benchmark/**"
python -m pip install requests==2.34.2
```

Replace the two resource origins and GPT deployment name below. Supply `AZURE_API_KEY` (MAI) and `AZURE_OPENAI_API_KEY` (GPT) in the process through your secret-management mechanism, never source control. Model version, region, SKU and rate-limit metadata must match your verified deployments; the values below describe this measurement, not your resources.

```powershell
$env:MAI_ENDPOINT = 'https://<mai-resource>.services.ai.azure.com'
$env:GPT_ENDPOINT = 'https://<openai-resource>.openai.azure.com'
$env:GPT_DEPLOYMENT = '<gpt-image-2-deployment>'
$env:GPT_API_VERSION = '2025-04-01-preview'
$env:MAI_MODEL_VERSION = '2026-07-31'
$env:GPT_MODEL_VERSION = '2026-04-21'
$env:MAI_DEPLOYMENT_SKU = 'GlobalStandard'
$env:GPT_DEPLOYMENT_SKU = 'GlobalStandard'
$env:MAI_DEPLOYMENT_REGION = 'swedencentral'
$env:GPT_DEPLOYMENT_REGION = 'eastus2'
$env:MAI_RATE_LIMIT_RPM = '2.0'
$env:GPT_RATE_LIMIT_RPM = '2.0'
$env:BENCHMARK_CLIENT_LOCATION = 'Describe your actual client location'
python scripts/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --gpt-model gpt-image-2 --gpt-quality all --dry-run
```

The first model command runs four warmups; the second continues the same output directory through the formal matrix. Both consume Azure service usage. Existing results are not overwritten and recorded samples are not rerun. Resume requires unchanged script, prompts, endpoints and configuration. An interrupted in-flight request may already have reached the service. Save the script and CSV before each new run and keep them unchanged during execution.

```powershell
$run = 'runs/paired-all-quality-new-run'
New-Item -ItemType Directory -Path "$run/source" -ErrorAction Stop
Copy-Item -LiteralPath scripts/benchmark_5way_v2.py -Destination "$run/source/benchmark_5way_v2.py"
Copy-Item -LiteralPath prompts.csv -Destination "$run/source/prompts.csv"
python -u scripts/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --gpt-model gpt-image-2 --gpt-quality all --output $run --warmup-only
python -u scripts/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --gpt-model gpt-image-2 --gpt-quality all --output $run --resume
python scripts/summarize_paired_run.py $run
```

These commands validate saved evidence without model calls. Regressions cover request tiers, failure denominators, original usage, image ownership and report coverage. HTTP mocks exist only in offline tests and do not establish image quality. A new run cannot produce its final summary until every planned sample is recorded.

```powershell
python scripts/summarize_paired_run.py data/paired-all-quality-20260907
python scripts/render_paired_report.py data/paired-all-quality-20260907 --check
python -m unittest discover -s tests -v
```

The web-grounding test needs only the MAI deployment. The first command verifies the existing archive without writing; the second checks parameters without network calls; only the third reruns all three subjects into a new directory, leaving published data unchanged.

```powershell
python scripts/summarize_web_grounding.py data/lenovo-web-grounding-20260908 --require-complete --check
python data/lenovo-web-grounding-20260908/source/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --mai-web-grounding both --prompts-csv data/lenovo-web-grounding-20260908/source/prompts.csv --output runs/web-grounding-reproduction --dry-run
python data/lenovo-web-grounding-20260908/source/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --mai-web-grounding both --prompts-csv data/lenovo-web-grounding-20260908/source/prompts.csv --output runs/web-grounding-reproduction
```

The multi-image test needs only the MAI deployment. The first command verifies the saved evidence and checks whether the PNGs carry an alpha channel; the remaining three call the API to rerun the capability group, the field validation and the count probe into their own output directories.

```powershell
python scripts/summarize_multi_image_edit.py data/mai-multi-image-edit-20260908 --check
python data/mai-multi-image-edit-20260908/source/probe_multi_image_clean.py
python data/mai-multi-image-edit-20260908/source/probe_multi_image_limit.py
python data/mai-multi-image-edit-20260908/source/check_alpha_and_cutout.py
```

Runner: [benchmark_5way_v2.py](scripts/benchmark_5way_v2.py); offline summary: [summarize_paired_run.py](scripts/summarize_paired_run.py); report rendering: [render_paired_report.py](scripts/render_paired_report.py); regressions: [tests](tests).


### Limits

This report compares only MAI-Image-2.6 and GPT-Image-2 at low, medium and high. Scope is eleven text-to-image scenarios at 1024x1024, excluding 2K, editing, multiple reference images, exact-text accuracy, concurrency capacity and other authentication modes. MAI sends no quality parameter and is not labeled as equivalent to GPT high. Every metric uses this four-configuration run only.

Evidence directory: [data/paired-all-quality-20260907](data/paired-all-quality-20260907). Contains original images, measurement records, attempts, response metadata and a redacted public source copy. Non-financial measurement fields and image bytes are unchanged; original execution hashes and published-file hashes are recorded separately in [provenance](data/paired-all-quality-20260907/provenance.json). Prompt SHA-256: `be3d628c66a1e4d535d06bcc84246a04aad11f35a48f3133d451fe86283782ce`.

## Side-by-Side Image Comparison

Every scenario and round compares only MAI-Image-2.6 with GPT-Image-2 low, medium and high. Images come from this four-configuration run; missing images retain their failure record. Click an image for the original 1024x1024 PNG.

### Test 1: Chrome Kimono Metallic Maiden

> **Prompt**: Chrome kimono, a maiden surrounded by metallic flowers, earrings, ornate, dark blue, exquisite realism, high exposure, Canon 5D, cinematic lighting, metallic luster, blurred foreground, depth of field, light

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 1, round 1](data/paired-all-quality-20260907/mai-image-2.6/r1/01_test.png) | ![GPT-Image-2 low, prompt 1, round 1](data/paired-all-quality-20260907/gpt-image-2-low/r1/01_test.png) | ![GPT-Image-2 medium, prompt 1, round 1](data/paired-all-quality-20260907/gpt-image-2-medium/r1/01_test.png) | No image returned |
| 38.82 s<br>1856 KiB | 51.44 s<br>1636 KiB | 78.13 s<br>1504 KiB | 3 attempts; logical duration 322.06 s |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 1, round 2](data/paired-all-quality-20260907/mai-image-2.6/r2/01_test.png) | ![GPT-Image-2 low, prompt 1, round 2](data/paired-all-quality-20260907/gpt-image-2-low/r2/01_test.png) | ![GPT-Image-2 medium, prompt 1, round 2](data/paired-all-quality-20260907/gpt-image-2-medium/r2/01_test.png) | ![GPT-Image-2 high, prompt 1, round 2](data/paired-all-quality-20260907/gpt-image-2-high/r2/01_test.png) |
| 33.96 s<br>1699 KiB | 26.25 s<br>1641 KiB | 63.52 s<br>1704 KiB | 182.78 s<br>1531 KiB |

### Test 2: Portal into Mythical Forest

> **Prompt**: a portal into a mythical forest on the wall of my small messy bedroom

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 2, round 1](data/paired-all-quality-20260907/mai-image-2.6/r1/02_test.png) | ![GPT-Image-2 low, prompt 2, round 1](data/paired-all-quality-20260907/gpt-image-2-low/r1/02_test.png) | ![GPT-Image-2 medium, prompt 2, round 1](data/paired-all-quality-20260907/gpt-image-2-medium/r1/02_test.png) | ![GPT-Image-2 high, prompt 2, round 1](data/paired-all-quality-20260907/gpt-image-2-high/r1/02_test.png) |
| 65.12 s<br>1676 KiB | 41.67 s<br>1438 KiB | 74.93 s<br>1477 KiB | 176.78 s<br>1727 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 2, round 2](data/paired-all-quality-20260907/mai-image-2.6/r2/02_test.png) | ![GPT-Image-2 low, prompt 2, round 2](data/paired-all-quality-20260907/gpt-image-2-low/r2/02_test.png) | ![GPT-Image-2 medium, prompt 2, round 2](data/paired-all-quality-20260907/gpt-image-2-medium/r2/02_test.png) | ![GPT-Image-2 high, prompt 2, round 2](data/paired-all-quality-20260907/gpt-image-2-high/r2/02_test.png) |
| 37.43 s<br>1721 KiB | 28.50 s<br>1491 KiB | 60.23 s<br>1489 KiB | 170.60 s<br>1619 KiB |

### Test 3: Tiny Astronaut on Moon

> **Prompt**: a tiny astronaut hatching from an egg on the moon

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 3, round 1](data/paired-all-quality-20260907/mai-image-2.6/r1/03_test.png) | ![GPT-Image-2 low, prompt 3, round 1](data/paired-all-quality-20260907/gpt-image-2-low/r1/03_test.png) | ![GPT-Image-2 medium, prompt 3, round 1](data/paired-all-quality-20260907/gpt-image-2-medium/r1/03_test.png) | ![GPT-Image-2 high, prompt 3, round 1](data/paired-all-quality-20260907/gpt-image-2-high/r1/03_test.png) |
| 32.29 s<br>1387 KiB | 82.39 s<br>1354 KiB | 68.42 s<br>1499 KiB | 170.29 s<br>1543 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 3, round 2](data/paired-all-quality-20260907/mai-image-2.6/r2/03_test.png) | ![GPT-Image-2 low, prompt 3, round 2](data/paired-all-quality-20260907/gpt-image-2-low/r2/03_test.png) | ![GPT-Image-2 medium, prompt 3, round 2](data/paired-all-quality-20260907/gpt-image-2-medium/r2/03_test.png) | ![GPT-Image-2 high, prompt 3, round 2](data/paired-all-quality-20260907/gpt-image-2-high/r2/03_test.png) |
| 32.19 s<br>1539 KiB | 23.61 s<br>1295 KiB | 59.58 s<br>1428 KiB | 152.75 s<br>1457 KiB |

### Test 4: LOTR Tiny Red Dragon

> **Prompt**: Photo realistic scene inspired by LOTR: [A tiny red dragon in a nest on a medieval wizard's table]. Shot with a macro lens (f/2.8, 50mm) and a Canon EOSR5, the soft focus captures [the cozy morning light filtering through a near by window]. The pastel colors and whimsical steam shapes enhance the serene atmosphere, evoking a DnD RPG setting. The image is rendered in 16K and 8K, highlighting [the intricate details and medieval charm].

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 4, round 1](data/paired-all-quality-20260907/mai-image-2.6/r1/04_test.png) | ![GPT-Image-2 low, prompt 4, round 1](data/paired-all-quality-20260907/gpt-image-2-low/r1/04_test.png) | ![GPT-Image-2 medium, prompt 4, round 1](data/paired-all-quality-20260907/gpt-image-2-medium/r1/04_test.png) | ![GPT-Image-2 high, prompt 4, round 1](data/paired-all-quality-20260907/gpt-image-2-high/r1/04_test.png) |
| 38.63 s<br>1589 KiB | 47.05 s<br>1382 KiB | 65.18 s<br>1457 KiB | 192.56 s<br>1443 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 4, round 2](data/paired-all-quality-20260907/mai-image-2.6/r2/04_test.png) | ![GPT-Image-2 low, prompt 4, round 2](data/paired-all-quality-20260907/gpt-image-2-low/r2/04_test.png) | ![GPT-Image-2 medium, prompt 4, round 2](data/paired-all-quality-20260907/gpt-image-2-medium/r2/04_test.png) | ![GPT-Image-2 high, prompt 4, round 2](data/paired-all-quality-20260907/gpt-image-2-high/r2/04_test.png) |
| 34.69 s<br>1585 KiB | 23.98 s<br>1366 KiB | 59.51 s<br>1485 KiB | 171.26 s<br>1402 KiB |

### Test 5: Fluffy Fantasy Creature

> **Prompt**: Cute and adorable fluffy cute creature fantasy, dreamlike, surrealism, super cute, trending on artstation

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 5, round 1](data/paired-all-quality-20260907/mai-image-2.6/r1/05_test.png) | ![GPT-Image-2 low, prompt 5, round 1](data/paired-all-quality-20260907/gpt-image-2-low/r1/05_test.png) | ![GPT-Image-2 medium, prompt 5, round 1](data/paired-all-quality-20260907/gpt-image-2-medium/r1/05_test.png) | ![GPT-Image-2 high, prompt 5, round 1](data/paired-all-quality-20260907/gpt-image-2-high/r1/05_test.png) |
| 60.09 s<br>1435 KiB | 29.09 s<br>1673 KiB | 69.86 s<br>1450 KiB | 187.57 s<br>1526 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 5, round 2](data/paired-all-quality-20260907/mai-image-2.6/r2/05_test.png) | ![GPT-Image-2 low, prompt 5, round 2](data/paired-all-quality-20260907/gpt-image-2-low/r2/05_test.png) | ![GPT-Image-2 medium, prompt 5, round 2](data/paired-all-quality-20260907/gpt-image-2-medium/r2/05_test.png) | ![GPT-Image-2 high, prompt 5, round 2](data/paired-all-quality-20260907/gpt-image-2-high/r2/05_test.png) |
| 38.42 s<br>1417 KiB | 24.80 s<br>1622 KiB | 63.22 s<br>1437 KiB | 163.33 s<br>1586 KiB |

### Test 6: Hidden Jungle Cenote

> **Prompt**: A hidden cenote in the heart of a lush jungle beckons with crystalline turquoise waters. Vibrant emerald vines cascade down weathered limestone walls, their tendrils barely kissing the water's surface. Shafts of golden sunlight pierce through a natural skylight above, creating a mystical interplay of light and shadow on the cavern walls. Iridescent butterflies flit between exotic orchids clinging to rocky outcrops. A partially submerged Mayan ruin, its intricate carvings softened by time, stand

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 6, round 1](data/paired-all-quality-20260907/mai-image-2.6/r1/06_test.png) | ![GPT-Image-2 low, prompt 6, round 1](data/paired-all-quality-20260907/gpt-image-2-low/r1/06_test.png) | ![GPT-Image-2 medium, prompt 6, round 1](data/paired-all-quality-20260907/gpt-image-2-medium/r1/06_test.png) | ![GPT-Image-2 high, prompt 6, round 1](data/paired-all-quality-20260907/gpt-image-2-high/r1/06_test.png) |
| 80.54 s<br>2149 KiB | 62.70 s<br>2088 KiB | 71.35 s<br>2110 KiB | 190.79 s<br>2024 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 6, round 2](data/paired-all-quality-20260907/mai-image-2.6/r2/06_test.png) | ![GPT-Image-2 low, prompt 6, round 2](data/paired-all-quality-20260907/gpt-image-2-low/r2/06_test.png) | ![GPT-Image-2 medium, prompt 6, round 2](data/paired-all-quality-20260907/gpt-image-2-medium/r2/06_test.png) | ![GPT-Image-2 high, prompt 6, round 2](data/paired-all-quality-20260907/gpt-image-2-high/r2/06_test.png) |
| 32.25 s<br>2131 KiB | 35.88 s<br>2042 KiB | 65.19 s<br>2151 KiB | 185.09 s<br>1979 KiB |

### Test 7: Tech-Savvy Girl with Holographic UI

> **Prompt**: A charming, tech-savvy [girl with short, silver pixie-cut] hair and vibrant [blue] eyes, wearing a casual yet futuristic outfit. She's focused on a holographic interface while working in a sleek, high-tech workshop.

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 7, round 1](data/paired-all-quality-20260907/mai-image-2.6/r1/07_test.png) | ![GPT-Image-2 low, prompt 7, round 1](data/paired-all-quality-20260907/gpt-image-2-low/r1/07_test.png) | ![GPT-Image-2 medium, prompt 7, round 1](data/paired-all-quality-20260907/gpt-image-2-medium/r1/07_test.png) | ![GPT-Image-2 high, prompt 7, round 1](data/paired-all-quality-20260907/gpt-image-2-high/r1/07_test.png) |
| 54.92 s<br>1556 KiB | 33.29 s<br>1543 KiB | 67.74 s<br>1520 KiB | 177.19 s<br>1538 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 7, round 2](data/paired-all-quality-20260907/mai-image-2.6/r2/07_test.png) | ![GPT-Image-2 low, prompt 7, round 2](data/paired-all-quality-20260907/gpt-image-2-low/r2/07_test.png) | ![GPT-Image-2 medium, prompt 7, round 2](data/paired-all-quality-20260907/gpt-image-2-medium/r2/07_test.png) | ![GPT-Image-2 high, prompt 7, round 2](data/paired-all-quality-20260907/gpt-image-2-high/r2/07_test.png) |
| 37.63 s<br>1495 KiB | 35.08 s<br>1548 KiB | 66.85 s<br>1529 KiB | 170.62 s<br>1648 KiB |

### Test 8: Universe Fractal Worlds

> **Prompt**: Universe, LSD, Fractal Worlds, Giant Eyes

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 8, round 1](data/paired-all-quality-20260907/mai-image-2.6/r1/08_test.png) | ![GPT-Image-2 low, prompt 8, round 1](data/paired-all-quality-20260907/gpt-image-2-low/r1/08_test.png) | ![GPT-Image-2 medium, prompt 8, round 1](data/paired-all-quality-20260907/gpt-image-2-medium/r1/08_test.png) | ![GPT-Image-2 high, prompt 8, round 1](data/paired-all-quality-20260907/gpt-image-2-high/r1/08_test.png) |
| 36.49 s<br>2305 KiB | 35.03 s<br>2175 KiB | 68.73 s<br>2270 KiB | 174.50 s<br>2250 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 8, round 2](data/paired-all-quality-20260907/mai-image-2.6/r2/08_test.png) | ![GPT-Image-2 low, prompt 8, round 2](data/paired-all-quality-20260907/gpt-image-2-low/r2/08_test.png) | ![GPT-Image-2 medium, prompt 8, round 2](data/paired-all-quality-20260907/gpt-image-2-medium/r2/08_test.png) | ![GPT-Image-2 high, prompt 8, round 2](data/paired-all-quality-20260907/gpt-image-2-high/r2/08_test.png) |
| 106.81 s<br>2356 KiB | 99.08 s<br>2441 KiB | 72.83 s<br>2337 KiB | 215.09 s<br>2270 KiB |

### Test 9: Fractal Mythical Creature

> **Prompt**: close up dof render of a mythical creature made of detailed spiraling fractals and tendrils, detailed recursive skin texture

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 9, round 1](data/paired-all-quality-20260907/mai-image-2.6/r1/09_test.png) | ![GPT-Image-2 low, prompt 9, round 1](data/paired-all-quality-20260907/gpt-image-2-low/r1/09_test.png) | ![GPT-Image-2 medium, prompt 9, round 1](data/paired-all-quality-20260907/gpt-image-2-medium/r1/09_test.png) | ![GPT-Image-2 high, prompt 9, round 1](data/paired-all-quality-20260907/gpt-image-2-high/r1/09_test.png) |
| 49.96 s<br>1767 KiB | 37.29 s<br>1871 KiB | 61.67 s<br>1731 KiB | 169.84 s<br>1686 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 9, round 2](data/paired-all-quality-20260907/mai-image-2.6/r2/09_test.png) | ![GPT-Image-2 low, prompt 9, round 2](data/paired-all-quality-20260907/gpt-image-2-low/r2/09_test.png) | ![GPT-Image-2 medium, prompt 9, round 2](data/paired-all-quality-20260907/gpt-image-2-medium/r2/09_test.png) | ![GPT-Image-2 high, prompt 9, round 2](data/paired-all-quality-20260907/gpt-image-2-high/r2/09_test.png) |
| 41.92 s<br>1737 KiB | 25.10 s<br>1840 KiB | 60.62 s<br>1747 KiB | 241.38 s<br>1666 KiB |

### Test 10: Angry Cat Playing Drums

> **Prompt**: an angry cat playing drums

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 10, round 1](data/paired-all-quality-20260907/mai-image-2.6/r1/10_test.png) | ![GPT-Image-2 low, prompt 10, round 1](data/paired-all-quality-20260907/gpt-image-2-low/r1/10_test.png) | ![GPT-Image-2 medium, prompt 10, round 1](data/paired-all-quality-20260907/gpt-image-2-medium/r1/10_test.png) | ![GPT-Image-2 high, prompt 10, round 1](data/paired-all-quality-20260907/gpt-image-2-high/r1/10_test.png) |
| 32.92 s<br>1606 KiB | 28.74 s<br>1460 KiB | 57.93 s<br>1603 KiB | 139.24 s<br>1511 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 10, round 2](data/paired-all-quality-20260907/mai-image-2.6/r2/10_test.png) | ![GPT-Image-2 low, prompt 10, round 2](data/paired-all-quality-20260907/gpt-image-2-low/r2/10_test.png) | ![GPT-Image-2 medium, prompt 10, round 2](data/paired-all-quality-20260907/gpt-image-2-medium/r2/10_test.png) | ![GPT-Image-2 high, prompt 10, round 2](data/paired-all-quality-20260907/gpt-image-2-high/r2/10_test.png) |
| 42.97 s<br>1652 KiB | 25.43 s<br>1611 KiB | 64.09 s<br>1581 KiB | 153.85 s<br>1592 KiB |

### Test 11: Monkey Playing Music

> **Prompt**: A monkey playing music

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 11, round 1](data/paired-all-quality-20260907/mai-image-2.6/r1/11_test.png) | ![GPT-Image-2 low, prompt 11, round 1](data/paired-all-quality-20260907/gpt-image-2-low/r1/11_test.png) | ![GPT-Image-2 medium, prompt 11, round 1](data/paired-all-quality-20260907/gpt-image-2-medium/r1/11_test.png) | ![GPT-Image-2 high, prompt 11, round 1](data/paired-all-quality-20260907/gpt-image-2-high/r1/11_test.png) |
| 33.49 s<br>1833 KiB | 27.58 s<br>1671 KiB | 56.04 s<br>1612 KiB | 140.32 s<br>1632 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2 low | GPT-Image-2 medium | GPT-Image-2 high |
| --- | --- | --- | --- |
| ![MAI-Image-2.6, prompt 11, round 2](data/paired-all-quality-20260907/mai-image-2.6/r2/11_test.png) | ![GPT-Image-2 low, prompt 11, round 2](data/paired-all-quality-20260907/gpt-image-2-low/r2/11_test.png) | ![GPT-Image-2 medium, prompt 11, round 2](data/paired-all-quality-20260907/gpt-image-2-medium/r2/11_test.png) | ![GPT-Image-2 high, prompt 11, round 2](data/paired-all-quality-20260907/gpt-image-2-high/r2/11_test.png) |
| 35.77 s<br>1725 KiB | 27.29 s<br>1615 KiB | 56.27 s<br>1541 KiB | 152.77 s<br>1715 KiB |

## Web Grounding Test

This section tests web grounding as a general image-generation capability: identical prompts are sent to MAI-Image-2.6 with `web_grounding=false/true` to compare text factual accuracy and latency. Public product announcements supply the test subjects; this is not a customer project or adoption case.

**What we asked the model**

Both subjects ask the model to put real product information into a poster. Subject 1 asks for every officially announced colour name and the screen-size options; subject 2 asks for the product name, screen size, computing platform, the officially named convertible modes and which surfaces accept pen input. The prompts only instruct the model to follow the official announcement; no correct answer is supplied in the prompt itself.

The exact prompt sent for subject 1 (New-product colours and sizes):

> Create a polished square English-language launch poster for the Lenovo IdeaPad Vibe series announced at Lenovo Innovation World in September 2026. Present the official launch colour lineup as clearly separated colour swatches, each with its exact official colour name, and include the official screen-size options. Use a restrained stylized laptop silhouette and prioritize readable product information. Base factual claims on Lenovo's announcement; do not substitute colours or models from older IdeaPad products. Do not include prices, purchase links or unsupported specifications.

The exact prompt sent for subject 2 (Product specifications and usage modes):

> Create a polished square English-language creator poster for the Lenovo Yoga 9n 2-in-1 announced at Lenovo Innovation World in September 2026. Include its exact product name, screen size and computing platform. Illustrate and label its officially named convertible usage modes, and describe which surfaces support pen input. Use a simple stylized device illustration with clear readable labels and generous spacing. Base the facts on Lenovo's announcement rather than specifications from older Yoga 9i products. Preserve qualifiers for optional features. Do not include prices or invented specifications.

**Controlled variable**

The only thing that changes is the `web_grounding` switch. Prompt, dimensions, model version, deployment and round count are identical.

The complete supplement contains 12 formal samples and 2 excluded warmups. Two subjects were selected after observing improved text facts; all off/on results from both rounds are shown, 8 original images and 4 samples per setting. The table covers only these examples, not an overall improvement rate. No GPT comparison was performed in this section, so it does not establish superiority over GPT-Image-2.

**Text-fact findings**

| Test subject | Grounding off | Grounding on |
| --- | --- | --- |
| New-product colours and sizes | Both rounds used unofficial colour names and incorrect screen options | Both matched all seven official colour names and the 14/15-inch options |
| Product specifications and usage modes | Screen size and computing platform were wrong; Canvas mode was missing | Both matched 16 inches, NVIDIA RTX Spark, five mode names and the pen-input surfaces |

**Latency and request outcomes**

| Metric | Grounding off | Grounding on |
| --- | --- | --- |
| Images returned / displayed samples | 4/4 | 4/4 |
| First-attempt successes / displayed samples | 4/4 | 1/4 |
| HTTP attempts | 4 | 7 |
| HTTP 408 responses | 0 | 3 |
| Mean successful request | 35.75 s | 68.91 s |
| Successful request P50 | 34.57 s | 67.23 s |
| Mean logical call including retries | 35.77 s | 168.21 s |

Both settings used 1024x1024, `auto_aspect_ratio=false`, model version 2026-07-31 and the same Sweden Central GlobalStandard deployment. Round 2 reversed request order. Only the grounding switch differed; reference answers were not included in prompts. Successful request time excludes JSON/base64 processing; logical call time includes failures, backoff and response processing, but excludes the outer five-second interval and final PNG write. All HTTP 408 responses and retries are retained. The internal timeout stage was not returned, so the additional time cannot all be attributed to search.

Improved text facts do not establish better aesthetics or product fidelity. In subject 2, round 2, the grounding-on `Tablet Mode` illustration still has an upright screen. Inspection was AI-assisted and unblinded, with few repetitions, not human preference voting or a statistically significant result. Responses included no search queries, source URLs or retrieval traces; usage changes do not identify retrieval sources.

#### New-product colours and sizes / Round 1

| `web_grounding=false` | `web_grounding=true` |
| --- | --- |
| ![Web grounding off, subject 1, round 1](data/lenovo-web-grounding-20260908/mai-image-2.6-web-off/r1/01_test.png) | ![Web grounding on, subject 1, round 1](data/lenovo-web-grounding-20260908/mai-image-2.6-web-on/r1/01_test.png) |

#### New-product colours and sizes / Round 2

| `web_grounding=false` | `web_grounding=true` |
| --- | --- |
| ![Web grounding off, subject 1, round 2](data/lenovo-web-grounding-20260908/mai-image-2.6-web-off/r2/01_test.png) | ![Web grounding on, subject 1, round 2](data/lenovo-web-grounding-20260908/mai-image-2.6-web-on/r2/01_test.png) |

#### Product specifications and usage modes / Round 1

| `web_grounding=false` | `web_grounding=true` |
| --- | --- |
| ![Web grounding off, subject 2, round 1](data/lenovo-web-grounding-20260908/mai-image-2.6-web-off/r1/02_test.png) | ![Web grounding on, subject 2, round 1](data/lenovo-web-grounding-20260908/mai-image-2.6-web-on/r1/02_test.png) |

#### Product specifications and usage modes / Round 2

| `web_grounding=false` | `web_grounding=true` |
| --- | --- |
| ![Web grounding off, subject 2, round 2](data/lenovo-web-grounding-20260908/mai-image-2.6-web-off/r2/02_test.png) | ![Web grounding on, subject 2, round 2](data/lenovo-web-grounding-20260908/mai-image-2.6-web-on/r2/02_test.png) |

Full original evidence is retained without rewriting previous runs. This section is measured separately from the two-model test above; its commands appear in the reproduction section below.

[Raw results](data/lenovo-web-grounding-20260908/5way_v2_results.json) | [All attempts](data/lenovo-web-grounding-20260908/attempts.jsonl) | [Visual observations](data/lenovo-web-grounding-20260908/visual-review.json) | [Full 12-sample statistics](data/lenovo-web-grounding-20260908/web-grounding-summary.json) | [Provenance and hashes](data/lenovo-web-grounding-20260908/provenance.json)

Result SHA-256: `669617dd5d59d0748a0fc398d98ec4c59cb4b26cc9655138edf9b6c9622f3c1b`.

Official references: [IdeaPad Vibe](https://news.lenovo.com/pressroom/press-releases/colorful-ideapad-vibe-series-all-in-one-ai-pcs/) | [Yoga](https://news.lenovo.com/pressroom/press-releases/yoga-portfolio-new-ai-pcs-and-tablets/) | [MAI API](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai-image#request-parameters)

## Multi-Image Input Edit Test

**What this section determines**

The question is how many reference images this edit endpoint accepts in one call, and whether an extra image is actually used. The official documentation does not say, so the answer below comes from real calls.

This section measures how many reference images `/mai/v1/images/edits` accepts. The official parameter table types `image` as a `string` described as "the image", with no multi-image statement and no count limit, so the counts and field rules below come from the service's own validation messages. They are measured behaviour, not an official support commitment.

**The two input images**

Both images are model outputs from the web-grounding section above, reused here as input material. The left one is a dark colour-lineup infographic containing four colour dots, 14/16-inch labels and a purple laptop. The right one is a light specification infographic containing a brown laptop, on-screen text and a row of four usage modes, one of which holds a pen. They are generated content, not official assets, and their colour names and specification text do not represent official product information.

| Input image 1, colour-lineup infographic | Input image 2, specification infographic |
| --- | --- |
| ![Input image 1](data/lenovo-web-grounding-20260908/mai-image-2.6-web-off/r1/01_test.png) | ![Input image 2](data/lenovo-web-grounding-20260908/mai-image-2.6-web-off/r1/02_test.png) |

**Group 1: what each usage returns**

The capability group gives each input count a prompt it can satisfy: a singular instruction for one image and a plural instruction for two. The prompts differ, so this group shows what each usage returns and cannot attribute a difference to the second image.

The prompt sent with one image:

> Show the laptop from the reference image alone on a plain white studio background as a clean product photograph.

The prompt sent with two images:

> Show the laptops from both reference images together on one plain white studio background as a clean product photograph.

| Input | Request latency | Output size |
| --- | --- | --- |
| One image, `image` x 1 | 31.619 s | 920,112 bytes |
| Two images, `image` x 2 | 38.455 s | 932,695 bytes |

| One-image output | Two-image output |
| --- | --- |
| ![Single-image edit output](data/mai-multi-image-edit-20260908/01_single_image_matched_prompt.png) | ![Two-image edit output](data/mai-multi-image-edit-20260908/02_two_images_matched_prompt.png) |

**Group 2: was the second image actually used**

The attribution group holds one prompt constant and changes only the images, keeping both single-image arms so the comparison is symmetric. That prompt is under-determined for a single input, so this group measures attribution only and is not evidence of single-image edit quality.

All three calls in this group use the same prompt:

> Place every laptop that appears in the reference images on one plain white studio background as a clean product photograph.

| Input combination | Images | Request latency | Observed result |
| --- | --- | --- | --- |
| Image 1 only | 1 | 31.783 s | Purple chassis only, no elements from image 2 |
| Image 2 only | 1 | 33.511 s | Only the image-2 device, no purple chassis |
| Both images | 2 | 41.639 s | Devices and mode row from both images appear together |

| Image 1 only | Image 2 only |
| --- | --- |
| ![Attribution, image 1 only](data/mai-multi-image-edit-20260908/attribution_01_single_image.png) | ![Attribution, image 2 only](data/mai-multi-image-edit-20260908/03_fixed_prompt_image_two_only.png) |

| Both input images |
| --- |
| ![Attribution, both images](data/mai-multi-image-edit-20260908/attribution_02_two_image_fields.png) |

Each image's unique elements appear only when that image is present, so the second image was read and influenced the result rather than being silently ignored.

**Group 3: how many images, and how the field must be named**

Terminology: `HTTP 429` means the quota was exhausted (two requests per minute on this deployment), so the request was never processed. That differs from the endpoint refusing an image count, which returns `HTTP 400`.

| Multipart field | Status | Service response |
| --- | --- | --- |
| `image` x 1 | 200 | Returned an image |
| `image` x 2 | 200 | Returned an image; the second image took effect |
| `image` x 3, 5 | 429 | Quota limit (2 RPM on this deployment); neither a capability refutation nor proof of support |
| `image` x 9 | 400 | `Only 1 to 5 image files are supported for edit requests.` |
| No image field | 400 | `Only 1 to 5 image files are supported for edit requests.` |
| `image[]`, `images`, `image1`+`image2`, `image_a`+`image_b`, `reference` | 400 | `File must be attached in a form field with a name starting with 'image'.` |

The service says the field name must start with `image`, yet `image1`, `image_a`, `image[]` and `images` were all rejected, so only repeated fields named `image` are accepted. The 1–5 range comes from the service message; no successful sample was obtained for 3 or 5 images because of the quota.

**Is this a cutout**

All three outputs are PNG colour type 2 with no alpha channel and opaque near-white corners. The white background is drawn by the model, not transparency, so compositing still requires a separate cutout. The API exposes no `background` or `output_format` parameter to request transparency and no `mask` parameter to select which part of each input is used; the output is a regenerated image, not a composite.

Each combination was called once with no repeatability check. `MAI-Image-2.6` is in preview with no SLA and its behaviour may change. Latency is client-side `requests.post` round-trip time, not server-side inference duration.

[Capability and third attribution arm](data/mai-multi-image-edit-20260908/clean-results.json) | [Field shapes](data/mai-multi-image-edit-20260908/field-shape-results.json) | [Validation and limit](data/mai-multi-image-edit-20260908/limit-probe-results.json) | [Probe scripts](data/mai-multi-image-edit-20260908/source)
