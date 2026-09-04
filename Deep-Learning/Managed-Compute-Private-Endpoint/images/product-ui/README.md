# Product UI evidence

| Asset | Source class | Run / date | Crop and dimensions | Claim boundary |
|---|---|---|---|---|
| `deployment-facts.png` | `LOCAL_MEASUREMENT` | `managed-compute-private-link-dedicated-20260831` / 2026-08-31 | Four field-level crops combined; 1318 × 583 | Identifies the model, `GlobalManagedCompute`, `Succeeded`, and `H100_80GB`; does not prove network behavior |

Account, project, deployment, endpoint, identity, tenant, and subscription
identifiers are omitted. The image was not redrawn and the displayed values
were not altered. SHA-256, redactions, configuration scope, and claim boundaries
are recorded in [`../../evidence/ui-evidence.json`](../../evidence/ui-evidence.json).

The inline Mermaid traffic diagram is `AUTHOR_SYNTHESIS`. Microsoft Foundry's
official network-isolation diagram was checked but is broader than this run; the
custom diagram adds the measured public-block/private-allow differential. Its
sources and non-claims are recorded in the same ledger.
