# Attribution and Licensing

This subtree contains original validation scripts, tests, diagrams, and documentation under
the parent repository's MIT License.

The runtime dependency is the public repository
[`Azure/AzureContextCache`](https://github.com/Azure/AzureContextCache), pinned to commit
[`7d1029a5`](https://github.com/Azure/AzureContextCache/commit/7d1029a5e8b59b1805e70992c85ffe6798d2f47a).

The pinned upstream commit does not contain a license file. Consequently, this project does
not check upstream source files into the public subtree. At execution time, the runner obtains
an official Git object source, verifies all 25 executable-input Git blob SHA-256 values, and
materializes those exact bytes into a temporary private run directory before invoking them.
The MIT License in this repository does not grant rights to upstream code.

The checked-in sanitized evidence has two explicitly separated lineages:

- `verified-run-summary.json` and the historical Quickstart rows in
	`validation-history.json` are derived from executions of the pinned official Quickstart.
- `paired-prefix-follow-up.json` and `scripts/paired_prefix_probe.py` are original work in
	this repository. The probe preserves the official Responses API request shape while
	assigning a distinct content-keyed prefix to each comparison arm; it is not presented as
	Microsoft-authored code or as an official product test.

Both evidence lineages contain only numeric call observations and public product metadata;
private cloud and identity fields are omitted.