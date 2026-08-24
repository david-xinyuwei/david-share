# Validation Checklist

- [x] Official repository and immutable commit identified
- [x] All 25 executable upstream Git blob contents pinned with SHA-256
- [x] Verified Git blob bytes materialized into a private run directory and invoked without modification
- [x] ARM deployment, AOAI model/cache binding, and Context Cache container contract verified
- [x] Exact Windows AMD64 CPython 3.11 wheel artifacts locked with SHA-256
- [x] Six real Responses API calls completed
- [x] Cache result independently recomputed from call rows
- [x] No-cache, zero-threshold, zero-latency, missing-row, HTTP-error, partial-hit, failed-ARM, and wrong-binding branches tested
- [x] PowerShell runner behavior tested with process-level Azure CLI doubles, bounded timeout, junction rejection, Preview/provider rejection, unsupported-region rejection, and lease release
- [x] Resource-group absence is checked both during preflight and immediately before the official deployment path
- [x] Public evidence stripped of cloud and identity identifiers
- [x] Public scanning rejects invalid UTF-8 and scans nested files even when their basename matches the scanner
- [x] Customer README separates Context Cache-specific ARM/binding evidence from non-attributed prompt-cache telemetry
- [x] The retained telemetry figure states that default prompt caching and Context Cache were both active
- [x] Paired-prefix probe isolates the two arms before the original prompt content and asserts equal-length markers
- [x] Warm evidence records an independent `0 -> 2304` transition on each arm with equal input-token counts
- [ ] Post-24-hour paired-prefix verification is pending; no completed retention verdict is published
- [x] Runtime has no mock, API-key fallback, automatic login, or automatic cleanup
- [x] English and Chinese documentation share structure, commands, images, and boundaries
- [x] Static validators and cross-platform CI included

The completed live capability result remains a bounded observation. The paired-prefix warm
stage is real runtime evidence, but its retention verification is pending. CI validates code,
contracts, and sanitized evidence offline; CI does not deploy Azure resources.