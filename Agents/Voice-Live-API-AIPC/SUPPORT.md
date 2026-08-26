# Support

This public repository is a reference implementation, not a managed service or production SLA.

Before opening an issue:

1. Run `python scripts/pre_delivery_check.py` and `python -m pytest`.
2. Run `python -m scripts.preflight --mode voicelive --dry-run`.
3. Remove credentials, account/resource identifiers, local paths, camera images, and message content from all output.
4. Include Windows version, Python version, package versions, the failing mode, and the exact redacted error.

Use GitHub issues for reproducible public-source defects. Use private vulnerability reporting for security issues. Azure service availability, quota, billing, RBAC, and regional model access belong in an Azure support request with the relevant redacted request/correlation ID.
