# Public Evidence Boundary

`verified-run-summary.json` is a sanitized, single-run observation produced by the pinned
official Quickstart. It retains the six response rows needed to recompute the cache result.

![Non-attributed single-run prompt-cache telemetry](../images/verified-observation.svg)

Both model-default prompt caching and Azure Context Cache were active in this run. The
figure therefore records generic cache telemetry only. It does not establish incremental
Context Cache hit rate, latency reduction, or savings.

It intentionally omits subscription and tenant identifiers, resource IDs, endpoint names,
user identities, email threads, and the private raw Azure deployment records. The included
latency values prove only what happened in that run. They are not a production benchmark,
an SLA, or a pricing claim.

`validation-history.json` discloses two complete runs, two later runs that the hardened
parser rejected because the official concurrent demo reported transport errors, and one
completed cross-day attribution run. Rejected runs are not scored or converted into passes.

The `cross-day-attribution` entry is a completed controlled run whose result **contradicted
the hypothesis it was designed to test**. After a verified idle window of `43.83` hours,
longer than the documented `24`-hour ceiling for default extended prompt-cache retention,
the deployment bound to the Context Cache container was called first and returned
`cached_tokens=0`. It is published unchanged. A controlled test that returns a negative
result is evidence, and suppressing it would invalidate the rest of this evidence set.

`manifest.json` records the exact byte count and SHA-256 of both sanitized evidence files.