# Security

## Reporting

Use [GitHub private vulnerability reporting](https://github.com/david-xinyuwei/david-share/security/advisories/new)
for suspected security issues. Do not open a public issue containing credentials or Azure
resource identifiers.

## Runtime Boundary

- Use a dedicated `AZURE_CONFIG_DIR`; do not rely on a shared default Azure CLI cache.
- Keep `.azure/`, `runtime/`, `live-evidence/`, `.env`, and raw logs outside Git.
- The runner does not accept API keys and does not invoke `az login`.
- Review the subscription, resource group, region, and `-WhatIf` output before a live run.
- Treat cleanup as a separate high-impact operation. Confirm resource ownership first.

## Public Boundary

The public scanner rejects likely secrets, concrete Azure UUIDs, Azure resource IDs, work
email addresses, local absolute paths, and internal project terms. Reserved example domains
and explicit placeholders are allowed. Scanner success is a minimum gate, not a substitute
for human review.