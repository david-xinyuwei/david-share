# [REVIEW] Round 1 — Blue Team — 2026-07-05

## Review Object

- Repo: `G:\github\david-share\Deep-Learning\Speculative-Decoding-EAGLE3`
- Mode: read-only super review, current model acting as Blue Team
- Files reviewed:
  - `README.md`
  - `README-CN.md`
  - `images/*.png`
  - `data/*.json`
  - `logs/*.log`
  - `scripts/*`
- Current diff scope inside target repo:
  - `README.md`
  - `README-CN.md`
  - `images/eagle_mtp_3params_explained.png`

## Review Dimensions

- Bilingual consistency
- L5 repo quality
- Data-rich principle
- Best-case-law principles (CL-001, CL-006, CL-007)
- Reader-perspective / 换位法

## Evidence Collected

### Machine Checks

| Check | Result |
|---|---|
| README H1 | Both `README.md` and `README-CN.md` now use `# Speculative Decoding` |
| Old title check | `Speculative Decoding on Azure = 0` in both files |
| Xiaomi/MiMo case leakage | `MiMo = 0`, `Xiaomi = 0`, `小米 = 0` in both files |
| Simulated acceptance markers | Both files contain `SGLANG_SIMULATE_ACC_LEN`, `SGLANG_SIMULATE_ACC_METHOD`, `accept_rate = accept_length / max_accept_length`, and `今天天气真好` |
| Local markdown references | 16 local refs in each README; missing local refs = `[]` |
| Data files | 5 JSON files exist and parse as JSON |
| Logs | 5 log files exist |
| Scripts | 11 scripts exist |

### Assets

| Directory | Count / Notes |
|---|---|
| `data/` | 5 JSON files, 56-112 lines each |
| `logs/` | 5 logs; H100 vLLM native MTP and DFlash logs are 235 / 213 lines |
| `scripts/` | 11 scripts, including benchmark clients and launch scripts |
| `images/` | 3 PNG files |

## Findings

### CRITICAL-1 — Two legacy images are visually corrupted / not L5-deliverable

**Evidence**

- `images/eagle3-architecture.png` displayed as a broken/corrupted chart-like image during `view_image`; it does not show a readable EAGLE3 architecture diagram.
- `images/eagle3-training-comparison.png` also displayed with severe overlaid/corrupted chart content and unreadable text.
- README references:
  - `README.md` line 71: `eagle3-architecture.png`
  - `README.md` line 658: `eagle3-training-comparison.png`
  - `README-CN.md` line 71: `eagle3-architecture.png`
  - `README-CN.md` line 658: `eagle3-training-comparison.png`

**Why it matters**

L5 repo quality requires images to be readable and support the technical explanation. These two images are currently likely to confuse readers and fail the visual review standard.

**Fix proposal**

- Replace both legacy images with clean regenerated diagrams:
  - `eagle3-architecture.png`: redraw EAGLE3 target layers -> selected hidden states -> draft head -> tree verify.
  - `eagle3-training-comparison.png`: redraw training-time vs inference-time flow with the train-test gap and EAGLE3 fix.
- Re-run `view_image` for every PNG after replacement.

**Verification**

- `view_image images/eagle3-architecture.png`
- `view_image images/eagle3-training-comparison.png`
- Confirm captions match actual image content in EN and CN.

**Risk**

If regenerated diagrams deviate from paper figures, label them as simplified explanatory diagrams rather than original paper figures.

---

### HIGH-1 — Public repo slug / folder name still contains `EAGLE3`

**Evidence**

- Local path remains `Speculative-Decoding-EAGLE3`.
- README tree was changed to `speculative-decoding-on-azure/` earlier and should now be `speculative-decoding/`, but the actual repo folder/GitHub repo name may still expose the old EAGLE3-centric positioning.

**Why it matters**

The user explicitly said the repo should not be named around EAGLE3 because EAGLE3 is only one technique. H1 and first-screen copy are fixed, but the public repo URL/name may still contradict the new positioning.

**Fix proposal**

- Decide whether to rename the GitHub repo / folder to `Speculative-Decoding`.
- Update README repository tree root to `speculative-decoding/` rather than `speculative-decoding-on-azure/` or `Speculative-Decoding-EAGLE3/`.

**Verification**

- `grep -R "Speculative-Decoding-EAGLE3\|speculative-decoding-on-azure" README.md README-CN.md`
- Confirm public GitHub repo URL/title if this repo is already published.

**Risk**

Renaming a public repo can affect existing links. If rename is not desired immediately, add a short note in release/issue tracking but keep README title generic.

---

### HIGH-2 — Data-rich coverage is partial: Phase 1 / Phase 2 key numbers are not backed by machine-readable data files inside repo

**Evidence**

- `data/` contains Gemma 4 and H100 DFlash/MTP JSONs only:
  - `gemma4_mtp_h100_baseline.json`
  - `gemma4_mtp_h100_mtp.json`
  - `h100_vllm_native_mtp.json`
  - `h100_vllm_dflash.json`
  - `h100_llamacpp_mtp_q4kxl.json`
- Executive Summary claims:
  - `441.7 vs 165.7 tok/s = 2.67x`
  - `207.7 vs 159.8 tok/s = 1.30x`
  - `80.2 vs 46.3 tok/s = 1.73x`
- Phase 1 and Phase 2 numbers are embedded in README text/log snippets, but there are no obvious machine-readable raw result files for those phases in `data/`.

**Why it matters**

Data-rich L5 means the headline numeric claims should trace to raw JSON/log artifacts, not only prose snippets. The repo is strong for Phase 3 and H100 route comparison but weaker for Phase 1/2 reproducibility evidence.

**Fix proposal**

- Add or locate raw machine-readable Phase 1 and Phase 2 data files, for example:
  - `data/eagle3_official_h100_validation.json`
  - `data/eagle3_self_trained_h100_results.json`
- Update `Data Files` tables in EN/CN to list them.
- If raw files are unavailable, explicitly label these Phase 1/2 numbers as README-embedded historical logs and downgrade their evidence strength.

**Verification**

- `python -m json.tool data/eagle3_official_h100_validation.json`
- `python -m json.tool data/eagle3_self_trained_h100_results.json`
- Grep Data Files table in both READMEs.

**Risk**

Adding reconstructed JSON after the fact can be misleading. Prefer original raw files if available.

---

### HIGH-3 — EN/CN section ordering is not fully aligned

**Evidence**

- EN order near the end:
  - `About EAGLE` at line 1234
  - `References` at line 1254
  - `When Does Speculative Decoding Actually Help?` at line 1274
  - `Key Takeaways` at line 1314
  - `Citation` at line 1324
  - `Reproducing the Results` at line 1337
- CN order near the end:
  - `参考资源` at line 1236
  - `Speculative Decoding 何时真正有效？` at line 1256
  - `核心结论` at line 1296
  - `关于 EAGLE` at line 1304
  - `复现实验` at line 1324
- `About EAGLE` / `关于 EAGLE` is not in the same relative position.
- EN has an explicit `Citation` section; CN does not show a matching `Citation` heading in the extracted structure.

**Why it matters**

The user requested bilingual consistency. The main content is mostly aligned, but section order and presence near the end diverge enough to be noticeable.

**Fix proposal**

- Align late-section order between EN/CN.
- Add a CN `引用` section corresponding to EN `Citation`, or remove/merge EN citation into a shared section if not needed.

**Verification**

- Run a heading extraction script and compare H2/H3 sequence.
- Ensure EN/CN line count difference remains within an explainable range.

**Risk**

Reordering can create anchor/link drift if external links point to headings. Keep heading text stable where possible.

---

### MEDIUM-1 — New hyperparameter figure is a clear improvement, but should be re-opened after cache refresh

**Evidence**

- `images/eagle_mtp_3params_explained.png` regenerated to 1280x940, 120,976 bytes.
- Machine pixel samples show a white clean canvas and expected colored panels.
- `view_image` displayed the main text clearly, but there were still apparent old chart fragments in the upper area during chat rendering.

**Why it matters**

The new figure directly addresses the user's confusion: `t`, `t+1..t+3`, `t+4 bonus`, and simulated 75% acceptance. However, because visual display showed possible cache/artifact behavior, it needs one more human browser/GitHub preview check.

**Fix proposal**

- Re-open the PNG after VS Code/GitHub cache refresh.
- If artifacts are still visible, regenerate under a new filename such as `speculative_decoding_hyperparams_timeline.png` and update README references.

**Verification**

- `view_image images/eagle_mtp_3params_explained.png`
- Browser/GitHub preview after refresh.

**Risk**

If image cache is the only issue, unnecessary filename changes could add churn. Verify once before renaming.

---

### MEDIUM-2 — Executive Summary is data-dense but still reads like a phase log rather than a reader-first decision map

**Evidence**

- Executive Summary table is clear but organized by Phase 1/2/3 rather than by reader decision:
  - use EAGLE3 when official draft exists
  - self-train when no draft exists and workload is narrow
  - use native MTP assistant when vendor publishes one
  - benchmark DFlash/MTP route under workload-specific conditions

**Why it matters**

Best-case-law and reader-perspective review favor “what should I do?” framing near the first screen. The current summary is accurate, but a practitioner may need to read deeper before seeing the decision logic.

**Fix proposal**

- Add a compact first-screen “Which route should I try first?” table.
- Keep the existing phase table as evidence below it.

**Verification**

- Check first screen contains reader action guidance, not only phase history.

**Risk**

Avoid turning the first screen into a marketing page. Keep it technical and evidence-based.

---

## Numeric Claims Audit

| Claim | Location | Source status | Judgment |
|---|---|---|---|
| `441.7 vs 165.7 tok/s = 2.67x` | EN line 34 / CN line 34 | Embedded raw results in README; no obvious JSON data file in repo | PARTIAL |
| `207.7 vs 159.8 tok/s = 1.30x` | EN line 35 / CN line 35 | Embedded results in README; no obvious JSON data file in repo | PARTIAL |
| `80.2 vs 46.3 tok/s = 1.73x` | EN line 36 / CN line 36; data files exist for Gemma baseline/MTP | OK |
| `191.7 vs 146.7` DFlash/native MTP | EN line 374 / 383; CN line 374 / 383; H100 JSON files exist | OK |
| `accept_rate = 3 / 4 = 0.75` | EN/CN simulated acceptance section | Clearly labeled as configured effect, not real model ability | OK |
| `1024 / 3 ≈ 341` | EN/CN simulated acceptance section | Formula is explanatory and correctly caveated | OK |

## Reader-Perspective Review

| Reader | Can they answer their main question? | Gaps |
|---|---|---|
| Algorithm reader | Mostly yes: taxonomy, mechanisms, hyperparams, caveats are now much clearer | Corrupted legacy diagrams block understanding |
| GPU inference engineer | Mostly yes: scripts/data/logs and runtime knobs exist | Phase 1/2 raw data should be machine-readable |
| Public repo evaluator | Partially: title and Xiaomi/MiMo leakage fixed | Repo slug still EAGLE3-centric; images are not L5 |
| Bilingual reader | Mostly yes | Late-section order mismatch and missing CN citation heading |

## Overall Blue-Team Judgment

Current repo is close to L5 in text structure and mechanism explanation after the latest fixes, but it is **not yet L5-ready** because of:

1. CRITICAL image quality issue.
2. Public repo naming/slug still likely EAGLE3-centric.
3. Phase 1/2 data-rich evidence gap.
4. Late-section bilingual ordering mismatch.

Recommended next step: do not commit/push as final until the CRITICAL and HIGH findings are fixed or consciously waived.

## Round 2 Red-Team Focus

Ask the red-team model to specifically challenge:

1. Whether the two old PNGs are truly corrupted or if the chat renderer is caching incorrectly.
2. Whether the repo slug must be renamed now or can be deferred.
3. Whether Phase 1/2 embedded logs are acceptable as data-rich evidence.
4. Whether any removed MiMo/Xiaomi references created loss of important algorithm taxonomy detail.
5. Whether the new simulated-acceptance example is technically precise enough for a public algorithm repo.
