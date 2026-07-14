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
- Azure credentials are resolved by `DefaultAzureCredential`; no secret belongs in source control.
- Meeting events are untrusted input and may contain sensitive organizational data.
- The `offline-contract` analyzer is test infrastructure, not a safety or quality filter.
- Generated summaries and attachments require human review.