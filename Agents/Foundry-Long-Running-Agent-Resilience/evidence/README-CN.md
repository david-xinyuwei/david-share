# 脱敏证据

`sanitized-runs/` 下的文件是从私有 authenticated Hosted run 提炼的作者证明公开 record。它们不是 synthetic fixture，也不是 raw event log。公开读者可以验证精确 contract 与 committed hash，但无法独立 replay 被保留的 execution。

原始证据可能包含 service endpoint、不可变任务标识、环境 metadata 和生成内容，因此继续保留在私有边界内。公开文件只保留判断文档主场景所需的 assertion。

每个 record 都包含由保留的私有 source artifact SHA-256 值生成的 commitment。作者可以用它发现后续 source drift，同时不公开文件名或内容。它不是 digital signature，也不是私有 execution 确实发生的公开证明。

运行 `python scripts/build_public_evidence.py` 可重建 `data/validation-matrix.json` 与 `evidence/manifest.json`；随后运行 `python scripts/validate_evidence.py`，验证契约和所有 hash。

Parser regression 使用的 synthetic events 独立放在 `tests/fixtures/`，并在 `scenario-manifest.json` 中标为 `test-fixture`；committed campaign record 使用 `sanitized-runtime-attestation`。
