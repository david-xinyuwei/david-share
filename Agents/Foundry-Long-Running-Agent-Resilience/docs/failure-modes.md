# Failure Modes and Adjudication

| Failure mode | Misleading conclusion | Correct response |
|---|---|---|
| Agent version is active | "The long-running scenario passed." | Run the workload through checkpoint, failure, recovery, and terminal completion. |
| A stream file reaches a byte cap | "The run ended at the last captured phase." | Treat the file as truncated; query durable state or capture the complete stream. |
| Observer token expires during the final read | "The workload failed with 403." | Separate observer authentication from workload state; refresh the token and perform a read-only final query. |
| One runtime omits another SDK's reset event at the cursor | "Recovery did not happen." | Check same-work identity, output-index continuity, reconnect cursor, and terminal completion. |
| Approval is interpreted twice | "Approve became deny." | Identify whether the hosting adapter or graph owns approval decisions; apply the contract once. |
| Background mode is omitted | "Stored response durability is broken." | Verify that the request actually selected the background/stored lifecycle required by the protocol. |
| Product onboarding is missing | "An unrelated resource provider feature must be enabled." | Distinguish service-side allowlisting from customer-configurable control-plane registration. |
| Inline shell quoting corrupts a request | "The service rejected the API payload." | Use a structured client or file-backed request and preserve the original HTTP response. |

## Adjudication rule

Prefer observable workload continuity over SDK-specific event names. A finding is accepted only when raw event order, durable state, final snapshot, or a deterministic validator supports it.
