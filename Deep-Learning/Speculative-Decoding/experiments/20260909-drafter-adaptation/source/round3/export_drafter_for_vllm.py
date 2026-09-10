#!/usr/bin/env python3
"""Export a trained drafter in the on-disk layout of the released DFlash 2 checkpoint.

``DFlash2DraftModel.from_pretrained`` in the dflash package renames the released
selector keys ``candidate_selector.<codebook>`` to ``...<codebook>.weight``. Our
checkpoints are saved by ``save_pretrained`` and therefore already carry ``.weight``.
vLLM's loader was written against the released files, so this script writes a copy
with the released key names and verifies that the two key sets otherwise coincide.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from safetensors.torch import load_file, save_file

RENAME = {
    "candidate_selector.predecessor_codebook.weight": "candidate_selector.predecessor_codebook",
    "candidate_selector.successor_codebook.weight": "candidate_selector.successor_codebook",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="our save_pretrained() directory")
    parser.add_argument("--reference", required=True, help="released checkpoint directory")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    source, reference, output = Path(args.source), Path(args.reference), Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    ref_keys = set()
    for file in reference.glob("*.safetensors"):
        ref_keys |= set(load_file(str(file)).keys())

    tensors = {}
    for file in source.glob("*.safetensors"):
        tensors.update(load_file(str(file)))
    renamed = {RENAME.get(key, key): value for key, value in tensors.items()}

    missing = sorted(ref_keys - set(renamed))
    extra = sorted(set(renamed) - ref_keys)
    report = {"source_keys": len(tensors), "reference_keys": len(ref_keys),
              "renamed": sorted(k for k in tensors if k in RENAME),
              "missing_vs_reference": missing, "extra_vs_reference": extra}
    print(json.dumps(report, indent=2))
    if missing or extra:
        raise SystemExit("EXPORT_KEY_MISMATCH")

    save_file(renamed, str(output / "model.safetensors"), metadata={"format": "pt"})
    for name in ("config.json",):
        shutil.copy2(source / name, output / name)
    # Non-weight files the serving stack may look for come from the released layout.
    for file in reference.iterdir():
        if file.suffix in {".json", ".txt", ".md", ".jinja"} and not (output / file.name).exists():
            shutil.copy2(file, output / file.name)
    print(json.dumps({"exported": str(output), "files": sorted(p.name for p in output.iterdir())}))
    print("EXPORT_DRAFTER=PASS")


if __name__ == "__main__":
    main()
