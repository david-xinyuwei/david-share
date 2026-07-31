#!/usr/bin/env python3
import argparse
import os
from pathlib import Path

from swebench_outcomes import sha256


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, default=Path("SHA256SUMS.txt"))
    args = parser.parse_args()

    root = args.root.resolve()
    output = args.output.resolve()
    if not root.is_dir():
        raise ValueError(f"Asset root is not a directory: {root}")
    files = []
    for current, directories, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in directories:
            path = current_path / name
            if path.is_symlink():
                raise ValueError(f"Symbolic links are not allowed in evidence: {path}")
        for name in filenames:
            path = current_path / name
            if path.is_symlink():
                raise ValueError(f"Symbolic links are not allowed in evidence: {path}")
            if path.resolve() != output:
                files.append(path)
    files.sort()
    if not files:
        raise ValueError(f"No files found under asset root: {root}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "".join(f"{sha256(path)}  {path.relative_to(root).as_posix()}\n" for path in files)
    )
    print(f"ASSET_MANIFEST=PASS files={len(files)} output={output}")


if __name__ == "__main__":
    main()
