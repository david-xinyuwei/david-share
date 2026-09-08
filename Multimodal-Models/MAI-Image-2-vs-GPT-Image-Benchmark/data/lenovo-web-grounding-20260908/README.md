# Lenovo Product Examples: MAI-Image-2.6 Web Grounding

[中文](README-CN.md) | [Main two-model benchmark](../../README.md)

**These two examples were selected after testing because web grounding improved the checked product text facts.** Both rounds of IdeaPad Vibe and Yoga 9n 2-in-1 are shown, with grounding off and on: eight original images, not a best-of selection within each scenario.

The full supplemental run contained three scenarios and 12 formal samples, plus two excluded warmups. All underlying measurements and original images are retained as evidence; the other scenario is not displayed here. Every metric below is recalculated for the eight displayed samples, four per setting. This is a selected case study, not an aggregate improvement rate or evidence that grounding improves every scenario. No GPT requests were made in this supplement, and the original two-model benchmark is unchanged.

## Observed Differences

| Scenario | Grounding off, both rounds | Grounding on, both rounds |
| --- | --- | --- |
| IdeaPad Vibe launch poster | Each round supplied four names outside the seven official launch colours. Screen options were 14/16 inches and 14/15.3/16 inches | All seven official colour names and the 14/15-inch options matched the announcement in both rounds |
| Yoga 9n 2-in-1 creator poster | Screen sizes were 14.5 and 14 inches; both specified Intel Core Ultra and only four modes, omitting Canvas | Both matched 16 inches, NVIDIA RTX Spark, all five mode names, and pen input on the display and Haptic Force Pad |

The second grounding-off Yoga image mentioned optional touchpad pen input, which was closer to the announcement than the first round's keyboard-deck claim. Its screen, platform and mode count were still incorrect. Grounding on also left a visual error: the second-round `Tablet Mode` illustration has an upright screen. Correct labels do not establish correct device geometry or a production-ready advertisement. Additional claims outside the frozen checklist are not certified by this review.

## Latency and Failed Attempts

| Metric | Grounding off | Grounding on |
| --- | ---: | ---: |
| Images returned / displayed samples | 4/4 | 4/4 |
| First-attempt successes / displayed samples | 4/4 | 1/4 |
| HTTP attempts for displayed samples | 4 | 7 |
| HTTP 408 responses | 0 | 3 |
| Mean successful HTTP request | 35.75 s | 68.91 s |
| Successful HTTP request P50 | 34.57 s | 67.23 s |
| Mean logical call, including failed attempts and retries | 35.77 s | 168.21 s |

All three HTTP 408 responses occurred with grounding on: IdeaPad round 1, Yoga round 1 and Yoga round 2. Each succeeded on retry under the frozen runner policy. The service returned `Timeout` without identifying the internal component; these failures cannot be attributed specifically to Bing or model inference.

Successful HTTP time covers sending the request through receipt of the full response, before JSON decoding. Logical call time additionally includes failed attempts, backoff, JSON/base64 processing and response-metadata writes. It excludes the outer five-second interval and final PNG-file write. Neither metric is isolated GPU inference time.

## Original Images

All eight images below are the unedited PNGs returned by MAI-Image-2.6 in this run at 1024x1024 with `auto_aspect_ratio=false`. Inspect product facts as well as the visible limitations; no image was regenerated or substituted for publication.

### IdeaPad Vibe: Round 1

Check the official colour names and 14/15-inch options, not just the layout.

| `web_grounding=false` | `web_grounding=true` |
| --- | --- |
| ![IdeaPad round 1, grounding off](mai-image-2.6-web-off/r1/01_test.png) | ![IdeaPad round 1, grounding on](mai-image-2.6-web-on/r1/01_test.png) |

### IdeaPad Vibe: Round 2

Requests ran on then off in this round. Display columns remain off on the left and on on the right.

| `web_grounding=false` | `web_grounding=true` |
| --- | --- |
| ![IdeaPad round 2, grounding off](mai-image-2.6-web-off/r2/01_test.png) | ![IdeaPad round 2, grounding on](mai-image-2.6-web-on/r2/01_test.png) |

### Yoga 9n 2-in-1: Round 1

Check screen size, computing platform, five mode names and the two pen-input surfaces. Device illustrations are not product photographs.

| `web_grounding=false` | `web_grounding=true` |
| --- | --- |
| ![Yoga round 1, grounding off](mai-image-2.6-web-off/r1/02_test.png) | ![Yoga round 1, grounding on](mai-image-2.6-web-on/r1/02_test.png) |

### Yoga 9n 2-in-1: Round 2

This round also reversed request order. The grounding-on mode names are correct, but the illustrated `Tablet Mode` posture needs correction.

| `web_grounding=false` | `web_grounding=true` |
| --- | --- |
| ![Yoga round 2, grounding off](mai-image-2.6-web-off/r2/02_test.png) | ![Yoga round 2, grounding on](mai-image-2.6-web-on/r2/02_test.png) |

## Scope and Evidence

- Model: MAI-Image-2.6, version 2026-07-31, the same Sweden Central GlobalStandard deployment for both settings. Requests were serial at 1024x1024 with automatic aspect ratio explicitly disabled.
- Prompts 1 and 2 of the three-prompt supplement are displayed. Each off/on pair used identical prompt text; only `web_grounding` differed. The second round reversed setting order. Reference answers were not included in the requests.
- Every original image was visually inspected. This was AI-assisted, unblinded inspection, not customer feedback, human preference voting or a statistically significant quality comparison. There are only four displayed samples per setting, selected for observed factual improvement.
- Responses provided no search queries, source URLs or retrieval traces. Changes in reported input text tokens do not identify retrieval sources or internal implementation. An image's claim to use official information is not a search trace.
- These checks concern selected facts from public announcements, not product photography, geometry, logos or calibrated colour accuracy. Production marketing material still needs approved product references and human review.
- No GPT comparison was performed here, so this supplement does not establish an advantage over GPT-Image-2.

Formal execution: 2026-09-08 02:06:40-02:23:50 UTC, exit code 0, state `COMPLETED`.

[Full measurement record, 12 samples](5way_v2_results.json) | [All HTTP attempts](attempts.jsonl) | [Full-run summary, not the selected statistics above](web-grounding-summary.json) | [Original visual observations](visual-review.json) | [Provenance and file hashes](provenance.json)

Original result SHA-256: `669617dd5d59d0748a0fc398d98ec4c59cb4b26cc9655138edf9b6c9622f3c1b`.

## Reproduce or Verify

Run from the benchmark project directory after completing the [main setup](../../README.md). Set `MAI_ENDPOINT` and `AZURE_API_KEY` securely in the environment. Offline verification does not call a model or alter the archive:

```bash
python scripts/summarize_web_grounding.py data/lenovo-web-grounding-20260908 --require-complete --check
```

To rerun the complete three-prompt supplement in a new output directory, use the frozen executed source and original prompt file. The dry run makes no network calls; the next command makes real generation requests, including two warmups and 12 planned formal samples:

```bash
python data/lenovo-web-grounding-20260908/source/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --mai-web-grounding both --prompts-csv data/lenovo-web-grounding-20260908/source/prompts.csv --output runs/web-grounding-reproduction --dry-run
python data/lenovo-web-grounding-20260908/source/benchmark_5way_v2.py --mai-model MAI-Image-2.6 --mai-web-grounding both --prompts-csv data/lenovo-web-grounding-20260908/source/prompts.csv --output runs/web-grounding-reproduction
```

Use `--resume` only to continue that same run, not to replace completed samples. Preserve failures and both rounds. This publication did not rerun any model requests.

## Official References

Reference pages were read and captured before testing; their URLs and snapshot hashes are in [source-captures.json](source-captures.json). The [frozen factual checklist](source/reference-facts.json) records the planned protocol and expected facts, not execution status.

- [Lenovo IdeaPad Vibe announcement, 2026-09-03](https://news.lenovo.com/pressroom/press-releases/colorful-ideapad-vibe-series-all-in-one-ai-pcs/)
- [Lenovo Yoga announcement, 2026-09-03](https://news.lenovo.com/pressroom/press-releases/yoga-portfolio-new-ai-pcs-and-tablets/)
- [MAI image request parameters](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-mai-image#request-parameters)

**Consider grounding for draft marketing material that needs recent product facts, not as a default for every image.** The observed factual gains came with higher latency and three timeout retries; adoption depends on acceptable waiting time, factual review and the intended use of the material.