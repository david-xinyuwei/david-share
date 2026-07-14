# July 14 Exact-Token and On-Node Evidence

This directory contains sanitized summaries from two checksum-verified two-node runs:

- `amd_onnode_source_exact_20260714T104200Z`: executed checksum-locked copies of the AMD-named on-node scripts. Six points passed; the 256K row reproduced 39,627.96 tok/s but was rejected at 5/16 retokenized outputs with eleven matching context errors on each worker.
- `amd_1p1d_256k_exacttokens_20260714T114857Z`: changed both worker context lengths to 262151 and used `--tokenize-prompt`. It completed 16/16 exact-token requests at 12,864.96 tok/s with zero context/fatal markers.

The files exclude host addresses, credentials, full environment dumps, and unrelated service output. Source-script hashes, runtime identifiers, direct-worker capacity, and client summaries are retained for verification.