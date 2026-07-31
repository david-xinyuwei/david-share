# Offline Frozen-Dispute Example

These six synthetic cases exercise the differential workflow without a model endpoint or Docker.

```bash
python scripts/build_dispute_manifest.py \
  --reference-report examples/reference-report.json \
  --candidate-report examples/candidate-report.json \
  --expected-count 6 \
  --output outputs/example/frozen-disputes.tsv

python scripts/finalize_frozen_disputes.py \
  --reference-report examples/reference-report.json \
  --baseline-report examples/candidate-report.json \
  --expected-count 6 \
  --dispute-manifest outputs/example/frozen-disputes.tsv \
  --retest-report examples/retest-shard-a.json \
  --retest-report examples/retest-shard-b.json \
  --output-dir outputs/example/final
```

Expected result:

- Frozen bidirectional disputes: 4
- Final Resolved: 3/6
- Accuracy: 50.00%

The files are synthetic test fixtures, not measured model results.
