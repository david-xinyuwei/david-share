# Validation Notes

This repo has three validation layers.

## 1. Static Repo Check

```bash
python scripts/repo_check.py
```

Checks:

- required files exist,
- Python files compile,
- manifest/config files contain the expected key text,
- obvious secret patterns are not present in commit-worthy files.

## 2. Toolbox MCP Listing

```bash
python scripts/verify_toolbox.py --endpoint "$TOOLBOX_MCP_ENDPOINT"
```

Expected output includes at least `code_interpreter`.

## 3. End-to-End Agent Smoke Test

```bash
python scripts/smoke_test.py
```

Expected markers:

```text
WEB_RESULT_START
...
WEB_RESULT_END
CODE_RESULT_START
...
CODE_RESULT_END
```

The code path should return `55` for the sum of squares from 1 through 5.

## 4. HTTP Responses Server Test

Terminal 1:

```bash
python main.py
```

Terminal 2:

```bash
python scripts/http_smoke_test.py --base-url http://localhost:8088
```

Use `--skip-web` if you only want to validate the Toolbox `code_interpreter` path:

```bash
python scripts/http_smoke_test.py --skip-web
```