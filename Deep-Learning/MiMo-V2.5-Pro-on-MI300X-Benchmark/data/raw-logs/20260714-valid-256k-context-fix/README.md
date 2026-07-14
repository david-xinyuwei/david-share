# Valid 1P1D 256K Context-Fix Evidence

This directory contains sanitized excerpts from the checksum-verified two-node 1P1D 256K/concurrency-4 confirmation.

- The AMD client workload is unchanged: 262,144 input tokens, output length 1, concurrency 4, 16 prompts, one warmup, cache flush, seed 12345, and PD separation.
- The only launch-parameter change is `--context-length 262144` to `262151` on both Prefill and Decode.
- Both `/server_info` responses report `max_req_input_len=262145`.
- The valid run completed 16/16 successful requests and 16/16 retokenized outputs at 12,393.19 input tok/s.
- The false-success excerpt shows 16 client-reported successes but only 5 retokenized outputs. Eleven matching context-overflow lines are included separately.

Full service logs are not published because they contain internal addresses and runtime paths. The public excerpts contain no credentials, internal IP addresses, or private filesystem locations.

See [`../../../reports/20260714-valid-reproduction-and-256k-context-fix.md`](../../../reports/20260714-valid-reproduction-and-256k-context-fix.md) for the interpretation and comparison boundary.