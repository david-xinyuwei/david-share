# Public Evidence Boundary

`verified-run-summary.json` is a sanitized, single-run observation produced by the pinned
official Quickstart. It retains the six response rows needed to recompute the cache result.

It intentionally omits subscription and tenant identifiers, resource IDs, endpoint names,
user identities, email threads, and the private raw Azure deployment records. The included
latency values prove only what happened in that run. They are not a production benchmark,
an SLA, or a pricing claim.

`validation-history.json` discloses two complete runs and two later runs that the hardened
parser rejected because the official concurrent demo reported transport errors. Rejected
runs are not scored or converted into passes.

`manifest.json` records the exact byte count and SHA-256 of both sanitized evidence files.