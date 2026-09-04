# Product UI evidence

| Asset | Source class | Run / date | Crop and dimensions | Claim boundary |
|---|---|---|---|---|
| `deploy-dialog-managed-compute.png` | `LOCAL_MEASUREMENT` | `foundry-deploy-dialog-20260904` / 2026-09-04 | Single uncropped screenshot with a red box around the Deployment template field; 3035 × 1683 | Shows Deployment type `Global Managed Compute` and the Deployment template list of GPU SKUs; does not identify the measured run or prove network behavior |

The dialog shows no account, project, endpoint, identity, tenant, or subscription
identifiers. The image was not redrawn and the displayed values
were not altered. SHA-256, configuration scope, and claim boundaries
are recorded in [`../../evidence/ui-evidence.json`](../../evidence/ui-evidence.json).

The inline Mermaid traffic diagram is `AUTHOR_SYNTHESIS`. Microsoft Foundry's
official network-isolation diagram was checked but is broader than this run; the
custom diagram adds the measured public-block/private-allow differential. Its
sources and non-claims are recorded in the same ledger.
