"""Makes verl 0.7.1's temperature scaling out-of-place in DataParallelPPOActor.

`logits_rmpad.div_(temperature)` modifies a squeeze() view in place. Under
compute_log_prob that is harmless because the call runs inside torch.no_grad(), but
update_policy runs with autograd enabled and the logits originate from a gradient
checkpointing custom Function, so PyTorch refuses:

    RuntimeError: Output 0 of SqueezeBackward1 is a view and is being modified inplace.
    This view was created inside a custom Function ... This behavior is forbidden.

Rewrites each `<name>.div_(temperature)` statement to `<name> = <name>.div(temperature)`,
which is numerically identical and allocates a fresh tensor instead of aliasing the view.

Fail-closed: aborts if a `.div_(temperature)` occurrence is not a standalone statement.
Idempotent: exits 0 without writing if the file is already out-of-place.
"""

import sys
from pathlib import Path

import verl.workers.actor.dp_actor as dp_actor

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from transforms import PatchError, make_temperature_div_out_of_place  # noqa: E402

path = Path(dp_actor.__file__)
source = path.read_text(encoding="utf-8")

try:
    patched, changed = make_temperature_div_out_of_place(source)
except PatchError as error:
    print(f"PATCH_DP_ACTOR FAILED {error} file={path}")
    sys.exit(1)

if not changed:
    print(f"PATCH_DP_ACTOR already-present file={path}")
    sys.exit(0)

path.write_text(patched, encoding="utf-8")

if ".div_(temperature)" in path.read_text(encoding="utf-8"):
    print("PATCH_DP_ACTOR FAILED not-persisted")
    sys.exit(1)

print(f"PATCH_DP_ACTOR applied file={path} lines={changed}")
