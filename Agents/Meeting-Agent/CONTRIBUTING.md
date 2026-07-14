# Contributing

## Development Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pip install -e .
```

## Required Checks

Run every gate before opening a pull request:

```bash
python scripts/audit_no_send.py
python scripts/validate_evidence.py
python scripts/validate_sample_runs.py
python scripts/validate_readmes.py
python scripts/pre_delivery_check.py
ruff check src tests scripts
pytest
pip-audit -r requirements.txt --progress-spinner off
```

## Change Rules

- Preserve the provider-neutral JSONL contract or version it explicitly.
- Add focused tests for every new field, event kind, analyzer, or artifact.
- Use synthetic data in tests and committed evidence.
- Keep endpoint, deployment, and credential values in environment variables.
- Do not add SMTP, Graph `sendMail`, Outlook `.Send`, UI Send activation, or any automatic transmission path.
- Do not turn `offline-contract` into a silent fallback for Azure failures.
- Update both `README.md` and `README-CN.md` with the same heading and image structure.
- Regenerate committed sample runs after artifact changes, then run `validate_sample_runs.py`.

## Dependency Updates

- Keep every direct runtime and development dependency pinned to an exact version.
- Run `pip-audit -r requirements.txt --progress-spinner off` before accepting an update.
- For SDK, renderer, or document-library changes, regenerate both committed sample runs and review the PNG/PPTX/EML outputs.
- Major-version updates require a compatibility note and the complete security, evidence, lint, and test gate.

## Pull Request Evidence

Describe the behavior changed, validation commands run, and any remaining platform-specific risk. For visual changes, include the generated artifact path and verify that the file is nonblank and readable.