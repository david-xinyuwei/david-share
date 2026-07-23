# Contributing

## Change rules

- Keep the evidence contract provider-neutral and public-safe.
- Add focused tests for every new scenario pattern, assertion, or event type.
- Use synthetic records only under `tests/fixtures/`; never label fixtures as hosted-run evidence.
- Keep runtime code free of third-party dependencies unless a real requirement justifies one.
- Update `README.md` and `README-CN.md` together with matching heading, table, code-block, and image structure.
- Run the full quality gate before opening a pull request.

## Local gate

```bash
python -m pip install -r requirements-dev.txt
python -m pip install -e .
python scripts/build_public_evidence.py
python scripts/validate_evidence.py
python scripts/validate_readmes.py
python scripts/validate_repo.py
python scripts/protocol_summary_differential.py
python scripts/check_lfs_pointers.py
ruff check src tests scripts
pytest -q
python -m build --wheel
python scripts/package_smoke.py
```

Generated Schema, matrix, and manifest must not change after rebuilding from committed sources.

## Add or change a scenario pattern

The committed eight-scenario matrix is a fixed campaign contract. Changing its IDs or count is a versioned contract change, not a documentation-only edit.

1. Add or update the public-safe assertion shape under `evidence/sanitized-runs/`.
2. Add `_validate_<pattern>()` in `src/lra_resilience/evidence.py`, then route the pattern from `_validate_scenario()`.
3. Update `EXPECTED_SCENARIOS` only when the campaign scope intentionally changes.
4. Add one passing case and at least one fail-closed case in `tests/test_evidence.py`.
5. Update `data/evidence-contract.schema.json`, both README scenario tables, and the EN/CN evidence-contract docs.
6. Rebuild the matrix and manifest, then run the full local gate.

`tests/fixtures/` contains synthetic parser inputs only. A new live-result assertion must come from an authenticated run, be sanitized outside the public repo, and remain clearly distinguishable from a test fixture.

## Bilingual and generated assets

`scripts/validate_readmes.py` checks heading levels, code-block languages, table shapes, image order, local links, all eight scenario IDs, and critical scope statements across both READMEs.

Canonical bilingual PNGs are generated with Pillow 12.3.0. Set `LRA_CJK_FONT` to a CJK-capable font before regenerating localized images. Font rasterization is platform-specific, so CI validates committed image presence, dimensions, and variance instead of comparing cross-platform pixel bytes. Every changed image must also be opened and reviewed for text rendering, clipping, overlap, caption accuracy, and public-boundary safety. Do not edit generated images manually.

`scripts/validate_readmes.py` is a deterministic structure, link, numeric-claim, and critical-boundary gate. It does not prove native-language quality by itself. Native Chinese and bilingual semantic review remain required for an external delivery.

Delete local `build/`, `dist/`, `.venv/`, and `*.egg-info/` directories when they are no longer needed; all are ignored and must never be staged.
