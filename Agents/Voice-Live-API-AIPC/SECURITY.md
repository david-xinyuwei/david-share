# Security Policy

## Supported Versions

Security fixes apply to the latest revision of the `master` branch.

## Report a Vulnerability

Do not open a public issue containing credentials, personal data, private endpoints, customer identifiers, or exploit details. Use GitHub private vulnerability reporting when available and include the affected revision, impact, and a minimal reproduction with synthetic data.

## Security Boundaries

- All Azure, WebIQ, SMTP, and Microsoft Graph credentials remain local and must never be committed.
- Device-control tools run only on the local Windows host; they are not cloud-side capabilities.
- Mail delivery requires a configured recipient allowlist and a second, later user utterance that explicitly confirms the exact subject, body, and recipient. Subject and body sizes are bounded before Graph/SMTP is called.
- Camera open/capture, timezone, power, wallpaper, image generation, and mail actions use one-time confirmation tokens bound to the exact arguments. Only one protected action may be pending. Competing, changed, replayed, expired, same-turn, or cancelled actions fail closed.
- Application launch is restricted to fixed Windows system paths. Wallpaper paths are constrained locally; every remote HTTPS hop rejects non-global DNS answers and pins TLS to the validated IP while retaining original-host certificate verification.
- Camera frames and generated artifacts are local runtime data under ignored directories.
- Graph token-cache reads fail closed unless the Windows DACL is non-inherited and grants Full Control only to the current SID and `SYSTEM`. Updates are atomic and secured before replacement.
- Tool UI events and logs record names, field names, status, and timing; they do not record full arguments or results.
- External dependency failures are returned explicitly; production code has no mock-data fallback.

## Before Sharing Logs

Remove access tokens, API keys, email addresses, resource names, tenant/subscription identifiers, endpoint hosts, local paths, camera frames, and message content.
