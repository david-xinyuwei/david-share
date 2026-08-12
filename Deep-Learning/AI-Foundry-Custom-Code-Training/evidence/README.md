# Evidence

Every claim in the READMEs and in [`../docs/troubleshooting.md`](../docs/troubleshooting.md)
traces to a run recorded here.

## What is in scope

These runs were executed on our own subscription against a managed 4× A100 80GB PCIe node.
Published here:

- **Run timeline** — per attempt: what changed, how long the container ran, where it died.
- **Log excerpts** — the lines around each failing call stack, enough to match the
  signature against your own logs.
- **Config observations** — the runtime config paths that the fixes target.

## What is removed, and why

Excerpts are trimmed rather than raw. Removed: subscription, tenant and resource
identifiers, cluster-internal hostnames and pod IPs, container scratch paths containing run
GUIDs, and registry coordinates for images we built. None of these change a signature or
a conclusion; all of them are specific to one environment.

Nothing that supports a technical claim has been removed. Where a path matters — a file
inside `site-packages`, a line number in a verl module — it is kept verbatim.

## Reading the excerpts

Excerpts were produced with [`../tools/scan_job_log.ps1`](../tools/scan_job_log.ps1),
which collapses consecutive repeats and drops known noise families. That matters here: one
of these runs emitted roughly 200 identical NCCL transport warnings on top of the single
`TypeError` that actually killed it. The unfiltered file is not more informative, only
longer.

Line numbers in excerpt headers refer to positions in the full job log, so the ordering
between excerpts is preserved even though the gaps are not shown.
