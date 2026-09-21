# MAI-Image-2.6 vs GPT-Image-2.5: All Quality Tiers

[![Models](https://img.shields.io/badge/Models-MAI--Image--2.6%20vs%20GPT--Image--2.5-0067b8)](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai-image) [![Samples](https://img.shields.io/badge/Samples-850%20measured-2e7d32)](data) ![Resolution](https://img.shields.io/badge/Resolution-1024%C3%971024-455a64) ![MAI version](https://img.shields.io/badge/MAI%20version-2026--07--31-6a1b9a) ![Data through](https://img.shields.io/badge/Data%20through-2026--09--21-37474f) [![Status](https://img.shields.io/badge/Status-Preview%20%C2%B7%20no%20SLA-b26500)](https://azure.microsoft.com/support/legal/preview-supplemental-terms/) [![Tests](https://img.shields.io/badge/Tests-87%20offline-00695c)](tests)

A measured comparison of MAI-Image-2.6 against GPT-Image-2.5 from one client, one account and one region (swedencentral). The spine is the same-session run of 2026-09-20, in which MAI and 2.5 flare medium and high were called alternately over 11 text-to-image scenarios in two rounds; the remaining tiers, image editing, Chinese/English text rendering, invoice cost and web grounding each have their own section and evidence directory. Image judgements are unblinded difference descriptions and produce no quality score or preference verdict.

> **Author**: Xinyu Wei (魏新宇) — Microsoft AI GBB Senior System Engineer

[English](README.md) | [中文](README-CN.md)

[Side-by-side images](#side-by-side-image-comparison) · [Image edit](#test-12-headwear-swap-image-edit) · [Latency and requests](#performance-and-reliability) · [Six tiers](#the-six-gpt-image-25-quality-tiers) · [Cost](#actual-cost-per-image-from-this-accounts-invoice) · [Text rendering](#chinese-and-english-text-rendering) · [Web grounding](#web-grounding-test) · [Reproduction](#reproduction-how-to) · [Raw evidence](data/mai-vs-gpt25-20260920)

---

## What the Measurements Show

All 5 items rest on the measurements in this repository; MAI-Image-2.6 is in preview with no SLA. Image quality has no numeric score: the side-by-side images are the evidence and the reader's judgement is the conclusion.

1. **In one session, MAI is level with 2.5 high on speed and slower than 2.5 medium.** 66/66 samples returned images; P50: MAI 31.61 s, 2.5 medium 22.24 s (MAI 1.42x slower), 2.5 high 32.11 s (level). The three were called alternately by one client, with no region or date difference. 2.5 low, in its own session on 2026-09-17, had a P50 of 21.85 s, faster than MAI but not the same session.

2. **On this account's invoice, MAI costs $38.91 per 1,000 images: 6.6x 2.5 low ($5.88), 3.0x 2.5 medium ($13.17) and 26% less than 2.5 high ($52.68).** Rates come from Azure Cost Management actuals, not a price page; 2.5 has no published price. "Expensive" only holds once the comparison tier is named; what each tier's images look like is in the side-by-side tables.

3. **Hard-set text rendering: MAI scores 100% in both languages, including the simplified-vs-traditional trap.** 6 scenes × 2 languages × 2 rounds, read back by a calibrated vision judge: GPT-Image-2.5 Flare auto missed 1 (H3 zh r2); GPT-Image-2.5 Flare max missed 1 (H4 en r2); GPT-Image-2.5 Flare xhigh missed 1 (H4 en r2). The documentation lists MAI's Languages as `en`; the Chinese result is an observation outside that declared scope.

4. **Image edit: all three configurations add the graduation cap and keep all 5 preservation items in both rounds.** MAI's output (1360×768) matches the input in colour and framing and reads as a head-only repaint; 2.5 (1674×940) regenerates the whole frame, keeping composition but re-rendering texture, and 2.5 medium misspells the title ADVISORS as ASVISORS in both rounds. Per-image checklist in Scenario 12.

5. **`web_grounding=true` adds current web information at generation time.** The model retrieves current information from Bing Search as extra context, which moved the product text facts in two subjects from wrong to matching the official announcement; the cost is a lower first-attempt success rate and clearly higher latency. This is a MAI-only parameter with no GPT counterpart.

## Side-by-Side Image Comparison

Scenarios 1-11 are text-to-image, two rounds each. In every round the first row is MAI-Image-2.6, GPT-Image-2.5 Flare medium, GPT-Image-2.5 Flare high, called alternately in one session on 2026-09-20; the second row is the remaining GPT-Image-2.5 Flare tiers, measured on 2026-09-17 and 2026-09-18 with the same client and prompt file, dated in the header. The rows are not the same session, so read the latencies under the images together with their dates. Sunburst is a second deployment of the same model; its images stay in the evidence directory and its numbers are in the tier table below. Click an image for the original 1024x1024 PNG. Scenario 12 is an image edit of one real photograph.

### Test 1: Chrome Kimono Metallic Maiden

> **Prompt**: Chrome kimono, a maiden surrounded by metallic flowers, earrings, ornate, dark blue, exquisite realism, high exposure, Canon 5D, cinematic lighting, metallic luster, blurred foreground, depth of field, light

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high |
| --- | --- | --- |
| ![MAI-Image-2.6, prompt 1, round 1](data/mai-vs-gpt25-20260920/mai-image-2.6/r1/01_test.png) | ![GPT-Image-2.5 Flare medium, prompt 1, round 1](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-medium/r1/01_test.png) | ![GPT-Image-2.5 Flare high, prompt 1, round 1](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-high/r1/01_test.png) |
| 46.69 s<br>1687 KiB | 20.50 s<br>1715 KiB | 31.45 s<br>1783 KiB |

| GPT-Image-2.5 Flare low<br>(2026-09-17) | GPT-Image-2.5 Flare xhigh<br>(2026-09-18) | GPT-Image-2.5 Flare max<br>(2026-09-18) | GPT-Image-2.5 Flare auto<br>(2026-09-18) |
| --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 1, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r1/01_test.png) | ![GPT-Image-2.5 Flare xhigh, prompt 1, round 1](data/gpt25-tiers-20260918/gpt-image-2.5-flare-xhigh/r1/01_test.png) | ![GPT-Image-2.5 Flare max, prompt 1, round 1](data/gpt25-tiers-20260918/gpt-image-2.5-flare-max/r1/01_test.png) | ![GPT-Image-2.5 Flare auto, prompt 1, round 1](data/gpt25-tiers-20260918/gpt-image-2.5-flare-auto/r1/01_test.png) |
| 21.93 s<br>1631 KiB | 43.22 s<br>1697 KiB | 66.83 s<br>1683 KiB | 19.37 s<br>1658 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high |
| --- | --- | --- |
| ![MAI-Image-2.6, prompt 1, round 2](data/mai-vs-gpt25-20260920/mai-image-2.6/r2/01_test.png) | ![GPT-Image-2.5 Flare medium, prompt 1, round 2](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-medium/r2/01_test.png) | ![GPT-Image-2.5 Flare high, prompt 1, round 2](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-high/r2/01_test.png) |
| 31.04 s<br>1644 KiB | 25.36 s<br>1801 KiB | 28.44 s<br>1693 KiB |

| GPT-Image-2.5 Flare low<br>(2026-09-17) | GPT-Image-2.5 Flare xhigh<br>(2026-09-18) | GPT-Image-2.5 Flare max<br>(2026-09-18) | GPT-Image-2.5 Flare auto<br>(2026-09-18) |
| --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 1, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r2/01_test.png) | ![GPT-Image-2.5 Flare xhigh, prompt 1, round 2](data/gpt25-tiers-20260918/gpt-image-2.5-flare-xhigh/r2/01_test.png) | ![GPT-Image-2.5 Flare max, prompt 1, round 2](data/gpt25-tiers-20260918/gpt-image-2.5-flare-max/r2/01_test.png) | ![GPT-Image-2.5 Flare auto, prompt 1, round 2](data/gpt25-tiers-20260918/gpt-image-2.5-flare-auto/r2/01_test.png) |
| 17.66 s<br>1546 KiB | 40.05 s<br>1753 KiB | 73.42 s<br>1631 KiB | 21.75 s<br>1695 KiB |

### Test 2: Portal into Mythical Forest

> **Prompt**: a portal into a mythical forest on the wall of my small messy bedroom

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high |
| --- | --- | --- |
| ![MAI-Image-2.6, prompt 2, round 1](data/mai-vs-gpt25-20260920/mai-image-2.6/r1/02_test.png) | ![GPT-Image-2.5 Flare medium, prompt 2, round 1](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-medium/r1/02_test.png) | ![GPT-Image-2.5 Flare high, prompt 2, round 1](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-high/r1/02_test.png) |
| 36.52 s<br>1740 KiB | 20.86 s<br>1397 KiB | 30.36 s<br>1488 KiB |

| GPT-Image-2.5 Flare low<br>(2026-09-17) | GPT-Image-2.5 Flare xhigh<br>(2026-09-18) | GPT-Image-2.5 Flare max<br>(2026-09-18) | GPT-Image-2.5 Flare auto<br>(2026-09-18) |
| --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 2, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r1/02_test.png) | ![GPT-Image-2.5 Flare xhigh, prompt 2, round 1](data/gpt25-tiers-20260918/gpt-image-2.5-flare-xhigh/r1/02_test.png) | ![GPT-Image-2.5 Flare max, prompt 2, round 1](data/gpt25-tiers-20260918/gpt-image-2.5-flare-max/r1/02_test.png) | ![GPT-Image-2.5 Flare auto, prompt 2, round 1](data/gpt25-tiers-20260918/gpt-image-2.5-flare-auto/r1/02_test.png) |
| 20.45 s<br>1429 KiB | 36.59 s<br>1542 KiB | 73.53 s<br>1509 KiB | 20.00 s<br>1424 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high |
| --- | --- | --- |
| ![MAI-Image-2.6, prompt 2, round 2](data/mai-vs-gpt25-20260920/mai-image-2.6/r2/02_test.png) | ![GPT-Image-2.5 Flare medium, prompt 2, round 2](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-medium/r2/02_test.png) | ![GPT-Image-2.5 Flare high, prompt 2, round 2](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-high/r2/02_test.png) |
| 32.08 s<br>1723 KiB | 20.92 s<br>1570 KiB | 30.67 s<br>1446 KiB |

| GPT-Image-2.5 Flare low<br>(2026-09-17) | GPT-Image-2.5 Flare xhigh<br>(2026-09-18) | GPT-Image-2.5 Flare max<br>(2026-09-18) | GPT-Image-2.5 Flare auto<br>(2026-09-18) |
| --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 2, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r2/02_test.png) | ![GPT-Image-2.5 Flare xhigh, prompt 2, round 2](data/gpt25-tiers-20260918/gpt-image-2.5-flare-xhigh/r2/02_test.png) | ![GPT-Image-2.5 Flare max, prompt 2, round 2](data/gpt25-tiers-20260918/gpt-image-2.5-flare-max/r2/02_test.png) | ![GPT-Image-2.5 Flare auto, prompt 2, round 2](data/gpt25-tiers-20260918/gpt-image-2.5-flare-auto/r2/02_test.png) |
| 22.78 s<br>1401 KiB | 46.70 s<br>1535 KiB | 73.52 s<br>1330 KiB | 21.22 s<br>1515 KiB |

### Test 3: Tiny Astronaut on Moon

> **Prompt**: a tiny astronaut hatching from an egg on the moon

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high |
| --- | --- | --- |
| ![MAI-Image-2.6, prompt 3, round 1](data/mai-vs-gpt25-20260920/mai-image-2.6/r1/03_test.png) | ![GPT-Image-2.5 Flare medium, prompt 3, round 1](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-medium/r1/03_test.png) | ![GPT-Image-2.5 Flare high, prompt 3, round 1](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-high/r1/03_test.png) |
| 30.92 s<br>1593 KiB | 27.00 s<br>1531 KiB | 33.09 s<br>1482 KiB |

| GPT-Image-2.5 Flare low<br>(2026-09-17) | GPT-Image-2.5 Flare xhigh<br>(2026-09-18) | GPT-Image-2.5 Flare max<br>(2026-09-18) | GPT-Image-2.5 Flare auto<br>(2026-09-18) |
| --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 3, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r1/03_test.png) | ![GPT-Image-2.5 Flare xhigh, prompt 3, round 1](data/gpt25-tiers-20260918/gpt-image-2.5-flare-xhigh/r1/03_test.png) | ![GPT-Image-2.5 Flare max, prompt 3, round 1](data/gpt25-tiers-20260918/gpt-image-2.5-flare-max/r1/03_test.png) | ![GPT-Image-2.5 Flare auto, prompt 3, round 1](data/gpt25-tiers-20260918/gpt-image-2.5-flare-auto/r1/03_test.png) |
| 48.27 s<br>1596 KiB | 40.06 s<br>1517 KiB | 68.61 s<br>1402 KiB | 20.84 s<br>1498 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high |
| --- | --- | --- |
| ![MAI-Image-2.6, prompt 3, round 2](data/mai-vs-gpt25-20260920/mai-image-2.6/r2/03_test.png) | ![GPT-Image-2.5 Flare medium, prompt 3, round 2](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-medium/r2/03_test.png) | ![GPT-Image-2.5 Flare high, prompt 3, round 2](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-high/r2/03_test.png) |
| 29.44 s<br>1586 KiB | 22.24 s<br>1573 KiB | 33.76 s<br>1483 KiB |

| GPT-Image-2.5 Flare low<br>(2026-09-17) | GPT-Image-2.5 Flare xhigh<br>(2026-09-18) | GPT-Image-2.5 Flare max<br>(2026-09-18) | GPT-Image-2.5 Flare auto<br>(2026-09-18) |
| --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 3, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r2/03_test.png) | ![GPT-Image-2.5 Flare xhigh, prompt 3, round 2](data/gpt25-tiers-20260918/gpt-image-2.5-flare-xhigh/r2/03_test.png) | ![GPT-Image-2.5 Flare max, prompt 3, round 2](data/gpt25-tiers-20260918/gpt-image-2.5-flare-max/r2/03_test.png) | ![GPT-Image-2.5 Flare auto, prompt 3, round 2](data/gpt25-tiers-20260918/gpt-image-2.5-flare-auto/r2/03_test.png) |
| 20.04 s<br>1576 KiB | 45.34 s<br>1466 KiB | 77.89 s<br>1465 KiB | 22.10 s<br>1460 KiB |

### Test 4: LOTR Tiny Red Dragon

> **Prompt**: Photo realistic scene inspired by LOTR: [A tiny red dragon in a nest on a medieval wizard's table]. Shot with a macro lens (f/2.8, 50mm) and a Canon EOSR5, the soft focus captures [the cozy morning light filtering through a near by window]. The pastel colors and whimsical steam shapes enhance the serene atmosphere, evoking a DnD RPG setting. The image is rendered in 16K and 8K, highlighting [the intricate details and medieval charm].

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high |
| --- | --- | --- |
| ![MAI-Image-2.6, prompt 4, round 1](data/mai-vs-gpt25-20260920/mai-image-2.6/r1/04_test.png) | ![GPT-Image-2.5 Flare medium, prompt 4, round 1](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-medium/r1/04_test.png) | ![GPT-Image-2.5 Flare high, prompt 4, round 1](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-high/r1/04_test.png) |
| 48.47 s<br>1581 KiB | 21.39 s<br>1451 KiB | 31.54 s<br>1447 KiB |

| GPT-Image-2.5 Flare low<br>(2026-09-17) | GPT-Image-2.5 Flare xhigh<br>(2026-09-18) | GPT-Image-2.5 Flare max<br>(2026-09-18) | GPT-Image-2.5 Flare auto<br>(2026-09-18) |
| --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 4, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r1/04_test.png) | ![GPT-Image-2.5 Flare xhigh, prompt 4, round 1](data/gpt25-tiers-20260918/gpt-image-2.5-flare-xhigh/r1/04_test.png) | ![GPT-Image-2.5 Flare max, prompt 4, round 1](data/gpt25-tiers-20260918/gpt-image-2.5-flare-max/r1/04_test.png) | ![GPT-Image-2.5 Flare auto, prompt 4, round 1](data/gpt25-tiers-20260918/gpt-image-2.5-flare-auto/r1/04_test.png) |
| 22.31 s<br>1536 KiB | 36.94 s<br>1379 KiB | 63.49 s<br>1308 KiB | 19.95 s<br>1524 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high |
| --- | --- | --- |
| ![MAI-Image-2.6, prompt 4, round 2](data/mai-vs-gpt25-20260920/mai-image-2.6/r2/04_test.png) | ![GPT-Image-2.5 Flare medium, prompt 4, round 2](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-medium/r2/04_test.png) | ![GPT-Image-2.5 Flare high, prompt 4, round 2](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-high/r2/04_test.png) |
| 34.71 s<br>1622 KiB | 17.74 s<br>1405 KiB | 30.32 s<br>1363 KiB |

| GPT-Image-2.5 Flare low<br>(2026-09-17) | GPT-Image-2.5 Flare xhigh<br>(2026-09-18) | GPT-Image-2.5 Flare max<br>(2026-09-18) | GPT-Image-2.5 Flare auto<br>(2026-09-18) |
| --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 4, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r2/04_test.png) | ![GPT-Image-2.5 Flare xhigh, prompt 4, round 2](data/gpt25-tiers-20260918/gpt-image-2.5-flare-xhigh/r2/04_test.png) | ![GPT-Image-2.5 Flare max, prompt 4, round 2](data/gpt25-tiers-20260918/gpt-image-2.5-flare-max/r2/04_test.png) | ![GPT-Image-2.5 Flare auto, prompt 4, round 2](data/gpt25-tiers-20260918/gpt-image-2.5-flare-auto/r2/04_test.png) |
| 18.24 s<br>1381 KiB | 44.01 s<br>1449 KiB | 65.18 s<br>1409 KiB | 26.41 s<br>1333 KiB |

### Test 5: Fluffy Fantasy Creature

> **Prompt**: Cute and adorable fluffy cute creature fantasy, dreamlike, surrealism, super cute, trending on artstation

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high |
| --- | --- | --- |
| ![MAI-Image-2.6, prompt 5, round 1](data/mai-vs-gpt25-20260920/mai-image-2.6/r1/05_test.png) | ![GPT-Image-2.5 Flare medium, prompt 5, round 1](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-medium/r1/05_test.png) | ![GPT-Image-2.5 Flare high, prompt 5, round 1](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-high/r1/05_test.png) |
| 52.27 s<br>1651 KiB | 24.92 s<br>1613 KiB | 32.86 s<br>1669 KiB |

| GPT-Image-2.5 Flare low<br>(2026-09-17) | GPT-Image-2.5 Flare xhigh<br>(2026-09-18) | GPT-Image-2.5 Flare max<br>(2026-09-18) | GPT-Image-2.5 Flare auto<br>(2026-09-18) |
| --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 5, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r1/05_test.png) | ![GPT-Image-2.5 Flare xhigh, prompt 5, round 1](data/gpt25-tiers-20260918/gpt-image-2.5-flare-xhigh/r1/05_test.png) | ![GPT-Image-2.5 Flare max, prompt 5, round 1](data/gpt25-tiers-20260918/gpt-image-2.5-flare-max/r1/05_test.png) | ![GPT-Image-2.5 Flare auto, prompt 5, round 1](data/gpt25-tiers-20260918/gpt-image-2.5-flare-auto/r1/05_test.png) |
| 22.87 s<br>1484 KiB | 60.20 s<br>1597 KiB | 68.71 s<br>1512 KiB | 24.54 s<br>1545 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high |
| --- | --- | --- |
| ![MAI-Image-2.6, prompt 5, round 2](data/mai-vs-gpt25-20260920/mai-image-2.6/r2/05_test.png) | ![GPT-Image-2.5 Flare medium, prompt 5, round 2](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-medium/r2/05_test.png) | ![GPT-Image-2.5 Flare high, prompt 5, round 2](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-high/r2/05_test.png) |
| 33.10 s<br>1499 KiB | 21.48 s<br>1567 KiB | 33.54 s<br>1714 KiB |

| GPT-Image-2.5 Flare low<br>(2026-09-17) | GPT-Image-2.5 Flare xhigh<br>(2026-09-18) | GPT-Image-2.5 Flare max<br>(2026-09-18) | GPT-Image-2.5 Flare auto<br>(2026-09-18) |
| --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 5, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r2/05_test.png) | ![GPT-Image-2.5 Flare xhigh, prompt 5, round 2](data/gpt25-tiers-20260918/gpt-image-2.5-flare-xhigh/r2/05_test.png) | ![GPT-Image-2.5 Flare max, prompt 5, round 2](data/gpt25-tiers-20260918/gpt-image-2.5-flare-max/r2/05_test.png) | ![GPT-Image-2.5 Flare auto, prompt 5, round 2](data/gpt25-tiers-20260918/gpt-image-2.5-flare-auto/r2/05_test.png) |
| 26.37 s<br>1693 KiB | 43.51 s<br>1622 KiB | 70.75 s<br>1544 KiB | 23.13 s<br>1656 KiB |

### Test 6: Hidden Jungle Cenote

> **Prompt**: A hidden cenote in the heart of a lush jungle beckons with crystalline turquoise waters. Vibrant emerald vines cascade down weathered limestone walls, their tendrils barely kissing the water's surface. Shafts of golden sunlight pierce through a natural skylight above, creating a mystical interplay of light and shadow on the cavern walls. Iridescent butterflies flit between exotic orchids clinging to rocky outcrops. A partially submerged Mayan ruin, its intricate carvings softened by time, stand

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high |
| --- | --- | --- |
| ![MAI-Image-2.6, prompt 6, round 1](data/mai-vs-gpt25-20260920/mai-image-2.6/r1/06_test.png) | ![GPT-Image-2.5 Flare medium, prompt 6, round 1](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-medium/r1/06_test.png) | ![GPT-Image-2.5 Flare high, prompt 6, round 1](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-high/r1/06_test.png) |
| 30.25 s<br>2116 KiB | 23.38 s<br>2179 KiB | 36.32 s<br>2224 KiB |

| GPT-Image-2.5 Flare low<br>(2026-09-17) | GPT-Image-2.5 Flare xhigh<br>(2026-09-18) | GPT-Image-2.5 Flare max<br>(2026-09-18) | GPT-Image-2.5 Flare auto<br>(2026-09-18) |
| --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 6, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r1/06_test.png) | ![GPT-Image-2.5 Flare xhigh, prompt 6, round 1](data/gpt25-tiers-20260918/gpt-image-2.5-flare-xhigh/r1/06_test.png) | ![GPT-Image-2.5 Flare max, prompt 6, round 1](data/gpt25-tiers-20260918/gpt-image-2.5-flare-max/r1/06_test.png) | ![GPT-Image-2.5 Flare auto, prompt 6, round 1](data/gpt25-tiers-20260918/gpt-image-2.5-flare-auto/r1/06_test.png) |
| 20.62 s<br>2095 KiB | 42.70 s<br>2127 KiB | 71.24 s<br>2091 KiB | 22.84 s<br>2127 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high |
| --- | --- | --- |
| ![MAI-Image-2.6, prompt 6, round 2](data/mai-vs-gpt25-20260920/mai-image-2.6/r2/06_test.png) | ![GPT-Image-2.5 Flare medium, prompt 6, round 2](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-medium/r2/06_test.png) | ![GPT-Image-2.5 Flare high, prompt 6, round 2](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-high/r2/06_test.png) |
| 30.44 s<br>2205 KiB | 27.87 s<br>2142 KiB | 32.69 s<br>2263 KiB |

| GPT-Image-2.5 Flare low<br>(2026-09-17) | GPT-Image-2.5 Flare xhigh<br>(2026-09-18) | GPT-Image-2.5 Flare max<br>(2026-09-18) | GPT-Image-2.5 Flare auto<br>(2026-09-18) |
| --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 6, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r2/06_test.png) | ![GPT-Image-2.5 Flare xhigh, prompt 6, round 2](data/gpt25-tiers-20260918/gpt-image-2.5-flare-xhigh/r2/06_test.png) | ![GPT-Image-2.5 Flare max, prompt 6, round 2](data/gpt25-tiers-20260918/gpt-image-2.5-flare-max/r2/06_test.png) | ![GPT-Image-2.5 Flare auto, prompt 6, round 2](data/gpt25-tiers-20260918/gpt-image-2.5-flare-auto/r2/06_test.png) |
| 24.02 s<br>2151 KiB | 43.28 s<br>2147 KiB | 74.58 s<br>2131 KiB | 25.91 s<br>2156 KiB |

### Test 7: Tech-Savvy Girl with Holographic UI

> **Prompt**: A charming, tech-savvy [girl with short, silver pixie-cut] hair and vibrant [blue] eyes, wearing a casual yet futuristic outfit. She's focused on a holographic interface while working in a sleek, high-tech workshop.

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high |
| --- | --- | --- |
| ![MAI-Image-2.6, prompt 7, round 1](data/mai-vs-gpt25-20260920/mai-image-2.6/r1/07_test.png) | ![GPT-Image-2.5 Flare medium, prompt 7, round 1](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-medium/r1/07_test.png) | ![GPT-Image-2.5 Flare high, prompt 7, round 1](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-high/r1/07_test.png) |
| 35.10 s<br>1555 KiB | 24.40 s<br>1487 KiB | 35.81 s<br>1494 KiB |

| GPT-Image-2.5 Flare low<br>(2026-09-17) | GPT-Image-2.5 Flare xhigh<br>(2026-09-18) | GPT-Image-2.5 Flare max<br>(2026-09-18) | GPT-Image-2.5 Flare auto<br>(2026-09-18) |
| --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 7, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r1/07_test.png) | ![GPT-Image-2.5 Flare xhigh, prompt 7, round 1](data/gpt25-tiers-20260918/gpt-image-2.5-flare-xhigh/r1/07_test.png) | ![GPT-Image-2.5 Flare max, prompt 7, round 1](data/gpt25-tiers-20260918/gpt-image-2.5-flare-max/r1/07_test.png) | ![GPT-Image-2.5 Flare auto, prompt 7, round 1](data/gpt25-tiers-20260918/gpt-image-2.5-flare-auto/r1/07_test.png) |
| 24.69 s<br>1587 KiB | 47.53 s<br>1555 KiB | 76.86 s<br>1472 KiB | 29.02 s<br>1534 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high |
| --- | --- | --- |
| ![MAI-Image-2.6, prompt 7, round 2](data/mai-vs-gpt25-20260920/mai-image-2.6/r2/07_test.png) | ![GPT-Image-2.5 Flare medium, prompt 7, round 2](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-medium/r2/07_test.png) | ![GPT-Image-2.5 Flare high, prompt 7, round 2](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-high/r2/07_test.png) |
| 35.41 s<br>1534 KiB | 39.28 s<br>1548 KiB | 35.26 s<br>1525 KiB |

| GPT-Image-2.5 Flare low<br>(2026-09-17) | GPT-Image-2.5 Flare xhigh<br>(2026-09-18) | GPT-Image-2.5 Flare max<br>(2026-09-18) | GPT-Image-2.5 Flare auto<br>(2026-09-18) |
| --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 7, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r2/07_test.png) | ![GPT-Image-2.5 Flare xhigh, prompt 7, round 2](data/gpt25-tiers-20260918/gpt-image-2.5-flare-xhigh/r2/07_test.png) | ![GPT-Image-2.5 Flare max, prompt 7, round 2](data/gpt25-tiers-20260918/gpt-image-2.5-flare-max/r2/07_test.png) | ![GPT-Image-2.5 Flare auto, prompt 7, round 2](data/gpt25-tiers-20260918/gpt-image-2.5-flare-auto/r2/07_test.png) |
| 23.76 s<br>1542 KiB | 57.35 s<br>1521 KiB | 79.60 s<br>1472 KiB | 30.29 s<br>1533 KiB |

### Test 8: Universe Fractal Worlds

> **Prompt**: Universe, LSD, Fractal Worlds, Giant Eyes

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high |
| --- | --- | --- |
| ![MAI-Image-2.6, prompt 8, round 1](data/mai-vs-gpt25-20260920/mai-image-2.6/r1/08_test.png) | ![GPT-Image-2.5 Flare medium, prompt 8, round 1](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-medium/r1/08_test.png) | ![GPT-Image-2.5 Flare high, prompt 8, round 1](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-high/r1/08_test.png) |
| 40.90 s<br>2298 KiB | 22.24 s<br>2288 KiB | 32.68 s<br>2283 KiB |

| GPT-Image-2.5 Flare low<br>(2026-09-17) | GPT-Image-2.5 Flare xhigh<br>(2026-09-18) | GPT-Image-2.5 Flare max<br>(2026-09-18) | GPT-Image-2.5 Flare auto<br>(2026-09-18) |
| --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 8, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r1/08_test.png) | ![GPT-Image-2.5 Flare xhigh, prompt 8, round 1](data/gpt25-tiers-20260918/gpt-image-2.5-flare-xhigh/r1/08_test.png) | ![GPT-Image-2.5 Flare max, prompt 8, round 1](data/gpt25-tiers-20260918/gpt-image-2.5-flare-max/r1/08_test.png) | ![GPT-Image-2.5 Flare auto, prompt 8, round 1](data/gpt25-tiers-20260918/gpt-image-2.5-flare-auto/r1/08_test.png) |
| 21.65 s<br>2262 KiB | 41.24 s<br>2254 KiB | 79.96 s<br>2206 KiB | 24.28 s<br>2230 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high |
| --- | --- | --- |
| ![MAI-Image-2.6, prompt 8, round 2](data/mai-vs-gpt25-20260920/mai-image-2.6/r2/08_test.png) | ![GPT-Image-2.5 Flare medium, prompt 8, round 2](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-medium/r2/08_test.png) | ![GPT-Image-2.5 Flare high, prompt 8, round 2](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-high/r2/08_test.png) |
| 31.14 s<br>2310 KiB | 22.63 s<br>2339 KiB | 29.75 s<br>2216 KiB |

| GPT-Image-2.5 Flare low<br>(2026-09-17) | GPT-Image-2.5 Flare xhigh<br>(2026-09-18) | GPT-Image-2.5 Flare max<br>(2026-09-18) | GPT-Image-2.5 Flare auto<br>(2026-09-18) |
| --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 8, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r2/08_test.png) | ![GPT-Image-2.5 Flare xhigh, prompt 8, round 2](data/gpt25-tiers-20260918/gpt-image-2.5-flare-xhigh/r2/08_test.png) | ![GPT-Image-2.5 Flare max, prompt 8, round 2](data/gpt25-tiers-20260918/gpt-image-2.5-flare-max/r2/08_test.png) | ![GPT-Image-2.5 Flare auto, prompt 8, round 2](data/gpt25-tiers-20260918/gpt-image-2.5-flare-auto/r2/08_test.png) |
| 25.37 s<br>2217 KiB | 44.08 s<br>2187 KiB | 75.92 s<br>2162 KiB | 40.38 s<br>2322 KiB |

### Test 9: Fractal Mythical Creature

> **Prompt**: close up dof render of a mythical creature made of detailed spiraling fractals and tendrils, detailed recursive skin texture

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high |
| --- | --- | --- |
| ![MAI-Image-2.6, prompt 9, round 1](data/mai-vs-gpt25-20260920/mai-image-2.6/r1/09_test.png) | ![GPT-Image-2.5 Flare medium, prompt 9, round 1](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-medium/r1/09_test.png) | ![GPT-Image-2.5 Flare high, prompt 9, round 1](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-high/r1/09_test.png) |
| 31.08 s<br>1693 KiB | 20.36 s<br>1747 KiB | 29.97 s<br>1676 KiB |

| GPT-Image-2.5 Flare low<br>(2026-09-17) | GPT-Image-2.5 Flare xhigh<br>(2026-09-18) | GPT-Image-2.5 Flare max<br>(2026-09-18) | GPT-Image-2.5 Flare auto<br>(2026-09-18) |
| --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 9, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r1/09_test.png) | ![GPT-Image-2.5 Flare xhigh, prompt 9, round 1](data/gpt25-tiers-20260918/gpt-image-2.5-flare-xhigh/r1/09_test.png) | ![GPT-Image-2.5 Flare max, prompt 9, round 1](data/gpt25-tiers-20260918/gpt-image-2.5-flare-max/r1/09_test.png) | ![GPT-Image-2.5 Flare auto, prompt 9, round 1](data/gpt25-tiers-20260918/gpt-image-2.5-flare-auto/r1/09_test.png) |
| 21.77 s<br>1581 KiB | 47.98 s<br>1734 KiB | 72.54 s<br>1575 KiB | 22.40 s<br>1769 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high |
| --- | --- | --- |
| ![MAI-Image-2.6, prompt 9, round 2](data/mai-vs-gpt25-20260920/mai-image-2.6/r2/09_test.png) | ![GPT-Image-2.5 Flare medium, prompt 9, round 2](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-medium/r2/09_test.png) | ![GPT-Image-2.5 Flare high, prompt 9, round 2](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-high/r2/09_test.png) |
| 30.97 s<br>1729 KiB | 19.52 s<br>1852 KiB | 35.19 s<br>1605 KiB |

| GPT-Image-2.5 Flare low<br>(2026-09-17) | GPT-Image-2.5 Flare xhigh<br>(2026-09-18) | GPT-Image-2.5 Flare max<br>(2026-09-18) | GPT-Image-2.5 Flare auto<br>(2026-09-18) |
| --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 9, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r2/09_test.png) | ![GPT-Image-2.5 Flare xhigh, prompt 9, round 2](data/gpt25-tiers-20260918/gpt-image-2.5-flare-xhigh/r2/09_test.png) | ![GPT-Image-2.5 Flare max, prompt 9, round 2](data/gpt25-tiers-20260918/gpt-image-2.5-flare-max/r2/09_test.png) | ![GPT-Image-2.5 Flare auto, prompt 9, round 2](data/gpt25-tiers-20260918/gpt-image-2.5-flare-auto/r2/09_test.png) |
| 16.93 s<br>1761 KiB | 41.72 s<br>1502 KiB | 77.44 s<br>1597 KiB | 27.98 s<br>1696 KiB |

### Test 10: Angry Cat Playing Drums

> **Prompt**: an angry cat playing drums

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high |
| --- | --- | --- |
| ![MAI-Image-2.6, prompt 10, round 1](data/mai-vs-gpt25-20260920/mai-image-2.6/r1/10_test.png) | ![GPT-Image-2.5 Flare medium, prompt 10, round 1](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-medium/r1/10_test.png) | ![GPT-Image-2.5 Flare high, prompt 10, round 1](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-high/r1/10_test.png) |
| 30.62 s<br>1655 KiB | 24.75 s<br>1458 KiB | 29.98 s<br>1440 KiB |

| GPT-Image-2.5 Flare low<br>(2026-09-17) | GPT-Image-2.5 Flare xhigh<br>(2026-09-18) | GPT-Image-2.5 Flare max<br>(2026-09-18) | GPT-Image-2.5 Flare auto<br>(2026-09-18) |
| --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 10, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r1/10_test.png) | ![GPT-Image-2.5 Flare xhigh, prompt 10, round 1](data/gpt25-tiers-20260918/gpt-image-2.5-flare-xhigh/r1/10_test.png) | ![GPT-Image-2.5 Flare max, prompt 10, round 1](data/gpt25-tiers-20260918/gpt-image-2.5-flare-max/r1/10_test.png) | ![GPT-Image-2.5 Flare auto, prompt 10, round 1](data/gpt25-tiers-20260918/gpt-image-2.5-flare-auto/r1/10_test.png) |
| 19.46 s<br>1587 KiB | 43.69 s<br>1392 KiB | 62.97 s<br>1371 KiB | 19.49 s<br>1563 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high |
| --- | --- | --- |
| ![MAI-Image-2.6, prompt 10, round 2](data/mai-vs-gpt25-20260920/mai-image-2.6/r2/10_test.png) | ![GPT-Image-2.5 Flare medium, prompt 10, round 2](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-medium/r2/10_test.png) | ![GPT-Image-2.5 Flare high, prompt 10, round 2](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-high/r2/10_test.png) |
| 32.59 s<br>1673 KiB | 20.83 s<br>1478 KiB | 28.20 s<br>1377 KiB |

| GPT-Image-2.5 Flare low<br>(2026-09-17) | GPT-Image-2.5 Flare xhigh<br>(2026-09-18) | GPT-Image-2.5 Flare max<br>(2026-09-18) | GPT-Image-2.5 Flare auto<br>(2026-09-18) |
| --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 10, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r2/10_test.png) | ![GPT-Image-2.5 Flare xhigh, prompt 10, round 2](data/gpt25-tiers-20260918/gpt-image-2.5-flare-xhigh/r2/10_test.png) | ![GPT-Image-2.5 Flare max, prompt 10, round 2](data/gpt25-tiers-20260918/gpt-image-2.5-flare-max/r2/10_test.png) | ![GPT-Image-2.5 Flare auto, prompt 10, round 2](data/gpt25-tiers-20260918/gpt-image-2.5-flare-auto/r2/10_test.png) |
| 24.01 s<br>1482 KiB | 46.16 s<br>1388 KiB | 74.30 s<br>1403 KiB | 21.49 s<br>1496 KiB |

### Test 11: Monkey Playing Music

> **Prompt**: A monkey playing music

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high |
| --- | --- | --- |
| ![MAI-Image-2.6, prompt 11, round 1](data/mai-vs-gpt25-20260920/mai-image-2.6/r1/11_test.png) | ![GPT-Image-2.5 Flare medium, prompt 11, round 1](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-medium/r1/11_test.png) | ![GPT-Image-2.5 Flare high, prompt 11, round 1](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-high/r1/11_test.png) |
| 28.70 s<br>1796 KiB | 44.42 s<br>1626 KiB | 29.81 s<br>1631 KiB |

| GPT-Image-2.5 Flare low<br>(2026-09-17) | GPT-Image-2.5 Flare xhigh<br>(2026-09-18) | GPT-Image-2.5 Flare max<br>(2026-09-18) | GPT-Image-2.5 Flare auto<br>(2026-09-18) |
| --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 11, round 1](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r1/11_test.png) | ![GPT-Image-2.5 Flare xhigh, prompt 11, round 1](data/gpt25-tiers-20260918/gpt-image-2.5-flare-xhigh/r1/11_test.png) | ![GPT-Image-2.5 Flare max, prompt 11, round 1](data/gpt25-tiers-20260918/gpt-image-2.5-flare-max/r1/11_test.png) | ![GPT-Image-2.5 Flare auto, prompt 11, round 1](data/gpt25-tiers-20260918/gpt-image-2.5-flare-auto/r1/11_test.png) |
| 20.30 s<br>1682 KiB | 43.26 s<br>1467 KiB | 76.03 s<br>1433 KiB | 20.47 s<br>1629 KiB |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high |
| --- | --- | --- |
| ![MAI-Image-2.6, prompt 11, round 2](data/mai-vs-gpt25-20260920/mai-image-2.6/r2/11_test.png) | ![GPT-Image-2.5 Flare medium, prompt 11, round 2](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-medium/r2/11_test.png) | ![GPT-Image-2.5 Flare high, prompt 11, round 2](data/mai-vs-gpt25-20260920/gpt-image-2.5-flare-high/r2/11_test.png) |
| 30.08 s<br>1717 KiB | 21.21 s<br>1619 KiB | 33.07 s<br>1501 KiB |

| GPT-Image-2.5 Flare low<br>(2026-09-17) | GPT-Image-2.5 Flare xhigh<br>(2026-09-18) | GPT-Image-2.5 Flare max<br>(2026-09-18) | GPT-Image-2.5 Flare auto<br>(2026-09-18) |
| --- | --- | --- | --- |
| ![GPT-Image-2.5 Flare low, prompt 11, round 2](data/gpt25-paired-20260917/gpt-image-2.5-flare-low/r2/11_test.png) | ![GPT-Image-2.5 Flare xhigh, prompt 11, round 2](data/gpt25-tiers-20260918/gpt-image-2.5-flare-xhigh/r2/11_test.png) | ![GPT-Image-2.5 Flare max, prompt 11, round 2](data/gpt25-tiers-20260918/gpt-image-2.5-flare-max/r2/11_test.png) | ![GPT-Image-2.5 Flare auto, prompt 11, round 2](data/gpt25-tiers-20260918/gpt-image-2.5-flare-auto/r2/11_test.png) |
| 17.81 s<br>1624 KiB | 39.73 s<br>1556 KiB | 65.76 s<br>1538 KiB | 20.74 s<br>1601 KiB |

### Test 12: Headwear Swap (Image Edit)

The first eleven scenarios are pure text-to-image. Scenario 12 switches to image editing: the same real photograph goes to each of the 3 configurations' edit endpoints with a prompt that asks for exactly one change and lists what must stay the same, so every output can be checked item by item without an aesthetic score. As in the first eleven scenarios it runs 2 rounds, with the configuration order reversed in round 2.

The input is one 553x311 JPEG photograph (39,539 bytes, SHA-256 `2f15a826dbc5d0e9…`): a foreground figure in a crown and embroidered robe, spear-bearing guards on the left, a purple-robed figure and gallery on the right, and a title with a seal in the top-left.

**Prompt (verbatim)**

> Replace only the headwear worn by the man in the foreground with a black academic graduation cap with a tassel. Keep his face, beard, expression and pose exactly as they are. Keep his embroidered robe, the courtyard and every other person unchanged.

**Controlled variables**

MAI uses `/mai/v1/images/edits` and GPT uses `/openai/deployments/gpt-image-2.5-flare/images/edits`. The GPT tiers differ only in `quality` and pass `size=auto`, so the service chooses the output dimensions; the MAI edit endpoint has no size parameter and the service likewise chooses. Both sides are therefore under the same contract: neither was told to produce a fixed size. Each configuration was called once per round over 2 rounds, on one account, in one region, in one session per round.

| Input photograph |
| --- |
| ![Input photograph](data/edit-hat-swap-gpt25-20260921/input.jpg) |

**Round 1:**

| MAI-Image-2.6 | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high |
| --- | --- | --- |
| ![MAI-Image-2.6, edit round 1](data/edit-hat-swap-gpt25-20260921/01_mai-image-2.6.png) | ![GPT-Image-2.5 Flare medium, edit round 1](data/edit-hat-swap-gpt25-20260921/02_gpt-image-2.5-flare-medium.png) | ![GPT-Image-2.5 Flare high, edit round 1](data/edit-hat-swap-gpt25-20260921/03_gpt-image-2.5-flare-high.png) |
| 24.77 s<br>1611 KiB<br>1360x768 | 25.64 s<br>2394 KiB<br>1674x940 | 30.23 s<br>2186 KiB<br>1674x940 |

| Checklist | MAI-Image-2.6 | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high |
| --- | --- | --- | --- |
| Preservation items kept | 5/5 | 5/5 | 5/5 |
| Headwear became a graduation cap | yes | yes | yes |
| Face and beard preserved | yes | yes | yes |
| Robe embroidery preserved | yes | yes | yes |
| Bystanders and background unchanged | yes | yes | yes |
| Title and seal preserved | yes | yes | yes |
| Input aspect ratio kept | yes | yes | yes |

| Configuration | Observation |
| --- | --- |
| MAI-Image-2.6 | The crown becomes a black graduation cap with a tassel. Face, beard, expression, robe embroidery, the spear-bearing guards on the left, the purple-robed figure on the right and the gallery are all in place; colour and framing are almost identical to the input, and the output keeps 16:9 (1360×768). The title and seal sit in the top-left; THE ADVISORS ALLIANCE reads letter-for-letter with slightly softened strokes, and the four Chinese characters are distorted. |
| GPT-Image-2.5 Flare medium | Graduation cap present. Subject, robe, guard column, the purple-robed figure and the architecture are all in place; output 1674×940, same aspect ratio as the input, with the colours slightly re-rendered. The title and seal are in place, but the Latin title reads THE ASVISORS ALLIANCE (ADVISORS misspelled) and the four Chinese characters are distorted. |
| GPT-Image-2.5 Flare high | Graduation cap present with its tassel. Subject, robe, guards, right-side figures and architecture all in place; output 1674×940. THE ADVISORS ALLIANCE is reproduced letter-for-letter, the four Chinese characters are distorted, and the seal is in place. |

**Round 2:**

| MAI-Image-2.6 | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high |
| --- | --- | --- |
| ![MAI-Image-2.6, edit round 2](data/edit-hat-swap-gpt25-20260921/r2/03_mai-image-2.6.png) | ![GPT-Image-2.5 Flare medium, edit round 2](data/edit-hat-swap-gpt25-20260921/r2/02_gpt-image-2.5-flare-medium.png) | ![GPT-Image-2.5 Flare high, edit round 2](data/edit-hat-swap-gpt25-20260921/r2/01_gpt-image-2.5-flare-high.png) |
| 39.62 s<br>1581 KiB<br>1360x768 | 29.70 s<br>2401 KiB<br>1674x940 | 29.55 s<br>2206 KiB<br>1674x940 |

| Checklist | MAI-Image-2.6 | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high |
| --- | --- | --- | --- |
| Preservation items kept | 5/5 | 5/5 | 5/5 |
| Headwear became a graduation cap | yes | yes | yes |
| Face and beard preserved | yes | yes | yes |
| Robe embroidery preserved | yes | yes | yes |
| Bystanders and background unchanged | yes | yes | yes |
| Title and seal preserved | yes | yes | yes |
| Input aspect ratio kept | yes | yes | yes |

| Configuration | Observation |
| --- | --- |
| MAI-Image-2.6 | Graduation cap present. Face, beard, robe, guards, right-side figures and architecture all in place; colour and framing almost identical to the input; output 1360×768. The Latin title reads letter-for-letter with softened strokes, the four Chinese characters are distorted, and the seal is in place. |
| GPT-Image-2.5 Flare medium | Graduation cap present. Subject, robe, guards, right-side figures and architecture all in place; output 1674×940. The title and seal are in place, but the Latin title reads THE ASVISORS followed by an unreadable third word (ALLIANCE rewritten), and the four Chinese characters are distorted; this is the largest title departure among the six outputs. |
| GPT-Image-2.5 Flare high | Graduation cap present. Subject, robe, guards, right-side figures and architecture all in place; output 1674×940. The Latin title is reproduced letter-for-letter, the four Chinese characters are distorted, and the seal is in place. |

| Across rounds | MAI-Image-2.6 | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high |
| --- | --- | --- | --- |
| Items kept (per round) | 5/5 / 5/5 | 5/5 / 5/5 | 5/5 / 5/5 |
| Latency per round | 24.77 s / 39.62 s | 25.64 s / 29.70 s | 30.23 s / 29.55 s |

**How to read this**: All three configurations produced the graduation cap in both rounds and kept every one of the five preservation items — face, robe, bystanders and background, title and seal, input aspect ratio — so all six outputs score 5/5. Three differences remain. Fidelity: the two MAI outputs match the input in colour and framing almost exactly and read as a repaint of the head only; the 2.5 outputs are whole-frame regenerations that keep composition and identity but re-render textures and colours. Title glyphs: 2.5 high reproduces THE ADVISORS ALLIANCE letter-for-letter in both rounds; 2.5 medium writes ADVISORS as ASVISORS in both rounds and in round 2 rewrites ALLIANCE into an unreadable word; MAI keeps the Latin text legible in both rounds with softened strokes. No configuration preserves the shapes of the four Chinese characters 軍師聯盟. Output resolution: 2.5 chose 1674×940 (about 1.57 MP) while MAI returned 1360×768 (1.04 MP, the endpoint's 1,048,576-pixel ceiling). Latency: MAI 24.8 / 39.6 s, 2.5 medium 25.6 / 29.7 s, 2.5 high 30.2 / 29.6 s. The prompt asked to preserve the input, and on the five-item checklist the six outputs do not differ; title glyph fidelity is outside the checklist and is reported as an observation only.

2 rounds with one call per configuration per round; two rounds show whether the outcome repeats and are not a statistical sample. Observations are unblinded and describe departures from the input, not image quality. Every output is a regeneration: 'preserved' means present, in place and recognisable, not pixel-identical. Latency is client-side `requests.post` round-trip time. No output PNG carries an alpha channel.

[Request records round 1](data/edit-hat-swap-gpt25-20260921/edit-results.json) | [Per-image checklist round 1](data/edit-hat-swap-gpt25-20260921/edit-review.json) | [Request records round 2](data/edit-hat-swap-gpt25-20260921/r2/edit-results.json) | [Per-image checklist round 2](data/edit-hat-swap-gpt25-20260921/r2/edit-review.json) | [Title-corner contact sheet](data/edit-hat-swap-gpt25-20260921/review-compact.png) | [Public reproduction runner](scripts/run_edit_hat_swap.py)

## Same-Session Run: MAI-Image-2.6 vs GPT-Image-2.5

[Side-by-side images](#side-by-side-image-comparison) | [Measurements](data/mai-vs-gpt25-20260920/5way_v2_results.json) | [Metrics](data/mai-vs-gpt25-20260920/summary.json) | [Attempts](data/mai-vs-gpt25-20260920/attempts.jsonl)

**This run returned images for 66/66 formal samples; 0 returned no image; the 3 warmups are excluded from the denominator.** The three configurations were called alternately by one client in one region, so latency differences are directly comparable; image quality has no numeric score, see the side-by-side images.

### Test Contract

| Configuration | Model version | Quality field | Dimensions | Resource region | Formal samples | Measured on |
| --- | --- | --- | --- | --- | --- | --- |
| MAI-Image-2.6 | 2026-07-31 | omitted | 1024x1024 | swedencentral | 22 | 2026-09-20 |
| GPT-Image-2.5 Flare medium | 2026-09-08 | medium | 1024x1024 | swedencentral | 22 | 2026-09-20 |
| GPT-Image-2.5 Flare high | 2026-09-08 | high | 1024x1024 | swedencentral | 22 | 2026-09-20 |

The input is the same eleven-prompt CSV. Each configuration receives one `blue circle` warmup; round 1 calls MAI-Image-2.6, GPT-Image-2.5 Flare medium, GPT-Image-2.5 Flare high in that order for every prompt, round 2 reverses it. Concurrency is 1 with 5 seconds after each logical call, at most 3 attempts with backoff. Both deployments are GlobalStandard at 2 requests per minute; to stay inside that quota the client starts at most 2 requests per 60 seconds per deployment, recording the wait per sample as `pacing_wait_seconds`, excluded from request latency. Request timeouts are 180 seconds for MAI and 900 for GPT.

Client: Windows-11-10.0.26200-SP0, ARM64, Python 3.13.15, requests 2.34.2. Formal interval (UTC): `2026-09-20T04:12:52.043132+00:00` – `2026-09-20T04:51:44.018032+00:00`.

```mermaid
flowchart LR
    prompts["Original 11 prompts"] --> runner["Local Windows Python runner"]
    runner --> mai["MAI-Image-2.6 / swedencentral"]
    runner --> gpt["GPT-Image-2.5 flare / swedencentral / medium, high"]
    mai --> evidence["PNG, usage, request IDs, timestamps, failures"]
    gpt --> evidence
    evidence --> summary["Offline validation and report"]
```

### Performance and Reliability

| Metric | MAI-Image-2.6 | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high |
| --- | --- | --- | --- |
| Successful / planned samples | 22 / 22 | 22 / 22 | 22 / 22 |
| First-attempt successes / planned | 22 / 22 | 22 / 22 | 22 / 22 |
| HTTP attempts / 429 responses | 22 / 0 | 22 / 0 | 22 / 0 |
| Mean request latency (s) | 34.66 | 24.24 | 32.03 |
| P50 / descriptive P95 (s) | 31.61 / 48.38 | 22.24 / 38.71 | 32.11 / 35.78 |
| Sample standard deviation (s) | 6.57 | 6.25 | 2.35 |
| Minimum / maximum request latency (s) | 28.70 / 52.27 | 17.74 / 44.42 | 28.20 / 36.32 |
| Round 1 / round 2 mean (s) | 37.41 / 31.91 | 24.93 / 23.55 | 32.17 / 31.90 |
| Mean logical duration, all samples (s) | 34.71 | 24.29 | 32.09 |
| Returned output tokens | 1024 | 439 | 1756 |
| Mean successful PNG size (KiB) | 1,755 | 1,699 | 1,673 |

Request latency measures `requests.post` through receipt of the complete HTTP response, for successful image-producing attempts only, before JSON/base64 processing and file writes. Logical duration includes failed attempts, retry waits and response processing across all planned samples. Failures are not averaged as zero-second responses or removed from the success-rate denominator. P95 is descriptive linear interpolation over at most 22 observations per group, not a production tail guarantee. Token counts come from returned usage; neither output tokens nor PNG size establishes image quality on its own.

### Exceptions and Waiting

No unsuccessful attempts were recorded.

### Every Scenario, Both Rounds

Seconds; failed cells remain tied to their original requests and are not replaced by another round.

| Scenario / round | MAI-Image-2.6 | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high |
| --- | --- | --- | --- |
| 01 / R1 | 46.69 | 20.50 | 31.45 |
| 01 / R2 | 31.04 | 25.36 | 28.44 |
| 02 / R1 | 36.52 | 20.86 | 30.36 |
| 02 / R2 | 32.08 | 20.92 | 30.67 |
| 03 / R1 | 30.92 | 27.00 | 33.09 |
| 03 / R2 | 29.44 | 22.24 | 33.76 |
| 04 / R1 | 48.47 | 21.39 | 31.54 |
| 04 / R2 | 34.71 | 17.74 | 30.32 |
| 05 / R1 | 52.27 | 24.92 | 32.86 |
| 05 / R2 | 33.10 | 21.48 | 33.54 |
| 06 / R1 | 30.25 | 23.38 | 36.32 |
| 06 / R2 | 30.44 | 27.87 | 32.69 |
| 07 / R1 | 35.10 | 24.40 | 35.81 |
| 07 / R2 | 35.41 | 39.28 | 35.26 |
| 08 / R1 | 40.90 | 22.24 | 32.68 |
| 08 / R2 | 31.14 | 22.63 | 29.75 |
| 09 / R1 | 31.08 | 20.36 | 29.97 |
| 09 / R2 | 30.97 | 19.52 | 35.19 |
| 10 / R1 | 30.62 | 24.75 | 29.98 |
| 10 / R2 | 32.59 | 20.83 | 28.20 |
| 11 / R1 | 28.70 | 44.42 | 29.81 |
| 11 / R2 | 30.08 | 21.21 | 33.07 |

### Measured API Settings

| API item | MAI-Image-2.6 | GPT-Image-2.5 |
| --- | --- | --- |
| POST | `/mai/v1/images/generations` | `/openai/deployments/{deployment}/images/generations?api-version=2025-04-01-preview` |
| Payload | `model`, `prompt`, `width=1024`, `height=1024` | `prompt`, `n=1`, `size=1024x1024`, `quality=<tier>` |
| Auth | `api-key` | `api-key` |
| Output | `data[0].b64_json`, PNG | `data[0].b64_json`, PNG |
| Usage | `usage.num_input_text_tokens`, `usage.num_output_tokens` | `usage.input_tokens_details`, `usage.output_tokens_details` |

### Reproduction and Tests

<a id="reproduction-how-to"></a>

Every data directory maps to one step below: step 4 makes no model calls, the rest consume Azure usage. All runners, summarizers and the judge live in `scripts/`; reproduction uses the same code that produced this report.

### 1. Clone and install dependencies

JSON and CSV in this repository are stored with Git LFS; fetch them before validating anything.

```powershell
git clone https://github.com/david-xinyuwei/david-share.git
cd david-share/Multimodal-Models/MAI-Image-2-vs-GPT-Image-Benchmark
git lfs pull --include "Multimodal-Models/MAI-Image-2-vs-GPT-Image-Benchmark/**"
python -m pip install requests pillow
```

### 2. Configure your deployments

One MAI-Image-2.6 deployment and the GPT-Image-2.5 deployments you want to measure, on accounts you control. Verify the underlying model versions; deployment names alone are not model identity. Supply `AZURE_API_KEY` (MAI) and `AZURE_OPENAI_API_KEY` (GPT) through your own secret management, never source control. The metadata variables must state your verified deployments; the values below describe ours.

```powershell
$env:MAI_ENDPOINT = 'https://<your-mai-resource>.services.ai.azure.com'
$env:GPT_ENDPOINT = 'https://<your-openai-resource>.openai.azure.com'
$env:MAI_MODEL_VERSION = '2026-07-31'
$env:GPT_MODEL_VERSIONS = '{"gpt-image-2.5-flare": "2026-09-08", "gpt-image-2.5-sunburst": "2026-09-08"}'
$env:MAI_DEPLOYMENT_REGION = 'swedencentral'
$env:GPT_DEPLOYMENT_REGION = 'swedencentral'
$env:MAI_DEPLOYMENT_SKU = 'GlobalStandard'
$env:GPT_DEPLOYMENT_SKU = 'GlobalStandard'
$env:MAI_RATE_LIMIT_RPM = '2.0'
$env:GPT_RATE_LIMIT_RPM = '2.0'
$env:BENCHMARK_CLIENT_LOCATION = 'Describe your actual client location'
python scripts/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --gpt-model gpt-image-2.5-flare:medium,high --dry-run
```

### 3. Rerun the same-session comparison

The primary run: MAI and 2.5 flare medium and high interleaved on the eleven prompts. `--gpt-model` accepts `deployment:tier,tier`. The first command runs one warmup per configuration; the second continues the same output directory through the formal matrix. Existing results are never overwritten and recorded samples are not rerun. Save the script and CSV into the run before starting and keep them unchanged during execution.

```powershell
python scripts/summarize_paired_run.py data/mai-vs-gpt25-20260920
$run = 'runs/mai-vs-gpt25-new-run'
New-Item -ItemType Directory -Path "$run/source" -ErrorAction Stop
Copy-Item -LiteralPath scripts/benchmark_5way_v2.py -Destination "$run/source/benchmark_5way_v2.py"
Copy-Item -LiteralPath prompts.csv -Destination "$run/source/prompts.csv"
python -u scripts/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --gpt-model gpt-image-2.5-flare:medium,high --output $run --warmup-only
python -u scripts/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --gpt-model gpt-image-2.5-flare:medium,high --output $run --resume
python scripts/summarize_paired_run.py $run
```

### 4. Verify published evidence without model calls

Recomputes every archive from its raw records and confirms both READMEs match; regressions cover request contracts, failure denominators, image ownership, the scoring rule, the invoice derivation and report coverage. HTTP mocks exist only in offline tests.

```powershell
python scripts/render_paired_report.py data/mai-vs-gpt25-20260920 --check
python -m unittest discover -s tests -v
```

### 5. Rerun the web-grounding comparison

Needs only the MAI deployment. The first command verifies the archive; the second checks parameters offline; the third reruns all three subjects into a new directory.

```powershell
python scripts/summarize_web_grounding.py data/lenovo-web-grounding-20260908 --require-complete --check
python data/lenovo-web-grounding-20260908/source/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --mai-web-grounding both --prompts-csv data/lenovo-web-grounding-20260908/source/prompts.csv --output runs/web-grounding-reproduction --dry-run
python data/lenovo-web-grounding-20260908/source/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --mai-web-grounding both --prompts-csv data/lenovo-web-grounding-20260908/source/prompts.csv --output runs/web-grounding-reproduction
```

### 6. Rerun the headwear-swap image edit

Set `GPT_DEPLOYMENT` to the 2.5 deployment (`gpt-image-2.5-flare` here) and name the tiers with `--gpt-quality`. The first command verifies the published outputs; the second is a credential-free dry run; the next two perform the live rounds; the last checks order, `size=auto` and hashes. The per-image checklist is a manual review under the published method, not generated automatically.

```powershell
python scripts/summarize_edit_hat_swap.py data/edit-hat-swap-gpt25-20260921 --check
$env:GPT_DEPLOYMENT = 'gpt-image-2.5-flare'
$out = 'runs/edit-hat-swap-reproduction'
python scripts/run_edit_hat_swap.py --input data/edit-hat-swap-gpt25-20260921/input.jpg --output $out --round 1 --gpt-size auto --gpt-quality medium --gpt-quality high --dry-run
python scripts/run_edit_hat_swap.py --input data/edit-hat-swap-gpt25-20260921/input.jpg --output $out --round 1 --gpt-size auto --gpt-quality medium --gpt-quality high
python scripts/run_edit_hat_swap.py --input data/edit-hat-swap-gpt25-20260921/input.jpg --output $out --round 2 --gpt-size auto --gpt-quality medium --gpt-quality high
python scripts/run_edit_hat_swap.py --output $out --check
```

### 7. Rerun GPT-Image-2.5 low/medium/high on both deployments

`--gpt-model` may be repeated; `--gpt-quality all` expands to low, medium and high. The client starts at most 2 requests per 60 seconds per deployment to match the 2 RPM quota; raise `RATE_PACING` if yours is higher.

```powershell
python scripts/summarize_paired_run.py data/gpt25-paired-20260917
$run = 'runs/gpt25-paired-new-run'
New-Item -ItemType Directory -Path "$run/source" -ErrorAction Stop
Copy-Item -LiteralPath scripts/benchmark_5way_v2.py -Destination "$run/source/benchmark_5way_v2.py"
Copy-Item -LiteralPath prompts.csv -Destination "$run/source/prompts.csv"
python -u scripts/benchmark_5way_v2.py --gpt-model gpt-image-2.5-flare --gpt-model gpt-image-2.5-sunburst --gpt-quality all --output $run --warmup-only
python -u scripts/benchmark_5way_v2.py --gpt-model gpt-image-2.5-flare --gpt-model gpt-image-2.5-sunburst --gpt-quality all --output $run --resume
```

### 8. Rerun xhigh/max/auto

Only gpt-image-2.5-* accepts these tiers. A single max request measured 229 s, so the runner's request timeout is 900 s. `auto` lets the service choose per request; the tier it used is recorded per attempt as `service_quality`.

```powershell
python scripts/summarize_paired_run.py data/gpt25-tiers-20260918
$run = 'runs/gpt25-tiers-new-run'
New-Item -ItemType Directory -Path "$run/source" -ErrorAction Stop
Copy-Item -LiteralPath scripts/benchmark_5way_v2.py -Destination "$run/source/benchmark_5way_v2.py"
Copy-Item -LiteralPath prompts.csv -Destination "$run/source/prompts.csv"
python -u scripts/benchmark_5way_v2.py --gpt-model gpt-image-2.5-flare --gpt-model gpt-image-2.5-sunburst --gpt-quality xhigh --gpt-quality max --gpt-quality auto --output $run --warmup-only
python -u scripts/benchmark_5way_v2.py --gpt-model gpt-image-2.5-flare --gpt-model gpt-image-2.5-sunburst --gpt-quality xhigh --gpt-quality max --gpt-quality auto --output $run --resume
```

### 9. Rerun text rendering and score it

Text rendering uses its own prompt file (`--prompts-csv`); the runner reads only the first column. Each deployment has its own quota, so shards run per deployment and are merged at scoring with repeated `--run`; the scorer refuses shards whose frozen prompt file differs. Scoring needs a vision-capable chat deployment via `JUDGE_ENDPOINT`, `JUDGE_DEPLOYMENT` and `AZURE_OPENAI_API_KEY`; calibrate it first, or its errors will be attributed to the image models. `--check` recomputes every score from saved transcriptions with no model calls.

```powershell
python scripts/score_text_rendering.py --check data/text-rendering-20260918/text-scoring.json
python scripts/score_text_rendering.py --check data/text-hard-20260919/text-scoring.json
python scripts/calibrate_text_judge.py --check data/text-rendering-20260918/judge-calibration/calibration.json
python scripts/calibrate_text_judge.py --check data/text-hard-20260919/judge-calibration/calibration.json
$env:JUDGE_ENDPOINT = 'https://<openai-resource>.openai.azure.com'
$env:JUDGE_DEPLOYMENT = '<vision-capable-chat-deployment>'
python scripts/calibrate_text_judge.py --prompts data/text-rendering-20260918/prompts-text-rendering.csv --out runs/judge-calibration
$run = 'runs/text-new-run-mai'
New-Item -ItemType Directory -Path "$run/source" -ErrorAction Stop
Copy-Item -LiteralPath scripts/benchmark_5way_v2.py -Destination "$run/source/benchmark_5way_v2.py"
Copy-Item -LiteralPath data/text-rendering-20260918/prompts-text-rendering.csv -Destination "$run/source/prompts-text-rendering.csv"
python -u scripts/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --prompts-csv "$run/source/prompts-text-rendering.csv" --output $run
python scripts/score_text_rendering.py --run $run --prompts data/text-rendering-20260918/prompts-text-rendering.csv --out runs/text-new-run-scored
```

### 10. Recompute cost per image from your own invoice

The first command recomputes `effective-prices.json` from the archived Cost Management response, offline. The second issues the same query against your own account (needs `az login`; the query is free) and writes a new archive; re-rendering then reads your invoice instead of ours.

```powershell
python scripts/effective_prices.py data/billing-20260920 --check
python scripts/effective_prices.py data/billing-<date> --query --subscription <id> --resource-group <rg> --account <cognitive-services-account>
```

Scripts: [benchmark_5way_v2.py](scripts/benchmark_5way_v2.py) · [run_edit_hat_swap.py](scripts/run_edit_hat_swap.py) · [summarize_paired_run.py](scripts/summarize_paired_run.py) · [summarize_edit_hat_swap.py](scripts/summarize_edit_hat_swap.py) · [score_text_rendering.py](scripts/score_text_rendering.py) · [calibrate_text_judge.py](scripts/calibrate_text_judge.py) · [effective_prices.py](scripts/effective_prices.py) · [render_paired_report.py](scripts/render_paired_report.py) · [tests](tests).

### Limits

This report compares only MAI-Image-2.6 with GPT-Image-2.5 (the flare and sunburst deployments at low, medium, high, xhigh, max, auto). The latency and side-by-side spine comes from one session; the remaining tiers come from sessions on two other dates and carry their dates in the headers. MAI sends no quality parameter and is not labeled as equivalent to any GPT tier. The eleven scenarios carry no per-image prose review; image quality is for the reader to judge from the side-by-side images, and exact-text accuracy covers only the scenes and characters listed in the two text-rendering sections. Not covered: 2K, multiple reference images, concurrency capacity or other authentication modes. Earlier versions of this report compared GPT-Image-2; those archives remain as evidence ([data/paired-all-quality-20260907](data/paired-all-quality-20260907), [data/mai-image-2.6-20260907](data/mai-image-2.6-20260907), [data/edit-hat-swap-20260908](data/edit-hat-swap-20260908), [data/edit-hat-swap-20260909-auto](data/edit-hat-swap-20260909-auto)) and feed no table.

Evidence directory: [data/mai-vs-gpt25-20260920](data/mai-vs-gpt25-20260920). Original images, measurement records, attempts, response metadata and the source snapshot that ran; prompt SHA-256: `be3d628c66a1e4d535d06bcc84246a04aad11f35a48f3133d451fe86283782ce`.

## The Six GPT-Image-2.5 Quality Tiers

`gpt-image-2.5-flare` and `gpt-image-2.5-sunburst` accept six quality tiers. low, medium and high come from the 2026-09-17 run and xhigh, max and auto from the 2026-09-18 run, both using the same client, prompt file and deployments in swedencentral. When a tier is requested explicitly its output-token count is constant and identical across the two deployments; `auto` behaves differently, as noted below the table. Neither run is the same session as the previous section, so compare latencies across sections together with their dates.

| Configuration | Successful / planned | Returned output tokens | Mean latency (s) | P50 (s) | Descriptive P95 (s) | Mean PNG (KiB) |
| --- | --- | --- | --- | --- | --- | --- |
| GPT-Image-2.5 Flare low | 22 / 22 | 196 | 22.79 | 21.85 | 26.32 | 1,675 |
| GPT-Image-2.5 Flare medium | 22 / 22 | 439 | 24.05 | 23.64 | 28.82 | 1,687 |
| GPT-Image-2.5 Flare high | 22 / 22 | 1756 | 33.79 | 32.64 | 39.89 | 1,679 |
| GPT-Image-2.5 Flare xhigh | 22 / 22 | 3122 | 44.33 | 43.40 | 56.88 | 1,654 |
| GPT-Image-2.5 Flare max | 22 / 22 | 7024 | 72.23 | 73.47 | 79.51 | 1,602 |
| GPT-Image-2.5 Flare auto | 22 / 22 | 196–781 (low x12, medium x10 [439/781]) | 23.84 | 22.25 | 30.22 | 1,680 |
| GPT-Image-2.5 Sunburst low | 22 / 22 | 196 | 33.19 | 32.54 | 42.49 | 1,678 |
| GPT-Image-2.5 Sunburst medium | 22 / 22 | 439 | 41.58 | 40.64 | 48.71 | 1,724 |
| GPT-Image-2.5 Sunburst high | 22 / 22 | 1756 | 77.14 | 76.08 | 83.81 | 1,681 |
| GPT-Image-2.5 Sunburst xhigh | 22 / 22 | 3122 | 112.68 | 111.55 | 120.37 | 1,681 |
| GPT-Image-2.5 Sunburst max | 22 / 22 | 7024 | 223.41 | 223.51 | 229.90 | 1,671 |
| GPT-Image-2.5 Sunburst auto | 22 / 22 | 196–781 (low x12, medium x10 [439/781]) | 37.28 | 33.74 | 52.61 | 1,675 |

`auto` is not a fixed tier. The service chooses per request and echoes the tier it used; the `auto` rows list, in parentheses, the tiers the service reported and how often, taken from the response field. Moreover, when `auto` reports a tier, the returned output-token count is not necessarily the fixed value that tier returns when requested explicitly: this run produced 781, while every explicitly requested tier returned one constant across all 22 of its samples. `auto` is therefore not equivalent to selecting that tier, and its cost cannot be derived from the tier it reports. Their latency and token figures therefore describe the service's selection behaviour, not one quality level.

Evidence directories: [data/gpt25-paired-20260917](data/gpt25-paired-20260917), [data/gpt25-tiers-20260918](data/gpt25-tiers-20260918).

## Actual Cost per Image, from This Account's Invoice

**Question**: is MAI-Image-2.6 expensive? The answer depends on which 2.5 quality tier it is compared against, and the tiers differ by 36x in billed compute.

**Source**: an Azure Cost Management ActualCost query against the account that ran every test in this repository (Sweden Central), period 2026-09-04..2026-09-20, field `PreTaxCost`. Each model's output-image tokens are metered separately; dividing cost by billed tokens gives the effective rate. On the same invoice gpt-image-2 bills at exactly its published $30 per 1M tokens, which confirms the reading; GPT-Image-2.5 has no published price yet, so the invoice is the only official figure.

| Model | Billed USD per 1M output-image tokens |
| --- | --- |
| gpt-image-2 | $30.00 |
| gpt-image-2.5-flare | $30.00 |
| gpt-image-2.5-sunburst | $30.00 |
| MAI-Image-2.6 | $38.00 |

| Configuration | Tokens / image | USD / 1,000 images | vs MAI |
| --- | --- | --- | --- |
| gpt-image-2.5 low | 196 | $5.88 | 0.15x |
| gpt-image-2.5 medium | 439 | $13.17 | 0.34x |
| MAI-Image-2.6 **(MAI)** | 1,024 | $38.91 | 1.00x |
| gpt-image-2.5 high | 1,756 | $52.68 | 1.35x |
| gpt-image-2.5 xhigh | 3,122 | $93.66 | 2.41x |
| gpt-image-2.5 max | 7,024 | $210.72 | 5.42x |

**How to read this**: per token, MAI costs 27% more than 2.5 ($38 vs $30). But MAI is a constant 1,024 tokens per image while 2.5 compute varies by tier. MAI therefore costs $38.91 per 1,000 images: 6.6x 2.5 low ($5.88), 3.0x medium ($13.17), 26% less than high ($52.68) and 82% less than max ($210.72). "Expensive" is meaningless until the comparison tier is named; which tier matches MAI in quality is answered by the side-by-side images, not by price.

**Boundary**: rates are this account's GlobalStandard pay-as-you-go actuals with no negotiated discount; token counts are the measured constants each configuration returned across every run here, and `auto` is omitted because its tokens are not constant; input text tokens (under $0.001 per image) are excluded. This is cost per token, not cost per unit of quality.

Evidence: [data/billing-20260920](data/billing-20260920) (raw Cost Management response; `scripts/effective_prices.py --check` recomputes it offline).

## Chinese and English Text Rendering

**Question**: for the same scene, with only the language of the required text changed, how much does the share of correctly rendered characters differ?

**Actual input**: 5 scenes, each written in English and Chinese, identical apart from the text to be rendered. The two P1 prompts, verbatim:

> A photograph of a small bakery storefront at dusk. The sign above the door reads exactly "GOLDEN CRUST".
>
> 黄昏时一家小面包店的门面照片，门上方的招牌上准确写着"金麦坊"。

Denominators are fixed per round: 79 English characters and 34 Chinese characters. Chinese expresses the same content in fewer characters, so each language is scored against its own denominator and the two are never pooled.

| Pair | Scene | English target | Chinese target |
| --- | --- | --- | --- |
| P1 | storefront sign | `GOLDEN CRUST` | `金麦坊` |
| P2 | product label | `JASMINE GREEN TEA` | `茉莉绿茶` |
| P3 | poster headline | `ANNUAL DESIGN SUMMIT 2026` | `2026年度设计峰会` |
| P4 | handwritten note | `Meeting at 3 PM` | `下午三点开会` |
| P5 | multi-line menu | `COFFEE 25 / TEA 18 / CAKE 32` | `咖啡 25 / 茶 18 / 蛋糕 32` |

**Controlled variables**: one client, one account, one region (Sweden Central), the same GlobalStandard quota, 1024x1024, two rounds. Within a pair, only the language of the text changes.

| Configuration | English character accuracy | English exact segments | Chinese character accuracy | Chinese exact segments |
| --- | --- | --- | --- | --- |
| GPT-Image-2.5 Flare high | 158/158 = 100% | 14/14 = 100% | 68/68 = 100% | 14/14 = 100% |
| GPT-Image-2.5 Flare max | 158/158 = 100% | 14/14 = 100% | 67/68 = 99% | 13/14 = 93% |
| GPT-Image-2.5 Sunburst high | 158/158 = 100% | 14/14 = 100% | 67/68 = 99% | 13/14 = 93% |
| GPT-Image-2.5 Sunburst max | 158/158 = 100% | 14/14 = 100% | 68/68 = 100% | 14/14 = 100% |
| MAI-Image-2.6 | 158/158 = 100% | 14/14 = 100% | 68/68 = 100% | 14/14 = 100% |

**Actual outputs**

One table per scene: columns are configurations (MAI and each GPT-Image-2.5 Flare tier; sunburst images are in the evidence directory), rows are the English and Chinese versions, with both rounds' character scores and what the judge read under each image. Round 1 is shown by default; when only round 2 missed, round 2 is shown and marked (r2). Click an image for the original.

**P1 — storefront sign**: `GOLDEN CRUST` / `金麦坊`

| Language | MAI-Image-2.6 | GPT-Image-2.5 Flare high | GPT-Image-2.5 Flare max |
| --- | --- | --- | --- |
| English | ![mai-image-2.6 P1 en round 1](data/text-rendering-20260918/mai/mai-image-2.6/r1/01_test.png) | ![gpt-image-2.5-flare-high P1 en round 1](data/text-rendering-20260918/gpt-image-2.5-flare/gpt-image-2.5-flare-high/r1/01_test.png) | ![gpt-image-2.5-flare-max P1 en round 1](data/text-rendering-20260918/gpt-image-2.5-flare/gpt-image-2.5-flare-max/r1/01_test.png) |
|  | r1 11/11 · r2 11/11<br>exact | r1 11/11 · r2 11/11<br>exact | r1 11/11 · r2 11/11<br>exact |
| Chinese | ![mai-image-2.6 P1 zh round 1](data/text-rendering-20260918/mai/mai-image-2.6/r1/02_test.png) | ![gpt-image-2.5-flare-high P1 zh round 1](data/text-rendering-20260918/gpt-image-2.5-flare/gpt-image-2.5-flare-high/r1/02_test.png) | ![gpt-image-2.5-flare-max P1 zh round 1](data/text-rendering-20260918/gpt-image-2.5-flare/gpt-image-2.5-flare-max/r1/02_test.png) |
|  | r1 3/3 · r2 3/3<br>exact | r1 3/3 · r2 3/3<br>exact | r1 3/3 · r2 3/3<br>exact |

**P2 — product label**: `JASMINE GREEN TEA` / `茉莉绿茶`

| Language | MAI-Image-2.6 | GPT-Image-2.5 Flare high | GPT-Image-2.5 Flare max |
| --- | --- | --- | --- |
| English | ![mai-image-2.6 P2 en round 1](data/text-rendering-20260918/mai/mai-image-2.6/r1/03_test.png) | ![gpt-image-2.5-flare-high P2 en round 1](data/text-rendering-20260918/gpt-image-2.5-flare/gpt-image-2.5-flare-high/r1/03_test.png) | ![gpt-image-2.5-flare-max P2 en round 1](data/text-rendering-20260918/gpt-image-2.5-flare/gpt-image-2.5-flare-max/r1/03_test.png) |
|  | r1 15/15 · r2 15/15<br>exact | r1 15/15 · r2 15/15<br>exact | r1 15/15 · r2 15/15<br>exact |
| Chinese | ![mai-image-2.6 P2 zh round 1](data/text-rendering-20260918/mai/mai-image-2.6/r1/04_test.png) | ![gpt-image-2.5-flare-high P2 zh round 1](data/text-rendering-20260918/gpt-image-2.5-flare/gpt-image-2.5-flare-high/r1/04_test.png) | ![gpt-image-2.5-flare-max P2 zh round 2](data/text-rendering-20260918/gpt-image-2.5-flare/gpt-image-2.5-flare-max/r2/04_test.png) |
|  | r1 4/4 · r2 4/4<br>exact | r1 4/4 · r2 4/4<br>exact | r1 4/4 · r2 3/4<br>read `茉莉綠茶` (r2) |

**P3 — poster headline**: `ANNUAL DESIGN SUMMIT 2026` / `2026年度设计峰会`

| Language | MAI-Image-2.6 | GPT-Image-2.5 Flare high | GPT-Image-2.5 Flare max |
| --- | --- | --- | --- |
| English | ![mai-image-2.6 P3 en round 1](data/text-rendering-20260918/mai/mai-image-2.6/r1/05_test.png) | ![gpt-image-2.5-flare-high P3 en round 1](data/text-rendering-20260918/gpt-image-2.5-flare/gpt-image-2.5-flare-high/r1/05_test.png) | ![gpt-image-2.5-flare-max P3 en round 1](data/text-rendering-20260918/gpt-image-2.5-flare/gpt-image-2.5-flare-max/r1/05_test.png) |
|  | r1 22/22 · r2 22/22<br>exact | r1 22/22 · r2 22/22<br>exact | r1 22/22 · r2 22/22<br>exact |
| Chinese | ![mai-image-2.6 P3 zh round 1](data/text-rendering-20260918/mai/mai-image-2.6/r1/06_test.png) | ![gpt-image-2.5-flare-high P3 zh round 1](data/text-rendering-20260918/gpt-image-2.5-flare/gpt-image-2.5-flare-high/r1/06_test.png) | ![gpt-image-2.5-flare-max P3 zh round 1](data/text-rendering-20260918/gpt-image-2.5-flare/gpt-image-2.5-flare-max/r1/06_test.png) |
|  | r1 10/10 · r2 10/10<br>exact | r1 10/10 · r2 10/10<br>exact | r1 10/10 · r2 10/10<br>exact |

**P4 — handwritten note**: `Meeting at 3 PM` / `下午三点开会`

| Language | MAI-Image-2.6 | GPT-Image-2.5 Flare high | GPT-Image-2.5 Flare max |
| --- | --- | --- | --- |
| English | ![mai-image-2.6 P4 en round 1](data/text-rendering-20260918/mai/mai-image-2.6/r1/07_test.png) | ![gpt-image-2.5-flare-high P4 en round 1](data/text-rendering-20260918/gpt-image-2.5-flare/gpt-image-2.5-flare-high/r1/07_test.png) | ![gpt-image-2.5-flare-max P4 en round 1](data/text-rendering-20260918/gpt-image-2.5-flare/gpt-image-2.5-flare-max/r1/07_test.png) |
|  | r1 12/12 · r2 12/12<br>exact | r1 12/12 · r2 12/12<br>exact | r1 12/12 · r2 12/12<br>exact |
| Chinese | ![mai-image-2.6 P4 zh round 1](data/text-rendering-20260918/mai/mai-image-2.6/r1/08_test.png) | ![gpt-image-2.5-flare-high P4 zh round 1](data/text-rendering-20260918/gpt-image-2.5-flare/gpt-image-2.5-flare-high/r1/08_test.png) | ![gpt-image-2.5-flare-max P4 zh round 1](data/text-rendering-20260918/gpt-image-2.5-flare/gpt-image-2.5-flare-max/r1/08_test.png) |
|  | r1 6/6 · r2 6/6<br>exact | r1 6/6 · r2 6/6<br>exact | r1 6/6 · r2 6/6<br>exact |

**P5 — multi-line menu**: `COFFEE 25 / TEA 18 / CAKE 32` / `咖啡 25 / 茶 18 / 蛋糕 32`

| Language | MAI-Image-2.6 | GPT-Image-2.5 Flare high | GPT-Image-2.5 Flare max |
| --- | --- | --- | --- |
| English | ![mai-image-2.6 P5 en round 1](data/text-rendering-20260918/mai/mai-image-2.6/r1/09_test.png) | ![gpt-image-2.5-flare-high P5 en round 1](data/text-rendering-20260918/gpt-image-2.5-flare/gpt-image-2.5-flare-high/r1/09_test.png) | ![gpt-image-2.5-flare-max P5 en round 1](data/text-rendering-20260918/gpt-image-2.5-flare/gpt-image-2.5-flare-max/r1/09_test.png) |
|  | r1 19/19 · r2 19/19<br>exact | r1 19/19 · r2 19/19<br>exact | r1 19/19 · r2 19/19<br>exact |
| Chinese | ![mai-image-2.6 P5 zh round 1](data/text-rendering-20260918/mai/mai-image-2.6/r1/10_test.png) | ![gpt-image-2.5-flare-high P5 zh round 1](data/text-rendering-20260918/gpt-image-2.5-flare/gpt-image-2.5-flare-high/r1/10_test.png) | ![gpt-image-2.5-flare-max P5 zh round 1](data/text-rendering-20260918/gpt-image-2.5-flare/gpt-image-2.5-flare-max/r1/10_test.png) |
|  | r1 11/11 · r2 11/11<br>exact | r1 11/11 · r2 11/11<br>exact | r1 11/11 · r2 11/11<br>exact |

**How it was judged**: each image is transcribed by `gpt-5.6-terra` and compared with the target string programmatically, ignoring all whitespace. Two denominators are reported: character accuracy scores the best-matching window of equal length anywhere in the transcription, character by character; exact segments requires the target to appear verbatim as a substring, with no partial credit. This is model-judged, not a blind human study. The judge is an OpenAI-family model and some of the judged images come from OpenAI image models; the calibration below rules out an inability to read Chinese, not a lenience toward one vendor's style, which is why every image is shown below for human review.

**Scoring correction**: the first pass matched each target against a **single transcribed line**. The judge emits one line per visual text block, so a model that wrapped a phrase onto two lines was scored as misspelling it; the penalty grew with target length, and the English targets are two to four times longer than the Chinese ones, so English was systematically understated. The corrected rule ignores whitespace and matches anywhere in the transcription; the first-pass scores are kept as [`text-scoring-line-anchored.json`](data/text-rendering-20260918/text-scoring-line-anchored.json).

**The judge's own error floor**: rendering this section's targets with Microsoft YaHei and asking the judge to read them back scores 79/79 (100.0%) for English and 34/34 (100.0%) for Chinese under the same scoring rule as the table. The judge therefore has no systematic bias against these characters, and the gaps above are attributable to the image models. Boundary: this only establishes that the judge reads clean horizontal renders; distorted, stylised or vertical text in generated images is harder, so the table may understate accuracy and will not overstate it. The renders and transcriptions are in [judge-calibration](data/text-rendering-20260918/judge-calibration) and `calibrate_text_judge.py --check` recomputes them offline.

**Boundary**: 100 successful samples across 5 scenes, 2 rounds and 5 configurations. This measures spelling accuracy for a specified string, not typographic quality, font choice or design appeal. MAI-Image-2.6 takes no quality parameter and therefore has a single row. **Declared support**: the Foundry model documentation lists MAI-Image-2.6 Languages as `en`; Chinese is outside its declared scope. The Chinese results here are observed behaviour outside that scope, not a product commitment, and should not be cited as a supported capability.

Evidence directory: [data/text-rendering-20260918](data/text-rendering-20260918) (per-group contact sheets in `review/`). Prompt SHA-256: `51585dcf118fec7b6164eea9fc1115cfd44718035f82c4e9a2252fb45ee4d3a4`.

## Chinese and English Text Rendering: Hard Set

**Question**: the short targets in the previous section scored near 100% for every model and had no discriminating power. With scenes built around known Chinese failure modes (long strings, simplified-vs-traditional traps, digits mixed with script, vertical layout, multi-line, handwriting) and every tier of both 2.5 deployments measured, where do gaps appear?

**Actual input**: 6 scenes, each written in English and Chinese, identical apart from the text to be rendered. The two H1 prompts, verbatim:

> A bookstore banner photo. The banner reads exactly "READING LIGHTS THE ROAD AHEAD".
>
> 书店横幅照片，横幅上准确写着"阅读照亮前行的道路"。

Denominators are fixed per round: 131 English characters and 43 Chinese characters. Chinese expresses the same content in fewer characters, so each language is scored against its own denominator and the two are never pooled.

| Pair | Scene | Tests | English target | Chinese target |
| --- | --- | --- | --- | --- |
| H1 | bookstore banner | long string | `READING LIGHTS THE ROAD AHEAD` | `阅读照亮前行的道路` |
| H2 | tea packaging | simplified vs traditional | `GREEN TEA FROM YUNNAN CLOUDS` | `云南绿茶发源地` |
| H3 | street plaque | digits mixed with script | `EAST GATE No. 18 THIRD FLOOR` | `东门大街18号三楼` |
| H4 | calligraphy scroll | vertical layout | `STILL WATERS RUN DEEP` | `宁静致远` |
| H5 | conference badge | multi-line | `ZHANG WEI / SENIOR ARCHITECT` | `张伟 / 高级架构师` |
| H6 | handwritten whiteboard | handwriting | `SHIP IT BY FRIDAY NOON` | `周五中午前发布` |

**Controlled variables**: one client, one account, one region (Sweden Central), the same GlobalStandard quota, 1024x1024, two rounds. Within a pair, only the language of the text changes.

| Configuration | English character accuracy | English exact segments | Chinese character accuracy | Chinese exact segments |
| --- | --- | --- | --- | --- |
| GPT-Image-2.5 Flare auto | 262/262 = 100% | 14/14 = 100% | 85/86 = 99% | 13/14 = 93% |
| GPT-Image-2.5 Flare high | 262/262 = 100% | 14/14 = 100% | 86/86 = 100% | 14/14 = 100% |
| GPT-Image-2.5 Flare low | 262/262 = 100% | 14/14 = 100% | 86/86 = 100% | 14/14 = 100% |
| GPT-Image-2.5 Flare max | 237/239 = 99% | 12/13 = 92% | 82/82 = 100% | 13/13 = 100% |
| GPT-Image-2.5 Flare medium | 262/262 = 100% | 14/14 = 100% | 86/86 = 100% | 14/14 = 100% |
| GPT-Image-2.5 Flare xhigh | 260/262 = 99% | 13/14 = 93% | 86/86 = 100% | 14/14 = 100% |
| GPT-Image-2.5 Sunburst auto | 262/262 = 100% | 14/14 = 100% | 86/86 = 100% | 14/14 = 100% |
| GPT-Image-2.5 Sunburst high | 262/262 = 100% | 14/14 = 100% | 86/86 = 100% | 14/14 = 100% |
| GPT-Image-2.5 Sunburst low | 262/262 = 100% | 14/14 = 100% | 86/86 = 100% | 14/14 = 100% |
| GPT-Image-2.5 Sunburst max | 262/262 = 100% | 14/14 = 100% | 86/86 = 100% | 14/14 = 100% |
| GPT-Image-2.5 Sunburst medium | 262/262 = 100% | 14/14 = 100% | 86/86 = 100% | 14/14 = 100% |
| GPT-Image-2.5 Sunburst xhigh | 262/262 = 100% | 14/14 = 100% | 86/86 = 100% | 14/14 = 100% |
| MAI-Image-2.6 | 262/262 = 100% | 14/14 = 100% | 86/86 = 100% | 14/14 = 100% |

**Actual outputs**

One table per scene: columns are configurations (MAI and each GPT-Image-2.5 Flare tier; sunburst images are in the evidence directory), rows are the English and Chinese versions, with both rounds' character scores and what the judge read under each image. Round 1 is shown by default; when only round 2 missed, round 2 is shown and marked (r2). Click an image for the original.

**H1 — bookstore banner**: `READING LIGHTS THE ROAD AHEAD` / `阅读照亮前行的道路`

| Language | MAI-Image-2.6 | GPT-Image-2.5 Flare low | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high | GPT-Image-2.5 Flare xhigh | GPT-Image-2.5 Flare max | GPT-Image-2.5 Flare auto |
| --- | --- | --- | --- | --- | --- | --- | --- |
| English | ![mai-image-2.6 H1 en round 1](data/text-hard-20260919/first-mai/mai-image-2.6/r1/01_test.png) | ![gpt-image-2.5-flare-low H1 en round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-low/r1/01_test.png) | ![gpt-image-2.5-flare-medium H1 en round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-medium/r1/01_test.png) | ![gpt-image-2.5-flare-high H1 en round 1](data/text-hard-20260919/first-gpt-image-2.5-flare/gpt-image-2.5-flare-high/r1/01_test.png) | ![gpt-image-2.5-flare-xhigh H1 en round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-xhigh/r1/01_test.png) | ![gpt-image-2.5-flare-max H1 en round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-max/r1/01_test.png) | ![gpt-image-2.5-flare-auto H1 en round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-auto/r1/01_test.png) |
|  | r1 25/25 · r2 25/25<br>exact | r1 25/25 · r2 25/25<br>exact | r1 25/25 · r2 25/25<br>exact | r1 25/25 · r2 25/25<br>exact | r1 25/25 · r2 25/25<br>exact | r1 25/25 · r2 25/25<br>exact | r1 25/25 · r2 25/25<br>exact |
| Chinese | ![mai-image-2.6 H1 zh round 1](data/text-hard-20260919/first-mai/mai-image-2.6/r1/02_test.png) | ![gpt-image-2.5-flare-low H1 zh round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-low/r1/02_test.png) | ![gpt-image-2.5-flare-medium H1 zh round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-medium/r1/02_test.png) | ![gpt-image-2.5-flare-high H1 zh round 1](data/text-hard-20260919/first-gpt-image-2.5-flare/gpt-image-2.5-flare-high/r1/02_test.png) | ![gpt-image-2.5-flare-xhigh H1 zh round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-xhigh/r1/02_test.png) | ![gpt-image-2.5-flare-max H1 zh round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-max/r1/02_test.png) | ![gpt-image-2.5-flare-auto H1 zh round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-auto/r1/02_test.png) |
|  | r1 9/9 · r2 9/9<br>exact | r1 9/9 · r2 9/9<br>exact | r1 9/9 · r2 9/9<br>exact | r1 9/9 · r2 9/9<br>exact | r1 9/9 · r2 9/9<br>exact | r1 9/9 · r2 9/9<br>exact | r1 9/9 · r2 9/9<br>exact |

**H2 — tea packaging**: `GREEN TEA FROM YUNNAN CLOUDS` / `云南绿茶发源地`

| Language | MAI-Image-2.6 | GPT-Image-2.5 Flare low | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high | GPT-Image-2.5 Flare xhigh | GPT-Image-2.5 Flare max | GPT-Image-2.5 Flare auto |
| --- | --- | --- | --- | --- | --- | --- | --- |
| English | ![mai-image-2.6 H2 en round 1](data/text-hard-20260919/first-mai/mai-image-2.6/r1/03_test.png) | ![gpt-image-2.5-flare-low H2 en round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-low/r1/03_test.png) | ![gpt-image-2.5-flare-medium H2 en round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-medium/r1/03_test.png) | ![gpt-image-2.5-flare-high H2 en round 1](data/text-hard-20260919/first-gpt-image-2.5-flare/gpt-image-2.5-flare-high/r1/03_test.png) | ![gpt-image-2.5-flare-xhigh H2 en round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-xhigh/r1/03_test.png) | ![gpt-image-2.5-flare-max H2 en round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-max/r1/03_test.png) | ![gpt-image-2.5-flare-auto H2 en round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-auto/r1/03_test.png) |
|  | r1 24/24 · r2 24/24<br>exact | r1 24/24 · r2 24/24<br>exact | r1 24/24 · r2 24/24<br>exact | r1 24/24 · r2 24/24<br>exact | r1 24/24 · r2 24/24<br>exact | r1 24/24 · r2 24/24<br>exact | r1 24/24 · r2 24/24<br>exact |
| Chinese | ![mai-image-2.6 H2 zh round 1](data/text-hard-20260919/first-mai/mai-image-2.6/r1/04_test.png) | ![gpt-image-2.5-flare-low H2 zh round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-low/r1/04_test.png) | ![gpt-image-2.5-flare-medium H2 zh round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-medium/r1/04_test.png) | ![gpt-image-2.5-flare-high H2 zh round 1](data/text-hard-20260919/first-gpt-image-2.5-flare/gpt-image-2.5-flare-high/r1/04_test.png) | ![gpt-image-2.5-flare-xhigh H2 zh round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-xhigh/r1/04_test.png) | ![gpt-image-2.5-flare-max H2 zh round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-max/r1/04_test.png) | ![gpt-image-2.5-flare-auto H2 zh round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-auto/r1/04_test.png) |
|  | r1 7/7 · r2 7/7<br>exact | r1 7/7 · r2 7/7<br>exact | r1 7/7 · r2 7/7<br>exact | r1 7/7 · r2 7/7<br>exact | r1 7/7 · r2 7/7<br>exact | r1 7/7 · r2 7/7<br>exact | r1 7/7 · r2 7/7<br>exact |

**H3 — street plaque**: `EAST GATE No. 18 THIRD FLOOR` / `东门大街18号三楼`

| Language | MAI-Image-2.6 | GPT-Image-2.5 Flare low | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high | GPT-Image-2.5 Flare xhigh | GPT-Image-2.5 Flare max | GPT-Image-2.5 Flare auto |
| --- | --- | --- | --- | --- | --- | --- | --- |
| English | ![mai-image-2.6 H3 en round 1](data/text-hard-20260919/first-mai/mai-image-2.6/r1/05_test.png) | ![gpt-image-2.5-flare-low H3 en round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-low/r1/05_test.png) | ![gpt-image-2.5-flare-medium H3 en round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-medium/r1/05_test.png) | ![gpt-image-2.5-flare-high H3 en round 1](data/text-hard-20260919/first-gpt-image-2.5-flare/gpt-image-2.5-flare-high/r1/05_test.png) | ![gpt-image-2.5-flare-xhigh H3 en round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-xhigh/r1/05_test.png) | ![gpt-image-2.5-flare-max H3 en round 2](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-max/r2/05_test.png) | ![gpt-image-2.5-flare-auto H3 en round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-auto/r1/05_test.png) |
|  | r1 23/23 · r2 23/23<br>exact | r1 23/23 · r2 23/23<br>exact | r1 23/23 · r2 23/23<br>exact | r1 23/23 · r2 23/23<br>exact | r1 23/23 · r2 23/23<br>exact | r2 23/23<br>exact (r2) | r1 23/23 · r2 23/23<br>exact |
| Chinese | ![mai-image-2.6 H3 zh round 1](data/text-hard-20260919/first-mai/mai-image-2.6/r1/06_test.png) | ![gpt-image-2.5-flare-low H3 zh round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-low/r1/06_test.png) | ![gpt-image-2.5-flare-medium H3 zh round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-medium/r1/06_test.png) | ![gpt-image-2.5-flare-high H3 zh round 1](data/text-hard-20260919/first-gpt-image-2.5-flare/gpt-image-2.5-flare-high/r1/06_test.png) | ![gpt-image-2.5-flare-xhigh H3 zh round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-xhigh/r1/06_test.png) | ![gpt-image-2.5-flare-max H3 zh round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-max/r1/06_test.png) | ![gpt-image-2.5-flare-auto H3 zh round 2](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-auto/r2/06_test.png) |
|  | r1 9/9 · r2 9/9<br>exact | r1 9/9 · r2 9/9<br>exact | r1 9/9 · r2 9/9<br>exact | r1 9/9 · r2 9/9<br>exact | r1 9/9 · r2 9/9<br>exact | r1 9/9 · r2 9/9<br>exact | r1 9/9 · r2 8/9<br>read `东门大街18号二楼` (r2) |

**H4 — calligraphy scroll**: `STILL WATERS RUN DEEP` / `宁静致远`

| Language | MAI-Image-2.6 | GPT-Image-2.5 Flare low | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high | GPT-Image-2.5 Flare xhigh | GPT-Image-2.5 Flare max | GPT-Image-2.5 Flare auto |
| --- | --- | --- | --- | --- | --- | --- | --- |
| English | ![mai-image-2.6 H4 en round 1](data/text-hard-20260919/first-mai/mai-image-2.6/r1/07_test.png) | ![gpt-image-2.5-flare-low H4 en round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-low/r1/07_test.png) | ![gpt-image-2.5-flare-medium H4 en round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-medium/r1/07_test.png) | ![gpt-image-2.5-flare-high H4 en round 1](data/text-hard-20260919/first-gpt-image-2.5-flare/gpt-image-2.5-flare-high/r1/07_test.png) | ![gpt-image-2.5-flare-xhigh H4 en round 2](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-xhigh/r2/07_test.png) | ![gpt-image-2.5-flare-max H4 en round 2](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-max/r2/07_test.png) | ![gpt-image-2.5-flare-auto H4 en round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-auto/r1/07_test.png) |
|  | r1 18/18 · r2 18/18<br>exact | r1 18/18 · r2 18/18<br>exact | r1 18/18 · r2 18/18<br>exact | r1 18/18 · r2 18/18<br>exact | r1 18/18 · r2 16/18<br>read `STILLWATERDEEP` (r2) | r1 18/18 · r2 16/18<br>read `STILLWATERSDEEP` (r2) | r1 18/18 · r2 18/18<br>exact |
| Chinese | ![mai-image-2.6 H4 zh round 1](data/text-hard-20260919/first-mai/mai-image-2.6/r1/08_test.png) | ![gpt-image-2.5-flare-low H4 zh round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-low/r1/08_test.png) | ![gpt-image-2.5-flare-medium H4 zh round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-medium/r1/08_test.png) | ![gpt-image-2.5-flare-high H4 zh round 1](data/text-hard-20260919/first-gpt-image-2.5-flare/gpt-image-2.5-flare-high/r1/08_test.png) | ![gpt-image-2.5-flare-xhigh H4 zh round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-xhigh/r1/08_test.png) | ![gpt-image-2.5-flare-max H4 zh round 2](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-max/r2/08_test.png) | ![gpt-image-2.5-flare-auto H4 zh round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-auto/r1/08_test.png) |
|  | r1 4/4 · r2 4/4<br>exact | r1 4/4 · r2 4/4<br>exact | r1 4/4 · r2 4/4<br>exact | r1 4/4 · r2 4/4<br>exact | r1 4/4 · r2 4/4<br>exact | r2 4/4<br>exact (r2) | r1 4/4 · r2 4/4<br>exact |

**H5 — conference badge**: `ZHANG WEI / SENIOR ARCHITECT` / `张伟 / 高级架构师`

| Language | MAI-Image-2.6 | GPT-Image-2.5 Flare low | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high | GPT-Image-2.5 Flare xhigh | GPT-Image-2.5 Flare max | GPT-Image-2.5 Flare auto |
| --- | --- | --- | --- | --- | --- | --- | --- |
| English | ![mai-image-2.6 H5 en round 1](data/text-hard-20260919/first-mai/mai-image-2.6/r1/09_test.png) | ![gpt-image-2.5-flare-low H5 en round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-low/r1/09_test.png) | ![gpt-image-2.5-flare-medium H5 en round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-medium/r1/09_test.png) | ![gpt-image-2.5-flare-high H5 en round 1](data/text-hard-20260919/first-gpt-image-2.5-flare/gpt-image-2.5-flare-high/r1/09_test.png) | ![gpt-image-2.5-flare-xhigh H5 en round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-xhigh/r1/09_test.png) | ![gpt-image-2.5-flare-max H5 en round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-max/r1/09_test.png) | ![gpt-image-2.5-flare-auto H5 en round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-auto/r1/09_test.png) |
|  | r1 23/23 · r2 23/23<br>exact | r1 23/23 · r2 23/23<br>exact | r1 23/23 · r2 23/23<br>exact | r1 23/23 · r2 23/23<br>exact | r1 23/23 · r2 23/23<br>exact | r1 23/23 · r2 23/23<br>exact | r1 23/23 · r2 23/23<br>exact |
| Chinese | ![mai-image-2.6 H5 zh round 1](data/text-hard-20260919/first-mai/mai-image-2.6/r1/10_test.png) | ![gpt-image-2.5-flare-low H5 zh round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-low/r1/10_test.png) | ![gpt-image-2.5-flare-medium H5 zh round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-medium/r1/10_test.png) | ![gpt-image-2.5-flare-high H5 zh round 1](data/text-hard-20260919/first-gpt-image-2.5-flare/gpt-image-2.5-flare-high/r1/10_test.png) | ![gpt-image-2.5-flare-xhigh H5 zh round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-xhigh/r1/10_test.png) | ![gpt-image-2.5-flare-max H5 zh round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-max/r1/10_test.png) | ![gpt-image-2.5-flare-auto H5 zh round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-auto/r1/10_test.png) |
|  | r1 7/7 · r2 7/7<br>exact | r1 7/7 · r2 7/7<br>exact | r1 7/7 · r2 7/7<br>exact | r1 7/7 · r2 7/7<br>exact | r1 7/7 · r2 7/7<br>exact | r1 7/7 · r2 7/7<br>exact | r1 7/7 · r2 7/7<br>exact |

**H6 — handwritten whiteboard**: `SHIP IT BY FRIDAY NOON` / `周五中午前发布`

| Language | MAI-Image-2.6 | GPT-Image-2.5 Flare low | GPT-Image-2.5 Flare medium | GPT-Image-2.5 Flare high | GPT-Image-2.5 Flare xhigh | GPT-Image-2.5 Flare max | GPT-Image-2.5 Flare auto |
| --- | --- | --- | --- | --- | --- | --- | --- |
| English | ![mai-image-2.6 H6 en round 1](data/text-hard-20260919/first-mai/mai-image-2.6/r1/11_test.png) | ![gpt-image-2.5-flare-low H6 en round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-low/r1/11_test.png) | ![gpt-image-2.5-flare-medium H6 en round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-medium/r1/11_test.png) | ![gpt-image-2.5-flare-high H6 en round 1](data/text-hard-20260919/first-gpt-image-2.5-flare/gpt-image-2.5-flare-high/r1/11_test.png) | ![gpt-image-2.5-flare-xhigh H6 en round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-xhigh/r1/11_test.png) | ![gpt-image-2.5-flare-max H6 en round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-max/r1/11_test.png) | ![gpt-image-2.5-flare-auto H6 en round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-auto/r1/11_test.png) |
|  | r1 18/18 · r2 18/18<br>exact | r1 18/18 · r2 18/18<br>exact | r1 18/18 · r2 18/18<br>exact | r1 18/18 · r2 18/18<br>exact | r1 18/18 · r2 18/18<br>exact | r1 18/18 · r2 18/18<br>exact | r1 18/18 · r2 18/18<br>exact |
| Chinese | ![mai-image-2.6 H6 zh round 1](data/text-hard-20260919/first-mai/mai-image-2.6/r1/12_test.png) | ![gpt-image-2.5-flare-low H6 zh round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-low/r1/12_test.png) | ![gpt-image-2.5-flare-medium H6 zh round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-medium/r1/12_test.png) | ![gpt-image-2.5-flare-high H6 zh round 1](data/text-hard-20260919/first-gpt-image-2.5-flare/gpt-image-2.5-flare-high/r1/12_test.png) | ![gpt-image-2.5-flare-xhigh H6 zh round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-xhigh/r1/12_test.png) | ![gpt-image-2.5-flare-max H6 zh round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-max/r1/12_test.png) | ![gpt-image-2.5-flare-auto H6 zh round 1](data/text-hard-20260919/fill-gpt-image-2.5-flare/gpt-image-2.5-flare-auto/r1/12_test.png) |
|  | r1 7/7 · r2 7/7<br>exact | r1 7/7 · r2 7/7<br>exact | r1 7/7 · r2 7/7<br>exact | r1 7/7 · r2 7/7<br>exact | r1 7/7 · r2 7/7<br>exact | r1 7/7 · r2 7/7<br>exact | r1 7/7 · r2 7/7<br>exact |

**How it was judged**: each image is transcribed by `gpt-5.6-terra` and compared with the target string programmatically, ignoring all whitespace. Two denominators are reported: character accuracy scores the best-matching window of equal length anywhere in the transcription, character by character; exact segments requires the target to appear verbatim as a substring, with no partial credit. This is model-judged, not a blind human study. The judge is an OpenAI-family model and some of the judged images come from OpenAI image models; the calibration below rules out an inability to read Chinese, not a lenience toward one vendor's style, which is why every image is shown below for human review.

**The judge's own error floor**: rendering this section's targets with Microsoft YaHei and asking the judge to read them back scores 131/131 (100.0%) for English and 43/43 (100.0%) for Chinese under the same scoring rule as the table. The judge therefore has no systematic bias against these characters, and the gaps above are attributable to the image models. Boundary: this only establishes that the judge reads clean horizontal renders; distorted, stylised or vertical text in generated images is harder, so the table may understate accuracy and will not overstate it. The renders and transcriptions are in [judge-calibration](data/text-hard-20260919/judge-calibration) and `calibrate_text_judge.py --check` recomputes them offline.

**Boundary**: 310 successful samples across 6 scenes, 2 rounds and 13 configurations. This measures spelling accuracy for a specified string, not typographic quality, font choice or design appeal. MAI-Image-2.6 takes no quality parameter and therefore has a single row. **Declared support**: the Foundry model documentation lists MAI-Image-2.6 Languages as `en`; Chinese is outside its declared scope. The Chinese results here are observed behaviour outside that scope, not a product commitment, and should not be cited as a supported capability.

Evidence directory: [data/text-hard-20260919](data/text-hard-20260919) (per-group contact sheets in `review/`). Prompt SHA-256: `ccc4d655f4df2c664f261bb5d42277d7ecfb1f351cf0bf23c7a74bd77790d48b`.

## Web Grounding Test

This section tests a MAI-only parameter: identical prompts are sent to MAI-Image-2.6 with `web_grounding=false/true` to compare text factual accuracy and latency. Public product announcements supply the test subjects; this is not a customer project or adoption case. GPT-Image-2.5 has no equivalent parameter, so there is no GPT column here.

**What we asked the model**

Both subjects ask the model to put real product information into a poster. Subject 1 asks for every officially announced colour name and the screen-size options; subject 2 asks for the product name, screen size, computing platform, the officially named convertible modes and which surfaces accept pen input. The prompts only instruct the model to follow the official announcement; no correct answer is supplied in the prompt.

The exact prompt sent for subject 1 (New-product colours and sizes):

> Create a polished square English-language launch poster for the Lenovo IdeaPad Vibe series announced at Lenovo Innovation World in September 2026. Present the official launch colour lineup as clearly separated colour swatches, each with its exact official colour name, and include the official screen-size options. Use a restrained stylized laptop silhouette and prioritize readable product information. Base factual claims on Lenovo's announcement; do not substitute colours or models from older IdeaPad products. Do not include prices, purchase links or unsupported specifications.

The exact prompt sent for subject 2 (Product specifications and usage modes):

> Create a polished square English-language creator poster for the Lenovo Yoga 9n 2-in-1 announced at Lenovo Innovation World in September 2026. Include its exact product name, screen size and computing platform. Illustrate and label its officially named convertible usage modes, and describe which surfaces support pen input. Use a simple stylized device illustration with clear readable labels and generous spacing. Base the facts on Lenovo's announcement rather than specifications from older Yoga 9i products. Preserve qualifiers for optional features. Do not include prices or invented specifications.

**Controlled variable**

The only thing that changes is the `web_grounding` switch. Prompt, dimensions, model version, deployment and round count are identical.

The complete supplement contains 12 formal samples and 2 excluded warmups. Two subjects were selected after observing improved text facts; all off/on results from both rounds are shown, 8 original images and 4 samples per setting. The table covers only these examples, not an overall improvement rate.

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

Both settings used 1024x1024, `auto_aspect_ratio=false`, model version 2026-07-31 and the same Sweden Central GlobalStandard deployment; round 2 reversed request order. Only the grounding switch differed; reference answers were not included in prompts. Successful request time excludes JSON/base64 processing; logical call time includes failures, backoff and response processing. All HTTP 408 responses and retries are retained; the internal timeout stage was not returned, so the additional time cannot all be attributed to search. Improved text facts do not establish better aesthetics or product fidelity: in subject 2, round 2, the grounding-on `Tablet Mode` illustration still has an upright screen. Inspection was AI-assisted and unblinded; responses included no search queries, source URLs or retrieval traces.

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

[Raw results](data/lenovo-web-grounding-20260908/5way_v2_results.json) | [All attempts](data/lenovo-web-grounding-20260908/attempts.jsonl) | [Visual observations](data/lenovo-web-grounding-20260908/visual-review.json) | [Full 12-sample statistics](data/lenovo-web-grounding-20260908/web-grounding-summary.json) | [Provenance and hashes](data/lenovo-web-grounding-20260908/provenance.json)

Result SHA-256: `669617dd5d59d0748a0fc398d98ec4c59cb4b26cc9655138edf9b6c9622f3c1b`. Official references: [IdeaPad Vibe](https://news.lenovo.com/pressroom/press-releases/colorful-ideapad-vibe-series-all-in-one-ai-pcs/) | [Yoga](https://news.lenovo.com/pressroom/press-releases/yoga-portfolio-new-ai-pcs-and-tablets/) | [MAI API](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai-image#request-parameters)
