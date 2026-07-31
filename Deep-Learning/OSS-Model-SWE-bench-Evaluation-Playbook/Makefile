.PHONY: test validate

test:
	python3 -m unittest discover -s tests -v

validate:
	python3 -m py_compile scripts/*.py tests/*.py
	bash -n scripts/setup_environment.sh scripts/run_generation.sh scripts/run_official_harness.sh
	python3 scripts/validate_repo.py .
