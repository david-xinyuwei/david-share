"""Build-time compatibility gate for the consolidated verl image."""

from __future__ import annotations

import inspect
from importlib import metadata

import accelerate
import torch
import transformers
from accelerate import init_empty_weights
from accelerate.big_modeling import init_on_device


def probe_empty_weights() -> TypeError | None:
    """Return the transformers-v5 parameter error, or None when accelerate guards it."""
    try:
        with init_empty_weights():
            module = torch.nn.Linear(4, 4)
            parameter = torch.nn.Parameter(torch.empty(4, 4))
            parameter._is_hf_initialized = True
            module.weight = parameter
    except TypeError as error:
        return error
    return None


def main() -> int:
    failure = probe_empty_weights()
    guarded = "_is_hf_initialized" in inspect.getsource(init_on_device)
    print(
        "VERIFY_STACK",
        f"verl={metadata.version('verl')}",
        f"torch={torch.__version__}",
        f"torch_cuda={torch.version.cuda}",
        f"vllm={metadata.version('vllm')}",
        f"transformers={transformers.__version__}",
        f"accelerate={accelerate.__version__}",
        f"accelerate_guarded={guarded}",
        f"empty_weights_error={failure!r}",
        flush=True,
    )
    if failure is not None:
        raise SystemExit("accelerate still forwards _is_hf_initialized into Parameter.__new__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
