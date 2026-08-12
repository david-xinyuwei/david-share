"""Reports whether verl's temperature scaling is in-place.

Exit code 0 means every occurrence is out-of-place, 1 means at least one in-place call
remains. Safe to run before and after apply.py to capture the differential.
"""

import sys
from pathlib import Path

import torch
import verl
import verl.workers.actor.dp_actor as dp_actor

path = Path(dp_actor.__file__)
source = path.read_text(encoding="utf-8")

inplace = source.count(".div_(temperature)")
outofplace = source.count(".div(temperature)")

print(f"VERIFY_DP_ACTOR verl={verl.__version__} torch={torch.__version__}")
print(f"VERIFY_DP_ACTOR file={path}")
print(f"VERIFY_DP_ACTOR inplace_div={inplace} outofplace_div={outofplace}")

for number, line in enumerate(source.splitlines(), start=1):
    if "div" in line and "temperature" in line:
        print(f"VERIFY_DP_ACTOR line={number}: {line.strip()}")

sys.exit(0 if inplace == 0 else 1)
