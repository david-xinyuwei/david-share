"""Behaviour tests for the patch transforms. No GPU, CUDA, or verl install required.

    pip install pytest && pytest tests/
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "patches"))

from transforms import (  # noqa: E402
    PatchError,
    add_fsdp2_set_guard,
    make_temperature_div_out_of_place,
)

FSDP2_SOURCE = """\
def apply_fsdp2(model, config):
    fsdp_transformer_layer_cls_to_wrap = model._no_split_modules
    assert fsdp_transformer_layer_cls_to_wrap[0] is not None, "no layer class"
    return wrap(model, fsdp_transformer_layer_cls_to_wrap)
"""


class TestFsdp2SetGuard:
    def test_inserts_guard_above_the_anchor(self):
        patched = add_fsdp2_set_guard(FSDP2_SOURCE)
        lines = patched.splitlines()
        guard_line = next(i for i, l in enumerate(lines) if "isinstance" in l)
        anchor_line = next(i for i, l in enumerate(lines) if "[0] is not None" in l)
        assert guard_line < anchor_line

    def test_guard_matches_anchor_indentation(self):
        patched = add_fsdp2_set_guard(FSDP2_SOURCE)
        guard = next(l for l in patched.splitlines() if "isinstance" in l)
        assert guard.startswith("    if ")

    def test_is_idempotent(self):
        once = add_fsdp2_set_guard(FSDP2_SOURCE)
        assert add_fsdp2_set_guard(once) == once

    def test_result_is_valid_python(self):
        compile(add_fsdp2_set_guard(FSDP2_SOURCE), "<patched>", "exec")

    def test_rejects_missing_anchor(self):
        with pytest.raises(PatchError, match="found 0"):
            add_fsdp2_set_guard("def apply_fsdp2(model, config):\n    return model\n")

    def test_rejects_ambiguous_anchor(self):
        with pytest.raises(PatchError, match="found 2"):
            add_fsdp2_set_guard(FSDP2_SOURCE + FSDP2_SOURCE)


class TestTemperatureDiv:
    def test_rewrites_to_out_of_place(self):
        source = "def f(self, x):\n    logits_rmpad.div_(temperature)\n    return logits_rmpad\n"
        patched, changed = make_temperature_div_out_of_place(source)
        assert "logits_rmpad = logits_rmpad.div(temperature)" in patched
        assert ".div_(temperature)" not in patched
        assert changed == [2]

    def test_preserves_indentation_and_variable_name(self):
        source = "class A:\n    def f(self):\n        my_logits.div_(temperature)\n"
        patched, _ = make_temperature_div_out_of_place(source)
        assert "        my_logits = my_logits.div(temperature)\n" in patched

    def test_handles_multiple_occurrences(self):
        source = "a.div_(temperature)\nb = 1\nc.div_(temperature)\n"
        _, changed = make_temperature_div_out_of_place(source)
        assert changed == [1, 3]

    def test_is_idempotent(self):
        source = "logits.div_(temperature)\n"
        once, _ = make_temperature_div_out_of_place(source)
        twice, changed = make_temperature_div_out_of_place(once)
        assert twice == once
        assert changed == []

    def test_result_is_valid_python(self):
        source = "def f():\n    logits.div_(temperature)\n"
        patched, _ = make_temperature_div_out_of_place(source)
        compile(patched, "<patched>", "exec")

    def test_leaves_unrelated_div_calls_alone(self):
        source = "x = y.div_(2)\nz.div_(scale)\n"
        patched, changed = make_temperature_div_out_of_place(source)
        assert patched == source
        assert changed == []

    @pytest.mark.parametrize(
        "line",
        [
            "out = logits.div_(temperature)",       # result is bound
            "if logits.div_(temperature): pass",    # used in a condition
            "f(logits.div_(temperature))",          # passed as an argument
        ],
    )
    def test_refuses_non_standalone_forms(self, line):
        with pytest.raises(PatchError, match="not a standalone statement"):
            make_temperature_div_out_of_place(line + "\n")
