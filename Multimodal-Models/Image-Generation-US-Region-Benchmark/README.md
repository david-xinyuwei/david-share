# MAI-Image-2.6 vs GPT-Image-2 vs GPT-Image-2.5 — US-region deployments, one client, one session

9 configurations · 17 prompts · 2 rounds · 306 images · resources: East US (MAI) / East US 2 (GPT) · client: Xinyu SURFACE-2 laptop; resources East US (MAI) / East US 2 (GPT); Entra bearer auth

Every configuration received the same prompts verbatim, from the same client, in one session, interleaved so no model got a warmer or quieter minute than another. Timings are wall-clock seconds from HTTP request to full response body — what a user waits, not model-only inference.

## Results

Seconds per image, wall-clock from HTTP request to full response. P50 is the median; P90 / P95 are the values below which 90% / 95% of this run's requests finished (linear interpolation; descriptive on ≈34 samples per configuration, not a tail-latency guarantee).

| Configuration | Images | P50 s | P90 s | P95 s | Mean s | Min–max s | Output tokens / image | USD / image (P50) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| MAI-Image-2.6 | 34 | 30.02 | 37.57 | 44.30 | 32.48 | 26.33–59.83 | 1,024 | 0.0391 |
| GPT-Image-2 · low | 34 | 22.98 | 27.37 | 30.71 | 23.57 | 17.72–32.63 | 196 | 0.0062 |
| GPT-Image-2 · high | 34 | 150.64 | 170.77 | 176.40 | 145.21 | 109.14–184.80 | 7,024 | 0.2110 |
| GPT-Image-2.5 Flare · auto | 34 | 23.87 | 33.89 | 35.60 | 25.09 | 15.95–39.43 | 196–1,756 | 0.0133 |
| GPT-Image-2.5 Flare · low | 34 | 20.55 | 24.24 | 27.68 | 21.03 | 15.95–34.63 | 196 | 0.0062 |
| GPT-Image-2.5 Flare · high | 34 | 35.26 | 42.04 | 44.08 | 35.79 | 27.80–48.28 | 1,756 | 0.0529 |
| GPT-Image-2.5 Sunburst · auto | 34 | 37.21 | 54.25 | 58.62 | 39.06 | 25.05–63.88 | 196–1,756 | 0.0133 |
| GPT-Image-2.5 Sunburst · low | 34 | 30.61 | 38.95 | 44.55 | 32.20 | 23.46–46.07 | 196 | 0.0062 |
| GPT-Image-2.5 Sunburst · high | 34 | 69.47 | 80.67 | 82.55 | 70.92 | 59.39–88.55 | 1,756 | 0.0529 |

`auto` is not a fixed tier: the service chooses a tier per request and echoes the one it used. Tiers echoed in this run — GPT-Image-2.5 Flare · auto: medium ×18, low ×14, high ×2; GPT-Image-2.5 Sunburst · auto: medium ×18, low ×14, high ×2. The token column for `auto` therefore shows the observed range, and its cost is per-image actuals, not a tier price.

## Cost

Cost per image = input text tokens × input price + output image tokens × output price, using the exact token counts each API returned for each request. No rounding to a tier price: `auto` and any variance are costed as billed.

| Configuration | Images | Output tokens P50 / P90 | USD / image P50 | USD / image P90 | USD / image P95 | USD / image mean | USD / 1,000 images (mean) | vs MAI-Image-2.6 | Run spend (USD) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| MAI-Image-2.6 | 34 | 1,024 / 1,024 | 0.0391 | 0.0396 | 0.0396 | 0.0392 | 39.23 | 1.00× | 1.33 |
| GPT-Image-2 · low | 34 | 196 / 196 | 0.0062 | 0.0066 | 0.0066 | 0.0062 | 6.23 | 0.16× | 0.21 |
| GPT-Image-2 · high | 34 | 7,024 / 7,024 | 0.2110 | 0.2114 | 0.2115 | 0.2111 | 211.07 | 5.38× | 7.18 |
| GPT-Image-2.5 Flare · auto | 34 | 439 / 781 | 0.0133 | 0.0242 | 0.0343 | 0.0156 | 15.56 | 0.40× | 0.53 |
| GPT-Image-2.5 Flare · low | 34 | 196 / 196 | 0.0062 | 0.0066 | 0.0066 | 0.0062 | 6.23 | 0.16× | 0.21 |
| GPT-Image-2.5 Flare · high | 34 | 1,756 / 1,756 | 0.0529 | 0.0534 | 0.0534 | 0.0530 | 53.03 | 1.35× | 1.80 |
| GPT-Image-2.5 Sunburst · auto | 34 | 439 / 781 | 0.0133 | 0.0242 | 0.0343 | 0.0159 | 15.86 | 0.40× | 0.54 |
| GPT-Image-2.5 Sunburst · low | 34 | 196 / 196 | 0.0062 | 0.0066 | 0.0066 | 0.0062 | 6.23 | 0.16× | 0.21 |
| GPT-Image-2.5 Sunburst · high | 34 | 1,756 / 1,756 | 0.0529 | 0.0534 | 0.0534 | 0.0530 | 53.03 | 1.35× | 1.80 |

**Model charges for this run: $13.82** for 306 formal images, plus $0.38 for 9 warm-up images. Excludes the client machine, storage of the archive, and any Azure resource fixed fees (none: GlobalStandard image deployments bill per token only).

**Where each price comes from.** `list` = the public Azure pricing page on the date shown; `invoice` = actual charge on our own Azure subscription (Cost Management, PreTaxCost ÷ billed tokens) because the model was not yet on the public page.

| Model | Input text USD / 1M | Output image USD / 1M | Source | Verified |
|---|---:|---:|---|---|
| MAI-Image-2.6 | 5.00 | 38.00 | invoice | Not on the public Foundry Models pricing page as of 2026-09-26 (page lists MAI-Image-2 $33, MAI-Image-2.5 $47, 2.5 Flash $19.50, 2.5 Pro $106 per 1M output; no 2.6 row). Azure Cost Management actual charges on our account 2026-09-04..09-20 = $38.00 per 1M output tokens. Input text $5 per 1M taken from the MAI-Image-2 / 2.5 list rows (all $5 text input). Evidence: data/billing-20260920 in the same repo |
| gpt-image-2 | 5.00 | 30.00 | list | https://azure.microsoft.com/en-us/pricing/details/azure-openai/ 'GPT-Image Series' row 'GPT-Image-2 Global': Input Text $5, Output Image $30 per 1M tokens — read 2026-09-26 |
| gpt-image-2.5-flare | 5.00 | 30.00 | invoice | Not on the public pricing page as of 2026-09-26 (page lists GPT-Image-2 / 1.5 / 1 / 1-mini only). Azure Cost Management actual charges on the account that ran the Sweden Central tests, 2026-09-04..09-20: PreTaxCost / billed output-image tokens = $30.00 per 1M. Input text assumed equal to GPT-Image-2's $5 (input is <1% of per-image cost). Evidence: david-share Multimodal-Models/MAI-Image-2-vs-GPT-Image-Benchmark data/billing-20260920 |
| gpt-image-2.5-sunburst | 5.00 | 30.00 | invoice | Same basis as gpt-image-2.5-flare: Cost Management actual charges 2026-09-04..09-20 = $30.00 per 1M output-image tokens; not on the public pricing page as of 2026-09-26 |

Prices are Global deployment, pay-as-you-go, USD, before any negotiated discount. Read the ratio column, not the absolute dollars: a tier that returns more output tokens costs proportionally more on every model. For fixed tiers P50 = P90 = P95 = mean because every image bills the same token count; the percentiles only spread for `auto`, where the service picks the tier per request.

## Robustness against earlier runs

Same runner family, same 11 repo prompts (matched by prompt SHA-256; the 6 newer prompts have no earlier counterpart), same 1024×1024 and 2-round interleaving — but Sweden Central resources, a different day and a different client. So the question is not whether the seconds match (they should not), but whether the **billing tokens are identical**, whether the **ordering of configurations** holds, and whether **round 1 and round 2 agree** inside this run.

| Configuration | Tokens identical | P50 s this run / earlier | P90 s this run / earlier | P50 ratio (shared prompts) | Per-prompt ratio P25–P75 | R1 / R2 P50 s | Earlier run |
|---|:---:|---:|---:|---:|---:|---:|---|
| MAI-Image-2.6 | yes | 30.02 / 31.61 | 37.57 / 46.11 | 0.93× | 0.86–1.07 | 29.9 / 30.4 | `mai-vs-gpt25-20260920` (2026-09-20) |
| GPT-Image-2 · low | yes | 22.98 / 31.19 | 27.37 / 61.58 | 0.69× | 0.56–0.81 | 23.0 / 22.2 | `paired-all-quality-20260907` (2026-09-07) |
| GPT-Image-2 · high | yes | 150.64 / 171.26 | 170.77 / 192.56 | 0.89× | 0.82–0.92 | 149.4 / 152.2 | `paired-all-quality-20260907` (2026-09-07) |
| GPT-Image-2.5 Flare · auto | yes | 23.87 / 22.25 | 33.89 / 28.91 | 1.01× | 0.93–1.15 | 23.7 / 24.0 | `gpt25-tiers-20260918` (2026-09-18) |
| GPT-Image-2.5 Flare · low | yes | 20.55 / 21.85 | 24.24 / 25.31 | 0.94× | 0.93–1.04 | 20.6 / 20.3 | `gpt25-paired-20260917` (2026-09-17) |
| GPT-Image-2.5 Flare · high | yes | 35.26 / 32.11 | 42.04 / 35.25 | 1.16× | 1.02–1.21 | 36.5 / 34.6 | `mai-vs-gpt25-20260920` (2026-09-20) |
| GPT-Image-2.5 Sunburst · auto | yes | 37.21 / 33.74 | 54.25 / 48.44 | 0.98× | 0.94–1.00 | 38.1 / 36.3 | `gpt25-tiers-20260918` (2026-09-18) |
| GPT-Image-2.5 Sunburst · low | yes | 30.61 / 32.54 | 38.95 / 37.03 | 1.01× | 0.87–1.03 | 31.1 / 29.8 | `gpt25-paired-20260917` (2026-09-17) |
| GPT-Image-2.5 Sunburst · high | yes | 69.47 / 76.08 | 80.67 / 82.69 | 0.93× | 0.89–1.00 | 72.4 / 65.7 | `gpt25-paired-20260917` (2026-09-17) |

`auto` tier choices, this run vs earlier: GPT-Image-2.5 Flare · auto — now {'low': 14, 'medium': 18, 'high': 2}, earlier {'low': 12, 'medium': 10}; GPT-Image-2.5 Sunburst · auto — now {'low': 14, 'medium': 18, 'high': 2}, earlier {'low': 12, 'medium': 10}. For `auto`, 'tokens identical' means: the same echoed tier billed the same token count in both runs.

Latency ordering (fastest → slowest) identical to the earlier runs: **no**.

- this run: gpt-image-2.5-flare-low < gpt-image-2-low < gpt-image-2.5-flare-auto < mai-image-2.6 < gpt-image-2.5-sunburst-low < gpt-image-2.5-flare-high < gpt-image-2.5-sunburst-auto < gpt-image-2.5-sunburst-high < gpt-image-2-high
- earlier: gpt-image-2.5-flare-low < gpt-image-2.5-flare-auto < gpt-image-2-low < mai-image-2.6 < gpt-image-2.5-flare-high < gpt-image-2.5-sunburst-low < gpt-image-2.5-sunburst-auto < gpt-image-2.5-sunburst-high < gpt-image-2-high

Earlier runs used (each is a published run record in the same repository; SHA-256 of the file as read): `mai-vs-gpt25-20260920` (2026-09-20, swedencentral; `Multimodal-Models/MAI-Image-2-vs-GPT-Image-Benchmark/data/mai-vs-gpt25-20260920/5way_v2_results.json`, SHA-256 `2dedbb00ff09…`); `paired-all-quality-20260907` (2026-09-07, MAI: swedencentral; gpt-image-2: eastus2 (another account); `Multimodal-Models/MAI-Image-2-vs-GPT-Image-Benchmark/data/paired-all-quality-20260907/5way_v2_results.json`, SHA-256 `307031c102b3…`); `gpt25-tiers-20260918` (2026-09-18, swedencentral; `Multimodal-Models/MAI-Image-2-vs-GPT-Image-Benchmark/data/gpt25-tiers-20260918/5way_v2_results.json`, SHA-256 `a7e6464ba07a…`); `gpt25-paired-20260917` (2026-09-17, swedencentral; `Multimodal-Models/MAI-Image-2-vs-GPT-Image-Benchmark/data/gpt25-paired-20260917/5way_v2_results.json`, SHA-256 `e499047d4abd…`).

## Images

Round 1 outputs. Each row is one prompt; each column is one configuration. Under each image: the seconds that request took and what that one image cost — its own returned token counts × the verified price, not a tier average. For `auto`, the tier the service chose for that request is shown too. Click any image for full size.

### R01 · photoreal portrait

> Chrome kimono, a maiden surrounded by metallic flowers, earrings, ornate, dark blue, exquisite realism, high exposure, Canon 5D, cinematic lighting, metallic luster, blurred foreground, depth of field, light

| MAI-Image-2.6 | GPT-Image-2 · low | GPT-Image-2 · high | GPT-Image-2.5 Flare · auto | GPT-Image-2.5 Flare · low | GPT-Image-2.5 Flare · high | GPT-Image-2.5 Sunburst · auto | GPT-Image-2.5 Sunburst · low | GPT-Image-2.5 Sunburst · high |
|---|---|---|---|---|---|---|---|---|
| <a href="images/mai-image-2.6-r1-p01.png"><img src="images/mai-image-2.6-r1-p01.png" width="160"></a><br>36.6 s · $0.0391 | <a href="images/gpt-image-2-low-r1-p01.png"><img src="images/gpt-image-2-low-r1-p01.png" width="160"></a><br>26.6 s · $0.0061 | <a href="images/gpt-image-2-high-r1-p01.png"><img src="images/gpt-image-2-high-r1-p01.png" width="160"></a><br>160.7 s · $0.2110 | <a href="images/gpt-image-2.5-flare-auto-r1-p01.png"><img src="images/gpt-image-2.5-flare-auto-r1-p01.png" width="160"></a><br>21.1 s · $0.0061 · low | <a href="images/gpt-image-2.5-flare-low-r1-p01.png"><img src="images/gpt-image-2.5-flare-low-r1-p01.png" width="160"></a><br>17.6 s · $0.0061 | <a href="images/gpt-image-2.5-flare-high-r1-p01.png"><img src="images/gpt-image-2.5-flare-high-r1-p01.png" width="160"></a><br>34.4 s · $0.0529 | <a href="images/gpt-image-2.5-sunburst-auto-r1-p01.png"><img src="images/gpt-image-2.5-sunburst-auto-r1-p01.png" width="160"></a><br>28.7 s · $0.0061 · low | <a href="images/gpt-image-2.5-sunburst-low-r1-p01.png"><img src="images/gpt-image-2.5-sunburst-low-r1-p01.png" width="160"></a><br>26.9 s · $0.0061 | <a href="images/gpt-image-2.5-sunburst-high-r1-p01.png"><img src="images/gpt-image-2.5-sunburst-high-r1-p01.png" width="160"></a><br>67.0 s · $0.0529 |

### R02 · scene composition

> a portal into a mythical forest on the wall of my small messy bedroom

| MAI-Image-2.6 | GPT-Image-2 · low | GPT-Image-2 · high | GPT-Image-2.5 Flare · auto | GPT-Image-2.5 Flare · low | GPT-Image-2.5 Flare · high | GPT-Image-2.5 Sunburst · auto | GPT-Image-2.5 Sunburst · low | GPT-Image-2.5 Sunburst · high |
|---|---|---|---|---|---|---|---|---|
| <a href="images/mai-image-2.6-r1-p02.png"><img src="images/mai-image-2.6-r1-p02.png" width="160"></a><br>31.0 s · $0.0390 | <a href="images/gpt-image-2-low-r1-p02.png"><img src="images/gpt-image-2-low-r1-p02.png" width="160"></a><br>23.0 s · $0.0060 | <a href="images/gpt-image-2-high-r1-p02.png"><img src="images/gpt-image-2-high-r1-p02.png" width="160"></a><br>153.5 s · $0.2108 | <a href="images/gpt-image-2.5-flare-auto-r1-p02.png"><img src="images/gpt-image-2.5-flare-auto-r1-p02.png" width="160"></a><br>23.3 s · $0.0133 · medium | <a href="images/gpt-image-2.5-flare-low-r1-p02.png"><img src="images/gpt-image-2.5-flare-low-r1-p02.png" width="160"></a><br>22.4 s · $0.0060 | <a href="images/gpt-image-2.5-flare-high-r1-p02.png"><img src="images/gpt-image-2.5-flare-high-r1-p02.png" width="160"></a><br>38.1 s · $0.0528 | <a href="images/gpt-image-2.5-sunburst-auto-r1-p02.png"><img src="images/gpt-image-2.5-sunburst-auto-r1-p02.png" width="160"></a><br>39.7 s · $0.0133 · medium | <a href="images/gpt-image-2.5-sunburst-low-r1-p02.png"><img src="images/gpt-image-2.5-sunburst-low-r1-p02.png" width="160"></a><br>39.4 s · $0.0060 | <a href="images/gpt-image-2.5-sunburst-high-r1-p02.png"><img src="images/gpt-image-2.5-sunburst-high-r1-p02.png" width="160"></a><br>68.4 s · $0.0528 |

### R03 · whimsical concept

> a tiny astronaut hatching from an egg on the moon

| MAI-Image-2.6 | GPT-Image-2 · low | GPT-Image-2 · high | GPT-Image-2.5 Flare · auto | GPT-Image-2.5 Flare · low | GPT-Image-2.5 Flare · high | GPT-Image-2.5 Sunburst · auto | GPT-Image-2.5 Sunburst · low | GPT-Image-2.5 Sunburst · high |
|---|---|---|---|---|---|---|---|---|
| <a href="images/mai-image-2.6-r1-p03.png"><img src="images/mai-image-2.6-r1-p03.png" width="160"></a><br>27.1 s · $0.0390 | <a href="images/gpt-image-2-low-r1-p03.png"><img src="images/gpt-image-2-low-r1-p03.png" width="160"></a><br>22.4 s · $0.0060 | <a href="images/gpt-image-2-high-r1-p03.png"><img src="images/gpt-image-2-high-r1-p03.png" width="160"></a><br>151.9 s · $0.2108 | <a href="images/gpt-image-2.5-flare-auto-r1-p03.png"><img src="images/gpt-image-2.5-flare-auto-r1-p03.png" width="160"></a><br>19.7 s · $0.0060 · low | <a href="images/gpt-image-2.5-flare-low-r1-p03.png"><img src="images/gpt-image-2.5-flare-low-r1-p03.png" width="160"></a><br>19.3 s · $0.0060 | <a href="images/gpt-image-2.5-flare-high-r1-p03.png"><img src="images/gpt-image-2.5-flare-high-r1-p03.png" width="160"></a><br>29.7 s · $0.0528 | <a href="images/gpt-image-2.5-sunburst-auto-r1-p03.png"><img src="images/gpt-image-2.5-sunburst-auto-r1-p03.png" width="160"></a><br>35.9 s · $0.0060 · low | <a href="images/gpt-image-2.5-sunburst-low-r1-p03.png"><img src="images/gpt-image-2.5-sunburst-low-r1-p03.png" width="160"></a><br>30.7 s · $0.0060 | <a href="images/gpt-image-2.5-sunburst-high-r1-p03.png"><img src="images/gpt-image-2.5-sunburst-high-r1-p03.png" width="160"></a><br>77.6 s · $0.0528 |

### R04 · photoreal macro

> Photo realistic scene inspired by LOTR: [A tiny red dragon in a nest on a medieval wizard's table]. Shot with a macro lens (f/2.8, 50mm) and a Canon EOSR5, the soft focus captures [the cozy morning light filtering through a near by window]. The pastel colors and whimsical steam shapes enhance the serene atmosphere, evoking a DnD RPG setting. The image is rendered in 16K and 8K, highlighting [the intricate details and medieval charm].

| MAI-Image-2.6 | GPT-Image-2 · low | GPT-Image-2 · high | GPT-Image-2.5 Flare · auto | GPT-Image-2.5 Flare · low | GPT-Image-2.5 Flare · high | GPT-Image-2.5 Sunburst · auto | GPT-Image-2.5 Sunburst · low | GPT-Image-2.5 Sunburst · high |
|---|---|---|---|---|---|---|---|---|
| <a href="images/mai-image-2.6-r1-p04.png"><img src="images/mai-image-2.6-r1-p04.png" width="160"></a><br>38.6 s · $0.0394 | <a href="images/gpt-image-2-low-r1-p04.png"><img src="images/gpt-image-2-low-r1-p04.png" width="160"></a><br>24.2 s · $0.0064 | <a href="images/gpt-image-2-high-r1-p04.png"><img src="images/gpt-image-2-high-r1-p04.png" width="160"></a><br>156.8 s · $0.2113 | <a href="images/gpt-image-2.5-flare-auto-r1-p04.png"><img src="images/gpt-image-2.5-flare-auto-r1-p04.png" width="160"></a><br>16.0 s · $0.0064 · low | <a href="images/gpt-image-2.5-flare-low-r1-p04.png"><img src="images/gpt-image-2.5-flare-low-r1-p04.png" width="160"></a><br>20.6 s · $0.0064 | <a href="images/gpt-image-2.5-flare-high-r1-p04.png"><img src="images/gpt-image-2.5-flare-high-r1-p04.png" width="160"></a><br>29.4 s · $0.0532 | <a href="images/gpt-image-2.5-sunburst-auto-r1-p04.png"><img src="images/gpt-image-2.5-sunburst-auto-r1-p04.png" width="160"></a><br>32.1 s · $0.0064 · low | <a href="images/gpt-image-2.5-sunburst-low-r1-p04.png"><img src="images/gpt-image-2.5-sunburst-low-r1-p04.png" width="160"></a><br>34.6 s · $0.0064 | <a href="images/gpt-image-2.5-sunburst-high-r1-p04.png"><img src="images/gpt-image-2.5-sunburst-high-r1-p04.png" width="160"></a><br>84.6 s · $0.0532 |

### R05 · stylized creature

> Cute and adorable fluffy cute creature fantasy, dreamlike, surrealism, super cute, trending on artstation

| MAI-Image-2.6 | GPT-Image-2 · low | GPT-Image-2 · high | GPT-Image-2.5 Flare · auto | GPT-Image-2.5 Flare · low | GPT-Image-2.5 Flare · high | GPT-Image-2.5 Sunburst · auto | GPT-Image-2.5 Sunburst · low | GPT-Image-2.5 Sunburst · high |
|---|---|---|---|---|---|---|---|---|
| <a href="images/mai-image-2.6-r1-p05.png"><img src="images/mai-image-2.6-r1-p05.png" width="160"></a><br>29.7 s · $0.0390 | <a href="images/gpt-image-2-low-r1-p05.png"><img src="images/gpt-image-2-low-r1-p05.png" width="160"></a><br>27.3 s · $0.0060 | <a href="images/gpt-image-2-high-r1-p05.png"><img src="images/gpt-image-2-high-r1-p05.png" width="160"></a><br>149.4 s · $0.2109 | <a href="images/gpt-image-2.5-flare-auto-r1-p05.png"><img src="images/gpt-image-2.5-flare-auto-r1-p05.png" width="160"></a><br>24.6 s · $0.0060 · low | <a href="images/gpt-image-2.5-flare-low-r1-p05.png"><img src="images/gpt-image-2.5-flare-low-r1-p05.png" width="160"></a><br>20.6 s · $0.0060 | <a href="images/gpt-image-2.5-flare-high-r1-p05.png"><img src="images/gpt-image-2.5-flare-high-r1-p05.png" width="160"></a><br>33.9 s · $0.0528 | <a href="images/gpt-image-2.5-sunburst-auto-r1-p05.png"><img src="images/gpt-image-2.5-sunburst-auto-r1-p05.png" width="160"></a><br>32.5 s · $0.0060 · low | <a href="images/gpt-image-2.5-sunburst-low-r1-p05.png"><img src="images/gpt-image-2.5-sunburst-low-r1-p05.png" width="160"></a><br>37.4 s · $0.0060 | <a href="images/gpt-image-2.5-sunburst-high-r1-p05.png"><img src="images/gpt-image-2.5-sunburst-high-r1-p05.png" width="160"></a><br>78.0 s · $0.0528 |

### R06 · landscape long prompt

> A hidden cenote in the heart of a lush jungle beckons with crystalline turquoise waters. Vibrant emerald vines cascade down weathered limestone walls, their tendrils barely kissing the water's surface. Shafts of golden sunlight pierce through a natural skylight above, creating a mystical interplay of light and shadow on the cavern walls. Iridescent butterflies flit between exotic orchids clinging to rocky outcrops. A partially submerged Mayan ruin, its intricate carvings softened by time, stand

| MAI-Image-2.6 | GPT-Image-2 · low | GPT-Image-2 · high | GPT-Image-2.5 Flare · auto | GPT-Image-2.5 Flare · low | GPT-Image-2.5 Flare · high | GPT-Image-2.5 Sunburst · auto | GPT-Image-2.5 Sunburst · low | GPT-Image-2.5 Sunburst · high |
|---|---|---|---|---|---|---|---|---|
| <a href="images/mai-image-2.6-r1-p06.png"><img src="images/mai-image-2.6-r1-p06.png" width="160"></a><br>59.8 s · $0.0394 | <a href="images/gpt-image-2-low-r1-p06.png"><img src="images/gpt-image-2-low-r1-p06.png" width="160"></a><br>32.6 s · $0.0064 | <a href="images/gpt-image-2-high-r1-p06.png"><img src="images/gpt-image-2-high-r1-p06.png" width="160"></a><br>172.8 s · $0.2112 | <a href="images/gpt-image-2.5-flare-auto-r1-p06.png"><img src="images/gpt-image-2.5-flare-auto-r1-p06.png" width="160"></a><br>31.2 s · $0.0240 · medium | <a href="images/gpt-image-2.5-flare-low-r1-p06.png"><img src="images/gpt-image-2.5-flare-low-r1-p06.png" width="160"></a><br>21.5 s · $0.0064 | <a href="images/gpt-image-2.5-flare-high-r1-p06.png"><img src="images/gpt-image-2.5-flare-high-r1-p06.png" width="160"></a><br>43.5 s · $0.0532 | <a href="images/gpt-image-2.5-sunburst-auto-r1-p06.png"><img src="images/gpt-image-2.5-sunburst-auto-r1-p06.png" width="160"></a><br>48.6 s · $0.0240 · medium | <a href="images/gpt-image-2.5-sunburst-low-r1-p06.png"><img src="images/gpt-image-2.5-sunburst-low-r1-p06.png" width="160"></a><br>45.9 s · $0.0064 | <a href="images/gpt-image-2.5-sunburst-high-r1-p06.png"><img src="images/gpt-image-2.5-sunburst-high-r1-p06.png" width="160"></a><br>72.4 s · $0.0532 |

### R07 · character

> A charming, tech-savvy [girl with short, silver pixie-cut] hair and vibrant [blue] eyes, wearing a casual yet futuristic outfit. She's focused on a holographic interface while working in a sleek, high-tech workshop.

| MAI-Image-2.6 | GPT-Image-2 · low | GPT-Image-2 · high | GPT-Image-2.5 Flare · auto | GPT-Image-2.5 Flare · low | GPT-Image-2.5 Flare · high | GPT-Image-2.5 Sunburst · auto | GPT-Image-2.5 Sunburst · low | GPT-Image-2.5 Sunburst · high |
|---|---|---|---|---|---|---|---|---|
| <a href="images/mai-image-2.6-r1-p07.png"><img src="images/mai-image-2.6-r1-p07.png" width="160"></a><br>30.8 s · $0.0391 | <a href="images/gpt-image-2-low-r1-p07.png"><img src="images/gpt-image-2-low-r1-p07.png" width="160"></a><br>27.4 s · $0.0062 | <a href="images/gpt-image-2-high-r1-p07.png"><img src="images/gpt-image-2-high-r1-p07.png" width="160"></a><br>157.5 s · $0.2110 | <a href="images/gpt-image-2.5-flare-auto-r1-p07.png"><img src="images/gpt-image-2.5-flare-auto-r1-p07.png" width="160"></a><br>34.5 s · $0.0237 · medium | <a href="images/gpt-image-2.5-flare-low-r1-p07.png"><img src="images/gpt-image-2.5-flare-low-r1-p07.png" width="160"></a><br>23.6 s · $0.0062 | <a href="images/gpt-image-2.5-flare-high-r1-p07.png"><img src="images/gpt-image-2.5-flare-high-r1-p07.png" width="160"></a><br>45.1 s · $0.0529 | <a href="images/gpt-image-2.5-sunburst-auto-r1-p07.png"><img src="images/gpt-image-2.5-sunburst-auto-r1-p07.png" width="160"></a><br>53.4 s · $0.0237 · medium | <a href="images/gpt-image-2.5-sunburst-low-r1-p07.png"><img src="images/gpt-image-2.5-sunburst-low-r1-p07.png" width="160"></a><br>37.3 s · $0.0062 | <a href="images/gpt-image-2.5-sunburst-high-r1-p07.png"><img src="images/gpt-image-2.5-sunburst-high-r1-p07.png" width="160"></a><br>80.8 s · $0.0529 |

### R08 · abstract

> Universe, LSD, Fractal Worlds, Giant Eyes

| MAI-Image-2.6 | GPT-Image-2 · low | GPT-Image-2 · high | GPT-Image-2.5 Flare · auto | GPT-Image-2.5 Flare · low | GPT-Image-2.5 Flare · high | GPT-Image-2.5 Sunburst · auto | GPT-Image-2.5 Sunburst · low | GPT-Image-2.5 Sunburst · high |
|---|---|---|---|---|---|---|---|---|
| <a href="images/mai-image-2.6-r1-p08.png"><img src="images/mai-image-2.6-r1-p08.png" width="160"></a><br>28.0 s · $0.0390 | <a href="images/gpt-image-2-low-r1-p08.png"><img src="images/gpt-image-2-low-r1-p08.png" width="160"></a><br>25.3 s · $0.0060 | <a href="images/gpt-image-2-high-r1-p08.png"><img src="images/gpt-image-2-high-r1-p08.png" width="160"></a><br>166.0 s · $0.2108 | <a href="images/gpt-image-2.5-flare-auto-r1-p08.png"><img src="images/gpt-image-2.5-flare-auto-r1-p08.png" width="160"></a><br>25.4 s · $0.0132 · medium | <a href="images/gpt-image-2.5-flare-low-r1-p08.png"><img src="images/gpt-image-2.5-flare-low-r1-p08.png" width="160"></a><br>28.8 s · $0.0060 | <a href="images/gpt-image-2.5-flare-high-r1-p08.png"><img src="images/gpt-image-2.5-flare-high-r1-p08.png" width="160"></a><br>35.7 s · $0.0528 | <a href="images/gpt-image-2.5-sunburst-auto-r1-p08.png"><img src="images/gpt-image-2.5-sunburst-auto-r1-p08.png" width="160"></a><br>56.8 s · $0.0132 · medium | <a href="images/gpt-image-2.5-sunburst-low-r1-p08.png"><img src="images/gpt-image-2.5-sunburst-low-r1-p08.png" width="160"></a><br>36.6 s · $0.0060 | <a href="images/gpt-image-2.5-sunburst-high-r1-p08.png"><img src="images/gpt-image-2.5-sunburst-high-r1-p08.png" width="160"></a><br>88.5 s · $0.0528 |

### R09 · texture detail

> close up dof render of a mythical creature made of detailed spiraling fractals and tendrils, detailed recursive skin texture

| MAI-Image-2.6 | GPT-Image-2 · low | GPT-Image-2 · high | GPT-Image-2.5 Flare · auto | GPT-Image-2.5 Flare · low | GPT-Image-2.5 Flare · high | GPT-Image-2.5 Sunburst · auto | GPT-Image-2.5 Sunburst · low | GPT-Image-2.5 Sunburst · high |
|---|---|---|---|---|---|---|---|---|
| <a href="images/mai-image-2.6-r1-p09.png"><img src="images/mai-image-2.6-r1-p09.png" width="160"></a><br>29.9 s · $0.0390 | <a href="images/gpt-image-2-low-r1-p09.png"><img src="images/gpt-image-2-low-r1-p09.png" width="160"></a><br>23.8 s · $0.0060 | <a href="images/gpt-image-2-high-r1-p09.png"><img src="images/gpt-image-2-high-r1-p09.png" width="160"></a><br>141.9 s · $0.2109 | <a href="images/gpt-image-2.5-flare-auto-r1-p09.png"><img src="images/gpt-image-2.5-flare-auto-r1-p09.png" width="160"></a><br>24.1 s · $0.0133 · medium | <a href="images/gpt-image-2.5-flare-low-r1-p09.png"><img src="images/gpt-image-2.5-flare-low-r1-p09.png" width="160"></a><br>24.5 s · $0.0060 | <a href="images/gpt-image-2.5-flare-high-r1-p09.png"><img src="images/gpt-image-2.5-flare-high-r1-p09.png" width="160"></a><br>36.6 s · $0.0528 | <a href="images/gpt-image-2.5-sunburst-auto-r1-p09.png"><img src="images/gpt-image-2.5-sunburst-auto-r1-p09.png" width="160"></a><br>38.1 s · $0.0133 · medium | <a href="images/gpt-image-2.5-sunburst-low-r1-p09.png"><img src="images/gpt-image-2.5-sunburst-low-r1-p09.png" width="160"></a><br>31.1 s · $0.0060 | <a href="images/gpt-image-2.5-sunburst-high-r1-p09.png"><img src="images/gpt-image-2.5-sunburst-high-r1-p09.png" width="160"></a><br>75.0 s · $0.0528 |

### R10 · short prompt

> an angry cat playing drums

| MAI-Image-2.6 | GPT-Image-2 · low | GPT-Image-2 · high | GPT-Image-2.5 Flare · auto | GPT-Image-2.5 Flare · low | GPT-Image-2.5 Flare · high | GPT-Image-2.5 Sunburst · auto | GPT-Image-2.5 Sunburst · low | GPT-Image-2.5 Sunburst · high |
|---|---|---|---|---|---|---|---|---|
| <a href="images/mai-image-2.6-r1-p10.png"><img src="images/mai-image-2.6-r1-p10.png" width="160"></a><br>29.3 s · $0.0389 | <a href="images/gpt-image-2-low-r1-p10.png"><img src="images/gpt-image-2-low-r1-p10.png" width="160"></a><br>22.9 s · $0.0059 | <a href="images/gpt-image-2-high-r1-p10.png"><img src="images/gpt-image-2-high-r1-p10.png" width="160"></a><br>140.7 s · $0.2108 | <a href="images/gpt-image-2.5-flare-auto-r1-p10.png"><img src="images/gpt-image-2.5-flare-auto-r1-p10.png" width="160"></a><br>19.4 s · $0.0059 · low | <a href="images/gpt-image-2.5-flare-low-r1-p10.png"><img src="images/gpt-image-2.5-flare-low-r1-p10.png" width="160"></a><br>22.6 s · $0.0059 | <a href="images/gpt-image-2.5-flare-high-r1-p10.png"><img src="images/gpt-image-2.5-flare-high-r1-p10.png" width="160"></a><br>39.7 s · $0.0527 | <a href="images/gpt-image-2.5-sunburst-auto-r1-p10.png"><img src="images/gpt-image-2.5-sunburst-auto-r1-p10.png" width="160"></a><br>25.0 s · $0.0059 · low | <a href="images/gpt-image-2.5-sunburst-low-r1-p10.png"><img src="images/gpt-image-2.5-sunburst-low-r1-p10.png" width="160"></a><br>28.0 s · $0.0059 | <a href="images/gpt-image-2.5-sunburst-high-r1-p10.png"><img src="images/gpt-image-2.5-sunburst-high-r1-p10.png" width="160"></a><br>64.2 s · $0.0527 |

### R11 · short prompt

> A monkey playing music

| MAI-Image-2.6 | GPT-Image-2 · low | GPT-Image-2 · high | GPT-Image-2.5 Flare · auto | GPT-Image-2.5 Flare · low | GPT-Image-2.5 Flare · high | GPT-Image-2.5 Sunburst · auto | GPT-Image-2.5 Sunburst · low | GPT-Image-2.5 Sunburst · high |
|---|---|---|---|---|---|---|---|---|
| <a href="images/mai-image-2.6-r1-p11.png"><img src="images/mai-image-2.6-r1-p11.png" width="160"></a><br>36.3 s · $0.0389 | <a href="images/gpt-image-2-low-r1-p11.png"><img src="images/gpt-image-2-low-r1-p11.png" width="160"></a><br>22.3 s · $0.0059 | <a href="images/gpt-image-2-high-r1-p11.png"><img src="images/gpt-image-2-high-r1-p11.png" width="160"></a><br>130.8 s · $0.2108 | <a href="images/gpt-image-2.5-flare-auto-r1-p11.png"><img src="images/gpt-image-2.5-flare-auto-r1-p11.png" width="160"></a><br>19.8 s · $0.0059 · low | <a href="images/gpt-image-2.5-flare-low-r1-p11.png"><img src="images/gpt-image-2.5-flare-low-r1-p11.png" width="160"></a><br>19.4 s · $0.0059 | <a href="images/gpt-image-2.5-flare-high-r1-p11.png"><img src="images/gpt-image-2.5-flare-high-r1-p11.png" width="160"></a><br>38.5 s · $0.0527 | <a href="images/gpt-image-2.5-sunburst-auto-r1-p11.png"><img src="images/gpt-image-2.5-sunburst-auto-r1-p11.png" width="160"></a><br>31.3 s · $0.0059 · low | <a href="images/gpt-image-2.5-sunburst-low-r1-p11.png"><img src="images/gpt-image-2.5-sunburst-low-r1-p11.png" width="160"></a><br>35.7 s · $0.0059 | <a href="images/gpt-image-2.5-sunburst-high-r1-p11.png"><img src="images/gpt-image-2.5-sunburst-high-r1-p11.png" width="160"></a><br>69.5 s · $0.0527 |

### A01 · photorealistic portrait

> Create a photorealistic editorial photograph, square composition. An adult East Asian ceramic artist in a bright workshop holds a small white porcelain bowl with both hands, all fingers naturally visible. Three-quarter waist-up portrait, natural skin texture, soft morning window light from the left and a subtle warm rim light from the right. Shelves of pottery softly out of focus, realistic anatomy and physically consistent shadows. No text, no logos, no watermark.

| MAI-Image-2.6 | GPT-Image-2 · low | GPT-Image-2 · high | GPT-Image-2.5 Flare · auto | GPT-Image-2.5 Flare · low | GPT-Image-2.5 Flare · high | GPT-Image-2.5 Sunburst · auto | GPT-Image-2.5 Sunburst · low | GPT-Image-2.5 Sunburst · high |
|---|---|---|---|---|---|---|---|---|
| <a href="images/mai-image-2.6-r1-p12.png"><img src="images/mai-image-2.6-r1-p12.png" width="160"></a><br>30.1 s · $0.0394 | <a href="images/gpt-image-2-low-r1-p12.png"><img src="images/gpt-image-2-low-r1-p12.png" width="160"></a><br>23.0 s · $0.0064 | <a href="images/gpt-image-2-high-r1-p12.png"><img src="images/gpt-image-2-high-r1-p12.png" width="160"></a><br>135.8 s · $0.2112 | <a href="images/gpt-image-2.5-flare-auto-r1-p12.png"><img src="images/gpt-image-2.5-flare-auto-r1-p12.png" width="160"></a><br>39.4 s · $0.0532 · high | <a href="images/gpt-image-2.5-flare-low-r1-p12.png"><img src="images/gpt-image-2.5-flare-low-r1-p12.png" width="160"></a><br>23.1 s · $0.0064 | <a href="images/gpt-image-2.5-flare-high-r1-p12.png"><img src="images/gpt-image-2.5-flare-high-r1-p12.png" width="160"></a><br>29.5 s · $0.0532 | <a href="images/gpt-image-2.5-sunburst-auto-r1-p12.png"><img src="images/gpt-image-2.5-sunburst-auto-r1-p12.png" width="160"></a><br>63.9 s · $0.0532 · high | <a href="images/gpt-image-2.5-sunburst-low-r1-p12.png"><img src="images/gpt-image-2.5-sunburst-low-r1-p12.png" width="160"></a><br>26.3 s · $0.0064 | <a href="images/gpt-image-2.5-sunburst-high-r1-p12.png"><img src="images/gpt-image-2.5-sunburst-high-r1-p12.png" width="160"></a><br>74.7 s · $0.0532 |

### A02 · product and materials

> Create a premium studio product advertising photograph in a square composition. Exactly one unbranded brushed silver stainless-steel vacuum bottle stands upright on a pale stone block. Beside it sits one transparent glass containing clear sparkling water and exactly one thin lemon slice. Tiny realistic condensation droplets on the bottle, precise brushed metal texture, physically plausible glass refraction and reflections. Soft pale blue background, elegant negative space in the upper third, controlled softbox lighting. No lettering, no logos, no watermark.

| MAI-Image-2.6 | GPT-Image-2 · low | GPT-Image-2 · high | GPT-Image-2.5 Flare · auto | GPT-Image-2.5 Flare · low | GPT-Image-2.5 Flare · high | GPT-Image-2.5 Sunburst · auto | GPT-Image-2.5 Sunburst · low | GPT-Image-2.5 Sunburst · high |
|---|---|---|---|---|---|---|---|---|
| <a href="images/mai-image-2.6-r1-p13.png"><img src="images/mai-image-2.6-r1-p13.png" width="160"></a><br>26.8 s · $0.0394 | <a href="images/gpt-image-2-low-r1-p13.png"><img src="images/gpt-image-2-low-r1-p13.png" width="160"></a><br>20.1 s · $0.0064 | <a href="images/gpt-image-2-high-r1-p13.png"><img src="images/gpt-image-2-high-r1-p13.png" width="160"></a><br>122.2 s · $0.2112 | <a href="images/gpt-image-2.5-flare-auto-r1-p13.png"><img src="images/gpt-image-2.5-flare-auto-r1-p13.png" width="160"></a><br>20.1 s · $0.0064 · low | <a href="images/gpt-image-2.5-flare-low-r1-p13.png"><img src="images/gpt-image-2.5-flare-low-r1-p13.png" width="160"></a><br>19.1 s · $0.0064 | <a href="images/gpt-image-2.5-flare-high-r1-p13.png"><img src="images/gpt-image-2.5-flare-high-r1-p13.png" width="160"></a><br>39.7 s · $0.0532 | <a href="images/gpt-image-2.5-sunburst-auto-r1-p13.png"><img src="images/gpt-image-2.5-sunburst-auto-r1-p13.png" width="160"></a><br>32.0 s · $0.0064 · low | <a href="images/gpt-image-2.5-sunburst-low-r1-p13.png"><img src="images/gpt-image-2.5-sunburst-low-r1-p13.png" width="160"></a><br>27.1 s · $0.0064 | <a href="images/gpt-image-2.5-sunburst-high-r1-p13.png"><img src="images/gpt-image-2.5-sunburst-high-r1-p13.png" width="160"></a><br>64.5 s · $0.0532 |

### A03 · Chinese/English poster text

> 设计一张正方形的高品质咖啡店活动海报，现代简洁排版，奶油白背景配深绿色文字，中心是一杯写实拿铁，杯面有清晰叶形拉花。只允许出现以下四行文字，必须逐字准确、不增不减，每行单独排版：第一行标题「周末慢一点」，第二行「第二杯半价」，第三行「9月20日—9月21日」，第四行英文「COFFEE & CALM」。文字清晰易读，不要额外文字、标志或水印。

| MAI-Image-2.6 | GPT-Image-2 · low | GPT-Image-2 · high | GPT-Image-2.5 Flare · auto | GPT-Image-2.5 Flare · low | GPT-Image-2.5 Flare · high | GPT-Image-2.5 Sunburst · auto | GPT-Image-2.5 Sunburst · low | GPT-Image-2.5 Sunburst · high |
|---|---|---|---|---|---|---|---|---|
| <a href="images/mai-image-2.6-r1-p14.png"><img src="images/mai-image-2.6-r1-p14.png" width="160"></a><br>27.8 s · $0.0396 | <a href="images/gpt-image-2-low-r1-p14.png"><img src="images/gpt-image-2-low-r1-p14.png" width="160"></a><br>21.2 s · $0.0066 | <a href="images/gpt-image-2-high-r1-p14.png"><img src="images/gpt-image-2-high-r1-p14.png" width="160"></a><br>132.5 s · $0.2114 | <a href="images/gpt-image-2.5-flare-auto-r1-p14.png"><img src="images/gpt-image-2.5-flare-auto-r1-p14.png" width="160"></a><br>24.3 s · $0.0241 · medium | <a href="images/gpt-image-2.5-flare-low-r1-p14.png"><img src="images/gpt-image-2.5-flare-low-r1-p14.png" width="160"></a><br>18.8 s · $0.0066 | <a href="images/gpt-image-2.5-flare-high-r1-p14.png"><img src="images/gpt-image-2.5-flare-high-r1-p14.png" width="160"></a><br>48.3 s · $0.0534 | <a href="images/gpt-image-2.5-sunburst-auto-r1-p14.png"><img src="images/gpt-image-2.5-sunburst-auto-r1-p14.png" width="160"></a><br>43.3 s · $0.0241 · medium | <a href="images/gpt-image-2.5-sunburst-low-r1-p14.png"><img src="images/gpt-image-2.5-sunburst-low-r1-p14.png" width="160"></a><br>30.5 s · $0.0066 | <a href="images/gpt-image-2.5-sunburst-high-r1-p14.png"><img src="images/gpt-image-2.5-sunburst-high-r1-p14.png" width="160"></a><br>71.0 s · $0.0534 |

### A04 · object count and spatial

> Create a clean, photorealistic still-life photograph in square format on a plain light-gray tabletop against a neutral background. Show exactly five separate objects in a single horizontal row, ordered from the viewer's left to right: one red ceramic mug, one yellow banana, one blue closed book, one green glass bottle, and one white tennis ball. The mug handle points left. A single small silver key lies on top of the blue book; the key is the only additional object, making six objects total. All objects must be fully visible, with no overlaps except the key on the book. Soft daylight, realistic shadows. No writing, no additional objects, no watermark.

| MAI-Image-2.6 | GPT-Image-2 · low | GPT-Image-2 · high | GPT-Image-2.5 Flare · auto | GPT-Image-2.5 Flare · low | GPT-Image-2.5 Flare · high | GPT-Image-2.5 Sunburst · auto | GPT-Image-2.5 Sunburst · low | GPT-Image-2.5 Sunburst · high |
|---|---|---|---|---|---|---|---|---|
| <a href="images/mai-image-2.6-r1-p15.png"><img src="images/mai-image-2.6-r1-p15.png" width="160"></a><br>27.8 s · $0.0396 | <a href="images/gpt-image-2-low-r1-p15.png"><img src="images/gpt-image-2-low-r1-p15.png" width="160"></a><br>17.7 s · $0.0066 | <a href="images/gpt-image-2-high-r1-p15.png"><img src="images/gpt-image-2-high-r1-p15.png" width="160"></a><br>115.7 s · $0.2114 | <a href="images/gpt-image-2.5-flare-auto-r1-p15.png"><img src="images/gpt-image-2.5-flare-auto-r1-p15.png" width="160"></a><br>23.7 s · $0.0139 · medium | <a href="images/gpt-image-2.5-flare-low-r1-p15.png"><img src="images/gpt-image-2.5-flare-low-r1-p15.png" width="160"></a><br>18.5 s · $0.0066 | <a href="images/gpt-image-2.5-flare-high-r1-p15.png"><img src="images/gpt-image-2.5-flare-high-r1-p15.png" width="160"></a><br>36.5 s · $0.0534 | <a href="images/gpt-image-2.5-sunburst-auto-r1-p15.png"><img src="images/gpt-image-2.5-sunburst-auto-r1-p15.png" width="160"></a><br>30.6 s · $0.0139 · medium | <a href="images/gpt-image-2.5-sunburst-low-r1-p15.png"><img src="images/gpt-image-2.5-sunburst-low-r1-p15.png" width="160"></a><br>25.4 s · $0.0066 | <a href="images/gpt-image-2.5-sunburst-high-r1-p15.png"><img src="images/gpt-image-2.5-sunburst-high-r1-p15.png" width="160"></a><br>68.0 s · $0.0534 |

### A05 · business infographic

> Create a polished square business infographic on a white background with teal and navy accents. Main heading must be exactly 'IDEA TO LAUNCH'. Beneath the heading, show exactly four equally sized cards in a left-to-right horizontal flow, connected by three right-pointing arrows. The card headings in order must be exactly '1 RESEARCH', '2 DESIGN', '3 BUILD', '4 LAUNCH'. Each card has one simple corresponding icon: magnifying glass, pencil, gear, rocket. Beneath each heading show exactly one line respectively: 'Find the need', 'Shape the plan', 'Make it work', 'Share the result'. Excellent readable typography, aligned spacing, generous margins, flat vector style. No other text and no watermark.

| MAI-Image-2.6 | GPT-Image-2 · low | GPT-Image-2 · high | GPT-Image-2.5 Flare · auto | GPT-Image-2.5 Flare · low | GPT-Image-2.5 Flare · high | GPT-Image-2.5 Sunburst · auto | GPT-Image-2.5 Sunburst · low | GPT-Image-2.5 Sunburst · high |
|---|---|---|---|---|---|---|---|---|
| <a href="images/mai-image-2.6-r1-p16.png"><img src="images/mai-image-2.6-r1-p16.png" width="160"></a><br>26.3 s · $0.0397 | <a href="images/gpt-image-2-low-r1-p16.png"><img src="images/gpt-image-2-low-r1-p16.png" width="160"></a><br>20.6 s · $0.0067 | <a href="images/gpt-image-2-high-r1-p16.png"><img src="images/gpt-image-2-high-r1-p16.png" width="160"></a><br>111.1 s · $0.2115 | <a href="images/gpt-image-2.5-flare-auto-r1-p16.png"><img src="images/gpt-image-2.5-flare-auto-r1-p16.png" width="160"></a><br>21.9 s · $0.0242 · medium | <a href="images/gpt-image-2.5-flare-low-r1-p16.png"><img src="images/gpt-image-2.5-flare-low-r1-p16.png" width="160"></a><br>16.2 s · $0.0067 | <a href="images/gpt-image-2.5-flare-high-r1-p16.png"><img src="images/gpt-image-2.5-flare-high-r1-p16.png" width="160"></a><br>27.8 s · $0.0535 | <a href="images/gpt-image-2.5-sunburst-auto-r1-p16.png"><img src="images/gpt-image-2.5-sunburst-auto-r1-p16.png" width="160"></a><br>39.4 s · $0.0242 · medium | <a href="images/gpt-image-2.5-sunburst-low-r1-p16.png"><img src="images/gpt-image-2.5-sunburst-low-r1-p16.png" width="160"></a><br>28.0 s · $0.0067 | <a href="images/gpt-image-2.5-sunburst-high-r1-p16.png"><img src="images/gpt-image-2.5-sunburst-high-r1-p16.png" width="160"></a><br>60.9 s · $0.0535 |

### A06 · storybook illustration

> Create a richly detailed square storybook illustration in a consistent hand-painted gouache style. A tiny traveling library is built on the back of one enormous gentle turtle walking through a rainy forest at dusk. The library has warm glowing windows, a curved green roof, and a small ladder on its left side. Exactly two adult travelers wearing red raincoats walk beside the turtle. Cool blue-green forest, warm amber window light reflected in puddles, layered foliage, whimsical yet coherent architecture, clear focal point, painterly texture throughout. No text, no lettering, no watermark.

| MAI-Image-2.6 | GPT-Image-2 · low | GPT-Image-2 · high | GPT-Image-2.5 Flare · auto | GPT-Image-2.5 Flare · low | GPT-Image-2.5 Flare · high | GPT-Image-2.5 Sunburst · auto | GPT-Image-2.5 Sunburst · low | GPT-Image-2.5 Sunburst · high |
|---|---|---|---|---|---|---|---|---|
| <a href="images/mai-image-2.6-r1-p17.png"><img src="images/mai-image-2.6-r1-p17.png" width="160"></a><br>54.9 s · $0.0395 | <a href="images/gpt-image-2-low-r1-p17.png"><img src="images/gpt-image-2-low-r1-p17.png" width="160"></a><br>26.8 s · $0.0065 | <a href="images/gpt-image-2-high-r1-p17.png"><img src="images/gpt-image-2-high-r1-p17.png" width="160"></a><br>184.8 s · $0.2113 | <a href="images/gpt-image-2.5-flare-auto-r1-p17.png"><img src="images/gpt-image-2.5-flare-auto-r1-p17.png" width="160"></a><br>29.2 s · $0.0240 · medium | <a href="images/gpt-image-2.5-flare-low-r1-p17.png"><img src="images/gpt-image-2.5-flare-low-r1-p17.png" width="160"></a><br>34.6 s · $0.0065 | <a href="images/gpt-image-2.5-flare-high-r1-p17.png"><img src="images/gpt-image-2.5-flare-high-r1-p17.png" width="160"></a><br>36.5 s · $0.0533 | <a href="images/gpt-image-2.5-sunburst-auto-r1-p17.png"><img src="images/gpt-image-2.5-sunburst-auto-r1-p17.png" width="160"></a><br>49.4 s · $0.0240 · medium | <a href="images/gpt-image-2.5-sunburst-low-r1-p17.png"><img src="images/gpt-image-2.5-sunburst-low-r1-p17.png" width="160"></a><br>34.2 s · $0.0065 | <a href="images/gpt-image-2.5-sunburst-high-r1-p17.png"><img src="images/gpt-image-2.5-sunburst-high-r1-p17.png" width="160"></a><br>79.2 s · $0.0533 |

## Method

| | |
|---|---|
| Run | `us-matrix-9g-20260926`, 2026-09-26 |
| Client | Xinyu SURFACE-2 laptop; resources East US (MAI) / East US 2 (GPT); Entra bearer auth |
| Resource · MAI-Image-2.6 | xinyuwei-2026-eastus-img (East US, GlobalStandard) |
| Resource · gpt-image-2 / 2.5-flare / 2.5-sunburst | xinyuwei-2026-resource (East US 2, GlobalStandard) |
| Region caveat | GlobalStandard deployments do not pin the GPU to the resource region; timings are client->Azure front door->wherever the model is served. Resource region is a fact; GPU region is not observable from the client. |
| mai-image-2.6 | MAI-Image-2.6 2026-07-31 · Entra ID · timeout 180 s |
| gpt-image-2-low | gpt-image-2 2026-04-21 · api-version 2025-04-01-preview · Entra ID · timeout 900 s |
| gpt-image-2-high | gpt-image-2 2026-04-21 · api-version 2025-04-01-preview · Entra ID · timeout 900 s |
| gpt-image-2.5-flare-auto | gpt-image-2.5-flare 2026-09-08 · api-version 2025-04-01-preview · Entra ID · timeout 900 s |
| gpt-image-2.5-flare-low | gpt-image-2.5-flare 2026-09-08 · api-version 2025-04-01-preview · Entra ID · timeout 900 s |
| gpt-image-2.5-flare-high | gpt-image-2.5-flare 2026-09-08 · api-version 2025-04-01-preview · Entra ID · timeout 900 s |
| gpt-image-2.5-sunburst-auto | gpt-image-2.5-sunburst 2026-09-08 · api-version 2025-04-01-preview · Entra ID · timeout 900 s |
| gpt-image-2.5-sunburst-low | gpt-image-2.5-sunburst 2026-09-08 · api-version 2025-04-01-preview · Entra ID · timeout 900 s |
| gpt-image-2.5-sunburst-high | gpt-image-2.5-sunburst 2026-09-08 · api-version 2025-04-01-preview · Entra ID · timeout 900 s |
| Resolution | 1024x1024 PNG, one image per request |
| Pacing | 5 s between calls; 2 requests per 60 s per deployment |
| Order | round 1 forward, round 2 reversed: mai-image-2.6 → gpt-image-2-low → gpt-image-2-high … |
| Prompts | `source/prompts.csv`, SHA-256 `80ccc57bd44c1f37…` |
| Runner | `source/benchmark_5way_v2.py`, SHA-256 `24f2e805681cd69e…` |
| Runner revised mid-run | 2026-09-26T01:59Z, `a04944f4db61` → `24f2e805681c` after 41 ok / 7 failed samples: v2.2: bearer token refreshed from JWT exp and on HTTP 401; resume re-runs failed samples. Payloads, pacing, prompts, latency definition unchanged. Previous source kept as `source/benchmark_5way_v2.pre-revision-a04944f4db61.py`; failed samples were re-run, not patched. |
| Failed attempts | 22 of 337 logged requests failed (HTTP 401: 21, HTTP 429: 1); each affected sample was retried until it returned an image, and only the successful attempt's latency is reported. Every request is in `attempts.jsonl`. |

**What this does not show.** One client, one day, concurrency 1: these are typical latencies, not P95 under load. GlobalStandard deployments do not pin the physical GPU region. No image-quality score is computed; the images are shown so a reader can judge for the scenario they care about. GPT tiers are not calibrated to MAI's single tier — compare on output tokens per image, which is what each provider bills.

## Reproduce

```
pip install -r requirements.txt
python render.py runs/us-matrix-9g-20260926 --check   # re-renders from the frozen run and diffs against README.md
```

To measure again, use the test pack in `testpack/` with your own deployments; see `testpack/README.md`.
