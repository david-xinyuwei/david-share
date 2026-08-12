"""Backports upstream verl's set-coercion guard into verl 0.7.1's apply_fsdp2.

transformers v5 exposes `_no_split_modules` as a set. verl 0.7.1 indexes it directly and
dies with "'set' object is not subscriptable" while wrapping the model for FSDP2. Upstream
verl fixed this in verl/utils/fsdp_utils.py by coercing the set to a list before the
assert; this inserts the same two lines.

Fail-closed: refuses to touch the file unless exactly one anchor is found.
Idempotent: exits 0 without writing if the guard is already present.
"""

import sys
from pathlib import Path

import verl.utils.fsdp_utils as fsdp_utils

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from transforms import FSDP2_GUARD, PatchError, add_fsdp2_set_guard  # noqa: E402

path = Path(fsdp_utils.__file__)
source = path.read_text(encoding="utf-8")

if FSDP2_GUARD in source:
    print(f"PATCH_FSDP2 already-present file={path}")
    sys.exit(0)

try:
    patched = add_fsdp2_set_guard(source)
except PatchError as error:
    print(f"PATCH_FSDP2 FAILED {error} file={path}")
    sys.exit(1)

path.write_text(patched, encoding="utf-8")

# Read back from disk so the check reflects what a fresh worker process will import.
if FSDP2_GUARD not in path.read_text(encoding="utf-8"):
    print("PATCH_FSDP2 FAILED guard-not-persisted")
    sys.exit(1)

print(f"PATCH_FSDP2 applied file={path}")
