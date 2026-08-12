"""Pure source-to-source transforms behind the patches.

Kept free of verl imports so the transformation logic can be tested without a GPU box,
a CUDA build, or verl installed. Each `apply.py` only locates the installed file and
delegates here.

Every function raises `PatchError` rather than returning partially-patched source, so a
caller can treat "no exception" as "safe to write".
"""

import re


class PatchError(RuntimeError):
    """Raised when the source does not look the way the patch expects."""


FSDP2_ANCHOR = "fsdp_transformer_layer_cls_to_wrap[0] is not None"
FSDP2_GUARD = "isinstance(fsdp_transformer_layer_cls_to_wrap, set)"

_DIV_STATEMENT = re.compile(
    r"^(?P<indent>\s*)(?P<name>[A-Za-z_][A-Za-z0-9_]*)\.div_\(temperature\)\s*$"
)


def add_fsdp2_set_guard(source: str) -> str:
    """Coerce `_no_split_modules` to a list before verl subscripts it.

    transformers v5 turned that attribute into a set. Returns the source unchanged if the
    guard is already present.
    """
    if FSDP2_GUARD in source:
        return source

    lines = source.splitlines(keepends=True)
    targets = [i for i, line in enumerate(lines) if FSDP2_ANCHOR in line]
    if len(targets) != 1:
        raise PatchError(f"expected exactly 1 anchor, found {len(targets)}")

    index = targets[0]
    indent = lines[index][: len(lines[index]) - len(lines[index].lstrip())]
    lines.insert(
        index,
        f"{indent}if isinstance(fsdp_transformer_layer_cls_to_wrap, set):\n"
        f"{indent}    fsdp_transformer_layer_cls_to_wrap = list(fsdp_transformer_layer_cls_to_wrap)\n",
    )
    return "".join(lines)


def make_temperature_div_out_of_place(source: str) -> tuple[str, list[int]]:
    """Rewrite `x.div_(temperature)` to `x = x.div(temperature)`.

    Numerically identical, but allocates instead of mutating a view, which autograd
    forbids when the view came out of a gradient-checkpointing custom Function.

    Returns the new source and the 1-based line numbers changed. Raises if any occurrence
    is not a standalone expression statement, since rewriting those needs human judgement.
    """
    lines = source.splitlines(keepends=True)
    out: list[str] = []
    changed: list[int] = []

    for index, line in enumerate(lines):
        match = _DIV_STATEMENT.match(line.rstrip("\n"))
        if match is None:
            if ".div_(temperature)" in line:
                raise PatchError(f"line {index + 1} is not a standalone statement: {line.strip()}")
            out.append(line)
            continue
        name = match.group("name")
        out.append(f"{match.group('indent')}{name} = {name}.div(temperature)\n")
        changed.append(index + 1)

    return "".join(out), changed
