# Historical Evidence with Withdrawn 256K Rows

This directory preserves the original client logs and derived files from `tuned_moe_retest_20260713T014113Z`. It is not the current 256K acceptance source.

The following historical rows are withdrawn:

- 1P1D Prefill 256K/concurrency-4: `39,905.41 tok/s`
- DP=2 Prefill 256K/concurrency-4: `74,611.25 tok/s`
- DP=2 Prefill 256K/concurrency-8: `78,613.96 tok/s`

The historical `accepted_dp2_context_length=262149` validation is superseded. This runtime exposes `max_req_input_len=262143` at that context length. Current 256K acceptance requires context length 262151 and direct `/server_info` evidence showing `max_req_input_len>=262145`.

Before consuming `results.json`, `RESULTS.md`, or `checks/validation.txt`, apply the machine-readable validity map in [`STATUS.json`](STATUS.json). See [`STATUS.md`](STATUS.md) for the evidence boundary and the current corrected bundle.