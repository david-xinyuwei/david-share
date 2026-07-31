# Maintainer Validation

## Fast Gate

```bash
make validate
make test
```

## Clean Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
bash scripts/setup_environment.sh
python -m minisweagent.run.benchmarks.swebench --help
python -m swebench.harness.run_evaluation --help
```

The default setup consumes `requirements-lock.txt`; SWE-bench itself is installed from the pinned editable source checkout.

## Script Checks

```bash
python3 -m py_compile scripts/*.py tests/*.py
bash -n scripts/setup_environment.sh scripts/run_generation.sh scripts/run_official_harness.sh
python3 -m unittest discover -s tests -v
```

## Public Boundary Scan

```bash
grep -RInE 'api[_-]?key\s*[:=]\s*[^<$ ]|Bearer [A-Za-z0-9._-]+|root@|/mnt/[a-z]/|[A-Z]:\\' . \
  --exclude-dir=.git --exclude='*.png'
```

Review findings in context. Placeholder names and security documentation are not secrets.

## Documentation Checks

```bash
python3 scripts/validate_repo.py .
```

`make validate` checks Python and Shell syntax. The Repo validator checks required files, local links, bilingual heading/code-block shape, forbidden private-path patterns, symlinks, pinned versions, and secret-in-argv regressions while pruning ignored dependency and runtime directories.
