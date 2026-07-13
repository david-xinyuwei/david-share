# Evidence Status

Run: `tuned_moe_retest_20260713T014113Z`

This directory is immutable historical evidence. Its client logs, derived JSON, Markdown, and SHA-256 manifest are preserved as originally published; they are not the current 256K acceptance source.

Machine-readable status: [`STATUS.json`](STATUS.json). Consumers must apply that validity map before reading the historical `results.json` or `RESULTS.md`.

## Valid Rows

- Decode 8K/1K at concurrency 16/32/64/128.
- 1P1D Prefill 8K/1 and 64K/1 at concurrency 4.
- DP=2 Prefill 8K/1 and 64K/1 at concurrency 4/8.

## Withdrawn Rows

- 1P1D Prefill 256K/1 at concurrency 4 (`39,905.41 tok/s` client summary).
- DP=2 Prefill 256K/1 at concurrency 4 (`74,611.25 tok/s` client summary).
- DP=2 Prefill 256K/1 at concurrency 8 (`78,613.96 tok/s` client summary).

The historical 262149 retry is also invalid for a 262,144-token input. In this runtime it exposes `max_req_input_len=262143`; a valid request requires context length 262151 and direct `/server_info` evidence showing `max_req_input_len>=262145`.

Use the corrected current bundle:

- [`../../../scripts/20260713-amd-tuned-moe-expanded-concurrency/`](../../../scripts/20260713-amd-tuned-moe-expanded-concurrency/)
- [`../../../reports/20260713-amd-tuned-moe-retest.md`](../../../reports/20260713-amd-tuned-moe-retest.md) for the erratum