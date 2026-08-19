# Validation Checklist

- [x] Official repository and immutable commit identified
- [x] Eleven upstream Git blob contents pinned with SHA-256
- [x] Official Quickstart invoked without source modification
- [x] Real Azure control-plane deployment verified
- [x] Six real Responses API calls completed
- [x] Cache result independently recomputed from call rows
- [x] No-cache, missing-row, HTTP-error, and partial-hit branches tested
- [x] Public evidence stripped of cloud and identity identifiers
- [x] Runtime has no mock, API-key fallback, automatic login, or automatic cleanup
- [x] English and Chinese documentation share structure, commands, images, and boundaries
- [x] Static validators and cross-platform CI included

The live capability result is a single-run observation. CI validates code, contracts, and
sanitized evidence offline; CI does not deploy Azure resources.