# Security Policy

## Supported Versions

Security fixes are applied to the latest revision of the `main` branch.

## Reporting a Vulnerability

Do not open a public issue containing credentials, meeting content, personal data, customer identifiers, or exploit details.

Report vulnerabilities through GitHub private vulnerability reporting when it is available for this repository. Include:

- the affected file and revision;
- the security impact;
- minimal reproduction steps using synthetic data;
- any suggested mitigation.

Please allow reasonable time for triage before public disclosure.

## Security Boundaries

- This project creates an unsent EML draft and does not transmit mail.
- The Windows launcher uses an isolated Azure CLI profile and the runtime uses `AzureCliCredential`; no secret belongs in source control.
- Managed Agent endpoints must use HTTPS on the `*.services.ai.azure.com` Foundry domain. Tokens are never sent to arbitrary hosts, userinfo URLs, or custom ports.
- The local artifact backend binds only to `127.0.0.1` and rejects request bodies above 2 MiB.
- Meeting events are untrusted input and may contain sensitive organizational data.
- Windows runtime files are stored under `%LOCALAPPDATA%`, outside the source tree and OneDrive project folder. Operators are responsible for retention and manual purge after review.
- Deterministic test fixtures are isolated under `tests/` and are not available through product runtime or CLI paths.
- Generated summaries and attachments require human review.