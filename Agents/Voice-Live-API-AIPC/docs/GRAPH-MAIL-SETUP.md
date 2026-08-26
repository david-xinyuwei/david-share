# Microsoft Graph Mail Setup

The application can send real email through Microsoft Graph after an explicit request and a separate later confirmation of the exact action. Recipient allowlisting is mandatory.

## App registration

1. Register a Microsoft Entra application.
2. Configure it as a public client and enable public-client flows.
3. Add delegated Microsoft Graph permission `Mail.Send`.
4. Apply tenant/user consent according to organizational policy.
5. Put only the application ID and authority in the local `.env`; never commit the token cache.

```ini
MAIL_TRANSPORT=graph
GRAPH_CLIENT_ID=<your-public-client-application-id>
GRAPH_AUTHORITY=https://login.microsoftonline.com/<your-tenant-id>
MAIL_DEFAULT_RECIPIENT=user@example.com
MAIL_ALLOWED_RECIPIENTS=user@example.com
```

For personal Microsoft accounts, use the `consumers` authority. Run the one-time login:

```powershell
.\.venv\Scripts\python.exe -m scripts.graph_login
```

## Token lifecycle

MSAL acquires short-lived access tokens and silently refreshes them from the local delegated cache when possible. Interactive login is required again when consent is revoked, account security state changes, the refresh grant becomes unusable after inactivity, or `.msal_token_cache.json` is removed.

Every cache read first validates that the Windows DACL is non-inherited and grants Full Control only to the current SID and `SYSTEM`. Insecure primary or fallback caches are rejected. A valid fallback is migrated through the secured writer and revalidated before deserialization. Updates use a temporary file, flush it to disk, secure it, and then atomically replace the old cache.

## Safety checks

- Empty `MAIL_ALLOWED_RECIPIENTS` rejects all delivery.
- Unknown recipients and header newlines are rejected.
- Subject and body length limits are enforced before any transport call.
- A one-time token bound to the exact recipient, subject, and body requires a new explicit confirmation turn; token replay, expiry, cancellation, and changed arguments are rejected.
- The cache is equivalent to a credential and must remain outside Git, support bundles, screenshots, logs, and published archives.
- Use a synthetic recipient and subject for validation; never publish message content or account identifiers.
