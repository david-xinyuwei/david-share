# 脱敏证据

`sanitized-runs/` 下的文件来自经过身份验证的 Hosted 实测，是可公开 attestation。它们不是 synthetic fixture，也不是 raw event log。

原始证据可能包含 service endpoint、不可变任务标识、环境 metadata 和生成内容，因此继续保留在私有边界内。公开文件只保留判断文档主场景所需的 assertion。

运行 `python scripts/build_public_evidence.py` 可重建 `data/validation-matrix.json` 与 `evidence/manifest.json`；随后运行 `python scripts/validate_evidence.py`，验证契约和所有 hash。

Parser regression 使用的 synthetic events 独立放在 `tests/fixtures/`，并在 `scenario-manifest.json` 中标为 `test-fixture`。
