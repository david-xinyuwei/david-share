# Attribution and Licensing

This subtree contains original validation scripts, tests, diagrams, and documentation under
the parent repository's MIT License.

The runtime dependency is the public repository
[`Azure/AzureContextCache`](https://github.com/Azure/AzureContextCache), pinned to commit
[`7d1029a5`](https://github.com/Azure/AzureContextCache/commit/7d1029a5e8b59b1805e70992c85ffe6798d2f47a).

The pinned upstream commit does not contain a license file. Consequently, this project does
not copy, modify, or redistribute upstream source files. The runner obtains the repository
from its official URL at execution time and verifies its Git blob content SHA-256 values
before invoking it.
The MIT License in this repository does not grant rights to upstream code.

The checked-in sanitized evidence is derived from an execution of the official Quickstart.
It contains only numeric call observations and public product metadata; private cloud and
identity fields are omitted.