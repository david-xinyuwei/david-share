# Method and Lineage

## Authority

The product-producing source is `Azure/AzureContextCache`. This repository invokes the
official Quickstart at commit `7d1029a5e8b59b1805e70992c85ffe6798d2f47a`; it does not
reimplement the Azure resources, request payload, or cache logic.

## Execution Lineage

```mermaid
flowchart LR
    A[Public runner] --> B[Azure preflight]
    B --> C[25 verified Git blobs]
    C --> D[Private materialized Quickstart]
    D --> E[ARM resources]
    D --> F[Six Responses API calls]
    F --> G[Captured transcript]
    G --> H[Independent parser]
    H --> I[Run contract and summary]
```

The runner performs the following stages in order:

1. Verify the active subscription and live `Microsoft.Resources` read.
2. Require both resource providers and the gated feature to be registered.
3. Resolve the pinned official Git commit, compare all 25 executable-input Git blob SHA-256 values, and materialize those same verified bytes into the private run directory. External worktree bytes are never executed.
4. Install the verified live-run dependency set from exact Windows AMD64 CPython 3.11 wheel versions and artifact hashes; the upstream `demo/requirements.txt` remains independently source-locked.
5. Invoke the byte-identical materialized official `scripts/quickstart.ps1` with `-SkipPython`.
6. Capture stdout and stderr in a unique run directory outside the source tree.
7. Parse all six call rows and require the configured warm-hit ratio.
8. Validate deployment success and the model/cache binding across ARM outputs, the AOAI deployment, and the Context Cache container before writing the bounded run contract and artifact manifest.

## Measurement Contract

The parser treats each printed call row as one observation. It does not infer missing
calls and does not use the Quickstart's final success text as evidence. A run fails when:

- an HTTP or transport error appears;
- the row count or call order differs from the contract;
- the configured warm-hit threshold is zero, or fewer than that fraction of warm calls contain cached tokens;
- a row has no measurable latency; or
- the official process exits nonzero.

The default threshold is three cache hits among five warm calls. It accommodates observed
Private Preview variability while still rejecting a no-cache run. Changing this threshold
creates a different acceptance contract and must be disclosed with the result.

## Public Evidence Derivation

The checked-in evidence preserves call-level token and latency fields needed for arithmetic
recomputation. The export removes subscription, tenant, resource, endpoint, user, and email
identifiers. It also omits raw Azure JSON and private logs. This makes the public evidence a
sanitized derivative, not a replacement for private operational records.

## Attribution Boundary and Comparison Design

The bounded run proves that a deployment bound to `properties.contextCacheContainerId` completed repeated-prefix requests end to end and that the data plane reported nonzero `cached_tokens`. It does not attribute those cached tokens to the binding: the official demo sets `prompt_cache_retention` on every request, and the model family supports default caching independently of the Context Cache binding.

A private controlled comparison also exposed an ordering confound:

| Observation in this environment | What was measured |
|---|---|
| A new deployment in the same account had no container binding and had never been called, yet its first request returned nonzero `cached_tokens` | The bound deployment had cold-started the byte-identical prefix 3.759 seconds earlier |
| Later alternating rounds showed identical hit behavior on both deployments | The bound deployment was always called first and warmed the shared prefix before the unbound deployment was measured |

The narrow conclusion is limited to this environment: **prefix cache state was reused across two deployments in one Azure OpenAI account.** This is not a documented product guarantee or a statement about internal service behavior. It means that separate deployments in one account cannot be assumed to form a cache isolation boundary.

The corrected comparison uses the following design:

| Element | Design |
|---|---|
| Arms | One deployment with `contextCacheContainerId` and one deployment in the same account and region without it; model and version are identical |
| Prompt | The same base prompt and suffix contract on both arms, with an equal-length `ARM=A` or `ARM=B` marker before the original content so the cache keys are distinct |
| Intervals | Inside the in-memory window, past it but inside extended retention, and past extended retention |
| Call order | Fixed linked-then-control order for repeatability; attribution no longer depends on order because the two arms cannot warm the same content-keyed prefix |
| Metrics | Hit rate and `cached_tokens` per arm and interval |
| Reporting | Publish every interval, including intervals where the two arms are indistinguishable, and including negative results |

An earlier iteration called the *unbound* arm first at the deciding interval. That removed one pre-warm direction but destroyed attribution in the opposite direction: the unbound arm's own cold miss warmed the shared prefix, so a hit on the bound arm moments later had an ambiguous source. Bound-first ordering made the first linked call interpretable, but still left only one uncontaminated observation. The stronger design isolates the cache keys themselves, so each arm can be evaluated independently.

## Cross-Day Attribution Test

The deciding interval is the one past the documented extended-retention ceiling. This test was executed on `2026-08-23`.

### Preconditions, machine-verified and fail-closed

| Gate | Verified value |
|---|---|
| No inference traffic on the account since the previous phase | Azure Monitor `AzureOpenAIRequests`, hourly buckets: exactly one non-zero bucket, and it is the previous phase itself |
| Idle duration above the documented default-cache ceiling | `43.83` h idle versus a documented `24` h maximum for extended retention |
| Container lifetime still open | `124.17` h remaining of the 7-day `timeToLive`; `provisioningState=Succeeded` |
| Bound arm actually bound | `contextCacheContainerId` present |
| Control arm actually unbound | `contextCacheContainerId` is `null` |
| Arms otherwise identical | Both `gpt-5.4` / `2026-03-05-contextcache`, capacity `100`; byte-identical prefix |

The sealing step refuses to proceed if any gate fails, so a contaminated window cannot silently produce a result.

### Observation

| Order | Arm | `cached_tokens` | Latency |
|---:|---|---:|---:|
| 1st | bound to container | `0` | `3182 ms` |
| 2nd, `+3.185` s | unbound control | `2304` | `1678 ms` |

Integrity: single `prefix_sha256`, identical `input_tokens=2467`, both `HTTP 200`, bound arm confirmed first.

### Adjudicated findings

1. **The declared 7-day container lifetime did not produce a cross-day data-plane hit in this environment.** The reuse-window hypothesis is falsified for this environment, interval, model, and Preview build. This is a bounded negative result, not a defect report.
2. **Prefix cache state crossed the deployment boundary in both directions.** Combined with the earlier reverse observation, separate deployments in one Azure OpenAI account must not be assumed to form a cache isolation boundary.
3. **No latency claim is supportable.** Hit-versus-hit means were `1877.8 ms` (bound, sd `365.3`, n=11) and `2047.9 ms` (unbound, sd `766.8`, n=11). The `170 ms` gap is smaller than either standard deviation and its sign flips across phases (`−14.9`, `−672.2`, `+230.0` ms). What is supportable is that a hit beats a miss: `1962.9 ms` versus `3368.5 ms`, a `41.7%` reduction.

Incremental hit-rate, cost, and latency claims therefore remain unproven. The completed observation points against the hit-rate hypothesis in this environment, and the stronger paired-prefix follow-up below independently reached the same negative direction. The defensible differentiators are explicit lifetime declaration, residency, ownership, and governance — all verified through control-plane reads and none dependent on a cache-hit comparison.

Reproducing this test requires re-establishing an idle window longer than 24 hours on the account. Any inference traffic in between invalidates the precondition.

## Paired-Prefix Follow-Up (Completed)

This is a new experimental lineage, not a rewrite of the completed cross-day result. It removes the shared-key confound by giving each arm its own prefix family while preserving the same base prompt, suffix contract, model, version, capacity, request shape, and retention setting.

| Contract element | Frozen value |
|---|---|
| Arms | One deployment bound to the Context Cache container and one unbound control deployment |
| Cache-key isolation | Equal-length `ARM=A` and `ARM=B` markers appear before the original stable content |
| Runtime parity | Both arms must report the same measurable input-token count |
| Warm gate | Each arm must independently produce `cached_tokens: 0 -> >0` across two calls |
| Verify gate | One call per arm only after at least `26` hours; the script rejects an early or duplicate Verify |
| Current state | `COMPLETE / INCREMENTAL RETENTION NOT OBSERVED` |

Warm observations:

| Arm | Call 1 | Call 2 | Input tokens per call |
|---|---:|---:|---:|
| Linked Context Cache arm | `0` | `2304` | `2513` |
| Unbound control arm | `0` | `2304` | `2513` |

Verify observations after `26.012` idle hours:

| Arm | Cached tokens | Input tokens | Latency |
|---|---:|---:|---:|
| Linked Context Cache arm | `0` | `2512` | `3235 ms` |
| Unbound control arm | `0` | `2512` | `1846 ms` |

Both Verify calls returned `HTTP 200`. The verdict matrix was frozen before Verify; the linked-miss/control-miss cell maps to `context-cache-incremental-retention-not-observed`. This is a bounded result for one Private Preview environment, not a product-wide guarantee or defect report.

The public probe is parameterized and contains no endpoint, resource ID, or credential. Before sending requests, it uses the caller's isolated Azure CLI profile to verify both deployment definitions and the container model/TTL through ARM. It then obtains a data-plane token and writes request rows to a caller-selected path outside the public source tree.

```powershell
$env:AZURE_CONFIG_DIR = "$HOME\.azure-context-cache-validation"

$common = @(
    '--endpoint', 'https://YOUR-AOAI-ACCOUNT.openai.azure.com',
    '--subscription-id', 'YOUR-SUBSCRIPTION-ID',
    '--resource-group', 'YOUR-RESOURCE-GROUP',
    '--account-name', 'YOUR-AOAI-ACCOUNT',
    '--linked-deployment', 'YOUR-LINKED-DEPLOYMENT',
    '--control-deployment', 'YOUR-CONTROL-DEPLOYMENT',
    '--expected-container-id', '/subscriptions/YOUR-SUBSCRIPTION-ID/resourceGroups/YOUR-RESOURCE-GROUP/providers/Microsoft.Storage/contextCaches/YOUR-CACHE/contextCacheContainers/YOUR-CONTAINER',
    '--prefix-file', 'PATH-TO-STABLE-PREFIX',
    '--run-id', 'customer-eval-001',
    '--output', 'PATH-TO-PRIVATE-RESULTS.jsonl'
)

python .\scripts\paired_prefix_probe.py @common --phase WARM
# Wait at least 26 hours without reusing either isolated prefix.
python .\scripts\paired_prefix_probe.py @common --phase VERIFY
```

The verdict matrix was frozen before Verify:

| Linked after 26+ h | Control after 26+ h | Adjudication |
|---:|---:|---|
| hit | miss | Incremental Context Cache retention observed in this environment |
| miss | miss | Incremental Context Cache retention not observed in this environment |
| hit | hit | Ambiguous: both paths retained the prefixes |
| miss | hit | Unexpected control-only hit; investigate before making a product claim |

Until Verify completes, the warm rows prove only that both isolated prefix families were independently cacheable. They do not establish cross-day retention. The sanitized state is recorded in [`../evidence/paired-prefix-follow-up.json`](../evidence/paired-prefix-follow-up.json).

## Claim Boundary

The completed path proves that the deployment binding was present and that the bound path completed Responses API calls with nonzero cached tokens in one bounded run. It does not prove a latency distribution, pricing outcome, concurrency guarantee, regional availability, or production readiness. The completed cross-day observation establishes a bounded negative result for one prefix and interval; the paired-prefix follow-up has no retention result until Verify completes. Neither result generalises to other regions, models, prefixes, intervals, or Preview builds. Effect is reported; server-side mechanism is not inferred from client-side timing.