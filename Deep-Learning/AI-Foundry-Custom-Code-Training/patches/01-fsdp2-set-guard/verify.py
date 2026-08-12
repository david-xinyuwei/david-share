"""Reports whether verl's apply_fsdp2 can survive a set-valued _no_split_modules.

Exit code 0 means the guard is present, 1 means it is missing. Safe to run before and
after apply.py to capture the differential.
"""

import sys
from pathlib import Path

import transformers
import verl
import verl.utils.fsdp_utils as fsdp_utils

GUARD_FRAGMENT = "isinstance(fsdp_transformer_layer_cls_to_wrap, set)"
ANCHOR_FRAGMENT = "fsdp_transformer_layer_cls_to_wrap[0] is not None"

path = Path(fsdp_utils.__file__)
source = path.read_text(encoding="utf-8")
present = GUARD_FRAGMENT in source

print(f"VERIFY_FSDP2 verl={verl.__version__} transformers={transformers.__version__}")
print(f"VERIFY_FSDP2 file={path}")
print(f"VERIFY_FSDP2 guard_present={present}")

for number, line in enumerate(source.splitlines(), start=1):
    if ANCHOR_FRAGMENT in line or GUARD_FRAGMENT in line:
        print(f"VERIFY_FSDP2 line={number}: {line.strip()}")

sys.exit(0 if present else 1)
